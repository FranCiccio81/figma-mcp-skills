"""Tâches Celery de calcul des embeddings (08 §8, D06/D07/D13).

**Choix de file : ``ai``** (et non ``scoring``). Justification :

- la charge est de MÊME NATURE que celle de la file ``ai`` — appel à un
  fournisseur d'inférence, borné en débit, coûteux au token (R7),
  protégé par un circuit breaker (D18) et sujet aux mêmes incidents
  provider. Le provider local par défaut ne change pas cette nature : la
  file doit être dimensionnée pour le jour où Q11 sera tranchée en faveur
  d'un service managé ;
- la file ``scoring`` porte le moteur déterministe, dont 06 §4 exige
  qu'il ne fasse **aucun appel réseau** (cible < 50 ms). Y mettre des
  appels d'embedding mélangerait deux profils de latence opposés : un
  incident provider bloquerait le re-scoring, qui n'en dépend pas ;
- ``acks_late`` + idempotence (voir :mod:`app.ai.embeddings.backfill`)
  rendent la re-livraison sûre sur les deux files ; c'est l'isolation des
  pannes qui tranche.

Tâches exposées (noms préfixés ``ai.`` pour être routées sur la file
``ai`` par la règle ``"ai.*"`` déjà en place dans
:mod:`app.workers.celery_app`) :

- ``ai.embeddings.backfill_jobs`` — offres actives sans vecteur ;
- ``ai.embeddings.backfill_profiles`` — profils validés + intitulés
  cibles (``preference_titles``) sans vecteur ;
- ``ai.embeddings.backfill_skills`` — libellés de compétences de la
  taxonomie sans vecteur (crédit « proche », 06 §2.1) ;
- ``ai.embeddings.embed_profile`` — recalcul ciblé d'UN profil, prévu
  pour être enfilé à la validation du profil.

Boucle d'événements : même contrat que :mod:`app.workers.ingestion_tasks`
— UNE coroutine par tâche via ``asyncio.run`` sur un moteur dédié
``NullPool`` disposé en fin de coroutine.

🟡 **Non branché faute de périmètre** : l'appel de
``ai.embeddings.embed_profile`` depuis la validation de profil
(``app/modules/profiles/service.py``) — fichier hors du périmètre
autorisé de ce jalon. En attendant, les profils validés sont rattrapés
par le beat quotidien (au plus 24 h de latence ; ``title_similarity``
reste simplement inconnue, k=0, jusque-là — aucune régression).
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Sequence
from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.embeddings.backfill import (
    BackfillReport,
    EmbeddingTarget,
    compute_embeddings,
    plan_embeddings,
)
from app.ai.embeddings.base import EmbeddingProvider
from app.ai.embeddings.factory import get_embedding_provider
from app.ai.embeddings.text import (
    job_embedding_text,
    profile_embedding_text,
    skill_embedding_text,
)
from app.core.config import get_settings
from app.core.db import create_worker_engine
from app.modules.jobs.models import JobPosting
from app.modules.preferences.models import PreferenceTitle
from app.modules.profiles.models import Profile, ProfileExperience
from app.modules.referentials.models import Skill
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run[T](coro: Awaitable[T]) -> T:
    """Pont sync Celery → code async SQLAlchemy (UNE coroutine par tâche)."""
    return asyncio.run(coro)  # type: ignore[arg-type]


def _batch_size(batch: int | None) -> int:
    settings = get_settings()
    return max(1, batch if batch is not None else settings.embeddings_backfill_batch_size)


async def _persist(
    session: AsyncSession,
    model: type[Any],
    key_column: Any,
    vectors: dict[uuid.UUID, list[float]],
) -> None:
    """Écrit les vecteurs calculés (un UPDATE par ligne, lot borné)."""
    for key, vector in vectors.items():
        await session.execute(
            update(model).where(key_column == key).values(embedding=vector)
        )
    await session.commit()


# ------------------------------------------------------------------- offres


async def _job_targets(session: AsyncSession, limit: int, force: bool) -> list[EmbeddingTarget]:
    """Offres ACTIVES à embarquer — les offres éteintes ne sont jamais scorées."""
    stmt = select(
        JobPosting.id, JobPosting.title, JobPosting.description_text, JobPosting.embedding
    ).where(JobPosting.status == "active")
    if not force:
        stmt = stmt.where(JobPosting.embedding.is_(None))
    stmt = stmt.order_by(JobPosting.last_seen_at.desc()).limit(limit)
    return [
        EmbeddingTarget(
            key=row.id,
            text=job_embedding_text(row.title, row.description_text),
            current=row.embedding,
        )
        for row in await session.execute(stmt)
    ]


async def _backfill_jobs_cycle(limit: int, force: bool) -> dict[str, int]:
    provider = get_embedding_provider()
    settings = get_settings()
    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return await _embed_into(
                session, provider, JobPosting, JobPosting.id,
                await _job_targets(session, limit, force),
                force=force, batch_size=settings.embeddings_batch_size,
            )
    finally:
        await engine.dispose()


# ------------------------------------------------------------------ profils


async def _held_titles_by_profile(
    session: AsyncSession, profile_ids: Sequence[uuid.UUID], max_held: int = 2
) -> dict[uuid.UUID, list[str]]:
    """Derniers intitulés occupés, du plus récent au plus ancien (06 §2.3).

    Tri par ``end_date`` décroissant en traitant « en cours » (NULL) comme
    le plus récent, départagé par ``start_date`` — pas d'ORDER BY partiel
    côté SQL pour rester lisible sur des lots bornés.
    """
    if not profile_ids:
        return {}
    stmt = select(
        ProfileExperience.profile_id,
        ProfileExperience.title,
        ProfileExperience.start_date,
        ProfileExperience.end_date,
    ).where(ProfileExperience.profile_id.in_(list(profile_ids)))
    grouped: dict[uuid.UUID, list[Any]] = {}
    for row in await session.execute(stmt):
        grouped.setdefault(row.profile_id, []).append(row)

    def _recency(row: Any) -> tuple[bool, date, date]:
        # « en cours » (end_date NULL) = le plus récent ; date.min sert de
        # butée neutre pour garder un tuple comparable.
        return (row.end_date is None, row.end_date or date.min, row.start_date)

    return {
        profile_id: [
            row.title for row in sorted(rows, key=_recency, reverse=True)[:max_held]
        ]
        for profile_id, rows in grouped.items()
    }


async def _target_titles_by_user(
    session: AsyncSession, user_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    if not user_ids:
        return {}
    stmt = (
        select(PreferenceTitle.user_id, PreferenceTitle.title)
        .where(PreferenceTitle.user_id.in_(list(user_ids)))
        .order_by(PreferenceTitle.title)
    )
    grouped: dict[uuid.UUID, list[str]] = {}
    for row in await session.execute(stmt):
        grouped.setdefault(row.user_id, []).append(row.title)
    return grouped


async def _profile_targets(
    session: AsyncSession,
    limit: int,
    force: bool,
    profile_id: uuid.UUID | None = None,
) -> list[EmbeddingTarget]:
    """Profils VALIDÉS à embarquer (le moteur suppose un profil validé)."""
    stmt = select(Profile.id, Profile.user_id, Profile.embedding).where(
        Profile.status == "validated"
    )
    if profile_id is not None:
        stmt = stmt.where(Profile.id == profile_id)
    if not force:
        stmt = stmt.where(Profile.embedding.is_(None))
    rows = list(await session.execute(stmt.limit(limit)))
    if not rows:
        return []
    held = await _held_titles_by_profile(session, [row.id for row in rows])
    targets = await _target_titles_by_user(session, [row.user_id for row in rows])
    return [
        EmbeddingTarget(
            key=row.id,
            text=profile_embedding_text(
                targets.get(row.user_id, []), held.get(row.id, [])
            ),
            current=row.embedding,
        )
        for row in rows
    ]


async def _preference_title_targets(
    session: AsyncSession, limit: int, force: bool
) -> list[EmbeddingTarget]:
    """Un vecteur PAR intitulé cible — forme exacte de 06 §2.3 (max des cosinus)."""
    stmt = select(PreferenceTitle.id, PreferenceTitle.title, PreferenceTitle.embedding)
    if not force:
        stmt = stmt.where(PreferenceTitle.embedding.is_(None))
    return [
        EmbeddingTarget(key=row.id, text=skill_embedding_text(row.title), current=row.embedding)
        for row in await session.execute(stmt.limit(limit))
    ]


async def _backfill_profiles_cycle(limit: int, force: bool) -> dict[str, Any]:
    provider = get_embedding_provider()
    settings = get_settings()
    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            profiles_report = await _embed_into(
                session, provider, Profile, Profile.id,
                await _profile_targets(session, limit, force),
                force=force, batch_size=settings.embeddings_batch_size,
            )
            titles_report = await _embed_into(
                session, provider, PreferenceTitle, PreferenceTitle.id,
                await _preference_title_targets(session, limit, force),
                force=force, batch_size=settings.embeddings_batch_size,
            )
            return {"profiles": profiles_report, "preference_titles": titles_report}
    finally:
        await engine.dispose()


# ----------------------------------------------------------------- compétences


async def _skill_targets(
    session: AsyncSession, limit: int, force: bool
) -> list[EmbeddingTarget]:
    stmt = select(Skill.id, Skill.canonical_label, Skill.embedding)
    if not force:
        stmt = stmt.where(Skill.embedding.is_(None))
    return [
        EmbeddingTarget(
            key=row.id,
            text=skill_embedding_text(row.canonical_label),
            current=row.embedding,
        )
        for row in await session.execute(stmt.limit(limit))
    ]


async def _backfill_skills_cycle(limit: int, force: bool) -> dict[str, int]:
    provider = get_embedding_provider()
    settings = get_settings()
    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return await _embed_into(
                session, provider, Skill, Skill.id,
                await _skill_targets(session, limit, force),
                force=force, batch_size=settings.embeddings_batch_size,
            )
    finally:
        await engine.dispose()


async def _embed_into(
    session: AsyncSession,
    provider: EmbeddingProvider,
    model: type[Any],
    key_column: Any,
    targets: list[EmbeddingTarget],
    *,
    force: bool,
    batch_size: int,
) -> dict[str, int]:
    """Planifie, calcule et persiste un lot — chemin commun aux trois cibles."""
    report = BackfillReport()
    planned = plan_embeddings(targets, report, force=force)
    vectors = compute_embeddings(provider, planned, batch_size=batch_size, report=report)
    await _persist(session, model, key_column, vectors)
    return report.as_dict()


async def _embed_profile_cycle(profile_id: uuid.UUID) -> dict[str, int]:
    provider = get_embedding_provider()
    settings = get_settings()
    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return await _embed_into(
                session, provider, Profile, Profile.id,
                await _profile_targets(session, 1, True, profile_id),
                force=True, batch_size=settings.embeddings_batch_size,
            )
    finally:
        await engine.dispose()


# ---------------------------------------------------------------- tâches Celery


@celery_app.task(name="ai.embeddings.backfill_jobs")
def backfill_jobs(batch: int | None = None, force: bool = False) -> dict[str, int]:
    """Calcule les embeddings des offres actives qui n'en ont pas (07 §5.6).

    Idempotente : sans ``force``, seules les lignes ``embedding IS NULL``
    sont traitées — rejouer la tâche est un no-op.
    """
    report = _run(_backfill_jobs_cycle(_batch_size(batch), force))
    logger.info("embeddings_backfill_jobs report=%s force=%s", report, force)
    return report


@celery_app.task(name="ai.embeddings.backfill_profiles")
def backfill_profiles(batch: int | None = None, force: bool = False) -> dict[str, Any]:
    """Embeddings des profils validés et de leurs intitulés cibles (06 §2.3)."""
    report = _run(_backfill_profiles_cycle(_batch_size(batch), force))
    logger.info("embeddings_backfill_profiles report=%s force=%s", report, force)
    return report


@celery_app.task(name="ai.embeddings.backfill_skills")
def backfill_skills(batch: int | None = None, force: bool = False) -> dict[str, int]:
    """Embeddings des libellés de compétences — crédit « proche » (06 §2.1)."""
    report = _run(_backfill_skills_cycle(_batch_size(batch), force))
    logger.info("embeddings_backfill_skills report=%s force=%s", report, force)
    return report


@celery_app.task(name="ai.embeddings.embed_profile")
def embed_profile(profile_id: str) -> dict[str, int]:
    """Recalcul ciblé du vecteur d'UN profil (à enfiler à sa validation).

    ``force=True`` : à la validation, le profil a changé — son vecteur
    existant est périmé et doit être remplacé.
    """
    report = _run(_embed_profile_cycle(uuid.UUID(str(profile_id))))
    logger.info("embeddings_embed_profile profile=%s report=%s", profile_id, report)
    return report

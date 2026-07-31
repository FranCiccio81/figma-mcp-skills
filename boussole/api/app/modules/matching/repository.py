"""Accès aux données du module matching.

Le protocole ``MatchingRepository`` couvre : chargement d'une offre avec ses
relations (compétences, langues, lieux, sources), pré-filtre du calcul
paresseux de ``GET /matches``, labels canoniques de la taxonomie, vecteurs
alimentant le moteur (compétences et intitulés cibles, 06 §2.1/§2.3), cache
``match_results`` (upsert) et invalidation par utilisateur (hook
« preferences_changed », purge D21). Les tests unitaires substituent une
implémentation en mémoire (patterns du module jobs).
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from fastapi import Depends
from sqlalchemy import ScalarSelect, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db_session
from app.modules.jobs.models import JobPosting, SavedJob
from app.modules.matching.models import MatchExplanationRow, MatchResultRow
from app.modules.preferences.models import PreferenceTitle
from app.modules.profiles.models import Profile
from app.modules.referentials.models import Skill


class MatchingRepository(Protocol):
    async def get_job(self, job_id: uuid.UUID) -> JobPosting | None:
        """Offre avec relations chargées (skills, languages, locations, sources)."""
        ...

    async def list_recent_active(
        self, *, contracts: Sequence[str], limit: int
    ) -> list[JobPosting]:
        """Pré-filtre du calcul paresseux : offres actives dont le contrat est
        accepté (ou inconnu — l'inconnu n'est pas un fait négatif), plafonnées
        aux ``limit`` plus récentes (``last_seen_at`` décroissant)."""
        ...

    async def list_recent_outside_contracts(
        self, *, contracts: Sequence[str], limit: int
    ) -> list[JobPosting]:
        """Offres actives dont le contrat est HORS des préférences.

        Complément exact de :meth:`list_recent_active` : contrat renseigné et
        absent de la liste. Sert l'élargissement borné quand la préférence de
        contrat n'est pas stricte (voir ``MatchingService.search``)."""
        ...

    async def skill_labels(self, skill_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        """``skill_id`` → label canonique (table ``skills``)."""
        ...

    async def skill_embeddings(
        self, skill_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[float]]:
        """``skill_id`` → ``skills.embedding`` (crédit « proche » 0,5, 06 §2.1).

        Seules les compétences réellement vectorisées sont retournées : sans
        vecteur, le moteur retombe sur le match exact (aucune régression).
        """
        ...

    async def preference_title_embeddings(self, user_id: uuid.UUID) -> list[list[float]]:
        """Vecteurs des intitulés cibles (``preference_titles.embedding``).

        06 §2.3 prend le MAX des cosinus sur les intitulés du candidat : un
        vecteur PAR intitulé est donc la forme exacte de la règle. Le vecteur
        agrégé ``profiles.embedding`` (tous les intitulés fondus en un) écrase
        au contraire l'intitulé le mieux ciblé dans la moyenne. Liste vide →
        seul l'agrégé est utilisé (comportement antérieur).
        """
        ...

    async def get_cached(
        self, profile_id: uuid.UUID, job_id: uuid.UUID
    ) -> MatchResultRow | None: ...

    async def get_cached_many(
        self, profile_id: uuid.UUID, job_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, MatchResultRow]: ...

    async def upsert_result(self, row: MatchResultRow) -> None:
        """Upsert par (profile_id, job_posting_id) — remplace toutes les valeurs."""
        ...

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        """Invalide tous les ``match_results`` du profil de l'utilisateur
        (les ``match_explanations`` suivent — FK ON DELETE CASCADE)."""
        ...

    async def list_results_for_user(self, user_id: uuid.UUID) -> list[MatchResultRow]:
        """Résultats du profil de l'utilisateur (export RGPD D21)."""
        ...

    async def saved_states(
        self, user_id: uuid.UUID, job_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """État saved/hidden de l'utilisateur pour les offres listées."""
        ...


_JOB_RELATIONS = (
    selectinload(JobPosting.locations),
    selectinload(JobPosting.skills),
    selectinload(JobPosting.languages),
    selectinload(JobPosting.job_sources),
)


def _profile_ids_subquery(user_id: uuid.UUID) -> ScalarSelect[uuid.UUID]:
    return select(Profile.id).where(Profile.user_id == user_id).scalar_subquery()


class SqlAlchemyMatchingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_job(self, job_id: uuid.UUID) -> JobPosting | None:
        stmt = (
            select(JobPosting).where(JobPosting.id == job_id).options(*_JOB_RELATIONS)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_recent_active(
        self, *, contracts: Sequence[str], limit: int
    ) -> list[JobPosting]:
        conditions = [JobPosting.status == "active"]
        if contracts:
            conditions.append(
                or_(JobPosting.contract.is_(None), JobPosting.contract.in_(list(contracts)))
            )
        stmt = (
            select(JobPosting)
            .where(*conditions)
            .order_by(JobPosting.last_seen_at.desc(), JobPosting.id.desc())
            .limit(limit)
            .options(*_JOB_RELATIONS)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_recent_outside_contracts(
        self, *, contracts: Sequence[str], limit: int
    ) -> list[JobPosting]:
        """Complément exact de :meth:`list_recent_active`.

        ``contract IS NOT NULL AND contract NOT IN (...)`` : le contrat inconnu
        appartient à l'ensemble PRÉFÉRÉ (l'inconnu n'est pas un fait négatif),
        il ne doit donc pas être compté deux fois ici.
        """
        if not contracts:
            return []
        stmt = (
            select(JobPosting)
            .where(
                JobPosting.status == "active",
                JobPosting.contract.is_not(None),
                JobPosting.contract.not_in(list(contracts)),
            )
            .order_by(JobPosting.last_seen_at.desc(), JobPosting.id.desc())
            .limit(limit)
            .options(*_JOB_RELATIONS)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def skill_labels(self, skill_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not skill_ids:
            return {}
        stmt = select(Skill.id, Skill.canonical_label).where(Skill.id.in_(list(skill_ids)))
        return {row.id: row.canonical_label for row in await self._session.execute(stmt)}

    async def skill_embeddings(
        self, skill_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[float]]:
        if not skill_ids:
            return {}
        stmt = select(Skill.id, Skill.embedding).where(
            Skill.id.in_(list(skill_ids)), Skill.embedding.is_not(None)
        )
        return {
            row.id: list(row.embedding) for row in await self._session.execute(stmt)
        }

    async def preference_title_embeddings(self, user_id: uuid.UUID) -> list[list[float]]:
        stmt = (
            select(PreferenceTitle.embedding)
            .where(
                PreferenceTitle.user_id == user_id,
                PreferenceTitle.embedding.is_not(None),
            )
            .order_by(PreferenceTitle.title)
        )
        return [list(row[0]) for row in await self._session.execute(stmt)]

    async def get_cached(
        self, profile_id: uuid.UUID, job_id: uuid.UUID
    ) -> MatchResultRow | None:
        return await self._session.get(MatchResultRow, (profile_id, job_id))

    async def get_cached_many(
        self, profile_id: uuid.UUID, job_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, MatchResultRow]:
        if not job_ids:
            return {}
        stmt = select(MatchResultRow).where(
            MatchResultRow.profile_id == profile_id,
            MatchResultRow.job_posting_id.in_(list(job_ids)),
        )
        return {
            row.job_posting_id: row
            for row in (await self._session.execute(stmt)).scalars()
        }

    async def upsert_result(self, row: MatchResultRow) -> None:
        values = {
            "scoring_version": row.scoring_version,
            "score": row.score,
            "confidence": row.confidence,
            "low_data": row.low_data,
            "blocking_criteria": row.blocking_criteria,
            "unknown_dimensions": row.unknown_dimensions,
            "dimension_scores": row.dimension_scores,
            "computed_at": row.computed_at,
        }
        stmt = (
            pg_insert(MatchResultRow)
            .values(
                profile_id=row.profile_id, job_posting_id=row.job_posting_id, **values
            )
            .on_conflict_do_update(
                index_elements=[MatchResultRow.profile_id, MatchResultRow.job_posting_id],
                set_=values,
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        profile_ids = _profile_ids_subquery(user_id)
        # Explications supprimées explicitement (la FK composite ON DELETE
        # CASCADE du schéma couvre déjà le cas — ceinture et bretelles).
        await self._session.execute(
            delete(MatchExplanationRow).where(MatchExplanationRow.profile_id.in_(profile_ids))
        )
        await self._session.execute(
            delete(MatchResultRow).where(MatchResultRow.profile_id.in_(profile_ids))
        )
        await self._session.commit()

    async def list_results_for_user(self, user_id: uuid.UUID) -> list[MatchResultRow]:
        stmt = select(MatchResultRow).where(
            MatchResultRow.profile_id.in_(_profile_ids_subquery(user_id))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def saved_states(
        self, user_id: uuid.UUID, job_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        if not job_ids:
            return {}
        stmt = select(SavedJob).where(
            SavedJob.user_id == user_id, SavedJob.job_posting_id.in_(list(job_ids))
        )
        return {
            row.job_posting_id: row.state
            for row in (await self._session.execute(stmt)).scalars()
        }


async def get_matching_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MatchingRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyMatchingRepository(session)

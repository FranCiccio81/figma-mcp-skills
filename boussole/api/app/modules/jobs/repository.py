"""Accès aux données du module jobs — pipeline de recherche D07.

Pipeline (décision D07) :
1. filtres durs SQL (statut actif, remote, contrat, salaire Q32, fraîcheur,
   localisation pays ou haversine sur ``job_locations``, état saved/hidden) ;
2. full-text PostgreSQL ``websearch_to_tsquery`` sur ``job_postings.tsv``
   (config 'french' par défaut 🟡, 'english' si l'offre est filtrée en
   anglais) avec classement ``ts_rank_cd`` ;
3. rerank vectoriel pgvector : STUB au M2 (🟡 voir ``rerank_with_embeddings``) ;
4. tri final par score de matching : jalon M3 (``sort=match`` retombe sur
   ``relevance`` — documenté dans le service).

Pagination : curseur opaque base64 encodant un tuple keyset
``(sort_value, id)`` — jamais d'OFFSET (résultats mouvants, §1 des contrats).

Le protocole ``JobsRepository`` permet de substituer une implémentation en
mémoire dans les tests unitaires (pas de PostgreSQL requis).
"""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from fastapi import Depends
from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    case,
    exists,
    func,
    or_,
    select,
    text,
    tuple_,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.db import get_db_session
from app.modules.jobs.models import JobLocation, JobPosting, JobSource, SavedJob, Source

EARTH_RADIUS_KM = 6371.0

# ---------------------------------------------------------------- curseur


class InvalidCursorError(ValueError):
    """Curseur opaque illisible ou incohérent avec le tri demandé."""


@dataclass(frozen=True, slots=True)
class SearchCursor:
    """Tuple keyset décodé : (valeur de tri, id du dernier élément servi)."""

    sort: str  # 'date' | 'relevance'
    value: datetime | float
    last_id: uuid.UUID


def encode_cursor(sort: str, value: datetime | float, last_id: uuid.UUID) -> str:
    """Encode le tuple keyset en curseur opaque base64 URL-safe."""
    raw_value = value.isoformat() if isinstance(value, datetime) else repr(float(value))
    payload = json.dumps({"s": sort, "v": raw_value, "id": str(last_id)})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(raw: str, expected_sort: str) -> SearchCursor:
    """Décode et valide un curseur opaque.

    Toute anomalie (base64 invalide, JSON corrompu, clés manquantes, tri
    différent de celui de la requête, valeur intypable) lève
    ``InvalidCursorError`` — convertie en 422 problem+json par le service.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        sort = payload["s"]
        raw_value = payload["v"]
        last_id = uuid.UUID(payload["id"])
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, KeyError,
            TypeError, ValueError) as exc:
        raise InvalidCursorError("curseur illisible") from exc
    if sort != expected_sort:
        raise InvalidCursorError("curseur incompatible avec le tri demandé")
    try:
        value: datetime | float
        value = datetime.fromisoformat(raw_value) if sort == "date" else float(raw_value)
    except (TypeError, ValueError) as exc:
        raise InvalidCursorError("valeur de curseur intypable") from exc
    return SearchCursor(sort=sort, value=value, last_id=last_id)


# ---------------------------------------------------------------- filtres


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Filtres de recherche déjà validés/normalisés par le service.

    ``sort`` est le tri EFFECTIF ('date' ou 'relevance') : le service a déjà
    fait retomber ``match`` sur ``relevance`` (M2) et ``relevance`` sans ``q``
    sur ``date`` (aucun rang full-text disponible).
    """

    q: str | None = None
    remote: tuple[str, ...] = ()
    contract: tuple[str, ...] = ()
    salary_min: int | None = None
    posted_since_days: int | None = None
    language: str | None = None
    country: str | None = None
    lat: float | None = None
    lon: float | None = None
    radius_km: int = 30
    include_hidden: bool = False
    saved_only: bool = False
    sort: str = "date"  # 'date' | 'relevance' (avec q obligatoirement)


@dataclass(frozen=True, slots=True)
class JobSearchRow:
    """Ligne de résultat : offre + état saved/hidden + valeur de tri keyset."""

    posting: JobPosting
    saved_state: str | None
    sort_value: datetime | float


@dataclass(frozen=True, slots=True)
class JobDetailRow:
    """Détail : offre (relations chargées) + état saved/hidden de l'utilisateur."""

    posting: JobPosting
    saved_state: str | None


@dataclass(frozen=True, slots=True)
class SourceRow:
    """Ligne de GET /sources."""

    slug: str
    name: str
    kind: str
    last_sync_at: datetime | None


def _haversine_km(lat: float, lon: float) -> ColumnElement[float]:
    """Distance haversine SQL (km) entre (lat, lon) et une ``job_locations``.

    ``least(1.0, …)`` borne l'argument d'``acos`` contre les erreurs d'arrondi
    flottant qui produiraient un NaN.
    """
    return EARTH_RADIUS_KM * func.acos(
        func.least(
            1.0,
            func.cos(func.radians(lat))
            * func.cos(func.radians(JobLocation.lat))
            * func.cos(func.radians(JobLocation.lon) - func.radians(lon))
            + func.sin(func.radians(lat)) * func.sin(func.radians(JobLocation.lat)),
        )
    )


def ts_config_for(language: str | None) -> str:
    """Config full-text selon la langue filtrée — 'french' par défaut 🟡.

    Hypothèse 🟡 : sans filtre de langue explicite, la config 'french' est
    utilisée (marché cible fr) ; les offres 'en' restent trouvables car leur
    ``tsv`` est indexé en 'english' par le trigger — le rappel est simplement
    moindre. Aligné sur D07 (« tuning full-text multilingue limité »).
    """
    return "english" if language is not None and language.lower().startswith("en") else "french"


def build_search_statement(
    user_id: uuid.UUID,
    filters: SearchFilters,
    limit: int,
    cursor: SearchCursor | None,
) -> Select[Any]:
    """Construit le SELECT de recherche (étapes 1-2 du pipeline D07).

    Fonction pure (aucune E/S) : testable par compilation vers le dialecte
    postgresql sans base. Récupère ``limit + 1`` lignes pour détecter la page
    suivante sans COUNT ni OFFSET.
    """
    saved = aliased(SavedJob)
    conditions = [JobPosting.status == "active"]

    if filters.remote:
        conditions.append(JobPosting.remote.in_(filters.remote))
    if filters.contract:
        conditions.append(JobPosting.contract.in_(filters.contract))
    if filters.salary_min is not None:
        # Q32 : les offres sans salaire sont INCLUSES (badge « non communiqué »
        # côté front) — l'inconnu n'est pas un fait négatif.
        # Le filtre compare des montants ANNUALISÉS : les périodes non annuelles
        # sont converties (mois ×12, jour ×220, heure ×1600 🟡 — approximations
        # FR à calibrer), sans quoi une offre à 4 000 €/mois serait exclue par
        # salary_min=45000 alors qu'elle paie ~48 k€/an.
        period_factor = case(
            (JobPosting.salary_period == "month", 12),
            (JobPosting.salary_period == "day", 220),
            (JobPosting.salary_period == "hour", 1600),
            else_=1,
        )
        best_salary = func.coalesce(JobPosting.salary_max, JobPosting.salary_min)
        conditions.append(
            or_(best_salary.is_(None), best_salary * period_factor >= filters.salary_min)
        )
    if filters.posted_since_days is not None:
        threshold = datetime.now(UTC) - timedelta(days=filters.posted_since_days)
        conditions.append(JobPosting.last_seen_at >= threshold)
    if filters.language is not None:
        conditions.append(JobPosting.language == filters.language)
    if filters.country is not None:
        conditions.append(
            exists().where(
                JobLocation.job_posting_id == JobPosting.id,
                JobLocation.country_code == filters.country,
            )
        )
    if filters.lat is not None and filters.lon is not None:
        conditions.append(
            exists().where(
                JobLocation.job_posting_id == JobPosting.id,
                JobLocation.lat.is_not(None),
                JobLocation.lon.is_not(None),
                _haversine_km(filters.lat, filters.lon) <= filters.radius_km,
            )
        )
    if filters.saved_only:
        conditions.append(saved.state == "saved")
    if not filters.include_hidden:
        conditions.append(or_(saved.state.is_(None), saved.state != "hidden"))

    if filters.q:
        tsquery = func.websearch_to_tsquery(ts_config_for(filters.language), filters.q)
        conditions.append(JobPosting.tsv.op("@@")(tsquery))
        rank = func.ts_rank_cd(JobPosting.tsv, tsquery)
    else:
        rank = None

    # Any : InstrumentedAttribute et Function n'ont pas d'ancêtre commun
    # satisfaisant pour mypy ; les deux portent .desc()/.label().
    sort_expr: Any
    if filters.sort == "relevance" and rank is not None:
        sort_expr = rank
        order_by = (rank.desc(), JobPosting.id.desc())
    else:
        sort_expr = JobPosting.last_seen_at
        order_by = (JobPosting.last_seen_at.desc(), JobPosting.id.desc())

    if cursor is not None:
        # Keyset descendant : strictement « après » le dernier élément servi.
        conditions.append(tuple_(sort_expr, JobPosting.id) < (cursor.value, cursor.last_id))

    return (
        select(JobPosting, saved.state.label("saved_state"), sort_expr.label("sort_value"))
        .outerjoin(saved, and_(saved.job_posting_id == JobPosting.id, saved.user_id == user_id))
        .where(*conditions)
        .order_by(*order_by)
        .limit(limit + 1)
        .options(
            selectinload(JobPosting.locations),
            selectinload(JobPosting.job_sources),
        )
    )


def rerank_with_embeddings(rows: list[JobSearchRow]) -> list[JobSearchRow]:
    """Étape 3 du pipeline D07 (rerank vectoriel pgvector) — STUB M2 🟡.

    ``job_postings.embedding`` n'est pas peuplé au M2 (le worker d'embedding
    arrive avec le module IA, M3) : la fonction retourne les lignes inchangées.
    Elle matérialise l'étape du pipeline pour que le branchement M3 soit un
    remplacement local (similarité cosinus sur les ``limit×k`` premiers
    candidats full-text) sans toucher au service ni au routeur.
    """
    return rows


# ---------------------------------------------------------------- protocole


class JobsRepository(Protocol):
    async def search(
        self,
        *,
        user_id: uuid.UUID,
        filters: SearchFilters,
        limit: int,
        cursor: SearchCursor | None,
    ) -> list[JobSearchRow]:
        """Retourne jusqu'à ``limit + 1`` lignes (détection de page suivante)."""
        ...

    async def get_detail(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> JobDetailRow | None: ...

    async def set_saved_state(
        self, user_id: uuid.UUID, job_id: uuid.UUID, state: str
    ) -> None: ...

    async def clear_saved_state(self, user_id: uuid.UUID, job_id: uuid.UUID) -> None: ...

    async def list_sources(self) -> list[SourceRow]: ...


# ---------------------------------------------------------------- SQLAlchemy


class SqlAlchemyJobsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        *,
        user_id: uuid.UUID,
        filters: SearchFilters,
        limit: int,
        cursor: SearchCursor | None,
    ) -> list[JobSearchRow]:
        stmt = build_search_statement(user_id, filters, limit, cursor)
        result = await self._session.execute(stmt)
        rows = [
            JobSearchRow(posting=posting, saved_state=saved_state, sort_value=sort_value)
            for posting, saved_state, sort_value in result.all()
        ]
        return rerank_with_embeddings(rows)

    async def get_detail(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> JobDetailRow | None:
        saved = aliased(SavedJob)
        stmt = (
            select(JobPosting, saved.state.label("saved_state"))
            .outerjoin(
                saved, and_(saved.job_posting_id == JobPosting.id, saved.user_id == user_id)
            )
            .where(JobPosting.id == job_id)
            .options(
                selectinload(JobPosting.locations),
                selectinload(JobPosting.skills),
                selectinload(JobPosting.job_sources).selectinload(JobSource.source),
            )
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        posting, saved_state = row
        return JobDetailRow(posting=posting, saved_state=saved_state)

    async def set_saved_state(
        self, user_id: uuid.UUID, job_id: uuid.UUID, state: str
    ) -> None:
        """Upsert sur la clé (user_id, job_posting_id) — un seul état par offre."""
        stmt = (
            pg_insert(SavedJob)
            .values(user_id=user_id, job_posting_id=job_id, state=state)
            .on_conflict_do_update(
                index_elements=[SavedJob.user_id, SavedJob.job_posting_id],
                set_={"state": state},
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def clear_saved_state(self, user_id: uuid.UUID, job_id: uuid.UUID) -> None:
        saved = await self._session.get(SavedJob, (user_id, job_id))
        if saved is not None:
            await self._session.delete(saved)
        await self._session.commit()

    async def list_sources(self) -> list[SourceRow]:
        stmt = select(Source).where(Source.active.is_(True)).order_by(Source.name)
        sources = (await self._session.execute(stmt)).scalars().all()
        last_sync = await self._last_sync_by_source()
        return [
            SourceRow(
                slug=source.slug,
                name=source.name,
                kind=source.kind,
                last_sync_at=last_sync.get(source.id),
            )
            for source in sources
        ]

    async def _last_sync_by_source(self) -> dict[uuid.UUID, datetime]:
        """Fraîcheur par source via ``connector_state`` — tolérant 🟡.

        La table ``connector_state`` appartient au module ingestion et n'existe
        pas encore dans initial-schema.sql : requête textuelle best effort. Si
        la table manque (ou toute erreur SQL), ``last_sync_at`` reste null 🟡.
        """
        try:
            result = await self._session.execute(
                text(
                    "SELECT source_id, MAX(last_sync_at) AS last_sync_at "
                    "FROM connector_state GROUP BY source_id"
                )
            )
            return {row.source_id: row.last_sync_at for row in result}
        except SQLAlchemyError:
            await self._session.rollback()
            return {}


async def get_jobs_repository(
    session: AsyncSession = Depends(get_db_session),
) -> JobsRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyJobsRepository(session)

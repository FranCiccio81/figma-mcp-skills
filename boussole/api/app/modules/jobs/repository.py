"""Accès aux données du module jobs — pipeline de recherche D07.

Pipeline (décision D07) :
1. filtres durs SQL (statut actif, remote, contrat, salaire Q32, fraîcheur,
   localisation pays ou haversine sur ``job_locations``, état saved/hidden) ;
2. full-text PostgreSQL ``websearch_to_tsquery`` sur ``job_postings.tsv``
   (config 'french' par défaut 🟡, 'english' si l'offre est filtrée en
   anglais) avec classement ``ts_rank_cd`` ;
3. rerank vectoriel : combinaison du rang full-text et du cosinus entre
   l'embedding de la requête et ``job_postings.embedding``, pondération
   configurable (🟡 Q41) — voir ``rerank_with_embeddings`` ;
4. tri final par score de matching : jalon M3 (``sort=match`` retombe sur
   ``relevance`` — documenté dans le service).

Pagination : curseur opaque base64 encodant un tuple keyset
``(sort_value, id)`` — jamais d'OFFSET (résultats mouvants, §1 des contrats).
Le rerank de l'étape 3 est conçu pour ne PAS l'altérer : il réordonne à
l'intérieur d'une page sans toucher ni à sa composition ni à la borne du
curseur (démonstration dans ``rerank_with_embeddings``).

Le protocole ``JobsRepository`` permet de substituer une implémentation en
mémoire dans les tests unitaires (pas de PostgreSQL requis).
"""

import asyncio
import base64
import binascii
import json
import logging
import math
import uuid
from collections.abc import Sequence
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

from app.ai.embeddings.base import EmbeddingError, EmbeddingProvider
from app.ai.embeddings.factory import get_embedding_provider
from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.modules.jobs.models import JobLocation, JobPosting, JobSource, SavedJob, Source

# Lecture seule d'une table d'un autre module : la carte d'offre doit porter
# le score, et le recopier dans `jobs` créerait deux sources de vérité pour le
# chiffre central du produit.
from app.modules.matching.models import MatchResultRow
from app.modules.profiles.models import Profile

logger = logging.getLogger(__name__)

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
class MatchRowSummary:
    """Ce que la carte affiche du matching — pas le détail par dimension."""

    score: int
    confidence: int
    low_data: bool
    has_blocking: bool


@dataclass(frozen=True, slots=True)
class JobSearchRow:
    """Ligne de résultat : offre + état saved/hidden + valeur de tri keyset."""

    posting: JobPosting
    saved_state: str | None
    sort_value: datetime | float
    #: Résumé de matching de l'utilisateur courant, ``None`` si l'offre n'a
    #: pas encore été scorée pour lui (ou si son profil n'est pas validé).
    match: MatchRowSummary | None = None


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


#: Score de substitution pour une offre NON SCORÉE, en tri par compatibilité.
#:
#: ``NULLS LAST`` seul ne suffit pas : la pagination keyset compare un tuple
#: ``(score, id)``, et un ``NULL`` y rend toute comparaison indéterminée — la
#: page suivante reviendrait vide. ``-1`` est hors de l'intervalle 0–100, donc
#: les offres non scorées se rangent après toutes les autres, dans un ordre
#: stable et comparable.
UNSCORED_SORT_VALUE = -1


def build_search_statement(
    user_id: uuid.UUID,
    filters: SearchFilters,
    limit: int,
    cursor: SearchCursor | None,
    *,
    profile_id: uuid.UUID | None = None,
    scoring_version: str | None = None,
) -> Select[Any]:
    """Construit le SELECT de recherche (étapes 1-2 du pipeline D07).

    Fonction pure (aucune E/S) : testable par compilation vers le dialecte
    postgresql sans base. Récupère ``limit + 1`` lignes pour détecter la page
    suivante sans COUNT ni OFFSET.
    """
    saved = aliased(SavedJob)
    match = aliased(MatchResultRow)
    #: Le matching n'est joint que si l'utilisateur a un profil validé ET que
    #: la version de scoring est connue : un score calculé par une version
    #: précédente n'est pas comparable à un score courant, et l'afficher
    #: mélangerait deux échelles.
    matching_joint = profile_id is not None and scoring_version is not None
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
        # ``unaccent`` DES DEUX CÔTÉS : le trigger de la migration 0001
        # désaccentue le texte indexé (« développeur » → lexème
        # ``developpeur``). Sans le même traitement sur la requête, un
        # francophone qui tape ses accents — le cas nominal — ne trouve
        # rien. Anomalie détectée par la suite d'intégration.
        tsquery = func.websearch_to_tsquery(
            ts_config_for(filters.language), func.unaccent(filters.q)
        )
        conditions.append(JobPosting.tsv.op("@@")(tsquery))
        rank = func.ts_rank_cd(JobPosting.tsv, tsquery)
    else:
        rank = None

    # Any : InstrumentedAttribute et Function n'ont pas d'ancêtre commun
    # satisfaisant pour mypy ; les deux portent .desc()/.label().
    sort_expr: Any
    if filters.sort == "match" and matching_joint:
        # Le tri par compatibilité EXISTE désormais. Il retombait sur la
        # pertinence full-text — donc « Trier par → Compatibilité » ne triait
        # rien, et aucune carte n'affichait de score, alors que le tableau de
        # bord renvoyait vers cette page précisément pour ça.
        sort_expr = func.coalesce(match.score, UNSCORED_SORT_VALUE)
        order_by = (sort_expr.desc(), JobPosting.id.desc())
    elif filters.sort == "relevance" and rank is not None:
        sort_expr = rank
        order_by = (rank.desc(), JobPosting.id.desc())
    else:
        sort_expr = JobPosting.last_seen_at
        order_by = (JobPosting.last_seen_at.desc(), JobPosting.id.desc())

    if cursor is not None:
        # Keyset descendant : strictement « après » le dernier élément servi.
        conditions.append(tuple_(sort_expr, JobPosting.id) < (cursor.value, cursor.last_id))

    colonnes: list[Any] = [
        JobPosting,
        saved.state.label("saved_state"),
        sort_expr.label("sort_value"),
    ]
    if matching_joint:
        colonnes += [
            match.score.label("match_score"),
            match.confidence.label("match_confidence"),
            match.low_data.label("match_low_data"),
            match.blocking_criteria.label("match_blocking"),
        ]

    stmt = (
        select(*colonnes)
        .outerjoin(saved, and_(saved.job_posting_id == JobPosting.id, saved.user_id == user_id))
    )
    if matching_joint:
        stmt = stmt.outerjoin(
            match,
            and_(
                match.job_posting_id == JobPosting.id,
                match.profile_id == profile_id,
                match.scoring_version == scoring_version,
            ),
        )
    return (
        stmt.where(*conditions)
        .order_by(*order_by)
        .limit(limit + 1)
        .options(
            selectinload(JobPosting.locations),
            selectinload(JobPosting.job_sources),
        )
    )


# ------------------------------------------------------- rerank vectoriel D07


@dataclass(frozen=True, slots=True)
class RerankWeights:
    """Pondération rang full-text / cosinus — **Q41** 🟡 (« 50/50 normalisé »).

    Les deux poids sont renormalisés à somme 1 : seule leur PROPORTION
    compte, ce qui rend la calibration en alpha indépendante de l'échelle.
    """

    fulltext: float = 0.5
    vector: float = 0.5

    @classmethod
    def from_settings(cls, settings: Settings) -> "RerankWeights":
        return cls(
            fulltext=float(settings.search_rerank_fulltext_weight),
            vector=float(settings.search_rerank_vector_weight),
        )

    def normalized(self) -> tuple[float, float]:
        total = self.fulltext + self.vector
        if total <= 0:
            return (1.0, 0.0)  # garde-fou : rerank neutre
        return (self.fulltext / total, self.vector / total)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosinus borné [-1, 1] ; 0,0 si dimensions incompatibles ou norme nulle."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _min_max(values: Sequence[float]) -> list[float]:
    """Normalise en [0, 1] ; tout à 0,5 si toutes les valeurs sont égales."""
    if not values:
        return []
    low, high = min(values), max(values)
    if high - low <= 0:
        return [0.5] * len(values)
    return [(value - low) / (high - low) for value in values]


def rerank_with_embeddings(
    rows: list[JobSearchRow],
    *,
    limit: int | None = None,
    query_embedding: Sequence[float] | None = None,
    weights: RerankWeights | None = None,
) -> list[JobSearchRow]:
    """Étape 3 du pipeline D07 — re-ranking hybride full-text + cosinus.

    Score combiné, par ligne de la page :

    ``w_ft × rang_fulltext_normalisé + w_vec × cosinus_normalisé``

    où le rang full-text (``ts_rank_cd``, porté par ``sort_value``) et le
    cosinus (``job_postings.embedding`` vs embedding de la requête) sont
    tous deux min-max normalisés SUR LA PAGE. Pondération configurable
    (**Q41** 🟡, 50/50 par défaut).

    **Compatibilité avec la pagination keyset — garantie forte.** Le
    rerank ne change QUE l'ordre à l'intérieur d'une page ; il ne change
    jamais quelles lignes composent la page (c'est le SQL, ordonné par
    ``(ts_rank_cd DESC, id DESC)``, qui en décide) et il ne touche à aucun
    ``sort_value``. De plus, quand une page suivante existe, la DERNIÈRE
    ligne servie est ÉPINGLÉE à sa place : c'est elle qui produit le
    curseur (``encode_cursor(sort, last.sort_value, last.posting.id)`` côté
    service), et comme le SQL rend les lignes par tuple keyset
    décroissant, c'est exactement la borne minimale de la page. Le curseur
    émis est donc bit pour bit celui d'avant le rerank : **ni doublon, ni
    ligne sautée, ni curseur incohérent**. Quand la page est terminale
    (aucun curseur émis), toutes les lignes servies sont réordonnées.

    **Limite assumée 🟡** : le rerank est donc LOCAL À LA PAGE — une offre
    très pertinente au cosinus mais mal classée en full-text ne remonte
    pas d'une page à l'autre. Un rerank global exigerait de trier
    entièrement le résultat avant pagination (donc un OFFSET ou un
    curseur portant le score combiné, recalculé à chaque requête et
    invalidé au moindre re-embedding) : incompatible avec le keyset des
    contrats §1. Ce compromis est préférable à une pagination incohérente.

    Neutre (lignes rendues inchangées) si : pas d'embedding de requête,
    moins de deux lignes réordonnables, ou aucune offre de la page ne
    porte de vecteur.
    """
    if query_embedding is None or len(query_embedding) == 0 or len(rows) < 2:
        return rows
    ranks: list[float] = []
    for row in rows:
        if isinstance(row.sort_value, datetime):
            # Tri chronologique explicite : l'utilisateur a demandé un ordre,
            # on ne le réordonne pas (le rerank D07 ne vaut qu'en pertinence).
            return rows
        ranks.append(float(row.sort_value))

    served = len(rows) if limit is None else min(limit, len(rows))
    has_next_page = limit is not None and len(rows) > limit
    # Épinglage de la borne keyset : voir docstring.
    window_end = served - 1 if has_next_page else served
    window = rows[:window_end]
    if len(window) < 2:
        return rows

    cosines = [
        _cosine(query_embedding, row.posting.embedding)
        if row.posting.embedding is not None
        else None
        for row in window
    ]
    observed = [value for value in cosines if value is not None]
    if not observed:
        return rows  # aucune offre embarquée : rerank sans objet
    # « L'inconnu n'est pas un fait négatif » : une offre sans vecteur prend
    # le cosinus MOYEN de la page — elle n'est ni promue ni reléguée.
    neutral = sum(observed) / len(observed)
    filled = [neutral if value is None else value for value in cosines]

    w_fulltext, w_vector = (weights or RerankWeights()).normalized()
    rank_norm = _min_max(ranks[:window_end])
    cosine_norm = _min_max(filled)
    scored = [
        (w_fulltext * rank + w_vector * cosine, index)
        for index, (rank, cosine) in enumerate(zip(rank_norm, cosine_norm, strict=True))
    ]
    # Tri stable, départage par rang full-text d'origine (index croissant).
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [window[index] for _, index in scored] + rows[window_end:]


async def _query_embedding(
    filters: SearchFilters,
    settings: Settings,
    provider: EmbeddingProvider | None = None,
) -> list[float] | None:
    """Embedding du texte de recherche — ``None`` = rerank neutre.

    Conditions cumulatives (toute autre situation rend ``None``) :

    - ``SEARCH_RERANK_ENABLED`` (coupe-circuit d'exploitation : la cible
      p95 < 500 ms de D06 prime sur la pertinence) ;
    - une requête ``q`` non vide ;
    - un tri par ``relevance`` — en tri ``date``, l'ordre demandé par
      l'utilisateur n'est jamais réarrangé.

    L'appel provider passe par ``asyncio.to_thread`` : le provider local
    est du calcul pur, mais un fournisseur managé (Q11) ferait un appel
    réseau BLOQUANT dans la boucle d'événements. Toute erreur dégrade
    silencieusement vers un rerank neutre — jamais une recherche en échec.
    """
    if not settings.search_rerank_enabled or not filters.q or filters.sort != "relevance":
        return None
    embedder = provider
    try:
        if embedder is None:
            embedder = get_embedding_provider(settings)
        vectors = await asyncio.to_thread(embedder.embed_texts, [filters.q])
    except EmbeddingError as exc:
        logger.warning("search_query_embedding_failed error_code=%s", exc.error_code)
        return None
    if not vectors or not any(vectors[0]):
        return None
    return list(vectors[0])


# ---------------------------------------------------------------- protocole


class JobsRepository(Protocol):
    async def search(
        self,
        *,
        user_id: uuid.UUID,
        filters: SearchFilters,
        limit: int,
        cursor: SearchCursor | None,
        profile_id: uuid.UUID | None = None,
        scoring_version: str | None = None,
    ) -> list[JobSearchRow]:
        """Retourne jusqu'à ``limit + 1`` lignes (détection de page suivante)."""
        ...

    async def validated_profile_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """Profil VALIDÉ de l'utilisateur, ``None`` sinon."""
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
        profile_id: uuid.UUID | None = None,
        scoring_version: str | None = None,
    ) -> list[JobSearchRow]:
        stmt = build_search_statement(
            user_id, filters, limit, cursor,
            profile_id=profile_id, scoring_version=scoring_version,
        )
        result = await self._session.execute(stmt)
        joint = profile_id is not None and scoring_version is not None
        rows = [
            JobSearchRow(
                posting=ligne[0],
                saved_state=ligne[1],
                sort_value=ligne[2],
                match=(
                    MatchRowSummary(
                        score=ligne[3],
                        confidence=ligne[4],
                        low_data=bool(ligne[5]),
                        has_blocking=bool(ligne[6]),
                    )
                    if joint and ligne[3] is not None
                    else None
                ),
            )
            for ligne in result.all()
        ]
        settings = get_settings()
        return rerank_with_embeddings(
            rows,
            limit=limit,
            query_embedding=await _query_embedding(filters, settings),
            weights=RerankWeights.from_settings(settings),
        )

    async def validated_profile_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """Profil validé — condition d'existence d'un score comparable.

        Un profil ``draft`` n'a pas de ``match_results`` : joindre pour lui
        coûterait une jointure garantie vide à chaque recherche.
        """
        stmt = select(Profile.id).where(
            Profile.user_id == user_id, Profile.status == "validated"
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

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

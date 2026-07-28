"""Logique métier du module matching (E7, D02/D03) — fin du jalon M3.

Règles portées ici :
- ``GET /jobs/{id}/match`` : 409 ``profile_not_validated`` si le profil n'est
  pas validé (le moteur suppose un profil validé — fiabilité 1,0 côté
  candidat) ; calcul synchrone via ``app.matching`` (cible < 50 ms, aucun
  réseau — 06 §4 déclencheur c) avec cache ``match_results`` (upsert par
  (profil, offre, scoring_version)) ;
- invalidation du cache : recalcul paresseux si ``profile.version`` ou
  ``scoring_version`` a changé — la version de profil (et les
  ``explanation_facts``, consommés par le module explanations, D14) est
  stockée dans le jsonb ``dimension_scores`` sous ``_meta`` 🟡 (le schéma SQL
  n'a pas de colonne ``profile_version``) ;
- ``GET /matches`` : au M3, calcul PARESSEUX — les offres actives du
  pré-filtre (contrat accepté ou inconnu) plafonnées aux 200 plus récentes 🟡
  sont scorées à la volée (cache réutilisé) ; le re-scoring asynchrone
  complet (06 §4 déclencheurs a/b) arrive avec les embeddings (M4).
  🟡 Le pré-filtre « pays » de 06 §4 n'est pas applicable :
  ``preference_locations`` ne porte aucun code pays (seulement lat/lon) — la
  localisation est de toute façon scorée par le moteur, et les offres hors
  zone sortent par le score/bloquant. Tri score décroissant, pagination par
  curseur keyset (score, job_id) — même encodage opaque que le module jobs ;
- offre inexistante ou retirée (``withdrawn`` 🟡, aligné sur le module jobs)
  → 404 ; une offre expirée reste scorée (bandeau côté front) ;
- hook « preferences_changed » (RM-D-4) : au M3, invalidation simple des
  ``match_results`` de l'utilisateur (delete) — TODO(M4) : re-scoring
  asynchrone des offres actives.
"""

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from app.core.problems import Problem
from app.matching.config import ScoringConfig, get_config
from app.matching.engine import compute_match
from app.matching.models import CandidateInput, ExplanationFacts, JobInput
from app.matching.models import MatchResult as EngineMatchResult
from app.modules.jobs.models import JobPosting
from app.modules.jobs.repository import InvalidCursorError, decode_cursor, encode_cursor
from app.modules.jobs.schemas import (
    ContractType,
    JobCard,
    MatchSummary,
    RemotePolicy,
    SavedState,
    SearchPage,
)
from app.modules.jobs.service import format_salary_label
from app.modules.matching.adapters import candidate_input_from, job_input_from
from app.modules.matching.models import MatchResultRow
from app.modules.matching.repository import MatchingRepository
from app.modules.matching.schemas import (
    BlockingCriterionOut,
    DimensionOut,
    MatchResultOut,
    UnknownDimensionOut,
    UnknownReason,
)
from app.modules.preferences.repository import PreferencesData, PreferencesRepository
from app.modules.profiles.models import Profile
from app.modules.profiles.repository import ProfilesRepository

#: Signature du moteur — injectable pour compter les appels dans les tests.
MatchEngine = Callable[[CandidateInput, JobInput], EngineMatchResult]

#: Plafond du calcul paresseux de GET /matches 🟡 (M3 — voir docstring module).
MAX_LAZY_SCORED_JOBS = 200

#: Défaut produit du module preferences quand rien n'est enregistré 🟡.
_DEFAULT_CONTRACTS: tuple[str, ...] = ("permanent",)

#: Raisons internes du moteur → vocabulaire du contrat (openapi.yaml).
#: 🟡 ``unconvertible_value`` (devise non supportée) est assimilée à
#: ``low_extraction_confidence`` — pas de code dédié dans le contrat.
_REASON_TO_API: dict[str, UnknownReason] = {
    "job_missing": "job_not_provided",
    "candidate_missing": "profile_not_provided",
    "low_confidence": "low_extraction_confidence",
    "unconvertible_value": "low_extraction_confidence",
}


def _profile_not_validated() -> Problem:
    return Problem(
        status=409,
        code="profile_not_validated",
        title="Profil non validé",
        detail="Validez votre profil pour obtenir un score de matching.",
    )


def _job_not_found() -> Problem:
    return Problem(
        status=404,
        code="not_found",
        title="Ressource introuvable",
        detail="Offre introuvable.",
    )


def _jsonable(value: object) -> Any:
    """Conversion défensive vers des types JSON (tuples → listes)."""
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return value


def _facts_to_json(facts: ExplanationFacts) -> dict[str, Any]:
    """Sérialise les ``explanation_facts`` du moteur (bloquants en premier)."""

    def _fact(kind_facts: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [
            {
                "kind": fact.kind,
                "dimension": fact.dimension,
                "label": fact.label,
                "data": _jsonable(dict(fact.data)),
            }
            for fact in kind_facts
        ]

    return {
        "blocking": _fact(facts.blocking),
        "strengths": _fact(facts.strengths),
        "gaps": _fact(facts.gaps),
        "uncertain": _fact(facts.uncertain),
    }


@dataclass(frozen=True)
class MatchData:
    """Résultat de matching sérialisé — depuis le cache ou fraîchement calculé."""

    job_id: uuid.UUID
    profile_id: uuid.UUID
    profile_version: int
    scoring_version: str
    score: int
    confidence: int
    low_data: bool
    blocking_criteria: list[dict[str, Any]]
    unknown_dimensions: list[dict[str, Any]]
    dimensions: list[dict[str, Any]]
    explanation_facts: dict[str, Any]


@dataclass(frozen=True)
class _ScoringContext:
    """Données partagées par toutes les offres d'un même appel (voir
    ``MatchingService._load_context``)."""

    taxonomy: dict[uuid.UUID, str]
    skill_vectors: dict[uuid.UUID, list[float]]
    title_vectors: list[list[float]]


def _earliest_posted_at(posting: JobPosting) -> datetime | None:
    dates = [js.posted_at for js in posting.job_sources if js.posted_at is not None]
    return min(dates) if dates else None


class MatchingService:
    def __init__(
        self,
        profiles: ProfilesRepository,
        preferences: PreferencesRepository,
        repository: MatchingRepository,
        engine: MatchEngine = compute_match,
        config: ScoringConfig | None = None,
    ) -> None:
        self._profiles = profiles
        self._preferences = preferences
        self._repository = repository
        self._engine = engine
        self._config = config

    def _get_config(self) -> ScoringConfig:
        return self._config if self._config is not None else get_config()

    # ------------------------------------------------------------ garde-fous

    async def _validated_profile(self, user_id: uuid.UUID) -> Profile:
        """Profil validé requis — 409 ``profile_not_validated`` sinon (contrat)."""
        profile = await self._profiles.get_by_user(user_id)
        if profile is None or profile.status != "validated":
            raise _profile_not_validated()
        return profile

    # ------------------------------------------------------------ match unitaire

    async def get_match(self, user_id: uuid.UUID, job_id: uuid.UUID) -> MatchResultOut:
        """GET /jobs/{id}/match — réponse conforme au schéma MatchResult."""
        data = await self.get_match_data(user_id, job_id)
        return MatchResultOut(
            job_id=data.job_id,
            profile_version=data.profile_version,
            scoring_version=data.scoring_version,
            score=data.score,
            confidence=data.confidence,
            low_data=data.low_data,
            blocking_criteria=[
                BlockingCriterionOut.model_validate(item) for item in data.blocking_criteria
            ],
            unknown_dimensions=[
                UnknownDimensionOut.model_validate(item) for item in data.unknown_dimensions
            ],
            dimensions=[DimensionOut.model_validate(item) for item in data.dimensions],
        )

    async def get_match_data(self, user_id: uuid.UUID, job_id: uuid.UUID) -> MatchData:
        """Résultat (cache valide ou calcul synchrone) — consommé aussi par le
        module explanations (D14 : les facts viennent du match_result)."""
        profile = await self._validated_profile(user_id)
        job = await self._repository.get_job(job_id)
        if job is None or job.status == "withdrawn":
            raise _job_not_found()
        cached = self._from_valid_cache(await self._repository.get_cached(profile.id, job.id),
                                        profile)
        if cached is not None:
            return cached
        preferences = await self._preferences.get(user_id)
        context = await self._load_context(profile, [job])
        return await self._compute_and_store(profile, preferences, job, context)

    # ------------------------------------------------------------ cache

    def _from_valid_cache(
        self, row: MatchResultRow | None, profile: Profile
    ) -> MatchData | None:
        """Relit le cache s'il est encore valide (scoring_version ET version de
        profil identiques — sinon recalcul paresseux, 06 §4)."""
        if row is None or row.scoring_version != self._get_config().scoring_version:
            return None
        stored = row.dimension_scores
        if not isinstance(stored, dict):
            return None  # forme inattendue (ex. legacy '[]') → recalcul
        meta = stored.get("_meta")
        if not isinstance(meta, dict) or meta.get("profile_version") != profile.version:
            return None
        facts = meta.get("explanation_facts")
        if not isinstance(facts, dict):
            return None
        items = stored.get("items")
        return MatchData(
            job_id=row.job_posting_id,
            profile_id=row.profile_id,
            profile_version=profile.version,
            scoring_version=row.scoring_version,
            score=row.score,
            confidence=row.confidence,
            low_data=row.low_data,
            blocking_criteria=list(row.blocking_criteria),
            unknown_dimensions=list(row.unknown_dimensions),
            dimensions=list(items) if isinstance(items, list) else [],
            explanation_facts=facts,
        )

    async def _load_context(
        self, profile: Profile, jobs: Sequence[JobPosting]
    ) -> _ScoringContext:
        """Charge EN UNE FOIS tout ce que le moteur consomme hors ORM.

        Perf : ces trois lectures étaient faites par offre dans la boucle de
        ``list_matches`` (jusqu'à ``MAX_LAZY_SCORED_JOBS`` offres), soit autant
        de requêtes ramenant des ``vector(1024)``. Elles sont ici groupées pour
        toute la page.
        """
        skill_ids = list(
            dict.fromkeys(
                [s.skill_id for s in profile.skills if s.skill_id is not None]
                + [
                    s.skill_id
                    for job in jobs
                    for s in job.skills
                    if s.skill_id is not None
                ]
            )
        )
        return _ScoringContext(
            taxonomy=await self._repository.skill_labels(skill_ids),
            # Crédit « compétence proche » (06 §2.1) : actif dès que les
            # vecteurs existent, exact-only sinon — aucune régression quand la
            # table ``skills`` n'est pas encore vectorisée.
            skill_vectors=await self._repository.skill_embeddings(skill_ids),
            # 06 §2.3 : un vecteur PAR intitulé cible (max des cosinus) — le
            # vecteur agrégé ``profiles.embedding`` seul noierait l'intitulé le
            # mieux ciblé dans la moyenne.
            title_vectors=await self._repository.preference_title_embeddings(
                profile.user_id
            ),
        )

    async def _compute_and_store(
        self,
        profile: Profile,
        preferences: PreferencesData | None,
        job: JobPosting,
        context: _ScoringContext,
    ) -> MatchData:
        """Calcul synchrone (aucun réseau) + upsert dans ``match_results``."""
        taxonomy = context.taxonomy
        skill_vectors = context.skill_vectors

        candidate = candidate_input_from(
            profile,
            preferences,
            taxonomy,
            title_embeddings=context.title_vectors,
            skill_embeddings=skill_vectors or None,
        )
        job_input = job_input_from(
            job,
            job.skills,
            job.languages,
            job.locations,
            skills_taxonomy=taxonomy,
            # Le crédit « proche » exige un vecteur des DEUX côtés
            # (``matching/dimensions.py``) : sans celui-ci, le dictionnaire
            # d'embeddings de l'offre reste vide et le crédit ne tombe jamais.
            skill_embeddings=skill_vectors or None,
        )
        result = self._engine(candidate, job_input)
        data = self._serialize(result, profile, job)
        await self._repository.upsert_result(
            MatchResultRow(
                profile_id=data.profile_id,
                job_posting_id=data.job_id,
                scoring_version=data.scoring_version,
                score=data.score,
                confidence=data.confidence,
                low_data=data.low_data,
                blocking_criteria=data.blocking_criteria,
                unknown_dimensions=data.unknown_dimensions,
                dimension_scores={
                    # 🟡 _meta : profile_version (invalidation) + facts (D14) —
                    # le schéma SQL n'a ni colonne ni table dédiée.
                    "_meta": {
                        "profile_version": data.profile_version,
                        "explanation_facts": data.explanation_facts,
                    },
                    "items": data.dimensions,
                },
                computed_at=datetime.now(UTC),
            )
        )
        return data

    @staticmethod
    def _serialize(
        result: EngineMatchResult, profile: Profile, job: JobPosting
    ) -> MatchData:
        return MatchData(
            job_id=job.id,
            profile_id=profile.id,
            profile_version=profile.version,
            scoring_version=result.scoring_version,
            score=result.score,
            confidence=result.confidence,
            low_data=result.low_data,
            blocking_criteria=[
                {"code": item.code, "label": item.label} for item in result.blocking_criteria
            ],
            unknown_dimensions=[
                {
                    "dimension": item.dimension,
                    "reason": _REASON_TO_API.get(item.reason, "low_extraction_confidence"),
                    "label": item.label,
                }
                for item in result.unknown_dimensions
            ],
            dimensions=[
                {
                    "dimension": item.dimension,
                    "subscore": item.subscore,
                    "weight": item.weight,
                    "known": item.known,
                    "details": _jsonable(dict(item.details)),
                }
                for item in result.dimension_scores
            ],
            explanation_facts=_facts_to_json(result.explanation_facts),
        )

    # ------------------------------------------------------------ liste

    async def list_matches(
        self,
        user_id: uuid.UUID,
        *,
        min_score: int | None,
        include_blocked: bool,
        limit: int,
        cursor: str | None,
    ) -> SearchPage:
        """GET /matches — calcul paresseux M3 (voir docstring du module)."""
        profile = await self._validated_profile(user_id)
        decoded = None
        if cursor is not None:
            try:
                decoded = decode_cursor(cursor, expected_sort="match")
            except InvalidCursorError as exc:
                raise Problem(
                    status=422,
                    code="invalid_cursor",
                    title="Curseur invalide",
                    detail="Le curseur de pagination est illisible ou périmé. "
                    "Relancez la requête sans curseur.",
                ) from exc

        preferences = await self._preferences.get(user_id)
        contracts = (
            tuple(preferences.contract_types) if preferences is not None else _DEFAULT_CONTRACTS
        )
        jobs = await self._repository.list_recent_active(
            contracts=contracts, limit=MAX_LAZY_SCORED_JOBS
        )
        cached = await self._repository.get_cached_many(profile.id, [job.id for job in jobs])

        entries: list[tuple[JobPosting, MatchData]] = []
        context: _ScoringContext | None = None
        for job in jobs:
            data = self._from_valid_cache(cached.get(job.id), profile)
            if data is None:
                # Chargé au plus une fois par page, et seulement si au moins
                # une offre doit réellement être (re)calculée.
                if context is None:
                    context = await self._load_context(profile, jobs)
                data = await self._compute_and_store(profile, preferences, job, context)
            entries.append((job, data))

        if min_score is not None:
            entries = [entry for entry in entries if entry[1].score >= min_score]
        if not include_blocked:
            entries = [entry for entry in entries if not entry[1].blocking_criteria]

        # Tri score décroissant, départage par id — keyset (score, job_id).
        entries.sort(key=lambda entry: (entry[1].score, entry[0].id.int), reverse=True)
        if decoded is not None:
            threshold = (decoded.value, decoded.last_id.int)
            entries = [
                entry
                for entry in entries
                if (float(entry[1].score), entry[0].id.int) < threshold
            ]

        has_more = len(entries) > limit
        page = entries[:limit]
        next_cursor = None
        if has_more and page:
            last_job, last_data = page[-1]
            next_cursor = encode_cursor("match", float(last_data.score), last_job.id)

        saved = await self._repository.saved_states(user_id, [job.id for job, _ in page])
        items = [self._to_card(job, data, saved.get(job.id)) for job, data in page]
        return SearchPage(items=items, next_cursor=next_cursor)

    @staticmethod
    def _to_card(job: JobPosting, data: MatchData, saved_state: str | None) -> JobCard:
        # Les casts vers les Literal sont sûrs : colonnes ENUM PostgreSQL.
        return JobCard(
            id=job.id,
            title=job.title,
            company_name=job.company_name,
            locations=[loc.raw_label for loc in job.locations],
            remote=cast(RemotePolicy | None, job.remote),
            contract=cast(ContractType | None, job.contract),
            salary_label=format_salary_label(
                job.salary_min, job.salary_max, job.salary_currency, job.salary_period
            ),
            posted_at=_earliest_posted_at(job),
            match=MatchSummary(
                score=data.score,
                confidence=data.confidence,
                low_data=data.low_data,
                has_blocking=bool(data.blocking_criteria),
            ),
            saved_state=cast(SavedState | None, saved_state),
        )


# ---------------------------------------------------------------- hook D04


def make_preferences_changed_hook(
    repository: MatchingRepository,
) -> Callable[[uuid.UUID], Awaitable[None]]:
    """Hook « preferences_changed » (RM-D-4) branché sur le module matching.

    M3 : invalidation simple — suppression des ``match_results`` de
    l'utilisateur (les explications suivent par cascade) ; le prochain accès
    recalcule paresseusement. TODO(M4) : re-scoring asynchrone des offres
    actives (06 §4 déclencheur a) via worker.
    """

    async def preferences_changed(user_id: uuid.UUID) -> None:
        await repository.delete_for_user(user_id)

    return preferences_changed

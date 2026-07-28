"""Fixtures des tests API matching + explanations (fin du jalon M3).

Fakes en mémoire (patterns du module jobs) : profils, préférences, cache
``match_results`` / ``match_explanations`` et taxonomie de compétences. Le
moteur reste le vrai ``compute_match`` (déterministe), enveloppé d'un
compteur d'appels ; le provider LLM est le :class:`FakeProvider` avec une
sortie canned pilotable par test.

⚠️ Ces tests tournent sur une configuration de scoring **calibrée** pour le
provider d'embeddings actif, sans quoi ``title_similarity`` serait inconnue
partout (la config livrée porte ``calibrated_for_model: null`` — N14) et le
chemin « offre et profil ont tous deux un vecteur » ne serait jamais exercé.
Le comportement de la config LIVRÉE est vérifié par
``tests/unit/matching/test_shipped_config.py``.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeProvider
from app.matching.engine import compute_match
from app.matching.models import CandidateInput, JobInput
from app.matching.models import MatchResult as EngineMatchResult
from app.modules.explanations.repository import get_explanations_repository
from app.modules.explanations.router import get_llm_provider
from app.modules.explanations.service import FAKE_EXPLANATION
from app.modules.explanations.service import TASK as EXPLAIN_TASK
from app.modules.jobs.models import JobLanguage as JobLanguageRow
from app.modules.jobs.models import JobPosting
from app.modules.matching.models import MatchExplanationRow, MatchResultRow
from app.modules.matching.repository import get_matching_repository
from app.modules.matching.router import get_match_engine
from app.modules.preferences.repository import (
    LocationData,
    PreferencesData,
    get_preferences_repository,
)
from app.modules.profiles.models import Profile
from app.modules.profiles.repository import get_profiles_repository
from tests.unit.jobs.conftest import make_posting
from tests.unit.preferences.conftest import InMemoryPreferencesRepository
from tests.unit.profiles.conftest import InMemoryProfilesRepository, make_profile

# ------------------------------------------------------------------ fabriques


def make_job(
    *,
    experience_min: float | None = None,
    experience_max: float | None = None,
    languages: list[tuple[str, str, float]] | None = None,  # (code, niveau, confiance)
    **kwargs: Any,
) -> JobPosting:
    """Offre détachée (fabrique jobs) + relations manquantes pour le matching."""
    posting = make_posting(**kwargs)
    posting.experience_min = experience_min
    posting.experience_max = experience_max
    posting.languages = [
        JobLanguageRow(
            job_posting_id=posting.id, lang_code=code, min_level=level, confidence=conf
        )
        for code, level, conf in (languages or [])
    ]
    return posting


def make_validated_profile(user_id: uuid.UUID, *, version: int = 3) -> Profile:
    """Profil validé prêt pour le moteur : compétences, langue, séniorité."""
    profile = make_profile(
        user_id,
        status="validated",
        version=version,
        skills=[
            ("Python", "user_input", 1.0),
            ("FastAPI", "user_input", 1.0),
            ("PostgreSQL", "user_input", 1.0),
        ],
        languages=[("fr", "C2", "user_input")],
    )
    profile.seniority = "mid"
    profile.total_experience_years = 5.0
    return profile


def make_preferences(**overrides: Any) -> PreferencesData:
    """Préférences par défaut des tests (Lyon, CDI, 45 k€ souhaités)."""
    base: dict[str, Any] = {
        "remote_pref": "indifferent",
        "contract_types": ("permanent",),
        "contract_strict": False,
        "salary_min": 45000,
        "salary_min_strict": None,
        "locations": (LocationData(label="Lyon", lat=45.75, lon=4.85, radius_km=30),),
        "target_titles": (),
        "sectors_preferred": (),
        "sectors_excluded": (),
        "target_companies": (),
        "keywords": (),
    }
    base.update(overrides)
    return PreferencesData(**base)


# ------------------------------------------------------------------ fakes


class InMemoryExplanationsRepository:
    """Implémentation en mémoire du protocole ExplanationsRepository."""

    def __init__(self, profiles: InMemoryProfilesRepository) -> None:
        self._profiles = profiles
        self.rows: dict[tuple[uuid.UUID, uuid.UUID, str, str], dict[str, Any]] = {}

    async def get(
        self,
        profile_id: uuid.UUID,
        job_id: uuid.UUID,
        scoring_version: str,
        prompt_version: str,
    ) -> dict[str, Any] | None:
        return self.rows.get((profile_id, job_id, scoring_version, prompt_version))

    async def put(
        self,
        profile_id: uuid.UUID,
        job_id: uuid.UUID,
        scoring_version: str,
        prompt_version: str,
        content: dict[str, Any],
    ) -> None:
        self.rows[(profile_id, job_id, scoring_version, prompt_version)] = content

    def _profile_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        profile = self._profiles.profiles_by_user.get(user_id)
        return None if profile is None else profile.id

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        profile_id = self._profile_id(user_id)
        for key in [k for k in self.rows if k[0] == profile_id]:
            del self.rows[key]

    async def list_for_user(self, user_id: uuid.UUID) -> list[MatchExplanationRow]:
        profile_id = self._profile_id(user_id)
        return [
            MatchExplanationRow(
                id=uuid.uuid4(),
                profile_id=key[0],
                job_posting_id=key[1],
                scoring_version=key[2],
                prompt_version=key[3],
                content=content,
                created_at=datetime.now(UTC),
            )
            for key, content in self.rows.items()
            if key[0] == profile_id
        ]


class InMemoryMatchingRepository:
    """Implémentation en mémoire du protocole MatchingRepository.

    ``delete_for_user`` émule la cascade FK du schéma : les explications de
    l'utilisateur sont supprimées avec ses ``match_results``.
    """

    def __init__(
        self,
        profiles: InMemoryProfilesRepository,
        explanations: InMemoryExplanationsRepository | None = None,
    ) -> None:
        self._profiles = profiles
        self.explanations = explanations
        self.jobs: dict[uuid.UUID, JobPosting] = {}
        self.results: dict[tuple[uuid.UUID, uuid.UUID], MatchResultRow] = {}
        self.saved: dict[tuple[uuid.UUID, uuid.UUID], str] = {}
        self.skills: dict[uuid.UUID, str] = {}
        self.skill_vectors: dict[uuid.UUID, list[float]] = {}
        #: ``user_id`` → vecteurs de ``preference_titles.embedding`` (06 §2.3).
        self.title_vectors: dict[uuid.UUID, list[list[float]]] = {}
        #: Compteur d'appels par méthode — sert à prouver que les lectures de
        #: vecteurs ne sont PAS refaites offre par offre dans ``list_matches``.
        self.calls: dict[str, int] = {}

    def add(self, job: JobPosting) -> JobPosting:
        self.jobs[job.id] = job
        return job

    async def get_job(self, job_id: uuid.UUID) -> JobPosting | None:
        return self.jobs.get(job_id)

    async def list_recent_active(
        self, *, contracts: tuple[str, ...], limit: int
    ) -> list[JobPosting]:
        jobs = [
            job
            for job in self.jobs.values()
            if job.status == "active"
            and (not contracts or job.contract is None or job.contract in contracts)
        ]
        jobs.sort(key=lambda job: (job.last_seen_at, job.id.int), reverse=True)
        return jobs[:limit]

    def _record(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    async def skill_labels(self, skill_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        self._record("skill_labels")
        return {sid: self.skills[sid] for sid in skill_ids if sid in self.skills}

    async def skill_embeddings(
        self, skill_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[float]]:
        """Vecteurs de compétences — vide par défaut (exact-only, comme en
        production tant que la table ``skills`` n'est pas vectorisée)."""
        self._record("skill_embeddings")
        return {sid: self.skill_vectors[sid] for sid in skill_ids if sid in self.skill_vectors}

    async def preference_title_embeddings(self, user_id: uuid.UUID) -> list[list[float]]:
        """Vecteurs des intitulés cibles — vide par défaut (seul le vecteur
        agrégé ``profiles.embedding`` est alors utilisé, comme avant M4)."""
        self._record("preference_title_embeddings")
        return list(self.title_vectors.get(user_id, []))

    async def get_cached(
        self, profile_id: uuid.UUID, job_id: uuid.UUID
    ) -> MatchResultRow | None:
        return self.results.get((profile_id, job_id))

    async def get_cached_many(
        self, profile_id: uuid.UUID, job_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, MatchResultRow]:
        found: dict[uuid.UUID, MatchResultRow] = {}
        for job_id in job_ids:
            row = self.results.get((profile_id, job_id))
            if row is not None:
                found[job_id] = row
        return found

    async def upsert_result(self, row: MatchResultRow) -> None:
        self.results[(row.profile_id, row.job_posting_id)] = row

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        profile = self._profiles.profiles_by_user.get(user_id)
        if profile is None:
            return
        for key in [k for k in self.results if k[0] == profile.id]:
            del self.results[key]
        if self.explanations is not None:  # cascade FK émulée
            await self.explanations.delete_for_user(user_id)

    async def list_results_for_user(self, user_id: uuid.UUID) -> list[MatchResultRow]:
        profile = self._profiles.profiles_by_user.get(user_id)
        if profile is None:
            return []
        return [row for (pid, _), row in self.results.items() if pid == profile.id]

    async def saved_states(
        self, user_id: uuid.UUID, job_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        wanted = set(job_ids)
        return {
            job_id: state
            for (uid, job_id), state in self.saved.items()
            if uid == user_id and job_id in wanted
        }


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def profiles_repository() -> InMemoryProfilesRepository:
    return InMemoryProfilesRepository()


@pytest.fixture
def preferences_repository() -> InMemoryPreferencesRepository:
    return InMemoryPreferencesRepository()


@pytest.fixture
def explanations_repository(
    profiles_repository: InMemoryProfilesRepository,
) -> InMemoryExplanationsRepository:
    return InMemoryExplanationsRepository(profiles_repository)


@pytest.fixture
def matching_repository(
    profiles_repository: InMemoryProfilesRepository,
    explanations_repository: InMemoryExplanationsRepository,
) -> InMemoryMatchingRepository:
    return InMemoryMatchingRepository(profiles_repository, explanations_repository)


@pytest.fixture
def engine_calls() -> list[tuple[CandidateInput, JobInput]]:
    """Compteur d'appels au moteur (vérification du cache)."""
    return []


@pytest.fixture
def canned_explanation() -> dict[str, Any]:
    """Sortie canned du FakeProvider — mutable par test (contrôle numérique)."""
    return dict(FAKE_EXPLANATION)


@pytest.fixture
def llm_provider(canned_explanation: dict[str, Any]) -> FakeProvider:
    return FakeProvider(canned={EXPLAIN_TASK: canned_explanation})


@pytest.fixture
def client(
    client: TestClient,
    profiles_repository: InMemoryProfilesRepository,
    preferences_repository: InMemoryPreferencesRepository,
    matching_repository: InMemoryMatchingRepository,
    explanations_repository: InMemoryExplanationsRepository,
    engine_calls: list[tuple[CandidateInput, JobInput]],
    llm_provider: FakeProvider,
) -> TestClient:
    """Étend le client commun avec les fakes matching/explanations."""

    def counting_engine(candidate: CandidateInput, job: JobInput) -> EngineMatchResult:
        engine_calls.append((candidate, job))
        return compute_match(candidate, job)

    overrides = client.app.dependency_overrides
    overrides[get_profiles_repository] = lambda: profiles_repository
    overrides[get_preferences_repository] = lambda: preferences_repository
    overrides[get_matching_repository] = lambda: matching_repository
    overrides[get_explanations_repository] = lambda: explanations_repository
    overrides[get_match_engine] = lambda: counting_engine
    overrides[get_llm_provider] = lambda: llm_provider
    return client


@pytest.fixture(scope="session", autouse=True)
def _calibrated_scoring_config(tmp_path_factory: pytest.TempPathFactory):
    """Voir l'en-tête du module. Substitution par le CHEMIN par défaut :
    ``get_config`` est mis en cache par chemin, la config calibrée a donc sa
    propre entrée et n'écrase pas celle de la config livrée."""
    import app.matching.config as config_module
    from tests.unit.matching._calibration import write_calibrated_config

    source = Path(config_module._DEFAULT_CONFIG_PATH)
    calibree = write_calibrated_config(
        source, tmp_path_factory.mktemp("scoring") / "scoring-config.json"
    )
    config_module._DEFAULT_CONFIG_PATH = calibree
    yield
    config_module._DEFAULT_CONFIG_PATH = source

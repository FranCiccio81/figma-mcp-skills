"""Fixtures des tests du module generation (jalon M4).

Fakes en mémoire (patterns des modules jobs/matching) : documents générés,
offres et profils. Le provider LLM est le :class:`FakeProvider` avec des
sorties canned injectables PAR TÂCHE (``canned_outputs`` mutable par test) ;
l'enfilement Celery est remplacé par un simple recorder (``enqueued``) et le
worker est exécuté à la demande via :func:`run_generation` (même
orchestration ``execute_generation`` que la tâche ``ai.generate``).
"""

import asyncio
import uuid
from copy import deepcopy
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeProvider
from app.ai.tasks.generate import FAKE_GENERATION_OUTPUTS
from app.modules.generation.models import GeneratedDocument, api_status
from app.modules.generation.repository import get_generation_repository
from app.modules.generation.router import get_generation_enqueuer
from app.modules.generation.service import execute_generation
from app.modules.jobs.models import JobPosting
from app.modules.profiles.models import Profile
from app.modules.profiles.repository import get_profiles_repository
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.profiles.conftest import InMemoryProfilesRepository, make_profile

GENERATIONS_URL = "/api/v1/generations"


# ------------------------------------------------------------------ fabriques


def make_generation_profile(
    user_id: uuid.UUID, *, status: str = "validated", version: int = 4
) -> Profile:
    """Profil validé avec expériences/compétences/formation/résumé — les ids
    réels de ses éléments servent de références d'ancrage dans les tests."""
    profile = make_profile(
        user_id,
        status=status,
        version=version,
        skills=[
            ("Python", "user_confirmed", 1.0),
            ("FastAPI", "user_input", 1.0),
            ("PostgreSQL", "user_confirmed", 1.0),
        ],
        experiences=[(date(2020, 1, 1), None, "user_confirmed")],
        educations=[("Master Informatique", "user_confirmed")],
        languages=[("fr", "C2", "user_input")],
    )
    profile.headline = "Ingénieure backend"
    profile.summary = "Cinq ans de développement backend Python."
    return profile


# ------------------------------------------------------------------ fakes


class InMemoryGenerationRepository:
    """Implémentation en mémoire du protocole GenerationRepository."""

    def __init__(self) -> None:
        self.docs: dict[uuid.UUID, GeneratedDocument] = {}
        self.jobs: dict[uuid.UUID, JobPosting] = {}

    def add_job(self, job: JobPosting) -> JobPosting:
        self.jobs[job.id] = job
        return job

    async def add(self, document: GeneratedDocument) -> None:
        self.docs[document.id] = document

    async def get_for_user(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocument | None:
        document = self.docs.get(document_id)
        if document is None or document.user_id != user_id:
            return None
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> GeneratedDocument | None:
        return self.docs.get(document_id)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        doc_type: str | None,
        status: str | None,
        job_id: uuid.UUID | None,
        before: tuple[Any, uuid.UUID] | None,
        limit: int,
    ) -> list[GeneratedDocument]:
        rows = [d for d in self.docs.values() if d.user_id == user_id]
        if doc_type is not None:
            rows = [d for d in rows if d.doc_type == doc_type]
        if status is not None:
            rows = [d for d in rows if api_status(d) == status]
        if job_id is not None:
            rows = [d for d in rows if d.job_posting_id == job_id]
        rows.sort(key=lambda d: (d.created_at, d.id.int), reverse=True)
        if before is not None:
            before_at, before_id = before
            rows = [d for d in rows if (d.created_at, d.id.int) < (before_at, before_id.int)]
        return rows[:limit]

    async def get_job(self, job_id: uuid.UUID) -> JobPosting | None:
        return self.jobs.get(job_id)

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        for key in [k for k, d in self.docs.items() if d.user_id == user_id]:
            del self.docs[key]

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[GeneratedDocument]:
        rows = [d for d in self.docs.values() if d.user_id == user_id]
        rows.sort(key=lambda d: (d.created_at, d.id.int))
        return rows

    async def commit(self) -> None:  # mutations en place, rien à persister
        return None


# ------------------------------------------------------------------ helpers


def register(client: TestClient, email: str = "camille@example.eu") -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "un mot de passe très long",
            "locale": "fr",
            "accepted_terms_version": "2026-07",
            "accepted_privacy_version": "2026-07",
        },
    )
    assert response.status_code == 201


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["boussole_csrf"]}


def current_user_id(auth_repository: InMemoryAuthRepository) -> uuid.UUID:
    (user_id,) = auth_repository.users_by_id
    return user_id


def setup_validated_user(
    client: TestClient,
    auth_repository: InMemoryAuthRepository,
    profiles_repository: InMemoryProfilesRepository,
    *,
    status: str = "validated",
) -> tuple[uuid.UUID, Profile]:
    """Inscrit un utilisateur et pose son profil (validé par défaut)."""
    register(client)
    user_id = current_user_id(auth_repository)
    profile = make_generation_profile(user_id, status=status)
    profiles_repository.add(profile)
    return user_id, profile


def post_generation(
    client: TestClient,
    *,
    doc_type: str = "email",
    job_id: uuid.UUID | None = None,
    key: uuid.UUID | str | None = "auto",
    options: dict[str, Any] | None = None,
) -> Any:
    """POST /generations avec CSRF + Idempotency-Key (nouvelle clé par défaut)."""
    headers = csrf_headers(client)
    if key == "auto":
        headers["Idempotency-Key"] = str(uuid.uuid4())
    elif key is not None:
        headers["Idempotency-Key"] = str(key)
    body: dict[str, Any] = {"doc_type": doc_type}
    if job_id is not None:
        body["job_id"] = str(job_id)
    if options is not None:
        body["options"] = options
    return client.post(GENERATIONS_URL, json=body, headers=headers)


def run_generation(
    document_id: uuid.UUID,
    generation_repository: InMemoryGenerationRepository,
    profiles_repository: InMemoryProfilesRepository,
    provider: FakeProvider,
) -> dict[str, Any]:
    """Exécute la même orchestration que la tâche Celery ``ai.generate``."""
    return asyncio.run(
        execute_generation(document_id, generation_repository, profiles_repository, provider)
    )


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def profiles_repository() -> InMemoryProfilesRepository:
    return InMemoryProfilesRepository()


@pytest.fixture
def generation_repository() -> InMemoryGenerationRepository:
    return InMemoryGenerationRepository()


@pytest.fixture
def enqueued() -> list[uuid.UUID]:
    """Ids des documents enfilés (remplace ``celery_app.send_task``)."""
    return []


@pytest.fixture
def canned_outputs() -> dict[str, dict[str, Any]]:
    """Sorties canned du FakeProvider — mutables par test (ancrage piloté)."""
    return deepcopy(FAKE_GENERATION_OUTPUTS)


@pytest.fixture
def llm_provider(canned_outputs: dict[str, dict[str, Any]]) -> FakeProvider:
    return FakeProvider(canned=canned_outputs)


@pytest.fixture
def client(
    client: TestClient,
    profiles_repository: InMemoryProfilesRepository,
    generation_repository: InMemoryGenerationRepository,
    enqueued: list[uuid.UUID],
) -> TestClient:
    """Étend le client commun avec les fakes generation."""
    overrides = client.app.dependency_overrides
    overrides[get_profiles_repository] = lambda: profiles_repository
    overrides[get_generation_repository] = lambda: generation_repository
    overrides[get_generation_enqueuer] = lambda: enqueued.append
    return client

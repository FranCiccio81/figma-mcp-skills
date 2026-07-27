"""Fixtures des tests du module applications.

``InMemoryApplicationsRepository`` implémente le protocole
``ApplicationsRepository`` sans PostgreSQL : scoping utilisateur, filtre
``status``, keyset ``(created_at, id)`` décroissant et historique
d'événements sont reproduits en Python (patterns du module jobs).
"""

import itertools
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.modules.applications.models import Application, ApplicationEvent
from app.modules.applications.repository import (
    ApplicationCursor,
    JobRef,
    get_applications_repository,
)


def make_application(
    user_id: uuid.UUID,
    *,
    job_posting_id: uuid.UUID | None = None,
    external_title: str | None = None,
    external_company: str | None = None,
    external_url: str | None = None,
    status: str = "draft",
    applied_at: datetime | None = None,
    notes: str | None = None,
    created_at: datetime | None = None,
) -> Application:
    """Fabrique une candidature détachée (events vide, aucune session)."""
    now = created_at or datetime.now(UTC)
    application = Application(
        id=uuid.uuid4(),
        user_id=user_id,
        job_posting_id=job_posting_id,
        external_title=external_title,
        external_company=external_company,
        external_url=external_url,
        status=status,
        applied_at=applied_at,
        notes=notes,
        created_at=now,
        updated_at=now,
    )
    application.events = []
    return application


class InMemoryApplicationsRepository:
    """Implémentation en mémoire du protocole ApplicationsRepository."""

    def __init__(self) -> None:
        self.applications: dict[uuid.UUID, Application] = {}
        self.jobs: dict[uuid.UUID, JobRef] = {}
        #: Nombre de REQUÊTES de résolution des libellés d'offre — permet aux
        #: tests d'affirmer l'absence de N+1 (une seule requête par page).
        #: Compté comme en SQL : un lot vide ne déclenche aucune requête.
        self.job_ref_calls = 0
        self._event_seq = itertools.count(1)

    def add(self, application: Application) -> Application:
        self.applications[application.id] = application
        return application

    def add_job(
        self,
        job_posting_id: uuid.UUID,
        *,
        title: str = "Développeuse backend",
        company: str = "ACME",
    ) -> uuid.UUID:
        """Enregistre une offre interne connue (title / company_name)."""
        self.jobs[job_posting_id] = JobRef(title=title, company=company)
        return job_posting_id

    async def list_for_user(
        self,
        *,
        user_id: uuid.UUID,
        status: str | None,
        limit: int,
        cursor: ApplicationCursor | None,
    ) -> list[Application]:
        rows = [
            application
            for application in self.applications.values()
            if application.user_id == user_id
            and (status is None or application.status == status)
        ]
        rows.sort(key=lambda a: (a.created_at, a.id.int), reverse=True)
        if cursor is not None:
            rows = [
                a
                for a in rows
                if (a.created_at, a.id.int) < (cursor.created_at, cursor.last_id.int)
            ]
        return rows[: limit + 1]

    async def get_for_user(
        self, application_id: uuid.UUID, user_id: uuid.UUID
    ) -> Application | None:
        application = self.applications.get(application_id)
        if application is None or application.user_id != user_id:
            return None
        return application

    async def get_job_ref(self, job_posting_id: uuid.UUID) -> JobRef | None:
        self.job_ref_calls += 1
        return self.jobs.get(job_posting_id)

    async def job_refs(
        self, job_posting_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, JobRef]:
        wanted = list(dict.fromkeys(job_posting_ids))
        if not wanted:
            return {}  # comme en SQL : aucune requête pour un lot vide
        self.job_ref_calls += 1
        return {job_id: self.jobs[job_id] for job_id in wanted if job_id in self.jobs}

    async def create(self, application: Application) -> Application:
        return self.add(application)

    async def save(self, application: Application) -> None:
        self.applications[application.id] = application

    async def add_event(self, application: Application, event: ApplicationEvent) -> None:
        event.id = next(self._event_seq)
        application.events.append(event)

    async def delete(self, application: Application) -> None:
        self.applications.pop(application.id, None)

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        self.applications = {
            application_id: application
            for application_id, application in self.applications.items()
            if application.user_id != user_id
        }

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[Application]:
        rows = [a for a in self.applications.values() if a.user_id == user_id]
        rows.sort(key=lambda a: (a.created_at, a.id.int))
        return rows


@pytest.fixture
def applications_repository() -> InMemoryApplicationsRepository:
    return InMemoryApplicationsRepository()


@pytest.fixture
def client(
    client: TestClient, applications_repository: InMemoryApplicationsRepository
) -> TestClient:
    """Étend le client commun (tests/unit/conftest.py) avec le repo applications."""
    client.app.dependency_overrides[get_applications_repository] = (
        lambda: applications_repository
    )
    return client

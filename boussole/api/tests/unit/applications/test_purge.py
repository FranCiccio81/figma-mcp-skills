"""Tests de la purge / export RGPD (D21) du module applications.

Repository injecté (fake en mémoire) — le chemin par défaut (session
SQLAlchemy via la fabrique globale) est couvert par les tests d'intégration.
"""

import uuid
from datetime import UTC, datetime

from app.modules.applications import purge
from app.modules.applications.models import ApplicationEvent
from tests.unit.applications.conftest import (
    InMemoryApplicationsRepository,
    make_application,
)


async def _seed(
    repository: InMemoryApplicationsRepository, user_id: uuid.UUID
) -> uuid.UUID:
    application = repository.add(
        make_application(
            user_id,
            external_title="Dev",
            external_company="ACME",
            notes="à relancer",
        )
    )
    await repository.add_event(
        application,
        ApplicationEvent(
            application_id=application.id,
            from_status="draft",
            to_status="applied",
            note="Envoyée",
            at=datetime.now(UTC),
        ),
    )
    application.status = "applied"
    application.applied_at = datetime.now(UTC)
    return application.id


class TestPurge:
    async def test_purge_user_removes_only_that_users_applications(
        self, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        user, other = uuid.uuid4(), uuid.uuid4()
        await _seed(applications_repository, user)
        other_app_id = await _seed(applications_repository, other)

        await purge.purge_user(user, repository=applications_repository)

        assert await applications_repository.list_all_for_user(user) == []
        remaining = await applications_repository.list_all_for_user(other)
        assert [a.id for a in remaining] == [other_app_id]

    async def test_export_user_returns_applications_with_events(
        self, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        user = uuid.uuid4()
        application_id = await _seed(applications_repository, user)

        export = await purge.export_user(user, repository=applications_repository)

        (entry,) = export["applications"]
        assert entry["id"] == str(application_id)
        assert entry["external_title"] == "Dev"
        assert entry["external_company"] == "ACME"
        assert entry["status"] == "applied"
        assert entry["notes"] == "à relancer"
        assert entry["applied_at"] is not None
        (event,) = entry["events"]
        assert event == {
            "from_status": "draft",
            "to_status": "applied",
            "note": "Envoyée",
            "at": event["at"],
        }
        assert event["at"]  # horodatage ISO présent

    async def test_export_user_without_data_is_empty(
        self, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        assert (
            await purge.export_user(uuid.uuid4(), repository=applications_repository)
            == {}
        )

"""Purge / export RGPD du module applications (D21).

Chaque module expose ``purge_user`` / ``export_user`` ; le module ``privacy``
orchestre, journalise et vérifie l'exhaustivité (registre déclaratif — M5).
La suppression des ``applications`` cascade sur ``application_events``
(FK ON DELETE CASCADE — et suppression explicite côté repository).

``repository`` est injectable (tests unitaires : fake en mémoire) ; par
défaut, une session SQLAlchemy est ouverte via la fabrique globale.
"""

import uuid
from typing import Any

from app.core.db import get_session_factory
from app.modules.applications.models import Application
from app.modules.applications.repository import (
    ApplicationsRepository,
    SqlAlchemyApplicationsRepository,
)


async def purge_user(
    user_id: uuid.UUID, repository: ApplicationsRepository | None = None
) -> None:
    """Supprime physiquement candidatures ET historique de l'utilisateur."""
    if repository is not None:
        await repository.delete_for_user(user_id)
        return
    factory = get_session_factory()
    async with factory() as session:
        await SqlAlchemyApplicationsRepository(session).delete_for_user(user_id)


async def export_user(
    user_id: uuid.UUID, repository: ApplicationsRepository | None = None
) -> dict[str, Any]:
    """Export RGPD (art. 20) des candidatures et de leur historique."""
    if repository is not None:
        rows = await repository.list_all_for_user(user_id)
    else:
        factory = get_session_factory()
        async with factory() as session:
            rows = await SqlAlchemyApplicationsRepository(session).list_all_for_user(user_id)
    if not rows:
        return {}
    return {"applications": [_application_payload(row) for row in rows]}


def _application_payload(application: Application) -> dict[str, Any]:
    return {
        "id": str(application.id),
        "job_posting_id": (
            str(application.job_posting_id)
            if application.job_posting_id is not None
            else None
        ),
        "external_title": application.external_title,
        "external_company": application.external_company,
        "external_url": application.external_url,
        "status": application.status,
        "applied_at": (
            application.applied_at.isoformat() if application.applied_at is not None else None
        ),
        "notes": application.notes,
        "created_at": application.created_at.isoformat(),
        "updated_at": application.updated_at.isoformat(),
        "events": [
            {
                "from_status": event.from_status,
                "to_status": event.to_status,
                "note": event.note,
                "at": event.at.isoformat(),
            }
            for event in application.events
        ],
    }

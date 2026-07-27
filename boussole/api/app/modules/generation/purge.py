"""Purge / export RGPD du module generation (D21) — jalon M4.

Chaque module expose ``purge_user`` / ``export_user`` ; le module ``privacy``
orchestre, journalise et vérifie l'exhaustivité (registre déclaratif — M5).
``repository`` est injectable (tests unitaires : fake en mémoire) ; par
défaut, une session SQLAlchemy est ouverte via la fabrique globale.
"""

import uuid
from typing import Any

from app.core.db import get_session_factory
from app.modules.generation.models import GeneratedDocument, api_status
from app.modules.generation.repository import (
    GenerationRepository,
    SqlAlchemyGenerationRepository,
)


async def purge_user(
    user_id: uuid.UUID, repository: GenerationRepository | None = None
) -> None:
    """Supprime physiquement tous les documents générés de l'utilisateur."""
    if repository is not None:
        await repository.delete_for_user(user_id)
        return
    factory = get_session_factory()
    async with factory() as session:
        await SqlAlchemyGenerationRepository(session).delete_for_user(user_id)


def _document_payload(row: GeneratedDocument) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "doc_type": row.doc_type,
        "status": api_status(row),
        "job_posting_id": str(row.job_posting_id) if row.job_posting_id else None,
        "application_id": str(row.application_id) if row.application_id else None,
        "based_on_profile_version": row.based_on_profile_version,
        "prompt_version": row.prompt_version,
        "content": row.content,
        "anchoring_check": row.anchoring_check,
        "manually_edited": row.manually_edited,
        "options": row.options,
        "error_code": row.error_code,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
    }


async def export_user(
    user_id: uuid.UUID, repository: GenerationRepository | None = None
) -> dict[str, Any]:
    """Export RGPD (art. 20) des contenus générés de l'utilisateur."""
    if repository is not None:
        rows = await repository.list_all_for_user(user_id)
    else:
        factory = get_session_factory()
        async with factory() as session:
            rows = await SqlAlchemyGenerationRepository(session).list_all_for_user(user_id)
    if not rows:
        return {}
    return {"generated_documents": [_document_payload(row) for row in rows]}

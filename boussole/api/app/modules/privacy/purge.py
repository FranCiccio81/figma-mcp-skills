"""Purge / export RGPD du module privacy lui-même (D21) — M5.

Données propres du module : les demandes d'export (``privacy_exports``) et
leurs archives stockées. Le module privacy n'apparaît PAS dans le registre
d'orchestration (il en est l'orchestrateur) : ``purge_runner`` purge ces
données directement — ces interfaces existent pour honorer le contrat D21
(tout module expose ``purge_user`` / ``export_user``).
"""

import uuid
from typing import Any

from app.core.db import get_session_factory
from app.modules.privacy.repository import SqlAlchemyPrivacyRepository
from app.modules.privacy.storage import get_object_storage


async def purge_user(user_id: uuid.UUID) -> None:
    """Supprime les archives d'export (objets + lignes) de l'utilisateur."""
    factory = get_session_factory()
    async with factory() as session:
        repository = SqlAlchemyPrivacyRepository(session)
        storage = get_object_storage()
        for export in await repository.list_exports_for_user(user_id):
            if export.file_key:
                await storage.delete(export.file_key)
        await repository.delete_exports_for_user(user_id)


async def export_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Export RGPD (art. 20) : métadonnées des demandes d'export."""
    factory = get_session_factory()
    async with factory() as session:
        repository = SqlAlchemyPrivacyRepository(session)
        exports = await repository.list_exports_for_user(user_id)
        if not exports:
            return {}
        return {
            "privacy_exports": [
                {
                    "id": str(export.id),
                    "status": export.status,
                    "created_at": export.created_at.isoformat(),
                    "expires_at": (
                        export.expires_at.isoformat() if export.expires_at else None
                    ),
                }
                for export in exports
            ]
        }

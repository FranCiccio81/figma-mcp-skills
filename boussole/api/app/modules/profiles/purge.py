"""Purge / export RGPD du module profiles (D21) — profil + documents CV.

Chaque module expose ``purge_user`` / ``export_user`` ; le module ``privacy``
orchestre, journalise et vérifie l'exhaustivité (registre déclaratif — M5).
La suppression du profil cascade sur les sous-ressources (expériences,
formations, compétences, langues) via ``cascade='all, delete-orphan'``.

M4 : les ``cv_documents`` (et leurs ``extraction_runs``) appartiennent au
domaine profil — purgés ici, objets stockés (fichier, texte brut RM-B-7,
sorties d'extraction) supprimés du stockage, métadonnées incluses dans
l'export (jamais le binaire).

``cv_repository`` / ``profiles_repository`` / ``storage`` sont injectables
(tests unitaires : fakes en mémoire) ; par défaut, session SQLAlchemy via
la fabrique globale + stockage de configuration.
"""

import logging
import uuid
from typing import Any

from app.core.db import get_session_factory
from app.core.storage import ObjectStorage, get_object_storage
from app.modules.profiles.cv.models import CvDocument
from app.modules.profiles.cv.repository import (
    CvDocumentsRepository,
    SqlAlchemyCvDocumentsRepository,
)
from app.modules.profiles.repository import (
    ProfilesRepository,
    SqlAlchemyProfilesRepository,
)
from app.modules.profiles.service import to_profile_out

logger = logging.getLogger(__name__)


async def _delete_cv_data(
    user_id: uuid.UUID, cv_repository: CvDocumentsRepository, storage: ObjectStorage
) -> None:
    """Supprime documents + runs + objets stockés (au mieux — idempotent)."""
    for document in await cv_repository.list_for_user(user_id):
        keys = [document.file_key]
        if document.raw_text_key is not None:
            keys.append(document.raw_text_key)
        keys.extend(
            run.output_key
            for run in await cv_repository.runs_for_document(document.id)
            if run.output_key is not None
        )
        for key in keys:
            try:
                storage.delete(key)
            except Exception:  # purge au mieux : la ligne DB part quoi qu'il arrive
                logger.warning("cv_purge_storage_delete_failed key=%s", key)
    await cv_repository.delete_for_user(user_id)


def _cv_document_export(document: CvDocument) -> dict[str, Any]:
    """Métadonnées d'un document CV (art. 20) — jamais le binaire."""
    return {
        "id": str(document.id),
        "filename": document.filename,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "status": document.status,
        "error_code": document.error_code,
        "created_at": (
            document.created_at.isoformat() if document.created_at is not None else None
        ),
    }


async def purge_user(
    user_id: uuid.UUID,
    *,
    cv_repository: CvDocumentsRepository | None = None,
    profiles_repository: ProfilesRepository | None = None,
    storage: ObjectStorage | None = None,
) -> None:
    """Supprime physiquement profil, sous-ressources et documents CV."""
    storage = storage if storage is not None else get_object_storage()
    if cv_repository is not None and profiles_repository is not None:
        await _delete_cv_data(user_id, cv_repository, storage)
        await profiles_repository.delete_by_user(user_id)
        return

    factory = get_session_factory()
    async with factory() as session:
        await _delete_cv_data(
            user_id,
            cv_repository or SqlAlchemyCvDocumentsRepository(session),
            storage,
        )
        await (profiles_repository or SqlAlchemyProfilesRepository(session)).delete_by_user(
            user_id
        )


async def export_user(
    user_id: uuid.UUID,
    *,
    cv_repository: CvDocumentsRepository | None = None,
    profiles_repository: ProfilesRepository | None = None,
) -> dict[str, Any]:
    """Export RGPD (art. 20) : profil + métadonnées des documents CV."""
    export: dict[str, Any] = {}
    if cv_repository is not None and profiles_repository is not None:
        profile = await profiles_repository.get_by_user(user_id)
        documents = await cv_repository.list_for_user(user_id)
    else:
        factory = get_session_factory()
        async with factory() as session:
            profiles = profiles_repository or SqlAlchemyProfilesRepository(session)
            documents_repo = cv_repository or SqlAlchemyCvDocumentsRepository(session)
            profile = await profiles.get_by_user(user_id)
            documents = await documents_repo.list_for_user(user_id)

    if profile is not None:
        export["profile"] = to_profile_out(profile).model_dump(mode="json")
    if documents:
        export["cv_documents"] = [_cv_document_export(document) for document in documents]
    return export

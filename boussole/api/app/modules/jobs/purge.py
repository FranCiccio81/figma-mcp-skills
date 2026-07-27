"""Purge / export RGPD du module jobs (D21).

Le module ``jobs`` détient UNE table de données personnelles : ``saved_jobs``
(état ``saved`` / ``hidden`` posé par l'utilisateur sur une offre). Les offres
elles-mêmes (``job_postings``) sont des données publiques mutualisées : elles
ne sont NI exportées NI supprimées à la suppression d'un compte.

``repository`` est injectable (tests unitaires : fake en mémoire) ; par
défaut, une session SQLAlchemy est ouverte via la fabrique globale — même
patron que ``matching``/``explanations``/``applications``.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_factory
from app.modules.jobs.models import SavedJob


@dataclass(frozen=True, slots=True)
class SavedJobRow:
    """Ligne ``saved_jobs`` telle qu'exportée (art. 20)."""

    job_posting_id: uuid.UUID
    state: str
    created_at: datetime | None


class SavedJobsPurgeRepository(Protocol):
    """Accès minimal aux ``saved_jobs`` requis par la purge/l'export RGPD."""

    async def list_saved_for_user(self, user_id: uuid.UUID) -> list[SavedJobRow]: ...

    async def delete_saved_for_user(self, user_id: uuid.UUID) -> None: ...


class SqlAlchemySavedJobsPurgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_saved_for_user(self, user_id: uuid.UUID) -> list[SavedJobRow]:
        rows = (
            (
                await self._session.execute(
                    select(SavedJob)
                    .where(SavedJob.user_id == user_id)
                    .order_by(SavedJob.job_posting_id)
                )
            )
            .scalars()
            .all()
        )
        return [
            SavedJobRow(
                job_posting_id=row.job_posting_id,
                state=row.state,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def delete_saved_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(delete(SavedJob).where(SavedJob.user_id == user_id))
        await self._session.commit()


async def purge_user(
    user_id: uuid.UUID, repository: SavedJobsPurgeRepository | None = None
) -> None:
    """Supprime physiquement tous les ``saved_jobs`` de l'utilisateur.

    Idempotente : une seconde exécution ne supprime rien et ne lève pas.
    """
    if repository is not None:
        await repository.delete_saved_for_user(user_id)
        return
    factory = get_session_factory()
    async with factory() as session:
        await SqlAlchemySavedJobsPurgeRepository(session).delete_saved_for_user(user_id)


async def export_user(
    user_id: uuid.UUID, repository: SavedJobsPurgeRepository | None = None
) -> dict[str, Any]:
    """Export RGPD (art. 20) des offres sauvegardées/masquées de l'utilisateur.

    Seul l'ÉTAT posé par l'utilisateur est exporté (identifiant d'offre, état,
    date) : le contenu des offres est une donnée publique, hors art. 20.
    """
    if repository is not None:
        rows = await repository.list_saved_for_user(user_id)
    else:
        factory = get_session_factory()
        async with factory() as session:
            rows = await SqlAlchemySavedJobsPurgeRepository(session).list_saved_for_user(
                user_id
            )
    if not rows:
        return {}
    return {
        "saved_jobs": [
            {
                "job_posting_id": str(row.job_posting_id),
                "state": row.state,
                "created_at": (
                    row.created_at.isoformat() if row.created_at is not None else None
                ),
            }
            for row in rows
        ]
    }

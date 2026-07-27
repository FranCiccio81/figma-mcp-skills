"""Accès aux lignes ``ai_calls`` pour la purge / l'export RGPD (D21).

Protocole injectable (tests unitaires : fake en mémoire) + implémentation
SQLAlchemy, même patron que les autres modules de données.
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.calls import AiCall


class AiCallsRepository(Protocol):
    """Opérations RGPD sur le journal des appels IA."""

    async def anonymize_user(self, user_id: uuid.UUID) -> int:
        """Détache les lignes de l'utilisateur (``user_id → NULL``).

        Retourne le nombre de lignes anonymisées. Idempotente : un second
        appel n'a plus rien à détacher et retourne 0.
        """
        ...

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[AiCall]:
        """Lignes encore rattachées à l'utilisateur (ordre chronologique)."""
        ...


class SqlAlchemyAiCallsRepository:
    """Implémentation SQL du protocole :class:`AiCallsRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def anonymize_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            update(AiCall).where(AiCall.user_id == user_id).values(user_id=None)
        )
        await self._session.commit()
        # ``rowcount`` n'existe que sur le ``CursorResult`` d'un DML : accès
        # défensif (le typage générique de ``execute`` ne l'expose pas).
        return int(getattr(result, "rowcount", 0) or 0)

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[AiCall]:
        rows = await self._session.execute(
            select(AiCall).where(AiCall.user_id == user_id).order_by(AiCall.created_at)
        )
        return rows.scalars().all()

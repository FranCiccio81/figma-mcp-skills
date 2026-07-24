"""Accès aux données du module explanations — cache ``match_explanations``.

Cache par (profile, job, scoring_version, prompt_version) — contrainte
UNIQUE du schéma. Le protocole permet une implémentation en mémoire dans
les tests (pas de PostgreSQL requis).
"""

import uuid
from typing import Any, Protocol

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.modules.matching.models import MatchExplanationRow
from app.modules.profiles.models import Profile


class ExplanationsRepository(Protocol):
    async def get(
        self,
        profile_id: uuid.UUID,
        job_id: uuid.UUID,
        scoring_version: str,
        prompt_version: str,
    ) -> dict[str, Any] | None:
        """Contenu en cache (schéma ``match_explanation``) — None si absent."""
        ...

    async def put(
        self,
        profile_id: uuid.UUID,
        job_id: uuid.UUID,
        scoring_version: str,
        prompt_version: str,
        content: dict[str, Any],
    ) -> None:
        """Upsert du contenu validé (clé unique du schéma)."""
        ...

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        """Purge D21 : supprime toutes les explications de l'utilisateur."""
        ...

    async def list_for_user(self, user_id: uuid.UUID) -> list[MatchExplanationRow]:
        """Export RGPD D21 : explications du profil de l'utilisateur."""
        ...


class SqlAlchemyExplanationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        profile_id: uuid.UUID,
        job_id: uuid.UUID,
        scoring_version: str,
        prompt_version: str,
    ) -> dict[str, Any] | None:
        stmt = select(MatchExplanationRow.content).where(
            MatchExplanationRow.profile_id == profile_id,
            MatchExplanationRow.job_posting_id == job_id,
            MatchExplanationRow.scoring_version == scoring_version,
            MatchExplanationRow.prompt_version == prompt_version,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def put(
        self,
        profile_id: uuid.UUID,
        job_id: uuid.UUID,
        scoring_version: str,
        prompt_version: str,
        content: dict[str, Any],
    ) -> None:
        stmt = (
            pg_insert(MatchExplanationRow)
            .values(
                id=uuid.uuid4(),
                profile_id=profile_id,
                job_posting_id=job_id,
                scoring_version=scoring_version,
                prompt_version=prompt_version,
                content=content,
            )
            .on_conflict_do_update(
                index_elements=[
                    MatchExplanationRow.profile_id,
                    MatchExplanationRow.job_posting_id,
                    MatchExplanationRow.scoring_version,
                    MatchExplanationRow.prompt_version,
                ],
                set_={"content": content},
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        profile_ids = select(Profile.id).where(Profile.user_id == user_id).scalar_subquery()
        await self._session.execute(
            delete(MatchExplanationRow).where(MatchExplanationRow.profile_id.in_(profile_ids))
        )
        await self._session.commit()

    async def list_for_user(self, user_id: uuid.UUID) -> list[MatchExplanationRow]:
        profile_ids = select(Profile.id).where(Profile.user_id == user_id).scalar_subquery()
        stmt = select(MatchExplanationRow).where(
            MatchExplanationRow.profile_id.in_(profile_ids)
        )
        return list((await self._session.execute(stmt)).scalars().all())


async def get_explanations_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ExplanationsRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyExplanationsRepository(session)

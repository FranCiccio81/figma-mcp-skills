"""Accès aux données du module auth.

Le protocole ``AuthRepository`` permet de substituer une implémentation en
mémoire dans les tests unitaires (pas de PostgreSQL requis).
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.modules.auth.models import Consent, User


class AuthRepository(Protocol):
    async def get_user_by_email(self, email: str) -> User | None: ...

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        locale: str,
        consents: Sequence[tuple[str, str]],  # (kind, version)
    ) -> User: ...


class SqlAlchemyAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        locale: str,
        consents: Sequence[tuple[str, str]],
    ) -> User:
        user = User(email=email, password_hash=password_hash, locale=locale)
        self._session.add(user)
        await self._session.flush()
        for kind, version in consents:
            self._session.add(Consent(user_id=user.id, kind=kind, version=version))
        await self._session.commit()
        return user


async def get_auth_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AuthRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyAuthRepository(session)

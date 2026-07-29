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

    async def email_taken(self, email: str) -> bool: ...

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

    async def email_taken(self, email: str) -> bool:
        """Adresse occupée, y compris par un compte SUPPRIMÉ mais non purgé.

        ``users.email`` porte un index unique qui ne connaît pas
        ``deleted_at`` : l'adresse reste réservée pendant les 30 jours de
        rétention. ``get_user_by_email`` filtre les comptes supprimés — c'est
        juste pour la connexion, faux pour l'inscription.

        Sans cette distinction, se réinscrire après avoir supprimé son compte
        rendait **500** (``UniqueViolationError``) pendant un mois, sans la
        moindre explication. Et le 500 était un oracle d'énumération à
        l'envers : il distinguait « adresse jamais vue » (201 neutre) de
        « adresse d'un compte récemment supprimé » (500), exactement ce que
        la réponse neutre existe pour empêcher.
        """
        stmt = select(User.id).where(User.email == email).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

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

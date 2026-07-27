"""Accès aux données du module profiles.

Le protocole ``ProfilesRepository`` est volontairement étroit : il charge (ou
crée) l'agrégat profil complet et persiste les mutations faites par le service
directement sur les instances ORM (les collections ``experiences`` /
``educations`` / ``skills`` / ``languages`` portent ``cascade='all,
delete-orphan'`` : ajout/retrait dans la liste = INSERT/DELETE en base).
L'implémentation en mémoire des tests manipule les mêmes instances détachées.
"""

import uuid
from datetime import UTC, datetime
from typing import Protocol

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db_session
from app.modules.profiles.models import Profile


class ProfilesRepository(Protocol):
    async def get_by_user(self, user_id: uuid.UUID) -> Profile | None:
        """Profil de l'utilisateur, collections chargées — None s'il n'existe pas."""
        ...

    async def create_draft(self, user_id: uuid.UUID) -> Profile:
        """Crée le profil draft vide (version 1) — idempotent en cas de course."""
        ...

    async def commit(self) -> None:
        """Persiste les mutations faites sur l'agrégat chargé."""
        ...

    async def delete_by_user(self, user_id: uuid.UUID) -> None:
        """Supprime le profil et ses sous-ressources (purge RGPD, D21)."""
        ...


class SqlAlchemyProfilesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user(self, user_id: uuid.UUID) -> Profile | None:
        stmt = (
            select(Profile)
            .where(Profile.user_id == user_id)
            .options(
                selectinload(Profile.experiences),
                selectinload(Profile.educations),
                selectinload(Profile.skills),
                selectinload(Profile.languages),
            )
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_draft(self, user_id: uuid.UUID) -> Profile:
        profile = Profile(
            user_id=user_id,
            status="draft",
            version=1,
            updated_at=datetime.now(UTC),
        )
        # Collections initialisées vides : l'agrégat est utilisable sans
        # rechargement (expire_on_commit=False côté fabrique de sessions).
        profile.experiences = []
        profile.educations = []
        profile.skills = []
        profile.languages = []
        self._session.add(profile)
        try:
            await self._session.commit()
        except IntegrityError:
            # Course entre deux requêtes : l'unique (user_id) a tranché,
            # on relit le profil gagnant.
            await self._session.rollback()
            existing = await self.get_by_user(user_id)
            if existing is None:  # pragma: no cover - IntegrityError non liée
                raise
            return existing
        return profile

    async def commit(self) -> None:
        await self._session.commit()

    async def delete_by_user(self, user_id: uuid.UUID) -> None:
        profile = await self.get_by_user(user_id)
        if profile is not None:
            await self._session.delete(profile)
            await self._session.commit()


async def get_profiles_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ProfilesRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyProfilesRepository(session)

"""Moteur SQLAlchemy async + fabrique de sessions.

Le moteur est créé paresseusement : l'import du module ne tente aucune
connexion (les tests unitaires substituent les dépendances).
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles.

    Le schéma SQL n'utilise que ``timestamptz`` : tout ``datetime`` Python doit
    être mappé ``TIMESTAMP(timezone=True)``, sans quoi asyncpg caste les binds
    en ``TIMESTAMP WITHOUT TIME ZONE`` et rejette les datetimes aware
    (pagination par date, ``posted_since``).
    """

    type_annotation_map: ClassVar[dict[type, object]] = {datetime: DateTime(timezone=True)}


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=settings.debug)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Dépendance FastAPI : une session par requête."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def check_database() -> bool:
    """Sonde de readiness : SELECT 1."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # sonde volontairement large
        return False

"""Purge / export RGPD du module preferences (D21).

Chaque module expose ``purge_user`` / ``export_user`` ; le module ``privacy``
orchestre, journalise et vérifie l'exhaustivité (registre déclaratif — M5).
"""

import uuid
from dataclasses import asdict
from typing import Any

from sqlalchemy import delete

from app.core.db import get_session_factory
from app.modules.preferences.models import (
    PreferenceCompany,
    PreferenceKeyword,
    PreferenceLocation,
    Preferences,
    PreferenceSector,
    PreferenceTitle,
)
from app.modules.preferences.repository import SqlAlchemyPreferencesRepository


async def purge_user(user_id: uuid.UUID) -> None:
    """Supprime physiquement la ligne preferences et toutes les tables enfants."""
    factory = get_session_factory()
    async with factory() as session:
        for child in (
            PreferenceLocation,
            PreferenceTitle,
            PreferenceSector,
            PreferenceCompany,
            PreferenceKeyword,
        ):
            await session.execute(delete(child).where(child.user_id == user_id))
        await session.execute(delete(Preferences).where(Preferences.user_id == user_id))
        await session.commit()


async def export_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Export RGPD (art. 20) des données du module preferences."""
    factory = get_session_factory()
    async with factory() as session:
        repository = SqlAlchemyPreferencesRepository(session)
        data = await repository.get(user_id)
        if data is None:
            return {}
        return {"preferences": asdict(data)}

"""Purge / export RGPD du module profiles (D21).

Chaque module expose ``purge_user`` / ``export_user`` ; le module ``privacy``
orchestre, journalise et vérifie l'exhaustivité (registre déclaratif — M5).
La suppression du profil cascade sur les sous-ressources (expériences,
formations, compétences, langues) via ``cascade='all, delete-orphan'``.
"""

import uuid
from typing import Any

from app.core.db import get_session_factory
from app.modules.profiles.repository import SqlAlchemyProfilesRepository
from app.modules.profiles.service import to_profile_out


async def purge_user(user_id: uuid.UUID) -> None:
    """Supprime physiquement le profil et toutes ses sous-ressources."""
    factory = get_session_factory()
    async with factory() as session:
        repository = SqlAlchemyProfilesRepository(session)
        profile = await repository.get_by_user(user_id)
        if profile is not None:
            await session.delete(profile)
            await session.commit()


async def export_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Export RGPD (art. 20) des données du module profiles."""
    factory = get_session_factory()
    async with factory() as session:
        repository = SqlAlchemyProfilesRepository(session)
        profile = await repository.get_by_user(user_id)
        if profile is None:
            return {}
        return {"profile": to_profile_out(profile).model_dump(mode="json")}

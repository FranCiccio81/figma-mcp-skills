"""Purge / export RGPD du module auth (D21).

Chaque module expose ``purge_user`` / ``export_user`` ; le module ``privacy``
orchestre, journalise et vérifie l'exhaustivité (registre déclaratif — M5).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.redis import get_redis_persistent
from app.core.security import SessionStore
from app.modules.auth.models import Consent, User


async def purge_user(user_id: uuid.UUID) -> None:
    """Anonymise la ligne ``users`` et révoque toutes les sessions.

    Les consentements sont conservés (preuve légale) : ils ne référencent
    plus que l'identifiant technique d'un utilisateur anonymisé.
    """
    factory = get_session_factory()
    async with factory() as session:
        user = await session.get(User, user_id)
        if user is not None:
            user.email = f"purged+{user_id}@purged.invalid"
            user.password_hash = None
            user.deleted_at = datetime.now(UTC)
            await session.commit()

    sessions = SessionStore(get_redis_persistent(), get_settings().session_ttl_seconds)
    await sessions.delete_all_for_user(user_id)


async def export_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Export RGPD (art. 20) des données du module auth."""
    factory = get_session_factory()
    async with factory() as session:
        user = await session.get(User, user_id)
        if user is None:
            return {}
        consents = (
            (await session.execute(select(Consent).where(Consent.user_id == user_id)))
            .scalars()
            .all()
        )
        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "locale": user.locale,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "consents": [
                {
                    "kind": c.kind,
                    "version": c.version,
                    "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                    "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
                }
                for c in consents
            ],
        }

"""Purge / export RGPD du module explanations (D21).

Chaque module expose ``purge_user`` / ``export_user`` ; le module ``privacy``
orchestre, journalise et vérifie l'exhaustivité (registre déclaratif — M5).

``repository`` est injectable (tests unitaires : fake en mémoire) ; par
défaut, une session SQLAlchemy est ouverte via la fabrique globale.
"""

import uuid
from typing import Any

from app.core.db import get_session_factory
from app.modules.explanations.repository import (
    ExplanationsRepository,
    SqlAlchemyExplanationsRepository,
)


async def purge_user(
    user_id: uuid.UUID, repository: ExplanationsRepository | None = None
) -> None:
    """Supprime physiquement toutes les explications de l'utilisateur."""
    if repository is not None:
        await repository.delete_for_user(user_id)
        return
    factory = get_session_factory()
    async with factory() as session:
        await SqlAlchemyExplanationsRepository(session).delete_for_user(user_id)


async def export_user(
    user_id: uuid.UUID, repository: ExplanationsRepository | None = None
) -> dict[str, Any]:
    """Export RGPD (art. 20) des explications générées pour l'utilisateur."""
    if repository is not None:
        rows = await repository.list_for_user(user_id)
    else:
        factory = get_session_factory()
        async with factory() as session:
            rows = await SqlAlchemyExplanationsRepository(session).list_for_user(user_id)
    if not rows:
        return {}
    return {
        "match_explanations": [
            {
                "job_posting_id": str(row.job_posting_id),
                "scoring_version": row.scoring_version,
                "prompt_version": row.prompt_version,
                "content": row.content,
                "created_at": (
                    row.created_at.isoformat() if row.created_at is not None else None
                ),
            }
            for row in rows
        ]
    }

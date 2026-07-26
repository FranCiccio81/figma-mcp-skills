"""Purge / export RGPD du module matching (D21).

Chaque module expose ``purge_user`` / ``export_user`` ; le module ``privacy``
orchestre, journalise et vérifie l'exhaustivité (registre déclaratif — M5).
La suppression des ``match_results`` cascade sur ``match_explanations``
(FK composite ON DELETE CASCADE — et suppression explicite côté repository).

``repository`` est injectable (tests unitaires : fake en mémoire) ; par
défaut, une session SQLAlchemy est ouverte via la fabrique globale.
"""

import uuid
from typing import Any

from app.core.db import get_session_factory
from app.modules.matching.repository import (
    MatchingRepository,
    SqlAlchemyMatchingRepository,
)


async def purge_user(
    user_id: uuid.UUID, repository: MatchingRepository | None = None
) -> None:
    """Supprime physiquement tous les résultats de matching de l'utilisateur."""
    if repository is not None:
        await repository.delete_for_user(user_id)
        return
    factory = get_session_factory()
    async with factory() as session:
        await SqlAlchemyMatchingRepository(session).delete_for_user(user_id)


async def export_user(
    user_id: uuid.UUID, repository: MatchingRepository | None = None
) -> dict[str, Any]:
    """Export RGPD (art. 20) des résultats de matching de l'utilisateur."""
    if repository is not None:
        rows = await repository.list_results_for_user(user_id)
    else:
        factory = get_session_factory()
        async with factory() as session:
            rows = await SqlAlchemyMatchingRepository(session).list_results_for_user(user_id)
    if not rows:
        return {}
    return {
        "match_results": [
            {
                "job_posting_id": str(row.job_posting_id),
                "scoring_version": row.scoring_version,
                "score": row.score,
                "confidence": row.confidence,
                "low_data": row.low_data,
                "blocking_criteria": row.blocking_criteria,
                "unknown_dimensions": row.unknown_dimensions,
                "dimension_scores": row.dimension_scores,
                "computed_at": (
                    row.computed_at.isoformat() if row.computed_at is not None else None
                ),
            }
            for row in rows
        ]
    }

"""Purge / export RGPD du journal ``ai_calls`` (D21, RM-Q-2).

**La purge est une ANONYMISATION, pas une suppression** (11 §2) :
``user_id → NULL``. Deux raisons :

1. la ligne ne contient aucune donnée personnelle en dehors de ce lien
   (ni prompt, ni réponse — 11 §3) : une fois détachée, elle n'est plus
   rattachable à une personne ;
2. les métadonnées agrégées (coût par tâche, latence, taux d'échec) restent
   nécessaires à l'exploitation et au suivi budgétaire (08 §7.3, R7).

Même traitement que ``audit_log`` (anonymisé à la purge, jamais supprimé).
La rétention propre de la table reste 13 mois (11 §3) — voir
:mod:`app.ai.calls`.

``repository`` est injectable (tests unitaires : fake en mémoire) ; par
défaut une session SQLAlchemy est ouverte via la fabrique globale.
"""

import logging
import uuid
from typing import Any

from app.core.db import get_session_factory
from app.modules.ai_calls.repository import AiCallsRepository, SqlAlchemyAiCallsRepository

logger = logging.getLogger(__name__)


async def purge_user(user_id: uuid.UUID, repository: AiCallsRepository | None = None) -> None:
    """Anonymise les appels IA de l'utilisateur (``user_id → NULL``)."""
    if repository is not None:
        anonymized = await repository.anonymize_user(user_id)
    else:
        factory = get_session_factory()
        async with factory() as session:
            anonymized = await SqlAlchemyAiCallsRepository(session).anonymize_user(user_id)
    logger.info("ai_calls_anonymized rows=%d", anonymized)


async def export_user(
    user_id: uuid.UUID, repository: AiCallsRepository | None = None
) -> dict[str, Any]:
    """Export RGPD (art. 15) des métadonnées d'appels IA de l'utilisateur.

    Aucun contenu n'est exporté : il n'en existe pas dans la table.
    """
    if repository is not None:
        rows = await repository.list_for_user(user_id)
    else:
        factory = get_session_factory()
        async with factory() as session:
            rows = await SqlAlchemyAiCallsRepository(session).list_for_user(user_id)
    if not rows:
        return {}
    return {
        "ai_calls": [
            {
                "task": row.task,
                "prompt_version": row.prompt_version,
                "model": row.model,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "latency_ms": row.latency_ms,
                "status": row.status,
                "error_code": row.error_code,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }

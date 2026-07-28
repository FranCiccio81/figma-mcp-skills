"""Tâches Celery des générations de contenus (file ``ai``, D12/D16) — jalon M4.

``ai.generate(document_id)`` : exécute la génération d'un document
(:func:`app.modules.generation.service.execute_generation`) — prompt ancré
sur le profil validé minimisé (D09), sortie validée Pydantic contre
``ai-output-schemas.json`` (retry D08), contrôle d'ancrage post-génération,
statuts ``processing`` → ``draft``/``failed``.

Boucle d'événements : la tâche exécute UNE seule coroutine via
``asyncio.run`` sur un moteur dédié ``NullPool``
(:func:`app.core.db.create_worker_engine`), disposé en fin de coroutine —
jamais le moteur global poolé (voir ``ingestion_tasks``). ``acks_late``
(D16) : en cas de re-livraison, ``execute_generation`` est idempotente (un
document déjà ``ready``/``failed`` est ignoré).

Provider : :class:`FakeProvider` déterministe avec les sorties canned
``FAKE_GENERATION_OUTPUTS`` 🟡 (D08, D22) — providers réels (Anthropic +
fallback, circuit breaker D18) branchés en M5.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable
from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai.providers.base import LLMProvider
from app.ai.providers.factory import get_llm_provider
from app.ai.providers.fake import FakeProvider
from app.ai.tasks.generate import FAKE_GENERATION_OUTPUTS
from app.core.config import get_settings
from app.core.db import create_worker_engine
from app.core.ratelimit import FixedWindowRateLimiter
from app.core.redis import worker_redis_cache
from app.modules.generation.repository import SqlAlchemyGenerationRepository
from app.modules.generation.service import execute_generation
from app.modules.profiles.repository import SqlAlchemyProfilesRepository
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run[T](coro: Awaitable[T]) -> T:
    """Pont sync Celery → code async SQLAlchemy (UNE coroutine par tâche)."""
    return asyncio.run(coro)  # type: ignore[arg-type]


def get_generation_provider() -> LLMProvider:
    """Provider LLM du worker — sélectionné par configuration (D08).

    ``AI_PROVIDER=fake`` (défaut) rend le provider déterministe historique,
    sorties canned comprises ; toute autre valeur passe par la fabrique
    (primaire + fallback + circuit breaker). L'activation d'un provider réel
    reste conditionnée à Q4/Q38 — voir ``app/ai/providers/anthropic.py``.
    """
    if get_settings().ai_provider == "fake":
        return FakeProvider(canned=deepcopy(FAKE_GENERATION_OUTPUTS))
    return get_llm_provider("generate")


async def _generate_cycle(document_id: uuid.UUID) -> dict[str, Any]:
    """Cycle complet dans UNE coroutine, moteur NullPool disposé au retour."""
    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        # Client Redis dédié au cycle, comme le moteur : le singleton
        # ``get_redis_cache`` garde des connexions liées à la boucle qui les a
        # ouvertes, et chaque tâche a la sienne (``asyncio.run``). Le
        # remboursement de quota tombait donc une fois sur deux — silencieusement,
        # puisque ``_refund_quota`` est best-effort.
        async with worker_redis_cache() as cache, factory() as session:
            repository = SqlAlchemyGenerationRepository(session)
            profiles = SqlAlchemyProfilesRepository(session)
            # Limiteur passé pour rembourser le quota si la génération
            # échoue de notre fait (Q28) — le prélèvement a eu lieu au POST.
            limiter = FixedWindowRateLimiter(cache)
            return await execute_generation(
                document_id,
                repository,
                profiles,
                get_generation_provider(),
                limiter=limiter,
            )
    finally:
        await engine.dispose()


@celery_app.task(name="ai.generate", bind=True, max_retries=0)
def generate(self: Any, document_id: str) -> dict[str, Any]:
    """Génère le contenu du document ``document_id`` (F-L/M/N/O).

    Pas de retry Celery : les échecs LLM sont gérés par la chaîne D08
    (retry de validation puis échec PROPRE persisté sur le document —
    l'utilisateur voit ``failed`` + bouton réessayer, jamais une tâche
    zombie). ``max_retries=0`` évite de re-consommer du quota en arrière-plan.
    """
    report = _run(_generate_cycle(uuid.UUID(document_id)))
    logger.info("generation_task_done id=%s report=%s", document_id, report)
    return report

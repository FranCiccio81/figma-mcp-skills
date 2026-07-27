"""Tâches Celery du module privacy (file ``maintenance`` — F-Q, D21).

- ``maintenance.privacy_export(export_id)`` : assemble l'archive RGPD en
  agrégeant les ``export_user()`` du registre déclaratif ;
- ``maintenance.purge_due_accounts()`` : purge les comptes dont la demande de
  suppression est échue (``purge_after`` ≤ now) — à planifier QUOTIDIENNE.

Intégration coordinateur (ce fichier ne modifie PAS ``celery_app.py``) :

1. ajouter ``"app.workers.privacy_tasks"`` aux ``include`` de ``celery_app`` ;
2. ajouter l'entrée beat (purge quotidienne, D20 : alerte si en retard) ::

       "maintenance-purge-due-accounts": {
           "task": "maintenance.purge_due_accounts",
           "schedule": crontab(minute=15, hour=4),
       },

Boucle d'événements : chaque tâche exécute UNE coroutine via ``asyncio.run``
sur un moteur dédié ``NullPool`` (:func:`app.core.db.create_worker_engine`),
disposé en fin de coroutine (voir ``ingestion_tasks.py``). Les
``purge_user``/``export_user`` des modules du registre ouvrent leur session
via la fabrique globale : chaque coroutine est donc enveloppée par
:func:`app.core.db.override_engine` afin que TOUT le code exécuté dans la
tâche (registre compris) utilise le moteur ``NullPool`` de la tâche.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable
from dataclasses import asdict
from typing import Any

from app.core.db import create_worker_engine, override_engine
from app.modules.privacy.export_builder import build_export
from app.modules.privacy.purge_runner import purge_due_accounts as run_purge_due_accounts
from app.modules.privacy.registry import DEFAULT_REGISTRY
from app.modules.privacy.repository import SqlAlchemyPrivacyRepository
from app.modules.privacy.storage import get_object_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run[T](coro: Awaitable[T]) -> T:
    """Pont sync Celery → code async SQLAlchemy (UNE coroutine par tâche)."""
    return asyncio.run(coro)  # type: ignore[arg-type]


async def _build_export(export_id: uuid.UUID) -> dict[str, Any]:
    engine = create_worker_engine()
    try:
        with override_engine(engine) as factory:
            async with factory() as session:
                result = await build_export(
                    export_id,
                    repository=SqlAlchemyPrivacyRepository(session),
                    storage=get_object_storage(),
                    registry=DEFAULT_REGISTRY,
                )
        return asdict(result)
    finally:
        await engine.dispose()


async def _purge_due_accounts() -> list[dict[str, Any]]:
    engine = create_worker_engine()
    try:
        with override_engine(engine) as factory:
            async with factory() as session:
                outcomes = await run_purge_due_accounts(
                    repository=SqlAlchemyPrivacyRepository(session),
                    storage=get_object_storage(),
                    registry=DEFAULT_REGISTRY,
                )
        return [
            {
                "deletion_id": str(outcome.deletion_id),
                "purged": outcome.purged,
                "failed_modules": list(outcome.failed_modules),
            }
            for outcome in outcomes
        ]
    finally:
        await engine.dispose()


@celery_app.task(name="maintenance.privacy_export")
def privacy_export(export_id: str) -> dict[str, Any]:
    """Constitue l'archive d'export RGPD (F-Q, AC-Q-3)."""
    return _run(_build_export(uuid.UUID(export_id)))


@celery_app.task(name="maintenance.purge_due_accounts")
def purge_due_accounts() -> list[dict[str, Any]]:
    """Purge les comptes échus (F-Q, AC-Q-2) — idempotente, échec partiel logué."""
    return _run(_purge_due_accounts())

"""Tâches Celery du module privacy (file ``maintenance`` — F-Q, D21).

- ``maintenance.privacy_export(export_id)`` : assemble l'archive RGPD en
  agrégeant les ``export_user()`` du registre déclaratif ;
- ``maintenance.purge_due_accounts()`` : purge les comptes dont la demande de
  suppression est échue (``purge_after`` ≤ now) — planifiée QUOTIDIENNE ;
- ``maintenance.purge_expired_exports()`` : ménage des archives d'export dont
  le lien signé a expiré (objet + ligne) — planifiée QUOTIDIENNE.

Les trois tâches sont enregistrées dans ``celery_app.py`` (``include`` +
``beat_schedule``) ; l'alerte « purges en retard » (D20) surveille les
demandes ``pending`` échues.

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
from app.core.storage import get_object_storage
from app.modules.privacy.export_builder import build_export
from app.modules.privacy.purge_runner import purge_due_accounts as run_purge_due_accounts
from app.modules.privacy.purge_runner import (
    purge_expired_exports as run_purge_expired_exports,
)
from app.modules.privacy.registry import DEFAULT_REGISTRY
from app.modules.privacy.repository import SqlAlchemyPrivacyRepository
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


async def _purge_expired_exports() -> dict[str, Any]:
    engine = create_worker_engine()
    try:
        with override_engine(engine) as factory:
            async with factory() as session:
                outcome = await run_purge_expired_exports(
                    repository=SqlAlchemyPrivacyRepository(session),
                    storage=get_object_storage(),
                )
        return {
            "deleted_objects": outcome.deleted_objects,
            "deleted_rows": outcome.deleted_rows,
            "failed_keys": list(outcome.failed_keys),
        }
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


@celery_app.task(name="maintenance.purge_expired_exports")
def purge_expired_exports() -> dict[str, Any]:
    """Supprime les archives d'export expirées (objet + ligne) — idempotente.

    Le lien signé expire à J+7 mais l'objet, lui, survivait indéfiniment
    (dump personnel complet conservé sans finalité — D09). Planifiée
    quotidiennement par beat (``celery_app.beat_schedule``).
    """
    return _run(_purge_expired_exports())

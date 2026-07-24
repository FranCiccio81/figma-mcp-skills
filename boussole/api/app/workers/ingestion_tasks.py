"""Tâches Celery de la file ``ingestion`` + expiration (07 §4.1, D16).

- ``ingestion.sync_source(slug)`` : cycle incrémental — fetch connecteur →
  archivage payload S3 (STUB logué 🟡) → ``ingest_batch`` →
  ``connector_state`` mis à jour (le curseur n'avance qu'après cycle
  complet réussi) ;
- ``ingestion.reconcile(slug)`` : réconciliation complète — même chaîne +
  détection d'expiration par disparition du flux (07 §4.6.2) ;
- ``maintenance.expire_jobs`` : mécanisme 1 (``expires_at`` dépassé).

Non implémenté au M2 (🟡, documenté) : verrou Redis anti-chevauchement
``ingestion:lock:{slug}``, circuit breaker ``ingestion:cb:{slug}``
(07 §4.2/§4.5) — à brancher en intégration M2 avec les métriques §7.3.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.modules.ingestion.connectors.base import Connector, RawJob
from app.modules.ingestion.connectors.france_travail import FranceTravailConnector
from app.modules.ingestion.connectors.greenhouse import GreenhouseConnector
from app.modules.ingestion.connectors.lever import LeverConnector
from app.modules.ingestion.models import ConnectorState
from app.modules.ingestion.service import (
    SqlAlchemyJobStore,
    ingest_batch,
    mark_expired,
)
from app.modules.ingestion.settings import get_ingestion_settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

def _run[T](coro: Awaitable[T]) -> T:
    """Pont sync Celery → code async SQLAlchemy."""
    return asyncio.run(coro)  # type: ignore[arg-type]


def _feature_enabled(slug: str) -> bool:
    settings = get_settings()
    return {
        "france-travail": settings.feature_source_france_travail,
        "greenhouse": settings.feature_source_greenhouse,
        "lever": settings.feature_source_lever,
    }.get(slug, False)


def _build_connector(slug: str) -> Connector:
    ingestion_settings = get_ingestion_settings()
    if slug == "france-travail":
        return FranceTravailConnector(
            client_id=ingestion_settings.france_travail_client_id,
            client_secret=ingestion_settings.france_travail_client_secret,
        )
    if slug == "greenhouse":
        return GreenhouseConnector(boards=ingestion_settings.greenhouse_board_list)
    if slug == "lever":
        return LeverConnector(sites=ingestion_settings.lever_site_list)
    raise ValueError(f"connecteur inconnu : {slug!r}")


def _store_raw_payloads_stub(slug: str, raw_jobs: list[RawJob]) -> None:
    """STUB S3 🟡 — archivage des payloads bruts (07 §4.4.1).

    Clé cible : ``raw/{source_slug}/{external_ref}/{ingested_at_iso}.json``
    (bucket versionné, SSE, rétention 12 mois post-expiration). Branché en
    intégration M2 sur le client S3/MinIO ; en attendant, trace loguée pour
    ne rien perdre silencieusement.
    """
    for raw in raw_jobs:
        logger.info(
            "s3_payload_store_stub 🟡 key=raw/%s/%s/%s.json",
            slug, raw.external_ref, datetime.now(UTC).isoformat(),
        )


async def _with_session[T](
    fn: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    factory = get_session_factory()
    async with factory() as session:
        result = await fn(session)
        await session.commit()
        return result


async def _sync(slug: str, raw_jobs: list[RawJob], new_cursor: str | None) -> dict[str, Any]:
    async def _do(session: AsyncSession) -> dict[str, Any]:
        store = SqlAlchemyJobStore(session)
        source = await store.get_source_by_slug(slug)
        if source is None:
            raise ValueError(f"source non enregistrée : {slug!r}")
        report = await ingest_batch(slug, raw_jobs, store)
        now = datetime.now(UTC)
        state = await session.get(ConnectorState, source.id)
        if state is None:
            state = ConnectorState(source_id=source.id)
            session.add(state)
        if new_cursor is not None:
            state.cursor = new_cursor
        state.last_sync_at = now
        state.updated_at = now
        return asdict(report)

    return await _with_session(_do)


async def _read_cursor(slug: str) -> str | None:
    async def _do(session: AsyncSession) -> str | None:
        store = SqlAlchemyJobStore(session)
        source = await store.get_source_by_slug(slug)
        if source is None:
            return None
        state = await session.get(ConnectorState, source.id)
        return state.cursor if state else None

    return await _with_session(_do)


@celery_app.task(
    name="ingestion.sync_source",
    bind=True,
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=30,  # backoff exponentiel 07 §4.5 (base 30 s)
    retry_backoff_max=1800,  # plafond 30 min
    retry_jitter=True,
)
def sync_source(self: Any, slug: str) -> dict[str, Any] | None:
    """Cycle d'ingestion incrémental d'une source (07 §4.1)."""
    if not _feature_enabled(slug):
        logger.info("ingestion_cycle_skipped slug=%s reason=feature_flag_off", slug)
        return None
    connector = _build_connector(slug)
    cursor = _run(_read_cursor(slug))
    raw_jobs, new_cursor = connector.fetch(cursor)
    _store_raw_payloads_stub(slug, raw_jobs)
    report = _run(_sync(slug, raw_jobs, new_cursor))
    logger.info("ingestion_cycle_success slug=%s report=%s", slug, report)
    return report


@celery_app.task(name="ingestion.reconcile", bind=True, max_retries=2)
def reconcile(self: Any, slug: str) -> dict[str, Any] | None:
    """Réconciliation complète : ré-ingestion + expiration par absence.

    La détection d'expiration (07 §4.6.2) ne s'applique qu'après un fetch
    complet RÉUSSI — toute exception du connecteur interrompt la tâche
    avant ``mark_expired``.
    """
    if not _feature_enabled(slug):
        logger.info("ingestion_cycle_skipped slug=%s reason=feature_flag_off", slug)
        return None
    connector = _build_connector(slug)
    raw_jobs, _ = connector.fetch(None)  # fetch complet (sans curseur)
    _store_raw_payloads_stub(slug, raw_jobs)

    async def _do(session: AsyncSession) -> dict[str, Any]:
        store = SqlAlchemyJobStore(session)
        source = await store.get_source_by_slug(slug)
        if source is None:
            raise ValueError(f"source non enregistrée : {slug!r}")
        ingest_report = await ingest_batch(slug, raw_jobs, store)
        expiration = await mark_expired(
            store,
            source_id=source.id,
            present_external_refs={raw.external_ref for raw in raw_jobs},
        )
        return {"ingest": asdict(ingest_report), "expiration": asdict(expiration)}

    report = _run(_with_session(_do))
    logger.info("ingestion_reconcile_success slug=%s report=%s", slug, report)
    return report


@celery_app.task(name="maintenance.expire_jobs")
def expire_jobs() -> dict[str, Any]:
    """Expiration par signal explicite : ``expires_at`` dépassé (07 §4.6.1)."""

    async def _do(session: AsyncSession) -> dict[str, Any]:
        store = SqlAlchemyJobStore(session)
        return asdict(await mark_expired(store))

    report = _run(_with_session(_do))
    logger.info("expire_jobs_done report=%s", report)
    return report

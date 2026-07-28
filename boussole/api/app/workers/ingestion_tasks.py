"""Tâches Celery de la file ``ingestion`` + expiration (07 §4.1, D16).

- ``ingestion.sync_source(slug)`` : cycle incrémental — fetch connecteur →
  archivage payload S3 (STUB logué 🟡) → ``ingest_batch`` →
  ``connector_state`` mis à jour (le curseur n'avance qu'après cycle
  complet réussi) ;
- ``ingestion.reconcile(slug)`` : réconciliation complète — même chaîne +
  détection d'expiration par disparition du flux (07 §4.6.2) ;
- ``maintenance.expire_jobs`` : mécanisme 1 (``expires_at`` dépassé).

Boucle d'événements : chaque tâche exécute UNE seule coroutine via
``asyncio.run`` (curseur lu DANS la coroutine) sur un moteur dédié
``NullPool`` (:func:`app.core.db.create_worker_engine`), disposé en fin de
coroutine — jamais le moteur global poolé, dont les connexions asyncpg
resteraient liées à une boucle fermée (RuntimeError au cycle suivant).

Non implémenté au M2 (🟡, documenté) : verrou Redis anti-chevauchement
``ingestion:lock:{slug}``, circuit breaker ``ingestion:cb:{slug}``
(07 §4.2/§4.5) — à brancher en intégration M2 avec les métriques §7.3.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.db import create_worker_engine
from app.modules.ingestion.connectors.base import Connector, RawJob
from app.modules.ingestion.connectors.demo_corpus import SLUG as DEMO_SLUG
from app.modules.ingestion.connectors.demo_corpus import build_demo_connector
from app.modules.ingestion.connectors.france_travail import FranceTravailConnector
from app.modules.ingestion.connectors.greenhouse import GreenhouseConnector
from app.modules.ingestion.connectors.lever import LeverConnector
from app.modules.ingestion.models import ConnectorState
from app.modules.ingestion.service import (
    JobStore,
    SqlAlchemyJobStore,
    ingest_batch,
    mark_expired,
)
from app.modules.ingestion.settings import get_ingestion_settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

def _run[T](coro: Awaitable[T]) -> T:
    """Pont sync Celery → code async SQLAlchemy (UNE coroutine par tâche)."""
    return asyncio.run(coro)  # type: ignore[arg-type]


def _feature_enabled(slug: str) -> bool:
    settings = get_settings()
    return {
        "france-travail": settings.feature_source_france_travail,
        "greenhouse": settings.feature_source_greenhouse,
        "lever": settings.feature_source_lever,
        DEMO_SLUG: settings.feature_source_demo,
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
    if slug == DEMO_SLUG:
        # Deuxième barrière, après le feature flag : le corpus est FICTIF et
        # ``build_demo_connector`` refuse de le construire hors développement.
        return build_demo_connector()
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


async def _refs_of_failed_scopes(
    store: JobStore, source_id: uuid.UUID, failed_scopes: list[str]
) -> set[str]:
    """External_refs des job_sources appartenant aux périmètres en échec.

    Un board Greenhouse / site Lever dont le fetch a échoué n'a PAS été
    observé : ses offres ne sont ni « présentes » ni « absentes » — elles
    sont exclues du périmètre ``mark_expired`` du cycle. Le rattachement se
    fait par le jeton du board/site dans ``original_url``
    (``…greenhouse.io/{board}/…``, ``…lever.co/{site}/…``).
    """
    if not failed_scopes:
        return set()
    markers = tuple(f"/{scope}/" for scope in failed_scopes)
    return {
        job_source.external_ref
        for job_source in await store.job_sources_for_source(source_id)
        if any(marker in job_source.original_url for marker in markers)
    }


async def _sync_cycle(slug: str, connector: Connector) -> dict[str, Any]:
    """Cycle incrémental complet dans UNE coroutine (curseur lu dedans)."""
    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            store = SqlAlchemyJobStore(session)
            source = await store.get_source_by_slug(slug)
            if source is None:
                raise ValueError(f"source non enregistrée : {slug!r}")
            state = await session.get(ConnectorState, source.id)
            cursor = state.cursor if state else None
            await session.commit()  # libère la connexion pendant le fetch HTTP

            fetched = await asyncio.to_thread(connector.fetch, cursor)
            _store_raw_payloads_stub(slug, fetched.jobs)

            report = await ingest_batch(slug, fetched.jobs, store)
            now = datetime.now(UTC)
            state = await session.get(ConnectorState, source.id)
            if state is None:
                state = ConnectorState(source_id=source.id)
                session.add(state)
            if fetched.cursor is not None and fetched.complete:
                # Le curseur n'avance qu'après un cycle COMPLET réussi
                # (07 §4.3) : fetch tronqué → curseur inchangé.
                state.cursor = fetched.cursor
            state.last_sync_at = now
            state.updated_at = now
            await session.commit()
            return asdict(report) | {
                "parse_errors": fetched.parse_errors,
                "complete": fetched.complete,
            }
    finally:
        await engine.dispose()


async def _reconcile_cycle(slug: str, connector: Connector) -> dict[str, Any]:
    """Réconciliation complète dans UNE coroutine : ré-ingestion + expiration.

    Garde-fous du mécanisme 2 (07 §4.6.2, §4.5) :

    - fetch TRONQUÉ (``complete=False``, ex. MAX_PAGES France Travail) →
      ``mark_expired`` n'est PAS appelé ce cycle (le périmètre observé
      n'est pas exhaustif : toute absence serait un faux signal) ;
    - board/site en ÉCHEC (``failed_scopes``) → ses job_sources sont
      exclues du périmètre (ni absence comptée, ni remise à zéro).
    """
    fetched = await asyncio.to_thread(connector.fetch, None)  # fetch complet
    _store_raw_payloads_stub(slug, fetched.jobs)

    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            store = SqlAlchemyJobStore(session)
            source = await store.get_source_by_slug(slug)
            if source is None:
                raise ValueError(f"source non enregistrée : {slug!r}")
            ingest_report = await ingest_batch(slug, fetched.jobs, store)

            expiration: dict[str, Any] | None = None
            if not fetched.complete:
                logger.warning(
                    "reconcile_expiration_skipped slug=%s reason=fetch_tronque", slug
                )
            else:
                skip_refs = await _refs_of_failed_scopes(
                    store, source.id, fetched.failed_scopes
                )
                expiration = asdict(await mark_expired(
                    store,
                    source_id=source.id,
                    present_external_refs={raw.external_ref for raw in fetched.jobs},
                    skip_external_refs=skip_refs,
                ))
            await session.commit()
            return {
                "ingest": asdict(ingest_report),
                "expiration": expiration,
                "parse_errors": fetched.parse_errors,
                "failed_scopes": fetched.failed_scopes,
            }
    finally:
        await engine.dispose()


async def _expire_cycle() -> dict[str, Any]:
    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            store = SqlAlchemyJobStore(session)
            report = asdict(await mark_expired(store))
            await session.commit()
            return report
    finally:
        await engine.dispose()


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
    report = _run(_sync_cycle(slug, connector))
    logger.info("ingestion_cycle_success slug=%s report=%s", slug, report)
    return report


@celery_app.task(name="ingestion.reconcile", bind=True, max_retries=2)
def reconcile(self: Any, slug: str) -> dict[str, Any] | None:
    """Réconciliation complète : ré-ingestion + expiration par absence.

    La détection d'expiration (07 §4.6.2) ne s'applique qu'après un fetch
    complet RÉUSSI — toute exception du connecteur interrompt la tâche
    avant ``mark_expired``, un fetch tronqué la saute, un board/site en
    échec est exclu du périmètre (voir :func:`_reconcile_cycle`).
    """
    if not _feature_enabled(slug):
        logger.info("ingestion_cycle_skipped slug=%s reason=feature_flag_off", slug)
        return None
    connector = _build_connector(slug)
    report = _run(_reconcile_cycle(slug, connector))
    logger.info("ingestion_reconcile_success slug=%s report=%s", slug, report)
    return report


@celery_app.task(name="maintenance.expire_jobs")
def expire_jobs() -> dict[str, Any]:
    """Expiration par signal explicite : ``expires_at`` dépassé (07 §4.6.1)."""
    report = _run(_expire_cycle())
    logger.info("expire_jobs_done report=%s", report)
    return report

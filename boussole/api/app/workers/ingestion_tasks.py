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

Verrou anti-chevauchement (07 §4.2) : ``sync_source`` **et** ``reconcile``
prennent le bail Redis ``ingestion:{slug}`` et RENONCENT s'il est déjà tenu.
Deux cycles concurrents sur la même source liraient le même curseur de
départ, referaient le même travail et pourraient faire reculer le curseur de
l'autre. Pour la réconciliation, l'enjeu est plus grave encore : elle appelle
``mark_expired``, dont le compteur d'absence n'est correct que si les
instantanés de fetch sont sérialisés — sans verrou, une offre vivante ingérée
par un cycle concurrent était **éteinte à tort**.

🟡 Circuit breaker par source (``ingestion:cb:{slug}``, 07 §4.5) toujours
non implémenté : les retries bornés de Celery (backoff exponentiel plafonné
à 30 min, 5 tentatives) couvrent le cas courant.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.db import create_worker_engine
from app.core.locks import LeaseLock, LockNotAcquiredError, hold
from app.core.redis import worker_redis_cache
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


#: Bail des cycles d'ingestion. Généreux devant la durée d'un cycle (dizaines
#: de secondes) : un bail trop court libérerait le verrou en cours de route et
#: laisserait un second cycle démarrer, ce que le verrou existe pour empêcher.
INGESTION_LOCK_TTL_SECONDS = 3600


async def _sous_verrou(slug: str, fabrique: Callable[[], Awaitable[Any]]) -> Any:
    """Exécute le cycle sous le verrou de la source, ou lève.

    ``fabrique`` et non ``coro`` : une coroutine passée en argument est créée
    AVANT l'appel, donc avant la prise du verrou. Quand le verrou n'est pas
    obtenu — le cas nominal que ce mécanisme existe pour traiter — elle n'est
    jamais consommée, et Python journalise un ``RuntimeWarning: coroutine was
    never awaited`` à chaque cycle renoncé. Elle retient de surcroît le
    connecteur, qui ouvre un client HTTP à sa construction.

    Le client Redis est dédié au cycle et refermé au retour : chaque tâche
    Celery a sa propre boucle d'événements (voir ``app/core/redis.py``).
    """
    async with worker_redis_cache() as cache:
        verrou = LeaseLock(cache)
        async with hold(verrou, f"ingestion:{slug}", ttl_seconds=INGESTION_LOCK_TTL_SECONDS):
            return await fabrique()


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
    """Cycle d'ingestion incrémental d'une source (07 §4.1).

    Sous verrou : un cycle déjà en cours sur la même source fait RENONCER
    celui-ci (retour ``None``), il ne le met pas en attente. Ces tâches sont
    planifiées et repasseront ; empiler les cycles accumulerait du retard
    sans jamais rattraper, et masquerait la vraie anomalie — un cycle qui
    dure plus longtemps que sa période.
    """
    if not _feature_enabled(slug):
        logger.info("ingestion_cycle_skipped slug=%s reason=feature_flag_off", slug)
        return None
    connector = _build_connector(slug)
    try:
        report = _run(_sous_verrou(slug, lambda: _sync_cycle(slug, connector)))
    except LockNotAcquiredError:
        logger.warning("ingestion_cycle_skipped slug=%s reason=deja_en_cours", slug)
        return None
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
    # MÊME verrou que ``sync_source``, et ce n'est pas une symétrie
    # cosmétique. ``_reconcile_cycle`` ingère PUIS appelle ``mark_expired`` :
    # le mécanisme d'expiration par absence (compteur, seuil 2) ne vaut que
    # si les instantanés de fetch sont sérialisés. Mesuré en revue avec un
    # `sync_source` concurrent : une offre VIVANTE, ingérée pendant le fetch
    # de la réconciliation, voyait son compteur d'absence atteindre 2 et
    # passait en `expired`.
    #
    # La fenêtre est réelle : le bail de sync vaut une heure, France Travail
    # synchronise à 02:00 et réconcilie à 03:00.
    try:
        report = _run(_sous_verrou(slug, lambda: _reconcile_cycle(slug, connector)))
    except LockNotAcquiredError:
        logger.warning("ingestion_reconcile_skipped slug=%s reason=deja_en_cours", slug)
        return None
    logger.info("ingestion_reconcile_success slug=%s report=%s", slug, report)
    return report


@celery_app.task(name="maintenance.expire_jobs")
def expire_jobs() -> dict[str, Any]:
    """Expiration par signal explicite : ``expires_at`` dépassé (07 §4.6.1)."""
    report = _run(_expire_cycle())
    logger.info("expire_jobs_done report=%s", report)
    return report

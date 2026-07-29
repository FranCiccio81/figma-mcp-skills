"""Tests des tâches workers d'ingestion (correctifs revue M2).

Correctif 1 : UNE seule coroutine (donc UNE seule boucle ``asyncio.run``)
par tâche, curseur lu DANS la coroutine, moteur ``NullPool`` dédié disposé
en fin de coroutine — plus jamais le moteur global poolé dont les
connexions asyncpg resteraient liées à une boucle fermée.

Correctif 5 : garde-fous du mécanisme d'expiration 2 (fetch tronqué →
pas de ``mark_expired`` ; board/site en échec → exclu du périmètre) et
compteurs d'absence persistés dans ``connector_state.absence_counters``.

Aucune base ni réseau : session/engine factices, store en mémoire.
"""

import asyncio
import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any

import fakeredis.aioredis
import pytest
from sqlalchemy.pool import NullPool

from app.core.db import create_worker_engine
from app.modules.ingestion.connectors.base import FetchResult
from app.modules.ingestion.models import ConnectorState
from app.modules.ingestion.service import (
    ExpirationReport,
    SqlAlchemyJobStore,
)
from app.modules.jobs.models import JobSource
from app.workers import ingestion_tasks
from tests.unit.ingestion.conftest import InMemoryJobStore

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


# ------------------------------------------------------------ doublures
class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeSession:
    """Session minimale : identité ConnectorState + commits comptés."""

    def __init__(self, state: ConnectorState | None = None) -> None:
        self.state = state
        self.added: list[object] = []
        self.commits = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get(self, model: type, key: object) -> ConnectorState | None:
        assert model is ConnectorState
        return self.state

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, ConnectorState):
            self.state = obj

    async def commit(self) -> None:
        self.commits += 1


class FakeConnector:
    slug = "france-travail"

    def __init__(self, result: FetchResult) -> None:
        self._result = result
        self.received_cursors: list[str | None] = []

    def fetch(self, state: str | None) -> FetchResult:
        self.received_cursors.append(state)
        return self._result


@pytest.fixture
def worker_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Câble la tâche sur des doublures et espionne ``_run`` (asyncio.run)."""
    env: dict[str, Any] = {
        "engine": FakeEngine(),
        "store": InMemoryJobStore(),
        "session": FakeSession(),
        "run_calls": 0,
    }

    def spy_run(coro: Awaitable[Any]) -> Any:
        env["run_calls"] += 1
        return asyncio.run(coro)  # type: ignore[arg-type]

    monkeypatch.setattr(ingestion_tasks, "_run", spy_run)
    monkeypatch.setattr(ingestion_tasks, "_feature_enabled", lambda _slug: True)
    monkeypatch.setattr(
        ingestion_tasks, "create_worker_engine", lambda: env["engine"]
    )
    monkeypatch.setattr(
        ingestion_tasks, "async_sessionmaker",
        lambda _engine, **_kw: lambda: env["session"],
    )
    monkeypatch.setattr(
        ingestion_tasks, "SqlAlchemyJobStore", lambda _session: env["store"]
    )
    # Redis substitué. Sans ça, le verrou d'ingestion ouvre une VRAIE connexion
    # sur le port du cache : ces tests ne passaient que sur une machine où un
    # Redis écoutait par hasard, et tombaient en CI. Exactement le défaut que
    # cette revue traque ailleurs — un test qui ne mesure pas ce qu'il croit
    # parce que l'environnement le sauve.
    monkeypatch.setattr(
        "app.core.redis.create_worker_redis_cache",
        lambda: fakeredis.aioredis.FakeRedis(decode_responses=True),
    )
    return env


# ------------------------------------------------------- correctif 1
class TestBoucleUnique:
    def test_create_worker_engine_nullpool(self) -> None:
        engine = create_worker_engine()
        try:
            assert isinstance(engine.sync_engine.pool, NullPool)
        finally:
            asyncio.run(engine.dispose())

    def test_sync_source_une_seule_coroutine_curseur_dedans(
        self, worker_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = worker_env["store"].add_source("france-travail")
        worker_env["session"].state = ConnectorState(
            source_id=source.id, cursor="2026-07-23T00:00:00+00:00"
        )
        connector = FakeConnector(
            FetchResult(jobs=[], cursor="2026-07-24T00:00:00+00:00", complete=True)
        )
        monkeypatch.setattr(ingestion_tasks, "_build_connector", lambda _slug: connector)

        report = ingestion_tasks.sync_source("france-travail")

        assert worker_env["run_calls"] == 1  # UNE coroutine = UNE boucle
        # Le curseur persisté a bien été lu DANS la même coroutine.
        assert connector.received_cursors == ["2026-07-23T00:00:00+00:00"]
        # Cycle complet réussi → le curseur avance.
        assert worker_env["session"].state.cursor == "2026-07-24T00:00:00+00:00"
        assert worker_env["engine"].disposed  # moteur NullPool disposé
        assert report is not None
        assert report["complete"] is True

    def test_sync_source_fetch_tronque_curseur_inchange(
        self, worker_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = worker_env["store"].add_source("france-travail")
        worker_env["session"].state = ConnectorState(
            source_id=source.id, cursor="OLD"
        )
        connector = FakeConnector(FetchResult(jobs=[], cursor="NEW", complete=False))
        monkeypatch.setattr(ingestion_tasks, "_build_connector", lambda _slug: connector)

        report = ingestion_tasks.sync_source("france-travail")

        assert worker_env["session"].state.cursor == "OLD"  # 07 §4.3
        assert report is not None
        assert report["complete"] is False

    def test_expire_jobs_une_coroutine_et_dispose(
        self, worker_env: dict[str, Any]
    ) -> None:
        ingestion_tasks.expire_jobs()
        assert worker_env["run_calls"] == 1
        assert worker_env["engine"].disposed


# ------------------------------------------------------- correctif 5
def _add_job_source(
    store: InMemoryJobStore, source_id: uuid.UUID, external_ref: str, url: str
) -> JobSource:
    job_source = JobSource(
        id=uuid.uuid4(), job_posting_id=uuid.uuid4(), source_id=source_id,
        external_ref=external_ref, original_url=url,
        posted_at=None, ingested_at=NOW,
    )
    store.job_sources[job_source.id] = job_source
    return job_source


class TestReconcileGardeFous:
    def test_fetch_tronque_saute_mark_expired(
        self, worker_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        worker_env["store"].add_source("france-travail")
        connector = FakeConnector(FetchResult(jobs=[], cursor="NEW", complete=False))
        monkeypatch.setattr(ingestion_tasks, "_build_connector", lambda _slug: connector)

        calls: list[dict[str, Any]] = []

        async def spy_mark_expired(_store: object, **kwargs: Any) -> ExpirationReport:
            calls.append(kwargs)
            return ExpirationReport()

        monkeypatch.setattr(ingestion_tasks, "mark_expired", spy_mark_expired)

        report = ingestion_tasks.reconcile("france-travail")

        assert calls == []  # correctif 5b : aucune expiration par absence
        assert report is not None
        assert report["expiration"] is None
        assert worker_env["engine"].disposed

    def test_board_en_echec_exclu_du_perimetre(
        self, worker_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = worker_env["store"]
        source = store.add_source("greenhouse", kind="ats_feed")
        _add_job_source(store, source.id, "gh-1",
                        "https://boards.greenhouse.io/acme/jobs/1")
        _add_job_source(store, source.id, "gh-2",
                        "https://boards.greenhouse.io/globex/jobs/2")

        connector = FakeConnector(
            FetchResult(jobs=[], complete=True, failed_scopes=["globex"])
        )
        monkeypatch.setattr(ingestion_tasks, "_build_connector", lambda _slug: connector)

        calls: list[dict[str, Any]] = []

        async def spy_mark_expired(_store: object, **kwargs: Any) -> ExpirationReport:
            calls.append(kwargs)
            return ExpirationReport()

        monkeypatch.setattr(ingestion_tasks, "mark_expired", spy_mark_expired)

        report = ingestion_tasks.reconcile("greenhouse")

        assert len(calls) == 1
        # Correctif 5a : les job_sources du board en échec sont hors périmètre.
        assert calls[0]["skip_external_refs"] == {"gh-2"}
        assert calls[0]["present_external_refs"] == set()
        assert report is not None
        assert report["failed_scopes"] == ["globex"]

    async def test_refs_of_failed_scopes_par_url(self) -> None:
        store = InMemoryJobStore()
        source = store.add_source("lever", kind="ats_feed")
        _add_job_source(store, source.id, "lv-1", "https://jobs.lever.co/globex/aaa")
        _add_job_source(store, source.id, "lv-2", "https://jobs.lever.co/initech/bbb")

        refs = await ingestion_tasks._refs_of_failed_scopes(
            store, source.id, ["initech"]
        )
        assert refs == {"lv-2"}
        assert await ingestion_tasks._refs_of_failed_scopes(store, source.id, []) == set()


# --------------------------------------------- correctif 5c (persistance)
class CounterSession:
    """Session factice pour les compteurs SqlAlchemyJobStore : résout
    ``JobSource.source_id`` via ``scalar`` et sert un ConnectorState réel."""

    def __init__(self, job_sources: dict[uuid.UUID, uuid.UUID]) -> None:
        self._job_sources = job_sources  # job_source_id → source_id
        self.states: dict[uuid.UUID, ConnectorState] = {}

    async def scalar(self, stmt: Any) -> uuid.UUID | None:
        job_source_id = stmt.whereclause.right.value
        return self._job_sources.get(job_source_id)

    async def get(self, model: type, key: uuid.UUID) -> ConnectorState | None:
        assert model is ConnectorState
        return self.states.get(key)

    def add(self, obj: object) -> None:
        assert isinstance(obj, ConnectorState)
        self.states[obj.source_id] = obj


class TestCompteursAbsencePersistes:
    async def test_note_clear_count_via_connector_state(self) -> None:
        source_id = uuid.uuid4()
        job_source_id = uuid.uuid4()
        session = CounterSession({job_source_id: source_id})
        store = SqlAlchemyJobStore(session)  # type: ignore[arg-type]

        assert await store.absence_count(job_source_id) == 0
        assert await store.note_source_absence(job_source_id) == 1
        assert await store.note_source_absence(job_source_id) == 2
        # Persisté dans la ligne connector_state (jsonb), pas en mémoire process.
        state = session.states[source_id]
        assert state.absence_counters == {str(job_source_id): 2}

        await store.clear_source_absence(job_source_id)
        assert await store.absence_count(job_source_id) == 0
        assert state.absence_counters == {}

    async def test_job_source_disparue_compteur_neutre(self) -> None:
        session = CounterSession({})
        store = SqlAlchemyJobStore(session)  # type: ignore[arg-type]
        ghost = uuid.uuid4()
        assert await store.note_source_absence(ghost) == 0
        assert await store.absence_count(ghost) == 0

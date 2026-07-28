"""Socle de la suite d'intégration — VRAI PostgreSQL (pgvector), VRAIES migrations.

POURQUOI CETTE SUITE EXISTE
---------------------------
La suite unitaire n'exerce JAMAIS de base de données : elle substitue des
repositories en mémoire ou se contente de compiler du SQL. Deux bugs
critiques lui ont donc échappé — les deux sont désormais couverts ici :

1. **Colonnes ``datetime`` sans fuseau** (``Mapped[datetime]`` mappé
   ``TIMESTAMP WITHOUT TIME ZONE``) : asyncpg refusait tout bind de datetime
   *aware*. Conséquence : 500 sur TOUTE pagination par date (``GET /jobs``
   page 2, curseur keyset) et sur ``posted_since``. Invisible en unitaire
   (aucun bind réel n'était envoyé à un serveur). Couvert par
   ``test_jobs_search_pagination.py``.

2. **Purge RGPD incomplète** : le ``purge_user`` du module ``jobs`` était un
   *stub* — les ``saved_jobs`` d'un compte supprimé survivaient à la purge.
   Les tests unitaires du registre vérifiaient l'ORCHESTRATION (chaque module
   est appelé), jamais l'EFFET (plus aucune ligne personnelle en base).
   Couvert par ``test_privacy_purge.py``, qui inventorie les tables réelles
   via ``information_schema`` et échoue dès qu'une table portant ``user_id``
   conserve des lignes.

COMMENT LA LANCER
-----------------
Ces tests sont marqués ``@pytest.mark.integration`` et EXCLUS par défaut
(``addopts = -m "not integration"`` dans ``pyproject.toml``) : ``pytest`` et
``make test`` restent rapides et sans Docker.

    make test-integration                        # depuis boussole/
    pytest tests/integration -m integration      # depuis boussole/api

Base de données, deux modes :

- **par défaut** : un conteneur PostgreSQL éphémère (image ``pgvector/pgvector:pg16``)
  démarré par ``testcontainers``. Docker absent ou injoignable → la suite est
  ``skip``ée avec un message explicite (jamais une erreur cryptique) ;
- **explicite** : ``BOUSSOLE_TEST_DATABASE_URL`` pointe une base JETABLE déjà
  disponible (service PostgreSQL de la CI, cluster local). Le contenu de cette
  base est TRONQUÉ entre chaque test — ne jamais y pointer une base utile.

Dans les deux cas le schéma vient des migrations Alembic RÉELLES
(``alembic upgrade head``), jamais d'un ``Base.metadata.create_all`` : le
trigger ``tsv``, les CHECK, les FK ``ON DELETE`` et les extensions
(``vector``, ``pg_trgm``, ``unaccent``, ``citext``) font partie de ce qui est
testé.

Périmètre assumé 🟡 : PostgreSQL est réel, Redis et le stockage objet ne le
sont pas (fakeredis + ``LocalDiskStorage`` sur un répertoire temporaire). Ces
deux dépendances ne portent aucune des régressions visées ici.
"""

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import fakeredis
import fakeredis.aioredis
import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.db import override_engine
from app.core.redis import get_redis_cache, get_redis_persistent
from app.core.storage import LocalDiskStorage
from app.main import create_app

#: Image du conteneur éphémère — pgvector est requis (colonnes ``vector(1024)``
#: et index HNSW de la migration 0001).
PGVECTOR_IMAGE = "pgvector/pgvector:pg16"

#: Base jetable fournie par l'appelant (CI, cluster local) — court-circuite
#: testcontainers. Voir la docstring du module.
DATABASE_URL_ENV = "BOUSSOLE_TEST_DATABASE_URL"

API_ROOT = Path(__file__).resolve().parents[2]

_SKIP_NO_DOCKER = (
    "Suite d'intégration ignorée : aucun PostgreSQL utilisable.\n"
    f"  • Docker indisponible pour démarrer l'image {PGVECTOR_IMAGE} ({{reason}}) ;\n"
    f"  • et {DATABASE_URL_ENV} n'est pas défini.\n"
    "Lancez Docker, ou pointez une base JETABLE :\n"
    f"  {DATABASE_URL_ENV}=postgresql+asyncpg://user:pass@localhost:5432/boussole_test"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Filet de sécurité : tout test de ce dossier porte le marqueur ``integration``.

    Les modules le déclarent déjà explicitement (``pytestmark``) ; ce hook
    garantit qu'un futur fichier qui l'oublierait ne se retrouve pas exécuté
    par le ``pytest`` par défaut (qui n'a ni Docker ni base).
    """
    for item in items:
        if Path(str(item.fspath)).parent == Path(__file__).parent:
            item.add_marker(pytest.mark.integration)


# ------------------------------------------------------------------ base


def _async_url(url: str) -> str:
    """Force le driver asyncpg (le reste de l'application ne connaît que lui)."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _start_container() -> Any:
    """Démarre le conteneur pgvector — ``skip`` explicite si Docker manque."""
    try:
        # testcontainers ≥ 4.13 a déplacé le module (l'ancien chemin émet un
        # DeprecationWarning) — on essaie le nouveau d'abord.
        try:
            from testcontainers.community.postgres import PostgresContainer
        except ImportError:
            from testcontainers.postgres import PostgresContainer
    except ImportError as exc:  # dépendance dev absente
        pytest.skip(_SKIP_NO_DOCKER.format(reason=f"testcontainers absent : {exc}"))
    try:
        container = PostgresContainer(PGVECTOR_IMAGE, driver="asyncpg")
        container.start()
    except Exception as exc:  # docker absent, socket injoignable, image non tirée…
        pytest.skip(_SKIP_NO_DOCKER.format(reason=f"{type(exc).__name__}: {exc}"))
    return container


def _run_migrations(url: str) -> None:
    """``alembic upgrade head`` — les VRAIES migrations, jamais ``create_all``."""
    config = Config(str(API_ROOT / "alembic" / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(config, "head")  # env.py lit DATABASE_URL via get_settings()


@pytest.fixture(scope="session")
def storage_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Racine du stockage objet local (archives d'export, fichiers CV)."""
    return tmp_path_factory.mktemp("boussole-storage")


@pytest.fixture(scope="session")
def database_url(storage_root: Path) -> Iterator[str]:
    """URL asyncpg d'une base MIGRÉE — conteneur éphémère ou base fournie.

    Pose aussi ``DATABASE_URL`` / ``STORAGE_LOCAL_PATH`` dans l'environnement
    et vide le cache de ``get_settings`` : tout le code applicatif (y compris
    ``get_session_factory()`` appelé par les modules de purge/export) vise la
    base de test.
    """
    explicit = os.environ.get(DATABASE_URL_ENV)
    container = None
    if explicit:
        url = _async_url(explicit)
    else:
        container = _start_container()
        url = _async_url(container.get_connection_url())

    previous = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "STORAGE_LOCAL_PATH": os.environ.get("STORAGE_LOCAL_PATH"),
    }
    os.environ["DATABASE_URL"] = url
    os.environ["STORAGE_LOCAL_PATH"] = str(storage_root)
    get_settings.cache_clear()
    try:
        _run_migrations(url)
        yield url
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        if container is not None:
            container.stop()


async def _public_tables(engine: AsyncEngine) -> tuple[str, ...]:
    """Tables réelles du schéma ``public`` (hors journal Alembic)."""
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "AND table_name <> 'alembic_version' ORDER BY table_name"
            )
        )
        return tuple(row[0] for row in rows)


@pytest.fixture
async def db_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """Moteur async ``NullPool`` + substitution du moteur GLOBAL de l'application.

    ``NullPool`` : une connexion par usage. Les tests, l'application ASGI et
    les modules de purge peuvent tourner dans des boucles d'événements
    différentes sans jamais réutiliser une connexion asyncpg liée à une boucle
    morte (même raison que ``create_worker_engine`` côté Celery).

    ``override_engine`` : les ``purge_user``/``export_user`` des modules
    ouvrent leurs sessions via la fabrique GLOBALE — sans substitution ils
    viseraient la base de développement.
    """
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        with override_engine(engine):
            yield engine
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_database(db_engine: AsyncEngine) -> None:
    """Isolation entre tests : TRUNCATE de toutes les tables AVANT chaque test.

    Avant (et non après) : l'état de la dernière exécution reste inspectable
    en cas d'échec, et un test n'hérite jamais des lignes d'un test précédent
    interrompu. ``RESTART IDENTITY CASCADE`` remet aussi les séquences
    (``audit_log``, ``application_events``) à zéro.
    """
    tables = await _public_tables(db_engine)
    if not tables:
        return
    joined = ", ".join(f'"{name}"' for name in tables)
    async with db_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session applicative sur la base de test (commits réels)."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def public_tables(db_engine: AsyncEngine) -> tuple[str, ...]:
    """Inventaire des tables réelles — lu depuis ``information_schema``."""
    return await _public_tables(db_engine)


# ------------------------------------------------------- dépendances hors DB


@pytest.fixture
def fake_redis_servers() -> tuple[fakeredis.FakeServer, fakeredis.FakeServer]:
    """Serveurs fakeredis (persistant, volatile) — Redis n'est pas le sujet 🟡."""
    return fakeredis.FakeServer(), fakeredis.FakeServer()


@pytest.fixture
def object_storage(storage_root: Path) -> LocalDiskStorage:
    """Stockage objet réel sur disque temporaire (contrat SYNCHRONE)."""
    return LocalDiskStorage(storage_root)


@pytest.fixture(autouse=True)
def _fake_session_store(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis_servers: tuple[fakeredis.FakeServer, fakeredis.FakeServer],
) -> None:
    """``auth.purge`` révoque les sessions Redis : fakeredis, pas de serveur réel 🟡.

    Sans cette substitution, ``purge_user`` du module auth échouerait sur une
    connexion Redis refusée et la purge serait rapportée PARTIELLE — un faux
    échec qui n'a rien à voir avec ce que la suite vérifie (l'état de la base).
    """
    persistent, _cache = fake_redis_servers

    @asynccontextmanager
    async def factory() -> AsyncIterator[Redis]:
        client = fakeredis.aioredis.FakeRedis(server=persistent, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()

    monkeypatch.setattr("app.modules.auth.purge.worker_redis_persistent", factory)


# ------------------------------------------------------------------- API


@pytest.fixture
def api_app(
    db_engine: AsyncEngine,
    fake_redis_servers: tuple[fakeredis.FakeServer, fakeredis.FakeServer],
) -> FastAPI:
    """Application FastAPI RÉELLE branchée sur la base de test.

    Aucune dépendance de base n'est substituée : ``get_db_session`` sert des
    sessions de la fabrique globale (elle-même substituée par ``db_engine``),
    donc les routes exécutent le VRAI SQL contre le VRAI schéma. Seuls les
    deux Redis sont factices (fakeredis) ; le stockage objet est le vrai
    ``LocalDiskStorage`` sur répertoire temporaire.
    """
    persistent, cache = fake_redis_servers

    def persistent_factory() -> Redis:
        return fakeredis.aioredis.FakeRedis(server=persistent, decode_responses=True)

    def cache_factory() -> Redis:
        return fakeredis.aioredis.FakeRedis(server=cache, decode_responses=True)

    app = create_app(
        redis_cache_factory=cache_factory,
        redis_persistent_factory=persistent_factory,
    )
    app.dependency_overrides[get_redis_persistent] = persistent_factory
    app.dependency_overrides[get_redis_cache] = cache_factory
    return app


@pytest.fixture
async def api_client(api_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Client HTTP asynchrone sur l'application (même boucle que le test).

    ``base_url`` en https : les cookies de session/CSRF sont ``Secure``.
    """
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
        yield client


DEFAULT_PASSWORD = "un mot de passe très long"


async def register_and_login(
    client: httpx.AsyncClient,
    *,
    email: str = "camille@example.eu",
    password: str = DEFAULT_PASSWORD,
) -> uuid.UUID:
    """Crée un compte RÉEL (INSERT ``users``) et ouvre une session — retourne l'id."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "locale": "fr",
            "accepted_terms_version": "2026-07",
            "accepted_privacy_version": "2026-07",
        },
    )
    assert response.status_code in (200, 201), response.text
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code in (200, 204), login.text
    me = await client.get("/api/v1/me")
    assert me.status_code == 200, me.text
    return uuid.UUID(me.json()["id"])


@pytest.fixture
async def authenticated_user(api_client: httpx.AsyncClient) -> uuid.UUID:
    """Compte créé et connecté via les vraies routes ``/auth`` (session ouverte)."""
    return await register_and_login(api_client)

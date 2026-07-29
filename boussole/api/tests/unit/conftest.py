"""Fixtures des tests unitaires.

Aucune dépendance externe : la base est remplacée par un repository en
mémoire, les deux Redis par fakeredis (serveurs partagés entre requêtes).
"""

import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime

import fakeredis
import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis

from app.core.redis import get_redis_cache, get_redis_persistent
from app.main import create_app
from app.modules.auth.models import User
from app.modules.auth.repository import get_auth_repository


class InMemoryAuthRepository:
    """Implémentation en mémoire du protocole AuthRepository."""

    def __init__(self) -> None:
        self.users_by_id: dict[uuid.UUID, User] = {}
        self.consents: list[tuple[uuid.UUID, str, str]] = []

    async def get_user_by_email(self, email: str) -> User | None:
        needle = email.lower()
        for user in self.users_by_id.values():
            if user.email.lower() == needle and user.deleted_at is None:
                return user
        return None

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        user = self.users_by_id.get(user_id)
        if user is None or user.deleted_at is not None:
            return None
        return user

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        locale: str,
        consents: Sequence[tuple[str, str]],
    ) -> User:
        now = datetime.now(UTC)
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            locale=locale,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.users_by_id[user.id] = user
        for kind, version in consents:
            self.consents.append((user.id, kind, version))
        return user


@pytest.fixture
def fake_persistent_server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
def fake_cache_server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
def fake_redis(fake_persistent_server: fakeredis.FakeServer) -> Redis:
    return fakeredis.aioredis.FakeRedis(server=fake_persistent_server, decode_responses=True)


@pytest.fixture
def auth_repository() -> InMemoryAuthRepository:
    return InMemoryAuthRepository()


@pytest.fixture
def client(
    auth_repository: InMemoryAuthRepository,
    fake_persistent_server: fakeredis.FakeServer,
    fake_cache_server: fakeredis.FakeServer,
) -> Iterator[TestClient]:
    def override_persistent() -> Redis:
        # Nouveau client par requête, état partagé via le serveur factice
        # (évite tout couplage de boucle asyncio avec TestClient).
        return fakeredis.aioredis.FakeRedis(
            server=fake_persistent_server, decode_responses=True
        )

    def override_cache() -> Redis:
        return fakeredis.aioredis.FakeRedis(server=fake_cache_server, decode_responses=True)

    # Les fabriques sont passées à create_app, pas seulement en dépendances :
    # le middleware de rate limiting lit ``app.state.redis_cache_factory`` et
    # NON les dépendances FastAPI. Sans elles, il parlait au vrai Redis.
    #
    # Deux conséquences, toutes deux constatées : la suite entière n'exerçait
    # que la branche DÉGRADÉE du limiteur (Redis injoignable → on laisse
    # passer), et elle échouait en masse — 209 tests en 429 — sur toute
    # machine où un Redis écoute sur le port par défaut, ce qui est le cas
    # courant d'un poste de développement.
    app = create_app(
        redis_cache_factory=override_cache,
        redis_persistent_factory=override_persistent,
    )

    def override_repository() -> InMemoryAuthRepository:
        return auth_repository

    app.dependency_overrides[get_auth_repository] = override_repository
    app.dependency_overrides[get_redis_persistent] = override_persistent
    app.dependency_overrides[get_redis_cache] = override_cache

    # base_url https : les cookies Secure doivent être renvoyés par le client.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client

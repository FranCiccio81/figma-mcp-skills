"""Deux clients Redis logiques (D17).

- persistant : sessions + broker Celery (AOF, noeviction) ;
- volatile  : cache + rate limiting (allkeys-lru).

Les fonctions ci-dessous servent aussi de dépendances FastAPI et sont
substituées par fakeredis dans les tests unitaires.

⚠️ **Deux régimes, deux accesseurs.** Les singletons ``get_redis_*`` sont
faits pour l'API : UNE boucle d'événements pour toute la vie du processus.
Un worker Celery exécute au contraire ``asyncio.run`` par tâche, donc une
boucle NEUVE à chaque fois — et les connexions gardées par le pool d'un
client ``redis.asyncio`` sont liées à la boucle qui les a ouvertes. Réutiliser
le singleton d'une tâche à l'autre lève ``RuntimeError: Event loop is closed``
(reproduit : tâche 1 OK, tâche 2 en erreur, tâche 3 OK…). Les tâches doivent
donc passer par :func:`worker_redis_cache` / :func:`worker_redis_persistent`,
qui ouvrent un client dédié au cycle et le referment — même parti pris que
``create_worker_engine`` pour SQLAlchemy.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from app.core.config import get_settings

_persistent: Redis | None = None
_cache: Redis | None = None


def get_redis_persistent() -> Redis:
    """Client Redis persistant (sessions). Jamais d'éviction LRU dessus.

    Réservé au processus API (boucle unique) — voir l'en-tête du module.
    """
    global _persistent
    if _persistent is None:
        _persistent = Redis.from_url(get_settings().redis_persistent_url, decode_responses=True)
    return _persistent


def get_redis_cache() -> Redis:
    """Client Redis volatile (cache, rate limiting).

    Réservé au processus API (boucle unique) — voir l'en-tête du module.
    """
    global _cache
    if _cache is None:
        _cache = Redis.from_url(get_settings().redis_cache_url, decode_responses=True)
    return _cache


def create_worker_redis_persistent() -> Redis:
    """Client persistant DÉDIÉ à un cycle de tâche — à refermer au retour."""
    return Redis.from_url(get_settings().redis_persistent_url, decode_responses=True)


def create_worker_redis_cache() -> Redis:
    """Client volatile DÉDIÉ à un cycle de tâche — à refermer au retour."""
    return Redis.from_url(get_settings().redis_cache_url, decode_responses=True)


@asynccontextmanager
async def worker_redis_persistent() -> AsyncIterator[Redis]:
    """Client persistant du cycle, fermé à la sortie (sessions de purge)."""
    client = create_worker_redis_persistent()
    try:
        yield client
    finally:
        await client.aclose()


@asynccontextmanager
async def worker_redis_cache() -> AsyncIterator[Redis]:
    """Client volatile du cycle, fermé à la sortie (quotas, cache)."""
    client = create_worker_redis_cache()
    try:
        yield client
    finally:
        await client.aclose()


async def check_redis(client: Redis) -> bool:
    """Sonde de readiness : PING."""
    try:
        await client.ping()
        return True
    except Exception:  # sonde volontairement large
        return False

"""Deux clients Redis logiques (D17).

- persistant : sessions + broker Celery (AOF, noeviction) ;
- volatile  : cache + rate limiting (allkeys-lru).

Les fonctions ci-dessous servent aussi de dépendances FastAPI et sont
substituées par fakeredis dans les tests unitaires.
"""

from redis.asyncio import Redis

from app.core.config import get_settings

_persistent: Redis | None = None
_cache: Redis | None = None


def get_redis_persistent() -> Redis:
    """Client Redis persistant (sessions). Jamais d'éviction LRU dessus."""
    global _persistent
    if _persistent is None:
        _persistent = Redis.from_url(get_settings().redis_persistent_url, decode_responses=True)
    return _persistent


def get_redis_cache() -> Redis:
    """Client Redis volatile (cache, rate limiting)."""
    global _cache
    if _cache is None:
        _cache = Redis.from_url(get_settings().redis_cache_url, decode_responses=True)
    return _cache


async def check_redis(client: Redis) -> bool:
    """Sonde de readiness : PING."""
    try:
        await client.ping()
        return True
    except Exception:  # sonde volontairement large
        return False

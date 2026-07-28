"""Rate limiting en fenêtre fixe sur le Redis volatile (D17).

Limites normatives : 12-api-contracts §1. En M1 seule la limite login
(5 tentatives/min 🟡) est branchée ; la classe est générique pour les
limites globales de M2+ (60 req/min, recherche 30/min, etc.).
"""

import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int  # secondes avant la prochaine fenêtre (0 si autorisé)


class FixedWindowRateLimiter:
    """Compteur INCR + EXPIRE par fenêtre fixe alignée sur l'horloge."""

    def __init__(self, redis: Redis, prefix: str = "rl") -> None:
        self._redis = redis
        self._prefix = prefix

    async def hit(
        self,
        scope: str,
        identifier: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        now = int(time.time())
        window_start = now - (now % window_seconds)
        key = f"{self._prefix}:{scope}:{identifier}:{window_start}"
        count = int(await self._redis.incr(key))
        if count == 1:
            # Filet de sécurité : la clé disparaît d'elle-même après la fenêtre.
            await self._redis.expire(key, window_seconds * 2)
        if count > limit:
            retry_after = max(1, window_start + window_seconds - now)
            return RateLimitResult(allowed=False, remaining=0, retry_after=retry_after)
        return RateLimitResult(allowed=True, remaining=limit - count, retry_after=0)

    async def refund(
        self,
        scope: str,
        identifier: str,
        *,
        window_seconds: int,
    ) -> bool:
        """Rend un jeton de la fenêtre COURANTE — quota prélevé à tort.

        Cas d'usage : un traitement asynchrone échoue de notre fait (panne
        provider, contrôle d'ancrage), et l'utilisateur ne doit pas être
        décompté pour un échec dont il n'est pas responsable.

        Limite assumée 🟡 : seule la fenêtre courante est remboursable. Si
        l'échec survient après une bascule de fenêtre, le jeton n'est pas
        rendu — le rembourser sur la nouvelle fenêtre offrirait un quota
        supplémentaire non consommé. Les traitements concernés durent des
        secondes, la bascule est donc marginale ; le remboursement retourne
        ``False`` dans ce cas, pour que l'appelant puisse le journaliser.

        Jamais en dessous de zéro : un remboursement sur une fenêtre déjà
        vide (clé expirée) est un no-op.
        """
        now = int(time.time())
        window_start = now - (now % window_seconds)
        key = f"{self._prefix}:{scope}:{identifier}:{window_start}"
        current = await self._redis.get(key)
        if current is None or int(current) <= 0:
            return False
        await self._redis.decr(key)
        return True

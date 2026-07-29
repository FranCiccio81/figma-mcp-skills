"""Verrou distribué à bail, pour les tâches qui ne doivent pas se chevaucher.

**Le cas qui l'impose.** Un cycle d'ingestion lit un curseur, récupère des
offres, écrit, puis avance le curseur. Deux cycles concurrents sur la même
source lisent le MÊME curseur de départ : ils refont le même travail, se
disputent les lignes, et le second peut faire reculer le curseur du premier.
Cela n'arrive pas tant qu'une source tourne toutes les deux heures et met dix
secondes — mais un fetch lent, une reprise après incident ou un déclenchement
manuel suffisent à faire chevaucher deux exécutions.

**Un bail, pas un verrou éternel.** ``SET NX EX`` : le verrou expire tout
seul. Un worker tué net ne laisse pas une source bloquée pour toujours, ce
qui serait la panne la plus pénible à diagnostiquer — tout a l'air normal, et
plus rien ne s'ingère.

**Un jeton, pas un booléen.** Chaque prise génère un identifiant aléatoire et
la libération ne supprime la clé QUE si le jeton correspond, par script Lua
atomique. Sans ça, un worker lent dont le bail a expiré libérerait le verrou
d'un autre worker en terminant — et deux cycles finiraient par tourner
ensemble, exactement ce qu'on voulait empêcher.
"""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from redis.exceptions import WatchError

logger = logging.getLogger(__name__)

class LockNotAcquiredError(RuntimeError):
    """Le verrou est tenu ailleurs — l'appelant doit renoncer, pas attendre."""


class LeaseLock:
    """Verrou à bail sur le Redis volatile."""

    def __init__(self, redis: Redis, *, prefix: str = "lock") -> None:
        self._redis = redis
        self._prefix = prefix

    async def acquire(self, name: str, *, ttl_seconds: int) -> str | None:
        """Prend le verrou et rend son jeton, ou ``None`` s'il est déjà tenu."""
        token = secrets.token_hex(16)
        pris = await self._redis.set(
            f"{self._prefix}:{name}", token, nx=True, ex=ttl_seconds
        )
        return token if pris else None

    async def release(self, name: str, token: str) -> bool:
        """Libère si et seulement si le jeton est encore le nôtre.

        Transaction optimiste ``WATCH``/``MULTI`` plutôt qu'un script Lua :
        même atomicité, aucune dépendance supplémentaire (fakeredis n'exécute
        ``EVAL`` qu'avec un interpréteur Lua installé, et faire dépendre la
        testabilité d'un tel paquet est un mauvais échange).

        La lecture-puis-suppression naïve, elle, ne conviendrait pas : entre
        les deux, le bail peut expirer et un autre worker prendre le verrou —
        on supprimerait le sien.
        """
        cle = f"{self._prefix}:{name}"
        async with self._redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(cle)
                    actuel = await pipe.get(cle)
                    if actuel is None:
                        await pipe.unwatch()
                        return False
                    texte = actuel.decode() if isinstance(actuel, bytes) else str(actuel)
                    if texte != token:
                        await pipe.unwatch()
                        return False
                    pipe.multi()
                    pipe.delete(cle)
                    resultat = await pipe.execute()
                    return bool(resultat and resultat[0])
                except WatchError:
                    # La clé a bougé pendant la transaction : on recommence, et
                    # le contrôle de jeton retranchera.
                    continue


@asynccontextmanager
async def hold(lock: LeaseLock, name: str, *, ttl_seconds: int) -> AsyncIterator[None]:
    """Tient le verrou le temps du bloc, ou lève :class:`LockNotAcquiredError`.

    Renoncer plutôt qu'attendre est délibéré : ces tâches sont planifiées et
    repasseront. Une file d'attente de cycles d'ingestion accumulerait du
    retard sans jamais rattraper, et masquerait la vraie anomalie (un cycle
    qui dure plus longtemps que sa période).
    """
    token = await lock.acquire(name, ttl_seconds=ttl_seconds)
    if token is None:
        raise LockNotAcquiredError(name)
    try:
        yield
    finally:
        # Le bail a pu expirer pendant le travail : dans ce cas la libération
        # ne fait rien, ce qui est correct — le verrou appartient déjà à un
        # autre. On le journalise, c'est le signe d'un TTL trop court.
        if not await lock.release(name, token):
            logger.warning("lock_deja_expire name=%s — TTL trop court ?", name)

"""Le code exécuté par Celery n'utilise pas les clients Redis singletons.

Contexte du défaut (revue de la finalisation). Un worker Celery exécute
``asyncio.run`` par tâche : une boucle d'événements NEUVE à chaque fois. Les
connexions gardées par le pool d'un client ``redis.asyncio`` sont liées à la
boucle qui les a ouvertes ; réutiliser le singleton d'une tâche à l'autre lève
``RuntimeError: Event loop is closed``. Reproduit contre un Redis réel avant
correction, avec le client singleton :

    tache 1: hit=True refund=True
    tache 2: RuntimeError: Event loop is closed
    tache 3: hit=True refund=True

Deux appelants étaient concernés, tous deux silencieux :

- ``generation_tasks`` — ``_refund_quota`` est best-effort et avale
  l'exception : le remboursement de quota ne marchait qu'une fois sur deux,
  l'utilisateur restait décompté d'un échec qui n'est pas le sien ;
- ``auth.purge`` — la révocation des sessions d'un compte purgé remontait en
  ``failed_modules`` : les sessions d'un compte supprimé lui survivaient.

Aucune suite ne pouvait le voir : les tests substituent fakeredis, qui ne
lie pas ses connexions à une boucle.
"""

import ast
import asyncio
from pathlib import Path

import pytest

from app.core.ratelimit import FixedWindowRateLimiter
from app.core.redis import worker_redis_cache

APP = Path(__file__).resolve().parents[3] / "app"

#: Accesseurs réservés au processus API (boucle unique et permanente).
SINGLETONS = {"get_redis_cache", "get_redis_persistent"}


def _modules_executes_par_celery() -> list[Path]:
    """Tâches Celery + fonctions de purge/export, appelées par les tâches."""
    return sorted(
        [p for p in (APP / "workers").glob("*.py") if p.name != "__init__.py"]
        + list(APP.glob("modules/*/purge.py"))
    )


class LoopBoundRedis:
    """Client fidèle au comportement observé de ``redis.asyncio``.

    Retient la boucle qui a ouvert la connexion et refuse de servir une autre
    boucle — c'est exactement ce qui casse entre deux ``asyncio.run``.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._store: dict[str, int] = {}
        self.closed = False

    def _bind(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError("Event loop is closed")

    async def incr(self, key: str) -> int:
        self._bind()
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def decr(self, key: str) -> int:
        self._bind()
        self._store[key] = self._store.get(key, 0) - 1
        return self._store[key]

    async def get(self, key: str) -> str | None:
        self._bind()
        value = self._store.get(key)
        return None if value is None else str(value)

    async def expire(self, key: str, seconds: int) -> bool:
        self._bind()
        return True

    async def aclose(self) -> None:
        self.closed = True


class TestLeSingletonCasseEntreDeuxTaches:
    """Le fake reproduit le défaut — sans lui, la correction ne prouve rien."""

    def test_un_client_partage_echoue_a_la_deuxieme_tache(self) -> None:
        partage = LoopBoundRedis()

        async def cycle() -> bool:
            limiter = FixedWindowRateLimiter(partage)
            return await limiter.refund("q", "u1", window_seconds=3600)

        asyncio.run(cycle())
        with pytest.raises(RuntimeError, match="Event loop is closed"):
            asyncio.run(cycle())


class TestClientDedieParCycle:
    def test_deux_taches_successives_aboutissent(self, monkeypatch) -> None:
        """Chaque cycle ouvre son client : la deuxième tâche passe aussi."""
        ouverts: list[LoopBoundRedis] = []

        def factory() -> LoopBoundRedis:
            client = LoopBoundRedis()
            ouverts.append(client)
            return client

        monkeypatch.setattr("app.core.redis.create_worker_redis_cache", factory)

        async def cycle() -> bool:
            async with worker_redis_cache() as cache:
                limiter = FixedWindowRateLimiter(cache)
                await limiter.hit("q", "u1", limit=10, window_seconds=3600)
                return await limiter.refund("q", "u1", window_seconds=3600)

        assert asyncio.run(cycle()) is True
        assert asyncio.run(cycle()) is True
        assert len(ouverts) == 2

    def test_le_client_est_referme_meme_sur_erreur(self, monkeypatch) -> None:
        """Un worker vit des jours : une connexion non fermée par tâche fuit."""
        client = LoopBoundRedis()
        monkeypatch.setattr("app.core.redis.create_worker_redis_cache", lambda: client)

        async def cycle() -> None:
            async with worker_redis_cache():
                raise ValueError("échec applicatif")

        with pytest.raises(ValueError):
            asyncio.run(cycle())
        assert client.closed is True


class TestAucunSingletonDansLeCodeDesWorkers:
    """Garde-fou structurel : le défaut revient par un simple import.

    Même parti pris que les tests de pureté du moteur de matching — un
    contrôle sur le texte du module, pas sur un comportement qu'aucun test
    ne peut observer avec fakeredis.
    """

    def test_le_perimetre_du_controle_nest_pas_vide(self) -> None:
        modules = _modules_executes_par_celery()
        assert len(modules) >= 5, [p.name for p in modules]

    @pytest.mark.parametrize(
        "module", _modules_executes_par_celery(), ids=lambda p: p.name
    )
    def test_pas_dappel_aux_accesseurs_singletons(self, module: Path) -> None:
        arbre = ast.parse(module.read_text(encoding="utf-8"))
        appels = {
            noeud.func.id
            for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Name)
            and noeud.func.id in SINGLETONS
        }
        assert not appels, (
            f"{module.name} appelle {sorted(appels)} : ce client garde des "
            "connexions liées à la boucle d'une AUTRE tâche. Utiliser "
            "worker_redis_cache() / worker_redis_persistent()."
        )

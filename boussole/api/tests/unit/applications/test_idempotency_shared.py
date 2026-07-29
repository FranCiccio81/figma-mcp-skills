"""L'idempotence doit survivre au redémarrage ET au multi-instance.

La première version tenait un dictionnaire en mémoire de processus. Derrière
deux répliques d'API — le déploiement normal — un double-clic tombait une
fois sur deux sur l'instance qui n'avait rien vu, et créait exactement le
doublon que la clé existait pour empêcher. Rien ne pouvait le montrer en
test : un seul processus voit toujours son propre dictionnaire.

D'où ces tests, qui font ce que la production fait : DEUX services distincts,
un magasin partagé.
"""

import uuid

import fakeredis.aioredis
import pytest

from app.core.idempotency import IdempotencyStore
from app.modules.applications.schemas import ApplicationInput
from app.modules.applications.service import ApplicationsService
from tests.unit.applications.conftest import InMemoryApplicationsRepository


@pytest.fixture
def magasin() -> IdempotencyStore:
    """Un serveur factice, plusieurs clients : la topologie de production."""
    serveur = fakeredis.FakeServer()
    return IdempotencyStore(
        fakeredis.aioredis.FakeRedis(server=serveur, decode_responses=True)
    )


def _saisie() -> ApplicationInput:
    return ApplicationInput(external_title="Développeuse", external_company="Fictis")


class TestPartageEntreInstances:
    async def test_deux_instances_ne_creent_pas_deux_candidatures(
        self, magasin: IdempotencyStore
    ) -> None:
        """LE test qui manquait. Deux services = deux répliques d'API."""
        depot = InMemoryApplicationsRepository()
        instance_a = ApplicationsService(depot, magasin)
        instance_b = ApplicationsService(depot, magasin)
        user = uuid.uuid4()

        premiere = await instance_a.create(user, _saisie(), idempotency_key="k-1")
        seconde = await instance_b.create(user, _saisie(), idempotency_key="k-1")

        assert premiere.id == seconde.id
        assert len(depot.applications) == 1

    async def test_deux_cles_distinctes_creent_bien_deux_candidatures(
        self, magasin: IdempotencyStore
    ) -> None:
        depot = InMemoryApplicationsRepository()
        service = ApplicationsService(depot, magasin)
        user = uuid.uuid4()

        await service.create(user, _saisie(), idempotency_key="k-1")
        await service.create(user, _saisie(), idempotency_key="k-2")

        assert len(depot.applications) == 2

    async def test_deux_utilisateurs_avec_la_meme_cle_ne_se_voient_pas(
        self, magasin: IdempotencyStore
    ) -> None:
        """La clé est choisie par le client : deux comptes peuvent tomber sur
        la même valeur, et l'un ne doit jamais récupérer la candidature de
        l'autre."""
        depot = InMemoryApplicationsRepository()
        service = ApplicationsService(depot, magasin)

        a = await service.create(uuid.uuid4(), _saisie(), idempotency_key="commune")
        b = await service.create(uuid.uuid4(), _saisie(), idempotency_key="commune")

        assert a.id != b.id
        assert len(depot.applications) == 2


class TestDegradations:
    async def test_sans_cle_aucune_idempotence(self, magasin: IdempotencyStore) -> None:
        depot = InMemoryApplicationsRepository()
        service = ApplicationsService(depot, magasin)
        user = uuid.uuid4()

        await service.create(user, _saisie())
        await service.create(user, _saisie())

        assert len(depot.applications) == 2

    async def test_sans_magasin_la_creation_fonctionne_quand_meme(self) -> None:
        """Une panne du cache ne doit jamais refuser un POST : on retombe sur
        le comportement d'avant l'idempotence, pas sur une erreur."""
        depot = InMemoryApplicationsRepository()
        service = ApplicationsService(depot, idempotency=None)

        resultat = await service.create(uuid.uuid4(), _saisie(), idempotency_key="k")

        assert resultat.id is not None
        assert len(depot.applications) == 1

    async def test_une_cle_pointant_vers_une_candidature_supprimee_recree(
        self, magasin: IdempotencyStore
    ) -> None:
        """Le cache survit à la ressource : il ne doit pas rendre un 404."""
        depot = InMemoryApplicationsRepository()
        service = ApplicationsService(depot, magasin)
        user = uuid.uuid4()

        premiere = await service.create(user, _saisie(), idempotency_key="k-1")
        depot.applications.clear()

        seconde = await service.create(user, _saisie(), idempotency_key="k-1")
        assert seconde.id != premiere.id

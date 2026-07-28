"""Enfilement de ``ai.embeddings.embed_profile`` à la validation du profil.

Régression visée : ``celery_app.send_task`` ouvre une connexion synchrone au
broker. Appelé tel quel depuis ``async def validate_profile``, un broker
injoignable gèle la boucle d'événements du worker ASGI — donc TOUTES les
requêtes en cours, pas seulement celle du validant — le temps du timeout TCP
(mesuré à 19,18 s). Le symptôme est invisible d'un test qui se contente de
vérifier que la tâche a été enfilée.
"""

import asyncio
import time
import uuid
from typing import Any

import pytest

from app.modules.profiles.service import ProfilesService, _default_embed_enqueuer
from tests.unit.profiles.conftest import InMemoryProfilesRepository, make_profile

#: Durée du « broker qui ne répond pas » — assez longue pour que la boucle
#: d'événements ait le temps de tourner des dizaines de fois si elle est libre.
LENTEUR_BROKER = 0.4
#: Période du battement témoin.
PERIODE_BATTEMENT = 0.01


class TestEnfilementNonBloquant:
    async def test_un_broker_lent_ne_gele_pas_la_boucle_d_evenements(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pendant l'enfilement, une autre tâche asyncio doit continuer à
        tourner. Enfilement synchrone → ``battements == 0``."""
        from app.workers.celery_app import celery_app

        def send_task_lent(*args: Any, **kwargs: Any) -> None:
            time.sleep(LENTEUR_BROKER)  # broker injoignable : timeout TCP

        monkeypatch.setattr(celery_app, "send_task", send_task_lent)

        battements = 0

        async def temoin() -> None:
            nonlocal battements
            while True:
                await asyncio.sleep(PERIODE_BATTEMENT)
                battements += 1

        tache = asyncio.create_task(temoin())
        await asyncio.sleep(0)  # laisse le témoin démarrer
        depart = time.perf_counter()
        await _default_embed_enqueuer(uuid.uuid4())
        duree = time.perf_counter() - depart
        tache.cancel()

        assert duree >= LENTEUR_BROKER, "l'enfilement n'a pas eu lieu"
        assert battements >= 10, (
            f"la boucle d'événements a été bloquée {duree:.2f} s "
            f"({battements} battements au lieu de ~{LENTEUR_BROKER / PERIODE_BATTEMENT:.0f})"
        )

    async def test_publication_bornee_et_sans_resultat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Broker injoignable : échouer tout de suite (0,1 s) plutôt que
        d'occuper un thread 19 s.

        ``retry=False`` seul ne suffit pas — il ne couvre que la
        republication. Les deux autres boucles sont ``backend.on_task_call``
        (abonnement au résultat : 13 s à lui seul, alors que PERSONNE ne lit
        le résultat de cette tâche) et la reconnexion de
        ``Connection.default_channel``.
        """
        from app.workers.celery_app import celery_app

        appels: list[dict[str, Any]] = []
        monkeypatch.setattr(
            celery_app, "send_task", lambda *a, **kw: appels.append(kw)
        )

        await _default_embed_enqueuer(uuid.uuid4())

        assert appels[0]["queue"] == "ai"
        assert appels[0]["retry"] is False
        assert appels[0]["ignore_result"] is True
        assert appels[0]["connection"].transport_options["max_retries"] == 0

    async def test_un_broker_en_panne_ne_fait_pas_echouer_la_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Best-effort : le beat quotidien rattrape (08 §8)."""
        from app.workers.celery_app import celery_app

        def send_task_casse(*args: Any, **kwargs: Any) -> None:
            raise ConnectionError("broker injoignable")

        monkeypatch.setattr(celery_app, "send_task", send_task_casse)

        await _default_embed_enqueuer(uuid.uuid4())  # ne doit rien lever


class TestEnfilementDepuisLaValidation:
    async def test_la_validation_attend_reellement_l_enfilement(self) -> None:
        """L'enfilement est une COROUTINE : sans ``await``, ``validate_profile``
        créerait un objet coroutine jamais exécuté et la tâche ne partirait
        jamais (échec silencieux — ``title_similarity`` restée inconnue)."""
        user_id = uuid.uuid4()
        repository = InMemoryProfilesRepository()
        profile = repository.add(
            make_profile(
                user_id,
                skills=[
                    ("Python", "cv_extraction", 0.7),
                    ("FastAPI", "cv_extraction", 0.7),
                    ("PostgreSQL", "cv_extraction", 0.7),
                ],
                educations=[("Master informatique", "cv_extraction")],
            )
        )
        enfiles: list[uuid.UUID] = []

        async def enqueuer(profile_id: uuid.UUID) -> None:
            await asyncio.sleep(0)  # un vrai point de suspension
            enfiles.append(profile_id)

        service = ProfilesService(repository, embed_enqueuer=enqueuer)
        result = await service.validate_profile(user_id)

        assert result.status == "validated"
        assert enfiles == [profile.id]

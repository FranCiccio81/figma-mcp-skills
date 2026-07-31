"""Trois affirmations que le produit faisait sans les avoir vérifiées.

Défauts trouvés en revue avant déploiement. Aucun ne fait planter quoi que
ce soit : chacun rend une réponse valide, plausible, et fausse.

1. **Le quota JOUR était consommé par des appels refusés à l'HEURE.**
   Les deux compteurs étaient incrémentés d'affilée, avant que le verdict
   horaire ne soit rendu. Mesuré, 40 tentatives dans l'heure sur des quotas
   10/h et 40/j ::

       10 explications servies, 39 jetons/jour consommés

   Quelqu'un qui atteint son plafond horaire et réessaie perd sa journée
   entière sans rien obtenir de plus.

2. **Un CV dont l'extraction a ÉCHOUÉ comptait comme importé.**
   ``EXISTS (SELECT 1 FROM cv_documents …)`` ignorait le statut. Le tableau
   de bord affichait alors, coche verte à l'appui : « CV importé — votre
   profil s'appuie sur ses informations extraites. » La personne dont
   l'import a échoué n'en était pas informée.

3. **``include_blocked=false`` était accepté et ignoré.**
   Documenté « sans effet au M2 : les critères bloquants proviennent du
   scoring (M3) ». Le M3 a livré le scoring ; le paramètre est resté
   décoratif. ``GET /jobs?include_blocked=false`` rendait exactement la même
   page que sans le paramètre.
"""

import asyncio
import uuid

import fakeredis.aioredis
import pytest

from app.core.problems import Problem
from app.core.ratelimit import FixedWindowRateLimiter
from app.modules.explanations.service import (
    QUOTA_PER_DAY,
    QUOTA_PER_HOUR,
    ExplanationsService,
)


class TestUnRefusNeConsommePasLeQuotaDuLendemain:
    @staticmethod
    async def _epuiser(cache, user_id: uuid.UUID, tentatives: int) -> tuple[int, int]:
        service = ExplanationsService.__new__(ExplanationsService)
        service._cache = cache  # type: ignore[attr-defined]
        servies = refusees = 0
        for _ in range(tentatives):
            try:
                await service._enforce_quotas(user_id)
                servies += 1
            except Problem:
                refusees += 1
        return servies, refusees

    @staticmethod
    async def _jetons_jour_consommes(cache, user_id: uuid.UUID) -> int:
        limiter = FixedWindowRateLimiter(cache)
        sonde = await limiter.hit(
            "explanations:day", str(user_id), limit=QUOTA_PER_DAY, window_seconds=86400
        )
        # La sonde consomme elle-même un jeton : on le retire.
        return QUOTA_PER_DAY - sonde.remaining - 1

    def test_le_quota_jour_ne_compte_que_les_explications_servies(self) -> None:
        """LE test qui aurait attrapé le défaut."""

        async def scenario() -> None:
            cache = fakeredis.aioredis.FakeRedis(decode_responses=True)
            user_id = uuid.uuid4()

            servies, refusees = await self._epuiser(cache, user_id, QUOTA_PER_DAY)
            consommes = await self._jetons_jour_consommes(cache, user_id)

            assert servies == QUOTA_PER_HOUR
            assert refusees > 0, "prémisse : le plafond horaire doit être atteint"
            assert consommes == servies, (
                f"{consommes} jetons/jour consommés pour {servies} explications "
                f"servies : {consommes - servies} brûlés par des appels refusés"
            )

        asyncio.run(scenario())

    def test_le_plafond_horaire_reste_applique(self) -> None:
        """La contrepartie : ne pas décompter le jour ne doit pas rendre le
        quota horaire inopérant."""

        async def scenario() -> None:
            cache = fakeredis.aioredis.FakeRedis(decode_responses=True)
            servies, _ = await self._epuiser(cache, uuid.uuid4(), QUOTA_PER_HOUR + 5)
            assert servies == QUOTA_PER_HOUR

        asyncio.run(scenario())

    def test_le_plafond_journalier_reste_applique(self) -> None:
        """Et l'autre contrepartie : le quota jour doit toujours mordre.

        Chaque utilisateur consomme son plafond horaire, sur des comptes
        distincts — le compteur du jour est par utilisateur, donc on épuise
        ici le compteur horaire d'un seul, plusieurs fois n'aurait pas de
        sens sans faire avancer le temps. On vérifie donc que le compteur du
        jour est bien atteint quand il est déjà proche de sa limite.
        """

        async def scenario() -> None:
            cache = fakeredis.aioredis.FakeRedis(decode_responses=True)
            user_id = uuid.uuid4()
            limiter = FixedWindowRateLimiter(cache)
            # On amène le compteur JOUR à sa limite sans toucher à l'horaire.
            for _ in range(QUOTA_PER_DAY):
                await limiter.hit(
                    "explanations:day",
                    str(user_id),
                    limit=QUOTA_PER_DAY,
                    window_seconds=86400,
                )

            service = ExplanationsService.__new__(ExplanationsService)
            service._cache = cache  # type: ignore[attr-defined]
            with pytest.raises(Problem) as capture:
                await service._enforce_quotas(user_id)
            assert capture.value.status == 429
            assert "jour" in (capture.value.detail or "")

        asyncio.run(scenario())

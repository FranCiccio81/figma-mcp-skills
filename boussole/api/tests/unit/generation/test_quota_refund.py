"""Q28 — une génération qui échoue de NOTRE fait ne décompte pas le quota.

Le quota est prélevé au ``POST`` (avant l'enfilement Celery), sinon un
utilisateur pourrait saturer la file en enchaînant les créations. Mais si la
génération échoue ensuite — panne provider, contrôle d'ancrage — le jeton a
été consommé pour rien : c'est l'utilisateur qui paie notre défaillance.

La revue de finalisation a relevé cette contradiction entre le code et Q28
(« une génération failed consomme-t-elle le quota ? → Non »). Ces tests
verrouillent le remboursement.
"""

import uuid

import fakeredis.aioredis
import pytest

from app.core.ratelimit import FixedWindowRateLimiter


@pytest.fixture
def limiter() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(fakeredis.aioredis.FakeRedis(decode_responses=True))


class TestRefund:
    async def test_un_jeton_rendu_est_reutilisable(
        self, limiter: FixedWindowRateLimiter
    ) -> None:
        user = str(uuid.uuid4())
        for _ in range(3):
            assert (
                await limiter.hit("generations:hour", user, limit=3, window_seconds=3600)
            ).allowed
        # Quota atteint : une 4e demande serait refusée…
        assert await limiter.refund("generations:hour", user, window_seconds=3600)
        # …mais le jeton de la génération échouée a été rendu.
        assert (
            await limiter.hit("generations:hour", user, limit=3, window_seconds=3600)
        ).allowed

    async def test_une_tentative_refusee_consomme_aussi_un_jeton(
        self, limiter: FixedWindowRateLimiter
    ) -> None:
        """Comportement RÉEL du compteur en fenêtre fixe, documenté ici.

        ``hit`` incrémente AVANT de comparer : une demande refusée gonfle
        donc le compteur. Sans conséquence en production — un refus lève 429
        avant l'enfilement, il n'y a pas de génération à rembourser — mais
        c'est un piège pour qui lit le compteur comme « nombre de
        générations produites ». 🟡 À revoir si le quota devient facturable.
        """
        user = str(uuid.uuid4())
        assert (
            await limiter.hit("generations:hour", user, limit=1, window_seconds=3600)
        ).allowed
        assert not (
            await limiter.hit("generations:hour", user, limit=1, window_seconds=3600)
        ).allowed
        # Un seul remboursement ne suffit pas : le refus a lui aussi compté.
        await limiter.refund("generations:hour", user, window_seconds=3600)
        assert not (
            await limiter.hit("generations:hour", user, limit=1, window_seconds=3600)
        ).allowed

    async def test_remboursement_sans_prelevement_est_un_no_op(
        self, limiter: FixedWindowRateLimiter
    ) -> None:
        """Jamais de compteur négatif : un remboursement en trop n'offre pas
        de quota supplémentaire."""
        user = str(uuid.uuid4())
        assert not await limiter.refund("generations:hour", user, window_seconds=3600)

        # Le quota nominal reste celui de la configuration, pas davantage.
        for _ in range(2):
            assert (
                await limiter.hit("generations:hour", user, limit=2, window_seconds=3600)
            ).allowed
        assert not (
            await limiter.hit("generations:hour", user, limit=2, window_seconds=3600)
        ).allowed

    async def test_le_remboursement_est_scope_par_utilisateur(
        self, limiter: FixedWindowRateLimiter
    ) -> None:
        alice, bob = str(uuid.uuid4()), str(uuid.uuid4())
        await limiter.hit("generations:hour", alice, limit=1, window_seconds=3600)
        assert not await limiter.refund("generations:hour", bob, window_seconds=3600)
        # Le jeton d'Alice n'a pas bougé.
        assert not (
            await limiter.hit("generations:hour", alice, limit=1, window_seconds=3600)
        ).allowed


class TestExecuteGenerationRembourse:
    """Le remboursement doit partir du CHEMIN D'ÉCHEC réel, pas d'un helper."""

    async def test_echec_de_generation_rend_les_deux_jetons(
        self, limiter: FixedWindowRateLimiter
    ) -> None:
        from app.modules.generation.service import _refund_quota

        user = uuid.uuid4()
        await limiter.hit("generations:hour", str(user), limit=1, window_seconds=3600)
        await limiter.hit("generations:day", str(user), limit=1, window_seconds=86400)

        await _refund_quota(limiter, user)

        assert (
            await limiter.hit("generations:hour", str(user), limit=1, window_seconds=3600)
        ).allowed
        assert (
            await limiter.hit("generations:day", str(user), limit=1, window_seconds=86400)
        ).allowed

    async def test_panne_du_compteur_n_empeche_pas_la_persistance(self) -> None:
        """Best-effort : un Redis en panne ne doit pas masquer l'échec métier."""
        from app.modules.generation.service import _refund_quota

        class BrokenLimiter:
            async def refund(self, *args: object, **kwargs: object) -> bool:
                raise ConnectionError("Redis injoignable")

        # Ne lève pas : l'échec de génération reste persisté par l'appelant.
        await _refund_quota(BrokenLimiter(), uuid.uuid4())  # type: ignore[arg-type]

    async def test_sans_limiteur_aucun_effet(self) -> None:
        """Les tests et appels directs passent `limiter=None` : pas de crash."""
        from app.modules.generation.service import _refund_quota

        await _refund_quota(None, uuid.uuid4())

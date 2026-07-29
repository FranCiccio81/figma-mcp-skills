"""Verrou à bail — les trois propriétés qui comptent.

Ce verrou protège les cycles d'ingestion. Deux cycles concurrents sur la même
source lisent le MÊME curseur de départ : ils refont le même travail, se
disputent les lignes, et le second peut faire reculer le curseur du premier.

Trois propriétés, chacune corrigeant une manière classique de rater ce genre
de verrou : il exclut vraiment, il expire tout seul, et il n'appartient qu'à
celui qui l'a pris.
"""

import fakeredis.aioredis
import pytest

from app.core.locks import LeaseLock, LockNotAcquiredError, hold


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


class TestExclusion:
    async def test_un_second_preneur_echoue(self, redis) -> None:
        verrou = LeaseLock(redis)
        assert await verrou.acquire("ingestion:demo", ttl_seconds=60) is not None
        assert await verrou.acquire("ingestion:demo", ttl_seconds=60) is None

    async def test_deux_sources_ne_se_bloquent_pas(self, redis) -> None:
        """Le verrou est PAR source : une source lente n'en gèle pas une autre."""
        verrou = LeaseLock(redis)
        assert await verrou.acquire("ingestion:a", ttl_seconds=60) is not None
        assert await verrou.acquire("ingestion:b", ttl_seconds=60) is not None

    async def test_apres_liberation_le_verrou_est_reprenable(self, redis) -> None:
        verrou = LeaseLock(redis)
        token = await verrou.acquire("ingestion:demo", ttl_seconds=60)
        assert token is not None
        assert await verrou.release("ingestion:demo", token) is True
        assert await verrou.acquire("ingestion:demo", ttl_seconds=60) is not None


class TestLeBailExpire:
    async def test_un_verrou_est_pose_avec_un_ttl(self, redis) -> None:
        """Sans expiration, un worker tué net gèlerait la source pour toujours
        — et c'est la panne la plus pénible à diagnostiquer : tout a l'air
        normal, mais plus rien ne s'ingère."""
        verrou = LeaseLock(redis)
        await verrou.acquire("ingestion:demo", ttl_seconds=42)
        assert 0 < await redis.ttl("lock:ingestion:demo") <= 42


class TestLeJetonProtegeLeProprietaire:
    async def test_un_jeton_etranger_ne_libere_rien(self, redis) -> None:
        """LE piège classique. Un worker dont le bail a expiré termine son
        travail et libère « son » verrou — qui appartient déjà à un autre.
        Résultat : deux cycles tournent ensemble, exactement ce qu'on voulait
        empêcher. La comparaison de jeton l'interdit.
        """
        verrou = LeaseLock(redis)
        legitime = await verrou.acquire("ingestion:demo", ttl_seconds=60)

        assert await verrou.release("ingestion:demo", "jeton-d-un-autre") is False
        # Le verrou est toujours tenu par son propriétaire.
        assert await verrou.acquire("ingestion:demo", ttl_seconds=60) is None
        assert legitime is not None
        assert await verrou.release("ingestion:demo", legitime) is True

    async def test_deux_prises_successives_ont_des_jetons_differents(
        self, redis
    ) -> None:
        verrou = LeaseLock(redis)
        premier = await verrou.acquire("x", ttl_seconds=60)
        assert premier is not None
        await verrou.release("x", premier)
        second = await verrou.acquire("x", ttl_seconds=60)
        assert second is not None and second != premier


class TestContexte:
    async def test_le_bloc_libere_meme_sur_erreur(self, redis) -> None:
        verrou = LeaseLock(redis)
        with pytest.raises(ValueError):
            async with hold(verrou, "ingestion:demo", ttl_seconds=60):
                raise ValueError("échec du cycle")
        assert await verrou.acquire("ingestion:demo", ttl_seconds=60) is not None

    async def test_le_bloc_renonce_au_lieu_dattendre(self, redis) -> None:
        """Renoncer est délibéré : ces tâches sont planifiées et repasseront.
        Empiler des cycles accumulerait du retard sans jamais rattraper, et
        masquerait la vraie anomalie — un cycle plus long que sa période."""
        verrou = LeaseLock(redis)
        await verrou.acquire("ingestion:demo", ttl_seconds=60)
        with pytest.raises(LockNotAcquiredError, match="ingestion:demo"):
            async with hold(verrou, "ingestion:demo", ttl_seconds=60):
                pytest.fail("le bloc n'aurait pas dû s'exécuter")

    async def test_un_bail_expire_pendant_le_travail_est_journalise(
        self, redis, caplog
    ) -> None:
        """Signe d'un TTL trop court : à voir dans les journaux, pas à deviner."""
        import logging

        verrou = LeaseLock(redis)
        with caplog.at_level(logging.WARNING, logger="app.core.locks"):
            async with hold(verrou, "ingestion:demo", ttl_seconds=60):
                await redis.delete("lock:ingestion:demo")  # simule l'expiration
        assert any("lock_deja_expire" in r.message for r in caplog.records)

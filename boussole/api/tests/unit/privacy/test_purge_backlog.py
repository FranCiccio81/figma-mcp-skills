"""Surveillance des purges RGPD en retard (D20).

Ce qui manquait : une purge qui échoue en boucle laisse la demande
``pending``, journalise ``account_purge_partial`` à chaque passage, et est
retentée indéfiniment. Aucun signal ne s'élevait au-dessus de la ligne de
log : un compte pouvait rester non purgé des semaines sans que l'engagement
des 30 jours apparaisse rompu nulle part.

La surveillance ne corrige rien — elle rend l'écart visible.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.privacy.purge_runner import BACKLOG_GRACE, check_purge_backlog
from app.modules.privacy.repository import DeletionRecord
from tests.unit.privacy.conftest import InMemoryPrivacyRepository

MAINTENANT = datetime(2026, 7, 28, 5, 15, tzinfo=UTC)


def _demande(
    repository: InMemoryPrivacyRepository,
    *,
    echeance: datetime,
    status: str = "pending",
) -> DeletionRecord:
    record = DeletionRecord(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        requested_at=echeance - timedelta(days=30),
        purge_after=echeance,
        status=status,
    )
    repository.deletion_requests[record.id] = record
    return record


@pytest.fixture
def repository() -> InMemoryPrivacyRepository:
    return InMemoryPrivacyRepository()


class TestRienASignaler:
    async def test_aucune_demande_du_tout(
        self, repository: InMemoryPrivacyRepository
    ) -> None:
        backlog = await check_purge_backlog(repository=repository, now=MAINTENANT)
        assert backlog.healthy
        assert backlog.overdue == 0

    async def test_une_demande_echue_depuis_moins_dun_cycle_nest_pas_en_retard(
        self, repository: InMemoryPrivacyRepository
    ) -> None:
        """La purge tourne une fois par jour : attendre son tour est normal.

        Sans cette marge, l'alerte se déclencherait tous les jours sur des
        demandes parfaitement saines — et une alerte qui crie toujours ne
        sert plus à rien.
        """
        _demande(repository, echeance=MAINTENANT - timedelta(hours=3))
        backlog = await check_purge_backlog(repository=repository, now=MAINTENANT)
        assert backlog.healthy

    async def test_une_demande_deja_purgee_est_ignoree(
        self, repository: InMemoryPrivacyRepository
    ) -> None:
        _demande(
            repository, echeance=MAINTENANT - timedelta(days=40), status="purged"
        )
        backlog = await check_purge_backlog(repository=repository, now=MAINTENANT)
        assert backlog.healthy

    async def test_une_demande_pas_encore_echue_est_ignoree(
        self, repository: InMemoryPrivacyRepository
    ) -> None:
        _demande(repository, echeance=MAINTENANT + timedelta(days=10))
        backlog = await check_purge_backlog(repository=repository, now=MAINTENANT)
        assert backlog.healthy


class TestRetardDetecte:
    async def test_une_demande_echue_au_dela_de_la_marge_est_signalee(
        self, repository: InMemoryPrivacyRepository
    ) -> None:
        record = _demande(repository, echeance=MAINTENANT - timedelta(hours=48))
        backlog = await check_purge_backlog(repository=repository, now=MAINTENANT)
        assert not backlog.healthy
        assert backlog.overdue == 1
        assert backlog.deletion_ids == (record.id,)

    async def test_lage_rapporte_est_celui_de_la_plus_ancienne(
        self, repository: InMemoryPrivacyRepository
    ) -> None:
        """C'est le chiffre qui dit si l'engagement est rompu, pas le compte."""
        _demande(repository, echeance=MAINTENANT - timedelta(hours=30))
        _demande(repository, echeance=MAINTENANT - timedelta(hours=200))
        backlog = await check_purge_backlog(repository=repository, now=MAINTENANT)
        assert backlog.overdue == 2
        assert backlog.oldest_age_hours == 200.0

    async def test_la_frontiere_de_la_marge(
        self, repository: InMemoryPrivacyRepository
    ) -> None:
        """Juste avant la marge : sain. Juste après : en retard."""
        _demande(repository, echeance=MAINTENANT - BACKLOG_GRACE + timedelta(minutes=1))
        assert (await check_purge_backlog(repository=repository, now=MAINTENANT)).healthy

        _demande(repository, echeance=MAINTENANT - BACKLOG_GRACE - timedelta(minutes=1))
        assert not (
            await check_purge_backlog(repository=repository, now=MAINTENANT)
        ).healthy


class TestJournalisation:
    """Les deux lignes sont le produit livré : rien d'autre ne sort d'ici."""

    async def test_le_retard_sort_en_ERROR(
        self, repository: InMemoryPrivacyRepository, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Le niveau EST l'alerte : c'est lui que la supervision filtre."""
        _demande(repository, echeance=MAINTENANT - timedelta(days=5))
        with caplog.at_level(logging.INFO, logger="boussole.privacy"):
            await check_purge_backlog(repository=repository, now=MAINTENANT)
        erreurs = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert [r.message for r in erreurs] == ["purge_backlog_detected"]

    async def test_le_cas_sain_journalise_un_battement_de_coeur(
        self, repository: InMemoryPrivacyRepository, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Sans cette ligne, un ordonnanceur mort est indétectable.

        La surveillance est elle-même une tâche beat : si beat s'arrête, ni
        la purge ni son contrôle ne tournent et le silence est total. Le
        battement permet à une supervision externe d'alerter sur l'ABSENCE
        du signal — le seul angle depuis lequel le cas se voit.
        """
        with caplog.at_level(logging.INFO, logger="boussole.privacy"):
            await check_purge_backlog(repository=repository, now=MAINTENANT)
        assert [r.message for r in caplog.records] == ["purge_backlog_ok"]

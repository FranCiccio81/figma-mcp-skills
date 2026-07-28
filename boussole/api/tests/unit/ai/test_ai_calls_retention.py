"""Rétention 13 mois du journal ``ai_calls`` (11 §3, D26).

Deux choses étaient vraies avant : la documentation annonçait 13 mois, et
rien ne les appliquait. Une durée de conservation qu'aucun code n'exécute est
un engagement rompu — silencieusement, puisque la table ne fait que grossir.

C'est aussi la table qui croît le plus vite (une ligne par appel IA, sur
quatre points d'appel), d'où la suppression par lots bornés plutôt qu'un
``DELETE`` global qui verrouillerait les écritures du journal — donc les
appels IA en cours.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.ai_calls.retention import (
    RETENTION_MONTHS,
    enforce_retention,
    months_before,
)

MAINTENANT = datetime(2026, 7, 28, 5, 30, tzinfo=UTC)


class FakeAiCallsRepository:
    """Fake en mémoire — on ne teste pas SQLAlchemy, on teste la boucle."""

    def __init__(self, dates: list[datetime]) -> None:
        self.dates = sorted(dates)
        self.appels: list[tuple[datetime, int]] = []

    async def delete_older_than(self, cutoff: datetime, *, batch: int) -> int:
        self.appels.append((cutoff, batch))
        doomed = [d for d in self.dates if d < cutoff][:batch]
        for date in doomed:
            self.dates.remove(date)
        return len(doomed)

    # Le protocole en porte deux autres, inutiles ici.
    async def anonymize_user(self, user_id: uuid.UUID) -> int:  # pragma: no cover
        return 0

    async def list_for_user(self, user_id: uuid.UUID) -> list[object]:  # pragma: no cover
        return []


class TestBorneCalendaire:
    """13 mois, pas 13 × 30 jours : l'écart est de six jours sur un engagement."""

    def test_treize_mois_en_arriere(self) -> None:
        assert months_before(MAINTENANT, 13) == datetime(
            2025, 6, 28, 5, 30, tzinfo=UTC
        )

    def test_lecart_avec_une_approximation_en_jours(self) -> None:
        """``timedelta(days=13 * 30)`` supprimerait CINQ JOURS TROP TÔT.

        390 jours, ce n'est pas 13 mois : la borne approchée tombe plus TARD
        dans le calendrier que la vraie, donc elle emporte des lignes qui
        n'ont pas encore atteint 13 mois. Se tromper dans ce sens-là détruit
        des données encore sous engagement de conservation — l'inverse d'une
        rétention trop longue, qui ne fait que coûter du disque.
        """
        approximation = MAINTENANT - timedelta(days=13 * 30)
        exacte = months_before(MAINTENANT, 13)
        assert (approximation - exacte).days == 5

    @pytest.mark.parametrize(
        ("depart", "attendu"),
        [
            # 31 mars − 1 mois : février n'a pas de 31.
            (datetime(2026, 3, 31, tzinfo=UTC), datetime(2026, 2, 28, tzinfo=UTC)),
            # Même chose une année bissextile.
            (datetime(2024, 3, 31, tzinfo=UTC), datetime(2024, 2, 29, tzinfo=UTC)),
            # 31 mai − 1 mois : avril n'a que 30 jours.
            (datetime(2026, 5, 31, tzinfo=UTC), datetime(2026, 4, 30, tzinfo=UTC)),
        ],
    )
    def test_le_quantieme_est_borne(self, depart: datetime, attendu: datetime) -> None:
        assert months_before(depart, 1) == attendu

    def test_le_passage_dannee(self) -> None:
        assert months_before(datetime(2026, 1, 15, tzinfo=UTC), 13) == datetime(
            2024, 12, 15, tzinfo=UTC
        )


class TestSuppression:
    async def test_seules_les_lignes_au_dela_de_la_retention_partent(self) -> None:
        borne = months_before(MAINTENANT, RETENTION_MONTHS)
        recente = borne + timedelta(days=1)
        ancienne = borne - timedelta(days=1)
        repository = FakeAiCallsRepository([recente, ancienne])

        outcome = await enforce_retention(repository=repository, now=MAINTENANT)

        assert outcome.deleted == 1
        assert repository.dates == [recente]
        assert outcome.cutoff == borne

    async def test_idempotente(self) -> None:
        borne = months_before(MAINTENANT, RETENTION_MONTHS)
        repository = FakeAiCallsRepository([borne - timedelta(days=5)])

        premier = await enforce_retention(repository=repository, now=MAINTENANT)
        second = await enforce_retention(repository=repository, now=MAINTENANT)

        assert premier.deleted == 1
        assert second.deleted == 0

    async def test_rien_a_supprimer_nest_pas_une_anomalie(self) -> None:
        repository = FakeAiCallsRepository([])
        outcome = await enforce_retention(repository=repository, now=MAINTENANT)
        assert outcome.deleted == 0
        assert not outcome.truncated


class TestBornesDExecution:
    async def test_la_suppression_se_fait_par_lots(self) -> None:
        """Un ``DELETE`` global verrouillerait la table le temps qu'il dure.

        Sur ``ai_calls``, ce verrou bloque l'écriture du journal, donc les
        appels IA en cours : le ménage prendrait le produit en otage.
        """
        borne = months_before(MAINTENANT, RETENTION_MONTHS)
        vieilles = [borne - timedelta(days=n + 1) for n in range(25)]
        repository = FakeAiCallsRepository(vieilles)

        outcome = await enforce_retention(
            repository=repository, now=MAINTENANT, batch=10
        )

        assert outcome.deleted == 25
        # 3 lots pleins ne suffisent pas à conclure : le 3e rend 5 < 10, donc
        # la boucle sait qu'elle a fini. D'où 3 appels, pas 4.
        assert [batch for _, batch in repository.appels] == [10, 10, 10]

    async def test_le_plafond_de_lots_borne_la_duree_et_le_dit(self) -> None:
        """Le premier passage peut avoir des mois de retard à rattraper.

        On préfère finir le lendemain plutôt que tenir la base des heures —
        mais l'exécution tronquée doit être VISIBLE, sinon on croit la
        rétention appliquée alors qu'elle est en cours de rattrapage.
        """
        borne = months_before(MAINTENANT, RETENTION_MONTHS)
        repository = FakeAiCallsRepository(
            [borne - timedelta(days=n + 1) for n in range(100)]
        )

        outcome = await enforce_retention(
            repository=repository, now=MAINTENANT, batch=10, max_batches=3
        )

        assert outcome.deleted == 30
        assert outcome.truncated is True
        assert len(repository.dates) == 70

    async def test_le_rattrapage_se_termine_aux_passages_suivants(self) -> None:
        borne = months_before(MAINTENANT, RETENTION_MONTHS)
        repository = FakeAiCallsRepository(
            [borne - timedelta(days=n + 1) for n in range(25)]
        )

        while True:
            outcome = await enforce_retention(
                repository=repository, now=MAINTENANT, batch=10, max_batches=1
            )
            if not outcome.truncated:
                break

        assert repository.dates == []

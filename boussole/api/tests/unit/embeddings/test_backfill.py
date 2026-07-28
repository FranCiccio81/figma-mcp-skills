"""Idempotence et économie des lots d'embeddings (08 §8, R7).

Le backfill est rejoué quotidiennement par le beat : il DOIT être un no-op
quand il n'y a rien de neuf, sous peine de refacturer tout le corpus à
chaque nuit (coût au token, R7) et de réécrire inutilement la base.
"""

import uuid
from collections.abc import Sequence

import pytest

from app.ai.embeddings.backfill import (
    BackfillReport,
    EmbeddingTarget,
    compute_embeddings,
    plan_embeddings,
)
from app.ai.embeddings.base import EmbeddingProviderUnavailableError
from app.ai.embeddings.hashing import HashingEmbeddingProvider

DIM = 32


class CountingProvider:
    """Provider local instrumenté : compte les appels ET les textes soumis."""

    def __init__(self, dimension: int = DIM) -> None:
        self.dimension = dimension
        self.model = "counting"
        self._inner = HashingEmbeddingProvider(dimension=dimension)
        self.batches: list[list[str]] = []

    @property
    def submitted(self) -> list[str]:
        return [text for batch in self.batches for text in batch]

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return self._inner.embed_texts(texts)


class BrokenProvider:
    def __init__(self) -> None:
        self.dimension = DIM
        self.model = "broken"

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        raise EmbeddingProviderUnavailableError("incident simulé")


def target(text: str, current: Sequence[float] | None = None) -> EmbeddingTarget:
    return EmbeddingTarget(key=uuid.uuid4(), text=text, current=current)


class TestIdempotence:
    def test_les_lignes_deja_embarquees_sont_ecartees(self) -> None:
        report = BackfillReport()
        planned = plan_embeddings(
            [target("Développeur", current=[0.1] * DIM), target("Comptable")], report
        )
        assert [item.text for item in planned] == ["Comptable"]
        assert report.skipped_present == 1
        assert report.seen == 2

    def test_force_recalcule_meme_ce_qui_existe(self) -> None:
        planned = plan_embeddings(
            [target("Développeur", current=[0.1] * DIM)], force=True
        )
        assert len(planned) == 1

    def test_rejouer_un_lot_complet_est_un_no_op(self) -> None:
        provider = CountingProvider()
        targets = [target("Développeur backend"), target("Data engineer")]
        vectors = compute_embeddings(provider, plan_embeddings(targets))
        assert len(vectors) == 2

        # Deuxième passage : les lignes portent désormais leur vecteur.
        embarques = [
            EmbeddingTarget(key=item.key, text=item.text, current=vectors[item.key])
            for item in targets
        ]
        provider.batches.clear()
        again = compute_embeddings(provider, plan_embeddings(embarques))
        assert again == {}
        assert provider.batches == []  # aucun appel provider : aucun coût

    def test_le_meme_texte_deux_fois_produit_le_meme_vecteur(self) -> None:
        provider = CountingProvider()
        first = compute_embeddings(provider, [target("Développeur backend")])
        second = compute_embeddings(provider, [target("Développeur backend")])
        assert next(iter(first.values())) == next(iter(second.values()))


class TestEconomieDesLots:
    def test_les_textes_identiques_ne_sont_soumis_qu_une_fois(self) -> None:
        provider = CountingProvider()
        targets = [target("Développeur backend") for _ in range(5)]
        vectors = compute_embeddings(provider, targets)
        assert len(vectors) == 5  # toutes les clés reçoivent leur vecteur
        assert provider.submitted == ["Développeur backend"]  # un seul texte soumis

    def test_les_lots_respectent_batch_size(self) -> None:
        provider = CountingProvider()
        targets = [target(f"Métier {index}") for index in range(7)]
        compute_embeddings(provider, targets, batch_size=3)
        assert [len(batch) for batch in provider.batches] == [3, 3, 1]


class TestTextesVidesEtPannes:
    def test_les_textes_vides_ne_sont_jamais_embarques(self) -> None:
        report = BackfillReport()
        planned = plan_embeddings([target(""), target("   "), target("Python")], report)
        assert [item.text for item in planned] == ["Python"]
        assert report.skipped_empty == 2

    def test_un_vecteur_nul_n_est_jamais_persiste(self) -> None:
        # Défense en profondeur : même si un texte non vide produisait un
        # vecteur nul, il ne doit pas atteindre la colonne pgvector.
        provider = CountingProvider()
        assert compute_embeddings(provider, [target("!!!")]) == {}

    def test_une_panne_provider_est_comptee_sans_interrompre(self) -> None:
        report = BackfillReport()
        vectors = compute_embeddings(
            BrokenProvider(), [target("Développeur"), target("Comptable")], report=report
        )
        assert vectors == {}
        assert report.errors == 2
        assert report.computed == 0

    def test_lot_vide(self) -> None:
        assert compute_embeddings(CountingProvider(), []) == {}


class TestRapport:
    def test_le_rapport_est_serialisable(self) -> None:
        report = BackfillReport()
        planned = plan_embeddings([target("Python"), target("")], report)
        compute_embeddings(CountingProvider(), planned, report=report)
        assert report.as_dict() == {
            "seen": 2,
            "computed": 1,
            "skipped_present": 0,
            "skipped_empty": 1,
            "errors": 0,
        }


@pytest.mark.parametrize("batch_size", [0, -1])
def test_batch_size_degenere_ne_boucle_pas(batch_size: int) -> None:
    provider = CountingProvider()
    targets = [target(f"Métier {index}") for index in range(3)]
    assert len(compute_embeddings(provider, targets, batch_size=batch_size)) == 3

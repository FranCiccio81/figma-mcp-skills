"""Provider d'embeddings local : déterminisme, stabilité, normalisation.

Ces propriétés ne sont pas cosmétiques : un provider non déterministe
écrirait en base des vecteurs incomparables entre l'API et les workers, et
un vecteur non normalisé fausserait TOUS les seuils de cosinus du produit
(0,75 crédit « proche », 0,55–0,80 similarité métier, 0,92 dédup).
"""

import math
import subprocess
import sys
from pathlib import Path

import pytest

from app.ai.embeddings.hashing import HashingEmbeddingProvider

DIM = 256
#: Racine du paquet ``app`` — le sous-processus doit pouvoir l'importer.
API_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def provider() -> HashingEmbeddingProvider:
    return HashingEmbeddingProvider(dimension=DIM)


def norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class TestDeterminisme:
    def test_deux_appels_rendent_le_meme_vecteur(
        self, provider: HashingEmbeddingProvider
    ) -> None:
        first = provider.embed("Développeur backend Python")
        second = provider.embed("Développeur backend Python")
        assert first == second

    def test_deux_instances_rendent_le_meme_vecteur(self) -> None:
        text = "Ingénieure data senior"
        assert (
            HashingEmbeddingProvider(dimension=DIM).embed(text)
            == HashingEmbeddingProvider(dimension=DIM).embed(text)
        )

    def test_stable_entre_processus_malgre_pythonhashseed(self) -> None:
        """Garde-fou anti-``hash()`` : le hachage natif est randomisé par
        processus. Un vecteur qui dépendrait de ``PYTHONHASHSEED`` rendrait
        la base incohérente entre l'API et les workers Celery."""
        script = (
            "from app.ai.embeddings.hashing import HashingEmbeddingProvider;"
            f"print(HashingEmbeddingProvider(dimension={DIM})"
            ".embed('Développeur backend Python')[:16])"
        )
        outputs = {
            subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                check=True,
                cwd=API_ROOT,
                env={"PYTHONHASHSEED": seed, "PATH": ""},
            ).stdout
            for seed in ("0", "1", "12345")
        }
        assert len(outputs) == 1


class TestNormalisation:
    def test_vecteur_normalise_l2(self, provider: HashingEmbeddingProvider) -> None:
        for text in ("Python", "Développeur backend Python chez Boussole", "data"):
            assert norm(provider.embed(text)) == pytest.approx(1.0)

    def test_dimension_respectee(self) -> None:
        for dimension in (8, 64, 1024):
            vector = HashingEmbeddingProvider(dimension=dimension).embed("Développeur")
            assert len(vector) == dimension

    def test_texte_vide_rend_un_vecteur_nul(
        self, provider: HashingEmbeddingProvider
    ) -> None:
        # Jamais persisté par le backfill : un vecteur nul rendrait tout
        # cosinus nul et ferait diverger l'index HNSW cosinus.
        for text in ("", "   ", "!!! ---"):
            vector = provider.embed(text)
            assert vector == [0.0] * DIM

    def test_embed_texts_preserve_l_ordre_et_l_arite(
        self, provider: HashingEmbeddingProvider
    ) -> None:
        texts = ["Python", "Comptable", "Python"]
        vectors = provider.embed_texts(texts)
        assert len(vectors) == 3
        assert vectors[0] == vectors[2]
        assert vectors[0] != vectors[1]

    def test_dimension_invalide_refusee(self) -> None:
        with pytest.raises(ValueError):
            HashingEmbeddingProvider(dimension=0)


class TestSimilariteLexicale:
    """Le provider local capture de la similarité LEXICALE (pas du sens) —
    c'est ce qui permet de calibrer la chaîne sans réseau (Q11 non tranchée)."""

    def test_variante_orthographique_plus_proche_qu_un_autre_metier(
        self, provider: HashingEmbeddingProvider
    ) -> None:
        reference = provider.embed("Développeur backend")
        variante = provider.embed("Developpeur back-end")
        autre = provider.embed("Infirmier anesthésiste")
        assert cosine(reference, variante) > cosine(reference, autre)

    def test_casse_et_accents_ignores(self, provider: HashingEmbeddingProvider) -> None:
        assert provider.embed("DÉVELOPPEUR") == provider.embed("developpeur")

    def test_texte_identique_cosinus_un(self, provider: HashingEmbeddingProvider) -> None:
        vector = provider.embed("Data engineer")
        assert cosine(vector, vector) == pytest.approx(1.0)

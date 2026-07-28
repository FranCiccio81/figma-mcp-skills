"""Provider d'embeddings local : déterminisme, stabilité, normalisation.

Ces propriétés ne sont pas cosmétiques : un provider non déterministe
écrirait en base des vecteurs incomparables entre l'API et les workers, et
un vecteur non normalisé fausserait TOUS les seuils de cosinus du produit
(0,75 crédit « proche », 0,55–0,80 similarité métier, 0,92 dédup).
"""

import hashlib
import math
import subprocess
import sys
from pathlib import Path

import pytest

from app.ai.embeddings.hashing import HASHING_MODEL_VERSION, HashingEmbeddingProvider

DIM = 256
#: Seuil produit du crédit « compétence proche » (06 §2.1).
SEUIL_PROCHE = 0.75
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


class TestSymbolesDesTechnologies:
    """Le symbole fait partie du NOM : ``C``, ``C++`` et ``C#`` sont des
    langages DIFFÉRENTS, ``.NET`` n'est pas ``NET``.

    Régression visée : une tokenisation ``[0-9a-z]+`` les rend strictement
    indiscernables (cosinus 1,0). Une offre exigeant C++ créditerait alors
    « proche » (seuil 0,75, 06 §2.1) un candidat ne connaissant que C —
    un faux positif que le candidat lit comme une compétence couverte.
    """

    @pytest.mark.parametrize(
        ("gauche", "droite"),
        [("C", "C++"), ("C", "C#"), ("C++", "C#"), (".NET", "NET")],
    )
    def test_deux_technologies_distinctes_ne_sont_pas_confondues(
        self, provider: HashingEmbeddingProvider, gauche: str, droite: str
    ) -> None:
        similarite = cosine(provider.embed(gauche), provider.embed(droite))
        assert similarite < SEUIL_PROCHE, (
            f"{gauche!r} et {droite!r} sont crédités « proches » (cos "
            f"{similarite:.4f} ≥ {SEUIL_PROCHE})"
        )

    def test_les_symboles_survivent_au_repli(
        self, provider: HashingEmbeddingProvider
    ) -> None:
        """Casse et accents restent ignorés — seuls ``+``, ``#`` et le point
        de tête sont désormais porteurs de sens."""
        assert provider.embed("C++") == provider.embed("c++")
        assert provider.embed(".NET") == provider.embed(".net")

    def test_ponctuation_de_fin_de_phrase_toujours_ignoree(
        self, provider: HashingEmbeddingProvider
    ) -> None:
        """Le point n'est capturé qu'en TÊTE : sans cela, tout texte finissant
        par un point dériverait d'un texte par ailleurs identique."""
        assert provider.embed("Développeur Python") == provider.embed(
            "Développeur Python."
        )

    @pytest.mark.parametrize(
        ("gauche", "droite", "attendu"),
        [
            ("Java", "JavaScript", 0.4045),
            ("Scala", "Scalabilité", 0.4714),
            ("Agile", "Fragile", 0.5774),
        ],
    )
    def test_non_regression_des_cas_sans_symbole(
        self, provider: HashingEmbeddingProvider, gauche: str, droite: str, attendu: float
    ) -> None:
        """Les libellés sans symbole doivent garder EXACTEMENT leur cosinus :
        la correction ne devait rien changer d'autre."""
        assert cosine(provider.embed(gauche), provider.embed(droite)) == pytest.approx(
            attendu, abs=1e-4
        )


def test_le_changement_d_algorithme_impose_d_incrementer_la_version() -> None:
    """08 §8 : les vecteurs en base ne sont comparables qu'à modèle constant.

    Empreinte d'un texte de référence, appariée à ``HASHING_MODEL_VERSION``.
    Toucher à la tokenisation ou à la projection sans incrémenter la version
    fait tomber ce test — c'est précisément le rappel qui manquait : les
    vecteurs déjà écrits deviennent obsolètes et doivent être recalculés
    (``backfill_* force=True``).
    """
    vecteur = HashingEmbeddingProvider(dimension=DIM).embed("Développeur C++ / .NET")
    empreinte = hashlib.sha256(
        ";".join(f"{value:.12f}" for value in vecteur).encode()
    ).hexdigest()[:16]

    assert (HASHING_MODEL_VERSION, empreinte) == (
        "hashing-ngram-v2",
        "8ba9c887bc1980d1",
    )

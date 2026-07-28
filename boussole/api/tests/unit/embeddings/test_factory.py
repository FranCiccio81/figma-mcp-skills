"""Fabrique d'embeddings : défaut local, validation de dimension, fallback.

Le point le plus important est la VALIDATION DE DIMENSION : un provider qui
ne produit pas ``EMBEDDING_DIM`` dimensions corromprait silencieusement la
base (colonnes ``vector(1024)`` + index HNSW, D06). La fabrique doit
échouer bruyamment, jamais dégrader.
"""

from collections.abc import Sequence

import pytest

from app.ai.embeddings.base import (
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingProviderUnavailableError,
)
from app.ai.embeddings.factory import (
    HASHING,
    MANAGED,
    RoutedEmbeddingProvider,
    build_embedding_provider,
    check_embedding_dimension,
    embedding_breaker_for,
    get_embedding_provider,
    reset_embedding_provider_cache,
)
from app.ai.embeddings.hashing import HashingEmbeddingProvider
from app.ai.embeddings.managed import ManagedEmbeddingProvider
from app.core.config import Settings
from app.modules.referentials.models import EMBEDDING_DIM


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    reset_embedding_provider_cache()


def settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


class FailingProvider:
    """Provider qui échoue toujours (simulation d'incident fournisseur)."""

    def __init__(self, dimension: int = EMBEDDING_DIM) -> None:
        self.dimension = dimension
        self.model = "failing"
        self.calls = 0

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        raise EmbeddingProviderUnavailableError("incident simulé")


class TestSelection:
    def test_provider_par_defaut_est_local_et_sans_reseau(self) -> None:
        provider = get_embedding_provider(settings())
        assert isinstance(provider, RoutedEmbeddingProvider)
        assert [name for name, _ in provider.candidates] == [HASHING]
        assert provider.dimension == EMBEDDING_DIM

    def test_le_provider_managé_n_est_jamais_actif_par_defaut(self) -> None:
        # Q11 non tranchée : aucun fournisseur réel ne doit être joignable
        # sans configuration explicite ET sans clé.
        assert settings().embeddings_provider == HASHING

    def test_managé_sans_cle_est_ignore_et_degrade_vers_le_local(self) -> None:
        provider = get_embedding_provider(
            settings(embeddings_provider=MANAGED, embeddings_api_key="")
        )
        assert isinstance(provider, RoutedEmbeddingProvider)
        assert [name for name, _ in provider.candidates] == [HASHING]

    def test_provider_inconnu_degrade_vers_le_local(self) -> None:
        provider = get_embedding_provider(settings(embeddings_provider="inexistant"))
        assert isinstance(provider, RoutedEmbeddingProvider)
        assert [name for name, _ in provider.candidates] == [HASHING]

    def test_nom_inconnu_leve_a_la_construction_directe(self) -> None:
        with pytest.raises(ValueError, match="inconnu"):
            build_embedding_provider("inexistant", settings())

    def test_managé_construit_avec_cle_mais_refuse_d_appeler(self) -> None:
        # Le squelette existe et se construit ; l'appel échoue proprement
        # tant que Q11 n'est pas tranchée — jamais d'appel réseau.
        provider = ManagedEmbeddingProvider(
            dimension=EMBEDDING_DIM,
            model="modele-a-choisir",
            api_key="clef",
            base_url="https://exemple.invalid",
        )
        with pytest.raises(EmbeddingProviderUnavailableError):
            provider.embed_texts(["Développeur"])


class TestValidationDimension:
    def test_dimension_divergente_leve_une_erreur_explicite(self) -> None:
        with pytest.raises(EmbeddingDimensionError) as excinfo:
            build_embedding_provider(HASHING, settings(embeddings_dim=512))
        message = str(excinfo.value)
        assert "512" in message
        assert str(EMBEDDING_DIM) in message
        assert "re-embedding" in message  # la procédure 08 §8 est rappelée

    def test_dimension_divergente_n_est_jamais_absorbee_par_le_fallback(self) -> None:
        # Contrairement à une clé manquante, une dimension fausse ne doit
        # PAS dégrader silencieusement : elle remonte.
        with pytest.raises(EmbeddingDimensionError):
            get_embedding_provider(settings(embeddings_dim=768))

    def test_dimension_conforme_acceptee(self) -> None:
        check_embedding_dimension(EMBEDDING_DIM, provider=HASHING)

    def test_provider_construit_a_la_dimension_du_schema(self) -> None:
        provider = build_embedding_provider(HASHING, settings())
        assert provider.dimension == EMBEDDING_DIM
        assert len(provider.embed_texts(["Développeur"])[0]) == EMBEDDING_DIM


class TestFallbackEtBreaker:
    def test_le_fallback_prend_le_relais_quand_le_primaire_echoue(self) -> None:
        failing = FailingProvider()
        healthy = HashingEmbeddingProvider(dimension=EMBEDDING_DIM)
        routed = RoutedEmbeddingProvider(
            candidates=(("failing", failing), (HASHING, healthy)),
            dimension=EMBEDDING_DIM,
            model="failing",
        )
        vectors = routed.embed_texts(["Développeur backend"])
        assert failing.calls == 1
        assert len(vectors[0]) == EMBEDDING_DIM

    def test_sans_fallback_l_erreur_remonte(self) -> None:
        routed = RoutedEmbeddingProvider(
            candidates=(("failing", FailingProvider()),),
            dimension=EMBEDDING_DIM,
            model="failing",
        )
        with pytest.raises(EmbeddingError):
            routed.embed_texts(["Développeur"])

    def test_le_circuit_ouvert_saute_le_provider(self) -> None:
        conf = settings(ai_circuit_breaker_threshold=2)
        failing = FailingProvider()
        breaker = embedding_breaker_for("failing", conf)
        routed = RoutedEmbeddingProvider(
            candidates=(("failing", failing), (HASHING, HashingEmbeddingProvider(
                dimension=EMBEDDING_DIM
            ))),
            dimension=EMBEDDING_DIM,
            model="failing",
            breakers={"failing": breaker},
        )
        for _ in range(2):
            routed.embed_texts(["Développeur"])
        assert breaker.state == "open"

        calls_before = failing.calls
        routed.embed_texts(["Développeur"])
        # Circuit ouvert : le provider en panne n'est plus rappelé, on sert
        # directement le fallback (D18).
        assert failing.calls == calls_before

    def test_aucun_provider_disponible_leve_une_erreur_explicite(self) -> None:
        conf = settings(ai_circuit_breaker_threshold=1)
        breaker = embedding_breaker_for("failing", conf)
        routed = RoutedEmbeddingProvider(
            candidates=(("failing", FailingProvider()),),
            dimension=EMBEDDING_DIM,
            model="failing",
            breakers={"failing": breaker},
        )
        with pytest.raises(EmbeddingError):
            routed.embed_texts(["Développeur"])  # ouvre le circuit
        with pytest.raises(EmbeddingProviderUnavailableError):
            routed.embed_texts(["Développeur"])  # circuit ouvert : plus personne

"""Interface ``EmbeddingProvider`` (08 §8) et erreurs de la couche embeddings.

Même patron que :mod:`app.ai.providers.base` (D08) : un Protocol minimal,
des erreurs à vocabulaire fermé, et une fabrique
(:func:`app.ai.embeddings.factory.get_embedding_provider`) qui sélectionne
l'implémentation par configuration avec fallback et circuit breaker (D18).

**Contrat de dimension** — un provider dont la dimension diffère de celle
du schéma (``vector(1024)``, D06) corromprait SILENCIEUSEMENT la base :
des vecteurs de dimensions mélangées rendent tout cosinus faux et l'index
HNSW inexploitable. La fabrique valide donc la dimension au démarrage et
lève :class:`EmbeddingDimensionError` — jamais de dégradation muette.

**Contrat de normalisation** — tout vecteur rendu est normalisé L2 (norme
1,0), sauf pour un texte vide qui rend le vecteur nul. Les seuils de
cosinus de 06/07 (0,75 / 0,80–0,55 / 0,85 / 0,92) supposent cette
normalisation ; un texte vide n'est jamais persisté (voir
:mod:`app.ai.embeddings.backfill`).
"""

from collections.abc import Sequence
from typing import Protocol

__all__ = [
    "EmbeddingDimensionError",
    "EmbeddingError",
    "EmbeddingProvider",
    "EmbeddingProviderConfigurationError",
    "EmbeddingProviderUnavailableError",
]


class EmbeddingError(RuntimeError):
    """Échec de la couche embeddings.

    ``str(exc)`` est un message TECHNIQUE : il ne recopie jamais le texte
    soumis (D09, 11 §3) — un intitulé de poste ou un libellé de CV est une
    donnée personnelle potentielle.
    """

    error_code = "embedding_error"


class EmbeddingProviderConfigurationError(EmbeddingError):
    """Provider réel demandé sans configuration exploitable (clé/endpoint).

    Levée à la CONSTRUCTION, jamais au premier appel réseau : un provider
    managé ne doit pas pouvoir exister sans clé (patron D08).
    """

    error_code = "embedding_provider_unavailable"


class EmbeddingProviderUnavailableError(EmbeddingError):
    """Aucun provider d'embeddings disponible (circuit ouvert, pas de fallback).

    L'application reste fonctionnelle : sans vecteurs, ``title_similarity``
    reste inconnue (k=0), le crédit « proche » reste désactivé, l'étage 2
    de dédup ne fusionne pas et le rerank est neutre (D18).
    """

    error_code = "embedding_provider_unavailable"


class EmbeddingDimensionError(EmbeddingError):
    """Dimension du provider incompatible avec le schéma ``vector(1024)``.

    Erreur BLOQUANTE et volontairement bruyante : mélanger des dimensions
    en base est irréversible sans re-embedding complet (08 §8 —
    « tout changement de modèle/dimension déclenche un re-embedding
    complet + un re-calibrage des seuils »).
    """

    error_code = "embedding_dimension_mismatch"


class EmbeddingProvider(Protocol):
    """Contrat minimal d'un fournisseur d'embeddings."""

    @property
    def dimension(self) -> int:
        """Dimension des vecteurs produits — validée contre ``EMBEDDING_DIM``."""
        ...

    @property
    def model(self) -> str:
        """Identifiant de modèle journalisé (``embedding_model_version``, 08 §8).

        Tout changement impose un re-embedding complet du corpus.
        """
        ...

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode ``texts`` en vecteurs normalisés L2, dans le même ordre.

        Retourne exactement ``len(texts)`` vecteurs de ``dimension``
        flottants. Un texte vide rend le vecteur nul (jamais persisté).
        """
        ...

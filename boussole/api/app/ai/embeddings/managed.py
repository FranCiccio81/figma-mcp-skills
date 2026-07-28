"""Squelette de provider d'embeddings MANAGÉ — jamais actif par défaut.

┌────────────────────────────────────────────────────────────────────────┐
│ ⚠️  Q11 N'EST PAS TRANCHÉE — 17-open-questions.md                       │
│                                                                        │
│ « Modèle d'embeddings (multilingue FR/EN, dimension, hébergement UE) »  │
│ — décideur : ML Eng, échéance : avant M2. Hypothèse de travail en       │
│ attente : dimension 1024, modèle multilingue managé, à évaluer sur le   │
│ jeu annoté. 08 §8 mentionne `multilingual-e5-large` auto-hébergé et 08  │
│ Q3 pose explicitement l'alternative auto-hébergé vs API managée.        │
│                                                                        │
│ Ce fichier ne choisit RIEN et n'affirme AUCUNE conformité :             │
│ - aucun fournisseur n'est nommé, aucun endpoint n'est codé en dur ;     │
│ - aucune affirmation de résidence, de traitement ou de non-entraînement │
│   UE n'est faite ici : elles relèvent d'un DPA signé (D09, Q4, Q38) et  │
│   d'une revue juridique, pas d'un commentaire de code ;                 │
│ - la dimension reste imposée par le schéma (`vector(1024)`, D06) et est │
│   validée par la fabrique : un modèle d'une autre dimension est REFUSÉ  │
│   au démarrage, jamais absorbé silencieusement.                         │
└────────────────────────────────────────────────────────────────────────┘

Ce qu'il reste à écrire quand Q11 sera tranchée (volontairement NON écrit
tant que la forme d'API du fournisseur retenu est inconnue) :

1. client HTTP borné (``httpx``, timeout ``embeddings_timeout_seconds``,
   retries bornés + ``Retry-After`` honoré comme
   :mod:`app.ai.providers.anthropic`) ;
2. découpage en lots de ``batch_size`` textes, ordre des vecteurs
   rendus identique à l'ordre des textes soumis (contrat du Protocol) ;
3. normalisation L2 en sortie si le fournisseur ne la garantit pas ;
4. vérification que la dimension annoncée par la réponse est bien
   ``dimension`` — sinon :class:`EmbeddingDimensionError` ;
5. journalisation par appel (tokens, latence, statut) sans contenu de
   texte (D09, 11 §3), et incrément de ``embedding_model_version``.

En l'état, toute tentative d'usage lève
:class:`EmbeddingProviderUnavailableError` : la fabrique dégrade alors
vers le provider local en journalisant bruyamment — l'application ne
part JAMAIS en appel réseau sur un fournisseur non choisi.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.ai.embeddings.base import (
    EmbeddingProviderConfigurationError,
    EmbeddingProviderUnavailableError,
)

__all__ = ["ManagedEmbeddingProvider"]


@dataclass
class ManagedEmbeddingProvider:
    """Provider managé — construit uniquement si clé ET endpoint sont fournis.

    La construction échoue explicitement sans configuration (patron D08 :
    « un provider réel ne doit pas pouvoir exister sans clé »), et l'appel
    échoue proprement tant que Q11 n'est pas tranchée.
    """

    dimension: int
    model: str
    api_key: str = field(repr=False, default="")
    base_url: str = ""
    timeout_seconds: float = 20.0
    batch_size: int = 64

    def __post_init__(self) -> None:
        if not self.api_key:
            raise EmbeddingProviderConfigurationError(
                "provider d'embeddings managé demandé sans EMBEDDINGS_API_KEY"
            )
        if not self.base_url:
            raise EmbeddingProviderConfigurationError(
                "provider d'embeddings managé demandé sans EMBEDDINGS_API_BASE_URL"
            )
        if not self.model:
            raise EmbeddingProviderConfigurationError(
                "provider d'embeddings managé demandé sans EMBEDDINGS_MODEL"
            )

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Non implémenté tant que Q11 n'est pas tranchée — échec propre."""
        raise EmbeddingProviderUnavailableError(
            "provider d'embeddings managé non implémenté : le choix du modèle "
            "(multilingue FR/EN, dimension, hébergement UE) relève de Q11, non "
            "tranchée. Aucun appel réseau n'est émis."
        )

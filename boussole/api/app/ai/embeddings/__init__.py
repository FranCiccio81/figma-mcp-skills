"""Couche d'embeddings (D06, D07, D13 — 08 §8).

Quatre fonctionnalités dépendent des vecteurs produits ici :

1. ``title_similarity`` (06 §2.3, poids 15) — cosinus entre l'embedding
   « intitulé + 1er paragraphe » de l'offre et les embeddings d'intitulés
   du candidat ;
2. crédit « compétence proche » 0,5 (06 §2.1, seuil 0,75) — cosinus entre
   libellés de compétences ;
3. déduplication étage 2 (D13, cosinus ≥ 0,92) ;
4. rerank vectoriel de la recherche hybride (D07).

Le module expose UNE interface (:class:`EmbeddingProvider`) et deux
implémentations : :class:`HashingEmbeddingProvider` (locale, déterministe,
défaut) et :class:`ManagedEmbeddingProvider` (squelette, jamais actif par
défaut — le choix du modèle relève de **Q11, non tranchée**).
"""

from app.ai.embeddings.base import (
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingProviderConfigurationError,
    EmbeddingProviderUnavailableError,
)
from app.ai.embeddings.factory import (
    HASHING,
    MANAGED,
    build_embedding_provider,
    check_embedding_dimension,
    get_embedding_provider,
    reset_embedding_provider_cache,
)
from app.ai.embeddings.hashing import HashingEmbeddingProvider
from app.ai.embeddings.text import (
    first_paragraph,
    job_embedding_text,
    profile_embedding_text,
    skill_embedding_text,
    source_text_hash,
)

__all__ = [
    "HASHING",
    "MANAGED",
    "EmbeddingDimensionError",
    "EmbeddingError",
    "EmbeddingProvider",
    "EmbeddingProviderConfigurationError",
    "EmbeddingProviderUnavailableError",
    "HashingEmbeddingProvider",
    "build_embedding_provider",
    "check_embedding_dimension",
    "first_paragraph",
    "get_embedding_provider",
    "job_embedding_text",
    "profile_embedding_text",
    "reset_embedding_provider_cache",
    "skill_embedding_text",
    "source_text_hash",
]

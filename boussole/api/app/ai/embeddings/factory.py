"""Fabrique de providers d'embeddings — même patron que les providers LLM.

Sélection par configuration (``EMBEDDINGS_PROVIDER``, défaut **hashing**) :
le provider managé n'est jamais actif implicitement, et jamais sans clé.
Un second provider (``EMBEDDINGS_FALLBACK_PROVIDER``) peut être configuré ;
il est essayé quand le primaire échoue ou que son circuit est ouvert.

Le :class:`~app.ai.providers.factory.CircuitBreaker` de la couche LLM est
réutilisé tel quel (D18) : un fournisseur d'embeddings en panne ne doit
pas être rappelé à chaque offre ingérée.

**Validation de dimension au démarrage** — un modèle dont la dimension
diffère de ``EMBEDDING_DIM`` (``vector(1024)`` du schéma, D06) corromprait
silencieusement la base. La fabrique refuse : :class:`EmbeddingDimensionError`
avec un message explicite. Ce contrôle est fait AVANT toute mise en cache
du provider, et à chaque appel de :func:`get_embedding_provider` (le coût
est une comparaison d'entiers).

Dégradation (D18) : si aucun provider n'est exploitable, la fabrique
retombe sur le provider local en journalisant une erreur — l'application
reste fonctionnelle, avec des vecteurs lexicaux plutôt qu'aucun vecteur.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from app.ai.embeddings.base import (
    EmbeddingDimensionError,
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingProviderConfigurationError,
    EmbeddingProviderUnavailableError,
)
from app.ai.embeddings.hashing import HashingEmbeddingProvider
from app.ai.providers.factory import CircuitBreaker
from app.core.config import Settings, get_settings
from app.modules.referentials.models import EMBEDDING_DIM

logger = logging.getLogger(__name__)

__all__ = [
    "EMBEDDING_PROVIDER_BUILDERS",
    "HASHING",
    "MANAGED",
    "RoutedEmbeddingProvider",
    "build_embedding_provider",
    "check_embedding_dimension",
    "embedding_breaker_for",
    "get_embedding_provider",
    "reset_embedding_provider_cache",
]

#: Noms de providers reconnus par la configuration.
HASHING = "hashing"
MANAGED = "managed"


@dataclass
class RoutedEmbeddingProvider:
    """``EmbeddingProvider`` composite : primaire → fallback, sous breaker.

    Implémente le Protocol à l'identique : les appelants (ingestion,
    backfill, recherche) ne voient aucune différence avec un provider
    simple.
    """

    candidates: tuple[tuple[str, EmbeddingProvider], ...]
    dimension: int
    model: str
    breakers: Mapping[str, CircuitBreaker] = field(default_factory=dict)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        last_error: EmbeddingError | None = None
        skipped: list[str] = []
        for name, provider in self.candidates:
            breaker = self.breakers.get(name)
            if breaker is not None and not breaker.allow():
                skipped.append(name)
                logger.warning("embedding_provider_circuit_open provider=%s", name)
                continue
            try:
                vectors = provider.embed_texts(texts)
            except EmbeddingError as exc:
                if breaker is not None:
                    breaker.record_failure()
                last_error = exc
                logger.warning(
                    "embedding_provider_failed provider=%s error_code=%s",
                    name, exc.error_code,
                )
                continue
            if breaker is not None:
                breaker.record_success()
            return vectors

        if last_error is not None:
            raise last_error
        raise EmbeddingProviderUnavailableError(
            "aucun provider d'embeddings disponible (circuits ouverts : "
            f"{', '.join(skipped) or 'aucun provider configuré'})"
        )


#: Constructeurs par nom — enregistrement déclaratif (ajouter un provider
#: réel = une entrée ici, rien d'autre à changer).
EmbeddingProviderBuilder = Callable[[Settings], EmbeddingProvider]


def _build_hashing(settings: Settings) -> EmbeddingProvider:
    return HashingEmbeddingProvider(dimension=settings.embeddings_dim)


def _build_managed(settings: Settings) -> EmbeddingProvider:
    # Import local : le squelette managé n'est chargé que s'il est demandé.
    from app.ai.embeddings.managed import ManagedEmbeddingProvider

    return ManagedEmbeddingProvider(
        dimension=settings.embeddings_dim,
        model=settings.embeddings_model,
        api_key=settings.embeddings_api_key,
        base_url=settings.embeddings_api_base_url,
        timeout_seconds=settings.embeddings_timeout_seconds,
        batch_size=settings.embeddings_batch_size,
    )


EMBEDDING_PROVIDER_BUILDERS: dict[str, EmbeddingProviderBuilder] = {
    HASHING: _build_hashing,
    MANAGED: _build_managed,
}

#: Instances et disjoncteurs partagés par processus.
_PROVIDERS: dict[str, EmbeddingProvider] = {}
_BREAKERS: dict[str, CircuitBreaker] = {}


def reset_embedding_provider_cache() -> None:
    """Vide instances et disjoncteurs (tests, changement de configuration)."""
    _PROVIDERS.clear()
    _BREAKERS.clear()


def check_embedding_dimension(dimension: int, *, provider: str) -> None:
    """Refuse toute dimension incompatible avec le schéma ``vector(1024)``.

    Un modèle d'une autre dimension écrirait des vecteurs inexploitables :
    l'insertion pgvector échouerait (au mieux) ou les cosinus seraient
    faux (au pire, si la dimension divise/complète par hasard). On échoue
    donc au DÉMARRAGE avec la procédure de migration en clair (08 §8).
    """
    if dimension != EMBEDDING_DIM:
        raise EmbeddingDimensionError(
            f"dimension d'embedding incompatible : provider {provider!r} produit "
            f"{dimension} dimensions, le schéma en attend {EMBEDDING_DIM} "
            "(colonnes vector(1024) + index HNSW, D06). Changer de modèle ou de "
            "dimension impose une migration de schéma, un re-embedding COMPLET "
            "et un re-calibrage des seuils 0,75 / 0,80–0,55 / 0,85 / 0,92 "
            "(08 §8, Q11/Q12) — jamais un simple changement de configuration."
        )


def embedding_breaker_for(name: str, settings: Settings | None = None) -> CircuitBreaker:
    """Disjoncteur du provider ``name`` (créé au besoin)."""
    breaker = _BREAKERS.get(name)
    if breaker is None:
        conf = settings or get_settings()
        breaker = CircuitBreaker(
            threshold=conf.ai_circuit_breaker_threshold,
            reset_seconds=conf.ai_circuit_breaker_reset_seconds,
        )
        _BREAKERS[name] = breaker
    return breaker


def build_embedding_provider(
    name: str, settings: Settings | None = None
) -> EmbeddingProvider:
    """Construit (et mémorise) le provider ``name``, dimension validée.

    Lève :class:`EmbeddingProviderConfigurationError` si un provider réel
    n'a pas de clé, :class:`EmbeddingDimensionError` si sa dimension ne
    correspond pas au schéma, ``ValueError`` si le nom est inconnu.
    """
    cached = _PROVIDERS.get(name)
    if cached is not None:
        return cached
    builder = EMBEDDING_PROVIDER_BUILDERS.get(name)
    if builder is None:
        raise ValueError(
            f"provider d'embeddings inconnu : {name!r} "
            f"(connus : {sorted(EMBEDDING_PROVIDER_BUILDERS)})"
        )
    provider = builder(settings or get_settings())
    check_embedding_dimension(provider.dimension, provider=name)
    _PROVIDERS[name] = provider
    return provider


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Provider d'embeddings effectif — primaire + fallback + breakers."""
    conf = settings or get_settings()
    names = [conf.embeddings_provider or HASHING]
    fallback = conf.embeddings_fallback_provider
    if fallback and fallback not in names:
        names.append(fallback)

    candidates: list[tuple[str, EmbeddingProvider]] = []
    for name in names:
        try:
            candidates.append((name, build_embedding_provider(name, conf)))
        except EmbeddingDimensionError:
            # Jamais absorbée : une dimension fausse corrompt la base.
            raise
        except EmbeddingProviderConfigurationError:
            logger.error(
                "embedding_provider_not_configured provider=%s — provider ignoré", name
            )
        except ValueError:
            logger.error("embedding_provider_unknown provider=%s — provider ignoré", name)

    if not candidates:
        # Dégradation explicite et bruyante (D18) : vecteurs lexicaux
        # locaux plutôt qu'aucun vecteur — l'ingestion et la recherche
        # continuent de fonctionner.
        logger.error("embedding_provider_fallback_to_hashing")
        candidates.append((HASHING, build_embedding_provider(HASHING, conf)))

    primary = candidates[0][1]
    return RoutedEmbeddingProvider(
        candidates=tuple(candidates),
        dimension=primary.dimension,
        model=primary.model,
        breakers={name: embedding_breaker_for(name, conf) for name, _ in candidates},
    )

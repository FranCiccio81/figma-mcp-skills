"""Interface ``LLMProvider`` (D08) et erreurs de la couche provider.

Toute sortie de provider est un ``dict`` JSON destiné à être validé
Pydantic contre ``ai-output-schemas.json`` par la tâche appelante ; en cas
d'échec de validation : 1 retry avec le message d'erreur, puis
repair-parse, puis échec propre (D08).

Implémentations : :class:`~app.ai.providers.fake.FakeProvider` (défaut),
:class:`~app.ai.providers.anthropic.AnthropicProvider` (réel, jamais actif
sans clé ni sans résolution de Q4), sélection et fallback par
:func:`app.ai.providers.factory.get_llm_provider` (circuit breaker D18).
Chaque appel réel est journalisé dans ``ai_calls`` par la couche provider
— jamais par les tâches (:mod:`app.ai.calls`).

Les erreurs ci-dessous portent un ``error_code`` du vocabulaire fermé de
08 §5.1 (:data:`app.ai.calls.ERROR_CODES`). Les tâches n'ont pas besoin de
les distinguer : elles remontent en ``provider_error`` dans leurs
gestionnaires existants (échec propre par tâche, 08 §5.1) — le détail est
journalisé, pas propagé à l'utilisateur.
"""

from collections.abc import Mapping
from typing import Any, Protocol


class LLMProviderError(RuntimeError):
    """Échec d'un appel provider, porteur d'un ``error_code`` fermé.

    ``str(exc)`` est un message TECHNIQUE : il ne doit JAMAIS recopier le
    prompt ni la réponse du modèle (D09, 11 §3).
    """

    error_code = "provider_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class LLMTimeoutError(LLMProviderError):
    """Dépassement du délai d'appel (cibles p95 de 08 §2.2)."""

    error_code = "timeout"


class LLMRateLimitError(LLMProviderError):
    """429 provider après épuisement des retries bornés (``Retry-After`` respecté)."""

    error_code = "rate_limited"


class LLMResponseError(LLMProviderError):
    """Réponse inexploitable : ni JSON valide, ni réparable (repair-parse)."""

    error_code = "parse_error"


class ProviderUnavailableError(LLMProviderError):
    """Aucun provider disponible (circuit ouvert, aucun fallback) — D18.

    L'application reste fonctionnelle sans LLM : seules les fonctions qui en
    dépendent sont suspendues, avec un échec propre par tâche.
    """

    error_code = "provider_unavailable"


class ProviderConfigurationError(LLMProviderError):
    """Provider réel demandé sans configuration exploitable (clé absente).

    Levée à la CONSTRUCTION, jamais au premier appel réseau : un provider
    réel ne doit pas pouvoir exister sans clé.
    """

    error_code = "provider_unavailable"


class LLMProvider(Protocol):
    """Contrat minimal d'un provider LLM à sorties JSON contraintes."""

    def complete_json(
        self,
        task: str,
        prompt: str,
        schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Exécute une tâche typée (``extract_job``, ``extract_cv``…).

        ``schema`` : JSON Schema attendu de la sortie (contrainte côté
        provider quand il le supporte). Retourne le JSON brut — la
        validation Pydantic reste du ressort de l'appelant.
        """
        ...

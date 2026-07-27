"""Fabrique de providers LLM : sélection, fallback, circuit breaker (D08, D18).

Sélection par configuration (``AI_PROVIDER``, défaut **fake** 🟡) : le
provider réel n'est jamais actif implicitement, et jamais sans clé. Un
second provider (``AI_FALLBACK_PROVIDER``) peut être configuré ; il est
essayé quand le primaire échoue ou que son circuit est ouvert.

**Circuit breaker par provider (D18)** : après
``AI_CIRCUIT_BREAKER_THRESHOLD`` échecs consécutifs, le circuit s'ouvre
pendant ``AI_CIRCUIT_BREAKER_RESET_SECONDS`` ; pendant ce temps le provider
n'est plus appelé (on bascule sur le fallback s'il existe). À l'expiration,
un appel d'essai est autorisé (« demi-ouvert ») : succès → circuit refermé,
échec → réouverture immédiate.

Quand plus aucun provider n'est disponible, la fabrique lève
:class:`ProviderUnavailableError` : les tâches traitent déjà ce cas en
échec propre (08 §5.1) et **l'application reste fonctionnelle sans LLM**
(recherche, scores, facts déterministes — D02/D14/D18).

Les tâches existantes ne changent pas : elles reçoivent toujours un
``LLMProvider`` en paramètre ; seule la façon de l'obtenir change.
"""

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.ai.providers.base import (
    LLMProvider,
    LLMProviderError,
    ProviderConfigurationError,
    ProviderUnavailableError,
)
from app.ai.providers.fake import FakeProvider
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

#: Noms de providers reconnus par la configuration.
FAKE = "fake"
ANTHROPIC = "anthropic"


@dataclass
class CircuitBreaker:
    """Disjoncteur simple par provider (D18) — fermé | ouvert | demi-ouvert."""

    threshold: int
    reset_seconds: float
    clock: Callable[[], float] = time.monotonic
    failures: int = 0
    opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if self.clock() - self.opened_at >= self.reset_seconds:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        """``True`` si un appel est autorisé (fermé ou demi-ouvert)."""
        return self.state != "open"

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        if self.state == "half_open":
            # L'appel d'essai a échoué : on rouvre pour un cycle complet.
            self.opened_at = self.clock()
            return
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = self.clock()


@dataclass
class RoutedProvider:
    """``LLMProvider`` composite : primaire → fallback, sous circuit breaker.

    Implémente le Protocol à l'identique : les tâches ne voient aucune
    différence avec un provider simple.
    """

    candidates: tuple[tuple[str, LLMProvider], ...]
    breakers: Mapping[str, CircuitBreaker] = field(default_factory=dict)

    def complete_json(
        self,
        task: str,
        prompt: str,
        schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        last_error: LLMProviderError | None = None
        skipped: list[str] = []
        for name, provider in self.candidates:
            breaker = self.breakers.get(name)
            if breaker is not None and not breaker.allow():
                skipped.append(name)
                logger.warning("ai_provider_circuit_open provider=%s task=%s", name, task)
                continue
            try:
                result = provider.complete_json(task, prompt, schema)
            except LLMProviderError as exc:
                if breaker is not None:
                    breaker.record_failure()
                last_error = exc
                logger.warning(
                    "ai_provider_failed provider=%s task=%s error_code=%s",
                    name, task, exc.error_code,
                )
                continue
            if breaker is not None:
                breaker.record_success()
            return result

        if last_error is not None:
            # Tous les providers essayés ont échoué : on remonte la dernière
            # erreur (son ``error_code`` reste exact : timeout, parse_error…).
            raise last_error
        raise ProviderUnavailableError(
            f"aucun provider LLM disponible (task={task}, circuits ouverts : "
            f"{', '.join(skipped) or 'aucun provider configuré'})"
        )


#: Constructeurs par nom — enregistrement déclaratif (ajout d'un second
#: provider réel = une entrée ici, rien d'autre à changer).
ProviderBuilder = Callable[[Settings], LLMProvider]


def _build_fake(settings: Settings) -> LLMProvider:
    return FakeProvider()


def _build_anthropic(settings: Settings) -> LLMProvider:
    # Import local : le SDK n'est chargé que si le provider est demandé.
    from app.ai.providers.anthropic import AnthropicProvider

    return AnthropicProvider(settings=settings)


PROVIDER_BUILDERS: dict[str, ProviderBuilder] = {
    FAKE: _build_fake,
    ANTHROPIC: _build_anthropic,
}

#: Instances et disjoncteurs partagés par processus : un circuit ouvert doit
#: valoir pour tous les appels, pas seulement pour l'appelant courant.
_PROVIDERS: dict[str, LLMProvider] = {}
_BREAKERS: dict[str, CircuitBreaker] = {}


def reset_provider_cache() -> None:
    """Vide instances et disjoncteurs (tests, changement de configuration)."""
    _PROVIDERS.clear()
    _BREAKERS.clear()


def breaker_for(name: str, settings: Settings | None = None) -> CircuitBreaker:
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


def build_provider(name: str, settings: Settings | None = None) -> LLMProvider:
    """Construit (et mémorise) le provider ``name``.

    Lève :class:`ProviderConfigurationError` si le provider réel n'a pas de
    clé, :class:`ValueError` si le nom est inconnu.
    """
    cached = _PROVIDERS.get(name)
    if cached is not None:
        return cached
    builder = PROVIDER_BUILDERS.get(name)
    if builder is None:
        raise ValueError(f"provider LLM inconnu : {name!r} (connus : {sorted(PROVIDER_BUILDERS)})")
    provider = builder(settings or get_settings())
    _PROVIDERS[name] = provider
    return provider


def get_llm_provider(task: str, settings: Settings | None = None) -> LLMProvider:
    """Provider à utiliser pour ``task`` — primaire + fallback + breakers.

    ``task`` n'influence pas encore la sélection (le modèle par tâche est
    résolu DANS le provider, 08 §2.1) : il sert à la journalisation et
    laisse la porte ouverte à un routage par tâche 🟡.
    """
    conf = settings or get_settings()
    names = [conf.ai_provider or FAKE]
    fallback = conf.ai_fallback_provider
    if fallback and fallback not in names:
        names.append(fallback)

    candidates: list[tuple[str, LLMProvider]] = []
    for name in names:
        try:
            candidates.append((name, build_provider(name, conf)))
        except ProviderConfigurationError:
            # Clé absente : le provider réel N'EST PAS activé (jamais d'appel
            # réseau sans clé). Dégradation explicite et bruyante (D18).
            logger.error(
                "ai_provider_not_configured provider=%s task=%s — provider ignoré", name, task
            )
        except ValueError:
            logger.error("ai_provider_unknown provider=%s task=%s — provider ignoré", name, task)

    if not candidates:
        # Aucun provider exploitable : on retombe sur le factice plutôt que
        # de casser l'application (D18) — sorties « vides mais valides »,
        # accompagnées d'un warning explicite côté tâche.
        logger.error("ai_provider_fallback_to_fake task=%s", task)
        candidates.append((FAKE, build_provider(FAKE, conf)))

    return RoutedProvider(
        candidates=tuple(candidates),
        breakers={name: breaker_for(name, conf) for name, _ in candidates},
    )

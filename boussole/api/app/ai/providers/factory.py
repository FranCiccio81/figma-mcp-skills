"""Fabrique de providers LLM : sélection, fallback, circuit breaker (D08, D18).

Sélection par configuration (``AI_PROVIDER``, défaut **fake** 🟡) : le
provider réel n'est jamais actif implicitement, et jamais sans clé. Un
second provider (``AI_FALLBACK_PROVIDER``) peut être configuré ; il est
essayé quand le primaire échoue ou que son circuit est ouvert.

**Le provider factice n'est JAMAIS un repli implicite (C3).** Il n'est
utilisé que si ``AI_PROVIDER=fake`` a été demandé EXPLICITEMENT. Avant, une
clé absente — ou un circuit ouvert avec ``AI_FALLBACK_PROVIDER=fake`` —
faisait retomber la fabrique sur ``FakeProvider`` : l'utilisateur recevait un
CV « analysé » **entièrement vide**, sans la moindre erreur, et aucune ligne
n'entrait dans ``ai_calls``. C'est exactement l'inverse de D18, qui exige des
fonctions « suspendues avec un message explicite ». Désormais la fabrique
lève :class:`ProviderUnavailableError` — les tâches ont déjà un chemin
d'échec propre pour ce cas.

**Circuit breaker par provider (D18)** : après
``AI_CIRCUIT_BREAKER_THRESHOLD`` échecs consécutifs, le circuit s'ouvre
pendant ``AI_CIRCUIT_BREAKER_RESET_SECONDS`` ; pendant ce temps le provider
n'est plus appelé (on bascule sur le fallback s'il existe). À l'expiration,
**un seul** appel d'essai est autorisé (« demi-ouvert ») : succès → circuit
refermé, échec → réouverture immédiate.

Quand plus aucun provider n'est disponible, la fabrique lève
:class:`ProviderUnavailableError` : les tâches traitent déjà ce cas en
échec propre (08 §5.1) et **l'application reste fonctionnelle sans LLM**
(recherche, scores, facts déterministes — D02/D14/D18).

Les tâches existantes ne changent pas : elles reçoivent toujours un
``LLMProvider`` en paramètre ; seule la façon de l'obtenir change.
"""

import logging
import threading
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
    #: Jeton d'essai du demi-ouvert : consommé par le PREMIER appel autorisé
    #: après expiration du délai, rendu par ``record_success`` /
    #: ``record_failure`` (11). Sans lui, ``allow()`` répondait ``True`` à
    #: TOUS les appels dès la seconde d'expiration (1000/1000 vérifié) : le
    #: « demi-ouvert » n'était pas un essai, c'était une réouverture complète
    #: qui renvoyait toute la charge sur un provider encore en panne.
    half_open_probe_taken: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if self.clock() - self.opened_at >= self.reset_seconds:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        """``True`` si un appel est autorisé — UN SEUL en demi-ouvert.

        Les workers Celery sont multi-threads et le disjoncteur est partagé
        par processus : la décision est prise sous verrou, sinon N threads
        arrivant ensemble à l'expiration prendraient tous « le » jeton.
        """
        with self._lock:
            state = self.state
            if state == "open":
                return False
            if state == "half_open":
                if self.half_open_probe_taken:
                    return False
                self.half_open_probe_taken = True
            return True

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None
            self.half_open_probe_taken = False

    def record_failure(self) -> None:
        with self._lock:
            if self.state == "half_open":
                # L'appel d'essai a échoué : on rouvre pour un cycle complet.
                self.opened_at = self.clock()
                self.half_open_probe_taken = False
                return
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = self.clock()
                self.half_open_probe_taken = False


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
            # ``Exception`` et non ``LLMProviderError`` (14) : un défaut de
            # code du provider (``TypeError``, ``AttributeError``, ``KeyError``
            # sur une réponse inattendue) court-circuitait TOUT le dispositif —
            # pas de bascule sur le fallback, pas de comptage dans le
            # disjoncteur, pas de journalisation — et remontait brut à la
            # tâche. Un provider qui casse est un provider en panne.
            except Exception as exc:
                if breaker is not None:
                    breaker.record_failure()
                if isinstance(exc, LLMProviderError):
                    last_error = exc
                else:
                    last_error = LLMProviderError(
                        f"erreur inattendue du provider {name} (task={task}) : "
                        f"{type(exc).__name__}"
                    )
                    last_error.__cause__ = exc
                logger.warning(
                    "ai_provider_failed provider=%s task=%s error_code=%s exception=%s",
                    name, task, last_error.error_code, type(exc).__name__,
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
    primary = conf.ai_provider or FAKE
    names = [primary]
    fallback = conf.ai_fallback_provider
    if fallback and fallback not in names:
        if fallback == FAKE and primary != FAKE:
            # ``AI_FALLBACK_PROVIDER=fake`` derrière un provider réel : ce
            # n'est pas une dégradation, c'est une PANNE MASQUÉE. Le circuit
            # du primaire s'ouvre et l'utilisateur reçoit des sorties vides
            # présentées comme un résultat. Refusé explicitement (C3, D18).
            logger.error(
                "ai_fallback_fake_refused primary=%s task=%s — un provider factice ne "
                "peut pas servir de secours à un provider réel", primary, task,
            )
        else:
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
        # AUCUN repli sur le factice (C3) : une clé manquante ou un nom de
        # provider erroné doit SUSPENDRE la fonction IA avec un message
        # explicite (D18), pas produire une extraction vide que l'utilisateur
        # prendra pour un résultat. Les tâches traitent déjà ce cas en échec
        # propre (08 §5.1) et le reste de l'application (recherche, scores,
        # facts déterministes) continue de fonctionner.
        logger.error("ai_provider_unavailable task=%s configured=%s", task, names)
        raise ProviderUnavailableError(
            f"aucun provider LLM exploitable (task={task}, configuré : "
            f"{', '.join(names)}) — clé absente ou provider inconnu. Le provider "
            "factice n'est utilisé que si AI_PROVIDER=fake est demandé explicitement."
        )

    return RoutedProvider(
        candidates=tuple(candidates),
        breakers={name: breaker_for(name, conf) for name, _ in candidates},
    )

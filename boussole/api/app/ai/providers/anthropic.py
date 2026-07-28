"""Provider Anthropic — implémentation réelle de ``LLMProvider`` (D08).

⚠️ ACTIVATION CONDITIONNÉE À LA RÉSOLUTION DE Q4 (17-open-questions).
--------------------------------------------------------------------
Q4 (« localisation UE garantie des providers LLM retenus : traitement et
non-entraînement contractuels ») est **NON TRANCHÉE** : l'hypothèse de
travail est « endpoint UE si disponible, sinon DPA + clauses », *à
confirmer*. Q38 la complète (suffisance SCC + TIA si le traitement a lieu
hors UE). Tant que ces points ne sont pas tranchés PAR ÉCRIT :

- ce provider n'est **jamais** actif par défaut (``AI_PROVIDER=fake``) ;
- il ne peut **jamais** s'instancier sans clé configurée
  (:class:`ProviderConfigurationError`) ;
- **aucune conformité n'est affirmée ici**. Le fait que le code minimise les
  données envoyées (D09, `app.ai.scrubbing`, prompts de 08 §4) ne vaut pas
  base légale : la localisation du traitement, les clauses de
  non-entraînement et le DPA relèvent d'une **revue juridique / DPO**, à
  documenter au registre des traitements avant toute activation en
  production. Le présent module ne fait aucune de ces vérifications et ne
  peut pas les faire.

Ce que le module garantit techniquement
---------------------------------------
- sortie JSON contrainte quand l'API l'accepte (``output_config.format``,
  schéma assaini — voir :func:`schema_for_structured_output`), avec
  dégradation automatique vers « prompt + extraction stricte » si l'API
  rejette le schéma ;
- **repair-parse déterministe AVANT de consommer le retry** (08 §5) :
  fences markdown retirées, premier objet JSON équilibré extrait, virgules
  terminales corrigées ;
- timeouts explicites (cibles p95 de 08 §2.2), retries bornés avec backoff,
  ``Retry-After`` respecté sur 429 (08 §5.1, max 3 🟡) ;
- erreurs mappées sur les exceptions de :mod:`app.ai.providers.base`, que
  les tâches traitent déjà comme un échec propre ;
- journalisation ``ai_calls`` de CHAQUE appel — métadonnées seulement, ni
  prompt ni réponse (11 §3, D09).
"""

import json
import logging
import re
import time
import uuid
from collections.abc import Callable, Mapping
from typing import Any

import anthropic

from app.ai.calls import (
    AiCallRecord,
    CallJournal,
    DatabaseJournal,
    current_ai_user,
    prompt_version_for,
)
from app.ai.providers.base import (
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    ProviderConfigurationError,
)
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

PROVIDER_NAME = "anthropic"

#: Cibles p95 par tâche (08 §2.2) utilisées comme timeout d'appel quand
#: ``AI_TIMEOUT_SECONDS`` n'est pas fixé. Une tâche inconnue prend
#: :data:`DEFAULT_TIMEOUT_SECONDS`.
TASK_TIMEOUTS: dict[str, float] = {
    "extract_cv": 30.0,
    "extract_job": 20.0,
    "explain_match": 4.0,
    "generate_email": 10.0,
    "generate_letter": 15.0,
    "tailor_cv": 15.0,
    "optimize_cv": 15.0,
}
DEFAULT_TIMEOUT_SECONDS = 30.0

#: Consigne de sortie ajoutée au prompt quand la contrainte de schéma n'est
#: pas disponible côté API (chemin « prompt + extraction stricte »).
_JSON_ONLY_SUFFIX = (
    "\n\nRéponds UNIQUEMENT avec un objet JSON valide conforme au schéma "
    "demandé. Aucun texte avant ou après, aucun bloc de code, aucun "
    "commentaire."
)

#: Consigne de correction jouée sur le retry quand la sortie précédente
#: n'était ni du JSON valide ni réparable. Ne recopie RIEN de la sortie
#: (11 §3) : seule la nature du défaut est indiquée.
_REPAIR_SUFFIX = (
    "\n\nTa précédente réponse n'était pas un objet JSON exploitable. "
    "Renvoie exclusivement l'objet JSON demandé, sans aucun autre texte."
)

#: Mots-clés JSON Schema non supportés par la sortie structurée de l'API :
#: retirés de la copie envoyée. Ils restent appliqués côté application par
#: la validation Pydantic de la tâche — rien n'est relâché.
_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "minLength",
        "maxLength",
        "pattern",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minProperties",
        "maxProperties",
        "format",
        "default",
        "examples",
    }
)

#: Fragments d'un 400 qui signalent un schéma refusé (et non une requête
#: invalide pour une autre raison) : on dégrade alors le mode de sortie.
_SCHEMA_REJECTION_MARKERS = ("output_config", "json_schema", "schema", "output_format")

#: Durée de la dégradation « structured outputs off », PAR TÂCHE 🟡 (M10).
#:
#: Le drapeau était porté par l'instance — mémorisée une seule fois par
#: processus : un unique 400 sur le schéma d'``extract_cv`` désactivait la
#: sortie contrainte pour ``extract_job``, ``explain_match`` et toutes les
#: ``generate_*``, définitivement, sans réactivation ni trace. Or le rejet
#: dépend du SCHÉMA, donc de la tâche : rien ne justifie de propager la
#: dégradation, ni de la rendre permanente (un schéma corrigé, ou une API qui
#: évolue, doivent pouvoir reprendre). 15 minutes : assez long pour ne pas
#: rejouer le 400 à chaque appel, assez court pour se réarmer tout seul.
STRUCTURED_OUTPUT_REARM_SECONDS = 900.0


def _text_of(message: Any) -> str:
    """Concatène les blocs texte d'une réponse Messages API."""
    parts: list[str] = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(str(getattr(block, "text", "")))
    return "".join(parts)


def schema_for_structured_output(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Copie du JSON Schema acceptable par ``output_config.format``.

    Les schémas des tâches sont générés par Pydantic et portent des
    contraintes que la sortie structurée ne supporte pas (``pattern``,
    ``maxLength``, bornes numériques…). On les retire de la COPIE envoyée à
    l'API et on ferme chaque objet (``additionalProperties: false``,
    ``required`` complet) ; la validation stricte reste faite côté
    application par le modèle Pydantic de la tâche.
    """

    def _clean(node: Any) -> Any:
        if isinstance(node, list):
            return [_clean(item) for item in node]
        if not isinstance(node, dict):
            return node
        cleaned = {
            key: _clean(value)
            for key, value in node.items()
            if key not in _UNSUPPORTED_SCHEMA_KEYS
        }
        properties = cleaned.get("properties")
        if isinstance(properties, dict):
            cleaned["type"] = "object"
            cleaned["additionalProperties"] = False
            # Sortie structurée : tous les champs sont émis ; les champs
            # optionnels du modèle Pydantic acceptent déjà ``null``.
            cleaned["required"] = list(properties)
        return cleaned

    result = _clean(dict(schema))
    return result if isinstance(result, dict) else {}


def _retry_after_seconds(error: anthropic.APIStatusError) -> float | None:
    """Valeur de l'en-tête ``Retry-After`` en secondes (``None`` si absente)."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        value = float(str(raw).strip())
    except ValueError:
        # Forme date HTTP : non gérée volontairement (backoff normal).
        return None
    return value if value >= 0 else None


def repair_json(raw: str) -> dict[str, Any] | None:
    """Repair-parse DÉTERMINISTE (08 §5) — aucun appel LLM.

    Trois corrections, dans cet ordre : retrait des fences markdown,
    extraction du **premier objet JSON équilibré** (chaînes et échappements
    respectés), suppression des virgules terminales. Retourne ``None`` si
    rien d'exploitable n'en sort.
    """
    text = raw.strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()

    candidate = _first_balanced_object(text)
    if candidate is None:
        return None
    for attempt in (candidate, _strip_trailing_commas(candidate)):
        try:
            parsed = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _strip_trailing_commas(text: str) -> str:
    """Retire les virgules terminales — **hors chaînes JSON** (M9).

    L'implémentation précédente était un ``re.sub(r",\\s*([}\\]])", r"\\1")``
    aveugle au contexte : appliqué à ``{"closing": "Cordialement, ] Jean"}``,
    il produisait ``"Cordialement] Jean"``. Le résultat restait un JSON
    parfaitement valide, passait la validation Pydantic, était persisté et
    servi à l'utilisateur — une corruption SILENCIEUSE du contenu généré, sur
    des textes (lettres de motivation, e-mails) où « , ] » et « , } » ne sont
    pas rares. Même automate que :func:`_first_balanced_object` : ce qui est
    entre guillemets n'est jamais touché.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            out.append(char)
            continue
        if char == ",":
            # Virgule terminale ⇔ le prochain caractère STRUCTUREL est une
            # fermeture. Les espaces intermédiaires sont conservés tels quels.
            rest = text[index + 1 :].lstrip()
            if rest[:1] in ("}", "]"):
                continue  # la virgule est supprimée, pas les espaces
        out.append(char)
    return "".join(out)


def _first_balanced_object(text: str) -> str | None:
    """Premier objet ``{…}`` équilibré du texte, chaînes JSON respectées."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


class AnthropicProvider:
    """``LLMProvider`` réel — SDK ``anthropic``, sorties JSON contraintes.

    ``client`` est injectable : les tests fournissent un client dont le
    transport httpx est simulé (aucun appel réseau).
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: anthropic.Anthropic | None = None,
        journal: CallJournal | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings or get_settings()
        if client is None:
            api_key = self._settings.anthropic_api_key
            if not api_key:
                # Un provider réel ne peut pas exister sans clé (§5 du
                # périmètre) : l'erreur est levée AVANT tout appel réseau.
                raise ProviderConfigurationError(
                    "AI_PROVIDER=anthropic sans ANTHROPIC_API_KEY configurée"
                )
            # ``max_retries=0`` : la politique de retry (bornée, Retry-After
            # respecté, journalisée) est la nôtre — pas celle du SDK.
            client = anthropic.Anthropic(api_key=api_key, max_retries=0)
        self._client = client
        self._journal: CallJournal = journal or DatabaseJournal()
        self._sleep = sleeper
        self._clock = clock
        #: Dégradation « structured outputs off » PAR TÂCHE et TEMPORAIRE
        #: (M10) : tâche → instant de réarmement. Absent = mode contraint
        #: actif. Voir :data:`STRUCTURED_OUTPUT_REARM_SECONDS`.
        self._structured_disabled_until: dict[str, float] = {}

    # ------------------------------------------------------------ interface

    def complete_json(
        self,
        task: str,
        prompt: str,
        schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Exécute une tâche typée et retourne le JSON brut (non validé)."""
        started = self._clock()
        model = self.model_for(task)
        user_id = current_ai_user()
        input_tokens = 0
        output_tokens = 0
        repaired = False
        attempts = max(1, self._settings.ai_max_retries)
        current_prompt = prompt

        try:
            for attempt in range(attempts):
                message = self._call_api(task, current_prompt, schema, model)
                usage = getattr(message, "usage", None)
                input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
                output_tokens += int(getattr(usage, "output_tokens", 0) or 0)

                text = _text_of(message)
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    self._record(
                        task, model, user_id,
                        status="schema_retry" if (repaired or attempt) else "success",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        started=started,
                    )
                    return parsed

                # Repair-parse AVANT de consommer le retry (08 §5).
                salvaged = repair_json(text)
                if salvaged is not None:
                    repaired = True
                    logger.warning("ai_output_repaired task=%s attempt=%d", task, attempt + 1)
                    self._record(
                        task, model, user_id,
                        status="schema_retry",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        started=started,
                    )
                    return salvaged

                logger.warning("ai_output_not_json task=%s attempt=%d", task, attempt + 1)
                repaired = True
                current_prompt = prompt + _REPAIR_SUFFIX

            raise LLMResponseError(
                f"sortie non JSON et non réparable après {attempts} tentatives (task={task})"
            )
        except LLMProviderError as exc:
            self._record(
                task, model, user_id,
                status="failed",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                started=started,
                error_code=exc.error_code,
            )
            raise

    def model_for(self, task: str) -> str:
        """Modèle configuré pour ``task`` (défauts 08 §2.1 🟡)."""
        configured = getattr(self._settings, f"ai_model_{task}", "")
        return str(configured) if configured else self._settings.ai_model_default

    def timeout_for(self, task: str) -> float:
        """Timeout explicite de l'appel (cibles p95 08 §2.2 par défaut)."""
        override = self._settings.ai_timeout_seconds
        if override is not None:
            return float(override)
        return TASK_TIMEOUTS.get(task, DEFAULT_TIMEOUT_SECONDS)

    def structured_outputs_enabled(self, task: str) -> bool:
        """Sortie contrainte active pour ``task`` ? (M10 — par tâche, réarmée)."""
        if not self._settings.ai_structured_outputs:
            return False
        until = self._structured_disabled_until.get(task)
        if until is None:
            return True
        if self._clock() >= until:
            del self._structured_disabled_until[task]
            logger.info("ai_structured_output_rearmed task=%s", task)
            return True
        return False

    def _disable_structured_outputs(self, task: str) -> None:
        """Dégrade ``task`` (et elle seule) vers « prompt + extraction »."""
        self._structured_disabled_until[task] = self._clock() + STRUCTURED_OUTPUT_REARM_SECONDS
        logger.warning(
            "ai_structured_output_disabled task=%s rearm_in=%.0fs",
            task, STRUCTURED_OUTPUT_REARM_SECONDS,
        )

    # ------------------------------------------------------------- interne

    def _call_api(
        self,
        task: str,
        prompt: str,
        schema: Mapping[str, Any],
        model: str,
    ) -> Any:
        """Un appel Messages API, retries provider bornés (réseau/429/5xx)."""
        attempts = max(1, self._settings.ai_max_retries)
        last_error: LLMProviderError = LLMProviderError(f"appel provider impossible ({task})")
        attempt = 0
        while attempt < attempts:
            try:
                return self._send(task, prompt, schema, model)
            except anthropic.APITimeoutError as exc:
                last_error = LLMTimeoutError(f"timeout provider (task={task})")
                self._wait_before_retry(attempt, attempts, exc=exc, task=task)
            except anthropic.RateLimitError as exc:
                last_error = LLMRateLimitError(f"429 provider (task={task})")
                delay = _retry_after_seconds(exc)
                if delay is not None and delay > self._settings.ai_retry_after_max_seconds:
                    # Attente annoncée trop longue : échec propre immédiat
                    # plutôt qu'un worker bloqué (D18).
                    logger.warning("ai_retry_after_too_long task=%s delay=%.1f", task, delay)
                    raise last_error from exc
                self._wait_before_retry(
                    attempt, attempts, exc=exc, task=task, retry_after=delay
                )
            except (anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
                last_error = LLMProviderError(f"erreur provider (task={task})")
                self._wait_before_retry(attempt, attempts, exc=exc, task=task)
            except anthropic.BadRequestError as exc:
                if self.structured_outputs_enabled(task) and self._is_schema_rejection(exc):
                    # Dégradation : l'API refuse le schéma contraint → on
                    # repasse en « prompt + extraction stricte » POUR CETTE
                    # TÂCHE (M10), temporairement. Ne consomme PAS de
                    # tentative (le compteur n'avance pas).
                    self._disable_structured_outputs(task)
                    continue
                raise LLMProviderError(f"requête refusée par le provider (task={task})") from exc
            except anthropic.APIStatusError as exc:
                # 401/403 et autres erreurs non transitoires : échec immédiat.
                raise LLMProviderError(
                    f"erreur provider HTTP {exc.status_code} (task={task})"
                ) from exc
            attempt += 1
        raise last_error

    def _send(
        self,
        task: str,
        prompt: str,
        schema: Mapping[str, Any],
        model: str,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": self._settings.ai_max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "timeout": self.timeout_for(task),
        }
        if self.structured_outputs_enabled(task) and schema:
            kwargs["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": schema_for_structured_output(schema),
                }
            }
        else:
            kwargs["messages"] = [{"role": "user", "content": prompt + _JSON_ONLY_SUFFIX}]
        return self._client.messages.create(**kwargs)

    @staticmethod
    def _is_schema_rejection(error: anthropic.BadRequestError) -> bool:
        message = str(error).lower()
        return any(marker in message for marker in _SCHEMA_REJECTION_MARKERS)

    def _wait_before_retry(
        self,
        attempt: int,
        attempts: int,
        *,
        exc: Exception,
        task: str,
        retry_after: float | None = None,
    ) -> None:
        """Backoff — **jamais après la dernière tentative** (15).

        ``_backoff`` était appelé à chaque échec, y compris sur l'ultime
        essai : l'appel dormait jusqu'à 8 s (ou toute la valeur d'un
        ``Retry-After``) puis sortait de la boucle pour lever de toute façon.
        Latence pure, prise sur le budget p95 de la tâche et, côté API,
        sur un thread du pool.
        """
        if attempt + 1 >= attempts:
            logger.warning(
                "ai_provider_giving_up task=%s attempts=%d error=%s",
                task, attempts, type(exc).__name__,
            )
            return
        self._backoff(attempt, exc=exc, task=task, retry_after=retry_after)

    def _backoff(
        self,
        attempt: int,
        *,
        exc: Exception,
        task: str,
        retry_after: float | None = None,
    ) -> None:
        """Attente avant nouvelle tentative — ``Retry-After`` prioritaire."""
        delay = retry_after if retry_after is not None else min(8.0, 0.5 * (2**attempt))
        logger.warning(
            "ai_provider_retry task=%s attempt=%d delay=%.2f error=%s",
            task, attempt + 1, delay, type(exc).__name__,
        )
        if delay > 0:
            self._sleep(delay)

    def _record(
        self,
        task: str,
        model: str,
        user_id: uuid.UUID | None,
        *,
        status: str,
        input_tokens: int,
        output_tokens: int,
        started: float,
        error_code: str | None = None,
    ) -> None:
        """Journalise l'appel — métadonnées uniquement (11 §3).

        La construction du ``AiCallRecord`` peut échouer (tâche hors du
        vocabulaire de l'enum SQL, M6) : le défaut est signalé BRUYAMMENT
        mais ne fait jamais échouer l'appel IA lui-même (D18).
        """
        try:
            record = AiCallRecord(
                task=task,
                prompt_version=prompt_version_for(task),
                model=model,
                status=status,
                user_id=user_id,
                input_tokens=input_tokens or None,
                output_tokens=output_tokens or None,
                latency_ms=int((self._clock() - started) * 1000),
                error_code=error_code,
            )
        except ValueError:
            logger.error("ai_call_record_rejected task=%s status=%s", task, status)
            return
        self._journal.record(record)

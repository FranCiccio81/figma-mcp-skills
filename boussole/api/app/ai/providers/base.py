"""Interface ``LLMProvider`` (D08) — interface seulement au M2.

Toute sortie de provider est un ``dict`` JSON destiné à être validé
Pydantic contre ``ai-output-schemas.json`` par la tâche appelante ; en cas
d'échec de validation : 1 retry avec le message d'erreur, puis
repair-parse, puis échec propre (D08). Les providers réels (Anthropic par
défaut 🟡 + second provider de fallback, circuit breaker D18) arrivent en
M3+ ; chaque appel sera journalisé (``ai_calls`` : prompt_version, model,
tokens, latence).
"""

from collections.abc import Mapping
from typing import Any, Protocol


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

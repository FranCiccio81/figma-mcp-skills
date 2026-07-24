"""Provider factice déterministe — tests et défaut M2 (D08, D22).

Aucun réseau, aucune donnée réelle : retourne des sorties canned par
tâche. Par défaut, la sortie ``extract_job`` est « vide mais valide »
(aucun attribut extrait) : l'offre est publiée avec les seuls attributs
déterministes (07 §5.2 — échec propre équivalent).
"""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

_DEFAULTS: dict[str, dict[str, Any]] = {
    "extract_job": {
        "skills_required": [],
        "skills_nice": [],
        "languages": [],
        "warnings": ["fake-provider: aucune extraction LLM (M2)"],
    },
}


class FakeProvider:
    """Implémentation déterministe de ``LLMProvider``.

    ``canned`` permet aux tests d'injecter une sortie par tâche ;
    la même entrée produit toujours la même sortie.
    """

    def __init__(self, canned: dict[str, dict[str, Any]] | None = None) -> None:
        self._canned = canned or {}
        self.calls: list[tuple[str, str]] = []  # (task, prompt) — introspection tests

    def complete_json(
        self,
        task: str,
        prompt: str,
        schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.calls.append((task, prompt))
        payload = self._canned.get(task) or _DEFAULTS.get(task)
        if payload is None:
            raise ValueError(f"FakeProvider: pas de sortie canned pour la tâche {task!r}")
        return deepcopy(payload)

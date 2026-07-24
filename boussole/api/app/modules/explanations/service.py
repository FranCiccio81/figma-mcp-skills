"""Logique métier du module explanations (E8, D14) — reformulation LLM.

Deux couches (D14) :
- couche 1 déterministe : les ``explanation_facts`` sont émis par le moteur
  et stockés avec le ``match_result`` (module matching) ;
- couche 2 (ici) : reformulation en langage naturel via ``LLMProvider`` —
  l'entrée du prompt est EXCLUSIVEMENT les facts (jamais l'offre brute), la
  sortie est validée Pydantic contre ``ai-output-schemas.json#match_explanation``
  (1 retry avec le message d'erreur, D08), puis contrôlée : aucun nombre de
  la sortie ne doit être absent des facts (diff des valeurs numériques,
  06 §6). Tout échec (validation après retry, nombre étranger) → 502
  ``explanation_generation_failed`` 🟡 (échec propre, jamais de contenu
  divergent servi).

Cache ``match_explanations`` par (profil, offre, scoring_version,
prompt_version) — invalidé par cascade quand le ``match_result`` est
supprimé (hook « preferences_changed », purge).

Provider : :class:`FakeProvider` par défaut au M3 🟡 (D08, D22 — provider
réel branché avec la couche IA complète), avec une sortie canned sans aucun
chiffre (donc toujours conforme au contrôle numérique).
"""

import json
import logging
import re
import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.providers.base import LLMProvider
from app.core.problems import Problem
from app.modules.explanations.repository import ExplanationsRepository
from app.modules.explanations.schemas import MatchExplanationOut
from app.modules.matching.service import MatchingService

logger = logging.getLogger(__name__)

#: Versionnement des prompts (D08) — clé de cache avec scoring_version.
PROMPT_VERSION = "match_explanation/1.0.0"

#: Sortie canned du provider factice (M3 🟡) : déterministe et SANS AUCUN
#: chiffre — elle passe le contrôle numérique quels que soient les facts.
FAKE_EXPLANATION: dict[str, Any] = {
    "summary": (
        "Synthèse générée à partir des faits du moteur de matching : points "
        "forts, écarts et incertitudes sont détaillés ci-dessous."
    ),
    "strengths": [],
    "gaps": [],
    "uncertainties": [],
    "blocking_notes": [],
}

_Item = Annotated[str, Field(max_length=250)]


class MatchExplanationPayload(BaseModel):
    """Sortie validée du schéma ``match_explanation`` (ai-output-schemas.json)."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=400)
    strengths: list[_Item] = Field(max_length=5)
    gaps: list[_Item] = Field(max_length=5)
    uncertainties: list[_Item] = Field(max_length=5)
    blocking_notes: list[_Item] = Field(default_factory=list, max_length=3)


_PROMPT_TEMPLATE = (
    "Tu reformules en français, pour un candidat, les faits d'explication "
    "d'un score de matching.\n"
    "Réponds UNIQUEMENT avec un JSON conforme au schéma match_explanation.\n"
    "INTERDICTION ABSOLUE d'introduire un chiffre, un nom ou un fait absent "
    "des faits ci-dessous (contrôle automatique post-génération).\n"
    "Les critères bloquants sont toujours mentionnés en premier.\n\n"
    "--- FAITS (seule source autorisée) ---\n{facts}\n--- FIN FAITS ---"
)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers_in_text(text: str) -> set[float]:
    """Valeurs numériques d'un texte (virgule décimale acceptée)."""
    return {float(match.replace(",", ".")) for match in _NUMBER_RE.findall(text)}


def _collect_numbers(value: object) -> set[float]:
    """Toutes les valeurs numériques d'une structure JSON (nombres + chaînes)."""
    numbers: set[float] = set()
    if isinstance(value, bool):
        return numbers
    if isinstance(value, (int, float)):
        numbers.add(float(value))
    elif isinstance(value, str):
        numbers |= _numbers_in_text(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            numbers |= _numbers_in_text(str(key))
            numbers |= _collect_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            numbers |= _collect_numbers(item)
    return numbers


def _generation_failed(detail: str) -> Problem:
    return Problem(
        status=502,
        code="explanation_generation_failed",
        title="Échec de génération de l'explication",
        detail=detail,
    )


class ExplanationsService:
    def __init__(
        self,
        matching: MatchingService,
        repository: ExplanationsRepository,
        provider: LLMProvider,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self._matching = matching
        self._repository = repository
        self._provider = provider
        self._prompt_version = prompt_version

    async def explain(self, user_id: uuid.UUID, job_id: uuid.UUID) -> MatchExplanationOut:
        """POST /jobs/{id}/explanation — reformulation D14 avec cache.

        Propage le 409 ``profile_not_validated`` et le 404 du module matching
        (les facts viennent du match_result — jamais de l'offre brute).
        """
        match = await self._matching.get_match_data(user_id, job_id)

        cached = await self._repository.get(
            match.profile_id, match.job_id, match.scoring_version, self._prompt_version
        )
        if cached is not None:
            return self._to_out(cached)

        content = self._generate(match.explanation_facts)
        await self._repository.put(
            match.profile_id,
            match.job_id,
            match.scoring_version,
            self._prompt_version,
            content,
        )
        return self._to_out(content)

    # ------------------------------------------------------------ génération

    def _generate(self, facts: dict[str, Any]) -> dict[str, Any]:
        """Appel provider + validation stricte + contrôle numérique (06 §6)."""
        prompt = _PROMPT_TEMPLATE.format(
            facts=json.dumps(facts, ensure_ascii=False, sort_keys=True)
        )
        schema: dict[str, Any] = MatchExplanationPayload.model_json_schema()

        payload: MatchExplanationPayload | None = None
        last_error: ValidationError | None = None
        for attempt in range(2):  # 1 retry avec le message d'erreur (D08)
            current_prompt = prompt
            if last_error is not None:
                current_prompt = (
                    f"{prompt}\n\nTa précédente réponse était invalide :\n{last_error}\n"
                    "Corrige et renvoie un JSON strictement conforme."
                )
            raw = self._provider.complete_json(
                "match_explanation", current_prompt, schema
            )
            try:
                payload = MatchExplanationPayload.model_validate(raw)
                break
            except ValidationError as exc:
                last_error = exc
                logger.warning("match_explanation_invalid attempt=%d", attempt + 1)
        if payload is None:
            raise _generation_failed(
                "La sortie du modèle est restée non conforme au schéma après retry."
            )

        content = payload.model_dump()
        foreign = sorted(_collect_numbers(content) - _collect_numbers(facts))
        if foreign:
            # Diff numérique (06 §6) : un chiffre absent des facts = divergence
            # potentielle score/explication → échec propre, rien n'est servi.
            logger.warning("match_explanation_foreign_numbers %s", foreign)
            raise _generation_failed(
                "L'explication générée contient des valeurs numériques absentes "
                f"des faits du moteur : {foreign}."
            )
        return content

    def _to_out(self, content: dict[str, Any]) -> MatchExplanationOut:
        return MatchExplanationOut(prompt_version=self._prompt_version, **content)

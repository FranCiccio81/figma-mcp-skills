"""Schémas Pydantic du module explanations — conformes à openapi.yaml.

``MatchExplanation`` du contrat : contenu validé du schéma
``match_explanation`` (ai-output-schemas.json) + ``prompt_version`` (posé par
le service, jamais par le LLM).
"""

from pydantic import BaseModel, Field


class MatchExplanationOut(BaseModel):
    """Réponse de POST /jobs/{id}/explanation — schéma MatchExplanation."""

    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    blocking_notes: list[str] = Field(default_factory=list)
    prompt_version: str

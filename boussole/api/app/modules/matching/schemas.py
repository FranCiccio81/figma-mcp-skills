"""Schémas Pydantic du module matching — conformes à openapi.yaml (MatchResult).

``unknown_dimensions[].reason`` suit le vocabulaire du contrat
(``job_not_provided`` / ``profile_not_provided`` /
``low_extraction_confidence``) : les raisons internes du moteur y sont
mappées par le service (🟡 ``unconvertible_value`` — devise non supportée —
est assimilée à ``low_extraction_confidence``, le contrat n'ayant pas de
code dédié).
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

UnknownReason = Literal[
    "job_not_provided",
    "profile_not_provided",
    "low_extraction_confidence",
    #: Limite de NOTRE outil, pas des données : le critère n'a pas pu être
    #: évalué. Ne jamais replier ce cas sur une raison qui met en cause le
    #: profil ou l'offre.
    "unavailable",
]


class BlockingCriterionOut(BaseModel):
    """Critère rédhibitoire — l'offre reste visible, badgée (06 §1)."""

    code: str
    label: str


class UnknownDimensionOut(BaseModel):
    """Dimension non évaluable (donnée absente ou extraction incertaine)."""

    dimension: str
    reason: UnknownReason
    label: str


class DimensionOut(BaseModel):
    """Détail par dimension — ``subscore`` null quand la dimension est inconnue."""

    dimension: str
    subscore: float | None = None
    weight: float
    known: bool
    details: dict[str, Any] = Field(default_factory=dict)


class MatchResultOut(BaseModel):
    """Réponse de GET /jobs/{id}/match — schéma MatchResult d'openapi.yaml."""

    job_id: uuid.UUID
    profile_version: int
    scoring_version: str
    score: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    low_data: bool
    blocking_criteria: list[BlockingCriterionOut] = Field(default_factory=list)
    unknown_dimensions: list[UnknownDimensionOut] = Field(default_factory=list)
    dimensions: list[DimensionOut] = Field(default_factory=list)

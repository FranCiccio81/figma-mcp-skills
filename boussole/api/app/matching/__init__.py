"""Moteur de matching déterministe de Boussole (D02, jalon M3).

Package de calcul PUR : aucune dépendance vers `app.modules.*`, `app.ai`,
SQLAlchemy ou httpx. Le moteur reçoit un `CandidateInput` et un `JobInput`
déjà normalisés et rend un `MatchResult` (voir `06-matching-specification.md`).

Point d'entrée : :func:`compute_match`.
"""

from app.matching.config import ConfigError, ScoringConfig, get_config
from app.matching.engine import compute_match
from app.matching.models import (
    BlockingCriterion,
    CandidateInput,
    CandidateLocation,
    Confident,
    DimensionScore,
    ExplanationFact,
    ExplanationFacts,
    JobInput,
    JobLanguage,
    JobLocation,
    JobSkill,
    MatchResult,
    RemotePolicy,
    RemotePreference,
    UnknownDimension,
    Vector,
)

__all__ = [
    "BlockingCriterion",
    "CandidateInput",
    "CandidateLocation",
    "Confident",
    "ConfigError",
    "DimensionScore",
    "ExplanationFact",
    "ExplanationFacts",
    "JobInput",
    "JobLanguage",
    "JobLocation",
    "JobSkill",
    "MatchResult",
    "RemotePolicy",
    "RemotePreference",
    "ScoringConfig",
    "UnknownDimension",
    "Vector",
    "compute_match",
    "get_config",
]

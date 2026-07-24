"""Entrées et sorties du moteur de matching (D02 — calcul pur).

Le moteur ne lit ni base ni réseau : il reçoit des dataclasses déjà
normalisées en amont (labels canoniques de la taxonomie, niveaux CECRL,
lat/lon géocodées, salaires numériques) et rend un ``MatchResult``.

Convention de confiance : côté candidat, les données proviennent d'un profil
validé (``user_input`` / ``user_confirmed``) → fiabilité 1,0. Côté offre,
chaque champ extrait porte sa confiance ; sous
``extraction_confidence_floor`` le champ est traité comme INCONNU (k=0),
jamais comme un fait.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "BlockingCriterion",
    "CandidateInput",
    "CandidateLocation",
    "Confident",
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
    "UnknownDimension",
    "Vector",
]

#: Embedding : vecteur dense de flottants (fourni par l'amont, jamais calculé ici).
Vector = tuple[float, ...]

RemotePolicy = Literal["full_remote", "hybrid", "onsite"]
RemotePreference = Literal["required", "preferred", "indifferent", "onsite_preferred"]


@dataclass(frozen=True)
class Confident:
    """Valeur extraite de l'offre, accompagnée de sa confiance d'extraction."""

    value: str
    confidence: float = 1.0


@dataclass(frozen=True)
class CandidateLocation:
    """Lieu accepté par le candidat, avec rayon en km (défaut : config)."""

    lat: float
    lon: float
    radius_km: float | None = None


@dataclass(frozen=True)
class JobLocation:
    """Lieu du poste, géocodé en amont."""

    lat: float
    lon: float


@dataclass(frozen=True)
class JobSkill:
    """Compétence extraite de l'offre (label canonique + confiance par item)."""

    label: str
    confidence: float = 1.0


@dataclass(frozen=True)
class JobLanguage:
    """Exigence de langue de l'offre (code ISO + niveau CECRL + confiance)."""

    code: str
    level: str
    confidence: float = 1.0


@dataclass(frozen=True)
class CandidateInput:
    """Profil candidat validé, déjà normalisé (fiabilité 1,0 côté candidat)."""

    skills: tuple[str, ...] = ()
    #: Embeddings des libellés de compétences du profil (optionnels — sans eux,
    #: le crédit « proche » 0,5 est désactivé : match exact uniquement 🟡).
    skill_embeddings: Mapping[str, Vector] = field(default_factory=dict)
    #: Embeddings des intitulés cibles (préférences, sinon 2 derniers intitulés occupés).
    target_titles_embeddings: tuple[Vector, ...] = ()
    seniority: str | None = None
    total_experience_years: float | None = None
    sectors_preferred: frozenset[str] = frozenset()
    sectors_excluded: frozenset[str] = frozenset()
    sectors_experienced: frozenset[str] = frozenset()
    #: secteur → parent taxonomique (pour le score « adjacent »).
    sector_parents: Mapping[str, str] = field(default_factory=dict)
    locations: tuple[CandidateLocation, ...] = ()
    remote_pref: RemotePreference | None = None
    #: code langue → niveau CECRL (A1…C2 ou « native »).
    languages: Mapping[str, str] = field(default_factory=dict)
    contract_types: frozenset[str] = frozenset()
    contract_strict: bool = False
    salary_expected_min: float | None = None
    salary_expected_max: float | None = None
    salary_min_strict: float | None = None
    target_companies: frozenset[str] = frozenset()
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobInput:
    """Offre normalisée ; chaque champ extrait porte sa confiance."""

    skills_required: tuple[JobSkill, ...] = ()
    skills_nice: tuple[JobSkill, ...] = ()
    #: Embeddings des libellés de compétences de l'offre (optionnels).
    skill_embeddings: Mapping[str, Vector] = field(default_factory=dict)
    #: Embedding « intitulé + 1er paragraphe » (optionnel — absent → k=0).
    title_embedding: Vector | None = None
    seniority: Confident | None = None
    experience_min: float | None = None
    experience_max: float | None = None
    experience_confidence: float = 1.0
    sector: Confident | None = None
    sector_parent: str | None = None
    locations: tuple[JobLocation, ...] = ()
    location_confidence: float = 1.0
    remote: Confident | None = None
    languages_required: tuple[JobLanguage, ...] = ()
    contract: Confident | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: Literal["year", "month"] = "year"
    salary_currency: str = "EUR"
    salary_confidence: float = 1.0
    company_name: str | None = None
    description_text: str | None = None


# --------------------------------------------------------------------- sorties


@dataclass(frozen=True)
class BlockingCriterion:
    """Critère rédhibitoire détecté (l'offre reste visible, badgée)."""

    code: str
    label: str


@dataclass(frozen=True)
class UnknownDimension:
    """Dimension non évaluable (donnée absente ou extraction trop incertaine)."""

    dimension: str
    reason: str
    label: str


@dataclass(frozen=True)
class DimensionScore:
    """Détail par dimension : sous-score, poids, statut, valeurs comparées."""

    dimension: str
    subscore: float | None
    weight: float
    known: bool
    details: Mapping[str, object]


@dataclass(frozen=True)
class ExplanationFact:
    """Fait structuré pour l'explication (06 §6) — jamais de texte généré ici."""

    kind: Literal["blocking", "strength", "gap", "uncertain"]
    dimension: str
    label: str
    data: Mapping[str, object]


@dataclass(frozen=True)
class ExplanationFacts:
    """Faits d'explication, bloquants toujours en premier (06 §6)."""

    blocking: tuple[ExplanationFact, ...]
    strengths: tuple[ExplanationFact, ...]
    gaps: tuple[ExplanationFact, ...]
    uncertain: tuple[ExplanationFact, ...]


@dataclass(frozen=True)
class MatchResult:
    """Résultat complet pour une paire (profil, offre)."""

    score: int
    confidence: int
    low_data: bool
    blocking_criteria: tuple[BlockingCriterion, ...]
    unknown_dimensions: tuple[UnknownDimension, ...]
    dimension_scores: tuple[DimensionScore, ...]
    explanation_facts: ExplanationFacts
    scoring_version: str

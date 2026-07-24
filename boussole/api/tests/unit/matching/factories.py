"""Constructeurs partagés des tests du moteur de matching.

`perfect_candidate`/`perfect_job` : paire à 12 dimensions connues, s=1, q=1
(UM-01). `um02_candidate`/`um02_job` : scénario de renormalisation UM-02
(connues : skills_required s=0,8 w25 ; title s=1,0 w15 ; location s=1,0 w8).
"""

from __future__ import annotations

import math

from app.matching import (
    CandidateInput,
    CandidateLocation,
    Confident,
    DimensionScore,
    JobInput,
    JobLanguage,
    JobLocation,
    JobSkill,
    MatchResult,
    get_config,
)
from app.matching.dimensions import DimensionOutcome, score_dimension
from app.matching.similarity import EARTH_RADIUS_KM

PARIS_LAT, PARIS_LON = 48.8566, 2.3522
E1 = (1.0, 0.0)


def lat_offset_deg(km: float) -> float:
    """Décalage de latitude (même longitude) correspondant à `km` kilomètres."""
    return math.degrees(km / EARTH_RADIUS_KM)


def vector_with_cosine(similarity: float) -> tuple[float, float]:
    """Vecteur unitaire dont le cosinus avec E1=(1,0) vaut `similarity`."""
    return (similarity, math.sqrt(1.0 - similarity * similarity))


def outcome(name: str, candidate: CandidateInput, job: JobInput) -> DimensionOutcome:
    """Calcule une seule dimension avec la config réelle."""
    config = get_config()
    return score_dimension(config.dimension(name), config, candidate, job)


def dim(result: MatchResult, name: str) -> DimensionScore:
    """Extrait le détail d'une dimension d'un MatchResult."""
    return next(score for score in result.dimension_scores if score.dimension == name)


def perfect_candidate() -> CandidateInput:
    return CandidateInput(
        skills=("python", "fastapi", "docker"),
        target_titles_embeddings=(E1,),
        seniority="senior",
        total_experience_years=5.0,
        sectors_preferred=frozenset({"tech"}),
        locations=(CandidateLocation(PARIS_LAT, PARIS_LON, 30.0),),
        remote_pref="indifferent",
        languages={"fr": "native", "en": "C1"},
        contract_types=frozenset({"cdi"}),
        salary_expected_min=45_000.0,
        salary_expected_max=55_000.0,
        target_companies=frozenset({"Acme"}),
        keywords=("impact",),
    )


def perfect_job() -> JobInput:
    return JobInput(
        skills_required=(JobSkill("python"), JobSkill("fastapi")),
        skills_nice=(JobSkill("docker"),),
        title_embedding=E1,
        seniority=Confident("senior"),
        experience_min=3.0,
        experience_max=8.0,
        sector=Confident("tech"),
        locations=(JobLocation(PARIS_LAT, PARIS_LON),),
        remote=Confident("hybrid"),
        languages_required=(JobLanguage("fr", "C1"),),
        contract=Confident("cdi"),
        salary_min=40_000.0,
        salary_max=60_000.0,
        company_name="Acme",
        description_text="Une mission à impact au sein d'une équipe produit.",
    )


def um02_candidate() -> CandidateInput:
    return CandidateInput(
        skills=("python", "fastapi", "postgresql", "docker"),
        target_titles_embeddings=(E1,),
        locations=(CandidateLocation(PARIS_LAT, PARIS_LON, 30.0),),
    )


def um02_job(skill_confidence: float = 1.0, location_confidence: float = 1.0) -> JobInput:
    labels = ("python", "fastapi", "postgresql", "docker", "kubernetes")
    return JobInput(
        skills_required=tuple(JobSkill(label, skill_confidence) for label in labels),
        title_embedding=E1,
        locations=(JobLocation(PARIS_LAT, PARIS_LON),),
        location_confidence=location_confidence,
    )

"""Règles d'explication déterministes (06 §6) : strength / gap / uncertain."""

from __future__ import annotations

import dataclasses

import pytest

from app.matching import (
    CandidateInput,
    Confident,
    JobInput,
    MatchResult,
    compute_match,
)
from tests.unit.matching.factories import (
    perfect_candidate,
    perfect_job,
    um02_candidate,
    um02_job,
)


def _kinds(result: MatchResult) -> dict[str, list[str]]:
    facts = result.explanation_facts
    return {
        "blocking": [f.dimension for f in facts.blocking],
        "strength": [f.dimension for f in facts.strengths],
        "gap": [f.dimension for f in facts.gaps],
        "uncertain": [f.dimension for f in facts.uncertain],
    }


def test_strength_requires_s_08_and_weight_6() -> None:
    """`strength` ssi s ≥ 0,8 ET w ≥ 6 — le secteur (w=4) n'y entre jamais."""
    result = compute_match(perfect_candidate(), perfect_job())
    kinds = _kinds(result)
    assert "skills_required" in kinds["strength"]
    assert "location" in kinds["strength"]
    # sector s=1,0 mais w=4 < 6 → ni strength ni gap.
    assert "sector" not in kinds["strength"]
    assert "sector" not in kinds["gap"]
    # salaire s=1,0, w=3 < 6 → exclu aussi.
    assert "salary" not in kinds["strength"]
    assert kinds["gap"] == []
    assert kinds["uncertain"] == []


def test_strength_boundary_exactly_08_and_w6() -> None:
    """s = 0,8 exactement avec w = 6 (remote préféré × hybride) → strength."""
    candidate = dataclasses.replace(um02_candidate(), remote_pref="preferred")
    job = dataclasses.replace(um02_job(), remote=Confident("hybrid"))
    result = compute_match(candidate, job)
    kinds = _kinds(result)
    assert "remote" in kinds["strength"]  # s=0,8, w=6 : bornes incluses
    assert "skills_required" in kinds["strength"]  # s=0,8, w=25


def test_gap_at_04_boundary_with_exact_data() -> None:
    """s = 0,4 exactement → gap, avec la donnée chiffrée exacte."""
    candidate = CandidateInput(total_experience_years=3.0)
    job = JobInput(experience_min=5.0)
    result = compute_match(candidate, job)
    facts = result.explanation_facts
    gap = next(f for f in facts.gaps if f.dimension == "experience_years")
    assert gap.data["subscore"] == pytest.approx(0.4)
    assert gap.data["candidate_years"] == pytest.approx(3.0)
    assert gap.data["job_min"] == pytest.approx(5.0)


def test_gap_lists_missing_skills_nominatively() -> None:
    result = compute_match(
        CandidateInput(skills=("python",)),
        dataclasses.replace(um02_job()),
    )
    gap = next(
        f for f in result.explanation_facts.gaps if f.dimension == "skills_required"
    )
    assert gap.data["missing"] == ["fastapi", "postgresql", "docker", "kubernetes"]
    assert gap.data["matched"] == ["python"]


def test_uncertain_labels_indicate_missing_side() -> None:
    result = compute_match(um02_candidate(), um02_job())
    uncertain = {f.dimension: f for f in result.explanation_facts.uncertain}
    assert "non précisé dans l'offre" in uncertain["salary"].label
    assert "absent de votre profil" in uncertain["preference_boost"].label
    assert len(result.explanation_facts.uncertain) == 9


def test_blocking_facts_listed_first_with_rule() -> None:
    candidate = dataclasses.replace(um02_candidate(), remote_pref="required")
    job = dataclasses.replace(um02_job(), remote=Confident("onsite"))
    result = compute_match(candidate, job)
    facts = result.explanation_facts
    assert len(facts.blocking) == 1
    blocking = facts.blocking[0]
    assert blocking.kind == "blocking"
    assert blocking.dimension == "remote"
    assert blocking.data["code"] == "remote_required"
    assert blocking.label == result.blocking_criteria[0].label
    # Le remote bloqué est aussi un gap (s=0) — sans mise à zéro du score.
    assert "remote" in {f.dimension for f in facts.gaps}


def test_no_invented_facts_in_explanations() -> None:
    """Chaque fait référence une dimension réellement évaluée ou inconnue."""
    result = compute_match(um02_candidate(), um02_job())
    facts = result.explanation_facts
    known_dims = {s.dimension for s in result.dimension_scores if s.known}
    unknown_dims = {u.dimension for u in result.unknown_dimensions}
    assert {f.dimension for f in facts.strengths} <= known_dims
    assert {f.dimension for f in facts.gaps} <= known_dims
    assert {f.dimension for f in facts.uncertain} == unknown_dims

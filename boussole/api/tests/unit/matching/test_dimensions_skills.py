"""Dimensions 1-2 : couverture des compétences (06 §2.1-2.2)."""

from __future__ import annotations

import pytest

from app.matching import CandidateInput, JobInput, JobSkill

from tests.unit.matching.factories import outcome


def _candidate(*skills: str, **kwargs: object) -> CandidateInput:
    return CandidateInput(skills=skills, **kwargs)  # type: ignore[arg-type]


def test_all_exact_matches() -> None:
    result = outcome(
        "skills_required",
        _candidate("python", "fastapi"),
        JobInput(skills_required=(JobSkill("python"), JobSkill("fastapi"))),
    )
    assert result.known
    assert result.subscore == pytest.approx(1.0)
    assert result.details["matched"] == ["python", "fastapi"]
    assert result.details["missing"] == []


def test_um06_mixed_coverage_with_related() -> None:
    """UM-06 : 2 exactes + 1 proche (cos ≥ 0,75) + 1 absente → 0,625."""
    candidate = CandidateInput(
        skills=("python", "fastapi", "react"),
        skill_embeddings={"react": (1.0, 0.0)},
    )
    job = JobInput(
        skills_required=(
            JobSkill("python"),
            JobSkill("fastapi"),
            JobSkill("reactjs"),
            JobSkill("kubernetes"),
        ),
        skill_embeddings={"reactjs": (0.95, 0.31224989991991997)},
    )
    result = outcome("skills_required", candidate, job)
    assert result.subscore == pytest.approx(0.625)
    assert result.details["matched"] == ["python", "fastapi"]
    related = result.details["related"]
    assert isinstance(related, list) and len(related) == 1
    assert related[0]["required"] == "reactjs"
    assert related[0]["via"] == "react"
    assert result.details["missing"] == ["kubernetes"]


def test_related_requires_embeddings_on_both_sides() -> None:
    """🟡 Sans embeddings fournis : match exact uniquement, jamais de crédit 0,5."""
    candidate = _candidate("react")
    job = JobInput(skills_required=(JobSkill("reactjs"),))
    result = outcome("skills_required", candidate, job)
    assert result.subscore == pytest.approx(0.0)
    assert result.details["missing"] == ["reactjs"]


def test_related_below_threshold_counts_missing() -> None:
    candidate = CandidateInput(skills=("go",), skill_embeddings={"go": (1.0, 0.0)})
    job = JobInput(
        skills_required=(JobSkill("rust"),),
        skill_embeddings={"rust": (0.70, 0.7141428428542851)},  # cos = 0,70 < 0,75
    )
    result = outcome("skills_required", candidate, job)
    assert result.subscore == pytest.approx(0.0)
    assert result.details["missing"] == ["rust"]


def test_normalization_case_and_spaces() -> None:
    result = outcome(
        "skills_required",
        _candidate("Python "),
        JobInput(skills_required=(JobSkill(" PYTHON"),)),
    )
    assert result.subscore == pytest.approx(1.0)


def test_um17_job_without_required_skills_is_unknown() -> None:
    """UM-17 : donnée manquante → k=0, jamais s=0."""
    result = outcome("skills_required", _candidate("python"), JobInput())
    assert not result.known
    assert result.subscore is None
    assert result.unknown_reason == "job_missing"


def test_all_items_below_extraction_floor_is_unknown() -> None:
    job = JobInput(skills_required=(JobSkill("python", 0.4), JobSkill("go", 0.2)))
    result = outcome("skills_required", _candidate("python"), job)
    assert not result.known
    assert result.unknown_reason == "low_confidence"
    assert result.details["dropped_low_confidence"] == ["python", "go"]


def test_low_confidence_items_excluded_from_denominator() -> None:
    job = JobInput(
        skills_required=(JobSkill("python", 0.9), JobSkill("go", 0.9), JobSkill("zig", 0.3))
    )
    result = outcome("skills_required", _candidate("python"), job)
    assert result.subscore == pytest.approx(0.5)  # 1 exacte / 2 retenues
    assert result.details["dropped_low_confidence"] == ["zig"]
    assert result.q == pytest.approx(0.9)


def test_q_is_mean_of_retained_confidences() -> None:
    job = JobInput(skills_required=(JobSkill("python", 0.8), JobSkill("go", 1.0)))
    result = outcome("skills_required", _candidate("python", "go"), job)
    assert result.q == pytest.approx(0.9)


def test_nice_to_have_same_method() -> None:
    job = JobInput(skills_nice=(JobSkill("docker"), JobSkill("terraform")))
    result = outcome("skills_nice", _candidate("docker"), job)
    assert result.subscore == pytest.approx(0.5)


def test_nice_to_have_absent_is_unknown_not_penalizing() -> None:
    result = outcome("skills_nice", _candidate("docker"), JobInput())
    assert not result.known
    assert result.unknown_reason == "job_missing"

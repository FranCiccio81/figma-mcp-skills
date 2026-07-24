"""Critères bloquants (06 §3) : les 6 codes, plancher 0,7, rétrogradation."""

from __future__ import annotations

import dataclasses

import pytest

from app.matching import (
    CandidateInput,
    CandidateLocation,
    Confident,
    JobInput,
    JobLanguage,
    JobLocation,
    MatchResult,
    compute_match,
    get_config,
)
from tests.unit.matching.factories import PARIS_LAT, PARIS_LON, dim, lat_offset_deg

ALL_CODES = {
    "location_incompatible",
    "remote_required",
    "language_missing",
    "contract_excluded",
    "salary_below_minimum",
    "sector_excluded",
}


def _codes(result: MatchResult) -> list[str]:
    return [criterion.code for criterion in result.blocking_criteria]


def _demoted_codes(result: MatchResult, dimension: str) -> list[str]:
    demoted = dim(result, dimension).details.get("demoted_blockings", [])
    assert isinstance(demoted, list)
    return [str(entry["code"]) for entry in demoted]


def _location_pair(confidence: float) -> tuple[CandidateInput, JobInput]:
    candidate = CandidateInput(locations=(CandidateLocation(PARIS_LAT, PARIS_LON, 30.0),))
    job = JobInput(
        locations=(JobLocation(PARIS_LAT + lat_offset_deg(70.0), PARIS_LON),),
        remote=Confident("onsite", confidence),
    )
    return candidate, job


def _remote_pair(confidence: float) -> tuple[CandidateInput, JobInput]:
    return CandidateInput(remote_pref="required"), JobInput(remote=Confident("onsite", confidence))


def _language_pair(confidence: float) -> tuple[CandidateInput, JobInput]:
    return (
        CandidateInput(languages={"fr": "native"}),
        JobInput(languages_required=(JobLanguage("de", "C1", confidence),)),
    )


def _contract_pair(confidence: float) -> tuple[CandidateInput, JobInput]:
    return (
        CandidateInput(contract_types=frozenset({"cdi"}), contract_strict=True),
        JobInput(contract=Confident("stage", confidence)),
    )


def _salary_pair(confidence: float) -> tuple[CandidateInput, JobInput]:
    return (
        CandidateInput(salary_min_strict=50_000.0, salary_expected_min=50_000.0),
        JobInput(salary_min=30_000.0, salary_max=40_000.0, salary_confidence=confidence),
    )


def _sector_pair(confidence: float) -> tuple[CandidateInput, JobInput]:
    return (
        CandidateInput(
            sectors_excluded=frozenset({"defense"}), sectors_preferred=frozenset({"tech"})
        ),
        JobInput(sector=Confident("defense", confidence)),
    )


_PAIRS = {
    "location_incompatible": ("location", _location_pair),
    "remote_required": ("remote", _remote_pair),
    "language_missing": ("languages", _language_pair),
    "contract_excluded": ("contract", _contract_pair),
    "salary_below_minimum": ("salary", _salary_pair),
    "sector_excluded": ("sector", _sector_pair),
}


@pytest.mark.parametrize("code", sorted(ALL_CODES))
def test_each_blocker_fires_at_full_confidence(code: str) -> None:
    _, make = _PAIRS[code]
    result = compute_match(*make(1.0))
    assert _codes(result) == [code]
    label = result.blocking_criteria[0].label
    assert label == get_config().blocking_labels[code]


@pytest.mark.parametrize("code", sorted(ALL_CODES))
def test_each_blocker_demoted_below_07(code: str) -> None:
    """Confiance 0,65 < 0,7 → jamais bloquant, rétrogradé en avertissement."""
    dimension, make = _PAIRS[code]
    result = compute_match(*make(0.65))
    assert _codes(result) == []
    assert _demoted_codes(result, dimension) == [code]


@pytest.mark.parametrize("code", sorted(ALL_CODES))
def test_below_extraction_floor_no_blocker_no_warning(code: str) -> None:
    """Confiance 0,45 < 0,5 → donnée inconnue : ni bloquant, ni avertissement."""
    dimension, make = _PAIRS[code]
    result = compute_match(*make(0.45))
    assert _codes(result) == []
    assert _demoted_codes(result, dimension) == []
    if code == "location_incompatible":
        # La donnée douteuse est la politique « onsite » : la distance reste
        # évaluable (s=0) mais « strict » ne peut plus être affirmé.
        assert dim(result, dimension).known
    else:
        assert not dim(result, dimension).known


def test_blocker_never_zeroes_score() -> None:
    candidate, job = _remote_pair(1.0)
    candidate = dataclasses.replace(
        candidate,
        skills=("python",),
        locations=(CandidateLocation(PARIS_LAT, PARIS_LON, 30.0),),
    )
    from app.matching import JobSkill

    job = dataclasses.replace(
        job,
        skills_required=(JobSkill("python"),),
        locations=(JobLocation(PARIS_LAT, PARIS_LON),),
    )
    result = compute_match(candidate, job)
    assert _codes(result) == ["remote_required"]
    # skills 25×1 + location 8×1 + remote 6×0 → round(100×33/39) = 85 ≠ 0.
    assert result.score == 85


def test_blocking_codes_are_deduplicated() -> None:
    """Deux langues manquantes → un seul critère `language_missing`."""
    candidate = CandidateInput(languages={"fr": "native"})
    job = JobInput(
        languages_required=(JobLanguage("de", "C1"), JobLanguage("es", "C1"))
    )
    result = compute_match(candidate, job)
    assert _codes(result) == ["language_missing"]


def test_blocking_labels_come_from_config() -> None:
    for code, (_, make) in _PAIRS.items():
        result = compute_match(*make(1.0))
        assert result.blocking_criteria[0].label == get_config().blocking_labels[code]

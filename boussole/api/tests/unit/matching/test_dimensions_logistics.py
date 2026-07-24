"""Dimensions 7-9 : localisation, télétravail, langues (06 §2)."""

from __future__ import annotations

import pytest

from app.matching import (
    CandidateInput,
    CandidateLocation,
    Confident,
    JobInput,
    JobLanguage,
    JobLocation,
)
from tests.unit.matching.factories import PARIS_LAT, PARIS_LON, lat_offset_deg, outcome

# --------------------------------------------------------------- localisation


def _geo(distance_km: float, radius_km: float | None = 30.0) -> tuple[CandidateInput, JobInput]:
    candidate = CandidateInput(locations=(CandidateLocation(PARIS_LAT, PARIS_LON, radius_km),))
    job = JobInput(locations=(JobLocation(PARIS_LAT + lat_offset_deg(distance_km), PARIS_LON),))
    return candidate, job


def test_location_within_radius() -> None:
    result = outcome("location", *_geo(0.0))
    assert result.subscore == pytest.approx(1.0)
    result = outcome("location", *_geo(30.0))
    assert result.subscore == pytest.approx(1.0, abs=1e-6)


def test_um11_linear_decay() -> None:
    result = outcome("location", *_geo(45.0))
    assert result.subscore == pytest.approx(0.5, abs=1e-6)
    assert result.details["distance_km"] == pytest.approx(45.0, abs=0.01)


def test_location_zero_beyond_double_radius() -> None:
    assert outcome("location", *_geo(60.0)).subscore == pytest.approx(0.0, abs=1e-6)
    assert outcome("location", *_geo(70.0)).subscore == pytest.approx(0.0)


def test_um11_onsite_strict_beyond_double_radius_blocks() -> None:
    candidate, job = _geo(70.0)
    job_onsite = JobInput(locations=job.locations, remote=Confident("onsite"))
    result = outcome("location", candidate, job_onsite)
    assert result.subscore == pytest.approx(0.0)
    assert result.blocking == ["location_incompatible"]


def test_location_blocker_demoted_when_onsite_uncertain() -> None:
    candidate, job = _geo(70.0)
    job_onsite = JobInput(locations=job.locations, remote=Confident("onsite", 0.65))
    result = outcome("location", candidate, job_onsite)
    assert result.blocking == []
    assert result.demoted_blockings
    assert result.demoted_blockings[0]["code"] == "location_incompatible"


def test_location_hybrid_far_away_no_blocker() -> None:
    candidate, job = _geo(70.0)
    job_hybrid = JobInput(locations=job.locations, remote=Confident("hybrid"))
    result = outcome("location", candidate, job_hybrid)
    assert result.subscore == pytest.approx(0.0)
    assert result.blocking == []


def test_location_full_remote_scores_one_anywhere() -> None:
    candidate, _ = _geo(500.0)
    result = outcome("location", candidate, JobInput(remote=Confident("full_remote", 0.9)))
    assert result.subscore == pytest.approx(1.0)
    assert result.q == pytest.approx(0.9)
    assert result.details["mode"] == "full_remote"


def test_location_default_radius_from_config() -> None:
    candidate, job = _geo(45.0, radius_km=None)  # défaut 30 km → décroissance
    result = outcome("location", candidate, job)
    assert result.subscore == pytest.approx(0.5, abs=1e-6)


def test_location_best_candidate_location_wins() -> None:
    candidate = CandidateInput(
        locations=(
            CandidateLocation(PARIS_LAT + lat_offset_deg(500.0), PARIS_LON, 30.0),
            CandidateLocation(PARIS_LAT, PARIS_LON, 30.0),
        )
    )
    job = JobInput(locations=(JobLocation(PARIS_LAT, PARIS_LON),))
    assert outcome("location", candidate, job).subscore == pytest.approx(1.0)


def test_location_unknown_is_critical() -> None:
    candidate, _ = _geo(0.0)
    result = outcome("location", candidate, JobInput())
    assert not result.known
    assert result.unknown_reason == "job_missing"
    assert result.details["critical"] is True


def test_location_candidate_missing() -> None:
    _, job = _geo(0.0)
    result = outcome("location", CandidateInput(), job)
    assert not result.known
    assert result.unknown_reason == "candidate_missing"


# ---------------------------------------------------------------- télétravail


@pytest.mark.parametrize(
    ("pref", "policy", "expected"),
    [
        ("required", "full_remote", 1.0),
        ("required", "hybrid", 0.4),
        ("required", "onsite", 0.0),
        ("preferred", "full_remote", 1.0),
        ("preferred", "hybrid", 0.8),
        ("preferred", "onsite", 0.3),
        ("indifferent", "full_remote", 1.0),
        ("indifferent", "hybrid", 1.0),
        ("indifferent", "onsite", 1.0),
        ("onsite_preferred", "full_remote", 0.5),
        ("onsite_preferred", "hybrid", 0.8),
        ("onsite_preferred", "onsite", 1.0),
    ],
)
def test_remote_matrix(pref: str, policy: str, expected: float) -> None:
    result = outcome(
        "remote",
        CandidateInput(remote_pref=pref),  # type: ignore[arg-type]
        JobInput(remote=Confident(policy)),
    )
    assert result.known
    assert result.subscore == pytest.approx(expected)


def test_um12_required_onsite_blocks() -> None:
    result = outcome(
        "remote", CandidateInput(remote_pref="required"), JobInput(remote=Confident("onsite"))
    )
    assert result.subscore == pytest.approx(0.0)
    assert result.blocking == ["remote_required"]


def test_um16_blocker_demoted_below_confidence_floor() -> None:
    """UM-16 : politique onsite extraite à 0,65 < 0,7 → avertissement, jamais bloquant."""
    result = outcome(
        "remote",
        CandidateInput(remote_pref="required"),
        JobInput(remote=Confident("onsite", 0.65)),
    )
    assert result.known  # 0,65 ≥ plancher d'extraction : la dimension est évaluée
    assert result.subscore == pytest.approx(0.0)
    assert result.blocking == []
    assert result.demoted_blockings
    assert result.demoted_blockings[0]["code"] == "remote_required"
    assert result.demoted_blockings[0]["confidence"] == pytest.approx(0.65)


def test_remote_unknown_cases() -> None:
    no_job = outcome("remote", CandidateInput(remote_pref="preferred"), JobInput())
    assert not no_job.known and no_job.unknown_reason == "job_missing"
    low_conf = outcome(
        "remote",
        CandidateInput(remote_pref="required"),
        JobInput(remote=Confident("onsite", 0.45)),
    )
    assert not low_conf.known and low_conf.unknown_reason == "low_confidence"
    assert low_conf.blocking == []  # sous 0,5 : jamais un fait, même pas un avertissement
    assert low_conf.demoted_blockings == []
    no_candidate = outcome("remote", CandidateInput(), JobInput(remote=Confident("hybrid")))
    assert not no_candidate.known
    assert no_candidate.unknown_reason == "candidate_missing"


# --------------------------------------------------------------------- langues


def _lang_candidate(**levels: str) -> CandidateInput:
    return CandidateInput(languages=dict(levels))


def test_um13_language_levels() -> None:
    job = JobInput(languages_required=(JobLanguage("en", "C1"),))
    meets = outcome("languages", _lang_candidate(en="C1"), job)
    assert meets.subscore == pytest.approx(1.0)
    one_below = outcome("languages", _lang_candidate(en="B2"), job)
    assert one_below.subscore == pytest.approx(0.5)
    assert one_below.blocking == []
    two_below = outcome("languages", _lang_candidate(en="B1"), job)
    assert two_below.subscore == pytest.approx(0.0)
    assert two_below.blocking == ["language_missing"]


def test_language_absent_blocks() -> None:
    job = JobInput(languages_required=(JobLanguage("de", "B2"),))
    result = outcome("languages", _lang_candidate(fr="native"), job)
    assert result.subscore == pytest.approx(0.0)
    assert result.blocking == ["language_missing"]


def test_native_counts_as_c2() -> None:
    job = JobInput(languages_required=(JobLanguage("fr", "C2"),))
    result = outcome("languages", _lang_candidate(fr="native"), job)
    assert result.subscore == pytest.approx(1.0)


def test_languages_mean_over_requirements() -> None:
    job = JobInput(
        languages_required=(JobLanguage("en", "C1"), JobLanguage("fr", "B2"))
    )
    result = outcome("languages", _lang_candidate(en="B2", fr="native"), job)
    assert result.subscore == pytest.approx(0.75)  # (0,5 + 1,0) / 2


def test_language_blocker_demoted_below_confidence_floor() -> None:
    job = JobInput(languages_required=(JobLanguage("de", "B2", 0.65),))
    result = outcome("languages", _lang_candidate(fr="native"), job)
    assert result.blocking == []
    assert result.demoted_blockings
    assert result.demoted_blockings[0]["code"] == "language_missing"


def test_languages_unknown_cases() -> None:
    no_job = outcome("languages", _lang_candidate(fr="native"), JobInput())
    assert not no_job.known and no_job.unknown_reason == "job_missing"
    low_conf = outcome(
        "languages",
        _lang_candidate(fr="native"),
        JobInput(languages_required=(JobLanguage("de", "B2", 0.3),)),
    )
    assert not low_conf.known and low_conf.unknown_reason == "low_confidence"
    assert low_conf.blocking == []


def test_languages_q_mean_of_confidences() -> None:
    job = JobInput(
        languages_required=(JobLanguage("en", "B2", 0.8), JobLanguage("fr", "B1", 1.0))
    )
    result = outcome("languages", _lang_candidate(en="C1", fr="native"), job)
    assert result.q == pytest.approx(0.9)

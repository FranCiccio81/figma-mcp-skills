"""Dimensions 3-6 : similarité métier, séniorité, expérience, secteur (06 §2)."""

from __future__ import annotations

import pytest

from app.matching import CandidateInput, Confident, JobInput

from tests.unit.matching.factories import E1, outcome, vector_with_cosine

# --------------------------------------------------------- similarité métier


def test_um07_affine_mapping_midpoint() -> None:
    candidate = CandidateInput(target_titles_embeddings=(E1,))
    job = JobInput(title_embedding=vector_with_cosine(0.675))
    result = outcome("title_similarity", candidate, job)
    assert result.subscore == pytest.approx(0.5, abs=1e-6)
    assert result.details["similarity"] == pytest.approx(0.675, abs=1e-4)


def test_um07_affine_bounds() -> None:
    candidate = CandidateInput(target_titles_embeddings=(E1,))
    low = outcome("title_similarity", candidate, JobInput(title_embedding=vector_with_cosine(0.55)))
    assert low.subscore == pytest.approx(0.0, abs=1e-6)
    below = outcome(
        "title_similarity", candidate, JobInput(title_embedding=vector_with_cosine(0.30))
    )
    assert below.subscore == pytest.approx(0.0)
    high = outcome(
        "title_similarity", candidate, JobInput(title_embedding=vector_with_cosine(0.80))
    )
    assert high.subscore == pytest.approx(1.0, abs=1e-6)
    above = outcome("title_similarity", candidate, JobInput(title_embedding=E1))
    assert above.subscore == pytest.approx(1.0)


def test_title_takes_max_over_candidate_targets() -> None:
    candidate = CandidateInput(
        target_titles_embeddings=(vector_with_cosine(0.0), E1)  # le meilleur cosinus gagne
    )
    result = outcome("title_similarity", candidate, JobInput(title_embedding=E1))
    assert result.subscore == pytest.approx(1.0)


def test_title_missing_embeddings_means_unknown() -> None:
    """Embeddings absents → k=0 (jamais de similarité inventée)."""
    no_job = outcome("title_similarity", CandidateInput(target_titles_embeddings=(E1,)), JobInput())
    assert not no_job.known
    assert no_job.unknown_reason == "job_missing"
    no_candidate = outcome("title_similarity", CandidateInput(), JobInput(title_embedding=E1))
    assert not no_candidate.known
    assert no_candidate.unknown_reason == "candidate_missing"


# ------------------------------------------------------------------ séniorité


@pytest.mark.parametrize(
    ("candidate_level", "job_level", "expected"),
    [
        ("senior", "senior", 1.0),  # Δ=0
        ("lead", "senior", 0.8),  # UM-08 : sur-qualifié de 1
        ("mid", "senior", 0.6),  # UM-08 : sous-qualifié de 1
        ("executive", "lead", 0.8),
        ("lead", "mid", 0.5),  # sur-qualifié de 2
        ("executive", "senior", 0.3),  # sur-qualifié de 3
        ("executive", "junior", 0.3),  # Δ=−5 borné à −3
        ("junior", "senior", 0.25),  # sous-qualifié de 2
        ("intern", "senior", 0.0),  # sous-qualifié de 3
        ("intern", "executive", 0.0),  # Δ=+6 borné à +3
    ],
)
def test_seniority_ordinal_table(candidate_level: str, job_level: str, expected: float) -> None:
    result = outcome(
        "seniority",
        CandidateInput(seniority=candidate_level),
        JobInput(seniority=Confident(job_level)),
    )
    assert result.known
    assert result.subscore == pytest.approx(expected)


def test_seniority_unknown_cases() -> None:
    missing_job = outcome("seniority", CandidateInput(seniority="senior"), JobInput())
    assert not missing_job.known and missing_job.unknown_reason == "job_missing"
    missing_candidate = outcome("seniority", CandidateInput(), JobInput(seniority=Confident("senior")))
    assert not missing_candidate.known
    assert missing_candidate.unknown_reason == "candidate_missing"


def test_um05_seniority_below_extraction_floor_is_unknown() -> None:
    """UM-05 : conf 0,45 < 0,5 → k=0, jamais utilisée comme fait."""
    result = outcome(
        "seniority",
        CandidateInput(seniority="senior"),
        JobInput(seniority=Confident("senior", 0.45)),
    )
    assert not result.known
    assert result.subscore is None
    assert result.unknown_reason == "low_confidence"


def test_seniority_invalid_level_raises() -> None:
    with pytest.raises(ValueError, match="séniorité"):
        outcome(
            "seniority",
            CandidateInput(seniority="wizard"),
            JobInput(seniority=Confident("senior")),
        )


# ----------------------------------------------------------------- expérience


def _experience(years: float, minimum: float | None, maximum: float | None) -> float | None:
    result = outcome(
        "experience_years",
        CandidateInput(total_experience_years=years),
        JobInput(experience_min=minimum, experience_max=maximum),
    )
    return result.subscore


def test_experience_within_range() -> None:
    assert _experience(5.0, 3.0, 8.0) == pytest.approx(1.0)
    assert _experience(3.0, 3.0, 8.0) == pytest.approx(1.0)  # borne basse incluse
    assert _experience(8.0, 3.0, 8.0) == pytest.approx(1.0)  # borne haute incluse


def test_um09_below_minimum() -> None:
    assert _experience(3.0, 5.0, None) == pytest.approx(0.4)  # 3/5 − 0,2


def test_below_minimum_floors_at_zero() -> None:
    assert _experience(0.5, 5.0, None) == pytest.approx(0.0)  # 0,1 − 0,2 → 0


def test_um10_above_maximum() -> None:
    assert _experience(10.0, None, 7.0) == pytest.approx(0.85)  # max(0,7 ; 1 − 0,05×3)


def test_above_maximum_floors_at_07() -> None:
    assert _experience(30.0, None, 7.0) == pytest.approx(0.7)


def test_open_ranges() -> None:
    assert _experience(6.0, 5.0, None) == pytest.approx(1.0)  # « 5+ ans » satisfait
    assert _experience(2.0, None, 7.0) == pytest.approx(1.0)  # max seul, en dessous


def test_experience_unknown_cases() -> None:
    no_job = outcome(
        "experience_years", CandidateInput(total_experience_years=5.0), JobInput()
    )
    assert not no_job.known and no_job.unknown_reason == "job_missing"
    low_conf = outcome(
        "experience_years",
        CandidateInput(total_experience_years=5.0),
        JobInput(experience_min=3.0, experience_confidence=0.4),
    )
    assert not low_conf.known and low_conf.unknown_reason == "low_confidence"
    no_candidate = outcome("experience_years", CandidateInput(), JobInput(experience_min=3.0))
    assert not no_candidate.known
    assert no_candidate.unknown_reason == "candidate_missing"


# -------------------------------------------------------------------- secteur


def _sector_candidate() -> CandidateInput:
    return CandidateInput(
        sectors_preferred=frozenset({"fintech"}),
        sectors_experienced=frozenset({"retail"}),
        sectors_excluded=frozenset({"defense"}),
        sector_parents={"fintech": "finance", "retail": "commerce"},
    )


def test_sector_categories() -> None:
    candidate = _sector_candidate()
    assert outcome("sector", candidate, JobInput(sector=Confident("fintech"))).subscore == (
        pytest.approx(1.0)
    )
    assert outcome("sector", candidate, JobInput(sector=Confident("retail"))).subscore == (
        pytest.approx(0.8)
    )
    adjacent = outcome(
        "sector",
        candidate,
        JobInput(sector=Confident("insurance"), sector_parent="finance"),
    )
    assert adjacent.subscore == pytest.approx(0.6)
    assert adjacent.details["category"] == "adjacent"
    other = outcome("sector", candidate, JobInput(sector=Confident("agriculture")))
    assert other.subscore == pytest.approx(0.3)
    assert other.details["category"] == "other"


def test_sector_excluded_blocks() -> None:
    result = outcome("sector", _sector_candidate(), JobInput(sector=Confident("defense")))
    assert result.blocking == ["sector_excluded"]
    assert result.subscore == pytest.approx(0.0)  # 🟡 hypothèse : exclu → s=0


def test_sector_excluded_demoted_below_blocking_floor() -> None:
    result = outcome("sector", _sector_candidate(), JobInput(sector=Confident("defense", 0.65)))
    assert result.blocking == []
    assert result.demoted_blockings and result.demoted_blockings[0]["code"] == "sector_excluded"


def test_sector_unknown_cases() -> None:
    no_job = outcome("sector", _sector_candidate(), JobInput())
    assert not no_job.known and no_job.unknown_reason == "job_missing"
    low_conf = outcome("sector", _sector_candidate(), JobInput(sector=Confident("fintech", 0.4)))
    assert not low_conf.known and low_conf.unknown_reason == "low_confidence"
    no_candidate = outcome("sector", CandidateInput(), JobInput(sector=Confident("fintech")))
    assert not no_candidate.known
    assert no_candidate.unknown_reason == "candidate_missing"


def test_sector_exclusion_blocks_even_without_positive_sectors() -> None:
    """La liste d'exclusion suffit pour bloquer, même si la dimension reste k=0."""
    candidate = CandidateInput(sectors_excluded=frozenset({"defense"}))
    result = outcome("sector", candidate, JobInput(sector=Confident("defense")))
    assert not result.known
    assert result.blocking == ["sector_excluded"]

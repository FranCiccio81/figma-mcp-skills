"""Dimensions 10-12 : contrat, salaire, préférences fines (06 §2)."""

from __future__ import annotations

import pytest

from app.matching import CandidateInput, Confident, JobInput

from tests.unit.matching.factories import outcome

# --------------------------------------------------------------------- contrat


def _contract_candidate(*types: str, strict: bool = False) -> CandidateInput:
    return CandidateInput(contract_types=frozenset(types), contract_strict=strict)


def test_contract_accepted() -> None:
    result = outcome("contract", _contract_candidate("cdi"), JobInput(contract=Confident("cdi")))
    assert result.subscore == pytest.approx(1.0)


def test_contract_refused_soft() -> None:
    result = outcome("contract", _contract_candidate("cdi"), JobInput(contract=Confident("cdd")))
    assert result.subscore == pytest.approx(0.2)
    assert result.blocking == []


def test_contract_refused_strict_blocks() -> None:
    result = outcome(
        "contract", _contract_candidate("cdi", strict=True), JobInput(contract=Confident("cdd"))
    )
    assert result.subscore == pytest.approx(0.0)
    assert result.blocking == ["contract_excluded"]


def test_contract_blocker_demoted_below_confidence_floor() -> None:
    result = outcome(
        "contract",
        _contract_candidate("cdi", strict=True),
        JobInput(contract=Confident("cdd", 0.6)),
    )
    assert result.blocking == []
    assert result.demoted_blockings
    assert result.demoted_blockings[0]["code"] == "contract_excluded"


def test_contract_unknown_cases() -> None:
    no_job = outcome("contract", _contract_candidate("cdi"), JobInput())
    assert not no_job.known and no_job.unknown_reason == "job_missing"
    low_conf = outcome(
        "contract", _contract_candidate("cdi"), JobInput(contract=Confident("cdd", 0.4))
    )
    assert not low_conf.known and low_conf.unknown_reason == "low_confidence"
    no_candidate = outcome("contract", CandidateInput(), JobInput(contract=Confident("cdi")))
    assert not no_candidate.known
    assert no_candidate.unknown_reason == "candidate_missing"


# --------------------------------------------------------------------- salaire


def _salary_candidate(
    minimum: float | None, maximum: float | None, strict: float | None = None
) -> CandidateInput:
    return CandidateInput(
        salary_expected_min=minimum, salary_expected_max=maximum, salary_min_strict=strict
    )


def test_um14_overlap() -> None:
    result = outcome(
        "salary",
        _salary_candidate(45_000, 55_000),
        JobInput(salary_min=50_000, salary_max=60_000),
    )
    assert result.subscore == pytest.approx(0.5)  # 5 k€ / 10 k€


def test_salary_full_overlap() -> None:
    result = outcome(
        "salary",
        _salary_candidate(45_000, 55_000),
        JobInput(salary_min=40_000, salary_max=60_000),
    )
    assert result.subscore == pytest.approx(1.0)


def test_salary_disjoint() -> None:
    result = outcome(
        "salary",
        _salary_candidate(45_000, 55_000),
        JobInput(salary_min=60_000, salary_max=70_000),
    )
    assert result.subscore == pytest.approx(0.0)


def test_salary_monthly_annualized() -> None:
    result = outcome(
        "salary",
        _salary_candidate(45_000, 55_000),
        JobInput(salary_min=3_750, salary_max=5_000, salary_period="month"),
    )
    # 45 000–60 000 € annuels → recouvrement complet de [45k, 55k].
    assert result.subscore == pytest.approx(1.0)
    assert result.details["job_range_eur_year"] == [45_000.0, 60_000.0]


def test_salary_open_job_range_padded() -> None:
    result = outcome(
        "salary", _salary_candidate(45_000, 55_000), JobInput(salary_min=50_000)
    )
    # « à partir de 50 k€ » → [50k, 57,5k] (+15 %) → recouvrement 5 k€ / 10 k€.
    assert result.details["job_range_eur_year"] == [50_000.0, 57_500.0]
    assert result.subscore == pytest.approx(0.5)


def test_salary_open_candidate_range_padded() -> None:
    result = outcome(
        "salary", _salary_candidate(50_000, None), JobInput(salary_min=40_000, salary_max=60_000)
    )
    # Souhait « 50 k€ min » → [50k, 57,5k] entièrement couvert.
    assert result.details["candidate_range_eur_year"] == [50_000.0, 57_500.0]
    assert result.subscore == pytest.approx(1.0)


def test_um14_strict_minimum_blocks() -> None:
    result = outcome(
        "salary",
        _salary_candidate(45_000, 55_000, strict=50_000),
        JobInput(salary_min=40_000, salary_max=45_000),
    )
    assert result.blocking == ["salary_below_minimum"]
    assert result.known  # le bloquant ne rend pas la dimension inconnue


def test_salary_strict_blocker_without_expected_range() -> None:
    """Minimum strict seul : dimension k=0 mais bloquant évaluable (06 §3)."""
    result = outcome(
        "salary",
        _salary_candidate(None, None, strict=50_000),
        JobInput(salary_min=40_000, salary_max=45_000),
    )
    assert not result.known
    assert result.unknown_reason == "candidate_missing"
    assert result.blocking == ["salary_below_minimum"]


def test_salary_strict_blocker_demoted_below_confidence_floor() -> None:
    result = outcome(
        "salary",
        _salary_candidate(45_000, 55_000, strict=50_000),
        JobInput(salary_min=40_000, salary_max=45_000, salary_confidence=0.65),
    )
    assert result.blocking == []
    assert result.demoted_blockings
    assert result.demoted_blockings[0]["code"] == "salary_below_minimum"


def test_salary_degenerate_candidate_range() -> None:
    inside = outcome(
        "salary", _salary_candidate(50_000, 50_000), JobInput(salary_min=40_000, salary_max=60_000)
    )
    assert inside.subscore == pytest.approx(1.0)
    outside = outcome(
        "salary", _salary_candidate(70_000, 70_000), JobInput(salary_min=40_000, salary_max=60_000)
    )
    assert outside.subscore == pytest.approx(0.0)


def test_salary_unknown_cases() -> None:
    unpublished = outcome("salary", _salary_candidate(45_000, 55_000), JobInput())
    assert not unpublished.known
    assert unpublished.unknown_reason == "job_missing"  # « salaire non communiqué »
    low_conf = outcome(
        "salary",
        _salary_candidate(45_000, 55_000),
        JobInput(salary_min=40_000, salary_max=60_000, salary_confidence=0.4),
    )
    assert not low_conf.known and low_conf.unknown_reason == "low_confidence"


def test_salary_non_eur_currency_is_unknown() -> None:
    """🟡 Pas de table de taux embarquée au MVP → devise ≠ EUR jamais inventée."""
    result = outcome(
        "salary",
        _salary_candidate(45_000, 55_000),
        JobInput(salary_min=40_000, salary_max=60_000, salary_currency="USD"),
    )
    assert not result.known
    assert result.unknown_reason == "unconvertible_value"


# ---------------------------------------------------------- préférences fines


def test_preference_target_company() -> None:
    candidate = CandidateInput(target_companies=frozenset({"Acme"}))
    result = outcome("preference_boost", candidate, JobInput(company_name="ACME"))
    assert result.subscore == pytest.approx(1.0)
    assert result.details["matched_company"] == "ACME"


def test_preference_keyword_match() -> None:
    candidate = CandidateInput(keywords=("climat", "open source"))
    job = JobInput(company_name="Autre", description_text="Nous travaillons sur le Climat.")
    result = outcome("preference_boost", candidate, job)
    assert result.subscore == pytest.approx(0.7)
    assert result.details["matched_keywords"] == ["climat"]


def test_preference_no_match() -> None:
    candidate = CandidateInput(target_companies=frozenset({"Acme"}), keywords=("climat",))
    job = JobInput(company_name="Autre", description_text="Logistique portuaire.")
    result = outcome("preference_boost", candidate, job)
    assert result.subscore == pytest.approx(0.0)


def test_preference_company_beats_keyword() -> None:
    candidate = CandidateInput(target_companies=frozenset({"Acme"}), keywords=("climat",))
    job = JobInput(company_name="Acme", description_text="Le climat au cœur de la mission.")
    assert outcome("preference_boost", candidate, job).subscore == pytest.approx(1.0)


def test_preference_unknown_cases() -> None:
    no_candidate = outcome("preference_boost", CandidateInput(), JobInput(company_name="Acme"))
    assert not no_candidate.known
    assert no_candidate.unknown_reason == "candidate_missing"
    no_job = outcome(
        "preference_boost", CandidateInput(target_companies=frozenset({"Acme"})), JobInput()
    )
    assert not no_job.known
    assert no_job.unknown_reason == "job_missing"

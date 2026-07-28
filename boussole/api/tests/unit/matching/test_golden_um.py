"""Cas de référence chiffrés UM-01…UM-18 (13-testing-strategy.md §2.1).

Chiffres calculés à la main et gelés — ces tests cassent si un seuil de
`scoring-config.json` change sans mise à jour assumée.

Écart documenté (le doc 06 fait foi) : UM-15 annonce « score inchangé (90) »
avec un bloquant contrat strict ; or selon 06 §2.10 un contrat extrait rend la
dimension CONNUE (s=0, w=4), donc le score renormalisé devient
round(100×43/52) = 83. L'invariant réel de 06 §1 — un bloquant ne met pas le
score à zéro et est signalé séparément — est vérifié ici sous les deux formes.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.matching import (
    CandidateInput,
    Confident,
    JobInput,
    JobLocation,
    compute_match,
    get_config,
)
from tests.unit.matching.factories import (
    E1,
    PARIS_LAT,
    PARIS_LON,
    dim,
    job_with_title_cosine,
    lat_offset_deg,
    perfect_candidate,
    perfect_job,
    um02_candidate,
    um02_job,
    vector_with_cosine,
)


def test_um01_perfect_score() -> None:
    """UM-01 : 12 dimensions connues, s=1, q=1 → 100/100, 0 bloquant."""
    result = compute_match(perfect_candidate(), perfect_job())
    assert result.score == 100
    assert result.confidence == 100
    assert result.blocking_criteria == ()
    assert result.unknown_dimensions == ()
    assert not result.low_data
    assert all(score.known for score in result.dimension_scores)
    assert len(result.dimension_scores) == 12


def test_um02_renormalization_on_known() -> None:
    """UM-02 : connues 25×0,8 + 15×1 + 8×1 → round(100×43/48) = 90."""
    result = compute_match(um02_candidate(), um02_job())
    assert result.score == 90
    assert len(result.unknown_dimensions) == 9
    assert not result.low_data  # 48 ≥ 40
    assert dim(result, "skills_required").subscore == pytest.approx(0.8)
    assert dim(result, "title_similarity").subscore == pytest.approx(1.0)
    assert dim(result, "location").subscore == pytest.approx(1.0)


def test_um03_low_data() -> None:
    """UM-03 : seule skills_required connue (25 < 40) → low_data, score retourné."""
    candidate = CandidateInput(skills=("python", "fastapi", "postgresql", "docker"))
    job = um02_job()
    job = dataclasses.replace(job, title_embedding=None, locations=())
    result = compute_match(candidate, job)
    assert result.low_data
    assert result.score == 80  # calculé et retourné quand même
    assert len(result.unknown_dimensions) == 11


def test_um04_confidence_partial_q() -> None:
    """UM-04 : q = 0,9 / 1,0 / 0,8 → confidence = round(22,5+15+6,4) = 44."""
    result = compute_match(
        um02_candidate(), um02_job(skill_confidence=0.9, location_confidence=0.8)
    )
    assert result.confidence == 44
    assert result.score == 90  # s inchangés : les q ne touchent pas le score


def test_um05_extraction_floor() -> None:
    """UM-05 : séniorité extraite à 0,45 < 0,5 → k=0, jamais un fait."""
    candidate = dataclasses.replace(um02_candidate(), seniority="senior")
    job = dataclasses.replace(um02_job(), seniority=Confident("senior", 0.45))
    result = compute_match(candidate, job)
    seniority = dim(result, "seniority")
    assert not seniority.known
    assert seniority.subscore is None
    assert any(
        u.dimension == "seniority" and u.reason == "low_confidence"
        for u in result.unknown_dimensions
    )
    assert result.score == 90  # inchangé : la donnée douteuse n'influe pas


def test_um06_skill_coverage_via_engine() -> None:
    """UM-06 : 2 exactes + 1 proche + 1 absente → s = 0,625, détails nominatifs."""
    candidate = CandidateInput(
        skills=("python", "fastapi", "react"), skill_embeddings={"react": E1}
    )
    job = JobInput(
        skills_required=(
            *um02_job().skills_required[:2],
            dataclasses.replace(um02_job().skills_required[0], label="reactjs"),
            dataclasses.replace(um02_job().skills_required[0], label="kubernetes"),
        ),
        skill_embeddings={"reactjs": vector_with_cosine(0.9)},
    )
    result = compute_match(candidate, job)
    skills = dim(result, "skills_required")
    assert skills.subscore == pytest.approx(0.625)
    assert skills.details["matched"] == ["python", "fastapi"]
    assert skills.details["missing"] == ["kubernetes"]


def test_um07_title_affine() -> None:
    """UM-07 : sim 0,675 → 0,5 ; bornes 0,55 → 0 et 0,80 → 1."""
    candidate = CandidateInput(target_titles_embeddings=(E1,))
    mid = compute_match(candidate, job_with_title_cosine(0.675))
    assert dim(mid, "title_similarity").subscore == pytest.approx(0.5, abs=1e-6)
    low = compute_match(candidate, job_with_title_cosine(0.55))
    assert dim(low, "title_similarity").subscore == pytest.approx(0.0, abs=1e-6)
    high = compute_match(candidate, job_with_title_cosine(0.80))
    assert dim(high, "title_similarity").subscore == pytest.approx(1.0, abs=1e-6)


def test_um08_seniority_deltas() -> None:
    """UM-08 : senior vs lead → 0,8 ; senior vs confirmé → 0,6."""
    job = JobInput(seniority=Confident("senior"))
    overqualified = compute_match(CandidateInput(seniority="lead"), job)
    assert dim(overqualified, "seniority").subscore == pytest.approx(0.8)
    underqualified = compute_match(CandidateInput(seniority="mid"), job)
    assert dim(underqualified, "seniority").subscore == pytest.approx(0.6)


def test_um09_experience_below_min() -> None:
    result = compute_match(
        CandidateInput(total_experience_years=3.0), JobInput(experience_min=5.0)
    )
    assert dim(result, "experience_years").subscore == pytest.approx(0.4)


def test_um10_experience_above_max() -> None:
    result = compute_match(
        CandidateInput(total_experience_years=10.0), JobInput(experience_max=7.0)
    )
    assert dim(result, "experience_years").subscore == pytest.approx(0.85)


def test_um11_location_decay_and_blocker() -> None:
    candidate = um02_candidate()
    at_45 = JobInput(locations=(JobLocation(PARIS_LAT + lat_offset_deg(45.0), PARIS_LON),))
    result = compute_match(candidate, at_45)
    assert dim(result, "location").subscore == pytest.approx(0.5, abs=1e-6)

    at_70_onsite = JobInput(
        locations=(JobLocation(PARIS_LAT + lat_offset_deg(70.0), PARIS_LON),),
        remote=Confident("onsite"),
    )
    blocked = compute_match(candidate, at_70_onsite)
    assert dim(blocked, "location").subscore == pytest.approx(0.0)
    assert [b.code for b in blocked.blocking_criteria] == ["location_incompatible"]


def test_um12_remote_matrix() -> None:
    onsite = JobInput(remote=Confident("onsite"))
    required = compute_match(CandidateInput(remote_pref="required"), onsite)
    assert dim(required, "remote").subscore == pytest.approx(0.0)
    assert [b.code for b in required.blocking_criteria] == ["remote_required"]
    for policy in ("full_remote", "hybrid", "onsite"):
        indifferent = compute_match(
            CandidateInput(remote_pref="indifferent"), JobInput(remote=Confident(policy))
        )
        assert dim(indifferent, "remote").subscore == pytest.approx(1.0)
        assert indifferent.blocking_criteria == ()


def test_um13_languages() -> None:
    from app.matching import JobLanguage

    job = JobInput(languages_required=(JobLanguage("en", "C1"),))
    b2 = compute_match(CandidateInput(languages={"en": "B2"}), job)
    assert dim(b2, "languages").subscore == pytest.approx(0.5)
    assert b2.blocking_criteria == ()
    b1 = compute_match(CandidateInput(languages={"en": "B1"}), job)
    assert dim(b1, "languages").subscore == pytest.approx(0.0)
    assert [b.code for b in b1.blocking_criteria] == ["language_missing"]


def test_um14_salary() -> None:
    overlap = compute_match(
        CandidateInput(salary_expected_min=45_000, salary_expected_max=55_000),
        JobInput(salary_min=50_000, salary_max=60_000),
    )
    assert dim(overlap, "salary").subscore == pytest.approx(0.5)
    blocked = compute_match(
        CandidateInput(
            salary_expected_min=45_000, salary_expected_max=55_000, salary_min_strict=50_000
        ),
        JobInput(salary_min=40_000, salary_max=45_000),
    )
    assert [b.code for b in blocked.blocking_criteria] == ["salary_below_minimum"]


def test_um15_blocker_does_not_zero_score_contract_variant() -> None:
    """UM-15 (variante 13) : bloquant contrat strict sur UM-02.

    ÉCART DOCUMENTÉ vs 13-testing-strategy : la dimension contrat devient
    connue (s=0, w=4) → score = round(100×43/52) = 83, pas 90. Le doc 06 fait
    foi : l'invariant est « bloquant ≠ score nul », vérifié ici.
    """
    candidate = dataclasses.replace(
        um02_candidate(), contract_types=frozenset({"cdi"}), contract_strict=True
    )
    job = dataclasses.replace(um02_job(), contract=Confident("stage"))
    result = compute_match(candidate, job)
    assert [b.code for b in result.blocking_criteria] == ["contract_excluded"]
    assert result.score == 83  # round(100×43/52) — jamais mis à zéro
    assert result.score > 0


def test_um15_blocker_leaves_score_unchanged_salary_variant() -> None:
    """UM-15 (esprit du cas) : bloquant sans dimension scorée → score 90 intact."""
    candidate = dataclasses.replace(um02_candidate(), salary_min_strict=50_000.0)
    job = dataclasses.replace(um02_job(), salary_min=40_000.0, salary_max=45_000.0)
    result = compute_match(candidate, job)
    assert [b.code for b in result.blocking_criteria] == ["salary_below_minimum"]
    assert result.score == 90  # identique à UM-02 : le bloquant est signalé à part
    assert len(result.unknown_dimensions) == 9


def test_um16_blocking_floor_demotes() -> None:
    """UM-16 : politique onsite extraite à 0,65 < 0,7 → avertissement, pas bloquant."""
    candidate = dataclasses.replace(um02_candidate(), remote_pref="required")
    job = dataclasses.replace(um02_job(), remote=Confident("onsite", 0.65))
    result = compute_match(candidate, job)
    assert result.blocking_criteria == ()
    remote = dim(result, "remote")
    assert remote.known
    assert remote.subscore == pytest.approx(0.0)
    demoted = remote.details["demoted_blockings"]
    assert isinstance(demoted, list)
    assert demoted[0]["code"] == "remote_required"


def test_um17_missing_data_is_unknown_not_zero() -> None:
    """UM-17 : offre sans skills_required → k=0, jamais s=0."""
    result = compute_match(perfect_candidate(), JobInput())
    skills = dim(result, "skills_required")
    assert not skills.known
    assert skills.subscore is None
    assert any(u.dimension == "skills_required" for u in result.unknown_dimensions)


def test_um18_scoring_version_stamped() -> None:
    """UM-18 : tout résultat est estampillé avec la version de la config."""
    for result in (
        compute_match(perfect_candidate(), perfect_job()),
        compute_match(CandidateInput(), JobInput()),
    ):
        assert result.scoring_version == "1.1.0"
        assert result.scoring_version == get_config().scoring_version

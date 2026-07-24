"""Agrégation du moteur : renormalisation, low_data, confiance, déterminisme."""

from __future__ import annotations

import dataclasses

import pytest

from app.matching import (
    CandidateInput,
    Confident,
    JobInput,
    JobSkill,
    compute_match,
    get_config,
)
from app.matching.config import ScoringConfig
from tests.unit.matching.factories import (
    perfect_candidate,
    perfect_job,
    um02_candidate,
    um02_job,
)


def test_unknown_dimension_weight_is_redistributed() -> None:
    """Une dimension inconnue est retirée du dénominateur (renormalisation)."""
    # skills 0,8 (w25) + title 1,0 (w15) + location 1,0 (w8) → 43/48.
    base = compute_match(um02_candidate(), um02_job())
    assert base.score == round(100 * 43 / 48) == 90
    # La même paire avec le titre inconnu → 28/33.
    without_title = dataclasses.replace(um02_job(), title_embedding=None)
    result = compute_match(um02_candidate(), without_title)
    assert result.score == round(100 * 28 / 33) == 85


def test_candidate_data_for_unknown_dimension_changes_nothing() -> None:
    """Ajouter une donnée candidat sur une dimension inconnue côté offre ≠ effet."""
    enriched = dataclasses.replace(
        um02_candidate(),
        languages={"en": "C1"},
        seniority="senior",
        total_experience_years=6.0,
        contract_types=frozenset({"cdi"}),
    )
    assert compute_match(enriched, um02_job()).score == (
        compute_match(um02_candidate(), um02_job()).score
    )


def test_dimension_order_invariance() -> None:
    """Le score ne dépend pas de l'ordre des dimensions dans la config."""
    config = get_config()
    reversed_config = ScoringConfig(
        scoring_version=config.scoring_version,
        min_known_weight_ratio=config.min_known_weight_ratio,
        extraction_confidence_floor=config.extraction_confidence_floor,
        blocking_confidence_floor=config.blocking_confidence_floor,
        dimensions=tuple(reversed(config.dimensions)),
        blocking_labels=config.blocking_labels,
        explanation=config.explanation,
        total_weight=config.total_weight,
    )
    candidate, job = perfect_candidate(), um02_job()
    direct = compute_match(candidate, job, config)
    shuffled = compute_match(candidate, job, reversed_config)
    assert direct.score == shuffled.score
    assert direct.confidence == shuffled.confidence
    assert direct.low_data == shuffled.low_data


def test_low_data_boundary_exactly_40_percent_is_not_low() -> None:
    """Σ(w·k) = 40 exactement (skills 25 + title 15) → low_data = false."""
    candidate = dataclasses.replace(um02_candidate(), locations=())
    result = compute_match(candidate, um02_job())
    known_weight = sum(score.weight for score in result.dimension_scores if score.known)
    assert known_weight == pytest.approx(40.0)
    assert not result.low_data


def test_low_data_below_40_percent() -> None:
    """Σ(w·k) = 33 (skills 25 + location 8) → low_data = true."""
    candidate = dataclasses.replace(um02_candidate(), target_titles_embeddings=())
    result = compute_match(candidate, um02_job())
    known_weight = sum(score.weight for score in result.dimension_scores if score.known)
    assert known_weight == pytest.approx(33.0)
    assert result.low_data


def test_nothing_known_yields_zero_scores_and_12_unknowns() -> None:
    result = compute_match(CandidateInput(), JobInput())
    assert result.score == 0
    assert result.confidence == 0
    assert result.low_data
    assert len(result.unknown_dimensions) == 12
    assert all(not score.known for score in result.dimension_scores)


def test_confidence_uses_min_of_sides_via_job_extraction() -> None:
    """q = min(conf candidat, conf offre) ; côté candidat validé → 1,0."""
    job = dataclasses.replace(perfect_job(), seniority=Confident("senior", 0.8))
    result = compute_match(perfect_candidate(), job)
    # Toutes les dimensions à q=1 sauf séniorité (w8, q=0,8) → 100 − 8×0,2 = 98,4.
    assert result.confidence == round(100 - 8 * 0.2) == 98
    assert result.score == 100  # la confiance n'altère jamais le score


def test_score_and_confidence_are_bounded_ints() -> None:
    pairs = [
        (perfect_candidate(), perfect_job()),
        (um02_candidate(), um02_job()),
        (CandidateInput(), JobInput()),
        (perfect_candidate(), JobInput(skills_required=(JobSkill("cobol"),))),
    ]
    for candidate, job in pairs:
        result = compute_match(candidate, job)
        assert isinstance(result.score, int) and 0 <= result.score <= 100
        assert isinstance(result.confidence, int) and 0 <= result.confidence <= 100


def test_determinism_100_runs() -> None:
    """Même entrée ⇒ même sortie, y compris détails et explications (100 runs)."""
    candidate = dataclasses.replace(
        perfect_candidate(),
        remote_pref="required",
        skill_embeddings={"react": (1.0, 0.0)},
    )
    job = dataclasses.replace(
        perfect_job(),
        remote=Confident("onsite", 0.65),  # avertissement rétrogradé
        skills_required=(*perfect_job().skills_required, JobSkill("reactjs")),
        skill_embeddings={"reactjs": (0.9, 0.4358898943540674)},
    )
    reference = compute_match(candidate, job)
    for _ in range(100):
        assert compute_match(candidate, job) == reference


def test_dimension_scores_expose_weight_and_status() -> None:
    result = compute_match(um02_candidate(), um02_job())
    config = get_config()
    assert [score.dimension for score in result.dimension_scores] == [
        d.name for d in config.dimensions
    ]
    for score in result.dimension_scores:
        assert score.weight == config.dimension(score.dimension).weight
        assert score.known == (score.subscore is not None)


def test_unknown_dimensions_carry_reason_and_label() -> None:
    result = compute_match(um02_candidate(), um02_job())
    by_dim = {u.dimension: u for u in result.unknown_dimensions}
    assert by_dim["salary"].reason == "job_missing"
    assert "non précisé dans l'offre" in by_dim["salary"].label
    assert by_dim["preference_boost"].reason == "candidate_missing"
    assert "absent de votre profil" in by_dim["preference_boost"].label

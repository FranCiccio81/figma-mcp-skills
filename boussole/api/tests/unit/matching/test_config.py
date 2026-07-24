"""Chargement de scoring-config.json : cache, version, garde-fous."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.matching import ConfigError, get_config


def test_version_stamped() -> None:
    assert get_config().scoring_version == "1.0.0"


def test_weights_sum_to_100() -> None:
    config = get_config()
    assert config.total_weight == pytest.approx(100.0)
    assert len(config.dimensions) == 12


def test_config_is_cached() -> None:
    assert get_config() is get_config()


def test_thresholds_loaded_from_file() -> None:
    config = get_config()
    assert config.min_known_weight_ratio == pytest.approx(0.4)
    assert config.extraction_confidence_floor == pytest.approx(0.5)
    assert config.blocking_confidence_floor == pytest.approx(0.7)
    assert config.explanation.strength_min_subscore == pytest.approx(0.8)
    assert config.explanation.strength_min_weight == pytest.approx(6.0)
    assert config.explanation.gap_max_subscore == pytest.approx(0.4)


def test_blocking_labels_loaded() -> None:
    labels = get_config().blocking_labels
    assert set(labels) == {
        "location_incompatible",
        "remote_required",
        "language_missing",
        "contract_excluded",
        "salary_below_minimum",
        "sector_excluded",
    }


def test_dimension_lookup_unknown_name() -> None:
    with pytest.raises(ConfigError):
        get_config().dimension("astrologie")


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        get_config(tmp_path / "absent.json")


def test_invalid_json_raises_config_error(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(ConfigError):
        get_config(broken)


def test_config_matches_reference_copy() -> None:
    """La copie sous config/ reste identique à la référence cv-job-matching."""
    api_root = Path(__file__).resolve().parents[3]
    local = (api_root / "config" / "scoring-config.json").read_text(encoding="utf-8")
    reference = api_root.parents[1] / "cv-job-matching" / "scoring-config.json"
    if reference.exists():  # la référence peut ne pas être livrée avec l'API
        assert local == reference.read_text(encoding="utf-8")

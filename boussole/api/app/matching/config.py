"""Chargement et validation de `config/scoring-config.json` (D02).

Le moteur ne contient AUCUN poids ni seuil en dur : tout provient de ce
fichier, chargé une seule fois (cache par chemin) et estampillé
(`scoring_version`) sur chaque résultat.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

__all__ = [
    "ConfigError",
    "DimensionConfig",
    "ExplanationThresholds",
    "ScoringConfig",
    "get_config",
]

#: `<api>/config/scoring-config.json` (ce fichier est dans `<api>/app/matching/`).
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "scoring-config.json"

#: Variable d'environnement qui prime sur le chemin ci-dessus.
#:
#: ``SCORING_CONFIG_PATH`` était déclarée dans ``Settings`` **et** dans
#: ``.env.example``, et lue par personne : le chemin ci-dessus était en dur.
#: Découvert quand l'image Docker s'est révélée ne pas copier ``config/`` —
#: le moteur rendait 500 à la première recherche, et l'exploitant n'avait
#: aucun moyen de contourner par configuration, malgré la variable annoncée.
#:
#: Lue via ``os.environ`` et non via ``app.core.config`` : ce paquet est pur
#: (aucun import applicatif — ``tests/unit/matching/test_purity.py``), et cette
#: propriété vaut plus que l'élégance d'un accès unifié aux réglages.
_CONFIG_PATH_ENV = "SCORING_CONFIG_PATH"


def default_config_path() -> Path:
    """Chemin effectif de la configuration de scoring."""
    surcharge = os.environ.get(_CONFIG_PATH_ENV, "").strip()
    return Path(surcharge) if surcharge else _DEFAULT_CONFIG_PATH


class ConfigError(RuntimeError):
    """Configuration de scoring absente, malformée ou incohérente."""


@dataclass(frozen=True)
class DimensionConfig:
    """Configuration d'une dimension : poids, méthode et paramètres bruts."""

    name: str
    weight: float
    method: str
    params: Mapping[str, object]

    def num(self, key: str) -> float:
        """Paramètre numérique obligatoire."""
        value = self.params.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(f"dimension {self.name!r} : paramètre numérique {key!r} manquant")
        return float(value)

    def mapping(self, key: str) -> Mapping[str, object]:
        """Paramètre objet obligatoire (table / matrice)."""
        value = self.params.get(key)
        if not isinstance(value, Mapping):
            raise ConfigError(f"dimension {self.name!r} : paramètre objet {key!r} manquant")
        return value

    def str_list(self, key: str) -> tuple[str, ...]:
        """Paramètre liste de chaînes obligatoire."""
        value = self.params.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ConfigError(f"dimension {self.name!r} : paramètre liste {key!r} manquant")
        return tuple(value)


@dataclass(frozen=True)
class ExplanationThresholds:
    """Seuils des règles d'explication déterministes (06 §6)."""

    strength_min_subscore: float
    strength_min_weight: float
    gap_max_subscore: float


@dataclass(frozen=True)
class ScoringConfig:
    """Configuration complète du moteur, immuable une fois chargée."""

    scoring_version: str
    min_known_weight_ratio: float
    extraction_confidence_floor: float
    blocking_confidence_floor: float
    dimensions: tuple[DimensionConfig, ...]
    blocking_labels: Mapping[str, str]
    explanation: ExplanationThresholds
    total_weight: float
    #: Seuils de qualité du matching (Spearman, NDCG@10, bloquants), exploités
    #: par :mod:`app.evaluation`. Portés ici pour qu'il n'existe qu'UNE source
    #: de vérité : des seuils recopiés dans le harnais continueraient de
    #: passer sur les anciennes valeurs le jour où on les resserre.
    evaluation_gates: Mapping[str, float] = field(default_factory=dict)

    def dimension(self, name: str) -> DimensionConfig:
        """Configuration d'une dimension par nom (erreur si absente)."""
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        raise ConfigError(f"dimension inconnue : {name!r}")


def _require_number(raw: Mapping[str, object], key: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"champ numérique {key!r} manquant dans scoring-config.json")
    return float(value)


def _parse(raw: Mapping[str, object], path: Path) -> ScoringConfig:
    version = raw.get("scoring_version")
    if not isinstance(version, str) or not version:
        raise ConfigError(f"scoring_version manquant dans {path}")

    dimensions_raw = raw.get("dimensions")
    if not isinstance(dimensions_raw, Mapping) or not dimensions_raw:
        raise ConfigError(f"dimensions manquantes dans {path}")

    dimensions: list[DimensionConfig] = []
    for name, dim_raw in dimensions_raw.items():
        if not isinstance(dim_raw, Mapping):
            raise ConfigError(f"dimension {name!r} malformée dans {path}")
        weight = dim_raw.get("weight")
        method = dim_raw.get("method")
        if isinstance(weight, bool) or not isinstance(weight, int | float) or weight <= 0:
            raise ConfigError(f"dimension {name!r} : poids invalide")
        if not isinstance(method, str) or not method:
            raise ConfigError(f"dimension {name!r} : méthode manquante")
        params = {k: v for k, v in dim_raw.items() if k not in ("weight", "method")}
        dimensions.append(
            DimensionConfig(name=str(name), weight=float(weight), method=method, params=params)
        )

    blocking_raw = raw.get("blocking_rules")
    blocking_labels: dict[str, str] = {}
    if isinstance(blocking_raw, list):
        for rule in blocking_raw:
            if isinstance(rule, Mapping):
                code = rule.get("code")
                description = rule.get("description")
                if isinstance(code, str) and isinstance(description, str):
                    blocking_labels[code] = description

    thresholds_raw = raw.get("explanation_thresholds")
    if not isinstance(thresholds_raw, Mapping):
        raise ConfigError(f"explanation_thresholds manquants dans {path}")
    explanation = ExplanationThresholds(
        strength_min_subscore=_require_number(thresholds_raw, "strength_min_subscore"),
        strength_min_weight=_require_number(thresholds_raw, "strength_min_weight"),
        gap_max_subscore=_require_number(thresholds_raw, "gap_max_subscore"),
    )

    return ScoringConfig(
        scoring_version=version,
        min_known_weight_ratio=_require_number(raw, "min_known_weight_ratio"),
        extraction_confidence_floor=_require_number(raw, "extraction_confidence_floor"),
        blocking_confidence_floor=_require_number(raw, "blocking_confidence_floor"),
        dimensions=tuple(dimensions),
        blocking_labels=blocking_labels,
        explanation=explanation,
        total_weight=sum(dim.weight for dim in dimensions),
        evaluation_gates=_parse_gates(raw.get("evaluation_gates")),
    )


def _parse_gates(raw: object) -> Mapping[str, float]:
    """Seuils d'évaluation — absents = dictionnaire vide, jamais une erreur.

    Le moteur doit tourner sans eux : ils ne servent qu'au harnais de mesure
    (:mod:`app.evaluation`), c'est lui qui refuse de mesurer sans seuil.
    """
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): float(value)
        for key, value in raw.items()
        if not isinstance(value, bool) and isinstance(value, int | float)
    }


@lru_cache(maxsize=8)
def _load(path_str: str) -> ScoringConfig:
    path = Path(path_str)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"scoring-config.json introuvable : {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"scoring-config.json invalide ({path}) : {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"scoring-config.json invalide ({path}) : objet attendu")
    return _parse(raw, path)


def get_config(path: Path | None = None) -> ScoringConfig:
    """Retourne la configuration de scoring (chargée une fois, mise en cache)."""
    return _load(str(path if path is not None else default_config_path()))

"""Moteur de matching déterministe (D02) — agrégation et explication.

Formules (06 §1) :

```
score      = round( 100 × Σ(w·s·k) / Σ(w·k) )      # renormalisation sur le connu
confidence = round( 100 × Σ(w·k·q) / Σ(w) )
```

- `low_data = true` si Σ(w·k) < `min_known_weight_ratio` × Σ(w).
- Un bloquant ne met JAMAIS le score à zéro : signalé séparément (06 §1).
- `scoring_version` estampillé depuis la config chargée.
"""

from __future__ import annotations

from app.matching.config import ScoringConfig, get_config
from app.matching.dimensions import (
    DIMENSION_LABELS,
    UNKNOWN_REASON_LABELS,
    DimensionOutcome,
    score_dimension,
)
from app.matching.models import (
    BlockingCriterion,
    CandidateInput,
    DimensionScore,
    ExplanationFact,
    ExplanationFacts,
    JobInput,
    MatchResult,
    UnknownDimension,
)

__all__ = ["compute_match"]

_SUBSCORE_DECIMALS = 6


def _dimension_label(name: str) -> str:
    return DIMENSION_LABELS.get(name, name)


def _build_explanations(
    config: ScoringConfig,
    outcomes: list[tuple[str, float, DimensionOutcome]],
    blocking_criteria: tuple[BlockingCriterion, ...],
    blocking_dimension: dict[str, str],
) -> ExplanationFacts:
    """Faits d'explication déterministes (06 §6) — bloquants toujours en tête."""
    thresholds = config.explanation
    blocking = tuple(
        ExplanationFact(
            kind="blocking",
            dimension=blocking_dimension.get(criterion.code, ""),
            label=criterion.label,
            data={"code": criterion.code},
        )
        for criterion in blocking_criteria
    )
    strengths: list[ExplanationFact] = []
    gaps: list[ExplanationFact] = []
    uncertain: list[ExplanationFact] = []
    for name, weight, outcome in outcomes:
        label = _dimension_label(name)
        if not outcome.known:
            reason = outcome.unknown_reason or "unknown"
            uncertain.append(
                ExplanationFact(
                    kind="uncertain",
                    dimension=name,
                    label=f"{label} : {UNKNOWN_REASON_LABELS.get(reason, reason)}",
                    data={"reason": reason, **outcome.details},
                )
            )
            continue
        subscore = outcome.subscore if outcome.subscore is not None else 0.0
        if (
            subscore >= thresholds.strength_min_subscore
            and weight >= thresholds.strength_min_weight
        ):
            strengths.append(
                ExplanationFact(
                    kind="strength",
                    dimension=name,
                    label=label,
                    data={"subscore": round(subscore, _SUBSCORE_DECIMALS), **outcome.details},
                )
            )
        elif subscore <= thresholds.gap_max_subscore:
            gaps.append(
                ExplanationFact(
                    kind="gap",
                    dimension=name,
                    label=label,
                    data={"subscore": round(subscore, _SUBSCORE_DECIMALS), **outcome.details},
                )
            )
    return ExplanationFacts(
        blocking=blocking,
        strengths=tuple(strengths),
        gaps=tuple(gaps),
        uncertain=tuple(uncertain),
    )


def compute_match(
    candidate: CandidateInput, job: JobInput, config: ScoringConfig | None = None
) -> MatchResult:
    """Calcule le résultat de matching pour une paire (profil, offre).

    Fonction pure et déterministe : aucun appel réseau, aucune horloge,
    aucun aléa — mêmes entrées ⇒ même sortie.
    """
    cfg = config if config is not None else get_config()

    outcomes: list[tuple[str, float, DimensionOutcome]] = []
    for dim in cfg.dimensions:
        outcomes.append((dim.name, dim.weight, score_dimension(dim, cfg, candidate, job)))

    total_weight = cfg.total_weight
    known_weight = 0.0
    weighted_subscores = 0.0
    weighted_quality = 0.0
    dimension_scores: list[DimensionScore] = []
    unknown_dimensions: list[UnknownDimension] = []
    blocking_codes: list[str] = []
    blocking_dimension: dict[str, str] = {}

    for name, weight, outcome in outcomes:
        details = dict(outcome.details)
        if outcome.demoted_blockings:
            details["demoted_blockings"] = outcome.demoted_blockings
        if outcome.known and outcome.subscore is not None:
            known_weight += weight
            weighted_subscores += weight * outcome.subscore
            weighted_quality += weight * outcome.q
            subscore: float | None = round(outcome.subscore, _SUBSCORE_DECIMALS)
        else:
            subscore = None
            reason = outcome.unknown_reason or "unknown"
            unknown_dimensions.append(
                UnknownDimension(
                    dimension=name,
                    reason=reason,
                    label=(
                        f"{_dimension_label(name)} : "
                        f"{UNKNOWN_REASON_LABELS.get(reason, reason)}"
                    ),
                )
            )
        dimension_scores.append(
            DimensionScore(
                dimension=name,
                subscore=subscore,
                weight=weight,
                known=outcome.known,
                details=details,
            )
        )
        for code in outcome.blocking:
            if code not in blocking_codes:
                blocking_codes.append(code)
                blocking_dimension[code] = name

    score = round(100.0 * weighted_subscores / known_weight) if known_weight > 0.0 else 0
    confidence = round(100.0 * weighted_quality / total_weight) if total_weight > 0.0 else 0
    low_data = known_weight < cfg.min_known_weight_ratio * total_weight

    blocking_criteria = tuple(
        BlockingCriterion(code=code, label=cfg.blocking_labels.get(code, code))
        for code in blocking_codes
    )
    explanation_facts = _build_explanations(cfg, outcomes, blocking_criteria, blocking_dimension)

    return MatchResult(
        score=score,
        confidence=confidence,
        low_data=low_data,
        blocking_criteria=blocking_criteria,
        unknown_dimensions=tuple(unknown_dimensions),
        dimension_scores=tuple(dimension_scores),
        explanation_facts=explanation_facts,
        scoring_version=cfg.scoring_version,
    )

"""Calcul des 12 dimensions du matching (06 §2) — fonctions pures.

Chaque dimension rend un ``DimensionOutcome`` : sous-score s ∈ [0,1],
statut connu/inconnu (k), fiabilité q = min(conf candidat, conf offre)
(côté candidat : 1,0 — profil validé), détails nominatifs, bloquants
détectés et bloquants rétrogradés (confiance < ``blocking_confidence_floor``).

Aucune valeur de poids ou de seuil en dur : tout vient de la config.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from app.matching.config import ConfigError, DimensionConfig, ScoringConfig
from app.matching.models import CandidateInput, JobInput, Vector
from app.matching.similarity import cosine_similarity, haversine_km

__all__ = [
    "CANDIDATE_MISSING",
    "DIMENSION_LABELS",
    "JOB_MISSING",
    "LOW_CONFIDENCE",
    "UNCONVERTIBLE",
    "UNKNOWN_REASON_LABELS",
    "DimensionOutcome",
    "score_dimension",
]

# Raisons d'inconnue (unknown_dimensions[].reason).
JOB_MISSING = "job_missing"
CANDIDATE_MISSING = "candidate_missing"
LOW_CONFIDENCE = "low_confidence"
UNCONVERTIBLE = "unconvertible_value"

UNKNOWN_REASON_LABELS: Mapping[str, str] = {
    JOB_MISSING: "non précisé dans l'offre",
    CANDIDATE_MISSING: "absent de votre profil",
    LOW_CONFIDENCE: "extraction trop incertaine pour être utilisée",
    UNCONVERTIBLE: "valeur non convertible (devise non supportée)",
}

DIMENSION_LABELS: Mapping[str, str] = {
    "skills_required": "Compétences indispensables",
    "skills_nice": "Compétences complémentaires",
    "title_similarity": "Similarité du métier",
    "seniority": "Séniorité",
    "experience_years": "Années d'expérience",
    "sector": "Secteur",
    "location": "Localisation",
    "remote": "Télétravail",
    "languages": "Langues",
    "contract": "Type de contrat",
    "salary": "Salaire",
    "preference_boost": "Préférences fines",
}

# CECRL : natif = C2 (06 §2.9).
_CEFR_RANKS: Mapping[str, int] = {
    "a1": 1,
    "a2": 2,
    "b1": 3,
    "b2": 4,
    "c1": 5,
    "c2": 6,
    "native": 6,
    "natif": 6,
}

_SALARY_PERIOD_FACTORS: Mapping[str, float] = {"year": 1.0, "month": 12.0}


@dataclass
class DimensionOutcome:
    """Résultat interne d'une dimension avant agrégation par le moteur."""

    known: bool
    subscore: float | None = None
    q: float = 1.0
    details: dict[str, object] = field(default_factory=dict)
    unknown_reason: str | None = None
    blocking: list[str] = field(default_factory=list)
    demoted_blockings: list[dict[str, object]] = field(default_factory=list)

    def demote(self, code: str, confidence: float) -> None:
        """Bloquant rétrogradé en avertissement (confiance < plancher bloquant)."""
        self.demoted_blockings.append(
            {
                "code": code,
                "confidence": confidence,
                "label": "avertissement possible — extraction incertaine",
            }
        )


def _unknown(reason: str, **details: object) -> DimensionOutcome:
    return DimensionOutcome(known=False, unknown_reason=reason, details=dict(details))


def _norm(label: str) -> str:
    return label.strip().casefold()


def _norm_set(labels: Iterable[str]) -> frozenset[str]:
    return frozenset(_norm(label) for label in labels)


def _apply_blocker(
    outcome: DimensionOutcome, code: str, confidence: float, config: ScoringConfig
) -> None:
    """Bloquant réel si confiance ≥ plancher, sinon rétrogradé (06 §3)."""
    if confidence >= config.blocking_confidence_floor:
        outcome.blocking.append(code)
    else:
        outcome.demote(code, confidence)


def _cefr_rank(level: str) -> int:
    rank = _CEFR_RANKS.get(_norm(level))
    if rank is None:
        raise ValueError(f"niveau CECRL inconnu : {level!r}")
    return rank


# ------------------------------------------------------------------ méthodes


def _coverage(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Couverture de compétences : crédit exact / proche / absent (06 §2.1-2.2)."""
    items = job.skills_required if dim.name == "skills_required" else job.skills_nice
    if not items:
        return _unknown(JOB_MISSING)

    floor = config.extraction_confidence_floor
    retained = [item for item in items if item.confidence >= floor]
    dropped = [item.label for item in items if item.confidence < floor]
    if not retained:
        return _unknown(LOW_CONFIDENCE, dropped_low_confidence=dropped)

    exact_credit = dim.num("exact_credit")
    related_credit = dim.num("related_credit")
    related_threshold = dim.num("related_similarity_threshold")

    candidate_skills = _norm_set(candidate.skills)
    # Seules les compétences réellement présentes au profil peuvent donner un
    # crédit « proche » — un embedding orphelin n'est pas une compétence.
    candidate_embeddings: dict[str, Vector] = {
        _norm(label): vector
        for label, vector in candidate.skill_embeddings.items()
        if _norm(label) in candidate_skills
    }
    job_embeddings: dict[str, Vector] = {
        _norm(label): vector for label, vector in job.skill_embeddings.items()
    }

    matched: list[str] = []
    related: list[dict[str, object]] = []
    missing: list[str] = []
    credits = 0.0
    for item in retained:
        label = _norm(item.label)
        if label in candidate_skills:
            credits += exact_credit
            matched.append(item.label)
            continue
        # Crédit « proche » uniquement si les embeddings des deux libellés sont
        # fournis 🟡 — sinon match exact seulement.
        required_vector = job_embeddings.get(label)
        best_label: str | None = None
        best_similarity = -1.0
        if required_vector is not None:
            for cand_label, cand_vector in candidate_embeddings.items():
                similarity = cosine_similarity(required_vector, cand_vector)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_label = cand_label
        if best_label is not None and best_similarity >= related_threshold:
            credits += related_credit
            related.append(
                {
                    "required": item.label,
                    "via": best_label,
                    "similarity": round(best_similarity, 4),
                }
            )
        else:
            missing.append(item.label)

    subscore = credits / len(retained)
    q = sum(item.confidence for item in retained) / len(retained)
    details: dict[str, object] = {"matched": matched, "related": related, "missing": missing}
    if dropped:
        details["dropped_low_confidence"] = dropped
    return DimensionOutcome(known=True, subscore=subscore, q=q, details=details)


def _embedding_piecewise(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Similarité métier : max des cosinus + mapping affine par morceaux (06 §2.3)."""
    if job.title_embedding is None:
        return _unknown(JOB_MISSING)
    if not candidate.target_titles_embeddings:
        # Sans embeddings d'intitulés (cibles ou derniers postes) → k=0.
        return _unknown(CANDIDATE_MISSING)

    similarity = max(
        cosine_similarity(vector, job.title_embedding)
        for vector in candidate.target_titles_embeddings
    )
    zero_below = dim.num("zero_below")
    one_above = dim.num("one_above")
    if similarity <= zero_below:
        subscore = 0.0
    elif similarity >= one_above:
        subscore = 1.0
    else:
        subscore = (similarity - zero_below) / (one_above - zero_below)
    return DimensionOutcome(
        known=True, subscore=subscore, q=1.0, details={"similarity": round(similarity, 4)}
    )


def _ordinal_table(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Séniorité : écart sur l'échelle ordinale → table de scores (06 §2.4)."""
    if job.seniority is None:
        return _unknown(JOB_MISSING)
    if job.seniority.confidence < config.extraction_confidence_floor:
        return _unknown(LOW_CONFIDENCE, extracted=job.seniority.value)
    if candidate.seniority is None:
        return _unknown(CANDIDATE_MISSING)

    levels = dim.str_list("levels")
    try:
        candidate_index = levels.index(_norm(candidate.seniority))
        job_index = levels.index(_norm(job.seniority.value))
    except ValueError as exc:
        raise ValueError(
            f"niveau de séniorité hors échelle {levels!r} : "
            f"candidat={candidate.seniority!r}, offre={job.seniority.value!r}"
        ) from exc

    cap = int(dim.num("delta_cap"))
    delta = max(-cap, min(cap, job_index - candidate_index))
    table = dim.mapping("delta_scores")
    raw = table.get(str(delta))
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ConfigError(f"delta_scores : entrée {delta!r} manquante")
    return DimensionOutcome(
        known=True,
        subscore=float(raw),
        q=job.seniority.confidence,
        details={
            "candidate_level": _norm(candidate.seniority),
            "job_level": _norm(job.seniority.value),
            "delta": delta,
        },
    )


def _range_fit(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Années d'expérience : ajustement à la fourchette de l'offre (06 §2.5)."""
    if job.experience_min is None and job.experience_max is None:
        return _unknown(JOB_MISSING)
    if job.experience_confidence < config.extraction_confidence_floor:
        return _unknown(LOW_CONFIDENCE)
    if candidate.total_experience_years is None:
        return _unknown(CANDIDATE_MISSING)

    years = candidate.total_experience_years
    minimum = job.experience_min
    maximum = job.experience_max
    if minimum is not None and minimum > 0 and years < minimum:
        # En dessous du minimum : s = max(0, années/min − offset), borné à 1.
        subscore = min(1.0, max(0.0, years / minimum - dim.num("below_min_slope_offset")))
    elif maximum is not None and years > maximum:
        # Au-dessus du maximum : s = max(plancher, 1 − pénalité×(années−max)).
        subscore = max(
            dim.num("above_max_floor"),
            1.0 - dim.num("above_max_penalty_per_year") * (years - maximum),
        )
    else:
        subscore = 1.0
    return DimensionOutcome(
        known=True,
        subscore=subscore,
        q=job.experience_confidence,
        details={"candidate_years": years, "job_min": minimum, "job_max": maximum},
    )


def _sector(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Secteur : catégoriel préféré / vécu / adjacent / autre + exclusion (06 §2.6)."""
    if job.sector is None:
        return _unknown(JOB_MISSING)
    if job.sector.confidence < config.extraction_confidence_floor:
        return _unknown(LOW_CONFIDENCE, extracted=job.sector.value)

    sector = _norm(job.sector.value)
    excluded = _norm_set(candidate.sectors_excluded)
    preferred = _norm_set(candidate.sectors_preferred)
    experienced = _norm_set(candidate.sectors_experienced)
    parents = {_norm(key): _norm(value) for key, value in candidate.sector_parents.items()}

    # Exclusion : bloquant même si le candidat n'a pas de secteurs positifs.
    blocked = sector in excluded
    if not preferred and not experienced:
        outcome = _unknown(CANDIDATE_MISSING, job_sector=sector)
        if blocked:
            _apply_blocker(outcome, "sector_excluded", job.sector.confidence, config)
        return outcome

    scores = dim.mapping("scores")

    def _score_of(key: str) -> float:
        raw = scores.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise ConfigError(f"sector.scores : entrée {key!r} manquante")
        return float(raw)

    if blocked:
        # 🟡 Sous-score d'un secteur exclu non spécifié par 06 : 0,0 retenu
        # (le bloquant est signalé séparément et ne met pas le score à zéro).
        outcome = DimensionOutcome(
            known=True,
            subscore=0.0,
            q=job.sector.confidence,
            details={"job_sector": sector, "category": "excluded"},
        )
        _apply_blocker(outcome, "sector_excluded", job.sector.confidence, config)
        return outcome

    job_parent = _norm(job.sector_parent) if job.sector_parent is not None else None
    adjacent = job_parent is not None and any(
        parents.get(known_sector) == job_parent for known_sector in preferred | experienced
    )
    if sector in preferred:
        category = "preferred"
    elif sector in experienced:
        category = "experienced"
    elif adjacent:
        category = "adjacent"
    else:
        category = "other"
    return DimensionOutcome(
        known=True,
        subscore=_score_of(category),
        q=job.sector.confidence,
        details={"job_sector": sector, "category": category},
    )


def _geo_decay(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Localisation : décroissance linéaire rayon → 2×rayon (06 §2.7)."""
    floor = config.extraction_confidence_floor
    remote = job.remote if job.remote is not None and job.remote.confidence >= floor else None

    if remote is not None and remote.value == "full_remote":
        # 🟡 Zone (pays/UE) supposée compatible — non modélisée au MVP.
        return DimensionOutcome(
            known=True, subscore=1.0, q=remote.confidence, details={"mode": "full_remote"}
        )

    if not job.locations:
        # Donnée critique : inconnue mise en avant côté UI.
        return _unknown(JOB_MISSING, critical=True)
    if job.location_confidence < floor:
        return _unknown(LOW_CONFIDENCE)
    if not candidate.locations:
        return _unknown(CANDIDATE_MISSING)

    zero_multiplier = dim.num("zero_at_radius_multiplier")
    default_radius = dim.num("default_radius_km")
    best_subscore = 0.0
    best_distance: float | None = None
    best_radius = default_radius
    within_reach = False  # au moins une paire avec d ≤ zero_multiplier × rayon
    for cand_loc in candidate.locations:
        radius = cand_loc.radius_km if cand_loc.radius_km is not None else default_radius
        for job_loc in job.locations:
            distance = haversine_km(cand_loc.lat, cand_loc.lon, job_loc.lat, job_loc.lon)
            if distance <= radius:
                subscore = 1.0
            elif distance <= zero_multiplier * radius:
                # Décroissance linéaire 1→0 entre rayon et zero_multiplier×rayon.
                span = (zero_multiplier - 1.0) * radius
                subscore = (zero_multiplier * radius - distance) / span
            else:
                subscore = 0.0
            within_reach = within_reach or distance <= zero_multiplier * radius
            if best_distance is None or subscore > best_subscore or (
                subscore == best_subscore and distance < best_distance
            ):
                best_subscore = subscore
                best_distance = distance
                best_radius = radius

    outcome = DimensionOutcome(
        known=True,
        subscore=best_subscore,
        q=job.location_confidence,
        details={
            "distance_km": round(best_distance, 2) if best_distance is not None else None,
            "radius_km": best_radius,
            "mode": remote.value if remote is not None else "unknown_policy",
        },
    )
    if not within_reach and remote is not None and remote.value == "onsite":
        # Sur-site strict hors zone : d > zero_multiplier × rayon partout (06 §3).
        _apply_blocker(outcome, "location_incompatible", remote.confidence, config)
    return outcome


def _matrix(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Télétravail : matrice préférence candidat × politique offre (06 §2.8)."""
    if job.remote is None:
        return _unknown(JOB_MISSING)
    if job.remote.confidence < config.extraction_confidence_floor:
        return _unknown(LOW_CONFIDENCE, extracted=job.remote.value)
    if candidate.remote_pref is None:
        return _unknown(CANDIDATE_MISSING)

    matrix = dim.mapping("matrix")
    row = matrix.get(candidate.remote_pref)
    if not isinstance(row, Mapping):
        raise ConfigError(f"remote.matrix : ligne {candidate.remote_pref!r} manquante")
    policy = _norm(job.remote.value)
    raw = row.get(policy)
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ConfigError(f"remote.matrix : colonne {policy!r} manquante")

    outcome = DimensionOutcome(
        known=True,
        subscore=float(raw),
        q=job.remote.confidence,
        details={"candidate_pref": candidate.remote_pref, "job_policy": policy},
    )
    if candidate.remote_pref == "required" and policy == "onsite":
        _apply_blocker(outcome, "remote_required", job.remote.confidence, config)
    return outcome


def _per_requirement_mean(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Langues : score par exigence puis moyenne (06 §2.9)."""
    if not job.languages_required:
        return _unknown(JOB_MISSING)
    floor = config.extraction_confidence_floor
    retained = [lang for lang in job.languages_required if lang.confidence >= floor]
    dropped = [lang.code for lang in job.languages_required if lang.confidence < floor]
    if not retained:
        return _unknown(LOW_CONFIDENCE, dropped_low_confidence=dropped)

    meets = dim.num("meets_level")
    one_below = dim.num("one_level_below")
    missing_score = dim.num("missing_or_lower")
    candidate_levels = {_norm(code): level for code, level in candidate.languages.items()}

    outcome = DimensionOutcome(known=True, q=1.0)
    per_language: list[dict[str, object]] = []
    total = 0.0
    for requirement in retained:
        required_rank = _cefr_rank(requirement.level)
        candidate_level = candidate_levels.get(_norm(requirement.code))
        if candidate_level is None:
            item_score = missing_score
            # Langue absente du profil → bloquant (gated par la confiance).
            _apply_blocker(outcome, "language_missing", requirement.confidence, config)
        else:
            candidate_rank = _cefr_rank(candidate_level)
            if candidate_rank >= required_rank:
                item_score = meets
            elif candidate_rank == required_rank - 1:
                item_score = one_below
            else:
                item_score = missing_score
                _apply_blocker(outcome, "language_missing", requirement.confidence, config)
        total += item_score
        per_language.append(
            {
                "code": requirement.code,
                "required_level": requirement.level,
                "candidate_level": candidate_level,
                "score": item_score,
            }
        )

    outcome.subscore = total / len(retained)
    outcome.q = sum(lang.confidence for lang in retained) / len(retained)
    outcome.details = {"languages": per_language}
    if dropped:
        outcome.details["dropped_low_confidence"] = dropped
    return outcome


def _membership(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Type de contrat : appartenance aux types acceptés (06 §2.10)."""
    if job.contract is None:
        return _unknown(JOB_MISSING)
    if job.contract.confidence < config.extraction_confidence_floor:
        return _unknown(LOW_CONFIDENCE, extracted=job.contract.value)
    if not candidate.contract_types:
        return _unknown(CANDIDATE_MISSING)

    contract = _norm(job.contract.value)
    accepted = _norm_set(candidate.contract_types)
    outcome = DimensionOutcome(
        known=True,
        q=job.contract.confidence,
        details={"job_contract": contract, "accepted": sorted(accepted)},
    )
    if contract in accepted:
        outcome.subscore = dim.num("in_accepted")
    elif candidate.contract_strict:
        outcome.subscore = 0.0
        _apply_blocker(outcome, "contract_excluded", job.contract.confidence, config)
    else:
        outcome.subscore = dim.num("not_accepted_soft")
    return outcome


def _annualized_range(
    minimum: float | None, maximum: float | None, factor: float, padding: float
) -> tuple[float, float]:
    """Fourchette annualisée, bornes ouvertes complétées par ±padding (06 §2.11)."""
    if minimum is not None and maximum is not None:
        return minimum * factor, maximum * factor
    if minimum is not None:
        annual = minimum * factor
        return annual, annual * (1.0 + padding)
    if maximum is not None:
        annual = maximum * factor
        return annual * (1.0 - padding), annual
    raise ValueError("fourchette vide")  # protégé par les appels amont


def _range_overlap(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Salaire : recouvrement des fourchettes annualisées (06 §2.11)."""
    if job.salary_min is None and job.salary_max is None:
        return _unknown(JOB_MISSING)  # « salaire non communiqué » (cas majoritaire)
    if job.salary_confidence < config.extraction_confidence_floor:
        return _unknown(LOW_CONFIDENCE)

    factor = _SALARY_PERIOD_FACTORS.get(job.salary_period)
    if factor is None:
        raise ValueError(f"période de salaire non supportée : {job.salary_period!r}")
    if job.salary_currency.upper() != "EUR":
        # 🟡 Taux de change figés par release non embarqués au MVP → inconnu.
        return _unknown(UNCONVERTIBLE, currency=job.salary_currency)

    padding = dim.num("open_range_padding_ratio")
    job_min, job_max = _annualized_range(job.salary_min, job.salary_max, factor, padding)

    def _with_strict_blocker(outcome: DimensionOutcome) -> DimensionOutcome:
        # Bloquant évaluable dès que minimum strict + salaire offre sont connus,
        # même sans fourchette souhaitée (06 §3 : donnée requise des deux côtés).
        strict = candidate.salary_min_strict
        if strict is not None and job_max < strict:
            _apply_blocker(outcome, "salary_below_minimum", job.salary_confidence, config)
        return outcome

    if candidate.salary_expected_min is None and candidate.salary_expected_max is None:
        return _with_strict_blocker(_unknown(CANDIDATE_MISSING))

    cand_min, cand_max = _annualized_range(
        candidate.salary_expected_min, candidate.salary_expected_max, 1.0, padding
    )
    width = cand_max - cand_min
    overlap = max(0.0, min(cand_max, job_max) - max(cand_min, job_min))
    if width <= 0.0:
        subscore = 1.0 if job_min <= cand_min <= job_max else 0.0
    else:
        subscore = min(1.0, overlap / width)
    outcome = DimensionOutcome(
        known=True,
        subscore=subscore,
        q=job.salary_confidence,
        details={
            "candidate_range_eur_year": [cand_min, cand_max],
            "job_range_eur_year": [job_min, job_max],
            "overlap_eur_year": overlap,
        },
    )
    return _with_strict_blocker(outcome)


def _preference_boost(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Préférences fines : entreprise cible ou mot-clé privilégié (06 §2.12)."""
    if not candidate.target_companies and not candidate.keywords:
        return _unknown(CANDIDATE_MISSING)
    if job.company_name is None and job.description_text is None:
        return _unknown(JOB_MISSING)

    scores = dim.mapping("scores")

    def _score_of(key: str) -> float:
        raw = scores.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise ConfigError(f"preference_boost.scores : entrée {key!r} manquante")
        return float(raw)

    company = _norm(job.company_name) if job.company_name is not None else None
    if company is not None and company in _norm_set(candidate.target_companies):
        return DimensionOutcome(
            known=True,
            subscore=_score_of("target_company"),
            q=1.0,
            details={"matched_company": job.company_name},
        )
    description = job.description_text.casefold() if job.description_text is not None else ""
    matched_keywords = [kw for kw in candidate.keywords if _norm(kw) in description]
    if matched_keywords:
        return DimensionOutcome(
            known=True,
            subscore=_score_of("keyword_match"),
            q=1.0,
            details={"matched_keywords": matched_keywords},
        )
    return DimensionOutcome(known=True, subscore=_score_of("none"), q=1.0, details={})


# ------------------------------------------------------- routage par méthode


def score_dimension(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    """Calcule une dimension en routant par le champ ``method`` de la config."""
    scorer = _METHODS.get(dim.method)
    if scorer is None:
        raise ConfigError(f"méthode de scoring inconnue : {dim.method!r} ({dim.name})")
    expected = _EXPECTED_METHODS.get(dim.name)
    if expected is not None and expected != dim.method:
        raise ConfigError(
            f"dimension {dim.name!r} : méthode {dim.method!r} incompatible "
            f"(attendue : {expected!r})"
        )
    return scorer(dim, config, candidate, job)


# Une méthode = une fonction de calcul (routage par `method`) ; `categorical`
# est partagée par `sector` et `preference_boost` via la table de liaison.
def _categorical(
    dim: DimensionConfig, config: ScoringConfig, candidate: CandidateInput, job: JobInput
) -> DimensionOutcome:
    if dim.name == "sector":
        return _sector(dim, config, candidate, job)
    if dim.name == "preference_boost":
        return _preference_boost(dim, config, candidate, job)
    raise ConfigError(f"méthode categorical non liée pour la dimension {dim.name!r}")


_ScorerFn = Callable[[DimensionConfig, ScoringConfig, CandidateInput, JobInput], DimensionOutcome]

_METHODS: Mapping[str, _ScorerFn] = {
    "coverage": _coverage,
    "embedding_piecewise": _embedding_piecewise,
    "ordinal_table": _ordinal_table,
    "range_fit": _range_fit,
    "categorical": _categorical,
    "geo_decay": _geo_decay,
    "matrix": _matrix,
    "per_requirement_mean": _per_requirement_mean,
    "membership": _membership,
    "range_overlap": _range_overlap,
}

# Garde-fou : chaque dimension connue doit être servie par la méthode attendue.
_EXPECTED_METHODS: Mapping[str, str] = {
    "skills_required": "coverage",
    "skills_nice": "coverage",
    "title_similarity": "embedding_piecewise",
    "seniority": "ordinal_table",
    "experience_years": "range_fit",
    "sector": "categorical",
    "location": "geo_decay",
    "remote": "matrix",
    "languages": "per_requirement_mean",
    "contract": "membership",
    "salary": "range_overlap",
    "preference_boost": "categorical",
}

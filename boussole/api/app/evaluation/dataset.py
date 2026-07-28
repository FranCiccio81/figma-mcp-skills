"""Chargement du jeu d'évaluation et construction des entrées du moteur.

Le jeu associe des **profils candidats** au corpus d'offres, avec pour chaque
paire une **pertinence attendue** de 0 à 3 et l'indication d'un éventuel
critère rédhibitoire. C'est le seul endroit du projet où figure un jugement
« cette offre convient à ce profil » ; tout le reste est calculé.

⚠️ **Statut du jeu livré.** Les annotations de ``evaluation-set.json`` sont
des **cas de référence construits**, du même statut que UM-01…UM-18 : ils
disent ce que le moteur DOIT faire sur des situations choisies pour être
discriminantes. Ce ne sont **pas** des annotations humaines d'offres réelles
par des recruteurs, et elles ne peuvent donc pas répondre à « le matching
est-il bon en vrai ». Elles font tourner l'instrument et prouvent qu'il
mesure ; répondre à la question demande Q19/Q20/Q47 (annotateurs, budget,
protocole). Confondre les deux serait exactement le genre d'hypothèse
présentée comme un fait que le produit s'interdit.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.matching.models import (
    CandidateInput,
    CandidateLocation,
    Confident,
    JobInput,
    JobLanguage,
    JobLocation,
    JobSkill,
    RemotePreference,
    Vector,
)

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "demo-corpus"
DEFAULT_JOBS_PATH = CONFIG_DIR / "jobs.json"
DEFAULT_EVALUATION_PATH = CONFIG_DIR / "evaluation-set.json"

#: Pertinence maximale d'une annotation (échelle 0–3, gains NDCG en 2^g − 1).
MAX_RELEVANCE = 3


class DatasetError(ValueError):
    """Jeu d'évaluation incohérent — refusé plutôt que mesuré de travers."""


@dataclass(frozen=True, slots=True)
class Annotation:
    """Jugement attendu pour une paire (candidat, offre)."""

    job_ref: str
    relevance: int
    blocking_expected: bool = False
    note: str = ""


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """Un profil candidat et ses annotations sur le corpus."""

    candidate_id: str
    label: str
    candidate: CandidateInput
    annotations: tuple[Annotation, ...]


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    """Corpus d'offres + cas d'évaluation, tous deux vérifiés cohérents."""

    jobs: dict[str, JobInput]
    cases: tuple[EvaluationCase, ...]
    corpus_version: str
    dataset_version: str


def load_dataset(
    jobs_path: Path | None = None,
    evaluation_path: Path | None = None,
    embedder: Any | None = None,
) -> EvaluationDataset:
    """Charge corpus et annotations, et refuse tout écart entre les deux.

    ``embedder`` : objet exposant ``embed_texts`` (le provider d'embeddings
    du projet). Sans lui, ni les intitulés ni les compétences ne portent de
    vecteur : la dimension « similarité d'intitulé » — 15 % du poids — reste
    inconnue et l'évaluation ne mesure alors qu'une partie du moteur. C'est
    autorisé (utile pour isoler un défaut), mais jamais silencieux : le
    rapport le signale.
    """
    corpus = json.loads((jobs_path or DEFAULT_JOBS_PATH).read_text(encoding="utf-8"))
    evaluation = json.loads(
        (evaluation_path or DEFAULT_EVALUATION_PATH).read_text(encoding="utf-8")
    )

    textes_intitules = [f"{item['title']}. {item['description'][:400]}" for item in corpus["jobs"]]
    vecteurs = _embed(embedder, textes_intitules)

    jobs = {
        str(item["external_ref"]): _to_job_input(item, vecteurs[index])
        for index, item in enumerate(corpus["jobs"])
    }

    cases = tuple(
        _to_case(raw, jobs, embedder) for raw in evaluation["cases"]
    )
    if not cases:
        raise DatasetError("jeu d'évaluation vide")

    return EvaluationDataset(
        jobs=jobs,
        cases=cases,
        corpus_version=str(corpus.get("corpus_version", "0")),
        dataset_version=str(evaluation.get("dataset_version", "0")),
    )


def _embed(embedder: Any | None, textes: list[str]) -> list[Vector | None]:
    if embedder is None:
        return [None] * len(textes)
    return [tuple(vecteur) for vecteur in embedder.embed_texts(textes)]


def _to_job_input(item: dict[str, Any], title_embedding: Vector | None) -> JobInput:
    locations = tuple(
        JobLocation(lat=float(loc["lat"]), lon=float(loc["lon"]))
        for loc in item.get("locations", [])
        if loc.get("lat") is not None and loc.get("lon") is not None
    )
    return JobInput(
        skills_required=tuple(JobSkill(label=s) for s in item.get("skills_required", [])),
        skills_nice=tuple(JobSkill(label=s) for s in item.get("skills_nice", [])),
        title_embedding=title_embedding,
        seniority=_confident(item.get("seniority")),
        experience_min=item.get("experience_min"),
        experience_max=item.get("experience_max"),
        sector=_confident(item.get("sector")),
        locations=locations,
        remote=_confident(_remote_policy(item.get("remote"))),
        languages_required=tuple(
            JobLanguage(code=code, level=level) for code, level in item.get("languages", [])
        ),
        contract=_confident(item.get("contract")),
        salary_min=item.get("salary_min"),
        salary_max=item.get("salary_max"),
        salary_period=item.get("salary_period", "year") if
        item.get("salary_period") in ("year", "month") else "year",
        salary_currency=item.get("salary_currency", "EUR"),
        company_name=item.get("company"),
        description_text=item.get("description"),
    )


def _remote_policy(value: str | None) -> str | None:
    """Vocabulaire du corpus → vocabulaire du moteur."""
    return {"full": "full_remote", "hybrid": "hybrid", "onsite": "onsite"}.get(value or "")


def _confident(value: str | None) -> Confident | None:
    return None if not value else Confident(value=value, confidence=1.0)


def _to_case(
    raw: dict[str, Any], jobs: dict[str, JobInput], embedder: Any | None
) -> EvaluationCase:
    annotations = tuple(
        Annotation(
            job_ref=str(a["job_ref"]),
            relevance=int(a["relevance"]),
            blocking_expected=bool(a.get("blocking_expected", False)),
            note=str(a.get("note", "")),
        )
        for a in raw["annotations"]
    )
    _check_annotations(raw["candidate_id"], annotations, jobs)
    return EvaluationCase(
        candidate_id=str(raw["candidate_id"]),
        label=str(raw.get("label", raw["candidate_id"])),
        candidate=_to_candidate_input(raw["profile"], embedder),
        annotations=annotations,
    )


def _check_annotations(
    candidate_id: str, annotations: tuple[Annotation, ...], jobs: dict[str, JobInput]
) -> None:
    """Le jeu doit couvrir TOUT le corpus, sans doublon ni référence morte.

    Une couverture partielle biaiserait NDCG en silence : les offres non
    annotées disparaîtraient du classement au lieu de compter pour 0, et un
    moteur qui remonte une offre oubliée en tête ne serait jamais pénalisé.
    """
    refs = [a.job_ref for a in annotations]
    doublons = {ref for ref in refs if refs.count(ref) > 1}
    if doublons:
        raise DatasetError(f"{candidate_id} : offres annotées deux fois {sorted(doublons)}")

    inconnues = set(refs) - set(jobs)
    if inconnues:
        raise DatasetError(
            f"{candidate_id} : annotations sur des offres absentes {sorted(inconnues)}"
        )

    manquantes = set(jobs) - set(refs)
    if manquantes:
        raise DatasetError(
            f"{candidate_id} : offres du corpus non annotées {sorted(manquantes)} — "
            "une couverture partielle fausse NDCG sans le dire"
        )

    hors_echelle = [a.relevance for a in annotations if not 0 <= a.relevance <= MAX_RELEVANCE]
    if hors_echelle:
        raise DatasetError(f"{candidate_id} : pertinences hors de 0–{MAX_RELEVANCE} {hors_echelle}")


def _to_candidate_input(profile: dict[str, Any], embedder: Any | None) -> CandidateInput:
    titres = list(profile.get("target_titles", []))
    vecteurs = _embed(embedder, titres) if titres else []
    remote_pref: RemotePreference | None = profile.get("remote_pref")
    return CandidateInput(
        skills=tuple(profile.get("skills", [])),
        target_titles_embeddings=tuple(v for v in vecteurs if v is not None),
        seniority=profile.get("seniority"),
        total_experience_years=profile.get("total_experience_years"),
        sectors_preferred=frozenset(profile.get("sectors_preferred", [])),
        sectors_excluded=frozenset(profile.get("sectors_excluded", [])),
        sectors_experienced=frozenset(profile.get("sectors_experienced", [])),
        locations=tuple(
            CandidateLocation(
                lat=float(loc["lat"]), lon=float(loc["lon"]), radius_km=loc.get("radius_km")
            )
            for loc in profile.get("locations", [])
        ),
        remote_pref=remote_pref,
        languages=dict(profile.get("languages", {})),
        contract_types=frozenset(profile.get("contract_types", [])),
        contract_strict=bool(profile.get("contract_strict", False)),
        salary_expected_min=profile.get("salary_expected_min"),
        salary_expected_max=profile.get("salary_expected_max"),
        salary_min_strict=profile.get("salary_min_strict"),
    )

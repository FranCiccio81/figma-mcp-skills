"""Exécution du jeu d'évaluation contre les ``evaluation_gates``.

Ce que fait ce module : scorer chaque paire (candidat, offre) avec le VRAI
moteur, comparer le classement obtenu au classement attendu, et confronter le
résultat aux seuils de ``scoring-config.json``.

Ce que ça vaut : exactement ce que vaut le jeu d'annotations qu'on lui donne
(voir l'avertissement en tête de :mod:`app.evaluation.dataset`). L'instrument
est réel ; ce qu'il mesure aujourd'hui, ce sont des cas de référence
construits, pas la qualité perçue par des recruteurs sur des offres réelles.

Les portes sont **par candidat** pour Spearman et NDCG, agrégées sur
l'ensemble pour les bloquants. Moyenner Spearman entre candidats masquerait
un profil pour lequel le moteur classe à l'envers derrière deux profils bien
classés — or c'est précisément ce profil qu'on veut voir.
"""

from dataclasses import dataclass, field
from typing import Any

from app.evaluation.dataset import EvaluationDataset
from app.evaluation.metrics import (
    BlockingScore,
    MetricError,
    blocking_score,
    ndcg_at_k,
    spearman,
)
from app.matching import ScoringConfig, compute_match, get_config


@dataclass(frozen=True, slots=True)
class CaseReport:
    """Mesures pour un profil candidat."""

    candidate_id: str
    label: str
    spearman: float
    ndcg_at_10: float
    scores: tuple[tuple[str, int, int], ...] = ()  # (job_ref, score, pertinence)


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """Verdict d'une porte : le nom, le seuil, la valeur, le passage."""

    name: str
    threshold: float
    value: float
    passed: bool
    detail: str = ""


@dataclass(slots=True)
class EvaluationReport:
    """Rapport complet — sérialisable, comparable d'une exécution à l'autre."""

    scoring_version: str
    corpus_version: str
    dataset_version: str
    cases: list[CaseReport] = field(default_factory=list)
    blocking: BlockingScore = field(default_factory=lambda: BlockingScore(0, 0, 0))
    gates: list[GateOutcome] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(gate.passed for gate in self.gates)


def run_evaluation(
    dataset: EvaluationDataset,
    config: ScoringConfig | None = None,
    *,
    embeddings_used: bool = True,
) -> EvaluationReport:
    """Score tout le jeu et rend le rapport, portes comprises."""
    cfg = config if config is not None else get_config()
    report = EvaluationReport(
        scoring_version=cfg.scoring_version,
        corpus_version=dataset.corpus_version,
        dataset_version=dataset.dataset_version,
    )
    if not embeddings_used:
        report.warnings.append(
            "Évaluation SANS embeddings : la dimension « similarité d'intitulé » "
            "(15 % du poids) est inconnue pour toutes les paires. Les valeurs "
            "ci-dessous ne mesurent qu'une partie du moteur."
        )

    bloquants_predits: list[bool] = []
    bloquants_attendus: list[bool] = []

    for case in dataset.cases:
        scores: list[float] = []
        pertinences: list[float] = []
        detail: list[tuple[str, int, int]] = []

        for annotation in case.annotations:
            resultat = compute_match(case.candidate, dataset.jobs[annotation.job_ref], cfg)
            scores.append(float(resultat.score))
            pertinences.append(float(annotation.relevance))
            detail.append((annotation.job_ref, resultat.score, annotation.relevance))
            bloquants_predits.append(bool(resultat.blocking_criteria))
            bloquants_attendus.append(annotation.blocking_expected)

        try:
            rho = spearman(scores, pertinences)
            ndcg = ndcg_at_k(scores, pertinences, k=10)
        except MetricError as exc:
            # Une métrique indéfinie n'est pas un échec de porte : c'est un
            # jeu ou un moteur inexploitable. Le dire, ne pas le noter 0.
            report.warnings.append(f"{case.candidate_id} : {exc}")
            continue

        report.cases.append(
            CaseReport(
                candidate_id=case.candidate_id,
                label=case.label,
                spearman=rho,
                ndcg_at_10=ndcg,
                scores=tuple(detail),
            )
        )

    report.blocking = blocking_score(bloquants_predits, bloquants_attendus)
    report.gates = _evaluate_gates(report, cfg)
    return report


def _evaluate_gates(report: EvaluationReport, cfg: ScoringConfig) -> list[GateOutcome]:
    gates = _gates_of(cfg)
    outcomes: list[GateOutcome] = []

    if not report.cases:
        return [
            GateOutcome(
                name="jeu exploitable",
                threshold=1.0,
                value=0.0,
                passed=False,
                detail="aucun cas mesurable — voir les avertissements",
            )
        ]

    # Par candidat : le PIRE fait foi. Un profil mal classé est un profil mal
    # servi, qu'il soit ou non compensé par les autres dans une moyenne.
    pire_spearman = min(report.cases, key=lambda c: c.spearman)
    outcomes.append(
        GateOutcome(
            name="spearman_min",
            threshold=gates["spearman_min"],
            value=pire_spearman.spearman,
            passed=pire_spearman.spearman >= gates["spearman_min"],
            detail=f"pire profil : {pire_spearman.candidate_id}",
        )
    )

    pire_ndcg = min(report.cases, key=lambda c: c.ndcg_at_10)
    outcomes.append(
        GateOutcome(
            name="ndcg_at_10_min",
            threshold=gates["ndcg_at_10_min"],
            value=pire_ndcg.ndcg_at_10,
            passed=pire_ndcg.ndcg_at_10 >= gates["ndcg_at_10_min"],
            detail=f"pire profil : {pire_ndcg.candidate_id}",
        )
    )

    outcomes.append(
        GateOutcome(
            name="blocking_precision_min",
            threshold=gates["blocking_precision_min"],
            value=report.blocking.precision,
            passed=report.blocking.precision >= gates["blocking_precision_min"],
            detail=f"{report.blocking.false_positives} bloquant(s) annoncé(s) à tort",
        )
    )
    outcomes.append(
        GateOutcome(
            name="blocking_recall_min",
            threshold=gates["blocking_recall_min"],
            value=report.blocking.recall,
            passed=report.blocking.recall >= gates["blocking_recall_min"],
            detail=f"{report.blocking.false_negatives} bloquant(s) manqué(s)",
        )
    )
    return outcomes


#: Portes que ce harnais sait évaluer. Toute porte déclarée dans la
#: configuration doit y figurer — voir :func:`_gates_of`.
IMPLEMENTED_GATES = frozenset(
    {
        "spearman_min",
        "ndcg_at_10_min",
        "blocking_precision_min",
        "blocking_recall_min",
    }
)


def _gates_of(cfg: ScoringConfig) -> dict[str, float]:
    """Seuils lus sur la configuration, jamais recopiés ici.

    Recopier les seuils dans le code désarmerait la mesure le jour où
    ``scoring-config.json`` est resserré : les portes continueraient de
    passer sur les anciennes valeurs.

    Deux refus, tous deux issus de la revue :

    - une porte **déclarée mais non implémentée** est refusée. La
      configuration portait ``max_spearman_regression`` que rien n'évaluait :
      la non-régression annoncée par 06 §5 n'existait pas, et le rapport
      disait « toutes les portes passent » ;
    - une porte **manquante ou mal typée** est refusée avec un message. Un
      ``"0.6"`` entre guillemets était écarté en silence par le chargeur de
      configuration, puis donnait un ``KeyError`` nu à l'exécution.
    """
    raw: Any = getattr(cfg, "evaluation_gates", None)
    if not raw:
        raise ValueError(
            "scoring-config.json ne porte pas d'evaluation_gates : rien à "
            "vérifier, et une évaluation sans seuil ne dit rien"
        )
    gates = {key: float(value) for key, value in dict(raw).items()}

    declarees_non_implementees = set(gates) - IMPLEMENTED_GATES
    if declarees_non_implementees:
        raise ValueError(
            f"portes déclarées mais NON évaluées : {sorted(declarees_non_implementees)}. "
            "Une porte que personne ne vérifie donne un faux sentiment de "
            "couverture — l'implémenter, ou la retirer de la configuration."
        )
    manquantes = IMPLEMENTED_GATES - set(gates)
    if manquantes:
        raise ValueError(
            f"portes absentes ou mal typées dans evaluation_gates : {sorted(manquantes)}. "
            "Une valeur non numérique (\"0.6\" entre guillemets) est écartée "
            "au chargement de la configuration."
        )
    return gates


def format_report(report: EvaluationReport) -> str:
    """Rendu texte du rapport — ce que la CI et l'humain lisent."""
    lignes = [
        f"Évaluation du matching — scoring {report.scoring_version}, "
        f"corpus {report.corpus_version}, jeu {report.dataset_version}",
        "",
        "⚠️  Jeu de CAS DE RÉFÉRENCE CONSTRUITS, pas d'annotations humaines "
        "d'offres réelles. Ce rapport dit si le moteur se comporte comme "
        "attendu sur des cas choisis ; il ne dit PAS si le matching est bon "
        "pour de vrais candidats (Q19/Q20/Q47).",
        "",
    ]
    for avertissement in report.warnings:
        lignes.append(f"  ⚠️  {avertissement}")
    if report.warnings:
        lignes.append("")

    lignes.append("Par profil :")
    for case in report.cases:
        lignes.append(
            f"  {case.candidate_id:<24} spearman={case.spearman:+.3f}  "
            f"ndcg@10={case.ndcg_at_10:.3f}   {case.label}"
        )

    lignes += [
        "",
        f"Bloquants : {report.blocking.true_positives} justes, "
        f"{report.blocking.false_positives} à tort, "
        f"{report.blocking.false_negatives} manqués "
        f"(précision {report.blocking.precision:.3f}, rappel {report.blocking.recall:.3f})",
        "",
        "Portes :",
    ]
    for gate in report.gates:
        marque = "✅" if gate.passed else "❌"
        detail = f"  ({gate.detail})" if gate.detail else ""
        lignes.append(
            f"  {marque} {gate.name:<24} {gate.value:+.3f} "
            f"{'≥' if gate.passed else '<'} {gate.threshold:.2f}{detail}"
        )

    lignes += ["", "RÉSULTAT : " + ("toutes les portes passent" if report.passed else "ÉCHEC")]
    return "\n".join(lignes)

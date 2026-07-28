"""Harnais de mesure de la qualité du matching.

    python -m app.evaluation

Charge le corpus de démonstration et son jeu d'évaluation, score chaque paire
avec le vrai moteur, et confronte le résultat aux ``evaluation_gates`` de
``scoring-config.json``. Sortie non nulle si une porte tombe : la commande
est faite pour tourner en CI le jour où le jeu sera annoté pour de bon.

Lire l'avertissement de :mod:`app.evaluation.dataset` avant d'interpréter un
résultat : l'instrument est réel, le jeu livré ne l'est qu'à moitié.
"""

from app.evaluation.dataset import EvaluationDataset, load_dataset
from app.evaluation.metrics import blocking_score, ndcg_at_k, spearman
from app.evaluation.runner import EvaluationReport, format_report, run_evaluation

__all__ = [
    "EvaluationDataset",
    "EvaluationReport",
    "blocking_score",
    "format_report",
    "load_dataset",
    "ndcg_at_k",
    "run_evaluation",
    "spearman",
]

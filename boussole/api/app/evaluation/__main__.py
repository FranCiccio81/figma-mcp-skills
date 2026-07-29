"""``python -m app.evaluation`` — mesure la qualité du matching.

Sortie 0 si toutes les portes passent, 1 sinon. ``--no-embeddings`` mesure le
moteur amputé de la similarité d'intitulé (15 % du poids) : utile pour isoler
la contribution des vecteurs, jamais pour rendre un verdict.
"""

import argparse
import sys
from pathlib import Path

from app.ai.embeddings.factory import get_embedding_provider
from app.evaluation.dataset import load_dataset
from app.evaluation.runner import format_report, run_evaluation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.evaluation")
    parser.add_argument("--jobs", type=Path, default=None, help="corpus d'offres")
    parser.add_argument("--evaluation-set", type=Path, default=None, help="jeu annoté")
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="mesurer sans vecteurs (title_similarity devient inconnue)",
    )
    args = parser.parse_args(argv)

    embedder = None if args.no_embeddings else get_embedding_provider()
    dataset = load_dataset(
        jobs_path=args.jobs, evaluation_path=args.evaluation_set, embedder=embedder
    )
    report = run_evaluation(dataset, embeddings_used=embedder is not None)
    print(format_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover - point d'entrée
    sys.exit(main())

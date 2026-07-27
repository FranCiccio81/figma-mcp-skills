"""Logique de calcul par lots des embeddings — pure, sans base ni Celery.

Séparée des tâches (:mod:`app.workers.embedding_tasks`) pour être testable
sans PostgreSQL : les tâches ne font que lire des lignes, appeler
:func:`compute_embeddings` et écrire les vecteurs.

**Idempotence** (exigence M4) — trois garde-fous :

1. :func:`plan_embeddings` écarte les cibles qui ont DÉJÀ un vecteur
   (``force=False``) : rejouer un backfill est un no-op, et la requête SQL
   des tâches filtre déjà ``embedding IS NULL`` (le lot suivant avance
   donc naturellement) ;
2. les textes source vides sont écartés : un vecteur nul rendrait tout
   cosinus nul et ferait diverger l'index HNSW cosinus ;
3. les doublons de texte d'un même lot sont calculés UNE seule fois
   (déduplication par condensat) — un provider managé est facturé au
   token (R7).

**Ce qui n'est PAS couvert** 🟡 : « le texte source a changé depuis le
calcul ». Aucune colonne du schéma ne porte le condensat du texte source
ni la version de modèle (08 §8) — voir
:func:`app.ai.embeddings.text.source_text_hash`. La fraîcheur est donc
assurée au POINT D'ÉCRITURE : l'ingestion recalcule l'embedding d'une
offre quand elle en modifie l'intitulé ou la description
(:mod:`app.modules.ingestion.service`). Le backfill quotidien ne rattrape
que les vecteurs MANQUANTS. Un rattrapage exact (et un changement de
modèle, qui impose un re-embedding complet) demande ``force=True`` sur
l'ensemble du corpus, ou l'ajout des colonnes
``embedding_source_hash`` / ``embedding_model_version`` — migration à
prévoir avec Q11.
"""

import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.ai.embeddings.base import EmbeddingError, EmbeddingProvider
from app.ai.embeddings.text import source_text_hash

logger = logging.getLogger(__name__)

__all__ = [
    "BackfillReport",
    "EmbeddingTarget",
    "compute_embeddings",
    "plan_embeddings",
]


@dataclass(frozen=True, slots=True)
class EmbeddingTarget:
    """Une ligne à embarquer : sa clé, son texte source, son vecteur actuel."""

    key: uuid.UUID
    text: str
    current: Sequence[float] | None = None


@dataclass(slots=True)
class BackfillReport:
    """Compteurs d'un lot de backfill (métriques 08 §7.3)."""

    seen: int = 0
    computed: int = 0
    skipped_present: int = 0
    skipped_empty: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "seen": self.seen,
            "computed": self.computed,
            "skipped_present": self.skipped_present,
            "skipped_empty": self.skipped_empty,
            "errors": self.errors,
        }


def plan_embeddings(
    targets: Iterable[EmbeddingTarget],
    report: BackfillReport | None = None,
    *,
    force: bool = False,
) -> list[EmbeddingTarget]:
    """Cibles restant à calculer — idempotence (voir docstring du module)."""
    report = report if report is not None else BackfillReport()
    planned: list[EmbeddingTarget] = []
    for target in targets:
        report.seen += 1
        if not target.text.strip():
            report.skipped_empty += 1
            continue
        if not force and target.current is not None and len(target.current) > 0:
            report.skipped_present += 1
            continue
        planned.append(target)
    return planned


def compute_embeddings(
    provider: EmbeddingProvider,
    targets: Sequence[EmbeddingTarget],
    *,
    batch_size: int = 64,
    report: BackfillReport | None = None,
) -> dict[uuid.UUID, list[float]]:
    """Calcule les vecteurs des ``targets`` — un appel provider par lot.

    Les textes identiques ne sont soumis qu'une fois. Un échec de lot est
    journalisé et compté sans interrompre les autres lots : un backfill
    partiel est rattrapé au passage suivant (les lignes restent
    ``embedding IS NULL``).
    """
    if not targets:
        return {}
    report = report if report is not None else BackfillReport()

    # Déduplication par texte : condensat → texte, et texte → clés.
    unique_texts: dict[str, str] = {}
    keys_by_digest: dict[str, list[uuid.UUID]] = {}
    for target in targets:
        digest = source_text_hash(target.text)
        unique_texts.setdefault(digest, target.text)
        keys_by_digest.setdefault(digest, []).append(target.key)

    digests = list(unique_texts)
    vectors: dict[uuid.UUID, list[float]] = {}
    step = max(1, batch_size)
    for start in range(0, len(digests), step):
        chunk = digests[start : start + step]
        try:
            computed = provider.embed_texts([unique_texts[digest] for digest in chunk])
        except EmbeddingError as exc:
            report.errors += len(chunk)
            logger.warning(
                "embedding_batch_failed size=%d error_code=%s", len(chunk), exc.error_code
            )
            continue
        if len(computed) != len(chunk):
            report.errors += len(chunk)
            logger.error(
                "embedding_batch_arity_mismatch expected=%d got=%d",
                len(chunk), len(computed),
            )
            continue
        for digest, vector in zip(chunk, computed, strict=True):
            if not any(vector):
                # Vecteur nul : jamais persisté (cosinus indéfini, HNSW).
                report.skipped_empty += len(keys_by_digest[digest])
                continue
            for key in keys_by_digest[digest]:
                vectors[key] = list(vector)
                report.computed += 1
    return vectors

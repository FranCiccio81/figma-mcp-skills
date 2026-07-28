"""Rétention 13 mois du journal ``ai_calls`` (11 §3, D26).

Deux problèmes, une seule tâche.

**Un engagement.** La documentation annonce une rétention de 13 mois. Elle
n'était appliquée par rien : les lignes s'accumulaient indéfiniment. Un
engagement de durée de conservation qu'aucun code n'exécute est un engagement
rompu, même si personne ne s'en plaint.

**Une table sans borne.** ``ai_calls`` reçoit une ligne par appel IA — quatre
points d'appel, sur chaque import de CV, chaque explication de score, chaque
génération. C'est la table qui croît le plus vite du système, et rien ne la
faisait décroître.

La purge est ici une **suppression**, contrairement à la purge de compte
(:mod:`app.modules.ai_calls.purge`) qui n'est qu'une anonymisation. Ce n'est
pas contradictoire : l'anonymisation répond au droit à l'effacement en
préservant les agrégats d'exploitation, la rétention répond à la limitation
de conservation et supprime des lignes déjà anonymes ou devenues inutiles.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.db import get_session_factory
from app.modules.ai_calls.repository import AiCallsRepository, SqlAlchemyAiCallsRepository

logger = logging.getLogger(__name__)

#: Durée de conservation annoncée (11 §3).
RETENTION_MONTHS = 13

#: Taille d'un lot de suppression. Chaque lot est une transaction : sur la
#: plus grosse table du système, un ``DELETE`` global tiendrait un verrou
#: pendant toute sa durée et bloquerait les écritures du journal, donc les
#: appels IA en cours.
BATCH_SIZE = 5_000

#: Plafond de lots par exécution. Le premier passage après la mise en service
#: peut avoir des mois de retard à rattraper : on borne la durée de la tâche
#: plutôt que de la laisser tourner des heures, quitte à finir le lendemain.
MAX_BATCHES = 20


@dataclass(frozen=True, slots=True)
class RetentionOutcome:
    """Compte-rendu d'une exécution."""

    deleted: int = 0
    cutoff: datetime | None = None
    #: ``True`` quand le plafond de lots a été atteint : il reste des lignes
    #: à supprimer, la prochaine exécution reprendra.
    truncated: bool = False


def months_before(moment: datetime, months: int) -> datetime:
    """Recule de ``months`` mois calendaires, en bornant le quantième.

    ``timedelta`` ne connaît pas les mois et 13 × 30 jours dérive de six
    jours ; sur un engagement de conservation, on soustrait des mois, pas une
    approximation. Le 31 mars moins un mois donne le 28 (ou 29) février.
    """
    total = (moment.year * 12 + moment.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    if month == 12:
        next_month_start = datetime(year + 1, 1, 1, tzinfo=moment.tzinfo)
    else:
        next_month_start = datetime(year, month + 1, 1, tzinfo=moment.tzinfo)
    last_day = (next_month_start - datetime(year, month, 1, tzinfo=moment.tzinfo)).days
    return moment.replace(year=year, month=month, day=min(moment.day, last_day))


async def enforce_retention(
    *,
    repository: AiCallsRepository | None = None,
    now: datetime | None = None,
    months: int = RETENTION_MONTHS,
    batch: int = BATCH_SIZE,
    max_batches: int = MAX_BATCHES,
) -> RetentionOutcome:
    """Supprime les lignes ``ai_calls`` au-delà de la durée de conservation.

    Idempotente : une seconde exécution ne trouve plus rien à supprimer.
    """
    now = now or datetime.now(UTC)
    cutoff = months_before(now, months)

    if repository is not None:
        deleted, truncated = await _delete_batches(repository, cutoff, batch, max_batches)
    else:
        factory = get_session_factory()
        async with factory() as session:
            deleted, truncated = await _delete_batches(
                SqlAlchemyAiCallsRepository(session), cutoff, batch, max_batches
            )

    if truncated:
        logger.warning(
            "ai_calls_retention_truncated deleted=%d cutoff=%s "
            "(plafond de lots atteint — reste à supprimer au prochain passage)",
            deleted, cutoff.isoformat(),
        )
    else:
        logger.info(
            "ai_calls_retention_done deleted=%d cutoff=%s", deleted, cutoff.isoformat()
        )
    return RetentionOutcome(deleted=deleted, cutoff=cutoff, truncated=truncated)


async def _delete_batches(
    repository: AiCallsRepository, cutoff: datetime, batch: int, max_batches: int
) -> tuple[int, bool]:
    """Boucle bornée ; retourne (lignes supprimées, plafond atteint)."""
    deleted = 0
    for _ in range(max_batches):
        removed = await repository.delete_older_than(cutoff, batch=batch)
        deleted += removed
        if removed < batch:
            # Lot incomplet = plus rien à supprimer avant la borne.
            return deleted, False
    return deleted, True

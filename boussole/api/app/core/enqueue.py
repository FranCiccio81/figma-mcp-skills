"""Enfilement de tâches Celery depuis le chemin API — sans geler la boucle.

**Le problème.** ``celery_app.send_task`` ouvre une connexion synchrone.
Appelé depuis un ``async def``, il bloque la boucle d'événements du worker
ASGI — donc **toutes** les requêtes en cours de cette instance, pas seulement
celle de l'appelant. Mesuré contre un courtier qui accepte la connexion mais
ne répond jamais (le cas le plus pénible : ni refus, ni réponse) :

===========================================  ===========
tel quel                                     19,18 s
``ignore_result=True``                        6,06 s
+ connexion à ``max_retries=0``               0,002 s
===========================================  ===========

L'essentiel du délai n'est **pas** le courtier mais le *result backend* :
``backend.on_task_call`` abonne un consommateur de résultat et retente jusqu'à
« Retry limit exceeded ». Or personne ne lit le résultat de ces tâches — l'API
interroge la base (statut du document), pas Celery. ``retry=False`` ne couvre
que la republication, pas ces deux boucles : les trois options sont
nécessaires ensemble.

**Pourquoi ce module existe.** Le correctif avait été appliqué à UN seul des
trois appels (le recalcul d'embedding). L'import de CV et la génération de
lettre appelaient ``send_task`` nu. Un correctif recopié à un endroit sur
trois n'est pas un correctif : c'est une ligne de code chanceuse.

**Deux régimes, parce que l'enjeu n'est pas le même.** Le recalcul
d'embedding est rattrapé par un beat quotidien : son échec est absorbable.
L'analyse d'un CV, non — si l'enfilement échoue et que personne ne le dit,
l'utilisateur regarde une roue tourner pour toujours.
"""

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class EnqueueError(RuntimeError):
    """Le courtier n'a pas accepté la tâche — l'appelant DOIT le dire."""


def _send(name: str, args: list[Any], queue: str) -> None:
    """Publication bornée : jamais plus de quelques millisecondes d'attente."""
    from app.workers.celery_app import celery_app

    with celery_app.connection_for_write(
        transport_options={"max_retries": 0}
    ) as connection:
        celery_app.send_task(
            name,
            args=args,
            queue=queue,
            connection=connection,
            retry=False,
            ignore_result=True,
        )


def enqueue(name: str, *args: uuid.UUID | str, queue: str) -> None:
    """Enfile une tâche dont l'échec doit remonter à l'utilisateur.

    Lève :class:`EnqueueError`. L'appelant la traduit en 503 : « réessayez »
    est une réponse honnête, un document éternellement ``parsing`` ne l'est
    pas.
    """
    try:
        _send(name, [str(a) for a in args], queue)
    except Exception as exc:
        logger.exception("enqueue_failed task=%s queue=%s", name, queue)
        raise EnqueueError(
            f"tâche {name!r} non enfilée : le courtier est injoignable"
        ) from exc


def enqueue_best_effort(name: str, *args: uuid.UUID | str, queue: str) -> None:
    """Enfile une tâche qu'un traitement périodique rattrapera.

    N'échoue jamais. Réservé aux tâches dont l'absence se répare toute seule —
    aujourd'hui le seul recalcul d'embedding de profil, rattrapé par le beat
    quotidien. Journalisé en WARNING : « rattrapable » ne veut pas dire
    « invisible ».
    """
    try:
        _send(name, [str(a) for a in args], queue)
    except Exception:
        logger.warning(
            "enqueue_best_effort_failed task=%s queue=%s args=%s", name, queue, args
        )

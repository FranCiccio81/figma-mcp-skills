"""Re-scoring asynchrone (06 §4, déclencheur a) — file ``scoring``.

**Ce que ça corrige.** Le hook « preferences_changed » se contentait de
SUPPRIMER les ``match_results`` de l'utilisateur, avec pour commentaire
« recalcul paresseux au prochain accès ». Or un seul écran recalcule
paresseusement — ``GET /matches`` — et la recherche d'offres, elle, se
contente de LIRE le cache.

Conséquence mesurée en revue finale, sur le chemin nominal, juste après
l'action que le produit encourage :

    GET /jobs?sort=match       → [86, 84, 79]
    PUT /preferences {...}     → 200
    GET /jobs?sort=match       → [null, null, null]   et l'ordre n'est plus
                                 celui des scores

La page Préférences affiche pourtant « Préférences enregistrées. **Vos
scores sont en cours de mise à jour.** » avec un bouton « Voir mes offres »
— une promesse que rien ne tenait. Même symptôme au premier accès, y compris
pour le compte que ``make demo`` déclare « application utilisable ».

**Pourquoi la file ``scoring`` et pas ``ai``.** Le moteur est déterministe et
ne fait **aucun appel réseau** (06 §4, cible < 50 ms par paire). C'est
exactement le profil de latence que cette file existe pour isoler : un
incident du fournisseur d'IA ne doit pas retarder un re-scoring qui n'en
dépend pas.

**Idempotence.** La tâche recalcule et réécrit par ``(profile_id, job_id)``.
La rejouer ne produit rien d'autre que les mêmes lignes : ``acks_late`` et
une re-livraison sont donc sans conséquence.
"""

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.db import create_worker_engine
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

#: Borne du re-scoring déclenché par un changement de préférences.
#:
#: Le même plafond que le calcul paresseux de ``GET /matches`` : au-delà, ce
#: n'est plus une réaction à une action utilisateur mais un batch, qui a sa
#: place dans un traitement nocturne. Sans borne, un utilisateur qui règle ses
#: préférences trois fois de suite mettrait la file à genoux.
MAX_RESCORED_JOBS = 200


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _rescore(user_id: uuid.UUID) -> dict[str, Any]:
    """Recalcule les correspondances de l'utilisateur et les réécrit."""
    from app.modules.matching.repository import SqlAlchemyMatchingRepository
    from app.modules.matching.service import MatchingService
    from app.modules.preferences.repository import SqlAlchemyPreferencesRepository
    from app.modules.profiles.repository import SqlAlchemyProfilesRepository

    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            service = MatchingService(
                repository=SqlAlchemyMatchingRepository(session),
                profiles=SqlAlchemyProfilesRepository(session),
                preferences=SqlAlchemyPreferencesRepository(session),
            )
            page = await service.list_matches(
                user_id,
                limit=MAX_RESCORED_JOBS,
                cursor=None,
                min_score=None,
                include_blocked=True,
            )
            await session.commit()
            return {"scored": len(page.items)}
    finally:
        await engine.dispose()


@celery_app.task(name="scoring.rescore_user", bind=True, max_retries=3)
def rescore_user(self: Any, user_id: str) -> dict[str, Any] | None:
    """Recalcule les correspondances d'UN utilisateur après un changement.

    Best-effort du point de vue de l'appelant : l'enregistrement des
    préférences a déjà abouti, et l'échec du re-scoring laisse simplement les
    cartes sans score — état honnête (« pas encore calculé »), jamais faux.
    Les retries bornés de Celery couvrent l'indisponibilité passagère.
    """
    try:
        rapport = _run(_rescore(uuid.UUID(user_id)))
    except Exception as exc:  # pragma: no cover - dépend de l'infra
        logger.exception("rescore_user_failed user=%s", user_id)
        raise self.retry(exc=exc, countdown=30) from exc
    logger.info("rescore_user_done user=%s report=%s", user_id, rapport)
    return rapport

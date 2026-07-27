"""Purge planifiée des comptes supprimés (F-Q, D09, D21) — exécutée par beat.

Pour chaque ``deletion_request`` pending échue (``purge_after`` ≤ now) :

1. exécute ``purge_user()`` de TOUS les modules du registre — chaque module
   gère sa propre transaction (sa propre session, pattern auth/purge.py) ;
   un échec est journalisé et rend la purge PARTIELLE (statut pending
   conservé → retentée au prochain passage), jamais silencieux ;
2. purge les données propres du module privacy (archives d'export : objets
   stockés + lignes ``privacy_exports`` — F-Q alt. 5) ;
3. anonymise ``audit_log`` (user_id → NULL, subject_key = hash irréversible) ;
4. marque la demande ``purged``.

Idempotente : les demandes déjà ``purged`` ne sont pas resélectionnées et
les purges de modules sont des suppressions idempotentes.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.privacy.registry import PurgeRegistry
from app.modules.privacy.repository import PrivacyRepository
from app.modules.privacy.signing import subject_key_for
from app.modules.privacy.storage import ObjectStorage

logger = logging.getLogger("boussole.privacy")


@dataclass(frozen=True, slots=True)
class PurgeOutcome:
    deletion_id: uuid.UUID
    user_id: uuid.UUID
    purged: bool
    failed_modules: tuple[str, ...] = ()


async def purge_due_accounts(
    *,
    repository: PrivacyRepository,
    storage: ObjectStorage,
    registry: PurgeRegistry,
    now: datetime | None = None,
) -> list[PurgeOutcome]:
    """Purge toutes les demandes échues ; retourne un compte-rendu par demande."""
    now = now or datetime.now(UTC)
    outcomes: list[PurgeOutcome] = []
    for request in await repository.due_deletion_requests(now):
        failed: list[str] = []
        for entry in registry.entries:
            try:
                purge_fn = entry.resolve_purge()
                await purge_fn(request.user_id)
            except Exception:
                logger.exception(
                    "account_purge_module_failed",
                    extra={"detail": f"module={entry.name} deletion={request.id}"},
                )
                failed.append(entry.name)

        # Données propres du module privacy : archives d'export (F-Q alt. 5).
        try:
            for export in await repository.list_exports_for_user(request.user_id):
                if export.file_key:
                    await storage.delete(export.file_key)
            await repository.delete_exports_for_user(request.user_id)
        except Exception:
            logger.exception(
                "account_purge_module_failed",
                extra={"detail": f"module=privacy deletion={request.id}"},
            )
            failed.append("privacy")

        if failed:
            # Statut PARTIEL explicite : la demande reste pending et sera
            # retentée ; l'alerte « purges en retard » (D20) prend le relais.
            logger.error(
                "account_purge_partial",
                extra={"detail": f"deletion={request.id} modules_en_echec={failed}"},
            )
            outcomes.append(
                PurgeOutcome(
                    deletion_id=request.id,
                    user_id=request.user_id,
                    purged=False,
                    failed_modules=tuple(failed),
                )
            )
            continue

        await repository.anonymize_audit(request.user_id, subject_key_for(request.user_id))
        await repository.mark_deletion_purged(request.id)
        # Événement anonyme (l'utilisateur n'existe plus) — F-Q analytics.
        await repository.add_audit(
            None,
            "account_purge_completed",
            entity="deletion_request",
            entity_id=request.id,
            meta={"latency_days": max(0, (now - request.purge_after).days)},
        )
        logger.info("account_purge_completed", extra={"detail": f"deletion={request.id}"})
        outcomes.append(
            PurgeOutcome(deletion_id=request.id, user_id=request.user_id, purged=True)
        )
    return outcomes

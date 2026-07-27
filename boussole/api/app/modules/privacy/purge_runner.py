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

Ce module porte aussi :func:`purge_expired_exports` (M3) — ménage quotidien
des archives dont le lien signé a expiré (objet + ligne).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.storage import ObjectStorage
from app.modules.privacy.registry import PurgeRegistry
from app.modules.privacy.repository import PrivacyRepository
from app.modules.privacy.signing import subject_key_for

logger = logging.getLogger("boussole.privacy")


@dataclass(frozen=True, slots=True)
class ExpiredExportsOutcome:
    """Compte-rendu du ménage des archives expirées (M3)."""

    deleted_objects: int = 0
    deleted_rows: int = 0
    failed_keys: tuple[str, ...] = ()


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
        # La suppression des OBJETS et celle des LIGNES sont dissociées : un
        # objet manquant / un backend en erreur ne doit JAMAIS empêcher la
        # suppression des lignes ``privacy_exports`` (sans quoi la trace de
        # l'export — et son file_key — survivrait à la suppression du compte).
        # ``ObjectStorage`` est SYNCHRONE (app/core/storage.py) : aucun await.
        try:
            for export in await repository.list_exports_for_user(request.user_id):
                if export.file_key:
                    storage.delete(export.file_key)
        except Exception:
            logger.exception(
                "account_purge_module_failed",
                extra={"detail": f"module=privacy_objects deletion={request.id}"},
            )
            failed.append("privacy")
        try:
            await repository.delete_exports_for_user(request.user_id)
        except Exception:
            logger.exception(
                "account_purge_module_failed",
                extra={"detail": f"module=privacy_rows deletion={request.id}"},
            )
            failed.append("privacy_rows")

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


async def purge_expired_exports(
    *,
    repository: PrivacyRepository,
    storage: ObjectStorage,
    now: datetime | None = None,
) -> ExpiredExportsOutcome:
    """Supprime les archives d'export dont le lien a expiré (M3).

    Le lien signé expire à J+7 (``EXPORT_LINK_TTL_DAYS``) mais l'OBJET, lui,
    survivait indéfiniment : un dump personnel complet restait stocké bien
    au-delà de sa finalité (minimisation, D09). Cette tâche supprime l'objet
    ET la ligne ``privacy_exports`` de toute archive échue.

    Idempotente : une seconde exécution ne trouve plus rien ; un objet déjà
    absent n'est pas une erreur (``delete`` est idempotent par contrat) et la
    ligne est supprimée QUOI QU'IL ARRIVE — un objet orphelin ne doit pas
    figer une ligne expirée en base.
    """
    now = now or datetime.now(UTC)
    deleted_objects = 0
    deleted_rows = 0
    failed_keys: list[str] = []
    for export in await repository.expired_exports(now):
        if export.file_key:
            try:
                storage.delete(export.file_key)  # contrat SYNCHRONE
                deleted_objects += 1
            except Exception:
                logger.exception(
                    "expired_export_object_delete_failed",
                    extra={"detail": f"export={export.id} key={export.file_key}"},
                )
                failed_keys.append(export.file_key)
        await repository.delete_export(export.id)
        deleted_rows += 1
    if deleted_rows or failed_keys:
        logger.info(
            "expired_exports_purged",
            extra={
                "detail": (
                    f"objets={deleted_objects} lignes={deleted_rows} "
                    f"echecs={len(failed_keys)}"
                )
            },
        )
    return ExpiredExportsOutcome(
        deleted_objects=deleted_objects,
        deleted_rows=deleted_rows,
        failed_keys=tuple(failed_keys),
    )

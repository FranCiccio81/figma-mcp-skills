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
des archives dont le lien signé a expiré (objet + ligne) — et
:func:`check_purge_backlog`, la surveillance de l'engagement des 30 jours
(D20).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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


#: Marge au-delà de l'échéance avant de crier au retard.
#:
#: La purge tourne UNE fois par jour (beat 04:15) : une demande dont
#: l'échéance tombe à 04:16 attend légitimement ~24 h avant d'être traitée.
#: 26 h = un cycle complet + 2 h pour une purge longue ou décalée.
#:
#: ⚠️ Conséquence à assumer : puisque ``purge_after`` EST le trentième jour,
#: cette marge signifie qu'une purge peut légitimement s'exécuter au 31e jour.
#: L'engagement « suppression sous 30 jours » est donc tenu à un cycle près,
#: par construction — ce n'est pas cette surveillance qui le corrige. Le fond
#: se règle en posant ``purge_after`` à J+29 (ou en purgeant plus souvent) ;
#: c'est une modification de D09, hors périmètre de la surveillance.
BACKLOG_GRACE = timedelta(hours=26)


@dataclass(frozen=True, slots=True)
class PurgeBacklog:
    """Compte-rendu de la surveillance des purges en retard (D20)."""

    overdue: int = 0
    oldest_age_hours: float = 0.0
    deletion_ids: tuple[uuid.UUID, ...] = ()

    @property
    def healthy(self) -> bool:
        return self.overdue == 0


async def check_purge_backlog(
    *,
    repository: PrivacyRepository,
    now: datetime | None = None,
    grace: timedelta = BACKLOG_GRACE,
) -> PurgeBacklog:
    """Signale les demandes de suppression échues **et toujours pending**.

    Ce que ça attrape : une purge qui échoue en boucle. Un module du registre
    qui lève à chaque passage laisse la demande ``pending`` — elle est
    retentée indéfiniment, chaque tentative journalise
    ``account_purge_partial``, et **rien ne remontait au-dessus du niveau de
    la ligne de log**. Un compte pouvait rester non purgé des semaines sans
    qu'aucun signal agrégé n'existe.

    ⚠️ **Ce que ça n'attrape pas** : un beat arrêté. Cette vérification est
    elle-même une tâche beat — si l'ordonnanceur est mort, ni la purge ni sa
    surveillance ne tournent, et le silence est total. C'est pourquoi le cas
    sain journalise quand même une ligne ``purge_backlog_ok`` : elle sert de
    **battement de cœur**, et c'est son ABSENCE que la supervision externe
    doit alerter (runbook §7.3). Une alerte sur l'absence d'un signal est le
    seul moyen de détecter un ordonnanceur mort depuis l'intérieur.
    """
    now = now or datetime.now(UTC)
    # ``due_deletion_requests`` sélectionne « pending ET purge_after ≤ borne » :
    # en lui passant ``now - grace``, on obtient exactement les demandes que la
    # purge aurait dû traiter au moins une fois.
    overdue = await repository.due_deletion_requests(now - grace)
    if not overdue:
        logger.info("purge_backlog_ok", extra={"detail": "overdue=0"})
        return PurgeBacklog()

    oldest = min(request.purge_after for request in overdue)
    age_hours = round((now - oldest).total_seconds() / 3600, 1)
    logger.error(
        "purge_backlog_detected",
        extra={
            "detail": (
                f"overdue={len(overdue)} plus_ancienne={age_hours}h "
                f"deletions={[str(r.id) for r in overdue]}"
            )
        },
    )
    return PurgeBacklog(
        overdue=len(overdue),
        oldest_age_hours=age_hours,
        deletion_ids=tuple(request.id for request in overdue),
    )


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

"""Constitution de l'archive d'export RGPD (art. 20) — exécutée par le worker.

Agrège les ``export_user()`` de tous les modules du registre (D21) en UNE
archive JSON, stockée via ObjectStorage (contrat SYNCHRONE de
``app/core/storage.py``). Un module défaillant (p. ex. encore en chantier)
est journalisé et listé dans ``incomplete_modules`` — jamais d'échec
silencieux, jamais d'échec global pour un module manquant.

TODO(M5+, arbitrage produit à confirmer) — fichiers CV binaires : l'archive
ne contient QUE les données structurées extraites des CV (``profiles``), pas
les fichiers d'origine (PDF/DOCX) stockés en objet. L'art. 20 vise les
données fournies par la personne : les fichiers déposés en font partie et
devraient à terme être joints (archive ZIP au lieu d'un JSON). Décision à
acter avec le produit/DPO avant M5 — l'écart est ici EXPLICITE, pas oublié.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.core.storage import ObjectStorage
from app.modules.privacy.registry import PurgeRegistry
from app.modules.privacy.repository import PrivacyRepository
from app.modules.privacy.signing import EXPORT_LINK_TTL_DAYS

logger = logging.getLogger("boussole.privacy")


@dataclass(frozen=True, slots=True)
class ExportBuildResult:
    status: str  # 'ready' | 'skipped'
    file_key: str | None = None
    incomplete_modules: tuple[str, ...] = field(default_factory=tuple)


def export_file_key(user_id: uuid.UUID, export_id: uuid.UUID) -> str:
    return f"privacy-exports/{user_id}/{export_id}.json"


async def build_export(
    export_id: uuid.UUID,
    *,
    repository: PrivacyRepository,
    storage: ObjectStorage,
    registry: PurgeRegistry,
    now: datetime | None = None,
) -> ExportBuildResult:
    """Assemble et stocke l'archive JSON ; marque l'export « ready ».

    Idempotent : un export inconnu ou déjà traité est ignoré (loggé).
    """
    now = now or datetime.now(UTC)
    record = await repository.get_export(export_id)
    if record is None:
        logger.warning("privacy_export_unknown", extra={"detail": str(export_id)})
        return ExportBuildResult(status="skipped")
    if record.status != "pending":
        logger.info(
            "privacy_export_already_done",
            extra={"detail": f"{export_id} status={record.status}"},
        )
        return ExportBuildResult(status="skipped")

    modules: dict[str, object] = {}
    incomplete: list[str] = []
    for entry in registry.entries:
        try:
            export_fn = entry.resolve_export()
            modules[entry.name] = await export_fn(record.user_id)
        except Exception:
            logger.exception(
                "privacy_export_module_failed",
                extra={"detail": f"module={entry.name} export={export_id}"},
            )
            incomplete.append(entry.name)

    archive: dict[str, object] = {
        "export_id": str(record.id),
        "user_id": str(record.user_id),
        "generated_at": now.isoformat(),
        "modules": modules,
    }
    if incomplete:
        archive["incomplete_modules"] = incomplete

    file_key = export_file_key(record.user_id, record.id)
    # ``ObjectStorage`` (app/core/storage.py) est SYNCHRONE : aucun await ici.
    storage.put(file_key, json.dumps(archive, ensure_ascii=False).encode())
    expires_at = now + timedelta(days=EXPORT_LINK_TTL_DAYS)
    await repository.mark_export_ready(record.id, file_key, expires_at)
    await repository.add_audit(
        record.user_id,
        "privacy_export_ready",
        entity="privacy_export",
        entity_id=record.id,
        meta={"incomplete_modules": incomplete} if incomplete else None,
    )
    return ExportBuildResult(
        status="ready", file_key=file_key, incomplete_modules=tuple(incomplete)
    )

"""Accès aux données du module privacy.

Le protocole ``PrivacyRepository`` permet de substituer une implémentation en
mémoire dans les tests unitaires (pas de PostgreSQL requis).

Écart D01 assumé (documenté) : la suppression de compte écrit
``users.deleted_at`` et ``deletion_requests`` via les modèles du module auth —
privacy est l'orchestrateur RGPD (D21) et auth n'expose pas encore de service
dédié ; à revoir si auth publie une interface de soft delete.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from fastapi import Depends
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.modules.auth.models import DeletionRequest, User
from app.modules.privacy.models import AuditLog, PrivacyExport


@dataclass(frozen=True, slots=True)
class ExportRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    status: str  # 'pending' | 'ready' ('expired' est dérivé à la lecture)
    file_key: str | None
    created_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class DeletionRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    requested_at: datetime
    purge_after: datetime
    status: str  # 'pending' | 'purged'


class PrivacyRepository(Protocol):
    # --- exports RGPD ---
    async def create_export(self, user_id: uuid.UUID, created_at: datetime) -> ExportRecord: ...

    async def get_export(self, export_id: uuid.UUID) -> ExportRecord | None: ...

    async def mark_export_ready(
        self, export_id: uuid.UUID, file_key: str, expires_at: datetime
    ) -> None: ...

    async def list_exports_for_user(self, user_id: uuid.UUID) -> list[ExportRecord]: ...

    async def delete_exports_for_user(self, user_id: uuid.UUID) -> None: ...

    # --- suppression de compte ---
    async def execute_account_deletion(
        self, user_id: uuid.UUID, *, now: datetime, purge_after: datetime
    ) -> DeletionRecord: ...

    async def due_deletion_requests(self, now: datetime) -> list[DeletionRecord]: ...

    async def mark_deletion_purged(self, deletion_id: uuid.UUID) -> None: ...

    # --- audit ---
    async def add_audit(
        self,
        user_id: uuid.UUID | None,
        action: str,
        *,
        entity: str | None = None,
        entity_id: uuid.UUID | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> None: ...

    async def anonymize_audit(self, user_id: uuid.UUID, subject_key: str) -> None: ...


def _export_record(row: PrivacyExport) -> ExportRecord:
    return ExportRecord(
        id=row.id,
        user_id=row.user_id,
        status=row.status,
        file_key=row.file_key,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def _deletion_record(row: DeletionRequest) -> DeletionRecord:
    return DeletionRecord(
        id=row.id,
        user_id=row.user_id,
        requested_at=row.requested_at,
        purge_after=row.purge_after,
        status=row.status,
    )


class SqlAlchemyPrivacyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_export(self, user_id: uuid.UUID, created_at: datetime) -> ExportRecord:
        row = PrivacyExport(user_id=user_id, status="pending", created_at=created_at)
        self._session.add(row)
        await self._session.commit()
        return _export_record(row)

    async def get_export(self, export_id: uuid.UUID) -> ExportRecord | None:
        row = await self._session.get(PrivacyExport, export_id)
        return _export_record(row) if row is not None else None

    async def mark_export_ready(
        self, export_id: uuid.UUID, file_key: str, expires_at: datetime
    ) -> None:
        await self._session.execute(
            update(PrivacyExport)
            .where(PrivacyExport.id == export_id)
            .values(status="ready", file_key=file_key, expires_at=expires_at)
        )
        await self._session.commit()

    async def list_exports_for_user(self, user_id: uuid.UUID) -> list[ExportRecord]:
        rows = (
            (
                await self._session.execute(
                    select(PrivacyExport).where(PrivacyExport.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        return [_export_record(row) for row in rows]

    async def delete_exports_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(PrivacyExport).where(PrivacyExport.user_id == user_id)
        )
        await self._session.commit()

    async def execute_account_deletion(
        self, user_id: uuid.UUID, *, now: datetime, purge_after: datetime
    ) -> DeletionRecord:
        """Soft delete + deletion_request + audit — UNE transaction (AC-Q-1)."""
        await self._session.execute(
            update(User).where(User.id == user_id).values(deleted_at=now)
        )
        request = DeletionRequest(
            user_id=user_id, requested_at=now, purge_after=purge_after, status="pending"
        )
        self._session.add(request)
        self._session.add(
            AuditLog(
                user_id=user_id,
                action="account_deletion_requested",
                entity="deletion_request",
                meta={"purge_after": purge_after.isoformat()},
            )
        )
        await self._session.commit()
        return _deletion_record(request)

    async def due_deletion_requests(self, now: datetime) -> list[DeletionRecord]:
        rows = (
            (
                await self._session.execute(
                    select(DeletionRequest).where(
                        DeletionRequest.status == "pending",
                        DeletionRequest.purge_after <= now,
                    )
                )
            )
            .scalars()
            .all()
        )
        return [_deletion_record(row) for row in rows]

    async def mark_deletion_purged(self, deletion_id: uuid.UUID) -> None:
        await self._session.execute(
            update(DeletionRequest)
            .where(DeletionRequest.id == deletion_id)
            .values(status="purged")
        )
        await self._session.commit()

    async def add_audit(
        self,
        user_id: uuid.UUID | None,
        action: str,
        *,
        entity: str | None = None,
        entity_id: uuid.UUID | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                user_id=user_id,
                action=action,
                entity=entity,
                entity_id=entity_id,
                meta=dict(meta) if meta else {},
            )
        )
        await self._session.commit()

    async def anonymize_audit(self, user_id: uuid.UUID, subject_key: str) -> None:
        """RM-Q-2 : user_id → NULL, subject_key = hash irréversible."""
        await self._session.execute(
            update(AuditLog)
            .where(AuditLog.user_id == user_id)
            .values(user_id=None, subject_key=subject_key)
        )
        await self._session.commit()


async def get_privacy_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PrivacyRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyPrivacyRepository(session)

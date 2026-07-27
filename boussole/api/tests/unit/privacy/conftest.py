"""Fixtures des tests du module privacy.

Fakes partout (D21) : AUCUN import des vrais modules de données — le registre
injecté porte des callables directs, le repository et le stockage sont en
mémoire. Le repository privacy partage les utilisateurs du
``InMemoryAuthRepository`` commun (soft delete visible par les dépendances
d'auth).
"""

import dataclasses
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.modules.privacy.registry import ModuleEntry, PurgeRegistry
from app.modules.privacy.repository import (
    DeletionRecord,
    ExportRecord,
    get_privacy_repository,
)
from app.modules.privacy.router import get_export_enqueuer, get_storage
from tests.unit.conftest import InMemoryAuthRepository

REGISTER_PAYLOAD = {
    "email": "camille@example.eu",
    "password": "un mot de passe très long",
    "locale": "fr",
    "accepted_terms_version": "2026-07",
    "accepted_privacy_version": "2026-07",
}


class InMemoryPrivacyRepository:
    """Implémentation en mémoire du protocole PrivacyRepository."""

    def __init__(self, auth_repository: InMemoryAuthRepository | None = None) -> None:
        self.auth_repository = auth_repository
        self.exports: dict[uuid.UUID, ExportRecord] = {}
        self.deletion_requests: dict[uuid.UUID, DeletionRecord] = {}
        self.audit_entries: list[dict[str, Any]] = []

    # --- exports ---
    async def create_export(self, user_id: uuid.UUID, created_at: datetime) -> ExportRecord:
        record = ExportRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            status="pending",
            file_key=None,
            created_at=created_at,
            expires_at=None,
        )
        self.exports[record.id] = record
        return record

    async def get_export(self, export_id: uuid.UUID) -> ExportRecord | None:
        return self.exports.get(export_id)

    async def mark_export_ready(
        self, export_id: uuid.UUID, file_key: str, expires_at: datetime
    ) -> None:
        record = self.exports[export_id]
        self.exports[export_id] = dataclasses.replace(
            record, status="ready", file_key=file_key, expires_at=expires_at
        )

    async def list_exports_for_user(self, user_id: uuid.UUID) -> list[ExportRecord]:
        return [r for r in self.exports.values() if r.user_id == user_id]

    async def delete_exports_for_user(self, user_id: uuid.UUID) -> None:
        for export_id in [i for i, r in self.exports.items() if r.user_id == user_id]:
            del self.exports[export_id]

    # --- suppression de compte ---
    async def execute_account_deletion(
        self, user_id: uuid.UUID, *, now: datetime, purge_after: datetime
    ) -> DeletionRecord:
        if self.auth_repository is not None:
            user = self.auth_repository.users_by_id.get(user_id)
            if user is not None:
                user.deleted_at = now
        record = DeletionRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            requested_at=now,
            purge_after=purge_after,
            status="pending",
        )
        self.deletion_requests[record.id] = record
        self.audit_entries.append(
            {
                "user_id": user_id,
                "subject_key": None,
                "action": "account_deletion_requested",
                "entity": "deletion_request",
                "entity_id": None,
                "meta": {"purge_after": purge_after.isoformat()},
            }
        )
        return record

    async def due_deletion_requests(self, now: datetime) -> list[DeletionRecord]:
        return [
            r
            for r in self.deletion_requests.values()
            if r.status == "pending" and r.purge_after <= now
        ]

    async def mark_deletion_purged(self, deletion_id: uuid.UUID) -> None:
        record = self.deletion_requests[deletion_id]
        self.deletion_requests[deletion_id] = dataclasses.replace(record, status="purged")

    # --- audit ---
    async def add_audit(
        self,
        user_id: uuid.UUID | None,
        action: str,
        *,
        entity: str | None = None,
        entity_id: uuid.UUID | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> None:
        self.audit_entries.append(
            {
                "user_id": user_id,
                "subject_key": None,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "meta": dict(meta) if meta else {},
            }
        )

    async def anonymize_audit(self, user_id: uuid.UUID, subject_key: str) -> None:
        for entry in self.audit_entries:
            if entry["user_id"] == user_id:
                entry["user_id"] = None
                entry["subject_key"] = subject_key


class FakeStorage:
    """ObjectStorage en mémoire (put/get/delete)."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class FakeModules:
    """Registre de fakes : enregistre les appels purge/export par module."""

    def __init__(self, names: tuple[str, ...] = ("alpha", "beta"),
                 failing: frozenset[str] = frozenset()) -> None:
        self.names = names
        self.failing = failing
        self.purged: list[tuple[str, uuid.UUID]] = []
        self.exported: list[tuple[str, uuid.UUID]] = []

    def registry(self) -> PurgeRegistry:
        entries = []
        for name in self.names:
            entries.append(
                ModuleEntry(
                    name=name,
                    purge=self._make_purge(name),
                    export=self._make_export(name),
                )
            )
        return PurgeRegistry(entries=tuple(entries))

    def _make_purge(self, name: str):
        async def purge(user_id: uuid.UUID) -> None:
            if name in self.failing:
                raise RuntimeError(f"panne du module {name}")
            self.purged.append((name, user_id))

        return purge

    def _make_export(self, name: str):
        async def export(user_id: uuid.UUID) -> dict[str, Any]:
            if name in self.failing:
                raise RuntimeError(f"panne du module {name}")
            self.exported.append((name, user_id))
            return {f"{name}_data": str(user_id)}

        return export


@pytest.fixture
def privacy_repository(auth_repository: InMemoryAuthRepository) -> InMemoryPrivacyRepository:
    return InMemoryPrivacyRepository(auth_repository)


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def enqueued_exports() -> list[uuid.UUID]:
    return []


@pytest.fixture
def client(
    client: TestClient,
    privacy_repository: InMemoryPrivacyRepository,
    fake_storage: FakeStorage,
    enqueued_exports: list[uuid.UUID],
) -> TestClient:
    """Étend le client commun avec le repo privacy, un stockage et un espion."""

    def spy_enqueuer(export_id: uuid.UUID) -> None:
        enqueued_exports.append(export_id)

    client.app.dependency_overrides[get_privacy_repository] = lambda: privacy_repository
    client.app.dependency_overrides[get_storage] = lambda: fake_storage
    client.app.dependency_overrides[get_export_enqueuer] = lambda: spy_enqueuer
    return client


def register(client: TestClient, **overrides: str) -> Any:
    return client.post("/api/v1/auth/register", json={**REGISTER_PAYLOAD, **overrides})


def csrf_headers(client: TestClient) -> dict[str, str]:
    """En-tête X-CSRF-Token aligné sur le cookie double-submit."""
    return {"X-CSRF-Token": client.cookies["boussole_csrf"]}


def make_export_record(
    user_id: uuid.UUID,
    *,
    status: str = "pending",
    file_key: str | None = None,
    expires_at: datetime | None = None,
) -> ExportRecord:
    return ExportRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        status=status,
        file_key=file_key,
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )


def make_deletion_record(
    user_id: uuid.UUID,
    *,
    purge_after: datetime,
    status: str = "pending",
    requested_at: datetime | None = None,
) -> DeletionRecord:
    return DeletionRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        requested_at=requested_at or datetime.now(UTC),
        purge_after=purge_after,
        status=status,
    )

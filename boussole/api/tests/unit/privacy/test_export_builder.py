"""Tests de la constitution d'archive RGPD (worker) — fakes uniquement."""

import json
import uuid
from datetime import UTC, datetime, timedelta

from app.modules.privacy.export_builder import build_export
from tests.unit.privacy.conftest import (
    FakeModules,
    FakeStorage,
    InMemoryPrivacyRepository,
)


async def _pending_export(repository: InMemoryPrivacyRepository) -> tuple[uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    record = await repository.create_export(user_id, datetime.now(UTC))
    return record.id, user_id


class TestBuildExport:
    async def test_agrege_tous_les_modules_du_registre(self) -> None:
        repository = InMemoryPrivacyRepository()
        storage = FakeStorage()
        modules = FakeModules(names=("alpha", "beta"))
        export_id, user_id = await _pending_export(repository)
        now = datetime.now(UTC)

        result = await build_export(
            export_id,
            repository=repository,
            storage=storage,
            registry=modules.registry(),
            now=now,
        )

        assert result.status == "ready"
        assert result.incomplete_modules == ()
        assert modules.exported == [("alpha", user_id), ("beta", user_id)]

        record = repository.exports[export_id]
        assert record.status == "ready"
        assert record.file_key is not None
        assert record.expires_at == now + timedelta(days=7)

        archive = json.loads(storage.objects[record.file_key])
        assert archive["user_id"] == str(user_id)
        assert archive["modules"] == {
            "alpha": {"alpha_data": str(user_id)},
            "beta": {"beta_data": str(user_id)},
        }
        assert "incomplete_modules" not in archive

    async def test_echec_d_un_module_signale_jamais_silencieux(self) -> None:
        repository = InMemoryPrivacyRepository()
        storage = FakeStorage()
        modules = FakeModules(names=("alpha", "beta"), failing=frozenset({"beta"}))
        export_id, _user_id = await _pending_export(repository)

        result = await build_export(
            export_id, repository=repository, storage=storage, registry=modules.registry()
        )

        # L'archive sort quand même, l'incomplétude est EXPLICITE.
        assert result.status == "ready"
        assert result.incomplete_modules == ("beta",)
        record = repository.exports[export_id]
        archive = json.loads(storage.objects[record.file_key])
        assert archive["incomplete_modules"] == ["beta"]
        assert "alpha" in archive["modules"]
        assert "beta" not in archive["modules"]
        # …et journalisée dans l'audit.
        ready = [e for e in repository.audit_entries if e["action"] == "privacy_export_ready"]
        assert ready and ready[0]["meta"] == {"incomplete_modules": ["beta"]}

    async def test_idempotent_un_export_deja_traite_est_ignore(self) -> None:
        repository = InMemoryPrivacyRepository()
        storage = FakeStorage()
        modules = FakeModules(names=("alpha",))
        export_id, _ = await _pending_export(repository)

        first = await build_export(
            export_id, repository=repository, storage=storage, registry=modules.registry()
        )
        second = await build_export(
            export_id, repository=repository, storage=storage, registry=modules.registry()
        )

        assert first.status == "ready"
        assert second.status == "skipped"
        assert len(storage.objects) == 1
        assert len(modules.exported) == 1  # pas de second passage

    async def test_export_inconnu_est_ignore(self) -> None:
        repository = InMemoryPrivacyRepository()
        result = await build_export(
            uuid.uuid4(),
            repository=repository,
            storage=FakeStorage(),
            registry=FakeModules(names=("alpha",)).registry(),
        )
        assert result.status == "skipped"

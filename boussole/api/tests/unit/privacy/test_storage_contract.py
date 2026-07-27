"""Tests du stockage objet RÉEL dans le flux privacy (C2).

``app/modules/privacy/storage.py`` déclarait un ``ObjectStorage`` **async**
alors que ``app/core/storage.py`` est **synchrone** : la résolution paresseuse
retournait le stockage sync et ``await storage.put(...)`` levait
``TypeError``. Conséquences en production :

- ``privacy_export`` échouait TOUJOURS (export « pending » à vie, quota
  consommé pour rien) ;
- dans ``purge_runner``, ``await storage.delete(...)`` échouait et entraînait
  dans sa chute ``delete_exports_for_user()`` : **l'archive contenant le dump
  personnel complet survivait indéfiniment à la suppression du compte**.

Les fakes de test, eux aussi async, rendaient le bug invisible. Ces tests
exercent donc le VRAI ``get_object_storage()`` (LocalDiskStorage sur
``tmp_path``) de bout en bout : export construit → relu → purgé.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.storage import LocalDiskStorage, ObjectNotFoundError, get_object_storage
from app.modules.privacy.export_builder import build_export
from app.modules.privacy.purge_runner import purge_due_accounts
from tests.unit.privacy.conftest import (
    FakeModules,
    FakeStorage,
    InMemoryPrivacyRepository,
    make_deletion_record,
    make_export_record,
)


@pytest.fixture
def real_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalDiskStorage:
    """Le VRAI ``get_object_storage()``, enraciné dans ``tmp_path``."""
    monkeypatch.setattr(
        "app.core.storage.get_settings",
        lambda: SimpleNamespace(storage_local_path=str(tmp_path)),
    )
    storage = get_object_storage()
    assert isinstance(storage, LocalDiskStorage)  # pas un fake : le vrai backend
    return storage


class TestContratSynchrone:
    """Le fake doit se comporter EXACTEMENT comme le stockage réel."""

    def test_get_absent_leve_object_not_found(self, real_storage: LocalDiskStorage) -> None:
        with pytest.raises(ObjectNotFoundError):
            real_storage.get("privacy-exports/inexistant.json")

    def test_le_fake_leve_la_meme_erreur_que_le_vrai(self) -> None:
        with pytest.raises(ObjectNotFoundError):
            FakeStorage().get("privacy-exports/inexistant.json")

    def test_delete_est_idempotent_des_deux_cotes(
        self, real_storage: LocalDiskStorage
    ) -> None:
        real_storage.delete("privacy-exports/inexistant.json")
        FakeStorage().delete("privacy-exports/inexistant.json")

    def test_put_get_sont_synchrones(self, real_storage: LocalDiskStorage) -> None:
        # Un `await` sur ces appels lèverait TypeError — c'était le bug C2.
        real_storage.put("privacy-exports/a.json", b"{}")
        assert real_storage.get("privacy-exports/a.json") == b"{}"


class TestBoutEnBoutAvecLeStockageReel:
    async def test_export_construit_relu_puis_purge(
        self, real_storage: LocalDiskStorage, tmp_path: Path
    ) -> None:
        repository = InMemoryPrivacyRepository()
        modules = FakeModules(names=("alpha",))
        user_id = uuid.uuid4()
        record = await repository.create_export(user_id, datetime.now(UTC))

        # 1. L'archive se construit RÉELLEMENT (avant : TypeError systématique).
        result = await build_export(
            record.id,
            repository=repository,
            storage=real_storage,
            registry=modules.registry(),
        )
        assert result.status == "ready"
        assert result.file_key is not None
        assert (tmp_path / result.file_key).is_file()

        # 2. …et se relit depuis le disque.
        archive = json.loads(real_storage.get(result.file_key))
        assert archive["user_id"] == str(user_id)
        assert archive["modules"]["alpha"] == {"alpha_data": str(user_id)}

        # 3. La suppression de compte emporte l'objet ET la ligne.
        deletion = make_deletion_record(
            user_id, purge_after=datetime.now(UTC) - timedelta(days=1)
        )
        repository.deletion_requests[deletion.id] = deletion
        outcomes = await purge_due_accounts(
            repository=repository, storage=real_storage, registry=modules.registry()
        )

        assert outcomes[0].purged is True
        assert not (tmp_path / result.file_key).exists()
        with pytest.raises(ObjectNotFoundError):
            real_storage.get(result.file_key)
        assert repository.exports == {}
        assert repository.deletion_requests[deletion.id].status == "purged"


class TestArchiveNeSurvitPasALaPurge:
    async def test_les_lignes_partent_meme_si_le_stockage_echoue(self) -> None:
        """Régression C2 : ``delete_exports_for_user`` hors du try des objets."""

        class ExplodingStorage(FakeStorage):
            def delete(self, key: str) -> None:
                raise OSError("backend objet injoignable")

        repository = InMemoryPrivacyRepository()
        user_id = uuid.uuid4()
        export = make_export_record(user_id, status="ready", file_key="archives/a.json")
        repository.exports[export.id] = export
        deletion = make_deletion_record(
            user_id, purge_after=datetime.now(UTC) - timedelta(days=1)
        )
        repository.deletion_requests[deletion.id] = deletion

        outcomes = await purge_due_accounts(
            repository=repository,
            storage=ExplodingStorage(),
            registry=FakeModules(names=("alpha",)).registry(),
        )

        # L'échec objet est signalé (purge partielle, retentée)…
        assert outcomes[0].purged is False
        assert "privacy" in outcomes[0].failed_modules
        # …mais la LIGNE privacy_exports, elle, a bien été supprimée : plus
        # aucune trace (ni file_key) ne survit à la suppression du compte.
        assert repository.exports == {}

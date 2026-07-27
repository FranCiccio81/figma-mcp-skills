"""Tests de la purge planifiée (F-Q, AC-Q-2, D21) — fakes uniquement."""

import uuid
from datetime import UTC, datetime, timedelta

from app.modules.privacy.purge_runner import purge_due_accounts
from app.modules.privacy.signing import subject_key_for
from tests.unit.privacy.conftest import (
    FakeModules,
    FakeStorage,
    InMemoryPrivacyRepository,
    make_deletion_record,
    make_export_record,
)

NOW = datetime.now(UTC)


def _due_request(
    repository: InMemoryPrivacyRepository, user_id: uuid.UUID
) -> uuid.UUID:
    record = make_deletion_record(user_id, purge_after=NOW - timedelta(days=1))
    repository.deletion_requests[record.id] = record
    return record.id


class TestPurgeDueAccounts:
    async def test_purge_echue_appelle_tous_les_modules_et_marque_purged(self) -> None:
        repository = InMemoryPrivacyRepository()
        storage = FakeStorage()
        modules = FakeModules(names=("alpha", "beta"))
        user_id = uuid.uuid4()
        deletion_id = _due_request(repository, user_id)
        # Données propres du module privacy : une archive d'export à purger.
        export = make_export_record(user_id, status="ready", file_key="archives/a.json")
        repository.exports[export.id] = export
        storage.objects["archives/a.json"] = b"{}"
        # Une entrée d'audit rattachée à l'utilisateur, à anonymiser.
        await repository.add_audit(user_id, "login")

        outcomes = await purge_due_accounts(
            repository=repository, storage=storage, registry=modules.registry(), now=NOW
        )

        assert len(outcomes) == 1
        assert outcomes[0].purged is True
        assert outcomes[0].failed_modules == ()
        # Tous les modules du registre ont été purgés pour CET utilisateur.
        assert modules.purged == [("alpha", user_id), ("beta", user_id)]
        # Archives d'export purgées (objets + lignes) — F-Q alt. 5.
        assert storage.objects == {}
        assert repository.exports == {}
        # Demande marquée purged.
        assert repository.deletion_requests[deletion_id].status == "purged"
        # Audit anonymisé : user_id → None, subject_key = hash irréversible.
        user_entries = [e for e in repository.audit_entries if e["action"] == "login"]
        assert user_entries[0]["user_id"] is None
        assert user_entries[0]["subject_key"] == subject_key_for(user_id)
        # Événement final anonyme.
        completed = [
            e for e in repository.audit_entries if e["action"] == "account_purge_completed"
        ]
        assert completed and completed[0]["user_id"] is None

    async def test_demande_non_echue_intacte(self) -> None:
        repository = InMemoryPrivacyRepository()
        modules = FakeModules()
        record = make_deletion_record(uuid.uuid4(), purge_after=NOW + timedelta(days=10))
        repository.deletion_requests[record.id] = record

        outcomes = await purge_due_accounts(
            repository=repository,
            storage=FakeStorage(),
            registry=modules.registry(),
            now=NOW,
        )
        assert outcomes == []
        assert modules.purged == []
        assert repository.deletion_requests[record.id].status == "pending"

    async def test_idempotente_une_purge_faite_n_est_pas_rejouee(self) -> None:
        repository = InMemoryPrivacyRepository()
        storage = FakeStorage()
        modules = FakeModules(names=("alpha",))
        _due_request(repository, uuid.uuid4())

        first = await purge_due_accounts(
            repository=repository, storage=storage, registry=modules.registry(), now=NOW
        )
        second = await purge_due_accounts(
            repository=repository, storage=storage, registry=modules.registry(), now=NOW
        )

        assert len(first) == 1 and first[0].purged
        assert second == []  # plus rien d'échu : demande déjà purged
        assert len(modules.purged) == 1  # aucun second appel de module

    async def test_echec_partiel_signale_et_retente(self) -> None:
        repository = InMemoryPrivacyRepository()
        storage = FakeStorage()
        user_id = uuid.uuid4()
        deletion_id = _due_request(repository, user_id)
        await repository.add_audit(user_id, "login")

        failing = FakeModules(names=("alpha", "beta"), failing=frozenset({"beta"}))
        outcomes = await purge_due_accounts(
            repository=repository, storage=storage, registry=failing.registry(), now=NOW
        )

        # Statut PARTIEL explicite : module en échec nommé, demande pending.
        assert len(outcomes) == 1
        assert outcomes[0].purged is False
        assert outcomes[0].failed_modules == ("beta",)
        # Les autres modules ont quand même été purgés.
        assert ("alpha", user_id) in failing.purged
        assert repository.deletion_requests[deletion_id].status == "pending"
        # Pas d'anonymisation prématurée tant que la purge n'est pas complète.
        entries = [e for e in repository.audit_entries if e["action"] == "login"]
        assert entries[0]["user_id"] == user_id

        # Au passage suivant (module réparé), la purge aboutit.
        repaired = FakeModules(names=("alpha", "beta"))
        outcomes = await purge_due_accounts(
            repository=repository, storage=storage, registry=repaired.registry(), now=NOW
        )
        assert len(outcomes) == 1 and outcomes[0].purged is True
        assert repository.deletion_requests[deletion_id].status == "purged"
        entries = [e for e in repository.audit_entries if e["action"] == "login"]
        assert entries[0]["user_id"] is None
        assert entries[0]["subject_key"] == subject_key_for(user_id)

"""Tests du ménage des archives expirées (M3).

Le lien signé d'un export meurt à J+7 mais l'OBJET stocké, lui, survivait
indéfiniment : un dump personnel complet restait conservé sans finalité
(minimisation, D09). ``maintenance.purge_expired_exports`` supprime l'objet
ET la ligne ``privacy_exports`` de toute archive échue.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.modules.privacy.purge_runner import purge_expired_exports
from tests.unit.privacy.conftest import (
    FakeStorage,
    InMemoryPrivacyRepository,
    make_export_record,
)

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def _export(
    repository: InMemoryPrivacyRepository,
    storage: FakeStorage,
    *,
    expires_at: datetime | None,
    key: str,
) -> uuid.UUID:
    record = make_export_record(
        uuid.uuid4(), status="ready", file_key=key, expires_at=expires_at
    )
    repository.exports[record.id] = record
    storage.objects[key] = b'{"modules": {}}'
    return record.id


class TestPurgeExpiredExports:
    async def test_supprime_objet_et_ligne_des_archives_echues(self) -> None:
        repository, storage = InMemoryPrivacyRepository(), FakeStorage()
        expired = _export(
            repository, storage, expires_at=NOW - timedelta(days=1), key="exports/vieux.json"
        )

        outcome = await purge_expired_exports(
            repository=repository, storage=storage, now=NOW
        )

        assert outcome.deleted_objects == 1
        assert outcome.deleted_rows == 1
        assert outcome.failed_keys == ()
        assert expired not in repository.exports
        assert storage.objects == {}

    async def test_epargne_les_archives_encore_valides(self) -> None:
        repository, storage = InMemoryPrivacyRepository(), FakeStorage()
        vivant = _export(
            repository, storage, expires_at=NOW + timedelta(days=3), key="exports/frais.json"
        )
        pending = make_export_record(uuid.uuid4())  # jamais expires_at
        repository.exports[pending.id] = pending

        outcome = await purge_expired_exports(
            repository=repository, storage=storage, now=NOW
        )

        assert outcome.deleted_rows == 0
        assert vivant in repository.exports
        assert pending.id in repository.exports
        assert storage.objects.keys() == {"exports/frais.json"}

    async def test_idempotente(self) -> None:
        repository, storage = InMemoryPrivacyRepository(), FakeStorage()
        _export(
            repository, storage, expires_at=NOW - timedelta(days=1), key="exports/a.json"
        )

        first = await purge_expired_exports(repository=repository, storage=storage, now=NOW)
        second = await purge_expired_exports(repository=repository, storage=storage, now=NOW)

        assert first.deleted_rows == 1
        assert second.deleted_rows == 0
        assert second.failed_keys == ()

    async def test_objet_manquant_n_empeche_pas_la_suppression_de_la_ligne(self) -> None:
        repository, storage = InMemoryPrivacyRepository(), FakeStorage()
        orphelin = _export(
            repository, storage, expires_at=NOW - timedelta(days=8), key="exports/b.json"
        )
        del storage.objects["exports/b.json"]  # objet déjà disparu

        outcome = await purge_expired_exports(
            repository=repository, storage=storage, now=NOW
        )

        # delete est idempotent par contrat : aucun échec, la ligne part.
        assert outcome.failed_keys == ()
        assert outcome.deleted_rows == 1
        assert orphelin not in repository.exports

    async def test_echec_du_stockage_signale_mais_ligne_supprimee(self) -> None:
        class ExplodingStorage(FakeStorage):
            def delete(self, key: str) -> None:
                raise OSError("backend objet injoignable")

        repository, storage = InMemoryPrivacyRepository(), ExplodingStorage()
        echu = _export(
            repository, storage, expires_at=NOW - timedelta(days=1), key="exports/c.json"
        )

        outcome = await purge_expired_exports(
            repository=repository, storage=storage, now=NOW
        )

        assert outcome.failed_keys == ("exports/c.json",)
        assert outcome.deleted_objects == 0
        # La ligne part quand même : une ligne expirée ne doit pas être figée
        # en base par un objet orphelin.
        assert outcome.deleted_rows == 1
        assert echu not in repository.exports


class TestPlanification:
    def test_la_tache_est_enregistree_et_planifiee_quotidiennement(self) -> None:
        from app.workers.celery_app import celery_app

        entry = celery_app.conf.beat_schedule["maintenance-purge-expired-exports"]
        assert entry["task"] == "maintenance.purge_expired_exports"
        # crontab quotidien : une heure et une minute fixes, tous les jours.
        schedule = entry["schedule"]
        assert schedule.hour == {4}
        assert schedule.minute == {45}
        assert schedule.day_of_week == set(range(7))

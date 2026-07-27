"""Tests de ``jobs.purge_user`` / ``jobs.export_user`` (C1, D21).

Le module ``jobs`` était resté un stub ``NotImplementedError`` : au J+30 la
purge RGPD échouait dessus, ``purge_runner`` passait au suivant sans jamais
atteindre l'anonymisation d'audit ni ``mark_deletion_purged`` — les
``saved_jobs`` survivaient et la demande restait « pending » à vie.

Fakes uniquement : le repository de purge est injectable.
"""

import uuid
from datetime import UTC, datetime

from app.modules.jobs.purge import SavedJobRow, export_user, purge_user


class FakeSavedJobsRepository:
    """Implémentation en mémoire de ``SavedJobsPurgeRepository``."""

    def __init__(self, rows: dict[uuid.UUID, list[SavedJobRow]] | None = None) -> None:
        self.rows = rows or {}
        self.deleted: list[uuid.UUID] = []

    async def list_saved_for_user(self, user_id: uuid.UUID) -> list[SavedJobRow]:
        return list(self.rows.get(user_id, []))

    async def delete_saved_for_user(self, user_id: uuid.UUID) -> None:
        self.deleted.append(user_id)
        self.rows.pop(user_id, None)


CREATED = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _rows() -> list[SavedJobRow]:
    return [
        SavedJobRow(job_posting_id=uuid.uuid4(), state="saved", created_at=CREATED),
        SavedJobRow(job_posting_id=uuid.uuid4(), state="hidden", created_at=None),
    ]


class TestPurgeUser:
    async def test_supprime_les_saved_jobs_de_l_utilisateur(self) -> None:
        user_id = uuid.uuid4()
        repository = FakeSavedJobsRepository({user_id: _rows()})

        await purge_user(user_id, repository)

        assert repository.deleted == [user_id]
        assert await repository.list_saved_for_user(user_id) == []

    async def test_ne_leve_jamais_not_implemented(self) -> None:
        # Régression C1 directe : c'est cette exception qui bloquait la purge.
        await purge_user(uuid.uuid4(), FakeSavedJobsRepository())

    async def test_idempotente(self) -> None:
        user_id = uuid.uuid4()
        repository = FakeSavedJobsRepository({user_id: _rows()})
        await purge_user(user_id, repository)
        await purge_user(user_id, repository)
        assert repository.deleted == [user_id, user_id]

    async def test_ne_touche_pas_les_autres_utilisateurs(self) -> None:
        mine, other = uuid.uuid4(), uuid.uuid4()
        repository = FakeSavedJobsRepository({mine: _rows(), other: _rows()})
        await purge_user(mine, repository)
        assert len(await repository.list_saved_for_user(other)) == 2


class TestExportUser:
    async def test_exporte_l_etat_sauvegarde_ou_masque(self) -> None:
        user_id = uuid.uuid4()
        rows = _rows()
        repository = FakeSavedJobsRepository({user_id: rows})

        export = await export_user(user_id, repository)

        assert export == {
            "saved_jobs": [
                {
                    "job_posting_id": str(rows[0].job_posting_id),
                    "state": "saved",
                    "created_at": CREATED.isoformat(),
                },
                {
                    "job_posting_id": str(rows[1].job_posting_id),
                    "state": "hidden",
                    "created_at": None,
                },
            ]
        }

    async def test_sans_donnee_retourne_un_dict_vide(self) -> None:
        assert await export_user(uuid.uuid4(), FakeSavedJobsRepository()) == {}

    async def test_ne_leve_jamais_not_implemented(self) -> None:
        await export_user(uuid.uuid4(), FakeSavedJobsRepository())

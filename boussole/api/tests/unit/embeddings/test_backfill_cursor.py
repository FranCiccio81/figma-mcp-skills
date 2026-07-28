"""Le recalcul complet (``force=True``) doit PROGRESSER.

Défaut relevé à la finalisation : le filtre ``embedding IS NULL`` n'est posé
que si ``force=False``. En mode forcé il ne restait donc qu'un ``LIMIT``, sans
curseur : chaque exécution reprenait les mêmes N lignes les plus récentes. La
commande prescrite au runbook après le changement de tokenisation M6 —
« rejouer jusqu'à épuisement » — ne terminait jamais.

Ces tests portent sur la REQUÊTE, là où vit le défaut.
"""

import uuid

from sqlalchemy.dialects import postgresql

from app.workers.embedding_tasks import _job_targets


def _compiled(force: bool, after_id: uuid.UUID | None) -> str:
    """Compile la requête réelle sans base — le défaut est dans le SQL."""

    class _Session:
        captured: object = None

        async def execute(self, stmt: object) -> list:
            _Session.captured = stmt
            return []

    import asyncio

    session = _Session()
    asyncio.run(_job_targets(session, 100, force, after_id))  # type: ignore[arg-type]
    return str(
        _Session.captured.compile(dialect=postgresql.dialect())  # type: ignore[attr-defined]
    )


class TestRecalculComplet:
    def test_le_mode_force_parcourt_par_keyset(self) -> None:
        sql = _compiled(force=True, after_id=uuid.uuid4())
        assert "job_postings.id >" in sql, (
            "sans borne sur l'id, le recalcul reprend les mêmes lignes à chaque run"
        )
        assert "ORDER BY job_postings.id" in sql

    def test_le_mode_force_ne_filtre_pas_sur_embedding_null(self) -> None:
        """C'est le point : tout le corpus doit être retraité."""
        sql = _compiled(force=True, after_id=None)
        assert "embedding IS NULL" not in sql

    def test_le_premier_run_force_part_du_debut(self) -> None:
        sql = _compiled(force=True, after_id=None)
        assert "job_postings.id >" not in sql
        assert "ORDER BY job_postings.id" in sql


class TestRattrapageQuotidien:
    def test_le_beat_filtre_toujours_les_vecteurs_manquants(self) -> None:
        """Non-régression : le rattrapage converge par rétrécissement du
        périmètre, il n'a pas besoin de curseur."""
        sql = _compiled(force=False, after_id=None)
        assert "embedding IS NULL" in sql
        assert "last_seen_at" in sql

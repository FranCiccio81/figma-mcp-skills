"""Purge RGPD d'``ai_calls`` : ANONYMISATION, jamais suppression (RM-Q-2).

Le point vérifié est celui de 11 §2 : après la purge d'un compte, les
lignes existent toujours (métadonnées agrégées : coût, latence, taux
d'échec) mais ne sont plus rattachables à une personne.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from app.ai.calls import AiCall
from app.modules.ai_calls.purge import export_user, purge_user


class InMemoryAiCallsRepository:
    """Implémentation en mémoire du protocole ``AiCallsRepository``."""

    def __init__(self, rows: list[AiCall] | None = None) -> None:
        self.rows = rows or []

    async def anonymize_user(self, user_id: uuid.UUID) -> int:
        touched = 0
        for row in self.rows:
            if row.user_id == user_id:
                row.user_id = None
                touched += 1
        return touched

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[AiCall]:
        return [row for row in self.rows if row.user_id == user_id]


def a_call(user_id: uuid.UUID | None, **overrides: object) -> AiCall:
    values: dict[str, object] = {
        "task": "extract_cv",
        "prompt_version": "extract_cv/1.0.0",
        "model": "claude-sonnet-5",
        "user_id": user_id,
        "input_tokens": 1200,
        "output_tokens": 340,
        "latency_ms": 8200,
        "status": "success",
        "error_code": None,
        "created_at": datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return AiCall(**values)


class TestPurgeAnonymisante:
    async def test_les_lignes_sont_detachees_et_non_supprimees(self) -> None:
        user_id = uuid.uuid4()
        autre = uuid.uuid4()
        repo = InMemoryAiCallsRepository([a_call(user_id), a_call(user_id), a_call(autre)])

        await purge_user(user_id, repo)

        # Les trois lignes SUBSISTENT (métadonnées agrégées, 11 §2)…
        assert len(repo.rows) == 3
        # …celles de l'utilisateur purgé ne portent plus son identifiant…
        assert [row.user_id for row in repo.rows[:2]] == [None, None]
        # …et les autres utilisateurs ne sont pas touchés.
        assert repo.rows[2].user_id == autre

    async def test_les_metadonnees_survivent_intactes_a_la_purge(self) -> None:
        user_id = uuid.uuid4()
        repo = InMemoryAiCallsRepository([a_call(user_id)])

        await purge_user(user_id, repo)

        row = repo.rows[0]
        assert (row.task, row.model, row.status) == ("extract_cv", "claude-sonnet-5", "success")
        assert (row.input_tokens, row.output_tokens, row.latency_ms) == (1200, 340, 8200)

    async def test_elle_est_idempotente(self) -> None:
        user_id = uuid.uuid4()
        repo = InMemoryAiCallsRepository([a_call(user_id)])

        await purge_user(user_id, repo)
        await purge_user(user_id, repo)  # re-livraison / re-tentative J+30

        assert repo.rows[0].user_id is None

    async def test_un_utilisateur_sans_appel_est_un_no_op(self) -> None:
        repo = InMemoryAiCallsRepository([])

        await purge_user(uuid.uuid4(), repo)

        assert repo.rows == []

    async def test_apres_purge_l_export_ne_retourne_plus_rien(self) -> None:
        user_id = uuid.uuid4()
        repo = InMemoryAiCallsRepository([a_call(user_id)])

        await purge_user(user_id, repo)

        assert await export_user(user_id, repo) == {}


class TestExport:
    async def test_il_expose_les_metadonnees_et_aucun_contenu(self) -> None:
        user_id = uuid.uuid4()
        repo = InMemoryAiCallsRepository([a_call(user_id, status="failed", error_code="timeout")])

        payload = await export_user(user_id, repo)

        (ligne,) = payload["ai_calls"]
        assert ligne == {
            "task": "extract_cv",
            "prompt_version": "extract_cv/1.0.0",
            "model": "claude-sonnet-5",
            "input_tokens": 1200,
            "output_tokens": 340,
            "latency_ms": 8200,
            "status": "failed",
            "error_code": "timeout",
            "created_at": "2026-07-01T10:00:00+00:00",
        }
        # Rien à exporter d'autre : la table ne contient aucun contenu.
        assert "prompt" not in ligne and "response" not in ligne

    async def test_un_utilisateur_sans_appel_exporte_un_dictionnaire_vide(self) -> None:
        assert await export_user(uuid.uuid4(), InMemoryAiCallsRepository([])) == {}

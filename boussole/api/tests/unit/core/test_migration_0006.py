"""(12) La migration 0006 ne doit pas bloquer les écritures de ``ai_calls``.

``ai_calls`` est la table la plus volumineuse du système (≤ 10 k lignes/jour
pour ``extract_job`` seule, 08 §2.2). Écrite naïvement, la migration prenait
deux verrous bloquants :

- ``ALTER TABLE … ADD CONSTRAINT … CHECK`` garde un ``ACCESS EXCLUSIVE``
  pendant TOUT le scan de validation — aucun ``INSERT`` de journal ne passe ;
- ``CREATE INDEX`` sans ``CONCURRENTLY`` prend un ``SHARE``, qui bloque
  également les écritures le temps de la construction.

Le déroulé correct est ``NOT VALID`` → ``VALIDATE CONSTRAINT`` (scan sous
``SHARE UPDATE EXCLUSIVE``) → ``CREATE INDEX CONCURRENTLY`` (hors
transaction, d'où ``autocommit_block``).

Contrôle STRUCTUREL : l'exécution réelle est couverte par
``tests/integration`` (``alembic upgrade head`` sur un PostgreSQL réel).
"""

import re
from pathlib import Path

import pytest

MIGRATION = (
    Path(__file__).resolve().parents[3] / "alembic" / "versions" / "0006_ai_calls.py"
)
SOURCE = MIGRATION.read_text(encoding="utf-8")
#: Corps du fichier sans la docstring de module (qui décrit le problème et
#: contient donc les mots-clés qu'on cherche dans le CODE).
CODE = SOURCE.split('"""', 2)[2]


class TestMigrationSansVerrouBloquant:
    def test_la_contrainte_est_posee_not_valid_puis_validee(self) -> None:
        assert re.search(r"ADD CONSTRAINT\s+ck_ai_calls_status.*NOT VALID", CODE, re.S)
        assert "VALIDATE CONSTRAINT ck_ai_calls_status" in CODE

    def test_la_contrainte_n_est_plus_posee_par_create_check_constraint(self) -> None:
        # ``op.create_check_constraint`` émet un ADD CONSTRAINT validant, donc
        # un ACCESS EXCLUSIVE pendant tout le scan.
        assert "create_check_constraint" not in CODE

    def test_l_index_est_cree_concurrently(self) -> None:
        assert "postgresql_concurrently=True" in CODE

    def test_l_index_concurrently_est_hors_transaction(self) -> None:
        # CREATE INDEX CONCURRENTLY échoue à l'intérieur d'une transaction :
        # sans autocommit_block, la migration ne passe tout simplement pas.
        assert "autocommit_block()" in CODE

    def test_le_downgrade_reste_symetrique(self) -> None:
        downgrade = CODE.split("def downgrade()", 1)[1]
        assert "postgresql_concurrently=True" in downgrade
        assert "autocommit_block()" in downgrade
        assert "drop_constraint" in downgrade

    @pytest.mark.parametrize("statut", ["success", "schema_retry", "failed"])
    def test_le_vocabulaire_des_statuts_est_inchange(self, statut: str) -> None:
        from app.ai.calls import CALL_STATUSES

        assert f"'{statut}'" in CODE
        assert statut in CALL_STATUSES

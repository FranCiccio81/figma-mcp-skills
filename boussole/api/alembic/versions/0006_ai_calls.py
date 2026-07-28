"""Alignement de ``ai_calls`` sur le contrat applicatif (11 §1, 08 §7.3).

Revision ID: 0006
Revises: 0005

CONSTAT (vérifié) : contrairement à ce que laissait penser le TODO du
registre de purge, la table ``ai_calls`` **existe déjà** — elle est créée
par la migration 0001, qui exécute ``sql/0001_initial.sql`` (copie conforme
de ``initial-schema.sql``, ligne « CREATE TABLE ai_calls »), avec son enum
``ai_task`` et l'index ``idx_ai_calls_task_time``. Cette migration ne la
recrée donc PAS : elle ajoute ce qui manquait pour que la table soit
réellement exploitable par l'application.

1. ``ck_ai_calls_status`` — le vocabulaire des statuts
   (``success | schema_retry | failed``) n'existait qu'en COMMENTAIRE SQL :
   rien n'empêchait d'écrire n'importe quoi dans une colonne ``text`` dont
   dépendent les métriques et les alertes de 08 §7.3. La contrainte le rend
   opposable.
2. ``ix_ai_calls_user_id`` (partiel, ``WHERE user_id IS NOT NULL``) — la
   purge RGPD anonymise par utilisateur (``UPDATE … WHERE user_id = :id``,
   RM-Q-2) : sans index, la purge d'un compte scanne toute la table, et
   celle-ci croît avec le volume d'appels IA (≤ 10 k/j sur ``extract_job``
   seule, 08 §2.2). Partiel : les lignes déjà anonymisées — la majorité à
   terme — n'ont pas à être indexées.

Rien d'autre n'est modifié : colonnes, types et FK ``ON DELETE SET NULL``
(qui porte déjà la sémantique d'anonymisation) sont conformes.

MIGRATION SANS INTERRUPTION (12)
--------------------------------
``ai_calls`` est la table la plus volumineuse du système (≤ 10 k lignes/jour
pour ``extract_job`` seule). Écrite naïvement, cette migration prend deux
verrous bloquants sur toute la durée du traitement :

- ``ADD CONSTRAINT … CHECK`` prend un ``ACCESS EXCLUSIVE`` **pendant le scan
  complet** de la table : aucun ``INSERT`` de journal ne passe, donc aucun
  appel IA n'est journalisé, pendant plusieurs minutes ;
- ``CREATE INDEX`` (sans ``CONCURRENTLY``) prend un ``SHARE`` : les écritures
  sont bloquées le temps de la construction.

D'où : ``NOT VALID`` (le verrou fort ne dure que le temps de poser la
contrainte — elle s'applique dès lors aux nouvelles lignes) puis
``VALIDATE CONSTRAINT`` (scan sous ``SHARE UPDATE EXCLUSIVE``, qui laisse
passer les écritures), et ``CREATE INDEX CONCURRENTLY``. Ce dernier ne peut
pas s'exécuter dans une transaction : d'où le ``autocommit_block``.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_STATUS_CHECK = "status IN ('success', 'schema_retry', 'failed')"


def upgrade() -> None:
    # 1. Contrainte posée NOT VALID : verrou fort, mais instantané.
    op.execute(
        sa.text(
            f"ALTER TABLE ai_calls ADD CONSTRAINT ck_ai_calls_status "
            f"CHECK ({_STATUS_CHECK}) NOT VALID"
        )
    )
    # 2. Validation de l'existant : scan sous SHARE UPDATE EXCLUSIVE — les
    #    INSERT du journal continuent de passer.
    op.execute(sa.text("ALTER TABLE ai_calls VALIDATE CONSTRAINT ck_ai_calls_status"))
    # 3. Index partiel CONCURRENTLY (hors transaction, d'où l'autocommit).
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_ai_calls_user_id",
            "ai_calls",
            ["user_id"],
            unique=False,
            postgresql_where=sa.text("user_id IS NOT NULL"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_ai_calls_user_id",
            table_name="ai_calls",
            postgresql_concurrently=True,
            if_exists=True,
        )
    op.drop_constraint("ck_ai_calls_status", "ai_calls", type_="check")

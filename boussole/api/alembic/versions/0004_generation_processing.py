"""Colonnes de cycle de vie applicatif de ``generated_documents`` — jalon M4.

Revision ID: 0004
Revises: 0003

Le contrat API (openapi.yaml ``GeneratedDocument.status``) expose cinq états :
``pending | draft | validated | exported | failed`` — mais l'enum SQL
``generated_doc_status`` (initial-schema.sql) n'en connaît que trois
(``draft | validated | exported``). Plutôt que d'altérer l'enum (verrou +
incompatibilité avec le CHECK ``exported ⇒ validated_at``), 🟡 les états
transitoires de la génération asynchrone sont portés par une colonne
applicative additive ``processing_status`` :

- ``pending``    : ligne créée, tâche ``ai.generate`` en file ;
- ``processing`` : tâche en cours d'exécution ;
- ``ready``      : génération aboutie — l'état contractuel redevient
  l'enum SQL (``draft``/``validated``/``exported``) ;
- ``failed``     : échec propre (D08) — ``error_code`` renseigné
  (``schema_error``, ``grounding_error``, ``provider_error``…).

Colonnes additives complémentaires (aucune colonne du schéma initial n'est
modifiée ; ``content`` reste NOT NULL — un document pending/failed porte
``'{}'::jsonb``, l'API le sert comme ``null`` 🟡) :

- ``anchoring_check`` : résultat du contrôle d'ancrage post-génération
  (``{"status": "passed"|"failed", "unanchored_claims": [...]}``) — null
  tant que rien n'a été généré, remis à null par une édition manuelle (Q6) ;
- ``manually_edited`` : l'édition manuelle (PATCH) lève le contrôle
  d'ancrage automatique — le contenu passe sous la responsabilité de
  l'utilisateur (rappel UI avant validation, D10) ;
- ``options`` : options de génération (tone/language/length) — nécessaires
  au worker pour construire le prompt, absentes du schéma initial.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default 'ready' : les lignes préexistantes (aucune en pratique
    # avant M4) sont des documents complets — les nouvelles lignes sont
    # créées 'pending' par l'application.
    op.add_column(
        "generated_documents",
        sa.Column(
            "processing_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ready'"),
        ),
    )
    op.add_column("generated_documents", sa.Column("error_code", sa.Text(), nullable=True))
    op.add_column(
        "generated_documents",
        sa.Column("anchoring_check", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "generated_documents",
        sa.Column(
            "manually_edited",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "generated_documents",
        sa.Column(
            "options",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "ck_generated_documents_processing_status",
        "generated_documents",
        "processing_status IN ('pending','processing','ready','failed')",
    )
    # Liste par curseur keyset (created_at DESC, id DESC) scopée utilisateur.
    op.create_index(
        "idx_generated_docs_user_created",
        "generated_documents",
        ["user_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_generated_docs_user_created", table_name="generated_documents")
    op.drop_constraint(
        "ck_generated_documents_processing_status",
        "generated_documents",
        type_="check",
    )
    op.drop_column("generated_documents", "options")
    op.drop_column("generated_documents", "manually_edited")
    op.drop_column("generated_documents", "anchoring_check")
    op.drop_column("generated_documents", "error_code")
    op.drop_column("generated_documents", "processing_status")

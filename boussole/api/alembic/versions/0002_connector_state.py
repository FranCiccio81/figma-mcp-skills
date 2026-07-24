"""Table ``connector_state`` — curseur de fetch incrémental (07 §4.3).

Revision ID: 0002
Revises: 0001

Une ligne par source : ``cursor`` (opaque, ISO-8601 pour France Travail),
``last_sync_at`` (dernier cycle complet réussi — le curseur n'avance
qu'après succès), ``updated_at``.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connector_state",
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("connector_state")

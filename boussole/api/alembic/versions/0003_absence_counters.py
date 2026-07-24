"""Colonne ``connector_state.absence_counters`` — compteurs persistés (07 §4.6.2).

Revision ID: 0003
Revises: 0002

Les compteurs d'absence du mécanisme d'expiration 2 (disparition du flux)
étaient conservés en mémoire du processus worker : ils ne survivaient ni à
un redémarrage ni à la rotation des workers Celery, rendant le seuil de
2 réconciliations consécutives inopérant. Ils sont désormais persistés en
jsonb ``{job_source_id: n}`` sur la ligne ``connector_state`` de la source.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "connector_state",
        sa.Column(
            "absence_counters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("connector_state", "absence_counters")

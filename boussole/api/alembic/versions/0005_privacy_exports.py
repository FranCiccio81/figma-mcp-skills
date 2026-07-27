"""Table ``privacy_exports`` — demandes d'export RGPD (F-Q, jalon M5).

Revision ID: 0005
Revises: 0004

Écart documenté 🟡 : ``initial-schema.sql`` ne prévoit AUCUNE table pour les
demandes d'export RGPD (seuls ``deletion_requests``, ``consents`` et
``audit_log`` existent) — or `GET /privacy/exports/{id}` exige un état
persistant (statut, clé d'archive, expiration du lien signé 7 j). Table
applicative ajoutée ici ; à reporter dans le schéma de référence.

``status`` ∈ ('pending','ready') — « expired » est dérivé de ``expires_at``
à la lecture, jamais stocké. Les archives d'un compte supprimé sont purgées
avec lui (F-Q alt. 5) : FK ON DELETE CASCADE + purge applicative des objets.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "privacy_exports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("file_key", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'ready')", name="ck_privacy_exports_status"),
    )
    op.create_index("ix_privacy_exports_user_id", "privacy_exports", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_privacy_exports_user_id", table_name="privacy_exports")
    op.drop_table("privacy_exports")

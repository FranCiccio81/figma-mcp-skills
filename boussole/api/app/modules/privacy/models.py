"""Modèles SQLAlchemy du module privacy.

- ``privacy_exports`` : table applicative des demandes d'export RGPD —
  ABSENTE de ``initial-schema.sql`` 🟡 (écart documenté) ; créée par la
  migration ``0005_privacy_exports``.
- ``audit_log`` : table transversale créée par la migration 0001 ; aucun
  module ne l'avait mappée jusqu'ici — le module privacy en est
  l'orchestrateur naturel (journalisation + anonymisation à la purge, D21).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PrivacyExport(Base):
    """Demande d'export RGPD (F-Q). ``status`` ∈ pending|ready ; « expired »
    est dérivé de ``expires_at`` à la lecture (jamais stocké)."""

    __tablename__ = "privacy_exports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'pending'"))
    file_key: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    expires_at: Mapped[datetime | None]


class AuditLog(Base):
    """Ligne d'audit append-only (09 §5.7) — anonymisée à la purge (F-Q)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger(), Identity(always=True), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    subject_key: Mapped[str | None] = mapped_column(Text())  # hash irréversible post-purge
    action: Mapped[str] = mapped_column(Text(), nullable=False)
    entity: Mapped[str | None] = mapped_column(Text())
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'{}'::jsonb")
    )

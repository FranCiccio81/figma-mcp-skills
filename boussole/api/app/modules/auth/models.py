"""Modèles SQLAlchemy du module auth — colonnes conformes à initial-schema.sql.

Le schéma est créé par la migration 0001 (SQL brut) ; ces modèles servent au
runtime (requêtes) et ne pilotent pas de ``create_all``.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Enum PostgreSQL créé par la migration 0001 (create_type=False).
deletion_status_enum = ENUM("pending", "purged", name="deletion_status", create_type=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text())  # NULL si OAuth (post-MVP)
    locale: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'fr'"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    deleted_at: Mapped[datetime | None]


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text(), nullable=False)  # 'terms','privacy',…
    version: Mapped[str] = mapped_column(Text(), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    revoked_at: Mapped[datetime | None]


class DeletionRequest(Base):
    __tablename__ = "deletion_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    purge_after: Mapped[datetime] = mapped_column(nullable=False)  # requested_at + 30 jours
    status: Mapped[str] = mapped_column(
        deletion_status_enum, nullable=False, server_default=text("'pending'")
    )

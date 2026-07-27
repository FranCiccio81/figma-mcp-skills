"""Modèles SQLAlchemy du module applications — conformes à initial-schema.sql.

Le schéma est créé par la migration 0001 (SQL brut) ; ces modèles servent au
runtime. La contrainte CHECK « offre interne OU couple externe » (RM-P-2)
vit en base ET en applicatif (service) — le service la vérifie avant insert
pour produire un 422 problem+json exploitable plutôt qu'une IntegrityError.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Identity, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

# Enum PostgreSQL créé par la migration 0001 (create_type=False).
application_status_enum = ENUM(
    "draft", "to_apply", "applied", "interviewing", "offer", "rejected", "withdrawn",
    name="application_status", create_type=False,
)


class Application(Base):
    """Candidature — table ``applications`` (initial-schema.sql).

    CHECK SQL : ``job_posting_id`` non nul OU (``external_title`` ET
    ``external_company``) non nuls. ``applied_at`` est posé par le service à
    la PREMIÈRE transition vers ``applied`` (D10 : déclaratif), jamais après.
    """

    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_posting_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="SET NULL")
    )
    external_title: Mapped[str | None] = mapped_column(Text())
    external_company: Mapped[str | None] = mapped_column(Text())
    external_url: Mapped[str | None] = mapped_column(Text())
    status: Mapped[str] = mapped_column(
        application_status_enum, nullable=False, server_default=text("'draft'")
    )
    applied_at: Mapped[datetime | None]
    notes: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Historique immuable (RM-P-3) : append-only, ordre chronologique garanti
    # par l'identity ``id`` (deux événements peuvent partager le même ``at``).
    events: Mapped[list["ApplicationEvent"]] = relationship(
        order_by="ApplicationEvent.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ApplicationEvent(Base):
    """Transition historisée — table ``application_events`` (append-only)."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(BigInteger(), Identity(always=True), primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(application_status_enum)
    to_status: Mapped[str] = mapped_column(application_status_enum, nullable=False)
    note: Mapped[str | None] = mapped_column(Text())
    at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

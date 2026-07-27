"""Modèles SQLAlchemy du sous-package CV — conformes à initial-schema.sql.

``cv_documents`` (fichier + statut du parsing) et ``extraction_runs``
(journal des appels d'extraction : prompt_version, model, statut, sortie
stockée par clé objet — D08, 08 §7.1). Tables créées par la migration 0001
(SQL brut) : ces modèles servent au runtime, pas de ``create_all``.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Enum PostgreSQL créé par la migration 0001 (create_type=False).
cv_status_enum = ENUM(
    "uploaded", "parsing", "parsed", "failed", name="cv_status", create_type=False
)


class CvDocument(Base):
    __tablename__ = "cv_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_key: Mapped[str] = mapped_column(Text(), nullable=False)  # clé objet (storage)
    filename: Mapped[str] = mapped_column(Text(), nullable=False)
    mime_type: Mapped[str] = mapped_column(Text(), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer(), nullable=False)  # CHECK ≤ 10 Mo (SQL)
    status: Mapped[str] = mapped_column(
        cv_status_enum, nullable=False, server_default=text("'uploaded'")
    )
    raw_text_key: Mapped[str | None] = mapped_column(Text())  # texte extrait (RM-B-7)
    error_code: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    cv_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cv_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_version: Mapped[str] = mapped_column(Text(), nullable=False)
    model: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(Text(), nullable=False)  # success|schema_error|failed
    output_key: Mapped[str | None] = mapped_column(Text())  # JSON validé, clé objet
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

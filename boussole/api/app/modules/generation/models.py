"""Modèles SQLAlchemy du module generation — conformes à initial-schema.sql + 0004.

``generated_documents`` : contenus générés ancrés au profil validé (D10) —
``content`` jsonb, ``based_on_profile_version`` (preuve d'ancrage RM-L-1),
``prompt_version`` (D08), CHECK SQL ``status <> 'exported' OR validated_at
IS NOT NULL`` (RM-L-3, testé applicativement par le service).

L'enum SQL ``generated_doc_status`` n'a que ``draft | validated | exported`` :
les états contractuels ``pending`` et ``failed`` (openapi.yaml) sont dérivés
de la colonne applicative ``processing_status`` ajoutée par la migration
0004 🟡 (voir sa docstring) via :func:`api_status`.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Enums PostgreSQL créés par la migration 0001 (create_type=False).
generated_doc_type_enum = ENUM(
    "email", "cover_letter", "cv_variant", "cv_optimization",
    name="generated_doc_type", create_type=False,
)
generated_doc_status_enum = ENUM(
    "draft", "validated", "exported",
    name="generated_doc_status", create_type=False,
)

#: États de la colonne applicative ``processing_status`` (migration 0004).
PROCESSING_STATUSES = ("pending", "processing", "ready", "failed")


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL")
    )
    job_posting_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="SET NULL")
    )
    doc_type: Mapped[str] = mapped_column(generated_doc_type_enum, nullable=False)
    status: Mapped[str] = mapped_column(
        generated_doc_status_enum, nullable=False, server_default=text("'draft'")
    )
    # NOT NULL dans le schéma initial : un document pending/failed porte {}
    # (l'API le sert comme null — voir migration 0004 🟡).
    content: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False, default=dict)
    based_on_profile_version: Mapped[int] = mapped_column(nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    validated_at: Mapped[datetime | None]

    # ---- colonnes applicatives (migration 0004 🟡) ----
    processing_status: Mapped[str] = mapped_column(
        Text(), nullable=False, default="pending", server_default=text("'ready'")
    )
    error_code: Mapped[str | None] = mapped_column(Text())
    anchoring_check: Mapped[dict[str, Any] | None] = mapped_column(JSONB())
    manually_edited: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False, server_default=text("false")
    )
    options: Mapped[dict[str, Any]] = mapped_column(
        JSONB(), nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


def api_status(document: GeneratedDocument) -> str:
    """État contractuel (openapi.yaml) dérivé de l'enum SQL + processing_status.

    ``pending`` couvre ``pending`` et ``processing`` (le contrat ne distingue
    pas la file de l'exécution) ; ``failed`` masque l'enum SQL ; sinon l'état
    contractuel est l'enum SQL (``draft``/``validated``/``exported``).
    """
    if document.processing_status in ("pending", "processing"):
        return "pending"
    if document.processing_status == "failed":
        return "failed"
    return document.status

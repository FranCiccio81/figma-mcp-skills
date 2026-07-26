"""Modèles SQLAlchemy du module matching — conformes à initial-schema.sql.

``match_results`` : cache des résultats du moteur (upsert par
(profile, job, scoring_version), PK composite (profile_id, job_posting_id)).

🟡 Le schéma SQL ne porte pas de colonne ``profile_version`` : la version du
profil ayant servi au calcul (et les ``explanation_facts`` du moteur, dont le
module explanations a besoin — D14) est stockée dans le jsonb
``dimension_scores`` sous la clé ``_meta`` (objet ``{"_meta": …, "items":
[…]}`` — le type jsonb accepte un objet même si le défaut SQL est ``'[]'``).

``match_explanations`` : cache des reformulations LLM par
(profile, job, scoring_version, prompt_version) — FK composite vers
``match_results`` ON DELETE CASCADE (une invalidation du résultat purge
l'explication).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MatchResultRow(Base):
    """Ligne de ``match_results`` (initial-schema.sql) — cache du moteur."""

    __tablename__ = "match_results"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    scoring_version: Mapped[str] = mapped_column(Text(), nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger(), nullable=False)
    confidence: Mapped[int] = mapped_column(SmallInteger(), nullable=False)
    low_data: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    blocking_criteria: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'")
    )
    unknown_dimensions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'")
    )
    #: 🟡 Objet ``{"_meta": {"profile_version", "explanation_facts"}, "items": […]}``
    #: (voir docstring du module) — jamais une simple liste côté application.
    dimension_scores: Mapped[dict[str, Any]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'")
    )
    computed_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()")
    )


class MatchExplanationRow(Base):
    """Ligne de ``match_explanations`` (initial-schema.sql) — cache D14."""

    __tablename__ = "match_explanations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["profile_id", "job_posting_id"],
            ["match_results.profile_id", "match_results.job_posting_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("profile_id", "job_posting_id", "scoring_version", "prompt_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_posting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scoring_version: Mapped[str] = mapped_column(Text(), nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text(), nullable=False)
    #: Sortie validée du schéma ``match_explanation`` (ai-output-schemas.json).
    content: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()")
    )

"""Modèles SQLAlchemy des référentiels — colonnes conformes à initial-schema.sql."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

EMBEDDING_DIM = 1024


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    canonical_label: Mapped[str] = mapped_column(Text(), unique=True, nullable=False)
    esco_id: Mapped[str | None] = mapped_column(Text())
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class SkillAlias(Base):
    __tablename__ = "skill_aliases"

    alias: Mapped[str] = mapped_column(CITEXT(), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )


class Sector(Base):
    __tablename__ = "sectors"

    code: Mapped[str] = mapped_column(Text(), primary_key=True)
    label_fr: Mapped[str] = mapped_column(Text(), nullable=False)
    label_en: Mapped[str] = mapped_column(Text(), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(Text(), ForeignKey("sectors.code"))

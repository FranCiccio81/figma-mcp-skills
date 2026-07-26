"""Modèles SQLAlchemy du module profiles — colonnes conformes à initial-schema.sql.

Profil canonique unique par utilisateur, versionné, avec provenance par champ
(D05) : chaque sous-ressource porte ``source`` ∈ {cv_extraction, user_input,
user_confirmed} et ``confidence`` ∈ [0,1].

Le schéma est créé par la migration 0001 (SQL brut) ; ces modèles servent au
runtime et ne pilotent pas de ``create_all``. Les enums ``seniority_level`` et
``cefr_level`` sont réutilisés depuis ``jobs/models.py`` (mêmes types
PostgreSQL, create_type=False).
"""

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, ForeignKey, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.jobs.models import cefr_enum, seniority_enum
from app.modules.referentials.models import EMBEDDING_DIM

# Enums PostgreSQL créés par la migration 0001 (create_type=False).
field_source_enum = ENUM(
    "cv_extraction", "user_input", "user_confirmed",
    name="field_source", create_type=False,
)
profile_status_enum = ENUM("draft", "validated", name="profile_status", create_type=False)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        profile_status_enum, nullable=False, server_default=text("'draft'")
    )
    version: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    headline: Mapped[str | None] = mapped_column(Text())
    summary: Mapped[str | None] = mapped_column(Text())
    seniority: Mapped[str | None] = mapped_column(seniority_enum)
    total_experience_years: Mapped[float | None] = mapped_column(Numeric(4, 1))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    # FK réelle vers cv_documents dans la migration 0001 ; la table n'est pas
    # déclarée côté ORM (module ingestion, M4) → pas de ForeignKey ici pour
    # éviter une NoReferencedTableError à la configuration des mappers.
    source_cv_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    validated_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    experiences: Mapped[list["ProfileExperience"]] = relationship(
        cascade="all, delete-orphan", order_by="ProfileExperience.position"
    )
    educations: Mapped[list["ProfileEducation"]] = relationship(
        cascade="all, delete-orphan"
    )
    skills: Mapped[list["ProfileSkill"]] = relationship(cascade="all, delete-orphan")
    languages: Mapped[list["ProfileLanguage"]] = relationship(cascade="all, delete-orphan")


class ProfileExperience(Base):
    __tablename__ = "profile_experiences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    company: Mapped[str] = mapped_column(Text(), nullable=False)
    sector_code: Mapped[str | None] = mapped_column(Text(), ForeignKey("sectors.code"))
    start_date: Mapped[date] = mapped_column(Date(), nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date())  # NULL = en cours
    description: Mapped[str | None] = mapped_column(Text())
    position: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    source: Mapped[str] = mapped_column(field_source_enum, nullable=False)
    confidence: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("1")
    )


class ProfileEducation(Base):
    __tablename__ = "profile_educations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    degree: Mapped[str] = mapped_column(Text(), nullable=False)
    institution: Mapped[str] = mapped_column(Text(), nullable=False)
    start_year: Mapped[int | None]
    end_year: Mapped[int | None]
    source: Mapped[str] = mapped_column(field_source_enum, nullable=False)
    confidence: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("1")
    )


class ProfileSkill(Base):
    __tablename__ = "profile_skills"
    __table_args__ = (UniqueConstraint("profile_id", "skill_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    # Rapprochement taxonomie (ESCO 🟡, RM-C-6) : peuplé par le pipeline
    # d'extraction (M4) — null pour les compétences saisies manuellement au M3.
    skill_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"))
    label_raw: Mapped[str] = mapped_column(Text(), nullable=False)
    source: Mapped[str] = mapped_column(field_source_enum, nullable=False)
    confidence: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("1")
    )


class ProfileLanguage(Base):
    __tablename__ = "profile_languages"
    __table_args__ = (UniqueConstraint("profile_id", "lang_code"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    lang_code: Mapped[str] = mapped_column(Text(), nullable=False)  # ISO 639-1
    level: Mapped[str] = mapped_column(cefr_enum, nullable=False)
    source: Mapped[str] = mapped_column(field_source_enum, nullable=False)
    confidence: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("1")
    )

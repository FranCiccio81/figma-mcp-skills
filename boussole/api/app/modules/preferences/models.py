"""Modèles SQLAlchemy du module preferences — colonnes conformes à initial-schema.sql.

Une ligne ``preferences`` par utilisateur (PK = user_id) + cinq tables
enfants remplacées en bloc par ``PUT /preferences`` (payload unique, F-D).
L'enum ``contract_type`` est réutilisé depuis ``jobs/models.py`` (même type
PostgreSQL, create_type=False).
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.jobs.models import contract_enum
from app.modules.referentials.models import EMBEDDING_DIM

# Enum PostgreSQL créé par la migration 0001 (create_type=False).
remote_preference_enum = ENUM(
    "required", "preferred", "indifferent", "onsite_preferred",
    name="remote_preference", create_type=False,
)


class Preferences(Base):
    __tablename__ = "preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    remote_pref: Mapped[str] = mapped_column(
        remote_preference_enum, nullable=False, server_default=text("'indifferent'")
    )
    contract_types: Mapped[list[str]] = mapped_column(
        ARRAY(contract_enum), nullable=False, server_default=text("'{permanent}'")
    )
    contract_strict: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    salary_min: Mapped[int | None]  # souhaité, EUR brut annuel (RM-D-5)
    salary_min_strict: Mapped[int | None]  # rédhibitoire → bloquant (RM-D-3)
    salary_currency: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'EUR'")
    )
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class PreferenceLocation(Base):
    __tablename__ = "preference_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text(), nullable=False)
    lat: Mapped[float] = mapped_column(nullable=False)
    lon: Mapped[float] = mapped_column(nullable=False)
    radius_km: Mapped[int] = mapped_column(nullable=False, server_default=text("30"))


class PreferenceTitle(Base):
    __tablename__ = "preference_titles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    # Peuplé par le worker d'embeddings (M4) — null à l'écriture.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class PreferenceSector(Base):
    __tablename__ = "preference_sectors"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    sector_code: Mapped[str] = mapped_column(
        Text(), ForeignKey("sectors.code"), primary_key=True
    )
    mode: Mapped[str] = mapped_column(Text(), nullable=False)  # 'preferred' | 'excluded'


class PreferenceCompany(Base):
    __tablename__ = "preference_companies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(CITEXT(), primary_key=True)


class PreferenceKeyword(Base):
    __tablename__ = "preference_keywords"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    keyword: Mapped[str] = mapped_column(CITEXT(), primary_key=True)

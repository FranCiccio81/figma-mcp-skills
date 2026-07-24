"""Modèles SQLAlchemy des offres — colonnes conformes à initial-schema.sql.

``job_postings.tsv`` est maintenu par trigger PostgreSQL (migration 0001) :
jamais écrit côté application. ``sources`` appartient au module ingestion au
sens D01 mais vit ici pour éviter un import circulaire (jobs lit les sources
pour l'affichage de provenance) ; seule l'ingestion écrit dedans.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ENUM, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.referentials.models import EMBEDDING_DIM

# Enums PostgreSQL créés par la migration 0001 (create_type=False).
seniority_enum = ENUM(
    "intern", "junior", "mid", "senior", "lead", "principal", "executive",
    name="seniority_level", create_type=False,
)
contract_enum = ENUM(
    "permanent", "fixed_term", "freelance", "internship", "apprenticeship", "other",
    name="contract_type", create_type=False,
)
remote_enum = ENUM("onsite", "hybrid", "full_remote", name="remote_policy", create_type=False)
job_status_enum = ENUM("active", "expired", "withdrawn", name="job_status", create_type=False)
cefr_enum = ENUM("A1", "A2", "B1", "B2", "C1", "C2", name="cefr_level", create_type=False)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(Text(), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    kind: Mapped[str] = mapped_column(Text(), nullable=False)  # public_api | ats_feed | partner
    legal_basis: Mapped[str] = mapped_column(Text(), nullable=False)
    terms_url: Mapped[str | None] = mapped_column(Text())
    active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    dedup_hash: Mapped[str] = mapped_column(Text(), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    company_name: Mapped[str] = mapped_column(Text(), nullable=False)
    sector_code: Mapped[str | None] = mapped_column(Text(), ForeignKey("sectors.code"))
    description_text: Mapped[str] = mapped_column(Text(), nullable=False)
    language: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'fr'"))
    seniority: Mapped[str | None] = mapped_column(seniority_enum)
    seniority_conf: Mapped[float | None] = mapped_column(Numeric(3, 2))
    experience_min: Mapped[float | None] = mapped_column(Numeric(4, 1))
    experience_max: Mapped[float | None] = mapped_column(Numeric(4, 1))
    contract: Mapped[str | None] = mapped_column(contract_enum)
    contract_conf: Mapped[float | None] = mapped_column(Numeric(3, 2))
    remote: Mapped[str | None] = mapped_column(remote_enum)
    remote_conf: Mapped[float | None] = mapped_column(Numeric(3, 2))
    salary_min: Mapped[int | None]
    salary_max: Mapped[int | None]
    salary_currency: Mapped[str | None] = mapped_column(Text())
    salary_period: Mapped[str | None] = mapped_column(Text())  # year | month | day | hour
    status: Mapped[str] = mapped_column(
        job_status_enum, nullable=False, server_default=text("'active'")
    )
    country_code: Mapped[str | None] = mapped_column(Text())
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    expires_at: Mapped[datetime | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[str | None] = mapped_column(TSVECTOR)  # maintenu par trigger, lecture seule
    extraction_prompt_version: Mapped[str | None] = mapped_column(Text())

    job_sources: Mapped[list["JobSource"]] = relationship(back_populates="job_posting")
    locations: Mapped[list["JobLocation"]] = relationship()
    skills: Mapped[list["JobSkill"]] = relationship()
    languages: Mapped[list["JobLanguage"]] = relationship()


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )
    external_ref: Mapped[str] = mapped_column(Text(), nullable=False)
    original_url: Mapped[str] = mapped_column(Text(), nullable=False)  # garantie produit
    posted_at: Mapped[datetime | None]
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    raw_payload_key: Mapped[str | None] = mapped_column(Text())

    job_posting: Mapped[JobPosting] = relationship(back_populates="job_sources")
    source: Mapped[Source] = relationship()


class JobLocation(Base):
    __tablename__ = "job_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False
    )
    raw_label: Mapped[str] = mapped_column(Text(), nullable=False)
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    country_code: Mapped[str | None] = mapped_column(Text())


class JobSkill(Base):
    __tablename__ = "job_skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"))
    label_raw: Mapped[str] = mapped_column(Text(), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("true"))
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)


class JobLanguage(Base):
    __tablename__ = "job_languages"

    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    lang_code: Mapped[str] = mapped_column(Text(), primary_key=True)
    min_level: Mapped[str] = mapped_column(cefr_enum, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)

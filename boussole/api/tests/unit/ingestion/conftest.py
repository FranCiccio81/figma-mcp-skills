"""Fixtures des tests d'ingestion : store en mémoire (aucune base).

``InMemoryJobStore`` implémente le protocole ``JobStore`` du service —
le pipeline complet (idempotence, dédup, fusion, expiration) est testé
sans PostgreSQL. Les requêtes SQL réelles (étage 2 trigram) sont
validées en intégration M2 🟡.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from app.modules.jobs.models import (
    JobLanguage,
    JobLocation,
    JobPosting,
    JobSkill,
    JobSource,
    Source,
)


class InMemoryJobStore:
    """Implémentation en mémoire du protocole ``JobStore``."""

    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}
        self.postings: dict[uuid.UUID, JobPosting] = {}
        self.job_sources: dict[uuid.UUID, JobSource] = {}
        self.locations: list[JobLocation] = []
        self.skills: list[JobSkill] = []
        self.languages: list[JobLanguage] = []
        self.skill_aliases: dict[str, uuid.UUID] = {}
        self.skill_canonicals: dict[str, uuid.UUID] = {}
        #: Référentiel ``sectors`` — les dix sections NACE d'``app/seeds.py``.
        #: En base c'est une clé étrangère : un code absent d'ici doit être
        #: écarté à la normalisation, sinon il fait perdre l'offre entière.
        self.sectors: set[str] = {"C", "F", "G", "H", "J", "K", "M", "N", "P", "Q"}
        self._absences: dict[uuid.UUID, int] = {}

    # -- helpers de test --------------------------------------------------
    def add_source(self, slug: str, *, kind: str = "public_api") -> Source:
        source = Source(
            id=uuid.uuid4(), slug=slug, name=slug.title(), kind=kind,
            legal_basis="test", active=True, created_at=datetime.now(UTC),
        )
        self.sources[slug] = source
        return source

    # -- protocole JobStore ----------------------------------------------
    async def get_source_by_slug(self, slug: str) -> Source | None:
        return self.sources.get(slug)

    async def get_job_source(
        self, source_id: uuid.UUID, external_ref: str
    ) -> JobSource | None:
        for job_source in self.job_sources.values():
            if job_source.source_id == source_id and job_source.external_ref == external_ref:
                return job_source
        return None

    async def get_posting(self, posting_id: uuid.UUID) -> JobPosting | None:
        return self.postings.get(posting_id)

    async def get_posting_by_dedup_hash(self, dedup_hash: str) -> JobPosting | None:
        for posting in self.postings.values():
            if posting.dedup_hash == dedup_hash:
                return posting
        return None

    async def stage2_candidates(self, company_name: str, title: str) -> list[JobPosting]:
        return []  # étage 2 non décidable sans pg_trgm/embeddings (stub 🟡)

    async def skill_lookup(self) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID]]:
        return dict(self.skill_aliases), dict(self.skill_canonicals)

    async def sector_codes(self) -> frozenset[str]:
        return frozenset(self.sectors)

    async def locations_for(self, posting_id: uuid.UUID) -> list[JobLocation]:
        return [x for x in self.locations if x.job_posting_id == posting_id]

    async def skills_for(self, posting_id: uuid.UUID) -> list[JobSkill]:
        return [x for x in self.skills if x.job_posting_id == posting_id]

    async def languages_for(self, posting_id: uuid.UUID) -> list[JobLanguage]:
        return [x for x in self.languages if x.job_posting_id == posting_id]

    async def job_sources_for_source(self, source_id: uuid.UUID) -> list[JobSource]:
        return [x for x in self.job_sources.values() if x.source_id == source_id]

    async def job_sources_for_posting(self, posting_id: uuid.UUID) -> list[JobSource]:
        return [x for x in self.job_sources.values() if x.job_posting_id == posting_id]

    async def posting_id_of_job_source(self, job_source_id: uuid.UUID) -> uuid.UUID | None:
        job_source = self.job_sources.get(job_source_id)
        return job_source.job_posting_id if job_source else None

    async def postings_with_expired_deadline(self, now: datetime) -> list[JobPosting]:
        return [
            p for p in self.postings.values()
            if p.status == "active" and p.expires_at is not None and p.expires_at <= now
        ]

    async def note_source_absence(self, job_source_id: uuid.UUID) -> int:
        self._absences[job_source_id] = self._absences.get(job_source_id, 0) + 1
        return self._absences[job_source_id]

    async def clear_source_absence(self, job_source_id: uuid.UUID) -> None:
        self._absences.pop(job_source_id, None)

    async def absence_count(self, job_source_id: uuid.UUID) -> int:
        return self._absences.get(job_source_id, 0)

    async def add(self, obj: object) -> None:
        if isinstance(obj, JobPosting):
            self.postings[obj.id] = obj
        elif isinstance(obj, JobSource):
            self.job_sources[obj.id] = obj
        elif isinstance(obj, JobLocation):
            self.locations.append(obj)
        elif isinstance(obj, JobSkill):
            self.skills.append(obj)
        elif isinstance(obj, JobLanguage):
            self.languages.append(obj)
        else:  # pragma: no cover - garde-fou
            raise TypeError(f"objet inattendu : {type(obj)!r}")

    async def flush(self) -> None:
        return None

    @asynccontextmanager
    async def savepoint(self) -> AsyncIterator[None]:
        """Équivalent en mémoire du SAVEPOINT : snapshot des collections,
        restauré si l'item échoue (l'échec d'un item ne pollue pas le batch)."""
        snapshot = (
            dict(self.postings), dict(self.job_sources),
            list(self.locations), list(self.skills), list(self.languages),
        )
        try:
            yield
        except BaseException:
            (self.postings, self.job_sources,
             self.locations, self.skills, self.languages) = snapshot
            raise


@pytest.fixture
def store() -> InMemoryJobStore:
    return InMemoryJobStore()

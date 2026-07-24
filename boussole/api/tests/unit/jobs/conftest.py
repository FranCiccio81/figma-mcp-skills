"""Fixtures des tests du module jobs.

``InMemoryJobsRepository`` implémente le protocole ``JobsRepository`` sans
PostgreSQL : la sémantique des filtres (Q32 inclus), du keyset et des états
saved/hidden est reproduite en Python. Le full-text est approximé par une
recherche de sous-chaîne (rang = nombre d'occurrences) — suffisant pour
tester le service et le routeur ; le SQL réel est couvert par compilation
dans ``test_search_sql.py``.
"""

import math
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.modules.jobs.models import JobLocation, JobPosting, JobSkill, JobSource, Source
from app.modules.jobs.repository import (
    EARTH_RADIUS_KM,
    JobDetailRow,
    JobSearchRow,
    SearchCursor,
    SearchFilters,
    SourceRow,
    get_jobs_repository,
)


def make_posting(
    *,
    title: str = "Développeur backend Python",
    company_name: str = "Boussole SAS",
    description_text: str = "FastAPI, PostgreSQL, Redis.",
    language: str = "fr",
    remote: str | None = "hybrid",
    contract: str | None = "permanent",
    salary_min: int | None = 45000,
    salary_max: int | None = 55000,
    salary_currency: str | None = "EUR",
    salary_period: str | None = "year",
    status: str = "active",
    seniority: str | None = None,
    last_seen_at: datetime | None = None,
    expires_at: datetime | None = None,
    locations: list[tuple[str, float | None, float | None, str | None]] | None = None,
    source_name: str = "France Travail",
    original_url: str = "https://ft.example.eu/offre/1",
    posted_at: datetime | None = None,
    skills: list[tuple[str, bool]] | None = None,
) -> JobPosting:
    """Fabrique une offre détachée (relations peuplées, aucune session)."""
    now = datetime.now(UTC)
    posting = JobPosting(
        id=uuid.uuid4(),
        dedup_hash=uuid.uuid4().hex,
        title=title,
        company_name=company_name,
        description_text=description_text,
        language=language,
        remote=remote,
        contract=contract,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        salary_period=salary_period,
        status=status,
        seniority=seniority,
        first_seen_at=now - timedelta(days=10),
        last_seen_at=last_seen_at or now,
        expires_at=expires_at,
    )
    posting.locations = [
        JobLocation(
            id=uuid.uuid4(),
            job_posting_id=posting.id,
            raw_label=label,
            lat=lat,
            lon=lon,
            country_code=country,
        )
        for label, lat, lon, country in (locations or [("Lyon", 45.75, 4.85, "FR")])
    ]
    posting.job_sources = [
        JobSource(
            id=uuid.uuid4(),
            job_posting_id=posting.id,
            source_id=uuid.uuid4(),
            external_ref="ext-1",
            original_url=original_url,
            posted_at=posted_at,
            ingested_at=now,
            source=Source(
                id=uuid.uuid4(),
                slug="france-travail",
                name=source_name,
                kind="public_api",
                legal_basis="API publique",
                active=True,
                created_at=now,
            ),
        )
    ]
    posting.skills = [
        JobSkill(
            id=uuid.uuid4(),
            job_posting_id=posting.id,
            label_raw=label,
            required=required,
            confidence=0.9,
        )
        for label, required in (skills or [])
    ]
    return posting


class InMemoryJobsRepository:
    """Implémentation en mémoire du protocole JobsRepository."""

    def __init__(self) -> None:
        self.postings: dict[uuid.UUID, JobPosting] = {}
        self.saved: dict[tuple[uuid.UUID, uuid.UUID], str] = {}
        self.sources: list[SourceRow] = []

    def add(self, posting: JobPosting) -> JobPosting:
        self.postings[posting.id] = posting
        return posting

    # ------------------------------------------------------------ recherche

    async def search(
        self,
        *,
        user_id: uuid.UUID,
        filters: SearchFilters,
        limit: int,
        cursor: SearchCursor | None,
    ) -> list[JobSearchRow]:
        now = datetime.now(UTC)
        rows: list[JobSearchRow] = []
        for posting in self.postings.values():
            if posting.status != "active":
                continue
            if filters.remote and posting.remote not in filters.remote:
                continue
            if filters.contract and posting.contract not in filters.contract:
                continue
            if filters.salary_min is not None:
                best = posting.salary_max or posting.salary_min
                # Q32 : salaire inconnu (None) → l'offre reste incluse.
                if best is not None and best < filters.salary_min:
                    continue
            if filters.posted_since_days is not None and posting.last_seen_at < (
                now - timedelta(days=filters.posted_since_days)
            ):
                continue
            if filters.language is not None and posting.language != filters.language:
                continue
            if filters.country is not None and not any(
                loc.country_code == filters.country for loc in posting.locations
            ):
                continue
            if (
                filters.lat is not None
                and filters.lon is not None
                and not any(
                    loc.lat is not None
                    and loc.lon is not None
                    and _haversine(filters.lat, filters.lon, loc.lat, loc.lon)
                    <= filters.radius_km
                    for loc in posting.locations
                )
            ):
                continue
            state = self.saved.get((user_id, posting.id))
            if filters.saved_only and state != "saved":
                continue
            if not filters.include_hidden and state == "hidden":
                continue
            rank = 0.0
            if filters.q:
                haystack = " ".join(
                    [posting.title, posting.company_name, posting.description_text]
                ).lower()
                rank = float(haystack.count(filters.q.lower()))
                if rank == 0.0:
                    continue
            sort_value: datetime | float
            sort_value = rank if filters.sort == "relevance" else posting.last_seen_at
            rows.append(
                JobSearchRow(posting=posting, saved_state=state, sort_value=sort_value)
            )

        rows.sort(key=lambda r: (r.sort_value, r.posting.id.int), reverse=True)
        if cursor is not None:
            rows = [
                r
                for r in rows
                if (r.sort_value, r.posting.id.int) < (cursor.value, cursor.last_id.int)
            ]
        return rows[: limit + 1]

    # ------------------------------------------------------------ détail

    async def get_detail(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> JobDetailRow | None:
        posting = self.postings.get(job_id)
        if posting is None:
            return None
        return JobDetailRow(posting=posting, saved_state=self.saved.get((user_id, job_id)))

    async def job_exists(self, job_id: uuid.UUID) -> bool:
        return job_id in self.postings

    async def set_saved_state(
        self, user_id: uuid.UUID, job_id: uuid.UUID, state: str
    ) -> None:
        self.saved[(user_id, job_id)] = state

    async def clear_saved_state(self, user_id: uuid.UUID, job_id: uuid.UUID) -> None:
        self.saved.pop((user_id, job_id), None)

    async def list_sources(self) -> list[SourceRow]:
        return list(self.sources)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return EARTH_RADIUS_KM * math.acos(
        min(
            1.0,
            math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.cos(math.radians(lon2) - math.radians(lon1))
            + math.sin(math.radians(lat1)) * math.sin(math.radians(lat2)),
        )
    )


@pytest.fixture
def jobs_repository() -> InMemoryJobsRepository:
    return InMemoryJobsRepository()


@pytest.fixture
def client(client: TestClient, jobs_repository: InMemoryJobsRepository) -> TestClient:
    """Étend le client commun (tests/unit/conftest.py) avec le repo jobs."""
    client.app.dependency_overrides[get_jobs_repository] = lambda: jobs_repository
    return client

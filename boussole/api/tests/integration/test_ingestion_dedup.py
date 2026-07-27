"""Déduplication étage 1 sur une VRAIE base — contraintes et savepoints réels.

Le pipeline d'ingestion s'appuie sur des garanties que seul PostgreSQL rend :
``dedup_hash`` UNIQUE, ``(source_id, external_ref)`` UNIQUE, ``original_url``
NOT NULL, et un SAVEPOINT par item pour qu'un échec n'empoisonne pas le
batch. Le store en mémoire des tests unitaires ne peut simuler aucune de ces
quatre choses.

Garantie produit vérifiée ici (07 §6.3.1) : quand deux sources publient la
même offre, le lien d'origine des DEUX est conservé et servi par l'API.
"""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.connectors.base import RawJob, RawLocation
from app.modules.ingestion.geocode import StaticGeocoder
from app.modules.ingestion.service import SqlAlchemyJobStore, ingest_batch
from app.modules.jobs.models import JobPosting, JobSource
from tests.integration.factories import make_job_source, make_posting, make_source

pytestmark = pytest.mark.integration

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _raw(
    external_ref: str,
    *,
    company: str = "ACME SAS",
    title: str = "Data Engineer",
    description: str = "Nous recherchons un Data Engineer en CDI à Lyon. 45-55k€.",
    url: str = "https://example.test/offre",
    employer_ref: str | None = None,
    location: str = "Lyon",
) -> RawJob:
    return RawJob(
        external_ref=external_ref,
        title=title,
        company=company,
        description=description,
        url=url,
        payload={"id": external_ref},
        employer_ref=employer_ref,
        locations=[RawLocation(label=location)],
    )


class TestDedupEtage1:
    async def test_deux_sources_une_offre_deux_liens_d_origine(
        self, db_session: AsyncSession
    ) -> None:
        """Même clé de dédup → une offre canonique, deux ``job_sources``."""
        await make_source(db_session, slug="greenhouse", name="Greenhouse", commit=False)
        await make_source(db_session, slug="lever", name="Lever")
        store = SqlAlchemyJobStore(db_session)

        await ingest_batch(
            "greenhouse",
            [_raw("gh-1", employer_ref="REQ-7", url="https://boards.example/gh-1")],
            store,
            geocoder=StaticGeocoder(),
            now=NOW,
        )
        report = await ingest_batch(
            "lever",
            [
                _raw(
                    "lv-9",
                    company="Groupe ACME",  # suffixe/préfixe normalisés → même hash
                    employer_ref="REQ-7",
                    url="https://jobs.example/lv-9",
                )
            ],
            store,
            geocoder=StaticGeocoder(),
            now=NOW + timedelta(hours=1),
        )
        await db_session.commit()

        assert report.attached_stage1 == 1
        assert report.created == 0
        assert await db_session.scalar(select(func.count()).select_from(JobPosting)) == 1
        urls = (await db_session.execute(select(JobSource.original_url))).scalars().all()
        assert set(urls) == {"https://boards.example/gh-1", "https://jobs.example/lv-9"}

    async def test_api_expose_les_deux_liens_d_origine(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """``GET /jobs/{id}`` sert les deux sources — garantie produit 07 §6.3.1."""
        greenhouse = await make_source(db_session, slug="greenhouse", name="Greenhouse")
        lever = await make_source(db_session, slug="lever", name="Lever")
        posting = await make_posting(db_session, title="Data Engineer")
        await make_job_source(
            db_session,
            posting=posting,
            source=greenhouse,
            external_ref="gh-1",
            original_url="https://boards.example/gh-1",
        )
        await make_job_source(
            db_session,
            posting=posting,
            source=lever,
            external_ref="lv-9",
            original_url="https://jobs.example/lv-9",
        )

        response = await api_client.get(f"/api/v1/jobs/{posting.id}")

        assert response.status_code == 200, response.text
        sources = response.json()["sources"]
        assert {source["original_url"] for source in sources} == {
            "https://boards.example/gh-1",
            "https://jobs.example/lv-9",
        }
        assert {source["name"] for source in sources} == {"Greenhouse", "Lever"}

    async def test_rejouer_le_meme_flux_n_ajoute_rien(
        self, db_session: AsyncSession
    ) -> None:
        """Idempotence ``(source_id, external_ref)`` — la contrainte UNIQUE tient."""
        await make_source(db_session, slug="france-travail")
        store = SqlAlchemyJobStore(db_session)
        batch = [_raw("ft-1", url="https://ft.example.eu/ft-1")]

        await ingest_batch("france-travail", batch, store, now=NOW)
        await db_session.commit()
        report = await ingest_batch(
            "france-travail", batch, store, now=NOW + timedelta(hours=2)
        )
        await db_session.commit()

        assert (report.updated, report.created, report.errors) == (1, 0, 0)
        assert await db_session.scalar(select(func.count()).select_from(JobPosting)) == 1
        assert await db_session.scalar(select(func.count()).select_from(JobSource)) == 1

    async def test_savepoint_par_item_isole_l_echec(
        self, db_session: AsyncSession
    ) -> None:
        """Un item en erreur DB est annulé SEUL : le reste du batch est écrit.

        Deux items du même batch portent le même ``external_ref`` : le second
        viole ``(source_id, external_ref)`` au flush. Sans SAVEPOINT, la
        transaction entière serait invalidée et TOUT le batch perdu — un
        comportement qu'aucun store en mémoire ne reproduit.
        """
        await make_source(db_session, slug="france-travail")
        store = SqlAlchemyJobStore(db_session)

        report = await ingest_batch(
            "france-travail",
            [
                _raw("ft-1", title="Data Engineer", url="https://ft.example.eu/1"),
                _raw("ft-1", title="Data Engineer", url="https://ft.example.eu/1-bis"),
                _raw("ft-2", title="Développeur Python", url="https://ft.example.eu/2"),
            ],
            store,
            now=NOW,
        )
        await db_session.commit()

        assert report.seen == 3
        assert report.errors == 1, "le doublon d'external_ref doit être compté en erreur"
        assert report.created == 2
        assert await db_session.scalar(select(func.count()).select_from(JobPosting)) == 2


class TestContraintesDedup:
    async def test_dedup_hash_unique_en_base(self, db_session: AsyncSession) -> None:
        """La clé de dédup est une contrainte SQL, pas une convention applicative."""
        await make_posting(db_session, dedup_hash="hash-partage")

        with pytest.raises(IntegrityError):
            await make_posting(db_session, dedup_hash="hash-partage", title="Autre")
        await db_session.rollback()

    async def test_source_id_external_ref_unique_en_base(
        self, db_session: AsyncSession
    ) -> None:
        source = await make_source(db_session)
        premiere = await make_posting(db_session, title="Offre A")
        seconde = await make_posting(db_session, title="Offre B")
        await make_job_source(
            db_session, posting=premiere, source=source, external_ref="ext-42"
        )

        with pytest.raises(IntegrityError):
            await make_job_source(
                db_session, posting=seconde, source=source, external_ref="ext-42"
            )
        await db_session.rollback()

    async def test_original_url_non_nul(self, db_session: AsyncSession) -> None:
        """``job_sources.original_url`` NOT NULL — le lien d'origine est la promesse."""
        source = await make_source(db_session)
        posting = await make_posting(db_session)

        db_session.add(
            JobSource(
                id=uuid.uuid4(),
                job_posting_id=posting.id,
                source_id=source.id,
                external_ref="ext-1",
                original_url=None,  # type: ignore[arg-type]
                ingested_at=datetime.now(UTC),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

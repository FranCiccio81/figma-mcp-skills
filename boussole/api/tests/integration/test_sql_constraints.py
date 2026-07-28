"""Contraintes SQL réelles : CHECK, NOT NULL, UNIQUE, cascades ON DELETE.

Ces règles vivent dans la migration 0001 (et 0004/0005). Elles sont le
dernier rempart quand le service se trompe — et la suite unitaire ne les
exécute JAMAIS : elle vérifie au mieux les gardes applicatives qui les
doublent. Un CHECK oublié dans une future migration ne se voit qu'ici.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application, ApplicationEvent
from app.modules.generation.models import GeneratedDocument
from app.modules.jobs.models import JobLocation, JobPosting, JobSource, SavedJob
from app.modules.matching.models import MatchExplanationRow, MatchResultRow
from app.modules.profiles.cv.models import CvDocument
from app.modules.profiles.models import Profile, ProfileExperience
from tests.integration.factories import make_job_source, make_posting, make_source, make_user

pytestmark = pytest.mark.integration


async def _make_profile(session: AsyncSession, user_id: uuid.UUID) -> Profile:
    profile = Profile(id=uuid.uuid4(), user_id=user_id, status="validated", version=1)
    session.add(profile)
    await session.commit()
    return profile


class TestChecksGeneratedDocuments:
    """RM-L-3 : ``status = 'exported'`` exige ``validated_at`` non nul."""

    async def test_exported_sans_validated_at_refuse(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)

        db_session.add(
            GeneratedDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                doc_type="cover_letter",
                status="exported",
                content={},
                based_on_profile_version=1,
                prompt_version="generate_letter@1",
                validated_at=None,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_exported_avec_validated_at_accepte(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)

        db_session.add(
            GeneratedDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                doc_type="cover_letter",
                status="exported",
                content={"body": "…"},
                based_on_profile_version=1,
                prompt_version="generate_letter@1",
                validated_at=datetime.now(UTC),
            )
        )
        await db_session.commit()

        assert (
            await db_session.scalar(select(func.count()).select_from(GeneratedDocument))
        ) == 1

    async def test_processing_status_hors_vocabulaire_refuse(
        self, db_session: AsyncSession
    ) -> None:
        """CHECK de la migration 0004 sur la colonne applicative."""
        user = await make_user(db_session)

        db_session.add(
            GeneratedDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                doc_type="email",
                status="draft",
                content={},
                based_on_profile_version=1,
                prompt_version="generate_email@1",
                processing_status="en_cours",  # hors ('pending','processing','ready','failed')
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestChecksApplications:
    """RM-P-2 : offre interne OU couple (titre, entreprise) externe."""

    async def test_candidature_sans_offre_ni_couple_externe_refusee(
        self, db_session: AsyncSession
    ) -> None:
        user = await make_user(db_session)

        db_session.add(
            Application(id=uuid.uuid4(), user_id=user.id, status="draft", external_title="Seul")
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_candidature_externe_complete_acceptee(
        self, db_session: AsyncSession
    ) -> None:
        user = await make_user(db_session)

        db_session.add(
            Application(
                id=uuid.uuid4(),
                user_id=user.id,
                status="draft",
                external_title="Développeuse",
                external_company="ACME",
            )
        )
        await db_session.commit()

        assert (await db_session.scalar(select(func.count()).select_from(Application))) == 1


class TestChecksDivers:
    async def test_cv_de_plus_de_10_mo_refuse(self, db_session: AsyncSession) -> None:
        """CHECK ``size_bytes <= 10 Mo`` (migration 0001)."""
        user = await make_user(db_session)

        db_session.add(
            CvDocument(
                id=uuid.uuid4(),
                user_id=user.id,
                file_key=f"cv/{user.id}/gros.pdf",
                filename="gros.pdf",
                mime_type="application/pdf",
                size_bytes=11 * 1024 * 1024,
                status="uploaded",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_score_hors_bornes_refuse(self, db_session: AsyncSession) -> None:
        """CHECK ``score BETWEEN 0 AND 100`` sur ``match_results``."""
        user = await make_user(db_session)
        profile = await _make_profile(db_session, user.id)
        posting = await make_posting(db_session)

        db_session.add(
            MatchResultRow(
                profile_id=profile.id,
                job_posting_id=posting.id,
                scoring_version="1.0.0",
                score=140,
                confidence=90,
                dimension_scores={"items": []},
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_email_insensible_a_la_casse(self, db_session: AsyncSession) -> None:
        """``users.email`` est ``citext`` UNIQUE : deux casses = un doublon."""
        await make_user(db_session, email="Camille@Example.eu")

        with pytest.raises(IntegrityError):
            await make_user(db_session, email="camille@example.eu")
        await db_session.rollback()

    async def test_experience_avec_fin_avant_debut_refusee(
        self, db_session: AsyncSession
    ) -> None:
        """CHECK ``end_date IS NULL OR end_date >= start_date``."""
        user = await make_user(db_session)
        profile = await _make_profile(db_session, user.id)

        db_session.add(
            ProfileExperience(
                id=uuid.uuid4(),
                profile_id=profile.id,
                title="Ingénieure",
                company="ACME",
                start_date=datetime(2024, 1, 1, tzinfo=UTC).date(),
                end_date=datetime(2023, 1, 1, tzinfo=UTC).date(),
                source="user_input",
                confidence=1.0,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_valeur_hors_enum_refusee(self, db_session: AsyncSession) -> None:
        """Les enums PostgreSQL rejettent toute valeur inconnue (``job_status``)."""
        with pytest.raises(DBAPIError):
            await make_posting(db_session, status="archived")
        await db_session.rollback()


class TestCascades:
    async def test_suppression_offre_cascade_sur_ses_dependances(
        self, db_session: AsyncSession
    ) -> None:
        """``job_sources``/``job_locations`` disparaissent avec l'offre."""
        source = await make_source(db_session)
        posting = await make_posting(db_session)
        await make_job_source(db_session, posting=posting, source=source)

        await db_session.execute(
            text("DELETE FROM job_postings WHERE id = :id"), {"id": posting.id}
        )
        await db_session.commit()

        assert (await db_session.scalar(select(func.count()).select_from(JobSource))) == 0
        assert (await db_session.scalar(select(func.count()).select_from(JobLocation))) == 0

    async def test_suppression_utilisateur_cascade_sur_ses_donnees(
        self, db_session: AsyncSession
    ) -> None:
        """FK ``ON DELETE CASCADE`` : filet de sécurité sous la purge applicative."""
        user = await make_user(db_session)
        posting = await make_posting(db_session)
        db_session.add(SavedJob(user_id=user.id, job_posting_id=posting.id, state="saved"))
        db_session.add(
            Application(
                id=uuid.uuid4(),
                user_id=user.id,
                job_posting_id=posting.id,
                status="draft",
            )
        )
        await _make_profile(db_session, user.id)
        await db_session.commit()

        await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
        await db_session.commit()

        assert (await db_session.scalar(select(func.count()).select_from(SavedJob))) == 0
        assert (await db_session.scalar(select(func.count()).select_from(Application))) == 0
        assert (await db_session.scalar(select(func.count()).select_from(Profile))) == 0
        assert (await db_session.scalar(select(func.count()).select_from(JobPosting))) == 1

    async def test_suppression_candidature_cascade_sur_l_historique(
        self, db_session: AsyncSession
    ) -> None:
        user = await make_user(db_session)
        application = Application(
            id=uuid.uuid4(),
            user_id=user.id,
            external_title="Développeuse",
            external_company="ACME",
            status="draft",
        )
        db_session.add(application)
        await db_session.flush()
        db_session.add(
            ApplicationEvent(application_id=application.id, to_status="applied")
        )
        await db_session.commit()

        await db_session.execute(
            text("DELETE FROM applications WHERE id = :id"), {"id": application.id}
        )
        await db_session.commit()

        assert (
            await db_session.scalar(select(func.count()).select_from(ApplicationEvent))
        ) == 0

    async def test_suppression_resultat_cascade_sur_l_explication(
        self, db_session: AsyncSession
    ) -> None:
        """FK COMPOSITE ``match_explanations`` → ``match_results`` ON DELETE CASCADE."""
        user = await make_user(db_session)
        profile = await _make_profile(db_session, user.id)
        posting = await make_posting(db_session)
        db_session.add(
            MatchResultRow(
                profile_id=profile.id,
                job_posting_id=posting.id,
                scoring_version="1.0.0",
                score=80,
                confidence=90,
                dimension_scores={"items": []},
            )
        )
        await db_session.flush()
        db_session.add(
            MatchExplanationRow(
                id=uuid.uuid4(),
                profile_id=profile.id,
                job_posting_id=posting.id,
                scoring_version="1.0.0",
                prompt_version="explain_match@1",
                content={"summary": "…"},
            )
        )
        await db_session.commit()

        await db_session.execute(text("DELETE FROM match_results"))
        await db_session.commit()

        assert (
            await db_session.scalar(select(func.count()).select_from(MatchExplanationRow))
        ) == 0

    async def test_suppression_offre_delie_les_documents_generes(
        self, db_session: AsyncSession
    ) -> None:
        """``ON DELETE SET NULL`` : le document généré survit à l'offre."""
        user = await make_user(db_session)
        posting = await make_posting(db_session)
        document = GeneratedDocument(
            id=uuid.uuid4(),
            user_id=user.id,
            job_posting_id=posting.id,
            doc_type="cover_letter",
            status="draft",
            content={"body": "…"},
            based_on_profile_version=1,
            prompt_version="generate_letter@1",
        )
        db_session.add(document)
        await db_session.commit()

        await db_session.execute(
            text("DELETE FROM job_postings WHERE id = :id"), {"id": posting.id}
        )
        await db_session.commit()

        relu = await db_session.get(GeneratedDocument, document.id, populate_existing=True)
        assert relu is not None, "le document généré ne doit pas disparaître avec l'offre"
        assert relu.job_posting_id is None

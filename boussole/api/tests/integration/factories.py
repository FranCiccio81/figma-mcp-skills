"""Fabriques de données pour la suite d'intégration — INSERT réels.

Aucune fabrique ne bypasse le schéma : les lignes passent par les modèles
SQLAlchemy de l'application, donc par les CHECK, les FK et les triggers
PostgreSQL créés par les migrations.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import ObjectStorage
from app.modules.applications.models import Application, ApplicationEvent
from app.modules.auth.models import Consent, DeletionRequest, User
from app.modules.generation.models import GeneratedDocument
from app.modules.jobs.models import JobLocation, JobPosting, JobSource, SavedJob, Source
from app.modules.matching.models import MatchExplanationRow, MatchResultRow
from app.modules.preferences.models import (
    PreferenceCompany,
    PreferenceKeyword,
    PreferenceLocation,
    Preferences,
    PreferenceSector,
    PreferenceTitle,
)
from app.modules.privacy.models import AuditLog, PrivacyExport
from app.modules.profiles.cv.models import CvDocument, ExtractionRun
from app.modules.profiles.models import (
    Profile,
    ProfileEducation,
    ProfileExperience,
    ProfileLanguage,
    ProfileSkill,
)
from app.modules.referentials.models import Sector, Skill


async def make_user(
    session: AsyncSession, *, email: str = "camille@example.eu", commit: bool = True
) -> User:
    """Utilisateur RÉEL (``users``) — ``password_hash`` factice (non vérifié ici)."""
    user = User(id=uuid.uuid4(), email=email, password_hash="argon2$factice", locale="fr")
    session.add(user)
    if commit:
        await session.commit()
    return user


async def make_source(
    session: AsyncSession,
    *,
    slug: str = "france-travail",
    name: str = "France Travail",
    commit: bool = True,
) -> Source:
    source = Source(
        id=uuid.uuid4(),
        slug=slug,
        name=name,
        kind="public_api",
        legal_basis="API publique — fiche de conformité",
        active=True,
    )
    session.add(source)
    if commit:
        await session.commit()
    return source


async def make_posting(
    session: AsyncSession,
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
    last_seen_at: datetime | None = None,
    expires_at: datetime | None = None,
    country_code: str | None = "FR",
    location: tuple[str, float | None, float | None, str | None] = ("Lyon", 45.75, 4.85, "FR"),
    dedup_hash: str | None = None,
    commit: bool = True,
) -> JobPosting:
    """Offre RÉELLE : le trigger ``trg_job_postings_tsv`` peuple ``tsv`` à l'INSERT."""
    now = datetime.now(UTC)
    posting = JobPosting(
        id=uuid.uuid4(),
        dedup_hash=dedup_hash or uuid.uuid4().hex,
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
        country_code=country_code,
        first_seen_at=now - timedelta(days=30),
        last_seen_at=last_seen_at or now,
        expires_at=expires_at,
    )
    session.add(posting)
    label, lat, lon, country = location
    session.add(
        JobLocation(
            id=uuid.uuid4(),
            job_posting_id=posting.id,
            raw_label=label,
            lat=lat,
            lon=lon,
            country_code=country,
        )
    )
    if commit:
        await session.commit()
    return posting


async def make_job_source(
    session: AsyncSession,
    *,
    posting: JobPosting,
    source: Source,
    external_ref: str = "ext-1",
    original_url: str = "https://ft.example.eu/offre/1",
    posted_at: datetime | None = None,
    commit: bool = True,
) -> JobSource:
    job_source = JobSource(
        id=uuid.uuid4(),
        job_posting_id=posting.id,
        source_id=source.id,
        external_ref=external_ref,
        original_url=original_url,
        posted_at=posted_at,
        ingested_at=datetime.now(UTC),
    )
    session.add(job_source)
    if commit:
        await session.commit()
    return job_source


#: Tables personnelles peuplées par :func:`populate_all_modules`, par module du
#: registre — sert d'assertion de couverture dans le test de purge.
POPULATED_TABLES: dict[str, tuple[str, ...]] = {
    "auth": ("users", "consents"),
    "profiles": (
        "profiles",
        "profile_experiences",
        "profile_educations",
        "profile_skills",
        "profile_languages",
        "cv_documents",
        "extraction_runs",
    ),
    "preferences": (
        "preferences",
        "preference_locations",
        "preference_titles",
        "preference_sectors",
        "preference_companies",
        "preference_keywords",
    ),
    "jobs": ("saved_jobs",),
    "matching": ("match_results",),
    "explanations": ("match_explanations",),
    "generation": ("generated_documents",),
    "applications": ("applications", "application_events"),
    "privacy": ("privacy_exports", "audit_log", "deletion_requests"),
}


async def populate_all_modules(
    session: AsyncSession,
    user: User,
    *,
    storage: ObjectStorage,
    posting: JobPosting,
) -> dict[str, uuid.UUID]:
    """Peuple une ligne personnelle dans CHAQUE module du registre (D21).

    C'est le point de départ du test de purge RGPD de bout en bout : si un
    module oublie de supprimer ses données, l'inventaire post-purge le voit.
    Retourne les identifiants utiles aux assertions.
    """
    user_id = user.id

    # --- référentiels partagés (non personnels, requis par les FK) ---
    session.add(Sector(code="J", label_fr="Information et communication", label_en="ICT"))
    skill = Skill(id=uuid.uuid4(), canonical_label="Python")
    session.add(skill)
    await session.flush()

    # --- auth ---
    session.add(Consent(id=uuid.uuid4(), user_id=user_id, kind="terms", version="2026-07"))
    session.add(Consent(id=uuid.uuid4(), user_id=user_id, kind="privacy", version="2026-07"))

    # --- profiles (CV + profil + sous-ressources) ---
    cv = CvDocument(
        id=uuid.uuid4(),
        user_id=user_id,
        file_key=f"cv/{user_id}/original.pdf",
        filename="cv-camille.pdf",
        mime_type="application/pdf",
        size_bytes=120_000,
        status="parsed",
        raw_text_key=f"cv/{user_id}/texte.txt",
    )
    session.add(cv)
    await session.flush()
    run = ExtractionRun(
        id=uuid.uuid4(),
        cv_document_id=cv.id,
        prompt_version="extract_cv@1",
        model="fake-model",
        status="success",
        output_key=f"cv/{user_id}/extraction.json",
    )
    session.add(run)
    storage.put(cv.file_key, b"%PDF-factice")
    storage.put(cv.raw_text_key or "", b"texte extrait")
    storage.put(run.output_key or "", b"{}")

    profile = Profile(
        id=uuid.uuid4(),
        user_id=user_id,
        status="validated",
        version=3,
        headline="Développeuse backend",
        summary="8 ans d'expérience Python.",
        seniority="senior",
        total_experience_years=8.0,
        source_cv_id=cv.id,
        validated_at=datetime.now(UTC),
    )
    session.add(profile)
    await session.flush()
    session.add(
        ProfileExperience(
            id=uuid.uuid4(),
            profile_id=profile.id,
            title="Ingénieure backend",
            company="ACME",
            sector_code="J",
            start_date=datetime(2020, 1, 1, tzinfo=UTC).date(),
            end_date=None,
            description="APIs Python.",
            position=0,
            source="cv_extraction",
            confidence=0.9,
        )
    )
    session.add(
        ProfileEducation(
            id=uuid.uuid4(),
            profile_id=profile.id,
            degree="Master informatique",
            institution="Université de Lyon",
            start_year=2014,
            end_year=2016,
            source="cv_extraction",
            confidence=0.9,
        )
    )
    session.add(
        ProfileSkill(
            id=uuid.uuid4(),
            profile_id=profile.id,
            skill_id=skill.id,
            label_raw="Python",
            source="user_confirmed",
            confidence=1.0,
        )
    )
    session.add(
        ProfileLanguage(
            id=uuid.uuid4(),
            profile_id=profile.id,
            lang_code="fr",
            level="C2",
            source="user_input",
            confidence=1.0,
        )
    )

    # --- preferences (ligne + 5 tables enfants) ---
    session.add(
        Preferences(
            user_id=user_id,
            remote_pref="preferred",
            contract_types=["permanent"],
            contract_strict=False,
            salary_min=45000,
            salary_min_strict=40000,
        )
    )
    session.add(
        PreferenceLocation(
            id=uuid.uuid4(), user_id=user_id, label="Lyon", lat=45.75, lon=4.85, radius_km=40
        )
    )
    session.add(
        PreferenceTitle(id=uuid.uuid4(), user_id=user_id, title="Développeuse backend")
    )
    session.add(PreferenceSector(user_id=user_id, sector_code="J", mode="preferred"))
    session.add(PreferenceCompany(user_id=user_id, name="ACME"))
    session.add(PreferenceKeyword(user_id=user_id, keyword="python"))

    # --- jobs (état saved/hidden posé par l'utilisateur) ---
    session.add(SavedJob(user_id=user_id, job_posting_id=posting.id, state="saved"))

    # --- matching + explanations ---
    session.add(
        MatchResultRow(
            profile_id=profile.id,
            job_posting_id=posting.id,
            scoring_version="1.0.0",
            score=82,
            confidence=90,
            low_data=False,
            blocking_criteria=[],
            unknown_dimensions=[],
            dimension_scores={"_meta": {"profile_version": 3}, "items": []},
        )
    )
    await session.flush()
    session.add(
        MatchExplanationRow(
            id=uuid.uuid4(),
            profile_id=profile.id,
            job_posting_id=posting.id,
            scoring_version="1.0.0",
            prompt_version="explain_match@1",
            content={"summary": "Bon accord de compétences."},
        )
    )

    # --- applications + historique ---
    application = Application(
        id=uuid.uuid4(),
        user_id=user_id,
        job_posting_id=posting.id,
        status="applied",
        applied_at=datetime.now(UTC),
        notes="Entretien prévu.",
    )
    session.add(application)
    await session.flush()
    session.add(
        ApplicationEvent(
            application_id=application.id, from_status="draft", to_status="applied"
        )
    )

    # --- generation ---
    document = GeneratedDocument(
        id=uuid.uuid4(),
        user_id=user_id,
        application_id=application.id,
        job_posting_id=posting.id,
        doc_type="cover_letter",
        status="draft",
        content={"body": "Madame, Monsieur…"},
        based_on_profile_version=3,
        prompt_version="generate_letter@1",
        processing_status="ready",
    )
    session.add(document)

    # --- privacy (archive d'export + audit) ---
    export = PrivacyExport(
        id=uuid.uuid4(),
        user_id=user_id,
        status="ready",
        file_key=f"privacy-exports/{user_id}/archive.json",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    session.add(export)
    storage.put(export.file_key or "", b'{"modules": {}}')
    session.add(
        AuditLog(user_id=user_id, action="account_deletion_requested", entity="deletion_request")
    )

    await session.commit()
    return {
        "profile_id": profile.id,
        "cv_id": cv.id,
        "application_id": application.id,
        "document_id": document.id,
        "export_id": export.id,
        "skill_id": skill.id,
    }


async def make_due_deletion_request(
    session: AsyncSession, user_id: uuid.UUID, *, days_overdue: int = 1
) -> DeletionRequest:
    """Demande de suppression ÉCHUE (``purge_after`` dépassé) — cible de la purge."""
    now = datetime.now(UTC)
    request = DeletionRequest(
        id=uuid.uuid4(),
        user_id=user_id,
        requested_at=now - timedelta(days=30 + days_overdue),
        purge_after=now - timedelta(days=days_overdue),
        status="pending",
    )
    session.add(request)
    await session.commit()
    return request

"""Logique métier du module profiles (F-C, D05).

Règles portées ici :
- ``GET /profile`` crée le profil draft vide à la volée s'il n'existe pas 🟡 ;
- toute mutation passe les champs touchés à ``source='user_input'``,
  ``confidence=1`` et incrémente ``version`` (RM-C-4) ;
- ``total_experience_years`` est recalculé à chaque mutation d'expérience :
  somme des durées avec fusion d'intervalles (chevauchants, adjacents à un
  jour près 🟡, inclus) — une expérience en cours court jusqu'à aujourd'hui ;
- ``POST /profile/validate`` : préconditions RM-C-3 (≥ 3 compétences ET ≥ 1
  expérience OU formation) sinon 409 ``profile_incomplete`` ; la validation
  promeut en bloc ``cv_extraction`` → ``user_confirmed`` (RM-C-2) ;
- l'édition d'un profil validé le laisse validé (Q23 🟡, F-C alternatif 2) ;
- le re-scoring asynchrone (RM-C-4) se branchera au M4 — non déclenché ici.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from typing import TypeVar, cast

from app.core.problems import Problem
from app.modules.jobs.schemas import SeniorityLevel
from app.modules.profiles.models import (
    Profile,
    ProfileEducation,
    ProfileExperience,
    ProfileLanguage,
    ProfileSkill,
)
from app.modules.profiles.repository import ProfilesRepository
from app.modules.profiles.schemas import (
    CefrLevel,
    EducationInput,
    EducationOut,
    ExperienceInput,
    ExperienceOut,
    FieldSource,
    LanguageInput,
    LanguageOut,
    ProfileOut,
    ProfileRootPatch,
    ProfileStatus,
    Provenance,
    SkillInput,
    SkillOut,
)

#: Seuils de validabilité (RM-C-3).
MIN_SKILLS_TO_VALIDATE = 3

#: Année moyenne (grégorienne) pour convertir des jours en années.
DAYS_PER_YEAR = 365.25

_HasId = TypeVar("_HasId", ProfileExperience, ProfileEducation, ProfileSkill, ProfileLanguage)


def compute_total_experience_years(
    periods: Iterable[tuple[date, date | None]], *, today: date | None = None
) -> float | None:
    """Total d'années d'expérience : intervalles fusionnés puis sommés.

    - ``end_date`` absente = expérience en cours → bornée à ``today`` ;
    - les intervalles chevauchants, inclus ou adjacents (fin + 1 jour =
      début suivant 🟡) sont fusionnés — les périodes de cumul d'emplois ne
      comptent qu'une fois ;
    - retourne ``None`` sans aucune expérience (dimension inconnue, pas 0).
    """
    reference = today or datetime.now(UTC).date()
    intervals = sorted(
        (start, end if end is not None else reference)
        for start, end in periods
        if (end if end is not None else reference) >= start
    )
    if not intervals:
        return None

    merged: list[tuple[date, date]] = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + timedelta(days=1):  # chevauchant, inclus ou adjacent
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_days = sum((end - start).days + 1 for start, end in merged)  # bornes incluses
    return round(total_days / DAYS_PER_YEAR, 1)


# ---------------------------------------------------------------- mapping


def _provenance(source: str, confidence: float) -> Provenance:
    # Cast sûr : colonne ENUM PostgreSQL field_source.
    return Provenance(source=cast(FieldSource, source), confidence=float(confidence))


def _experience_out(exp: ProfileExperience) -> ExperienceOut:
    return ExperienceOut(
        id=exp.id,
        title=exp.title,
        company=exp.company,
        sector_code=exp.sector_code,
        start_date=exp.start_date,
        end_date=exp.end_date,
        description=exp.description,
        provenance=_provenance(exp.source, exp.confidence),
    )


def _education_out(edu: ProfileEducation) -> EducationOut:
    return EducationOut(
        id=edu.id,
        degree=edu.degree,
        institution=edu.institution,
        start_year=edu.start_year,
        end_year=edu.end_year,
        provenance=_provenance(edu.source, edu.confidence),
    )


def _skill_out(skill: ProfileSkill) -> SkillOut:
    return SkillOut(
        id=skill.id,
        label=skill.label_raw,
        provenance=_provenance(skill.source, skill.confidence),
    )


def _language_out(lang: ProfileLanguage) -> LanguageOut:
    return LanguageOut(
        id=lang.id,
        lang_code=lang.lang_code,
        level=cast(CefrLevel, lang.level),
        provenance=_provenance(lang.source, lang.confidence),
    )


def to_profile_out(profile: Profile) -> ProfileOut:
    """Sérialise l'agrégat — réutilisé par le service et par purge.export_user."""
    return ProfileOut(
        id=profile.id,
        status=cast(ProfileStatus, profile.status),
        version=profile.version,
        headline=profile.headline,
        summary=profile.summary,
        seniority=cast(SeniorityLevel | None, profile.seniority),
        total_experience_years=(
            None
            if profile.total_experience_years is None
            else float(profile.total_experience_years)
        ),
        experiences=[_experience_out(e) for e in profile.experiences],
        educations=[_education_out(e) for e in profile.educations],
        skills=[_skill_out(s) for s in profile.skills],
        languages=[_language_out(lg) for lg in profile.languages],
    )


def _not_found(entity: str) -> Problem:
    return Problem(
        status=404,
        code="not_found",
        title="Ressource introuvable",
        detail=f"{entity} introuvable dans votre profil.",
    )


#: Signature d'enfilement de ``ai.embeddings.embed_profile`` (injectable).
#: **Coroutine** : l'enfilement est une E/S réseau (broker), elle ne peut pas
#: être appelée en synchrone depuis une route ``async`` — voir
#: :func:`_default_embed_enqueuer`.
EmbedProfileEnqueuer = Callable[[uuid.UUID], Awaitable[None]]

_logger = logging.getLogger(__name__)


def _send_embed_profile_task(profile_id: uuid.UUID) -> None:
    """Publication Celery BLOQUANTE — à n'appeler que hors boucle d'événements.

    Import tardif : le service ne doit pas dépendre de Celery à l'import
    (tests unitaires, outillage). Toute erreur est journalisée sans jamais
    faire échouer la validation — le beat quotidien rattrape les profils
    dont le vecteur manque.
    """
    try:
        from app.workers.celery_app import celery_app

        # Broker injoignable : échouer TOUT DE SUITE (best-effort — le beat
        # quotidien rattrape) plutôt que d'occuper un thread 19 s. Mesuré, sur
        # un broker refusant la connexion :
        # - tel quel .................................... 19,11 s
        # - ``ignore_result=True`` .......................  6,06 s : l'essentiel
        #   du délai n'est PAS le broker mais le RESULT BACKEND
        #   (``backend.on_task_call`` abonne un consommateur de résultat et
        #   retente jusqu'à « Retry limit exceeded »). Or personne ne lit le
        #   résultat de cette tâche : l'abonnement est du pur gaspillage ;
        # - + connexion à ``max_retries=0`` ..............  0,002 s : coupe la
        #   boucle de reconnexion de ``Connection.default_channel``.
        # ``retry=False`` ne couvre QUE la republication, pas ces deux
        # boucles — d'où les trois options ensemble.
        with celery_app.connection_for_write(
            transport_options={"max_retries": 0}
        ) as connection:
            celery_app.send_task(
                "ai.embeddings.embed_profile",
                args=[str(profile_id)],
                queue="ai",
                connection=connection,
                retry=False,
                ignore_result=True,
            )
    except Exception:  # pragma: no cover - dépend de l'infra broker
        _logger.warning("embed_profile_enqueue_failed", extra={"detail": str(profile_id)})


async def _default_embed_enqueuer(profile_id: uuid.UUID) -> None:
    """Enfile le recalcul d'embedding du profil — best-effort, NON bloquant.

    ``celery_app.send_task`` ouvre une connexion AMQP/Redis synchrone : appelé
    directement depuis ``async def validate_profile``, un broker injoignable
    gèle la boucle d'événements du worker ASGI (donc TOUTES les requêtes en
    cours) le temps du timeout TCP — mesuré à 19,18 s. Le travail est donc
    déporté sur le pool de threads (patron déjà utilisé par
    ``jobs/repository.py`` et ``workers/ingestion_tasks.py``).
    """
    await asyncio.to_thread(_send_embed_profile_task, profile_id)


class ProfilesService:
    def __init__(
        self,
        repository: ProfilesRepository,
        embed_enqueuer: EmbedProfileEnqueuer | None = None,
    ) -> None:
        self._repository = repository
        # Recalcul de l'embedding du profil à la validation (06 §2.3) : sans
        # lui, ``title_similarity`` reste inconnue jusqu'au rattrapage
        # nocturne. Injectable pour les tests (aucun Celery requis).
        self._embed_enqueuer = embed_enqueuer or _default_embed_enqueuer

    # ------------------------------------------------------------ racine

    async def get_profile(self, user_id: uuid.UUID) -> ProfileOut:
        """Profil complet — crée le draft vide à la volée s'il n'existe pas 🟡."""
        return to_profile_out(await self._get_or_create(user_id))

    async def patch_root(self, user_id: uuid.UUID, patch: ProfileRootPatch) -> ProfileOut:
        """PATCH /profile : seuls les champs présents dans le corps changent.

        headline/summary sont nullables : un ``null`` explicite efface, un
        champ absent est ignoré (distinction via ``model_fields_set``).
        Les champs racine ne portent pas de provenance en base (D05 ne
        s'applique qu'aux sous-ressources) — la saisie est par définition
        ``user_input``.
        """
        profile = await self._get_or_create(user_id)
        provided = patch.model_fields_set
        if provided:
            if "headline" in provided:
                profile.headline = patch.headline
            if "summary" in provided:
                profile.summary = patch.summary
            if "seniority" in provided:
                profile.seniority = patch.seniority
            self._bump_version(profile)
            await self._repository.commit()
        return to_profile_out(profile)

    # ------------------------------------------------------------ validation

    async def validate_profile(self, user_id: uuid.UUID) -> ProfileOut:
        """POST /profile/validate — promotion de provenance (F-C, RM-C-2/3)."""
        profile = await self._get_or_create(user_id)
        errors: list[dict[str, str]] = []
        if len(profile.skills) < MIN_SKILLS_TO_VALIDATE:
            errors.append(
                {
                    "field": "skills",
                    "code": "too_few_skills",
                    "message": (
                        f"Minimum {MIN_SKILLS_TO_VALIDATE} compétences requises "
                        f"(actuellement {len(profile.skills)})."
                    ),
                }
            )
        if not profile.experiences and not profile.educations:
            errors.append(
                {
                    "field": "experiences",
                    "code": "missing_experience_or_education",
                    "message": "Au moins une expérience ou une formation est requise.",
                }
            )
        if errors:
            raise Problem(
                status=409,
                code="profile_incomplete",
                title="Profil incomplet",
                detail="Le profil ne remplit pas les préconditions de validation.",
                errors=errors,
            )

        children: list[ProfileExperience | ProfileEducation | ProfileSkill | ProfileLanguage] = [
            *profile.experiences,
            *profile.educations,
            *profile.skills,
            *profile.languages,
        ]
        for child in children:
            if child.source == "cv_extraction":
                child.source = "user_confirmed"
        profile.status = "validated"
        profile.validated_at = datetime.now(UTC)
        self._bump_version(profile)
        await self._repository.commit()
        # Après commit : un échec d'enfilement ne doit jamais annuler une
        # validation réussie (le beat quotidien rattrape).
        await self._embed_enqueuer(profile.id)
        return to_profile_out(profile)

    # ------------------------------------------------------------ expériences

    async def add_experience(
        self, user_id: uuid.UUID, payload: ExperienceInput
    ) -> ExperienceOut:
        profile = await self._get_or_create(user_id)
        exp = ProfileExperience(
            id=uuid.uuid4(),
            profile_id=profile.id,
            title=payload.title,
            company=payload.company,
            sector_code=payload.sector_code,
            start_date=payload.start_date,
            end_date=payload.end_date,
            description=payload.description,
            position=len(profile.experiences),
            source="user_input",
            confidence=1.0,
        )
        profile.experiences.append(exp)
        self._after_experiences_changed(profile)
        await self._repository.commit()
        return _experience_out(exp)

    async def update_experience(
        self, user_id: uuid.UUID, experience_id: uuid.UUID, payload: ExperienceInput
    ) -> ExperienceOut:
        profile = await self._get_or_create(user_id)
        exp = self._find(profile.experiences, experience_id, "Expérience")
        exp.title = payload.title
        exp.company = payload.company
        exp.sector_code = payload.sector_code
        exp.start_date = payload.start_date
        exp.end_date = payload.end_date
        exp.description = payload.description
        self._mark_user_input(exp)
        self._after_experiences_changed(profile)
        await self._repository.commit()
        return _experience_out(exp)

    async def delete_experience(self, user_id: uuid.UUID, experience_id: uuid.UUID) -> None:
        profile = await self._get_or_create(user_id)
        exp = self._find(profile.experiences, experience_id, "Expérience")
        profile.experiences.remove(exp)
        self._after_experiences_changed(profile)
        await self._repository.commit()

    # ------------------------------------------------------------ formations

    async def add_education(self, user_id: uuid.UUID, payload: EducationInput) -> EducationOut:
        profile = await self._get_or_create(user_id)
        edu = ProfileEducation(
            id=uuid.uuid4(),
            profile_id=profile.id,
            degree=payload.degree,
            institution=payload.institution,
            start_year=payload.start_year,
            end_year=payload.end_year,
            source="user_input",
            confidence=1.0,
        )
        profile.educations.append(edu)
        self._bump_version(profile)
        await self._repository.commit()
        return _education_out(edu)

    async def update_education(
        self, user_id: uuid.UUID, education_id: uuid.UUID, payload: EducationInput
    ) -> EducationOut:
        profile = await self._get_or_create(user_id)
        edu = self._find(profile.educations, education_id, "Formation")
        edu.degree = payload.degree
        edu.institution = payload.institution
        edu.start_year = payload.start_year
        edu.end_year = payload.end_year
        self._mark_user_input(edu)
        self._bump_version(profile)
        await self._repository.commit()
        return _education_out(edu)

    async def delete_education(self, user_id: uuid.UUID, education_id: uuid.UUID) -> None:
        profile = await self._get_or_create(user_id)
        edu = self._find(profile.educations, education_id, "Formation")
        profile.educations.remove(edu)
        self._bump_version(profile)
        await self._repository.commit()

    # ------------------------------------------------------------ compétences

    async def add_skill(self, user_id: uuid.UUID, payload: SkillInput) -> SkillOut:
        profile = await self._get_or_create(user_id)
        self._ensure_skill_label_free(profile, payload.label, exclude_id=None)
        skill = ProfileSkill(
            id=uuid.uuid4(),
            profile_id=profile.id,
            skill_id=None,  # rapprochement taxonomie au M4 (RM-C-6)
            label_raw=payload.label,
            source="user_input",
            confidence=1.0,
        )
        profile.skills.append(skill)
        self._bump_version(profile)
        await self._repository.commit()
        return _skill_out(skill)

    async def update_skill(
        self, user_id: uuid.UUID, skill_id: uuid.UUID, payload: SkillInput
    ) -> SkillOut:
        profile = await self._get_or_create(user_id)
        skill = self._find(profile.skills, skill_id, "Compétence")
        self._ensure_skill_label_free(profile, payload.label, exclude_id=skill.id)
        skill.label_raw = payload.label
        skill.skill_id = None  # le label a changé : rapprochement à refaire (M4)
        self._mark_user_input(skill)
        self._bump_version(profile)
        await self._repository.commit()
        return _skill_out(skill)

    async def delete_skill(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> None:
        profile = await self._get_or_create(user_id)
        skill = self._find(profile.skills, skill_id, "Compétence")
        profile.skills.remove(skill)
        self._bump_version(profile)
        await self._repository.commit()

    # ------------------------------------------------------------ langues

    async def add_language(self, user_id: uuid.UUID, payload: LanguageInput) -> LanguageOut:
        profile = await self._get_or_create(user_id)
        self._ensure_lang_code_free(profile, payload.lang_code, exclude_id=None)
        lang = ProfileLanguage(
            id=uuid.uuid4(),
            profile_id=profile.id,
            lang_code=payload.lang_code,
            level=payload.level,
            source="user_input",
            confidence=1.0,
        )
        profile.languages.append(lang)
        self._bump_version(profile)
        await self._repository.commit()
        return _language_out(lang)

    async def update_language(
        self, user_id: uuid.UUID, language_id: uuid.UUID, payload: LanguageInput
    ) -> LanguageOut:
        profile = await self._get_or_create(user_id)
        lang = self._find(profile.languages, language_id, "Langue")
        self._ensure_lang_code_free(profile, payload.lang_code, exclude_id=lang.id)
        lang.lang_code = payload.lang_code
        lang.level = payload.level
        self._mark_user_input(lang)
        self._bump_version(profile)
        await self._repository.commit()
        return _language_out(lang)

    async def delete_language(self, user_id: uuid.UUID, language_id: uuid.UUID) -> None:
        profile = await self._get_or_create(user_id)
        lang = self._find(profile.languages, language_id, "Langue")
        profile.languages.remove(lang)
        self._bump_version(profile)
        await self._repository.commit()

    # ------------------------------------------------------------ interne

    async def _get_or_create(self, user_id: uuid.UUID) -> Profile:
        profile = await self._repository.get_by_user(user_id)
        if profile is None:
            profile = await self._repository.create_draft(user_id)
        return profile

    @staticmethod
    def _bump_version(profile: Profile) -> None:
        """RM-C-4 : toute mutation incrémente ``version``.

        Un profil validé RESTE validé après édition (Q23 🟡) : le statut n'est
        jamais rétrogradé ici.
        """
        profile.version += 1
        profile.updated_at = datetime.now(UTC)

    @staticmethod
    def _mark_user_input(
        child: ProfileExperience | ProfileEducation | ProfileSkill | ProfileLanguage,
    ) -> None:
        """Édition manuelle : provenance ``user_input``, confiance 1 (F-C §2)."""
        child.source = "user_input"
        child.confidence = 1.0

    @staticmethod
    def _after_experiences_changed(profile: Profile) -> None:
        profile.total_experience_years = compute_total_experience_years(
            (exp.start_date, exp.end_date) for exp in profile.experiences
        )
        ProfilesService._bump_version(profile)

    @staticmethod
    def _find(children: list[_HasId], child_id: uuid.UUID, entity: str) -> _HasId:
        for child in children:
            if child.id == child_id:
                return child
        raise _not_found(entity)

    @staticmethod
    def _ensure_skill_label_free(
        profile: Profile, label: str, *, exclude_id: uuid.UUID | None
    ) -> None:
        """Doublon de compétence (comparaison insensible à la casse 🟡) → 409."""
        needle = label.casefold()
        for skill in profile.skills:
            if skill.id != exclude_id and skill.label_raw.casefold() == needle:
                raise Problem(
                    status=409,
                    code="duplicate_skill",
                    title="Compétence déjà présente",
                    detail=f"La compétence « {skill.label_raw} » existe déjà dans le profil.",
                )

    @staticmethod
    def _ensure_lang_code_free(
        profile: Profile, lang_code: str, *, exclude_id: uuid.UUID | None
    ) -> None:
        """Unicité (profile_id, lang_code) — contrainte du schéma SQL → 409."""
        for lang in profile.languages:
            if lang.id != exclude_id and lang.lang_code == lang_code:
                raise Problem(
                    status=409,
                    code="duplicate_language",
                    title="Langue déjà présente",
                    detail=f"La langue « {lang_code} » existe déjà dans le profil.",
                )

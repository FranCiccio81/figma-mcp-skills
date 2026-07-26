"""Routes du module profiles (F-C, D05) : /profile et sous-ressources.

Toutes les routes exigent une session valide (cookie ``boussole_session``) —
401 problem+json sinon. Les mutations passent par le middleware CSRF global.
``GET /profile`` crée le profil draft vide à la volée s'il n'existe pas 🟡
(parcours « saisie 100 % manuelle », F-C alternatif 4).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.modules.auth.models import User
from app.modules.auth.router import require_current_user
from app.modules.profiles.repository import ProfilesRepository, get_profiles_repository
from app.modules.profiles.schemas import (
    EducationInput,
    EducationOut,
    ExperienceInput,
    ExperienceOut,
    LanguageInput,
    LanguageOut,
    ProfileOut,
    ProfileRootPatch,
    SkillInput,
    SkillOut,
)
from app.modules.profiles.service import ProfilesService

router = APIRouter(prefix="/profile", tags=["profiles"])


def get_profiles_service(
    repository: ProfilesRepository = Depends(get_profiles_repository),
) -> ProfilesService:
    return ProfilesService(repository)


CurrentUser = Annotated[User, Depends(require_current_user)]
Service = Annotated[ProfilesService, Depends(get_profiles_service)]


# ---------------------------------------------------------------- racine


@router.get("", response_model=ProfileOut, summary="Profil complet avec provenance (D05)")
async def get_profile(user: CurrentUser, service: Service) -> ProfileOut:
    """Profil complet — provenance et confiance par champ. Crée le draft vide
    à la volée au premier appel 🟡 (saisie manuelle sans CV possible)."""
    return await service.get_profile(user.id)


@router.patch("", response_model=ProfileOut, summary="Modifier les champs racine du profil")
async def patch_profile(
    payload: ProfileRootPatch, user: CurrentUser, service: Service
) -> ProfileOut:
    """Met à jour headline/summary/seniority (champs fournis uniquement,
    ``null`` explicite = effacement) et incrémente ``version`` (RM-C-4)."""
    return await service.patch_root(user.id, payload)


@router.post(
    "/validate",
    response_model=ProfileOut,
    summary="Valider le profil (promotion cv_extraction → user_confirmed)",
)
async def validate_profile(user: CurrentUser, service: Service) -> ProfileOut:
    """Préconditions RM-C-3 : ≥ 3 compétences ET (≥ 1 expérience OU ≥ 1
    formation), sinon 409 ``profile_incomplete`` avec le détail des manques."""
    return await service.validate_profile(user.id)


# ---------------------------------------------------------------- expériences


@router.post(
    "/experiences",
    status_code=201,
    response_model=ExperienceOut,
    summary="Ajouter une expérience (source = user_input)",
)
async def add_experience(
    payload: ExperienceInput, user: CurrentUser, service: Service
) -> ExperienceOut:
    return await service.add_experience(user.id, payload)


@router.patch(
    "/experiences/{experience_id}",
    response_model=ExperienceOut,
    summary="Modifier une expérience (provenance passe à user_input)",
)
async def update_experience(
    experience_id: uuid.UUID,
    payload: ExperienceInput,
    user: CurrentUser,
    service: Service,
) -> ExperienceOut:
    return await service.update_experience(user.id, experience_id, payload)


@router.delete(
    "/experiences/{experience_id}", status_code=204, summary="Supprimer une expérience"
)
async def delete_experience(
    experience_id: uuid.UUID, user: CurrentUser, service: Service
) -> Response:
    await service.delete_experience(user.id, experience_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- formations


@router.post(
    "/educations",
    status_code=201,
    response_model=EducationOut,
    summary="Ajouter une formation (source = user_input)",
)
async def add_education(
    payload: EducationInput, user: CurrentUser, service: Service
) -> EducationOut:
    return await service.add_education(user.id, payload)


@router.patch(
    "/educations/{education_id}",
    response_model=EducationOut,
    summary="Modifier une formation (provenance passe à user_input)",
)
async def update_education(
    education_id: uuid.UUID,
    payload: EducationInput,
    user: CurrentUser,
    service: Service,
) -> EducationOut:
    return await service.update_education(user.id, education_id, payload)


@router.delete(
    "/educations/{education_id}", status_code=204, summary="Supprimer une formation"
)
async def delete_education(
    education_id: uuid.UUID, user: CurrentUser, service: Service
) -> Response:
    await service.delete_education(user.id, education_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- compétences


@router.post(
    "/skills",
    status_code=201,
    response_model=SkillOut,
    summary="Ajouter une compétence (source = user_input)",
)
async def add_skill(payload: SkillInput, user: CurrentUser, service: Service) -> SkillOut:
    return await service.add_skill(user.id, payload)


@router.patch(
    "/skills/{skill_id}",
    response_model=SkillOut,
    summary="Modifier une compétence (provenance passe à user_input)",
)
async def update_skill(
    skill_id: uuid.UUID, payload: SkillInput, user: CurrentUser, service: Service
) -> SkillOut:
    return await service.update_skill(user.id, skill_id, payload)


@router.delete("/skills/{skill_id}", status_code=204, summary="Supprimer une compétence")
async def delete_skill(skill_id: uuid.UUID, user: CurrentUser, service: Service) -> Response:
    await service.delete_skill(user.id, skill_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- langues


@router.post(
    "/languages",
    status_code=201,
    response_model=LanguageOut,
    summary="Ajouter une langue (CECRL, source = user_input)",
)
async def add_language(
    payload: LanguageInput, user: CurrentUser, service: Service
) -> LanguageOut:
    return await service.add_language(user.id, payload)


@router.patch(
    "/languages/{language_id}",
    response_model=LanguageOut,
    summary="Modifier une langue (provenance passe à user_input)",
)
async def update_language(
    language_id: uuid.UUID,
    payload: LanguageInput,
    user: CurrentUser,
    service: Service,
) -> LanguageOut:
    return await service.update_language(user.id, language_id, payload)


@router.delete("/languages/{language_id}", status_code=204, summary="Supprimer une langue")
async def delete_language(
    language_id: uuid.UUID, user: CurrentUser, service: Service
) -> Response:
    await service.delete_language(user.id, language_id)
    return Response(status_code=204)

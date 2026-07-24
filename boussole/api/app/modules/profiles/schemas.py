"""Schémas Pydantic du module profiles — conformes à openapi.yaml.

Notes :
- ``Provenance`` (D05) accompagne chaque sous-ressource : ``source`` ∈
  {cv_extraction, user_input, user_confirmed}, ``confidence`` ∈ [0,1] ;
- les sous-ressources ``educations``/``languages`` exposent un ``id`` additif
  (autorisé par le versionnement §1 des contrats) : nécessaire aux routes
  PATCH/DELETE ``/profile/…/{id}`` ;
- PATCH ``/profile`` distingue « champ absent » de « champ null » via
  ``model_fields_set`` (headline/summary sont nullables dans le contrat).
"""

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from app.modules.jobs.schemas import SeniorityLevel

FieldSource = Literal["cv_extraction", "user_input", "user_confirmed"]
ProfileStatus = Literal["draft", "validated"]
CefrLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]

# Code ISO 639-1 (RM-C-6) — normalisé en minuscules après validation (le
# pattern pydantic s'applique AVANT to_lower, d'où l'AfterValidator).
LangCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-zA-Z]{2,3}$"),
    AfterValidator(str.lower),
]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Provenance(BaseModel):
    """Provenance et confiance d'un champ extrait (D05)."""

    source: FieldSource
    confidence: float = Field(ge=0, le=1)


class ExperienceInput(BaseModel):
    """Corps de POST/PATCH /profile/experiences — schéma ExperienceInput."""

    title: Label
    company: Label
    sector_code: str | None = None
    start_date: date
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def check_dates(self) -> "ExperienceInput":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date doit être postérieure ou égale à start_date")
        return self


class ExperienceOut(ExperienceInput):
    """Expérience en lecture — ExperienceInput + id + provenance."""

    id: uuid.UUID
    provenance: Provenance


class EducationInput(BaseModel):
    """Corps de POST/PATCH /profile/educations — champs de profile_educations."""

    degree: Label
    institution: Label
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_year: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def check_years(self) -> "EducationInput":
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.end_year < self.start_year
        ):
            raise ValueError("end_year doit être postérieure ou égale à start_year")
        return self


class EducationOut(EducationInput):
    id: uuid.UUID
    provenance: Provenance


class SkillInput(BaseModel):
    """Corps de POST/PATCH /profile/skills."""

    label: Label


class SkillOut(SkillInput):
    id: uuid.UUID
    provenance: Provenance


class LanguageInput(BaseModel):
    """Corps de POST/PATCH /profile/languages — niveau CECRL (RM-C-6)."""

    lang_code: LangCode
    level: CefrLevel


class LanguageOut(LanguageInput):
    id: uuid.UUID
    provenance: Provenance


class ProfileRootPatch(BaseModel):
    """Corps de PATCH /profile — seuls les champs fournis sont modifiés."""

    headline: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=2000)
    seniority: SeniorityLevel | None = None


class ProfileOut(BaseModel):
    """Profil complet avec provenance par champ — schéma Profile d'openapi.yaml."""

    id: uuid.UUID
    status: ProfileStatus
    version: int
    headline: str | None = None
    summary: str | None = None
    seniority: SeniorityLevel | None = None
    total_experience_years: float | None = None
    experiences: list[ExperienceOut] = Field(default_factory=list)
    educations: list[EducationOut] = Field(default_factory=list)
    skills: list[SkillOut] = Field(default_factory=list)
    languages: list[LanguageOut] = Field(default_factory=list)

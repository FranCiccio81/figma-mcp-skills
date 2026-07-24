"""Schémas Pydantic du module auth — conformes à openapi.yaml."""

import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    locale: str = "fr"
    accepted_terms_version: str
    accepted_privacy_version: str


class RegisterResponse(BaseModel):
    """Réponse neutre anti-énumération (🟡 Q31) — identique que le compte
    ait été créé ou que l'e-mail existe déjà."""

    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OnboardingState(BaseModel):
    cv_imported: bool = False
    profile_validated: bool = False
    preferences_set: bool = False


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    locale: str
    onboarding: OnboardingState

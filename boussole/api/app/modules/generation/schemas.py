"""Schémas Pydantic du module generation — conformes à openapi.yaml.

``GeneratedDocumentOut`` suit le schéma contractuel ``GeneratedDocument``
(id, doc_type, status 5 états, based_on_profile_version, prompt_version,
content nullable, anchoring_check nullable) + champs ADDITIFS (autorisés
sans bump de version, 12-api-contracts §1) : ``job_id``, ``application_id``,
``created_at``, ``validated_at``, ``error_code``, ``manually_edited`` et
``anchoring_note`` (rappel de responsabilité après édition manuelle, Q6 🟡).
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DocType = Literal["email", "cover_letter", "cv_variant", "cv_optimization"]
DocStatus = Literal["pending", "draft", "validated", "exported", "failed"]
Tone = Literal["sobre", "chaleureux", "direct"]
Language = Literal["fr", "en"]
Length = Literal["court", "standard"]
ExportFormat = Literal["text", "pdf", "docx"]


class GenerationOptions(BaseModel):
    """Options de génération (openapi.yaml) — langue par défaut : celle de
    l'offre (RM-L-5, D15), résolue à la création."""

    model_config = ConfigDict(extra="forbid")

    tone: Tone = "sobre"
    language: Language | None = None
    length: Length = "standard"


class GenerationCreate(BaseModel):
    """Corps de ``POST /generations`` — job_id requis sauf cv_optimization
    (contrôle porté par le service : message d'erreur contractuel)."""

    model_config = ConfigDict(extra="forbid")

    doc_type: DocType
    job_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class GenerationPatch(BaseModel):
    """Corps de ``PATCH /generations/{id}`` — édition manuelle du brouillon."""

    model_config = ConfigDict(extra="forbid")

    content: dict[str, Any]


class AnchoringCheckOut(BaseModel):
    """Résultat du contrôle d'ancrage post-génération (RM-L-2)."""

    status: Literal["passed", "failed"]
    unanchored_claims: list[str] = Field(default_factory=list)


class GeneratedDocumentOut(BaseModel):
    """Schéma contractuel ``GeneratedDocument`` + champs additifs."""

    id: uuid.UUID
    doc_type: DocType
    status: DocStatus
    job_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    based_on_profile_version: int
    prompt_version: str
    content: dict[str, Any] | None = None
    anchoring_check: AnchoringCheckOut | None = None
    anchoring_note: str | None = None
    manually_edited: bool = False
    error_code: str | None = None
    created_at: datetime
    validated_at: datetime | None = None


class GenerationPage(BaseModel):
    """Page paginée par curseur opaque (12-api-contracts §1)."""

    items: list[GeneratedDocumentOut]
    next_cursor: str | None = None


class ExportRequest(BaseModel):
    """Corps de ``POST /generations/{id}/export``."""

    model_config = ConfigDict(extra="forbid")

    format: ExportFormat = "text"


class ExportOut(BaseModel):
    """Réponse d'export : contenu texte (M4) ou lien signé (PDF/DOCX, M5 🟡)."""

    format: ExportFormat
    content: str | None = None
    download_url: str | None = None

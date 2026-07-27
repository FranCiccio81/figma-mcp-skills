"""Schémas Pydantic du module privacy (contrats 12 / openapi.yaml)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

ExportStatus = Literal["pending", "ready", "expired"]


class ExportRequestedResponse(BaseModel):
    """Réponse 202 de POST /privacy/export."""

    id: uuid.UUID
    status: ExportStatus


class ExportStatusResponse(BaseModel):
    """Réponse de GET /privacy/exports/{id}."""

    id: uuid.UUID
    status: ExportStatus
    download_url: str | None = None


class DeleteAccountRequest(BaseModel):
    """Corps de DELETE /account — confirmation par mot de passe (RM-Q-4)."""

    password: str = Field(min_length=1)

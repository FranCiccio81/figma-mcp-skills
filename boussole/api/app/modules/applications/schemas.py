"""Schémas Pydantic du module applications — conformes à openapi.yaml.

Champs additifs autorisés par le versionnement §1 des contrats :
``created_at`` / ``updated_at`` (tri du tableau de bord, « date de dernière
action » F-P) et ``job_title`` / ``job_company`` (libellés de l'offre liée)
sur ``ApplicationOut``.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ApplicationStatus = Literal[
    "draft", "to_apply", "applied", "interviewing", "offer", "rejected", "withdrawn"
]


class ApplicationInput(BaseModel):
    """Corps de POST /applications — schéma ApplicationInput d'openapi.yaml.

    La règle « offre interne OU couple externe » (RM-P-2, CHECK SQL) est
    vérifiée par le service pour produire un 422 problem+json avec la liste
    des champs requis (AC-P-2) — pas par le schéma.
    """

    job_posting_id: uuid.UUID | None = None
    external_title: str | None = Field(default=None, max_length=500)
    external_company: str | None = Field(default=None, max_length=500)
    external_url: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=10_000)


class ApplicationPatch(BaseModel):
    """Corps de PATCH /applications/{id} — champs éditables uniquement.

    ``job_posting_id`` et ``status`` ne sont PAS éditables ici : le statut
    passe exclusivement par POST /applications/{id}/status (historisation
    RM-P-3). Seuls les champs effectivement fournis sont appliqués
    (``exclude_unset``) ; ``null`` explicite efface la valeur.
    """

    external_title: str | None = Field(default=None, max_length=500)
    external_company: str | None = Field(default=None, max_length=500)
    external_url: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=10_000)


class StatusChangeInput(BaseModel):
    """Corps de POST /applications/{id}/status (transition libre Q29)."""

    to_status: ApplicationStatus
    note: str | None = Field(default=None, max_length=1000)


class ApplicationEventOut(BaseModel):
    """Événement d'historique — sous-schéma ``events[]`` d'openapi.yaml."""

    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus
    at: datetime
    note: str | None = None


class ApplicationOut(BaseModel):
    """Candidature — schéma Application d'openapi.yaml (+ dates, additif)."""

    id: uuid.UUID
    job_posting_id: uuid.UUID | None = None
    job_title: str | None = Field(
        default=None,
        description="Champ additif : intitulé de l'offre liée "
        "(``job_postings.title``) — ``null`` pour une candidature externe.",
    )
    job_company: str | None = Field(
        default=None,
        description="Champ additif : entreprise de l'offre liée "
        "(``job_postings.company_name``) — ``null`` pour une candidature externe.",
    )
    external_title: str | None = None
    external_company: str | None = None
    external_url: str | None = None
    notes: str | None = None
    status: ApplicationStatus
    applied_at: datetime | None = None
    events: list[ApplicationEventOut] = Field(default_factory=list)
    created_at: datetime = Field(
        description="Champ additif : date de création (tri du tableau de bord)."
    )
    updated_at: datetime = Field(
        description="Champ additif : date de dernière action (F-P, tableau de bord)."
    )


class ApplicationPage(BaseModel):
    """Page de GET /applications, paginée par curseur opaque (§1 des contrats)."""

    items: list[ApplicationOut]
    next_cursor: str | None = None

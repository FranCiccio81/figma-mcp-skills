"""Schémas Pydantic du module jobs — conformes à openapi.yaml.

Notes M2 :
- ``JobCard.match`` est présent dans le contrat mais TOUJOURS ``null`` au M2 :
  le scoring de matching arrive au jalon M3 (module matching). Le champ est
  conservé pour que le front n'ait pas de rupture de contrat en M3.
- ``JobDetail.status`` est un champ additif (autorisé par le versionnement §1)
  qui permet d'afficher le bandeau « offre expirée » sans appel supplémentaire.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RemotePolicy = Literal["onsite", "hybrid", "full_remote"]
ContractType = Literal[
    "permanent", "fixed_term", "freelance", "internship", "apprenticeship", "other"
]
SeniorityLevel = Literal["intern", "junior", "mid", "senior", "lead", "principal", "executive"]
JobStatus = Literal["active", "expired", "withdrawn"]
SavedState = Literal["saved", "hidden"]
SortMode = Literal["match", "date", "relevance"]
#: ``demo`` : corpus de démonstration, offres FICTIVES (D34). Le dire
#: explicitement permet à l'interface de l'étiqueter comme tel —
#: l'inverse de le faire passer pour une source ordinaire.
SourceKind = Literal["public_api", "ats_feed", "partner", "demo"]


class MatchSummary(BaseModel):
    """Résumé de matching embarqué dans une JobCard — peuplé au M3."""

    score: int
    confidence: int
    low_data: bool
    has_blocking: bool


class JobCard(BaseModel):
    """Carte d'offre (liste de résultats) — schéma JobCard d'openapi.yaml."""

    id: uuid.UUID
    title: str
    company_name: str
    locations: list[str]
    remote: RemotePolicy | None = None
    contract: ContractType | None = None
    salary_label: str | None = Field(
        default=None, description="'45–55 k€' ou null si non communiqué"
    )
    posted_at: datetime | None = None
    match: MatchSummary | None = Field(
        default=None,
        description="Toujours null au M2 — le scoring arrive au M3 (module matching).",
    )
    saved_state: SavedState | None = None


class JobSourceOut(BaseModel):
    """Source d'une offre — name et original_url obligatoires (garantie produit)."""

    name: str
    original_url: str
    posted_at: datetime | None = None


class JobDetail(JobCard):
    """Détail d'une offre — schéma JobDetail d'openapi.yaml (+ status, additif)."""

    description_text: str
    language: str
    seniority: SeniorityLevel | None = None
    skills_required: list[str] = Field(default_factory=list)
    skills_nice: list[str] = Field(default_factory=list)
    status: JobStatus = Field(
        description="Champ additif : permet le bandeau « offre expirée » côté front."
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Champ additif : date d'expiration si connue (bandeau front).",
    )
    sources: list[JobSourceOut] = Field(min_length=1)


class SearchPage(BaseModel):
    """Page de résultats paginée par curseur opaque (§1 des contrats API)."""

    items: list[JobCard]
    next_cursor: str | None = None


class SavedStateInput(BaseModel):
    """Corps de PUT /jobs/{id}/saved-state."""

    state: SavedState


class SourceOut(BaseModel):
    """Élément de GET /sources (transparence des sources actives)."""

    slug: str
    name: str
    kind: SourceKind
    last_sync_at: datetime | None = None

"""Schémas Pydantic du sous-package CV — conformes à openapi.yaml#CvDocument.

``CvDocumentOut`` reprend le schéma ``CvDocument`` du contrat (id, filename,
status, error_code, extraction_warnings) et lui ajoute deux champs ADDITIFS
(autorisés par le versionnement §1 des contrats) :

- ``proposal`` : la sortie d'extraction transformée en PROPOSITION de profil
  — chaque champ porte une provenance ``cv_extraction`` + ``confidence``
  (D05) et n'est JAMAIS écrit dans le profil avant l'action explicite
  ``POST /cv-documents/{id}/apply`` 🟡 (endpoint absent d'openapi.yaml —
  écart documenté dans le router) ;
- ``trace_id`` : identifiant de corrélation de l'échec d'extraction, exigé
  par 04 Flux 1 pour le bloc repliable « détails techniques » affiché sur
  ``error_code = extraction_failed``.
"""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.profiles.schemas import CefrLevel, Provenance

CvStatus = Literal["uploaded", "parsing", "parsed", "failed"]
CvErrorCode = Literal[
    "unreadable", "image_only_pdf", "too_large", "unsupported_format", "extraction_failed"
]


class ProposedExperience(BaseModel):
    """Expérience proposée — dates partielles converties (YYYY → 1er janvier,
    YYYY-MM → 1er du mois 🟡).

    ``item_id`` : identifiant déterministe et STABLE entre deux lectures
    (``experience:<index dans la sortie d'extraction>``) — support des cases
    à cocher par item du flux de revue (04 Flux 1 §5). ``evidence_quote`` :
    citation exacte du document qui justifie l'extraction (RM-B-5).
    """

    item_id: str
    title: str
    company: str
    start_date: date
    end_date: date | None = None
    description: str | None = None
    evidence_quote: str | None = None
    provenance: Provenance


class ProposedEducation(BaseModel):
    item_id: str
    degree: str
    institution: str
    start_year: int | None = None
    end_year: int | None = None
    evidence_quote: str | None = None
    provenance: Provenance


class ProposedSkill(BaseModel):
    item_id: str
    label: str
    evidence_quote: str | None = None
    provenance: Provenance


class ProposedLanguage(BaseModel):
    """Langue proposée — ``evidence_quote`` peut être None (le schéma
    d'extraction autorise les langues sans evidence)."""

    item_id: str
    lang_code: str
    level: CefrLevel
    evidence_quote: str | None = None
    provenance: Provenance


class CvProposal(BaseModel):
    """Proposition de profil issue de l'extraction (source=cv_extraction).

    Présentée en revue AVANT fusion (F-B alternatif 7) : rien n'est écrit
    dans le profil tant que l'utilisateur n'applique pas la proposition.
    """

    headline: str | None = None
    summary: str | None = None
    experiences: list[ProposedExperience] = Field(default_factory=list)
    educations: list[ProposedEducation] = Field(default_factory=list)
    skills: list[ProposedSkill] = Field(default_factory=list)
    languages: list[ProposedLanguage] = Field(default_factory=list)


class ApplyInput(BaseModel):
    """Corps OPTIONNEL de ``POST /cv-documents/{id}/apply`` — sélection par item.

    - ``item_ids`` : ``item_id`` des items cochés en revue (04 Flux 1 §5) ;
      ``None`` = tout appliquer (rétrocompatible avec l'apply tout-ou-rien).
      Un id inconnu est ignoré silencieusement 🟡 (proposition régénérée
      entre-temps : la sélection reste appliquée au mieux, sans erreur) ;
    - ``include_headline`` / ``include_summary`` : les champs racine n'étant
      pas des items de liste, leur inclusion est pilotée par ces booléens 🟡
      (défaut ``True`` = comportement historique).
    """

    item_ids: list[str] | None = None
    include_headline: bool = True
    include_summary: bool = True


class CvDocumentOut(BaseModel):
    """Schéma ``CvDocument`` d'openapi.yaml + additifs ``proposal``/``trace_id``."""

    id: uuid.UUID
    filename: str
    status: CvStatus
    error_code: CvErrorCode | None = None
    extraction_warnings: list[str] = Field(default_factory=list)
    proposal: CvProposal | None = None
    trace_id: str | None = Field(
        default=None,
        description="Champ additif : identifiant de corrélation de l'échec "
        "d'extraction (04 Flux 1, bloc « détails techniques » repliable). "
        "``null`` tant que le document n'a pas échoué sur un appel LLM.",
    )

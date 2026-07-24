"""Schémas Pydantic du module preferences — conformes à openapi.yaml (Preferences).

``PUT /preferences`` est un remplacement complet : toute liste omise est vidée
(F-D alternatif 1) ; ``remote_pref`` et ``contract_types`` omis retombent sur
les défauts produit (indifferent / [permanent] — défauts du schéma SQL) 🟡.
Le même schéma sert de corps de requête et de réponse (payload unique).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.modules.jobs.schemas import ContractType

RemotePreference = Literal["required", "preferred", "indifferent", "onsite_preferred"]

Item = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
SectorCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]

#: Rayon autorisé autour d'une localisation, en km 🟡 (défaut 30 — RM-D-2).
RADIUS_KM_MIN = 1
RADIUS_KM_MAX = 200


class LocationInput(BaseModel):
    """Localisation cible avec rayon (RM-D-2 : défaut 30 km)."""

    label: Item
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: int = Field(default=30, ge=RADIUS_KM_MIN, le=RADIUS_KM_MAX)


class PreferencesPayload(BaseModel):
    """Schéma Preferences d'openapi.yaml — requête ET réponse."""

    remote_pref: RemotePreference = "indifferent"
    contract_types: list[ContractType] = Field(
        default_factory=lambda: list[ContractType](["permanent"])
    )
    contract_strict: bool = False
    salary_min: int | None = Field(default=None, ge=0, description="EUR brut annuel (RM-D-5)")
    salary_min_strict: int | None = Field(
        default=None, ge=0, description="Rédhibitoire — bloquant salary_below_minimum (RM-D-3)"
    )
    locations: list[LocationInput] = Field(default_factory=list, max_length=20)
    target_titles: list[Item] = Field(default_factory=list, max_length=50)
    sectors_preferred: list[SectorCode] = Field(default_factory=list, max_length=50)
    sectors_excluded: list[SectorCode] = Field(default_factory=list, max_length=50)
    target_companies: list[Item] = Field(default_factory=list, max_length=50)
    keywords: list[Item] = Field(default_factory=list, max_length=50)

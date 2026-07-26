"""Logique métier du module preferences (F-D).

Règles portées ici :
- ``GET /preferences`` : défauts si jamais définies 🟡 (remote ``indifferent``,
  ``contract_types=[permanent]``, listes vides) — rien n'est persisté ;
- ``PUT /preferences`` : remplacement complet transactionnel ; validations
  422 (salaire strict > souhaité, secteurs inconnus ou à la fois préférés et
  exclus) avec ``errors[]`` ciblant le champ (AC-D-4) ;
- listes dédupliquées avant écriture (companies/keywords insensibles à la
  casse — clés primaires citext du schéma SQL) ;
- toute mise à jour émet l'événement interne « preferences_changed » via un
  hook injectable, no-op au M3 (RM-D-4).
"""

import uuid
from collections.abc import Awaitable, Callable, Iterable
from typing import cast

from app.core.problems import Problem
from app.modules.jobs.schemas import ContractType
from app.modules.preferences.repository import (
    LocationData,
    PreferencesData,
    PreferencesRepository,
)
from app.modules.preferences.schemas import (
    LocationInput,
    PreferencesPayload,
    RemotePreference,
)

#: Hook interne « preferences_changed » — signature : (user_id) -> None.
PreferencesChangedHook = Callable[[uuid.UUID], Awaitable[None]]


async def noop_preferences_changed(user_id: uuid.UUID) -> None:
    """Implémentation par défaut de l'événement « preferences_changed ».

    TODO(M4) : brancher ici le re-scoring asynchrone des offres actives
    (RM-D-4, 06 §4 déclencheur a) et l'invalidation des tris en cache.
    """
    return None


def _dedupe(values: Iterable[str], *, casefold: bool = False) -> tuple[str, ...]:
    """Déduplique en préservant l'ordre (option : insensible à la casse)."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold() if casefold else value
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _to_payload(data: PreferencesData) -> PreferencesPayload:
    # Casts sûrs : valeurs issues d'enums PostgreSQL ou déjà validées.
    return PreferencesPayload(
        remote_pref=cast(RemotePreference, data.remote_pref),
        contract_types=[cast(ContractType, c) for c in data.contract_types],
        contract_strict=data.contract_strict,
        salary_min=data.salary_min,
        salary_min_strict=data.salary_min_strict,
        locations=[
            LocationInput(
                label=location.label,
                lat=location.lat,
                lon=location.lon,
                radius_km=location.radius_km,
            )
            for location in data.locations
        ],
        target_titles=list(data.target_titles),
        sectors_preferred=list(data.sectors_preferred),
        sectors_excluded=list(data.sectors_excluded),
        target_companies=list(data.target_companies),
        keywords=list(data.keywords),
    )


def default_preferences() -> PreferencesPayload:
    """Défauts produit 🟡 tant que l'utilisateur n'a rien enregistré."""
    return PreferencesPayload()


class PreferencesService:
    def __init__(
        self,
        repository: PreferencesRepository,
        on_changed: PreferencesChangedHook | None = None,
    ) -> None:
        self._repository = repository
        self._on_changed = on_changed or noop_preferences_changed

    async def get(self, user_id: uuid.UUID) -> PreferencesPayload:
        data = await self._repository.get(user_id)
        if data is None:
            return default_preferences()
        return _to_payload(data)

    async def put(self, user_id: uuid.UUID, payload: PreferencesPayload) -> PreferencesPayload:
        """Remplacement complet (F-D) — 422 avant toute écriture (AC-D-4)."""
        sectors_preferred = _dedupe(payload.sectors_preferred)
        sectors_excluded = _dedupe(payload.sectors_excluded)
        await self._validate(payload, sectors_preferred, sectors_excluded)

        data = PreferencesData(
            remote_pref=payload.remote_pref,
            contract_types=_dedupe(payload.contract_types),
            contract_strict=payload.contract_strict,
            salary_min=payload.salary_min,
            salary_min_strict=payload.salary_min_strict,
            locations=tuple(
                LocationData(
                    label=location.label,
                    lat=location.lat,
                    lon=location.lon,
                    radius_km=location.radius_km,
                )
                for location in payload.locations
            ),
            target_titles=_dedupe(payload.target_titles, casefold=True),
            sectors_preferred=sectors_preferred,
            sectors_excluded=sectors_excluded,
            # Clés primaires citext (user_id, name/keyword) : dédup
            # insensible à la casse obligatoire avant insertion.
            target_companies=_dedupe(payload.target_companies, casefold=True),
            keywords=_dedupe(payload.keywords, casefold=True),
        )
        await self._repository.replace(user_id, data)
        # Événement interne « preferences_changed » (RM-D-4) — no-op au M3,
        # le re-scoring asynchrone s'y branchera (M4).
        await self._on_changed(user_id)
        return _to_payload(data)

    async def _validate(
        self,
        payload: PreferencesPayload,
        sectors_preferred: tuple[str, ...],
        sectors_excluded: tuple[str, ...],
    ) -> None:
        errors: list[dict[str, str]] = []
        if (
            payload.salary_min is not None
            and payload.salary_min_strict is not None
            and payload.salary_min_strict > payload.salary_min
        ):
            errors.append(
                {
                    "field": "salary_min_strict",
                    "code": "strict_above_target",
                    "message": (
                        "Le minimum strict (rédhibitoire) doit être inférieur "
                        "ou égal au salaire souhaité."
                    ),
                }
            )

        overlap = sorted(set(sectors_preferred) & set(sectors_excluded))
        if overlap:
            errors.append(
                {
                    "field": "sectors_excluded",
                    "code": "sector_both_preferred_and_excluded",
                    "message": (
                        "Secteurs à la fois préférés et exclus : " + ", ".join(overlap) + "."
                    ),
                }
            )

        requested = set(sectors_preferred) | set(sectors_excluded)
        if requested:
            known = await self._repository.existing_sector_codes(sorted(requested))
            unknown = sorted(requested - known)
            if unknown:
                field = (
                    "sectors_preferred"
                    if any(code in sectors_preferred for code in unknown)
                    else "sectors_excluded"
                )
                errors.append(
                    {
                        "field": field,
                        "code": "unknown_sector",
                        "message": "Secteurs inconnus du référentiel : "
                        + ", ".join(unknown)
                        + ".",
                    }
                )

        if errors:
            raise Problem(
                status=422,
                code="validation_error",
                title="Données invalides",
                detail="Les préférences n'ont pas été enregistrées : corrigez les champs.",
                errors=errors,
            )

"""Accès aux données du module preferences.

``replace`` est transactionnel : upsert de la ligne ``preferences`` +
delete/insert des cinq tables enfants dans la même transaction — un échec
laisse l'état précédent intact (AC-D-4). Le protocole permet une
implémentation en mémoire dans les tests (pas de PostgreSQL requis).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.modules.preferences.models import (
    PreferenceCompany,
    PreferenceKeyword,
    PreferenceLocation,
    Preferences,
    PreferenceSector,
    PreferenceTitle,
)
from app.modules.referentials.models import Sector


@dataclass(frozen=True, slots=True)
class LocationData:
    label: str
    lat: float
    lon: float
    radius_km: int


@dataclass(frozen=True, slots=True)
class PreferencesData:
    """Agrégat préférences — payload unique de GET/PUT (F-D)."""

    remote_pref: str
    contract_types: tuple[str, ...]
    contract_strict: bool
    salary_min: int | None
    salary_min_strict: int | None
    locations: tuple[LocationData, ...]
    target_titles: tuple[str, ...]
    sectors_preferred: tuple[str, ...]
    sectors_excluded: tuple[str, ...]
    target_companies: tuple[str, ...]
    keywords: tuple[str, ...]


class PreferencesRepository(Protocol):
    async def get(self, user_id: uuid.UUID) -> PreferencesData | None: ...

    async def replace(self, user_id: uuid.UUID, data: PreferencesData) -> None:
        """Remplacement complet transactionnel (ligne + enfants)."""
        ...

    async def existing_sector_codes(self, codes: Sequence[str]) -> set[str]:
        """Sous-ensemble de ``codes`` présent dans le référentiel ``sectors``."""
        ...


class SqlAlchemyPreferencesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> PreferencesData | None:
        row = await self._session.get(Preferences, user_id)
        if row is None:
            return None
        locations = (
            (
                await self._session.execute(
                    select(PreferenceLocation)
                    .where(PreferenceLocation.user_id == user_id)
                    .order_by(PreferenceLocation.label)
                )
            )
            .scalars()
            .all()
        )
        titles = (
            (
                await self._session.execute(
                    select(PreferenceTitle.title)
                    .where(PreferenceTitle.user_id == user_id)
                    .order_by(PreferenceTitle.title)
                )
            )
            .scalars()
            .all()
        )
        sectors = (
            (
                await self._session.execute(
                    select(PreferenceSector)
                    .where(PreferenceSector.user_id == user_id)
                    .order_by(PreferenceSector.sector_code)
                )
            )
            .scalars()
            .all()
        )
        companies = (
            (
                await self._session.execute(
                    select(PreferenceCompany.name)
                    .where(PreferenceCompany.user_id == user_id)
                    .order_by(PreferenceCompany.name)
                )
            )
            .scalars()
            .all()
        )
        keywords = (
            (
                await self._session.execute(
                    select(PreferenceKeyword.keyword)
                    .where(PreferenceKeyword.user_id == user_id)
                    .order_by(PreferenceKeyword.keyword)
                )
            )
            .scalars()
            .all()
        )
        return PreferencesData(
            remote_pref=row.remote_pref,
            contract_types=tuple(row.contract_types),
            contract_strict=row.contract_strict,
            salary_min=row.salary_min,
            salary_min_strict=row.salary_min_strict,
            locations=tuple(
                LocationData(label=lo.label, lat=lo.lat, lon=lo.lon, radius_km=lo.radius_km)
                for lo in locations
            ),
            target_titles=tuple(titles),
            sectors_preferred=tuple(s.sector_code for s in sectors if s.mode == "preferred"),
            sectors_excluded=tuple(s.sector_code for s in sectors if s.mode == "excluded"),
            target_companies=tuple(companies),
            keywords=tuple(keywords),
        )

    async def replace(self, user_id: uuid.UUID, data: PreferencesData) -> None:
        values = {
            "remote_pref": data.remote_pref,
            "contract_types": list(data.contract_types),
            "contract_strict": data.contract_strict,
            "salary_min": data.salary_min,
            "salary_min_strict": data.salary_min_strict,
            "updated_at": datetime.now(UTC),
        }
        await self._session.execute(
            pg_insert(Preferences)
            .values(user_id=user_id, **values)
            .on_conflict_do_update(index_elements=[Preferences.user_id], set_=values)
        )
        for child in (
            PreferenceLocation,
            PreferenceTitle,
            PreferenceSector,
            PreferenceCompany,
            PreferenceKeyword,
        ):
            await self._session.execute(delete(child).where(child.user_id == user_id))
        for location in data.locations:
            self._session.add(
                PreferenceLocation(
                    user_id=user_id,
                    label=location.label,
                    lat=location.lat,
                    lon=location.lon,
                    radius_km=location.radius_km,
                )
            )
        for title in data.target_titles:
            self._session.add(PreferenceTitle(user_id=user_id, title=title))
        for code in data.sectors_preferred:
            self._session.add(
                PreferenceSector(user_id=user_id, sector_code=code, mode="preferred")
            )
        for code in data.sectors_excluded:
            self._session.add(
                PreferenceSector(user_id=user_id, sector_code=code, mode="excluded")
            )
        for name in data.target_companies:
            self._session.add(PreferenceCompany(user_id=user_id, name=name))
        for keyword in data.keywords:
            self._session.add(PreferenceKeyword(user_id=user_id, keyword=keyword))
        # Commit unique : upsert + delete + insert atomiques (AC-D-4).
        await self._session.commit()

    async def existing_sector_codes(self, codes: Sequence[str]) -> set[str]:
        if not codes:
            return set()
        stmt = select(Sector.code).where(Sector.code.in_(list(codes)))
        return set((await self._session.execute(stmt)).scalars().all())


async def get_preferences_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PreferencesRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyPreferencesRepository(session)

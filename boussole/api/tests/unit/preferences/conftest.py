"""Fixtures des tests du module preferences.

``InMemoryPreferencesRepository`` implémente le protocole
``PreferencesRepository`` sans PostgreSQL ; le référentiel de secteurs est un
simple ensemble de codes. ``recorded_changes`` capture les émissions du hook
« preferences_changed » (surcharge de la dépendance du routeur).
"""

import uuid
from collections.abc import Sequence

import pytest
from fastapi.testclient import TestClient

from app.modules.preferences.repository import PreferencesData, get_preferences_repository
from app.modules.preferences.router import get_preferences_changed_hook

#: Codes NACE simplifiés considérés comme existants dans les tests.
KNOWN_SECTORS = {"J", "K", "M"}


class InMemoryPreferencesRepository:
    """Implémentation en mémoire du protocole PreferencesRepository."""

    def __init__(self, sector_codes: set[str] | None = None) -> None:
        self.by_user: dict[uuid.UUID, PreferencesData] = {}
        self.sector_codes = KNOWN_SECTORS if sector_codes is None else sector_codes

    async def get(self, user_id: uuid.UUID) -> PreferencesData | None:
        return self.by_user.get(user_id)

    async def replace(self, user_id: uuid.UUID, data: PreferencesData) -> None:
        self.by_user[user_id] = data

    async def existing_sector_codes(self, codes: Sequence[str]) -> set[str]:
        return {code for code in codes if code in self.sector_codes}


@pytest.fixture
def preferences_repository() -> InMemoryPreferencesRepository:
    return InMemoryPreferencesRepository()


@pytest.fixture
def recorded_changes() -> list[uuid.UUID]:
    return []


@pytest.fixture
def client(
    client: TestClient,
    preferences_repository: InMemoryPreferencesRepository,
    recorded_changes: list[uuid.UUID],
) -> TestClient:
    """Étend le client commun avec le repo preferences et un hook espion."""

    async def spy_hook(user_id: uuid.UUID) -> None:
        recorded_changes.append(user_id)

    client.app.dependency_overrides[get_preferences_repository] = (
        lambda: preferences_repository
    )
    client.app.dependency_overrides[get_preferences_changed_hook] = lambda: spy_hook
    return client

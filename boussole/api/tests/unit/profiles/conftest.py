"""Fixtures des tests du module profiles.

``InMemoryProfilesRepository`` implémente le protocole ``ProfilesRepository``
sans PostgreSQL : les instances ORM détachées se manipulent comme des objets
Python ordinaires (mêmes mutations que le service en production).
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.modules.profiles.models import (
    Profile,
    ProfileEducation,
    ProfileExperience,
    ProfileLanguage,
    ProfileSkill,
)
from app.modules.profiles.repository import get_profiles_repository


def make_profile(
    user_id: uuid.UUID,
    *,
    status: str = "draft",
    version: int = 1,
    skills: list[tuple[str, str, float]] | None = None,  # (label, source, confidence)
    experiences: list[tuple[date, date | None, str]] | None = None,  # (start, end, source)
    educations: list[tuple[str, str]] | None = None,  # (degree, source)
    languages: list[tuple[str, str, str]] | None = None,  # (lang, level, source)
) -> Profile:
    """Fabrique un profil détaché (collections peuplées, aucune session)."""
    profile = Profile(
        id=uuid.uuid4(),
        user_id=user_id,
        status=status,
        version=version,
        headline=None,
        summary=None,
        seniority=None,
        total_experience_years=None,
        validated_at=None,
        updated_at=datetime.now(UTC),
    )
    profile.experiences = [
        ProfileExperience(
            id=uuid.uuid4(),
            profile_id=profile.id,
            title=f"Poste {i}",
            company="Acme",
            sector_code=None,
            start_date=start,
            end_date=end,
            description=None,
            position=i,
            source=source,
            confidence=0.7 if source == "cv_extraction" else 1.0,
        )
        for i, (start, end, source) in enumerate(experiences or [])
    ]
    profile.educations = [
        ProfileEducation(
            id=uuid.uuid4(),
            profile_id=profile.id,
            degree=degree,
            institution="Université",
            start_year=None,
            end_year=None,
            source=source,
            confidence=0.8 if source == "cv_extraction" else 1.0,
        )
        for degree, source in (educations or [])
    ]
    profile.skills = [
        ProfileSkill(
            id=uuid.uuid4(),
            profile_id=profile.id,
            skill_id=None,
            label_raw=label,
            source=source,
            confidence=confidence,
        )
        for label, source, confidence in (skills or [])
    ]
    profile.languages = [
        ProfileLanguage(
            id=uuid.uuid4(),
            profile_id=profile.id,
            lang_code=lang,
            level=level,
            source=source,
            confidence=0.6 if source == "cv_extraction" else 1.0,
        )
        for lang, level, source in (languages or [])
    ]
    return profile


class InMemoryProfilesRepository:
    """Implémentation en mémoire du protocole ProfilesRepository."""

    def __init__(self) -> None:
        self.profiles_by_user: dict[uuid.UUID, Profile] = {}

    def add(self, profile: Profile) -> Profile:
        self.profiles_by_user[profile.user_id] = profile
        return profile

    async def get_by_user(self, user_id: uuid.UUID) -> Profile | None:
        return self.profiles_by_user.get(user_id)

    async def create_draft(self, user_id: uuid.UUID) -> Profile:
        profile = make_profile(user_id)
        self.profiles_by_user[user_id] = profile
        return profile

    async def commit(self) -> None:  # aucune persistance : mutations en place
        return None

    async def delete_by_user(self, user_id: uuid.UUID) -> None:
        self.profiles_by_user.pop(user_id, None)


@pytest.fixture
def profiles_repository() -> InMemoryProfilesRepository:
    return InMemoryProfilesRepository()


@pytest.fixture
def client(client: TestClient, profiles_repository: InMemoryProfilesRepository) -> TestClient:
    """Étend le client commun (tests/unit/conftest.py) avec le repo profiles."""
    client.app.dependency_overrides[get_profiles_repository] = lambda: profiles_repository
    return client

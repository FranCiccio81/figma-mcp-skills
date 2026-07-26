"""Tests des purges / exports RGPD (D21) des modules matching et explanations.

Repositories injectés (fakes en mémoire) — le chemin par défaut (session
SQLAlchemy via la fabrique globale) est couvert par les tests d'intégration.
"""

import uuid
from datetime import UTC, datetime

from app.modules.explanations import purge as explanations_purge
from app.modules.matching import purge as matching_purge
from app.modules.matching.models import MatchResultRow
from tests.unit.matching_api.conftest import (
    InMemoryExplanationsRepository,
    InMemoryMatchingRepository,
    make_validated_profile,
)
from tests.unit.profiles.conftest import InMemoryProfilesRepository


def _seed(
    profiles: InMemoryProfilesRepository,
    matching: InMemoryMatchingRepository,
    explanations: InMemoryExplanationsRepository,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    profile = profiles.add(make_validated_profile(user_id))
    matching.results[(profile.id, job_id)] = MatchResultRow(
        profile_id=profile.id,
        job_posting_id=job_id,
        scoring_version="1.0.0",
        score=72,
        confidence=64,
        low_data=False,
        blocking_criteria=[],
        unknown_dimensions=[],
        dimension_scores={"_meta": {"profile_version": 3, "explanation_facts": {}},
                          "items": []},
        computed_at=datetime.now(UTC),
    )
    explanations.rows[(profile.id, job_id, "1.0.0", "match_explanation/1.0.0")] = {
        "summary": "Résumé.",
        "strengths": [],
        "gaps": [],
        "uncertainties": [],
        "blocking_notes": [],
    }


class TestMatchingPurge:
    async def test_purge_user_removes_only_that_users_results(
        self,
        profiles_repository: InMemoryProfilesRepository,
        matching_repository: InMemoryMatchingRepository,
        explanations_repository: InMemoryExplanationsRepository,
    ) -> None:
        user, other = uuid.uuid4(), uuid.uuid4()
        _seed(profiles_repository, matching_repository, explanations_repository,
              user, uuid.uuid4())
        _seed(profiles_repository, matching_repository, explanations_repository,
              other, uuid.uuid4())

        await matching_purge.purge_user(user, repository=matching_repository)

        assert await matching_repository.list_results_for_user(user) == []
        assert len(await matching_repository.list_results_for_user(other)) == 1
        # Cascade : les explications de l'utilisateur purgé partent aussi.
        assert await explanations_repository.list_for_user(user) == []
        assert len(await explanations_repository.list_for_user(other)) == 1

    async def test_export_user_returns_match_results(
        self,
        profiles_repository: InMemoryProfilesRepository,
        matching_repository: InMemoryMatchingRepository,
        explanations_repository: InMemoryExplanationsRepository,
    ) -> None:
        user = uuid.uuid4()
        job_id = uuid.uuid4()
        _seed(profiles_repository, matching_repository, explanations_repository,
              user, job_id)

        export = await matching_purge.export_user(user, repository=matching_repository)
        (entry,) = export["match_results"]
        assert entry["job_posting_id"] == str(job_id)
        assert entry["score"] == 72
        assert entry["scoring_version"] == "1.0.0"

    async def test_export_user_without_data_is_empty(
        self, matching_repository: InMemoryMatchingRepository
    ) -> None:
        assert await matching_purge.export_user(
            uuid.uuid4(), repository=matching_repository
        ) == {}


class TestExplanationsPurge:
    async def test_purge_user_removes_only_that_users_explanations(
        self,
        profiles_repository: InMemoryProfilesRepository,
        matching_repository: InMemoryMatchingRepository,
        explanations_repository: InMemoryExplanationsRepository,
    ) -> None:
        user, other = uuid.uuid4(), uuid.uuid4()
        _seed(profiles_repository, matching_repository, explanations_repository,
              user, uuid.uuid4())
        _seed(profiles_repository, matching_repository, explanations_repository,
              other, uuid.uuid4())

        await explanations_purge.purge_user(user, repository=explanations_repository)

        assert await explanations_repository.list_for_user(user) == []
        assert len(await explanations_repository.list_for_user(other)) == 1

    async def test_export_user_returns_explanations(
        self,
        profiles_repository: InMemoryProfilesRepository,
        matching_repository: InMemoryMatchingRepository,
        explanations_repository: InMemoryExplanationsRepository,
    ) -> None:
        user = uuid.uuid4()
        job_id = uuid.uuid4()
        _seed(profiles_repository, matching_repository, explanations_repository,
              user, job_id)

        export = await explanations_purge.export_user(
            user, repository=explanations_repository
        )
        (entry,) = export["match_explanations"]
        assert entry["job_posting_id"] == str(job_id)
        assert entry["prompt_version"] == "match_explanation/1.0.0"
        assert entry["content"]["summary"] == "Résumé."

    async def test_export_user_without_data_is_empty(
        self, explanations_repository: InMemoryExplanationsRepository
    ) -> None:
        assert await explanations_purge.export_user(
            uuid.uuid4(), repository=explanations_repository
        ) == {}

"""Tests API du module explanations (D14 — reformulation contrôlée, cache)."""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeProvider
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.matching_api.conftest import (
    InMemoryExplanationsRepository,
    InMemoryMatchingRepository,
    make_job,
)
from tests.unit.matching_api.test_matching_api import (
    csrf_headers,
    current_user_id,
    default_job_kwargs,
    register,
    setup_validated_user,
)
from tests.unit.preferences.conftest import InMemoryPreferencesRepository
from tests.unit.profiles.conftest import InMemoryProfilesRepository, make_profile


def explanation_url(job_id: uuid.UUID) -> str:
    return f"/api/v1/jobs/{job_id}/explanation"


class TestAuthAndCsrf:
    def test_without_session_csrf_middleware_answers_403(
        self, client: TestClient
    ) -> None:
        # Mutation sans session ni cookie : le middleware CSRF répond avant
        # l'authentification (403 problem+json) — même ordre que les autres
        # mutations de l'API.
        response = client.post(explanation_url(uuid.uuid4()))
        assert response.status_code == 403
        assert response.json()["type"].endswith("/csrf_invalid")

    def test_with_session_but_no_csrf_header_is_403(
        self,
        client: TestClient,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        register(client)
        job = matching_repository.add(make_job(**default_job_kwargs()))
        response = client.post(explanation_url(job.id))
        assert response.status_code == 403
        assert response.json()["type"].endswith("/csrf_invalid")


class TestGenerate:
    def test_draft_profile_is_409_profile_not_validated(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        register(client)
        profiles_repository.add(make_profile(current_user_id(auth_repository), status="draft"))
        job = matching_repository.add(make_job(**default_job_kwargs()))

        response = client.post(explanation_url(job.id), headers=csrf_headers(client))
        assert response.status_code == 409
        assert response.json()["type"].endswith("/profile_not_validated")

    def test_unknown_job_is_404(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        response = client.post(explanation_url(uuid.uuid4()), headers=csrf_headers(client))
        assert response.status_code == 404

    def test_facts_to_validated_fake_output(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        llm_provider: FakeProvider,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))

        response = client.post(explanation_url(job.id), headers=csrf_headers(client))
        assert response.status_code == 200
        body = response.json()
        assert body["prompt_version"] == "match_explanation/1.0.0"
        assert isinstance(body["summary"], str) and body["summary"]
        for key in ("strengths", "gaps", "uncertainties", "blocking_notes"):
            assert isinstance(body[key], list)
        # D14 : le prompt contient les facts du moteur, jamais l'offre brute.
        ((task, prompt),) = llm_provider.calls
        assert task == "match_explanation"
        assert "FAITS" in prompt
        assert job.description_text not in prompt

    def test_numbers_present_in_facts_are_allowed(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        canned_explanation: dict[str, Any],
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        # Profil : 5 ans d'expérience ; offre : fourchette 2-8 ans → ces
        # nombres figurent dans les facts (dimension experience_years).
        job = matching_repository.add(make_job(**default_job_kwargs()))
        canned_explanation.update(
            {
                "summary": "Vos 5 ans d'expérience sont dans la fourchette "
                "demandée (2 à 8 ans).",
                "strengths": ["Expérience dans la fourchette de l'offre."],
            }
        )

        response = client.post(explanation_url(job.id), headers=csrf_headers(client))
        assert response.status_code == 200
        assert "5 ans" in response.json()["summary"]

    def test_foreign_number_in_output_is_502(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        explanations_repository: InMemoryExplanationsRepository,
        canned_explanation: dict[str, Any],
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))
        # 87 ne figure dans aucun fact → divergence potentielle → échec propre.
        canned_explanation["summary"] = "Compatibilité estimée à 87 pour cent."

        response = client.post(explanation_url(job.id), headers=csrf_headers(client))
        assert response.status_code == 502
        assert response.json()["type"].endswith("/explanation_generation_failed")
        assert explanations_repository.rows == {}  # rien n'est mis en cache

    def test_invalid_output_after_retry_is_502(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        canned_explanation: dict[str, Any],
        llm_provider: FakeProvider,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))
        canned_explanation.clear()
        canned_explanation.update({"resume": "clé inconnue — schéma violé"})

        response = client.post(explanation_url(job.id), headers=csrf_headers(client))
        assert response.status_code == 502
        assert response.json()["type"].endswith("/explanation_generation_failed")
        assert len(llm_provider.calls) == 2  # 1 retry avec le message d'erreur (D08)

    def test_second_call_hits_cache_provider_called_once(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        llm_provider: FakeProvider,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))

        first = client.post(explanation_url(job.id), headers=csrf_headers(client))
        second = client.post(explanation_url(job.id), headers=csrf_headers(client))
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        assert len(llm_provider.calls) == 1  # cache par (profil, offre, versions)

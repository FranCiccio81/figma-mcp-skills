"""Tests API du module generation : préconditions, idempotence, quotas, liste."""

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.generation.conftest import (
    GENERATIONS_URL,
    InMemoryGenerationRepository,
    post_generation,
    setup_validated_user,
)
from tests.unit.jobs.conftest import make_posting
from tests.unit.profiles.conftest import InMemoryProfilesRepository


class TestAuthRequired:
    def test_list_without_session_is_401_problem(self, client: TestClient) -> None:
        response = client.get(GENERATIONS_URL)
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")

    def test_get_without_session_is_401(self, client: TestClient) -> None:
        assert client.get(f"{GENERATIONS_URL}/{uuid.uuid4()}").status_code == 401


class TestPreconditions:
    def test_missing_idempotency_key_is_422(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        response = post_generation(client, job_id=job.id, key=None)
        assert response.status_code == 422
        body = response.json()
        assert body["type"].endswith("validation_error")
        assert body["errors"][0]["field"] == "Idempotency-Key"

    def test_non_uuid_idempotency_key_is_422(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        response = post_generation(client, job_id=job.id, key="pas-un-uuid")
        assert response.status_code == 422

    def test_profile_not_validated_is_409(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository, status="draft")
        job = generation_repository.add_job(make_posting())
        response = post_generation(client, job_id=job.id)
        assert response.status_code == 409
        assert response.json()["type"].endswith("profile_not_validated")
        assert generation_repository.docs == {}

    def test_missing_job_id_is_422_except_cv_optimization(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        response = post_generation(client, doc_type="cover_letter")
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "job_id"

    def test_cv_optimization_needs_no_job(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        enqueued: list[uuid.UUID],
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        response = post_generation(client, doc_type="cv_optimization")
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert body["content"] is None
        assert enqueued == [uuid.UUID(body["id"])]

    def test_unknown_job_is_404(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        assert post_generation(client, job_id=uuid.uuid4()).status_code == 404

    def test_withdrawn_job_is_404(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting(status="withdrawn"))
        assert post_generation(client, job_id=job.id).status_code == 404

    def test_expired_job_is_409_job_expired(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting(status="expired"))
        response = post_generation(client, job_id=job.id)
        assert response.status_code == 409
        assert response.json()["type"].endswith("job_expired")
        assert generation_repository.docs == {}

    def test_long_expired_job_is_404(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        setup_validated_user(client, auth_repository, profiles_repository)
        stale = datetime.now(UTC) - timedelta(days=400)
        job = generation_repository.add_job(
            make_posting(status="expired", expires_at=stale, last_seen_at=stale)
        )
        assert post_generation(client, job_id=job.id).status_code == 404

    def test_202_document_fields(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        response = post_generation(client, doc_type="cover_letter", job_id=job.id)
        assert response.status_code == 202
        body = response.json()
        assert body["doc_type"] == "cover_letter"
        assert body["based_on_profile_version"] == profile.version
        assert body["prompt_version"] == "generate_letter/1.0.0"
        assert body["job_id"] == str(job.id)
        assert body["anchoring_check"] is None


class TestIdempotency:
    def test_replay_returns_original_response_with_header(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        enqueued: list[uuid.UUID],
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        key = uuid.uuid4()

        first = post_generation(client, job_id=job.id, key=key)
        assert first.status_code == 202
        assert "Idempotent-Replay" not in first.headers

        second = post_generation(client, job_id=job.id, key=key)
        assert second.status_code == 202
        assert second.headers["Idempotent-Replay"] == "true"
        assert second.json() == first.json()
        # Aucune double génération : un seul document, une seule tâche.
        assert len(generation_repository.docs) == 1
        assert len(enqueued) == 1

    def test_replay_does_not_consume_quota(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import app.modules.generation.service as service_module

        monkeypatch.setattr(service_module, "QUOTA_PER_HOUR", 1)
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        key = uuid.uuid4()
        assert post_generation(client, job_id=job.id, key=key).status_code == 202
        # Le rejeu passe malgré le quota épuisé — réponse d'origine.
        replay = post_generation(client, job_id=job.id, key=key)
        assert replay.status_code == 202
        assert replay.headers["Idempotent-Replay"] == "true"
        # Une nouvelle clé, elle, est refusée.
        assert post_generation(client, job_id=job.id).status_code == 429


class TestQuotas:
    def test_11th_generation_in_hour_is_429(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        for _ in range(10):
            assert post_generation(client, job_id=job.id).status_code == 202
        response = post_generation(client, job_id=job.id)
        assert response.status_code == 429
        assert response.json()["type"].endswith("rate_limited")
        assert "Retry-After" in response.headers
        # AC-L-3 : aucune tâche créée au-delà du quota.
        assert len(generation_repository.docs) == 10

    def test_daily_quota_is_429(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import app.modules.generation.service as service_module

        monkeypatch.setattr(service_module, "QUOTA_PER_DAY", 2)
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        assert post_generation(client, job_id=job.id).status_code == 202
        assert post_generation(client, job_id=job.id).status_code == 202
        response = post_generation(client, job_id=job.id)
        assert response.status_code == 429
        assert "Retry-After" in response.headers


class TestReadScoping:
    def test_unknown_document_is_404(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        assert client.get(f"{GENERATIONS_URL}/{uuid.uuid4()}").status_code == 404

    def test_other_users_document_is_404(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        response = post_generation(client, job_id=job.id)
        document_id = response.json()["id"]
        # Le document appartient désormais à un AUTRE utilisateur.
        generation_repository.docs[uuid.UUID(document_id)].user_id = uuid.uuid4()
        assert client.get(f"{GENERATIONS_URL}/{document_id}").status_code == 404


class TestList:
    def _create_documents(
        self,
        client: TestClient,
        generation_repository: InMemoryGenerationRepository,
    ) -> tuple[uuid.UUID, list[str]]:
        job = generation_repository.add_job(make_posting())
        ids = [
            post_generation(client, doc_type="email", job_id=job.id).json()["id"],
            post_generation(client, doc_type="cover_letter", job_id=job.id).json()["id"],
            post_generation(client, doc_type="cv_optimization").json()["id"],
        ]
        return job.id, ids

    def test_list_orders_by_creation_desc(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        _, ids = self._create_documents(client, generation_repository)
        body = client.get(GENERATIONS_URL).json()
        assert [item["id"] for item in body["items"]] == list(reversed(ids))
        assert body["next_cursor"] is None

    def test_filters(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job_id, ids = self._create_documents(client, generation_repository)

        by_type = client.get(GENERATIONS_URL, params={"doc_type": "email"}).json()
        assert [item["id"] for item in by_type["items"]] == [ids[0]]

        by_job = client.get(GENERATIONS_URL, params={"job_id": str(job_id)}).json()
        assert {item["id"] for item in by_job["items"]} == {ids[0], ids[1]}

        pending = client.get(GENERATIONS_URL, params={"status": "pending"}).json()
        assert len(pending["items"]) == 3
        drafts = client.get(GENERATIONS_URL, params={"status": "draft"}).json()
        assert drafts["items"] == []

    def test_cursor_pagination(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        _, ids = self._create_documents(client, generation_repository)

        seen: list[str] = []
        cursor: str | None = None
        for _ in range(4):  # borne de sécurité
            params: dict[str, str] = {"limit": "1"}
            if cursor is not None:
                params["cursor"] = cursor
            page = client.get(GENERATIONS_URL, params=params).json()
            seen += [item["id"] for item in page["items"]]
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert seen == list(reversed(ids))

    def test_invalid_cursor_is_422(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        response = client.get(GENERATIONS_URL, params={"cursor": "n'importe quoi"})
        assert response.status_code == 422
        assert response.json()["type"].endswith("invalid_cursor")


class TestWorkerRegistration:
    def test_task_is_registered_on_ai_queue_name(self) -> None:
        from app.workers.celery_app import celery_app
        from app.workers.generation_tasks import generate

        assert generate.name == "ai.generate"
        # Le routage par préfixe « ai.* » envoie la tâche sur la file ``ai``.
        assert celery_app.conf.task_routes["ai.*"] == {"queue": "ai"}

"""Tests du cycle de statuts : pending → draft → validated → exported (D10)."""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeProvider
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.generation.conftest import (
    GENERATIONS_URL,
    InMemoryGenerationRepository,
    csrf_headers,
    post_generation,
    run_generation,
    setup_validated_user,
)
from tests.unit.jobs.conftest import make_posting
from tests.unit.profiles.conftest import InMemoryProfilesRepository


def create_draft_email(
    client: TestClient,
    generation_repository: InMemoryGenerationRepository,
    profiles_repository: InMemoryProfilesRepository,
    llm_provider: FakeProvider,
) -> str:
    """POST + exécution worker → document en draft ; retourne son id."""
    job = generation_repository.add_job(make_posting())
    response = post_generation(client, doc_type="email", job_id=job.id)
    assert response.status_code == 202
    document_id = response.json()["id"]
    report = run_generation(
        uuid.UUID(document_id), generation_repository, profiles_repository, llm_provider
    )
    assert report["status"] == "draft"
    return document_id


class TestWorkerTransition:
    def test_pending_then_draft_with_content(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        response = post_generation(client, doc_type="email", job_id=job.id)
        document_id = response.json()["id"]
        assert response.json()["status"] == "pending"

        run_generation(
            uuid.UUID(document_id), generation_repository, profiles_repository, llm_provider
        )
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert body["status"] == "draft"
        assert body["content"]["subject"]
        assert body["anchoring_check"] == {"status": "passed", "unanchored_claims": []}

    def test_redelivery_is_idempotent(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        document_id = uuid.UUID(
            create_draft_email(
                client, generation_repository, profiles_repository, llm_provider
            )
        )
        calls_before = len(llm_provider.calls)
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        # acks_late (D16) : une re-livraison ne regénère pas le contenu.
        assert report == {"status": "skipped"}
        assert len(llm_provider.calls) == calls_before

    def test_provider_failure_marks_document_failed(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        document_id = post_generation(client, doc_type="email", job_id=job.id).json()["id"]
        # Provider sans sortie canned pour generate_email → échec propre.
        broken = FakeProvider(canned={})
        report = run_generation(
            uuid.UUID(document_id), generation_repository, profiles_repository, broken
        )
        assert report["status"] == "failed"
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert body["status"] == "failed"
        assert body["error_code"] == "provider_error"
        assert body["content"] is None


class TestLifecycle:
    def test_patch_and_validate_refused_while_pending(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        job = generation_repository.add_job(make_posting())
        document_id = post_generation(client, doc_type="email", job_id=job.id).json()["id"]
        patch = client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": {"body": "..."}},
            headers=csrf_headers(client),
        )
        assert patch.status_code == 409
        assert patch.json()["type"].endswith("generation_not_editable")
        validate = client.post(
            f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client)
        )
        assert validate.status_code == 409

    def test_export_without_validation_is_409(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        document_id = create_draft_email(
            client, generation_repository, profiles_repository, llm_provider
        )
        response = client.post(
            f"{GENERATIONS_URL}/{document_id}/export",
            json={"format": "text"},
            headers=csrf_headers(client),
        )
        # AC-L-1 : export refusé tant que la validation humaine manque.
        assert response.status_code == 409
        assert response.json()["type"].endswith("generation_not_validated")
        document = generation_repository.docs[uuid.UUID(document_id)]
        assert document.status == "draft"

    def test_validate_then_export_text(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {
            "subject": "Candidature développeuse backend",
            "body": "Bonjour, je vous adresse ma candidature.",
            "claims": [],
        }
        document_id = create_draft_email(
            client, generation_repository, profiles_repository, llm_provider
        )
        validated = client.post(
            f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client)
        )
        assert validated.status_code == 200
        assert validated.json()["status"] == "validated"
        assert validated.json()["validated_at"] is not None

        exported = client.post(
            f"{GENERATIONS_URL}/{document_id}/export",
            json={"format": "text"},
            headers=csrf_headers(client),
        )
        assert exported.status_code == 200
        body = exported.json()
        assert body["format"] == "text"
        assert body["download_url"] is None
        assert "Objet : Candidature développeuse backend" in body["content"]
        assert "je vous adresse ma candidature" in body["content"]
        assert client.get(f"{GENERATIONS_URL}/{document_id}").json()["status"] == "exported"

    def test_patch_on_validated_is_409(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        document_id = create_draft_email(
            client, generation_repository, profiles_repository, llm_provider
        )
        assert (
            client.post(
                f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client)
            ).status_code
            == 200
        )
        response = client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": {"body": "réécrit"}},
            headers=csrf_headers(client),
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("generation_not_editable")

    def test_export_pdf_and_docx_are_501_until_m5(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        document_id = create_draft_email(
            client, generation_repository, profiles_repository, llm_provider
        )
        client.post(f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client))
        for export_format in ("pdf", "docx"):
            response = client.post(
                f"{GENERATIONS_URL}/{document_id}/export",
                json={"format": export_format},
                headers=csrf_headers(client),
            )
            assert response.status_code == 501
            assert response.json()["type"].endswith("not_implemented")
        # Le 501 n'a pas altéré le statut : l'export texte reste possible.
        assert client.get(f"{GENERATIONS_URL}/{document_id}").json()["status"] == "validated"

    def test_check_exported_requires_validated_at(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        """Vérification applicative du CHECK SQL « exported ⇒ validated_at »."""
        setup_validated_user(client, auth_repository, profiles_repository)
        document_id = create_draft_email(
            client, generation_repository, profiles_repository, llm_provider
        )
        client.post(f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client))
        document = generation_repository.docs[uuid.UUID(document_id)]
        document.validated_at = None  # incohérence simulée
        response = client.post(
            f"{GENERATIONS_URL}/{document_id}/export",
            json={"format": "text"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("generation_not_validated")
        assert document.status != "exported"

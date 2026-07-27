"""Tests des interfaces purge/export RGPD du module generation (D21)."""

import uuid

from fastapi.testclient import TestClient

from app.modules.generation.purge import export_user, purge_user
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.generation.conftest import (
    InMemoryGenerationRepository,
    post_generation,
    setup_validated_user,
)
from tests.unit.jobs.conftest import make_posting
from tests.unit.profiles.conftest import InMemoryProfilesRepository


async def test_purge_user_removes_only_the_users_documents(
    client: TestClient,
    auth_repository: InMemoryAuthRepository,
    profiles_repository: InMemoryProfilesRepository,
    generation_repository: InMemoryGenerationRepository,
) -> None:
    user_id, _ = setup_validated_user(client, auth_repository, profiles_repository)
    job = generation_repository.add_job(make_posting())
    post_generation(client, job_id=job.id)
    post_generation(client, doc_type="cv_optimization")
    # Document d'un autre utilisateur : il doit survivre à la purge.
    other_id = uuid.uuid4()
    (first_doc, *_) = generation_repository.docs.values()
    other_doc_id = uuid.uuid4()
    clone = type(first_doc)(
        id=other_doc_id,
        user_id=other_id,
        application_id=None,
        job_posting_id=None,
        doc_type="cv_optimization",
        status="draft",
        content={},
        based_on_profile_version=1,
        prompt_version="optimize_cv/1.0.0",
        created_at=first_doc.created_at,
        validated_at=None,
        processing_status="pending",
        error_code=None,
        anchoring_check=None,
        manually_edited=False,
        options={},
    )
    generation_repository.docs[other_doc_id] = clone

    await purge_user(user_id, generation_repository)
    remaining = list(generation_repository.docs.values())
    assert len(remaining) == 1
    assert remaining[0].user_id == other_id


async def test_export_user_returns_documents_payload(
    client: TestClient,
    auth_repository: InMemoryAuthRepository,
    profiles_repository: InMemoryProfilesRepository,
    generation_repository: InMemoryGenerationRepository,
) -> None:
    user_id, _ = setup_validated_user(client, auth_repository, profiles_repository)
    job = generation_repository.add_job(make_posting())
    document_id = post_generation(client, job_id=job.id).json()["id"]

    payload = await export_user(user_id, generation_repository)
    documents = payload["generated_documents"]
    assert [d["id"] for d in documents] == [document_id]
    assert documents[0]["doc_type"] == "email"
    assert documents[0]["status"] == "pending"
    assert documents[0]["prompt_version"] == "generate_email/1.0.0"
    assert documents[0]["job_posting_id"] == str(job.id)


async def test_export_user_without_documents_is_empty(
    generation_repository: InMemoryGenerationRepository,
) -> None:
    assert await export_user(uuid.uuid4(), generation_repository) == {}

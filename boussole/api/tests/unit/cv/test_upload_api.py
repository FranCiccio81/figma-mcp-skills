"""Tests API de POST /cv-documents et GET /cv-documents/{id} (F-B).

Validation par MAGIC BYTES réels (jamais le Content-Type déclaré), taille
≤ 10 Mo, quota 5/jour, cycle de statuts uploaded → parsing → parsed/failed,
proposition avec provenance ``cv_extraction`` (RM-B-1).
"""

import json
import uuid

from fastapi.testclient import TestClient

from app.modules.profiles.cv.models import CvDocument, ExtractionRun
from app.modules.profiles.cv.service import DOCX_MIME, MAX_UPLOAD_BYTES, PDF_MIME
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.cv.conftest import (
    InMemoryCvRepository,
    InMemoryObjectStorage,
    make_docx_bytes,
    make_pdf_bytes,
    make_plain_zip_bytes,
)

CV_URL = "/api/v1/cv-documents"


def register(client: TestClient, email: str = "camille@example.eu") -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "un mot de passe très long",
            "locale": "fr",
            "accepted_terms_version": "2026-07",
            "accepted_privacy_version": "2026-07",
        },
    )
    assert response.status_code == 201


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["boussole_csrf"]}


def upload(
    client: TestClient,
    data: bytes,
    *,
    filename: str = "cv.pdf",
    content_type: str = "application/pdf",
):
    return client.post(
        CV_URL,
        files={"file": (filename, data, content_type)},
        headers=csrf_headers(client),
    )


def current_user_id(auth_repository: InMemoryAuthRepository) -> uuid.UUID:
    (user_id,) = auth_repository.users_by_id
    return user_id


class TestUpload:
    def test_pdf_upload_returns_202_stores_and_enqueues(
        self,
        client: TestClient,
        cv_repository: InMemoryCvRepository,
        storage: InMemoryObjectStorage,
        enqueued: list[uuid.UUID],
    ) -> None:
        register(client)
        data = make_pdf_bytes()
        response = upload(client, data, filename="mon-cv.pdf")
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "uploaded"
        assert body["error_code"] is None
        assert body["filename"] == "mon-cv.pdf"
        assert body["proposal"] is None

        document_id = uuid.UUID(body["id"])
        document = cv_repository.documents[document_id]
        assert document.mime_type == PDF_MIME
        assert document.size_bytes == len(data)
        assert storage.objects[document.file_key] == data
        assert enqueued == [document_id]

    def test_docx_upload_detected_by_magic_bytes(
        self, client: TestClient, cv_repository: InMemoryCvRepository
    ) -> None:
        register(client)
        # Content-Type déclaré MENSONGER : seul le contenu réel compte.
        response = upload(
            client, make_docx_bytes(), filename="cv.docx", content_type="text/plain"
        )
        assert response.status_code == 202
        document = cv_repository.documents[uuid.UUID(response.json()["id"])]
        assert document.mime_type == DOCX_MIME

    def test_wrong_content_is_415_even_with_pdf_content_type(
        self,
        client: TestClient,
        storage: InMemoryObjectStorage,
        enqueued: list[uuid.UUID],
    ) -> None:
        register(client)
        response = upload(client, b"GIF89a fake image", content_type="application/pdf")
        assert response.status_code == 415
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["type"].endswith("/unsupported_format")
        assert storage.objects == {}  # rejet AVANT stockage (F-B alt. 3)
        assert enqueued == []

    def test_plain_zip_is_not_a_docx(self, client: TestClient) -> None:
        register(client)
        response = upload(client, make_plain_zip_bytes(), filename="cv.docx")
        assert response.status_code == 415
        assert response.json()["type"].endswith("/unsupported_format")

    def test_oversize_is_413_nothing_stored(
        self,
        client: TestClient,
        storage: InMemoryObjectStorage,
        enqueued: list[uuid.UUID],
    ) -> None:
        register(client)
        data = b"%PDF-" + b"0" * MAX_UPLOAD_BYTES  # > 10 Mo
        response = upload(client, data)
        assert response.status_code == 413
        assert response.json()["type"].endswith("/too_large")
        assert storage.objects == {}
        assert enqueued == []

    def test_quota_5_per_day_then_429_with_retry_after(
        self, client: TestClient, storage: InMemoryObjectStorage
    ) -> None:
        register(client)
        data = make_pdf_bytes()
        for _ in range(5):
            assert upload(client, data).status_code == 202
        response = upload(client, data)  # 6e upload du jour (AC-B-4)
        assert response.status_code == 429
        assert response.json()["type"].endswith("/rate_limited")
        assert int(response.headers["Retry-After"]) >= 1
        assert len(storage.objects) == 5  # aucun fichier stocké pour le 6e

    def test_invalid_file_does_not_consume_quota(self, client: TestClient) -> None:
        register(client)
        for _ in range(5):
            assert upload(client, b"pas un pdf").status_code == 415
        # 🟡 ordre de validation : magic bytes AVANT quota.
        assert upload(client, make_pdf_bytes()).status_code == 202

    def test_upload_requires_session_and_csrf(self, client: TestClient) -> None:
        # Sans session ni CSRF : le middleware CSRF répond d'abord (403).
        assert client.post(CV_URL).status_code == 403


class TestGetCvDocument:
    def _uploaded_document(
        self, client: TestClient, cv_repository: InMemoryCvRepository
    ) -> CvDocument:
        response = upload(client, make_pdf_bytes())
        assert response.status_code == 202
        return cv_repository.documents[uuid.UUID(response.json()["id"])]

    def test_unknown_id_is_404(self, client: TestClient) -> None:
        register(client)
        response = client.get(f"{CV_URL}/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_other_users_document_is_404_anti_enumeration(
        self, client: TestClient, cv_repository: InMemoryCvRepository
    ) -> None:
        register(client)
        foreign = CvDocument(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),  # un AUTRE utilisateur
            file_key="cv/other/doc/original.pdf",
            filename="autre.pdf",
            mime_type=PDF_MIME,
            size_bytes=10,
            status="parsed",
        )
        cv_repository.documents[foreign.id] = foreign
        assert client.get(f"{CV_URL}/{foreign.id}").status_code == 404

    def test_status_cycle_uploaded_then_parsing(
        self, client: TestClient, cv_repository: InMemoryCvRepository
    ) -> None:
        register(client)
        document = self._uploaded_document(client, cv_repository)
        assert client.get(f"{CV_URL}/{document.id}").json()["status"] == "uploaded"
        document.status = "parsing"  # le worker a pris la tâche
        assert client.get(f"{CV_URL}/{document.id}").json()["status"] == "parsing"

    def test_failed_document_exposes_error_code(
        self, client: TestClient, cv_repository: InMemoryCvRepository
    ) -> None:
        register(client)
        document = self._uploaded_document(client, cv_repository)
        document.status = "failed"
        document.error_code = "image_only_pdf"
        body = client.get(f"{CV_URL}/{document.id}").json()
        assert body["status"] == "failed"
        assert body["error_code"] == "image_only_pdf"
        assert body["proposal"] is None

    def test_parsed_document_returns_proposal_with_provenance(
        self,
        client: TestClient,
        cv_repository: InMemoryCvRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        register(client)
        document = self._uploaded_document(client, cv_repository)
        extraction = {
            "headline": "Développeuse backend",
            "summary": None,
            "experiences": [
                {
                    "title": "Développeuse Python",
                    "company": "Acme",
                    "start_date": "2020-03",
                    "end_date": None,
                    "description": None,
                    "confidence": 0.9,
                    "evidence": {"quote": "Développeuse Python chez Acme"},
                }
            ],
            "educations": [],
            "skills": [
                {
                    "label": "Python",
                    "confidence": 0.8,
                    "evidence": {"quote": "Python"},
                }
            ],
            "languages": [
                {"lang_code": "en", "level": "B2", "confidence": 0.6, "evidence": None}
            ],
            "warnings": ["Section « loisirs » ignorée"],
        }
        output_key = f"cv/{document.user_id}/{document.id}/extraction/run.json"
        storage.put(output_key, json.dumps(extraction).encode())
        cv_repository.runs.append(
            ExtractionRun(
                id=uuid.uuid4(),
                cv_document_id=document.id,
                prompt_version="extract_cv/1.0.0",
                model="claude-sonnet-5",
                status="success",
                output_key=output_key,
            )
        )
        document.status = "parsed"

        body = client.get(f"{CV_URL}/{document.id}").json()
        assert body["status"] == "parsed"
        assert body["extraction_warnings"] == ["Section « loisirs » ignorée"]
        proposal = body["proposal"]
        assert proposal["headline"] == "Développeuse backend"
        # Date partielle YYYY-MM → 1er du mois 🟡.
        exp = proposal["experiences"][0]
        assert exp["start_date"] == "2020-03-01"
        assert exp["provenance"] == {"source": "cv_extraction", "confidence": 0.9}
        # item_id déterministe + evidence exposée (revue par item, 04 Flux 1 §5).
        assert exp["item_id"] == "experience:0"
        assert exp["evidence_quote"] == "Développeuse Python chez Acme"
        assert proposal["skills"][0]["provenance"]["source"] == "cv_extraction"
        assert proposal["skills"][0]["item_id"] == "skill:0"
        assert proposal["skills"][0]["evidence_quote"] == "Python"
        assert proposal["languages"][0] == {
            "item_id": "language:0",
            "lang_code": "en",
            "level": "B2",
            "evidence_quote": None,  # langue sans evidence (schéma) → None
            "provenance": {"source": "cv_extraction", "confidence": 0.6},
        }

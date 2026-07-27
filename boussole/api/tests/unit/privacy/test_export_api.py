"""Tests API de l'export RGPD (F-Q) : 202, idempotence, quota, lien signé."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.modules.privacy.signing import make_download_url
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.privacy.conftest import (
    FakeStorage,
    InMemoryPrivacyRepository,
    csrf_headers,
    make_export_record,
    register,
)


def request_export(client: TestClient, **headers: str) -> object:
    return client.post(
        "/api/v1/privacy/export", headers={**csrf_headers(client), **headers}
    )


class TestRequestExport:
    def test_202_pending_et_tache_enfilee(
        self,
        client: TestClient,
        privacy_repository: InMemoryPrivacyRepository,
        enqueued_exports: list[uuid.UUID],
    ) -> None:
        register(client)
        response = request_export(client)
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        export_id = uuid.UUID(body["id"])
        assert export_id in privacy_repository.exports
        assert enqueued_exports == [export_id]
        # Audit : demande journalisée.
        actions = [entry["action"] for entry in privacy_repository.audit_entries]
        assert "privacy_export_requested" in actions

    def test_idempotency_key_rejoue_sans_consommer_le_quota(
        self,
        client: TestClient,
        privacy_repository: InMemoryPrivacyRepository,
        enqueued_exports: list[uuid.UUID],
    ) -> None:
        register(client)
        key = str(uuid.uuid4())
        first = request_export(client, **{"Idempotency-Key": key})
        replay_1 = request_export(client, **{"Idempotency-Key": key})
        replay_2 = request_export(client, **{"Idempotency-Key": key})

        assert first.status_code == replay_1.status_code == replay_2.status_code == 202
        assert first.json()["id"] == replay_1.json()["id"] == replay_2.json()["id"]
        # Une seule demande créée, une seule tâche enfilée.
        assert len(privacy_repository.exports) == 1
        assert len(enqueued_exports) == 1
        # Les rejeux n'ont pas consommé le quota : un 2e export réel passe.
        assert request_export(client).status_code == 202
        # …et c'est bien le 3e export RÉEL qui est refusé.
        assert request_export(client).status_code == 429

    def test_quota_2_par_jour_429_avec_retry_after(self, client: TestClient) -> None:
        register(client)
        assert request_export(client).status_code == 202
        assert request_export(client).status_code == 202
        third = request_export(client)
        assert third.status_code == 429
        assert third.headers["content-type"].startswith("application/problem+json")
        assert third.json()["type"].endswith("/rate_limited")
        assert int(third.headers["Retry-After"]) >= 1

    def test_sans_session_401(self, client: TestClient) -> None:
        # CSRF satisfait (double-submit posé à la main) mais aucune session.
        client.cookies.set("boussole_csrf", "jeton-csrf")
        response = client.post(
            "/api/v1/privacy/export", headers={"X-CSRF-Token": "jeton-csrf"}
        )
        assert response.status_code == 401

    def test_sans_jeton_csrf_403(self, client: TestClient) -> None:
        register(client)
        response = client.post("/api/v1/privacy/export")
        assert response.status_code == 403
        assert response.json()["type"].endswith("/csrf_invalid")


class TestExportStatus:
    def test_pending_sans_download_url(
        self, client: TestClient, privacy_repository: InMemoryPrivacyRepository
    ) -> None:
        register(client)
        export_id = request_export(client).json()["id"]
        body = client.get(f"/api/v1/privacy/exports/{export_id}").json()
        assert body["status"] == "pending"
        assert body["download_url"] is None

    def test_ready_fournit_un_lien_signe(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        privacy_repository: InMemoryPrivacyRepository,
        fake_storage: FakeStorage,
    ) -> None:
        register(client)
        user_id = next(iter(auth_repository.users_by_id))
        record = make_export_record(
            user_id,
            status="ready",
            file_key="privacy-exports/archive.json",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        privacy_repository.exports[record.id] = record
        fake_storage.objects["privacy-exports/archive.json"] = b'{"modules": {}}'

        body = client.get(f"/api/v1/privacy/exports/{record.id}").json()
        assert body["status"] == "ready"
        assert body["download_url"] is not None
        assert "sig=" in body["download_url"]

        download = client.get(body["download_url"])
        assert download.status_code == 200
        assert download.content == b'{"modules": {}}'
        assert "attachment" in download.headers["content-disposition"]

    def test_signature_falsifiee_404(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        privacy_repository: InMemoryPrivacyRepository,
        fake_storage: FakeStorage,
    ) -> None:
        register(client)
        user_id = next(iter(auth_repository.users_by_id))
        record = make_export_record(
            user_id,
            status="ready",
            file_key="k",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        privacy_repository.exports[record.id] = record
        fake_storage.objects["k"] = b"{}"
        url = client.get(f"/api/v1/privacy/exports/{record.id}").json()["download_url"]
        tampered = url.replace("sig=", "sig=0000")
        assert client.get(tampered).status_code == 404

    def test_lien_expire_statut_expired_et_download_410(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        privacy_repository: InMemoryPrivacyRepository,
    ) -> None:
        register(client)
        user_id = next(iter(auth_repository.users_by_id))
        expired_at = datetime.now(UTC) - timedelta(days=1)
        record = make_export_record(
            user_id, status="ready", file_key="k", expires_at=expired_at
        )
        privacy_repository.exports[record.id] = record

        body = client.get(f"/api/v1/privacy/exports/{record.id}").json()
        assert body["status"] == "expired"
        assert body["download_url"] is None

        # Un lien signé valide mais périmé → 410 export_expired (F-Q 🟡).
        url = make_download_url(record.id, expired_at)
        response = client.get(url)
        assert response.status_code == 410
        assert response.json()["type"].endswith("/export_expired")

    def test_export_d_autrui_404(
        self, client: TestClient, privacy_repository: InMemoryPrivacyRepository
    ) -> None:
        register(client)
        someone_else = uuid.uuid4()
        record = make_export_record(someone_else, status="ready")
        privacy_repository.exports[record.id] = record
        assert client.get(f"/api/v1/privacy/exports/{record.id}").status_code == 404

    def test_sans_session_401(self, client: TestClient) -> None:
        assert client.get(f"/api/v1/privacy/exports/{uuid.uuid4()}").status_code == 401

"""Tests de DELETE /account (F-Q, AC-Q-1) : soft delete + purge planifiée."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.privacy.conftest import (
    InMemoryPrivacyRepository,
    csrf_headers,
    register,
)

PASSWORD = "un mot de passe très long"


def delete_account(client: TestClient, password: str = PASSWORD) -> object:
    return client.request(
        "DELETE",
        "/api/v1/account",
        json={"password": password},
        headers=csrf_headers(client),
    )


class TestDeleteAccount:
    def test_mauvais_mot_de_passe_401_sans_aucun_effet(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        privacy_repository: InMemoryPrivacyRepository,
    ) -> None:
        register(client)
        response = delete_account(client, password="mauvais mot de passe !")
        assert response.status_code == 401
        assert response.json()["type"].endswith("/invalid_credentials")
        # Aucun effet : compte intact, pas de deletion_request, session valide.
        user = next(iter(auth_repository.users_by_id.values()))
        assert user.deleted_at is None
        assert privacy_repository.deletion_requests == {}
        assert client.get("/api/v1/me").status_code == 200

    def test_suppression_soft_delete_sessions_et_purge_a_30_jours(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        privacy_repository: InMemoryPrivacyRepository,
    ) -> None:
        register(client)
        user_id = next(iter(auth_repository.users_by_id))
        session_cookie = client.cookies["boussole_session"]

        response = delete_account(client)
        assert response.status_code == 204

        # Soft delete immédiat (RM-Q-1).
        user = auth_repository.users_by_id[user_id]
        assert user.deleted_at is not None

        # deletion_request pending à J+30 (AC-Q-1).
        assert len(privacy_repository.deletion_requests) == 1
        deletion = next(iter(privacy_repository.deletion_requests.values()))
        assert deletion.user_id == user_id
        assert deletion.status == "pending"
        expected = datetime.now(UTC) + timedelta(days=30)
        assert abs((deletion.purge_after - expected).total_seconds()) < 60

        # Sessions révoquées : même en rejouant l'ancien cookie → 401.
        client.cookies.set("boussole_session", session_cookie)
        assert client.get("/api/v1/me").status_code == 401

        # Audit journalisé.
        actions = [entry["action"] for entry in privacy_repository.audit_entries]
        assert "account_deletion_requested" in actions

    def test_le_login_refuse_un_compte_supprime(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        register(client)
        delete_account(client)
        # Comme pour un compte inexistant (AC-Q-1) : 401, pas d'oracle.
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "camille@example.eu", "password": PASSWORD},
        )
        assert response.status_code == 401

    def test_sans_jeton_csrf_403(self, client: TestClient) -> None:
        register(client)
        response = client.request(
            "DELETE", "/api/v1/account", json={"password": PASSWORD}
        )
        assert response.status_code == 403
        assert response.json()["type"].endswith("/csrf_invalid")

    def test_sans_session_401(self, client: TestClient) -> None:
        client.cookies.set("boussole_csrf", "jeton-csrf")
        response = client.request(
            "DELETE",
            "/api/v1/account",
            json={"password": PASSWORD},
            headers={"X-CSRF-Token": "jeton-csrf"},
        )
        assert response.status_code == 401

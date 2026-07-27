"""Tests de DELETE /account (F-Q, AC-Q-1) : soft delete + purge planifiée.

Contient aussi les tests du limiteur DÉDIÉ de la route (M4) : la route
vérifie un mot de passe et distingue 401 / 204, c'est donc un oracle de mot
de passe. Le middleware global ne la protège pas (identité contournable,
fail-open) : elle porte son propre limiteur 5/h par ``user_id``, fail-CLOSED.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.redis import get_redis_cache
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


class BrokenRedis:
    """Client Redis en panne — toute opération échoue (test du fail-closed)."""

    async def incr(self, key: str) -> int:
        raise ConnectionError("Redis volatile injoignable")

    async def expire(self, key: str, ttl: int) -> bool:
        raise ConnectionError("Redis volatile injoignable")


class TestLimiteurDedieM4:
    """Oracle de mot de passe : 5 tentatives/h par user_id, fail-closed."""

    def test_cinq_tentatives_puis_429_avec_retry_after(
        self, client: TestClient, privacy_repository: InMemoryPrivacyRepository
    ) -> None:
        register(client)
        for _ in range(5):
            assert delete_account(client, password="mauvais !").status_code == 401

        blocked = delete_account(client, password="mauvais !")
        assert blocked.status_code == 429
        assert blocked.headers["content-type"].startswith("application/problem+json")
        assert blocked.json()["type"].endswith("/rate_limited")
        assert int(blocked.headers["Retry-After"]) >= 1
        # Le blocage lui-même est audité (D20).
        actions = [e["action"] for e in privacy_repository.audit_entries]
        assert "account_deletion_rate_limited" in actions

    def test_echec_de_mot_de_passe_audite(
        self, client: TestClient, privacy_repository: InMemoryPrivacyRepository
    ) -> None:
        register(client)
        assert delete_account(client, password="mauvais !").status_code == 401
        failed = [
            e
            for e in privacy_repository.audit_entries
            if e["action"] == "account_deletion_failed"
        ]
        assert len(failed) == 1
        assert failed[0]["meta"] == {"reason": "invalid_password"}

    def test_une_suppression_legitime_passe_sous_la_limite(
        self, client: TestClient, privacy_repository: InMemoryPrivacyRepository
    ) -> None:
        register(client)
        assert delete_account(client).status_code == 204
        assert len(privacy_repository.deletion_requests) == 1

    def test_fail_closed_503_si_redis_indisponible(
        self, client: TestClient, privacy_repository: InMemoryPrivacyRepository
    ) -> None:
        register(client)
        client.app.dependency_overrides[get_redis_cache] = lambda: BrokenRedis()

        response = delete_account(client)

        # Écart ASSUMÉ à D18 (fail-open) : sans compteur, la route serait un
        # oracle de mot de passe non plafonné → on refuse proprement.
        assert response.status_code == 503
        assert response.json()["type"].endswith("/service_unavailable")
        assert response.headers["Retry-After"] == "60"
        # …et aucune suppression n'a eu lieu.
        assert privacy_repository.deletion_requests == {}

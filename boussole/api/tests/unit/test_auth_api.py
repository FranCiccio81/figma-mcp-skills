"""Tests API du module auth (TestClient, DB en mémoire, Redis factices)."""

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryAuthRepository

REGISTER_PAYLOAD = {
    "email": "camille@example.eu",
    "password": "un mot de passe très long",
    "locale": "fr",
    "accepted_terms_version": "2026-07",
    "accepted_privacy_version": "2026-07",
}


def register(client: TestClient, **overrides: str) -> object:
    return client.post("/api/v1/auth/register", json={**REGISTER_PAYLOAD, **overrides})


def login(client: TestClient, email: str = "camille@example.eu",
          password: str = "un mot de passe très long") -> object:
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


class TestRegister:
    def test_register_creates_user_and_opens_session(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        response = register(client)
        assert response.status_code == 201
        assert "boussole_session" in response.cookies
        assert "boussole_csrf" in response.cookies
        # Cookie de session httpOnly, le CSRF non (double-submit).
        set_cookie = ", ".join(response.headers.get_list("set-cookie"))
        assert "HttpOnly" in set_cookie
        assert len(auth_repository.users_by_id) == 1
        # Consentements horodatés enregistrés (terms + privacy).
        assert {kind for _, kind, _ in auth_repository.consents} == {"terms", "privacy"}
        # La session est immédiatement utilisable.
        assert client.get("/api/v1/me").status_code == 200

    def test_register_duplicate_email_is_neutral(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        first = register(client)
        second = register(client, password="un tout autre mot de passe")

        # Réponse strictement identique (anti-énumération 🟡 Q31)…
        assert second.status_code == first.status_code == 201
        assert second.json() == first.json()
        assert "boussole_session" in second.cookies
        # …mais aucun second compte n'est créé…
        assert len(auth_repository.users_by_id) == 1
        # …et le cookie posé est un leurre : pas de session valide.
        assert client.get("/api/v1/me").status_code == 401

    def test_register_password_too_short_is_422_problem(self, client: TestClient) -> None:
        response = register(client, password="court")
        assert response.status_code == 422
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert any(err["field"] == "password" for err in body["errors"])


class TestLogin:
    def test_login_ok_sets_cookies(self, client: TestClient) -> None:
        register(client)
        client.cookies.clear()

        response = login(client)
        assert response.status_code == 204
        assert "boussole_session" in response.cookies
        assert "boussole_csrf" in response.cookies
        assert client.get("/api/v1/me").status_code == 200

    def test_login_wrong_password_is_401_problem(self, client: TestClient) -> None:
        register(client)
        client.cookies.clear()

        response = login(client, password="mauvais mot de passe !")
        assert response.status_code == 401
        body = response.json()
        assert body["type"].endswith("/invalid_credentials")
        assert "boussole_session" not in response.cookies

    def test_login_unknown_email_is_401(self, client: TestClient) -> None:
        response = login(client, email="inconnue@example.eu")
        assert response.status_code == 401

    def test_login_rate_limited_after_5_attempts(self, client: TestClient) -> None:
        register(client)
        client.cookies.clear()

        for _ in range(5):
            assert login(client, password="mauvais mot de passe !").status_code == 401

        response = login(client, password="mauvais mot de passe !")
        assert response.status_code == 429
        assert response.headers["content-type"].startswith("application/problem+json")
        assert int(response.headers["Retry-After"]) >= 1

        # Même le bon mot de passe est bloqué dans la fenêtre courante.
        assert login(client).status_code == 429


class TestLogoutAndMe:
    def test_me_without_session_is_401_problem(self, client: TestClient) -> None:
        response = client.get("/api/v1/me")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")

    def test_me_returns_user_and_onboarding(self, client: TestClient) -> None:
        register(client)
        body = client.get("/api/v1/me").json()
        assert body["email"] == "camille@example.eu"
        assert body["locale"] == "fr"
        assert body["onboarding"] == {
            "cv_imported": False,
            "profile_validated": False,
            "preferences_set": False,
        }

    def test_logout_revokes_session(self, client: TestClient) -> None:
        register(client)
        csrf = client.cookies["boussole_csrf"]

        response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
        assert response.status_code == 204
        # La session est révoquée côté serveur (pas seulement le cookie).
        assert client.get("/api/v1/me").status_code == 401


class TestCsrfProtection:
    def test_mutation_without_csrf_header_is_403(self, client: TestClient) -> None:
        register(client)  # session + cookie CSRF posés
        response = client.post("/api/v1/auth/logout")  # en-tête absent
        assert response.status_code == 403
        assert response.json()["type"].endswith("/csrf_invalid")

    def test_mutation_with_wrong_csrf_header_is_403(self, client: TestClient) -> None:
        register(client)
        response = client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": "jeton-falsifié"}
        )
        assert response.status_code == 403

    def test_login_and_register_are_csrf_exempt(self, client: TestClient) -> None:
        # Aucun cookie CSRF encore posé : ces routes doivent rester accessibles.
        assert register(client).status_code == 201

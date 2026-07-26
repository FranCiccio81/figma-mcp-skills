"""Tests du format d'erreur RFC 9457 (application/problem+json)."""

from fastapi.testclient import TestClient


class TestProblemFormat:
    def test_404_is_problem_json(self, client: TestClient) -> None:
        response = client.get("/api/v1/nulle-part")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["type"] == "https://api.boussole.eu/errors/not_found"
        assert body["title"] == "Ressource introuvable"
        assert body["status"] == 404
        assert body["trace_id"]

    def test_trace_id_matches_response_header(self, client: TestClient) -> None:
        response = client.get("/api/v1/nulle-part")
        assert response.json()["trace_id"] == response.headers["X-Trace-Id"]

    def test_incoming_trace_id_is_propagated(self, client: TestClient) -> None:
        response = client.get("/api/v1/nulle-part", headers={"X-Trace-Id": "abc123"})
        assert response.json()["trace_id"] == "abc123"

    def test_validation_error_has_field_violations(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "pas-un-email", "password": "court"},
        )
        assert response.status_code == 422
        body = response.json()
        assert body["type"] == "https://api.boussole.eu/errors/validation_error"
        assert body["status"] == 422
        fields = {err["field"] for err in body["errors"]}
        assert "email" in fields
        assert "password" in fields
        for err in body["errors"]:
            assert set(err) == {"field", "code", "message"}

    def test_stub_module_returns_501_problem(self, client: TestClient) -> None:
        # Les modules non livrés (ici /generations, prévu M4) répondent un 501
        # documenté, pas un TODO muet. (/profile est implémenté depuis M3.)
        response = client.get("/api/v1/generations")
        assert response.status_code == 501
        body = response.json()
        assert body["type"] == "https://api.boussole.eu/errors/not_implemented"

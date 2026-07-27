"""Tests du format d'erreur RFC 9457 (application/problem+json)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.problems import not_implemented_problem, register_problem_handlers


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

    def test_stub_feature_returns_501_problem(self) -> None:
        # Les modules/fonctionnalités non livrés répondent un 501 documenté,
        # pas un TODO muet. Depuis M4/M5 tous les modules du contrat sont
        # branchés (le /generations testé ici jusqu'au M3 est implémenté) :
        # le format du 501 est vérifié via le helper ``not_implemented_problem``
        # — utilisé par les fonctionnalités restantes (ex. export PDF/DOCX,
        # M5, couvert par tests/unit/generation).
        app = FastAPI()
        register_problem_handlers(app)

        @app.get("/stub")
        async def stub() -> None:
            raise not_implemented_problem("demo", "M9")

        with TestClient(app) as stub_client:
            response = stub_client.get("/stub")
        assert response.status_code == 501
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["type"] == "https://api.boussole.eu/errors/not_implemented"
        assert "M9" in body["detail"]

"""Tests du durcissement M5 : en-têtes de sécurité et rate limiting fail-open."""

from fastapi.testclient import TestClient


class TestSecurityHeaders:
    def test_responses_carry_baseline_security_headers(self, client: TestClient) -> None:
        response = client.get("/healthz")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["Cache-Control"] == "no-store"


class TestRateLimitFailOpen:
    def test_requests_pass_when_redis_unavailable(self, client: TestClient) -> None:
        # En tests unitaires, le Redis volatile n'existe pas : le middleware
        # doit laisser passer (fail-open D18) — jamais un point de panne.
        response = client.get("/api/v1/me")
        assert response.status_code in (200, 401)  # jamais 429 ni 500

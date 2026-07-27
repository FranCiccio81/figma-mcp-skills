"""Tests du durcissement M5 : en-têtes de sécurité et rate limiting.

Le seul test existant ici validait le fail-open (Redis absent) et RIEN
d'autre : le middleware appelait ``get_redis_cache()`` en direct, hors DI, si
bien qu'aucun override de test ne l'atteignait. Les limites contractuelles
(12 §1) n'étaient donc jamais exercées — et l'identité de seau, dérivée d'un
cookie NON VALIDÉ, était contournable par un cookie aléatoire par requête
(200 requêtes, 0 rejet).

Les fabriques Redis sont désormais injectées à ``create_app`` (M2) : le
limiteur est exercé pour de vrai sur fakeredis.
"""

import uuid
from collections.abc import Iterator

import fakeredis
import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from starlette.requests import Request

from app.core.db import EngineOverrideError, override_engine
from app.core.redis import get_redis_cache, get_redis_persistent
from app.main import client_ip, create_app
from app.modules.auth.repository import get_auth_repository
from tests.unit.conftest import InMemoryAuthRepository

REGISTER_PAYLOAD = {
    "email": "camille@example.eu",
    "password": "un mot de passe très long",
    "locale": "fr",
    "accepted_terms_version": "2026-07",
    "accepted_privacy_version": "2026-07",
}

#: Horloge figée : la fenêtre fixe du limiteur est alignée sur l'horloge —
#: sans gel, une bascule de fenêtre au milieu d'une rafale de 61 requêtes
#: rendrait ces tests intermittents.
FROZEN_NOW = 1_700_000_040.0


class _FrozenClock:
    """Remplace le module ``time`` DANS ``app.core.ratelimit`` uniquement."""

    @staticmethod
    def time() -> float:
        return FROZEN_NOW


class TestSecurityHeaders:
    def test_responses_carry_baseline_security_headers(self, client: TestClient) -> None:
        response = client.get("/healthz")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["Cache-Control"] == "no-store"


class TestRateLimitFailOpen:
    def test_requests_pass_when_redis_unavailable(self, client: TestClient) -> None:
        # Le client commun ne fournit aucune fabrique : le middleware retombe
        # sur le vrai Redis volatile, absent en test unitaire. Fail-open D18 —
        # le rate limiting est une protection, jamais un point de panne.
        response = client.get("/api/v1/me")
        assert response.status_code in (200, 401)  # jamais 429 ni 500

    def test_fail_open_explicite_avec_un_client_en_panne(
        self, auth_repository: InMemoryAuthRepository
    ) -> None:
        class BrokenRedis:
            async def incr(self, key: str) -> int:
                raise ConnectionError("Redis volatile injoignable")

            async def get(self, key: str) -> str | None:
                raise ConnectionError("Redis persistant injoignable")

        app = create_app(
            redis_cache_factory=lambda: BrokenRedis(),  # type: ignore[arg-type,return-value]
            redis_persistent_factory=lambda: BrokenRedis(),  # type: ignore[arg-type,return-value]
        )
        app.dependency_overrides[get_auth_repository] = lambda: auth_repository
        with TestClient(app, base_url="https://testserver") as client:
            for _ in range(70):  # bien au-delà des 60/min
                assert client.get("/api/v1/me").status_code != 429


@pytest.fixture
def limited_client(
    auth_repository: InMemoryAuthRepository,
    fake_persistent_server: fakeredis.FakeServer,
    fake_cache_server: fakeredis.FakeServer,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """Application dont le limiteur est RÉELLEMENT branché (fakeredis)."""
    monkeypatch.setattr("app.core.ratelimit.time", _FrozenClock)

    def cache_factory() -> Redis:
        return fakeredis.aioredis.FakeRedis(server=fake_cache_server, decode_responses=True)

    def persistent_factory() -> Redis:
        return fakeredis.aioredis.FakeRedis(
            server=fake_persistent_server, decode_responses=True
        )

    app = create_app(
        redis_cache_factory=cache_factory, redis_persistent_factory=persistent_factory
    )
    app.dependency_overrides[get_auth_repository] = lambda: auth_repository
    app.dependency_overrides[get_redis_persistent] = persistent_factory
    app.dependency_overrides[get_redis_cache] = cache_factory
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def _register(client: TestClient) -> None:
    assert client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD).status_code == 201


class TestLimitesContractuelles:
    def test_limite_globale_60_par_minute(self, limited_client: TestClient) -> None:
        for _ in range(60):
            assert limited_client.get("/api/v1/me").status_code != 429

        blocked = limited_client.get("/api/v1/me")
        assert blocked.status_code == 429
        assert blocked.headers["content-type"].startswith("application/problem+json")
        assert blocked.json()["type"].endswith("/rate_limited")
        assert int(blocked.headers["Retry-After"]) >= 1

    def test_limite_recherche_30_par_minute_sur_get_jobs(
        self, limited_client: TestClient
    ) -> None:
        for _ in range(30):
            assert limited_client.get("/api/v1/jobs").status_code != 429

        blocked = limited_client.get("/api/v1/jobs")
        assert blocked.status_code == 429
        # La limite globale (60) n'est PAS atteinte : c'est bien le seau
        # « recherche » qui a parlé — une autre route passe encore.
        assert limited_client.get("/api/v1/me").status_code != 429


class TestIdentiteDeSeau:
    def test_un_cookie_de_session_inconnu_ne_cree_pas_de_nouveau_seau(
        self, limited_client: TestClient
    ) -> None:
        """Régression C3 : le PoC de revue (200 requêtes, 0 rejet)."""
        rejected = False
        for _ in range(61):
            # Un cookie DIFFÉRENT et arbitraire à chaque requête.
            limited_client.cookies.set("boussole_session", uuid.uuid4().hex)
            if limited_client.get("/api/v1/me").status_code == 429:
                rejected = True
                break
        assert rejected, (
            "un cookie de session non validé ouvre encore un seau neuf : "
            "l'identité doit venir de la session RÉELLEMENT résolue"
        )

    def test_isolation_entre_utilisateur_authentifie_et_anonyme(
        self, limited_client: TestClient
    ) -> None:
        _register(limited_client)  # pose une VRAIE session (1 hit anonyme)

        # Le seau de l'utilisateur authentifié se remplit…
        for _ in range(60):
            limited_client.get("/api/v1/me")
        assert limited_client.get("/api/v1/me").status_code == 429

        # …sans affecter le seau anonyme (identité = IP), qui a encore du mou.
        limited_client.cookies.clear()
        assert limited_client.get("/api/v1/me").status_code != 429

    def test_deux_sessions_du_meme_utilisateur_partagent_le_seau(
        self, limited_client: TestClient
    ) -> None:
        _register(limited_client)
        first_session = limited_client.cookies["boussole_session"]
        csrf = limited_client.cookies["boussole_csrf"]

        # Seconde session pour le MÊME compte (login) — cookie différent.
        response = limited_client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
        )
        assert response.status_code == 204
        second_session = limited_client.cookies["boussole_session"]
        assert second_session != first_session

        # L'identité est l'UTILISATEUR, pas le cookie : alterner les deux
        # sessions ne double pas le quota.
        rejected = False
        for index in range(62):
            token = first_session if index % 2 else second_session
            limited_client.cookies.set("boussole_session", token)
            limited_client.cookies.set("boussole_csrf", csrf)
            if limited_client.get("/api/v1/me").status_code == 429:
                rejected = True
                break
        assert rejected


class TestClientIpDerriereProxy:
    """M1 — ``X-Forwarded-For`` n'est cru que derrière un proxy de confiance."""

    @staticmethod
    def _request(peer: str, forwarded: str | None) -> Request:
        headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": headers,
                "client": (peer, 12345),
            }
        )

    def test_pair_non_fiable_l_en_tete_est_ignore(self) -> None:
        request = self._request("203.0.113.9", "1.2.3.4")
        assert client_ip(request, frozenset({"10.0.0.1"})) == "203.0.113.9"

    def test_pair_fiable_dernier_saut_de_confiance(self) -> None:
        # Chaîne « client, proxy amont, notre proxy » : on remonte de la
        # DROITE vers la gauche et on garde le premier saut non fiable.
        request = self._request("10.0.0.1", "198.51.100.7, 10.0.0.2")
        assert client_ip(request, frozenset({"10.0.0.1", "10.0.0.2"})) == "198.51.100.7"

    def test_entree_de_gauche_forgee_par_le_client_n_est_pas_retenue(self) -> None:
        # Un client qui préfixe lui-même l'en-tête ne choisit pas son identité.
        request = self._request("10.0.0.1", "9.9.9.9, 203.0.113.9")
        assert client_ip(request, frozenset({"10.0.0.1"})) == "203.0.113.9"

    def test_chaine_entierement_fiable_retombe_sur_le_pair(self) -> None:
        request = self._request("10.0.0.1", "10.0.0.2")
        assert client_ip(request, frozenset({"10.0.0.1", "10.0.0.2"})) == "10.0.0.1"

    def test_sans_en_tete_c_est_le_pair(self) -> None:
        request = self._request("10.0.0.1", None)
        assert client_ip(request, frozenset({"10.0.0.1"})) == "10.0.0.1"


class TestOverrideEngineNonReentrant:
    """Garde explicite : la substitution du moteur global n'est pas empilable."""

    def test_une_seconde_entree_leve(self) -> None:
        sentinel = object()
        with (
            override_engine(sentinel),  # type: ignore[arg-type]
            pytest.raises(EngineOverrideError),
            override_engine(sentinel),  # type: ignore[arg-type]
        ):
            pass

    def test_la_garde_est_relachee_apres_la_sortie(self) -> None:
        sentinel = object()
        with override_engine(sentinel):  # type: ignore[arg-type]
            pass
        with override_engine(sentinel):  # type: ignore[arg-type]
            pass  # aucune exception : l'état global a bien été restauré

    def test_la_garde_est_relachee_meme_apres_une_exception(self) -> None:
        sentinel = object()
        with pytest.raises(RuntimeError, match="panne"):  # noqa: SIM117
            with override_engine(sentinel):  # type: ignore[arg-type]
                raise RuntimeError("panne pendant la tâche")
        with override_engine(sentinel):  # type: ignore[arg-type]
            pass

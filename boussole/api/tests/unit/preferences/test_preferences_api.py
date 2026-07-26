"""Tests API du module preferences (TestClient, repository en mémoire)."""

import uuid

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.preferences.conftest import InMemoryPreferencesRepository

PREFS_URL = "/api/v1/preferences"

FULL_PAYLOAD = {
    "remote_pref": "preferred",
    "contract_types": ["permanent", "freelance"],
    "contract_strict": True,
    "salary_min": 50000,
    "salary_min_strict": 45000,
    "locations": [{"label": "Lyon", "lat": 45.75, "lon": 4.85, "radius_km": 50}],
    "target_titles": ["Développeuse backend"],
    "sectors_preferred": ["J"],
    "sectors_excluded": ["K"],
    "target_companies": ["Boussole SAS"],
    "keywords": ["python"],
}


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


def put(client: TestClient, payload: dict[str, object]) -> object:
    return client.put(PREFS_URL, json=payload, headers=csrf_headers(client))


class TestAuthAndCsrf:
    def test_routes_without_session_are_401_problem(self, client: TestClient) -> None:
        response = client.get(PREFS_URL)
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")
        # Mutation sans session : le middleware CSRF répond avant l'auth (403).
        assert client.put(PREFS_URL, json={}).status_code == 403

    def test_put_without_csrf_header_is_403(self, client: TestClient) -> None:
        register(client)
        response = client.put(PREFS_URL, json={})
        assert response.status_code == 403
        assert response.json()["type"].endswith("/csrf_invalid")


class TestGetDefaults:
    def test_defaults_when_never_set(
        self, client: TestClient, preferences_repository: InMemoryPreferencesRepository
    ) -> None:
        register(client)
        response = client.get(PREFS_URL)
        assert response.status_code == 200
        assert response.json() == {
            "remote_pref": "indifferent",
            "contract_types": ["permanent"],
            "contract_strict": False,
            "salary_min": None,
            "salary_min_strict": None,
            "locations": [],
            "target_titles": [],
            "sectors_preferred": [],
            "sectors_excluded": [],
            "target_companies": [],
            "keywords": [],
        }
        # Les défauts ne sont pas persistés 🟡.
        assert not preferences_repository.by_user


class TestPutPreferences:
    def test_roundtrip_full_payload(self, client: TestClient) -> None:
        register(client)
        response = put(client, FULL_PAYLOAD)
        assert response.status_code == 200
        assert response.json() == FULL_PAYLOAD
        assert client.get(PREFS_URL).json() == FULL_PAYLOAD

    def test_put_is_a_full_replacement(self, client: TestClient) -> None:
        register(client)
        put(client, FULL_PAYLOAD)
        # Payload partiel : toute liste omise est vidée (F-D alternatif 1).
        response = put(client, {"remote_pref": "required"})
        assert response.status_code == 200
        body = response.json()
        assert body["remote_pref"] == "required"
        assert body["locations"] == []
        assert body["target_titles"] == []
        assert body["salary_min"] is None
        assert body["contract_types"] == ["permanent"]  # défaut produit 🟡

    def test_default_radius_is_30_km(self, client: TestClient) -> None:
        register(client)
        response = put(
            client, {"locations": [{"label": "Lyon", "lat": 45.75, "lon": 4.85}]}
        )
        # AC-D-2 : rayon par défaut 30 km, explicite dans la réponse.
        assert response.json()["locations"][0]["radius_km"] == 30

    def test_deduplicates_lists_before_write(self, client: TestClient) -> None:
        register(client)
        response = put(
            client,
            {
                "contract_types": ["permanent", "permanent", "freelance"],
                "keywords": ["Python", "python", "sql"],
                "target_companies": ["Acme", "ACME"],
            },
        )
        body = response.json()
        assert body["contract_types"] == ["permanent", "freelance"]
        # Dédup insensible à la casse (clés primaires citext du schéma).
        assert body["keywords"] == ["Python", "sql"]
        assert body["target_companies"] == ["Acme"]

    def test_emits_preferences_changed_event(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        recorded_changes: list[uuid.UUID],
    ) -> None:
        register(client)
        put(client, FULL_PAYLOAD)
        (user_id,) = auth_repository.users_by_id
        assert recorded_changes == [user_id]


class TestPutValidation:
    def test_salary_min_strict_above_salary_min_is_422_and_state_kept(
        self, client: TestClient, preferences_repository: InMemoryPreferencesRepository
    ) -> None:
        register(client)
        put(client, FULL_PAYLOAD)
        response = put(client, {"salary_min": 40000, "salary_min_strict": 45000})
        # AC-D-4 : 422 ciblant le champ, état précédent conservé.
        assert response.status_code == 422
        assert response.headers["content-type"].startswith("application/problem+json")
        assert any(
            err["field"] == "salary_min_strict" for err in response.json()["errors"]
        )
        assert client.get(PREFS_URL).json() == FULL_PAYLOAD
        assert len(preferences_repository.by_user) == 1

    def test_radius_out_of_bounds_is_422(self, client: TestClient) -> None:
        register(client)
        for radius in (0, 201):
            response = put(
                client,
                {"locations": [{"label": "Lyon", "lat": 45.75, "lon": 4.85,
                                "radius_km": radius}]},
            )
            assert response.status_code == 422

    def test_location_without_coordinates_is_422(self, client: TestClient) -> None:
        register(client)
        response = put(client, {"locations": [{"label": "Lyon"}]})
        assert response.status_code == 422
        fields = {err["field"] for err in response.json()["errors"]}
        assert any(field.endswith("lat") for field in fields)

    def test_unknown_sector_is_422(self, client: TestClient) -> None:
        register(client)
        response = put(client, {"sectors_preferred": ["J", "ZZZ"]})
        assert response.status_code == 422
        body = response.json()
        assert any(
            err["code"] == "unknown_sector" and "ZZZ" in err["message"]
            for err in body["errors"]
        )

    def test_sector_both_preferred_and_excluded_is_422(self, client: TestClient) -> None:
        register(client)
        response = put(
            client, {"sectors_preferred": ["J"], "sectors_excluded": ["J", "K"]}
        )
        assert response.status_code == 422
        assert any(
            err["code"] == "sector_both_preferred_and_excluded"
            for err in response.json()["errors"]
        )

    def test_invalid_contract_type_is_422(self, client: TestClient) -> None:
        register(client)
        response = put(client, {"contract_types": ["cdi"]})
        assert response.status_code == 422

    def test_failed_validation_does_not_emit_event(
        self, client: TestClient, recorded_changes: list[uuid.UUID]
    ) -> None:
        register(client)
        put(client, {"salary_min": 40000, "salary_min_strict": 45000})
        assert recorded_changes == []

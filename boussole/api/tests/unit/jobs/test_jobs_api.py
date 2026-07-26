"""Tests API du module jobs (TestClient, repository en mémoire, Redis factices)."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.modules.jobs.repository import SourceRow
from tests.unit.jobs.conftest import InMemoryJobsRepository, make_posting

JOBS_URL = "/api/v1/jobs"


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


class TestAuthRequired:
    def test_search_without_session_is_401_problem(self, client: TestClient) -> None:
        response = client.get(JOBS_URL)
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")

    def test_detail_and_sources_without_session_are_401(self, client: TestClient) -> None:
        assert client.get(f"{JOBS_URL}/{uuid.uuid4()}").status_code == 401
        assert client.get("/api/v1/sources").status_code == 401


class TestSearch:
    def test_returns_cards_with_null_match_m2(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        jobs_repository.add(make_posting())
        register(client)

        response = client.get(JOBS_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["next_cursor"] is None
        (card,) = body["items"]
        assert card["title"] == "Développeur backend Python"
        assert card["company_name"] == "Boussole SAS"
        assert card["locations"] == ["Lyon"]
        assert card["salary_label"] == "45–55 k€"
        assert card["match"] is None  # M2 : scoring au M3
        assert card["saved_state"] is None

    def test_filters_remote_and_contract(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        kept = jobs_repository.add(make_posting(remote="full_remote", contract="permanent"))
        jobs_repository.add(make_posting(remote="onsite", contract="internship"))
        register(client)

        response = client.get(
            JOBS_URL, params={"remote": ["full_remote", "hybrid"], "contract": "permanent"}
        )
        assert [item["id"] for item in response.json()["items"]] == [str(kept.id)]

    def test_salary_min_keeps_unknown_salaries_q32(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        jobs_repository.add(make_posting(salary_min=30000, salary_max=35000))
        unknown = jobs_repository.add(
            make_posting(salary_min=None, salary_max=None, salary_currency=None,
                         salary_period=None)
        )
        rich = jobs_repository.add(make_posting(salary_min=50000, salary_max=60000))
        register(client)

        response = client.get(JOBS_URL, params={"salary_min": 45000})
        ids = {item["id"] for item in response.json()["items"]}
        assert ids == {str(unknown.id), str(rich.id)}
        by_id = {item["id"]: item for item in response.json()["items"]}
        # Badge « non communiqué » : salary_label null, jamais exclue (Q32).
        assert by_id[str(unknown.id)]["salary_label"] is None

    def test_excludes_inactive_jobs(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        jobs_repository.add(make_posting(status="expired"))
        jobs_repository.add(make_posting(status="withdrawn"))
        active = jobs_repository.add(make_posting())
        register(client)

        response = client.get(JOBS_URL)
        assert [item["id"] for item in response.json()["items"]] == [str(active.id)]

    def test_fulltext_query_filters_and_ranks(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        jobs_repository.add(make_posting(title="Comptable", description_text="Paie."))
        match = jobs_repository.add(make_posting(title="Data engineer Python"))
        register(client)

        response = client.get(JOBS_URL, params={"q": "python", "sort": "relevance"})
        assert [item["id"] for item in response.json()["items"]] == [str(match.id)]

    def test_sort_match_is_accepted_and_falls_back(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        jobs_repository.add(make_posting())
        register(client)
        # sort=match (défaut du contrat) → relevance au M2, sans erreur.
        assert client.get(JOBS_URL, params={"sort": "match", "q": "python"}).status_code == 200

    def test_limit_above_100_is_422(self, client: TestClient) -> None:
        register(client)
        response = client.get(JOBS_URL, params={"limit": 101})
        assert response.status_code == 422
        assert response.headers["content-type"].startswith("application/problem+json")

    def test_lat_without_lon_is_422(self, client: TestClient) -> None:
        register(client)
        response = client.get(JOBS_URL, params={"lat": 45.75})
        assert response.status_code == 422
        assert any(err["code"] == "missing_pair" for err in response.json()["errors"])

    def test_geo_radius_filters_locations(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        lyon = jobs_repository.add(make_posting(locations=[("Lyon", 45.75, 4.85, "FR")]))
        jobs_repository.add(make_posting(locations=[("Paris", 48.85, 2.35, "FR")]))
        register(client)

        response = client.get(JOBS_URL, params={"lat": 45.76, "lon": 4.84, "radius_km": 30})
        assert [item["id"] for item in response.json()["items"]] == [str(lyon.id)]


class TestPagination:
    def test_keyset_pagination_covers_all_without_overlap(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        now = datetime.now(UTC)
        expected = [
            jobs_repository.add(make_posting(last_seen_at=now - timedelta(hours=i)))
            for i in range(5)
        ]
        register(client)

        seen: list[str] = []
        cursor: str | None = None
        pages = 0
        while True:
            params: dict[str, object] = {"limit": 2, "sort": "date"}
            if cursor:
                params["cursor"] = cursor
            body = client.get(JOBS_URL, params=params).json()
            seen.extend(item["id"] for item in body["items"])
            pages += 1
            cursor = body["next_cursor"]
            if cursor is None:
                break
        assert pages == 3
        assert seen == [str(p.id) for p in expected]  # tri date DESC, aucun doublon


class TestSavedState:
    def test_save_then_saved_only_and_delete(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        job = jobs_repository.add(make_posting())
        jobs_repository.add(make_posting())
        register(client)

        put = client.put(
            f"{JOBS_URL}/{job.id}/saved-state",
            json={"state": "saved"},
            headers=csrf_headers(client),
        )
        assert put.status_code == 204

        body = client.get(JOBS_URL, params={"saved_only": True}).json()
        assert [item["id"] for item in body["items"]] == [str(job.id)]
        assert body["items"][0]["saved_state"] == "saved"

        delete = client.delete(
            f"{JOBS_URL}/{job.id}/saved-state", headers=csrf_headers(client)
        )
        assert delete.status_code == 204
        assert client.get(JOBS_URL, params={"saved_only": True}).json()["items"] == []

    def test_hidden_job_excluded_unless_include_hidden(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        job = jobs_repository.add(make_posting())
        register(client)

        client.put(
            f"{JOBS_URL}/{job.id}/saved-state",
            json={"state": "hidden"},
            headers=csrf_headers(client),
        )
        assert client.get(JOBS_URL).json()["items"] == []
        body = client.get(JOBS_URL, params={"include_hidden": True}).json()
        assert body["items"][0]["saved_state"] == "hidden"

    def test_delete_without_prior_state_is_idempotent_204(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        job = jobs_repository.add(make_posting())
        register(client)
        response = client.delete(
            f"{JOBS_URL}/{job.id}/saved-state", headers=csrf_headers(client)
        )
        assert response.status_code == 204

    def test_saved_state_on_unknown_job_is_404_problem(self, client: TestClient) -> None:
        register(client)
        response = client.put(
            f"{JOBS_URL}/{uuid.uuid4()}/saved-state",
            json={"state": "saved"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")

    def test_invalid_state_is_422(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        job = jobs_repository.add(make_posting())
        register(client)
        response = client.put(
            f"{JOBS_URL}/{job.id}/saved-state",
            json={"state": "favori"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 422

    def test_saved_state_is_scoped_per_user(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        """Ressource d'autrui : l'état saved d'un utilisateur ne fuit jamais."""
        job = jobs_repository.add(make_posting())
        register(client, email="alice@example.eu")
        client.put(
            f"{JOBS_URL}/{job.id}/saved-state",
            json={"state": "saved"},
            headers=csrf_headers(client),
        )

        client.cookies.clear()
        register(client, email="bob@example.eu")
        # Bob ne voit ni l'état d'Alice sur la carte, ni l'offre en saved_only.
        card = client.get(JOBS_URL).json()["items"][0]
        assert card["saved_state"] is None
        assert client.get(JOBS_URL, params={"saved_only": True}).json()["items"] == []
        detail = client.get(f"{JOBS_URL}/{job.id}").json()
        assert detail["saved_state"] is None


class TestDetail:
    def test_detail_has_nonempty_sources_with_original_url(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        job = jobs_repository.add(
            make_posting(skills=[("python", True), ("docker", False)])
        )
        register(client)

        response = client.get(f"{JOBS_URL}/{job.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["match"] is None
        assert body["skills_required"] == ["python"]
        assert body["skills_nice"] == ["docker"]
        # Garantie produit : au moins une source, avec nom + lien d'origine.
        assert len(body["sources"]) >= 1
        assert body["sources"][0]["name"] == "France Travail"
        assert body["sources"][0]["original_url"] == "https://ft.example.eu/offre/1"

    def test_unknown_job_is_404_problem(self, client: TestClient) -> None:
        register(client)
        response = client.get(f"{JOBS_URL}/{uuid.uuid4()}")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["type"].endswith("/not_found")

    def test_recently_expired_job_stays_readable_with_status(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        job = jobs_repository.add(
            make_posting(
                status="expired",
                expires_at=datetime.now(UTC) - timedelta(days=30),
            )
        )
        register(client)
        body = client.get(f"{JOBS_URL}/{job.id}").json()
        assert body["status"] == "expired"  # bandeau « offre expirée » côté front
        assert body["expires_at"] is not None  # date du bandeau

    def test_job_expired_beyond_12_months_is_404(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        job = jobs_repository.add(
            make_posting(
                status="expired",
                expires_at=datetime.now(UTC) - timedelta(days=400),
            )
        )
        register(client)
        assert client.get(f"{JOBS_URL}/{job.id}").status_code == 404

    def test_withdrawn_job_is_404(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        job = jobs_repository.add(make_posting(status="withdrawn"))
        register(client)
        assert client.get(f"{JOBS_URL}/{job.id}").status_code == 404

    def test_saved_state_follows_detail_readability(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        """Une offre 404 en lecture doit l'être aussi en mutation saved-state
        (anti-énumération : un 204 révélerait l'existence de l'offre retirée)."""
        job = jobs_repository.add(make_posting(status="withdrawn"))
        register(client)
        put = client.put(
            f"{JOBS_URL}/{job.id}/saved-state",
            json={"state": "saved"},
            headers=csrf_headers(client),
        )
        assert put.status_code == 404
        delete = client.delete(
            f"{JOBS_URL}/{job.id}/saved-state", headers=csrf_headers(client)
        )
        assert delete.status_code == 404


class TestSources:
    def test_lists_active_sources(
        self, client: TestClient, jobs_repository: InMemoryJobsRepository
    ) -> None:
        jobs_repository.sources = [
            SourceRow(slug="france-travail", name="France Travail",
                      kind="public_api", last_sync_at=None),
            SourceRow(slug="greenhouse", name="Greenhouse", kind="ats_feed",
                      last_sync_at=datetime(2026, 7, 23, 6, 0, tzinfo=UTC)),
        ]
        register(client)

        response = client.get("/api/v1/sources")
        assert response.status_code == 200
        body = response.json()
        assert [s["slug"] for s in body] == ["france-travail", "greenhouse"]
        assert body[0]["last_sync_at"] is None  # 🟡 connector_state pas encore peuplée
        assert body[1]["kind"] == "ats_feed"

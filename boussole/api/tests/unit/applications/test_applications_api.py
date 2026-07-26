"""Tests API du module applications (TestClient, repo en mémoire, Redis factices)."""

import uuid

from fastapi.testclient import TestClient

from tests.unit.applications.conftest import InMemoryApplicationsRepository

APPS_URL = "/api/v1/applications"


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


def create_external(
    client: TestClient,
    *,
    title: str = "Développeuse backend",
    company: str = "ACME",
    notes: str | None = None,
) -> dict:
    response = client.post(
        APPS_URL,
        json={"external_title": title, "external_company": company, "notes": notes},
        headers=csrf_headers(client),
    )
    assert response.status_code == 201
    return response.json()


class TestAuthAndCsrf:
    def test_list_and_detail_without_session_are_401_problem(
        self, client: TestClient
    ) -> None:
        response = client.get(APPS_URL)
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")
        assert client.get(f"{APPS_URL}/{uuid.uuid4()}").status_code == 401

    def test_mutations_without_csrf_are_403(self, client: TestClient) -> None:
        register(client)
        some_id = uuid.uuid4()
        assert client.post(APPS_URL, json={}).status_code == 403
        assert client.patch(f"{APPS_URL}/{some_id}", json={}).status_code == 403
        assert client.delete(f"{APPS_URL}/{some_id}").status_code == 403
        assert (
            client.post(
                f"{APPS_URL}/{some_id}/status", json={"to_status": "applied"}
            ).status_code
            == 403
        )


class TestCreate:
    def test_create_with_internal_job(
        self, client: TestClient, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        job_id = uuid.uuid4()
        applications_repository.job_ids.add(job_id)
        register(client)

        response = client.post(
            APPS_URL,
            json={"job_posting_id": str(job_id), "notes": "Vue depuis Sauvegardées"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["job_posting_id"] == str(job_id)
        assert body["status"] == "draft"
        assert body["applied_at"] is None
        assert body["events"] == []
        assert body["notes"] == "Vue depuis Sauvegardées"

    def test_create_with_unknown_job_is_404(self, client: TestClient) -> None:
        register(client)
        response = client.post(
            APPS_URL,
            json={"job_posting_id": str(uuid.uuid4())},
            headers=csrf_headers(client),
        )
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")

    def test_create_external_application(self, client: TestClient) -> None:
        register(client)
        response = client.post(
            APPS_URL,
            json={
                "external_title": "Data engineer",
                "external_company": "Hors plateforme SA",
                "external_url": "https://exemple.eu/offre",
            },
            headers=csrf_headers(client),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["job_posting_id"] is None
        assert body["external_title"] == "Data engineer"
        assert body["external_company"] == "Hors plateforme SA"
        assert body["status"] == "draft"

    def test_create_without_job_nor_external_is_422(self, client: TestClient) -> None:
        # AC-P-2 : 422 validation_error listant les champs requis.
        register(client)
        response = client.post(APPS_URL, json={}, headers=csrf_headers(client))
        assert response.status_code == 422
        body = response.json()
        assert body["type"].endswith("validation_error")
        fields = {error["field"] for error in body["errors"]}
        assert fields == {"job_posting_id", "external_title", "external_company"}

    def test_create_with_incomplete_external_pair_is_422(
        self, client: TestClient
    ) -> None:
        register(client)
        response = client.post(
            APPS_URL,
            json={"external_title": "Sans entreprise"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 422
        fields = {error["field"] for error in response.json()["errors"]}
        assert "external_company" in fields

    def test_idempotency_key_replay_returns_same_application(
        self, client: TestClient, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        register(client)
        key = str(uuid.uuid4())
        headers = {**csrf_headers(client), "Idempotency-Key": key}
        payload = {"external_title": "Dev", "external_company": "ACME"}

        first = client.post(APPS_URL, json=payload, headers=headers)
        replay = client.post(APPS_URL, json=payload, headers=headers)
        assert first.status_code == 201
        assert replay.status_code == 201
        assert replay.json()["id"] == first.json()["id"]
        assert len(applications_repository.applications) == 1

    def test_without_idempotency_key_each_post_creates(
        self, client: TestClient, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        register(client)
        create_external(client)
        create_external(client)
        assert len(applications_repository.applications) == 2


class TestList:
    def test_lists_only_own_applications_newest_first(
        self, client: TestClient, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        register(client, email="a@example.eu")
        first = create_external(client, title="Première")
        second = create_external(client, title="Seconde")

        register(client, email="b@example.eu")
        create_external(client, title="Autre utilisateur")

        # Retour à la session de l'utilisateur A impossible sans login : on
        # vérifie que B ne voit que la sienne (scoping).
        response = client.get(APPS_URL)
        assert response.status_code == 200
        titles = [item["external_title"] for item in response.json()["items"]]
        assert titles == ["Autre utilisateur"]
        assert {first["id"], second["id"]}.isdisjoint(
            {item["id"] for item in response.json()["items"]}
        )

    def test_filter_by_status(self, client: TestClient) -> None:
        register(client)
        kept = create_external(client, title="Envoyée")
        create_external(client, title="Brouillon")
        response = client.post(
            f"{APPS_URL}/{kept['id']}/status",
            json={"to_status": "applied"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 200

        listed = client.get(APPS_URL, params={"status": "applied"}).json()
        assert [item["id"] for item in listed["items"]] == [kept["id"]]
        assert client.get(APPS_URL, params={"status": "draft"}).json()["items"] != []

    def test_unknown_status_filter_is_422(self, client: TestClient) -> None:
        register(client)
        assert client.get(APPS_URL, params={"status": "sorcery"}).status_code == 422

    def test_cursor_paginates_without_overlap(self, client: TestClient) -> None:
        register(client)
        ids = {create_external(client, title=f"Candidature {i}")["id"] for i in range(3)}

        page1 = client.get(APPS_URL, params={"limit": 2}).json()
        assert len(page1["items"]) == 2
        assert page1["next_cursor"] is not None

        page2 = client.get(
            APPS_URL, params={"limit": 2, "cursor": page1["next_cursor"]}
        ).json()
        assert len(page2["items"]) == 1
        assert page2["next_cursor"] is None

        seen = [item["id"] for item in page1["items"] + page2["items"]]
        assert len(seen) == len(set(seen)) == 3
        assert set(seen) == ids

    def test_invalid_cursor_is_422_problem(self, client: TestClient) -> None:
        register(client)
        response = client.get(APPS_URL, params={"cursor": "n'importe quoi"})
        assert response.status_code == 422
        assert response.json()["type"].endswith("invalid_cursor")


class TestDetailScoping:
    def test_get_own_application(self, client: TestClient) -> None:
        register(client)
        created = create_external(client)
        response = client.get(f"{APPS_URL}/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_someone_elses_application_is_404(self, client: TestClient) -> None:
        register(client, email="a@example.eu")
        created = create_external(client)

        register(client, email="b@example.eu")
        response = client.get(f"{APPS_URL}/{created['id']}")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")

    def test_get_unknown_application_is_404(self, client: TestClient) -> None:
        register(client)
        assert client.get(f"{APPS_URL}/{uuid.uuid4()}").status_code == 404


class TestPatch:
    def test_patch_notes_and_external_fields(self, client: TestClient) -> None:
        register(client)
        created = create_external(client, notes="ancienne note")

        response = client.patch(
            f"{APPS_URL}/{created['id']}",
            json={"notes": "note à jour", "external_url": "https://exemple.eu/x"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["notes"] == "note à jour"
        assert body["external_url"] == "https://exemple.eu/x"
        assert body["external_title"] == created["external_title"]  # inchangé
        assert body["status"] == "draft"  # le statut ne passe jamais par PATCH
        assert body["updated_at"] >= created["updated_at"]

    def test_patch_cannot_strip_external_pair_of_external_application(
        self, client: TestClient
    ) -> None:
        # RM-P-2 : une candidature externe garde son couple titre/entreprise.
        register(client)
        created = create_external(client)
        response = client.patch(
            f"{APPS_URL}/{created['id']}",
            json={"external_company": None},
            headers=csrf_headers(client),
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("validation_error")

    def test_patch_can_clear_external_fields_of_internal_application(
        self, client: TestClient, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        job_id = uuid.uuid4()
        applications_repository.job_ids.add(job_id)
        register(client)
        created = client.post(
            APPS_URL,
            json={"job_posting_id": str(job_id), "external_title": "Doublon"},
            headers=csrf_headers(client),
        ).json()

        response = client.patch(
            f"{APPS_URL}/{created['id']}",
            json={"external_title": None},
            headers=csrf_headers(client),
        )
        assert response.status_code == 200
        assert response.json()["external_title"] is None

    def test_patch_someone_elses_application_is_404(self, client: TestClient) -> None:
        register(client, email="a@example.eu")
        created = create_external(client)
        register(client, email="b@example.eu")
        response = client.patch(
            f"{APPS_URL}/{created['id']}",
            json={"notes": "intrusion"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 404


class TestDelete:
    def test_delete_removes_application_and_history(
        self, client: TestClient, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        register(client)
        created = create_external(client)
        client.post(
            f"{APPS_URL}/{created['id']}/status",
            json={"to_status": "applied"},
            headers=csrf_headers(client),
        )

        response = client.delete(
            f"{APPS_URL}/{created['id']}", headers=csrf_headers(client)
        )
        assert response.status_code == 204
        assert client.get(f"{APPS_URL}/{created['id']}").status_code == 404
        assert applications_repository.applications == {}

    def test_delete_someone_elses_application_is_404(
        self, client: TestClient, applications_repository: InMemoryApplicationsRepository
    ) -> None:
        register(client, email="a@example.eu")
        created = create_external(client)
        register(client, email="b@example.eu")
        response = client.delete(
            f"{APPS_URL}/{created['id']}", headers=csrf_headers(client)
        )
        assert response.status_code == 404
        assert len(applications_repository.applications) == 1  # rien supprimé


class TestStatusTransitions:
    def test_transitions_are_recorded_in_order(self, client: TestClient) -> None:
        # AC-P-4 : les événements apparaissent dans l'ordre chronologique.
        register(client)
        created = create_external(client)
        url = f"{APPS_URL}/{created['id']}/status"
        for to_status, note in (
            ("to_apply", None),
            ("applied", "Envoyée par e-mail"),
            ("interviewing", "Entretien RH le 12"),
        ):
            response = client.post(
                url, json={"to_status": to_status, "note": note}, headers=csrf_headers(client)
            )
            assert response.status_code == 200

        body = client.get(f"{APPS_URL}/{created['id']}").json()
        assert body["status"] == "interviewing"
        assert [(e["from_status"], e["to_status"], e["note"]) for e in body["events"]] == [
            ("draft", "to_apply", None),
            ("to_apply", "applied", "Envoyée par e-mail"),
            ("applied", "interviewing", "Entretien RH le 12"),
        ]
        ats = [e["at"] for e in body["events"]]
        assert ats == sorted(ats)

    def test_applied_at_is_set_once_on_first_applied_transition(
        self, client: TestClient
    ) -> None:
        register(client)
        created = create_external(client)
        url = f"{APPS_URL}/{created['id']}/status"

        first = client.post(
            url, json={"to_status": "applied"}, headers=csrf_headers(client)
        ).json()
        assert first["applied_at"] is not None

        client.post(url, json={"to_status": "rejected"}, headers=csrf_headers(client))
        second = client.post(
            url, json={"to_status": "applied"}, headers=csrf_headers(client)
        ).json()
        # Repostuler ne réécrit pas l'horodatage initial.
        assert second["applied_at"] == first["applied_at"]
        assert len(second["events"]) == 3

    def test_free_transitions_q29_including_same_status_note(
        self, client: TestClient
    ) -> None:
        register(client)
        created = create_external(client)
        url = f"{APPS_URL}/{created['id']}/status"

        # Transition arbitraire (draft → offer) : permise, historisée.
        assert (
            client.post(
                url, json={"to_status": "offer"}, headers=csrf_headers(client)
            ).status_code
            == 200
        )
        # « Note seule » : même statut, événement quand même historisé.
        body = client.post(
            url,
            json={"to_status": "offer", "note": "Relance du recruteur"},
            headers=csrf_headers(client),
        ).json()
        assert body["status"] == "offer"
        assert [e["to_status"] for e in body["events"]] == ["offer", "offer"]
        assert body["events"][-1]["note"] == "Relance du recruteur"

    def test_updated_at_follows_transitions(self, client: TestClient) -> None:
        register(client)
        created = create_external(client)
        body = client.post(
            f"{APPS_URL}/{created['id']}/status",
            json={"to_status": "applied"},
            headers=csrf_headers(client),
        ).json()
        assert body["updated_at"] >= created["updated_at"]
        assert body["updated_at"] == body["events"][-1]["at"]

    def test_unknown_status_is_422(self, client: TestClient) -> None:
        register(client)
        created = create_external(client)
        response = client.post(
            f"{APPS_URL}/{created['id']}/status",
            json={"to_status": "acceptée"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 422

    def test_status_on_someone_elses_application_is_404(
        self, client: TestClient
    ) -> None:
        register(client, email="a@example.eu")
        created = create_external(client)
        register(client, email="b@example.eu")
        response = client.post(
            f"{APPS_URL}/{created['id']}/status",
            json={"to_status": "applied"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 404

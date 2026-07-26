"""Tests API du module profiles (TestClient, repository en mémoire)."""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.profiles.conftest import InMemoryProfilesRepository, make_profile

PROFILE_URL = "/api/v1/profile"

EXPERIENCE_PAYLOAD = {
    "title": "Développeuse backend",
    "company": "Boussole SAS",
    "start_date": "2020-01-01",
    "end_date": "2021-12-31",
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


def current_user_id(auth_repository: InMemoryAuthRepository) -> uuid.UUID:
    (user_id,) = auth_repository.users_by_id
    return user_id


class TestAuthAndCsrf:
    def test_routes_without_session_are_401_problem(self, client: TestClient) -> None:
        response = client.get(PROFILE_URL)
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")
        # Mutation sans session : le middleware CSRF répond avant l'auth (403).
        assert client.post(f"{PROFILE_URL}/validate").status_code == 403

    def test_mutation_without_csrf_header_is_403(self, client: TestClient) -> None:
        register(client)
        response = client.patch(PROFILE_URL, json={"headline": "Dev"})
        assert response.status_code == 403
        assert response.json()["type"].endswith("/csrf_invalid")


class TestGetProfile:
    def test_creates_empty_draft_on_the_fly(
        self, client: TestClient, profiles_repository: InMemoryProfilesRepository
    ) -> None:
        register(client)
        assert not profiles_repository.profiles_by_user

        response = client.get(PROFILE_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "draft"
        assert body["version"] == 1
        assert body["headline"] is None
        assert body["total_experience_years"] is None
        assert body["experiences"] == []
        assert body["educations"] == []
        assert body["skills"] == []
        assert body["languages"] == []
        # Le draft est persisté : le second GET renvoie le même profil.
        assert len(profiles_repository.profiles_by_user) == 1
        assert client.get(PROFILE_URL).json()["id"] == body["id"]


class TestPatchProfile:
    def test_updates_provided_fields_and_bumps_version(self, client: TestClient) -> None:
        register(client)
        response = client.patch(
            PROFILE_URL,
            json={"headline": "Dev backend", "seniority": "senior"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["headline"] == "Dev backend"
        assert body["seniority"] == "senior"
        assert body["summary"] is None
        assert body["version"] == 2

    def test_explicit_null_clears_field_absent_field_untouched(
        self, client: TestClient
    ) -> None:
        register(client)
        client.patch(
            PROFILE_URL,
            json={"headline": "Dev", "summary": "Résumé"},
            headers=csrf_headers(client),
        )
        response = client.patch(
            PROFILE_URL, json={"headline": None}, headers=csrf_headers(client)
        )
        body = response.json()
        assert body["headline"] is None  # null explicite = effacement
        assert body["summary"] == "Résumé"  # champ absent = inchangé
        assert body["version"] == 3

    def test_invalid_seniority_is_422_problem(self, client: TestClient) -> None:
        register(client)
        response = client.patch(
            PROFILE_URL, json={"seniority": "ninja"}, headers=csrf_headers(client)
        )
        assert response.status_code == 422
        assert response.headers["content-type"].startswith("application/problem+json")


class TestExperiences:
    def test_create_sets_user_input_provenance_and_total(self, client: TestClient) -> None:
        register(client)
        response = client.post(
            f"{PROFILE_URL}/experiences",
            json=EXPERIENCE_PAYLOAD,
            headers=csrf_headers(client),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["provenance"] == {"source": "user_input", "confidence": 1.0}

        profile = client.get(PROFILE_URL).json()
        assert profile["total_experience_years"] == 2.0
        assert profile["version"] == 2

    def test_overlapping_experiences_are_merged_in_total(self, client: TestClient) -> None:
        register(client)
        client.post(
            f"{PROFILE_URL}/experiences",
            json=EXPERIENCE_PAYLOAD,
            headers=csrf_headers(client),
        )
        # Chevauche entièrement 2021 : le total reste 2020→2022 = 3 ans.
        client.post(
            f"{PROFILE_URL}/experiences",
            json={**EXPERIENCE_PAYLOAD, "start_date": "2021-01-01",
                  "end_date": "2022-12-31"},
            headers=csrf_headers(client),
        )
        assert client.get(PROFILE_URL).json()["total_experience_years"] == 3.0

    def test_end_date_before_start_date_is_422(self, client: TestClient) -> None:
        register(client)
        response = client.post(
            f"{PROFILE_URL}/experiences",
            json={**EXPERIENCE_PAYLOAD, "end_date": "2019-01-01"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 422

    def test_patch_updates_fields_and_recomputes_total(self, client: TestClient) -> None:
        register(client)
        created = client.post(
            f"{PROFILE_URL}/experiences",
            json=EXPERIENCE_PAYLOAD,
            headers=csrf_headers(client),
        ).json()

        response = client.patch(
            f"{PROFILE_URL}/experiences/{created['id']}",
            json={**EXPERIENCE_PAYLOAD, "title": "Lead dev", "end_date": "2022-12-31"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Lead dev"

        profile = client.get(PROFILE_URL).json()
        assert profile["total_experience_years"] == 3.0
        assert profile["version"] == 3

    def test_delete_removes_and_resets_total_to_none(self, client: TestClient) -> None:
        register(client)
        created = client.post(
            f"{PROFILE_URL}/experiences",
            json=EXPERIENCE_PAYLOAD,
            headers=csrf_headers(client),
        ).json()

        response = client.delete(
            f"{PROFILE_URL}/experiences/{created['id']}", headers=csrf_headers(client)
        )
        assert response.status_code == 204
        profile = client.get(PROFILE_URL).json()
        assert profile["experiences"] == []
        assert profile["total_experience_years"] is None

    def test_unknown_experience_id_is_404_problem(self, client: TestClient) -> None:
        register(client)
        response = client.patch(
            f"{PROFILE_URL}/experiences/{uuid.uuid4()}",
            json=EXPERIENCE_PAYLOAD,
            headers=csrf_headers(client),
        )
        assert response.status_code == 404
        assert response.json()["type"].endswith("/not_found")


class TestEducations:
    def test_crud_roundtrip(self, client: TestClient) -> None:
        register(client)
        created = client.post(
            f"{PROFILE_URL}/educations",
            json={"degree": "Master informatique", "institution": "Université Lyon 1",
                  "start_year": 2016, "end_year": 2018},
            headers=csrf_headers(client),
        )
        assert created.status_code == 201
        body = created.json()
        assert body["provenance"]["source"] == "user_input"

        updated = client.patch(
            f"{PROFILE_URL}/educations/{body['id']}",
            json={"degree": "Master IA", "institution": "Université Lyon 1"},
            headers=csrf_headers(client),
        )
        assert updated.status_code == 200
        assert updated.json()["degree"] == "Master IA"

        deleted = client.delete(
            f"{PROFILE_URL}/educations/{body['id']}", headers=csrf_headers(client)
        )
        assert deleted.status_code == 204
        assert client.get(PROFILE_URL).json()["educations"] == []

    def test_end_year_before_start_year_is_422(self, client: TestClient) -> None:
        register(client)
        response = client.post(
            f"{PROFILE_URL}/educations",
            json={"degree": "Licence", "institution": "Fac",
                  "start_year": 2020, "end_year": 2018},
            headers=csrf_headers(client),
        )
        assert response.status_code == 422


class TestSkills:
    def test_create_and_duplicate_label_is_409(self, client: TestClient) -> None:
        register(client)
        first = client.post(
            f"{PROFILE_URL}/skills", json={"label": "Python"}, headers=csrf_headers(client)
        )
        assert first.status_code == 201
        assert first.json()["provenance"] == {"source": "user_input", "confidence": 1.0}

        duplicate = client.post(
            f"{PROFILE_URL}/skills", json={"label": "python"}, headers=csrf_headers(client)
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["type"].endswith("/duplicate_skill")

    def test_patch_and_delete(self, client: TestClient) -> None:
        register(client)
        created = client.post(
            f"{PROFILE_URL}/skills", json={"label": "Python"}, headers=csrf_headers(client)
        ).json()

        updated = client.patch(
            f"{PROFILE_URL}/skills/{created['id']}",
            json={"label": "FastAPI"},
            headers=csrf_headers(client),
        )
        assert updated.status_code == 200
        assert updated.json()["label"] == "FastAPI"

        assert (
            client.delete(
                f"{PROFILE_URL}/skills/{created['id']}", headers=csrf_headers(client)
            ).status_code
            == 204
        )
        assert client.get(PROFILE_URL).json()["skills"] == []


class TestLanguages:
    def test_create_normalizes_code_and_duplicate_is_409(self, client: TestClient) -> None:
        register(client)
        first = client.post(
            f"{PROFILE_URL}/languages",
            json={"lang_code": "FR", "level": "C2"},
            headers=csrf_headers(client),
        )
        assert first.status_code == 201
        assert first.json()["lang_code"] == "fr"  # normalisé ISO 639-1 minuscules

        duplicate = client.post(
            f"{PROFILE_URL}/languages",
            json={"lang_code": "fr", "level": "B2"},
            headers=csrf_headers(client),
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["type"].endswith("/duplicate_language")

    def test_invalid_cefr_level_is_422(self, client: TestClient) -> None:
        register(client)
        response = client.post(
            f"{PROFILE_URL}/languages",
            json={"lang_code": "fr", "level": "natif"},
            headers=csrf_headers(client),
        )
        assert response.status_code == 422

    def test_patch_and_delete(self, client: TestClient) -> None:
        register(client)
        created = client.post(
            f"{PROFILE_URL}/languages",
            json={"lang_code": "en", "level": "B2"},
            headers=csrf_headers(client),
        ).json()

        updated = client.patch(
            f"{PROFILE_URL}/languages/{created['id']}",
            json={"lang_code": "en", "level": "C1"},
            headers=csrf_headers(client),
        )
        assert updated.status_code == 200
        assert updated.json()["level"] == "C1"

        assert (
            client.delete(
                f"{PROFILE_URL}/languages/{created['id']}", headers=csrf_headers(client)
            ).status_code
            == 204
        )


class TestValidate:
    def _seed_extracted_profile(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        *,
        skills_count: int = 3,
    ) -> None:
        register(client)
        profiles_repository.add(
            make_profile(
                current_user_id(auth_repository),
                skills=[
                    (f"Compétence {i}", "cv_extraction", 0.7) for i in range(skills_count)
                ],
                experiences=[(date(2020, 1, 1), date(2021, 12, 31), "cv_extraction")],
                languages=[("fr", "C2", "cv_extraction")],
            )
        )

    def test_incomplete_profile_is_409_profile_incomplete(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        self._seed_extracted_profile(
            client, auth_repository, profiles_repository, skills_count=2
        )
        response = client.post(f"{PROFILE_URL}/validate", headers=csrf_headers(client))
        assert response.status_code == 409
        body = response.json()
        assert body["type"].endswith("/profile_incomplete")
        assert any(
            err["field"] == "skills" and "3" in err["message"] for err in body["errors"]
        )
        # AC-C-2 : le statut reste inchangé.
        assert client.get(PROFILE_URL).json()["status"] == "draft"

    def test_empty_profile_reports_both_missing_requirements(
        self, client: TestClient
    ) -> None:
        register(client)
        response = client.post(f"{PROFILE_URL}/validate", headers=csrf_headers(client))
        assert response.status_code == 409
        fields = {err["field"] for err in response.json()["errors"]}
        assert fields == {"skills", "experiences"}

    def test_validation_promotes_cv_extraction_to_user_confirmed(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        self._seed_extracted_profile(client, auth_repository, profiles_repository)
        response = client.post(f"{PROFILE_URL}/validate", headers=csrf_headers(client))
        assert response.status_code == 200
        body = response.json()
        # AC-C-1 : promotion en bloc, statut validé, version incrémentée.
        assert body["status"] == "validated"
        assert body["version"] == 2
        sources = {
            child["provenance"]["source"]
            for child in (*body["experiences"], *body["skills"], *body["languages"])
        }
        assert sources == {"user_confirmed"}
        # La confiance d'extraction est conservée (seule la source est promue).
        assert body["skills"][0]["provenance"]["confidence"] == 0.7
        profile = profiles_repository.profiles_by_user[current_user_id(auth_repository)]
        assert profile.validated_at is not None

    def test_user_input_children_are_not_promoted(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        register(client)
        profiles_repository.add(
            make_profile(
                current_user_id(auth_repository),
                skills=[
                    ("Python", "user_input", 1.0),
                    ("SQL", "cv_extraction", 0.5),
                    ("Docker", "user_input", 1.0),
                ],
                educations=[("Master", "user_input")],
            )
        )
        body = client.post(
            f"{PROFILE_URL}/validate", headers=csrf_headers(client)
        ).json()
        by_label = {s["label"]: s["provenance"]["source"] for s in body["skills"]}
        assert by_label == {
            "Python": "user_input",
            "SQL": "user_confirmed",
            "Docker": "user_input",
        }

    def test_edit_after_validation_keeps_validated_status_q23(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        self._seed_extracted_profile(client, auth_repository, profiles_repository)
        client.post(f"{PROFILE_URL}/validate", headers=csrf_headers(client))
        experience_id = client.get(PROFILE_URL).json()["experiences"][0]["id"]

        response = client.patch(
            f"{PROFILE_URL}/experiences/{experience_id}",
            json=EXPERIENCE_PAYLOAD,
            headers=csrf_headers(client),
        )
        assert response.status_code == 200
        # AC-C-4 / Q23 : champ édité → user_input, version++, statut inchangé.
        assert response.json()["provenance"] == {"source": "user_input", "confidence": 1.0}
        profile = client.get(PROFILE_URL).json()
        assert profile["status"] == "validated"
        assert profile["version"] == 3

"""Tests API du module matching (TestClient, fakes en mémoire — fin M3)."""

import uuid

from fastapi.testclient import TestClient

from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.matching_api.conftest import (
    InMemoryExplanationsRepository,
    InMemoryMatchingRepository,
    make_job,
    make_preferences,
    make_validated_profile,
)
from tests.unit.preferences.conftest import InMemoryPreferencesRepository
from tests.unit.profiles.conftest import InMemoryProfilesRepository, make_profile

MATCHES_URL = "/api/v1/matches"


def match_url(job_id: uuid.UUID) -> str:
    return f"/api/v1/jobs/{job_id}/match"


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


def setup_validated_user(
    client: TestClient,
    auth_repository: InMemoryAuthRepository,
    profiles_repository: InMemoryProfilesRepository,
    preferences_repository: InMemoryPreferencesRepository,
) -> uuid.UUID:
    """Inscrit un utilisateur avec profil validé + préférences par défaut."""
    register(client)
    user_id = current_user_id(auth_repository)
    profiles_repository.add(make_validated_profile(user_id))
    preferences_repository.by_user[user_id] = make_preferences()
    return user_id


def default_job_kwargs() -> dict:
    """Offre bien alignée sur le profil des tests (skills couvertes, Lyon…)."""
    return {
        "skills": [("Python", True), ("FastAPI", True)],
        "experience_min": 2.0,
        "experience_max": 8.0,
        "languages": [("fr", "B2", 0.9)],
    }


class TestAuthRequired:
    def test_match_without_session_is_401_problem(self, client: TestClient) -> None:
        response = client.get(match_url(uuid.uuid4()))
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")

    def test_matches_without_session_is_401(self, client: TestClient) -> None:
        assert client.get(MATCHES_URL).status_code == 401


class TestGetMatch:
    def test_draft_profile_is_409_profile_not_validated(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        register(client)
        profiles_repository.add(make_profile(current_user_id(auth_repository), status="draft"))
        job = matching_repository.add(make_job(**default_job_kwargs()))

        response = client.get(match_url(job.id))
        assert response.status_code == 409
        assert response.json()["type"].endswith("/profile_not_validated")

    def test_missing_profile_is_409(
        self,
        client: TestClient,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        register(client)
        job = matching_repository.add(make_job(**default_job_kwargs()))
        assert client.get(match_url(job.id)).status_code == 409

    def test_unknown_or_withdrawn_job_is_404(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        withdrawn = matching_repository.add(
            make_job(status="withdrawn", **default_job_kwargs())
        )
        assert client.get(match_url(uuid.uuid4())).status_code == 404
        assert client.get(match_url(withdrawn.id)).status_code == 404

    def test_returns_contract_conformant_match_result(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))

        response = client.get(match_url(job.id))
        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == str(job.id)
        assert body["profile_version"] == 3
        assert body["scoring_version"] == "1.3.0"
        assert 0 <= body["score"] <= 100
        assert 0 <= body["confidence"] <= 100
        assert isinstance(body["low_data"], bool)
        assert body["blocking_criteria"] == []
        # 12 dimensions détaillées, chacune avec poids/statut/détails.
        assert len(body["dimensions"]) == 12
        by_name = {d["dimension"]: d for d in body["dimensions"]}
        assert by_name["skills_required"]["known"] is True
        assert by_name["skills_required"]["subscore"] == 1.0
        assert sorted(by_name["skills_required"]["details"]["matched"]) == [
            "FastAPI",
            "Python",
        ]
        # Sans embeddings au M3 : title_similarity inconnue (k=0), vocabulaire
        # du contrat (job_not_provided : pas d'embedding d'offre fourni).
        unknown = {u["dimension"]: u for u in body["unknown_dimensions"]}
        assert unknown["title_similarity"]["reason"] in (
            "job_not_provided",
            "profile_not_provided",
            "low_extraction_confidence",
        )

    def test_second_call_hits_cache_engine_called_once(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        engine_calls: list,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))

        first = client.get(match_url(job.id)).json()
        second = client.get(match_url(job.id)).json()
        assert len(engine_calls) == 1  # le 2e appel ne recalcule pas
        assert first == second

    def test_profile_version_change_invalidates_cache(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        engine_calls: list,
    ) -> None:
        user_id = setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))

        assert client.get(match_url(job.id)).json()["profile_version"] == 3
        profiles_repository.profiles_by_user[user_id].version = 4  # profil modifié

        response = client.get(match_url(job.id))
        assert response.json()["profile_version"] == 4
        assert len(engine_calls) == 2  # recalcul paresseux

    def test_scoring_version_change_invalidates_cache(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        engine_calls: list,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))

        client.get(match_url(job.id))
        # Résultat calculé sous une ancienne version de scoring → recalcul.
        (key,) = matching_repository.results
        matching_repository.results[key].scoring_version = "0.9.0"

        assert client.get(match_url(job.id)).json()["scoring_version"] == "1.3.0"
        assert len(engine_calls) == 2

    def test_canonical_skill_labels_via_taxonomy(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        user_id = setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        # Compétence profil rapprochée de la taxonomie : « py3 » → « Python ».
        profile = profiles_repository.profiles_by_user[user_id]
        skill_id = uuid.uuid4()
        profile.skills[0].skill_id = skill_id
        profile.skills[0].label_raw = "py3"
        matching_repository.skills[skill_id] = "Python"
        job = matching_repository.add(make_job(**default_job_kwargs()))

        body = client.get(match_url(job.id)).json()
        by_name = {d["dimension"]: d for d in body["dimensions"]}
        assert "Python" in by_name["skills_required"]["details"]["matched"]


class TestListMatches:
    def test_draft_profile_is_409(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
    ) -> None:
        register(client)
        profiles_repository.add(make_profile(current_user_id(auth_repository), status="draft"))
        assert client.get(MATCHES_URL).status_code == 409

    def test_sorted_by_score_desc_with_match_summary(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        good = matching_repository.add(make_job(**default_job_kwargs()))
        weak = matching_repository.add(
            make_job(
                title="Comptable général",
                skills=[("Cobol", True), ("SAP", True)],
                experience_min=2.0,
                experience_max=8.0,
            )
        )

        response = client.get(MATCHES_URL)
        assert response.status_code == 200
        items = response.json()["items"]
        assert [item["id"] for item in items] == [str(good.id), str(weak.id)]
        scores = [item["match"]["score"] for item in items]
        assert scores[0] > scores[1]
        first = items[0]
        assert first["match"]["has_blocking"] is False
        assert isinstance(first["match"]["confidence"], int)
        assert first["salary_label"] == "45–55 k€"
        assert first["locations"] == ["Lyon"]

    def test_min_score_filters(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        good = matching_repository.add(make_job(**default_job_kwargs()))
        matching_repository.add(
            make_job(title="Comptable", skills=[("Cobol", True), ("SAP", True)])
        )

        scores = {
            item["id"]: item["match"]["score"]
            for item in client.get(MATCHES_URL).json()["items"]
        }
        threshold = scores[str(good.id)]  # exclut l'offre la plus faible
        response = client.get(MATCHES_URL, params={"min_score": threshold})
        assert [item["id"] for item in response.json()["items"]] == [str(good.id)]

    def test_include_blocked_false_excludes_blocked_jobs(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        user_id = setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        # Minimum strict 40 k€ → l'offre à 28-30 k€ est bloquée (RM-D-3).
        preferences_repository.by_user[user_id] = make_preferences(salary_min_strict=40000)
        fine = matching_repository.add(make_job(**default_job_kwargs()))
        blocked = matching_repository.add(
            make_job(salary_min=28000, salary_max=30000, **default_job_kwargs())
        )

        default = client.get(MATCHES_URL).json()["items"]
        by_id = {item["id"]: item for item in default}
        assert by_id[str(blocked.id)]["match"]["has_blocking"] is True
        assert by_id[str(fine.id)]["match"]["has_blocking"] is False

        filtered = client.get(MATCHES_URL, params={"include_blocked": "false"}).json()
        assert [item["id"] for item in filtered["items"]] == [str(fine.id)]

    def test_prefilter_keeps_unknown_and_drops_expired(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        """Le contrat INCONNU reste (l'inconnu n'est pas un fait négatif) ;
        une offre expirée part, quel que soit son contrat."""
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        kept = matching_repository.add(make_job(**default_job_kwargs()))
        unknown_contract = matching_repository.add(
            make_job(contract=None, **default_job_kwargs())
        )
        matching_repository.add(
            make_job(status="expired", contract="internship", **default_job_kwargs())
        )

        ids = {item["id"] for item in client.get(MATCHES_URL).json()["items"]}
        assert ids == {str(kept.id), str(unknown_contract.id)}

    def test_a_non_strict_preference_still_sees_other_contracts(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        """LE test qui aurait attrapé le défaut (voir ``MAX_WIDENED_JOBS``).

        ``contract_strict`` vaut ``false`` par défaut en base : « je préfère
        un CDI mais je reste ouvert ». Le pré-filtre SQL rendait cette option
        inatteignable — la personne ne voyait jamais un seul CDD.
        """
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        user_id = uuid.UUID(client.get("/api/v1/me").json()["id"])
        preferences_repository.by_user[user_id] = make_preferences(
            contract_strict=False
        )
        autre_contrat = matching_repository.add(
            make_job(contract="internship", **default_job_kwargs())
        )

        ids = {item["id"] for item in client.get(MATCHES_URL).json()["items"]}
        assert str(autre_contrat.id) in ids, (
            "l'offre est masquée alors que la préférence de contrat n'est pas "
            "stricte : contract_strict n'a aucun effet observable"
        )

    def test_a_strict_preference_hides_other_contracts(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        """La contrepartie, et c'est elle qui donne son sens à l'option :
        « strict » veut dire « ne me montre que ça »."""
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        user_id = uuid.UUID(client.get("/api/v1/me").json()["id"])
        preferences_repository.by_user[user_id] = make_preferences(
            contract_strict=True
        )
        garde = matching_repository.add(make_job(**default_job_kwargs()))
        matching_repository.add(make_job(contract="internship", **default_job_kwargs()))

        ids = {item["id"] for item in client.get(MATCHES_URL).json()["items"]}
        assert ids == {str(garde.id)}

    def test_cursor_pagination_no_overlap(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        for _ in range(3):
            matching_repository.add(make_job(**default_job_kwargs()))

        first = client.get(MATCHES_URL, params={"limit": 2}).json()
        assert len(first["items"]) == 2
        assert first["next_cursor"] is not None

        second = client.get(
            MATCHES_URL, params={"limit": 2, "cursor": first["next_cursor"]}
        ).json()
        assert len(second["items"]) == 1
        assert second["next_cursor"] is None
        seen = [item["id"] for item in first["items"] + second["items"]]
        assert len(seen) == len(set(seen)) == 3

    def test_invalid_cursor_is_422(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        response = client.get(MATCHES_URL, params={"cursor": "n'importe quoi"})
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid_cursor")

    def test_lazy_scoring_fills_cache_once(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        engine_calls: list,
    ) -> None:
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        matching_repository.add(make_job(**default_job_kwargs()))
        matching_repository.add(make_job(**default_job_kwargs()))

        client.get(MATCHES_URL)
        assert len(engine_calls) == 2
        client.get(MATCHES_URL)
        assert len(engine_calls) == 2  # cache réutilisé, aucun recalcul

    def test_saved_state_is_populated(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        user_id = setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))
        matching_repository.saved[(user_id, job.id)] = "saved"

        (item,) = client.get(MATCHES_URL).json()["items"]
        assert item["saved_state"] == "saved"


class TestPreferencesChangedHook:
    def test_put_preferences_invalidates_match_results_and_explanations(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
        explanations_repository: InMemoryExplanationsRepository,
        engine_calls: list,
    ) -> None:
        """Hook par défaut branché (RM-D-4) : PUT /preferences → delete du cache."""
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))
        client.get(match_url(job.id))
        client.post(f"/api/v1/jobs/{job.id}/explanation", headers=csrf_headers(client))
        assert matching_repository.results
        assert explanations_repository.rows

        response = client.put(
            "/api/v1/preferences", json={}, headers=csrf_headers(client)
        )
        assert response.status_code == 200
        assert matching_repository.results == {}
        assert explanations_repository.rows == {}  # cascade FK émulée

        # Prochain accès : recalcul paresseux.
        client.get(match_url(job.id))
        assert len(engine_calls) == 2

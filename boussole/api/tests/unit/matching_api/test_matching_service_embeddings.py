"""Embeddings vus depuis ``MatchingService`` — le chemin réellement pris en prod.

``test_matching_embeddings.py`` appelle ``candidate_input_from`` /
``job_input_from`` DIRECTEMENT, en leur passant les vecteurs à la main. Cet
angle mort a laissé passer deux régressions silencieuses : le service ne
transmettait les vecteurs de compétences qu'au CANDIDAT (le crédit « proche »
exige les deux côtés → dictionnaire toujours vide) et ne lisait jamais
``preference_titles.embedding`` (06 §2.3 impose le max des cosinus PAR
intitulé ; l'agrégé ``profiles.embedding`` noie l'intitulé le mieux ciblé).

Les tests ci-dessous passent donc par l'API — service, adaptateurs et moteur
réels, seul le repository est en mémoire.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.modules.jobs.models import JobSkill as JobSkillRow
from app.modules.profiles.models import ProfileSkill
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.matching_api.conftest import InMemoryMatchingRepository, make_job
from tests.unit.matching_api.test_matching_api import (
    MATCHES_URL,
    default_job_kwargs,
    match_url,
    setup_validated_user,
)
from tests.unit.matching_api.test_matching_embeddings import unit_vector, vector_at_cosine
from tests.unit.preferences.conftest import InMemoryPreferencesRepository
from tests.unit.profiles.conftest import InMemoryProfilesRepository


def dimension(body: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in body["dimensions"] if item["dimension"] == name)


class TestCreditCompetenceProcheBoutEnBout:
    """M3 — le crédit « proche » doit tomber via ``MatchingService``."""

    @pytest.fixture
    def scenario(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> dict[str, Any]:
        """Offre exigeant « React.js », profil portant « React » — cosinus 0,99.

        Les deux compétences sont VECTORISÉES en base (``skills.embedding``) :
        le crédit « proche » (seuil 0,75) doit s'appliquer.
        """
        user_id = setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        react_js_id, react_id = uuid.uuid4(), uuid.uuid4()

        job = matching_repository.add(make_job(skills=[]))
        job.skills = [
            JobSkillRow(
                id=uuid.uuid4(), job_posting_id=job.id, skill_id=react_js_id,
                label_raw="React.js", required=True, confidence=1.0,
            )
        ]
        profile = profiles_repository.profiles_by_user[user_id]
        profile.skills = [
            ProfileSkill(
                id=uuid.uuid4(), profile_id=profile.id, skill_id=react_id,
                label_raw="React", source="user_input", confidence=1.0,
            )
        ]
        matching_repository.skills = {react_js_id: "React.js", react_id: "React"}
        matching_repository.skill_vectors = {
            react_js_id: unit_vector(0.0),
            react_id: vector_at_cosine(0.99),
        }
        return {"user_id": user_id, "job": job}

    def test_le_credit_proche_tombe_via_le_service(
        self, client: TestClient, scenario: dict[str, Any]
    ) -> None:
        """Régression M3 : sans ``skill_embeddings=`` côté OFFRE, le moteur
        n'a aucun vecteur à comparer → subscore 0,0 et « React.js » manquant."""
        response = client.get(match_url(scenario["job"].id))
        assert response.status_code == 200

        scored = dimension(response.json(), "skills_required")
        assert scored["subscore"] == pytest.approx(0.5)
        assert scored["details"]["missing"] == []
        related = scored["details"]["related"]
        assert len(related) == 1
        assert related[0]["required"] == "React.js"
        assert related[0]["via"] == "react"
        assert related[0]["similarity"] == pytest.approx(0.99, abs=1e-3)

    def test_exact_only_quand_la_taxonomie_n_est_pas_vectorisee(
        self,
        client: TestClient,
        matching_repository: InMemoryMatchingRepository,
        scenario: dict[str, Any],
    ) -> None:
        """Non-régression : aucun vecteur en base → exact-only, comme avant."""
        matching_repository.skill_vectors = {}

        scored = dimension(
            client.get(match_url(scenario["job"].id)).json(), "skills_required"
        )
        assert scored["subscore"] == pytest.approx(0.0)
        assert scored["details"]["missing"] == ["React.js"]


class TestSimilariteMetierBoutEnBout:
    """M4 — max des cosinus sur les intitulés cibles (06 §2.3)."""

    @pytest.fixture
    def scenario(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> dict[str, Any]:
        """Le vecteur AGRÉGÉ du profil est loin de l'offre (cos 0,30 → 0,0),
        mais UN intitulé cible est quasi identique (cos 0,90 → 1,0)."""
        user_id = setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        job = matching_repository.add(make_job(**default_job_kwargs()))
        job.embedding = unit_vector(0.0)
        profiles_repository.profiles_by_user[user_id].embedding = vector_at_cosine(0.30)
        matching_repository.title_vectors[user_id] = [
            vector_at_cosine(0.10),  # « chef de projet » — hors sujet
            vector_at_cosine(0.90),  # l'intitulé RÉELLEMENT visé
        ]
        return {"user_id": user_id, "job": job}

    def test_le_max_des_cosinus_par_intitule_est_utilise(
        self, client: TestClient, scenario: dict[str, Any]
    ) -> None:
        """Régression M4 : sans ``preference_title_embeddings``, seul l'agrégé
        (cos 0,30 ≤ 0,55) compte → le candidat le mieux ciblé prend 0 sur 15."""
        scored = dimension(
            client.get(match_url(scenario["job"].id)).json(), "title_similarity"
        )
        assert scored["known"] is True
        assert scored["subscore"] == pytest.approx(1.0)

    def test_agrege_seul_quand_aucun_intitule_n_est_vectorise(
        self,
        client: TestClient,
        matching_repository: InMemoryMatchingRepository,
        scenario: dict[str, Any],
    ) -> None:
        """Non-régression : ``preference_titles.embedding`` vide → le vecteur
        agrégé reste la seule source, exactement comme avant M4."""
        matching_repository.title_vectors.clear()

        scored = dimension(
            client.get(match_url(scenario["job"].id)).json(), "title_similarity"
        )
        assert scored["known"] is True
        assert scored["subscore"] == pytest.approx(0.0)


class TestChargementGroupeHorsBoucle:
    """Mineur — les lectures de vecteurs ne doivent pas être faites par offre."""

    def test_les_vecteurs_sont_lus_une_seule_fois_pour_toute_la_page(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        """Régression perf : appelées dans la boucle de ``list_matches``, ces
        méthodes tiraient jusqu'à 200 requêtes de ``vector(1024)`` par page."""
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        for _ in range(6):
            matching_repository.add(make_job(**default_job_kwargs()))
        matching_repository.calls.clear()

        response = client.get(MATCHES_URL, params={"limit": 6})
        assert response.status_code == 200
        assert len(response.json()["items"]) == 6

        assert matching_repository.calls == {
            "skill_labels": 1,
            "skill_embeddings": 1,
            "preference_title_embeddings": 1,
        }

    def test_aucune_lecture_de_vecteurs_quand_tout_est_en_cache(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        preferences_repository: InMemoryPreferencesRepository,
        matching_repository: InMemoryMatchingRepository,
    ) -> None:
        """Page entièrement servie par ``match_results`` → zéro requête vecteur."""
        setup_validated_user(
            client, auth_repository, profiles_repository, preferences_repository
        )
        for _ in range(3):
            matching_repository.add(make_job(**default_job_kwargs()))
        assert client.get(MATCHES_URL).status_code == 200  # remplit le cache
        matching_repository.calls.clear()

        assert client.get(MATCHES_URL).status_code == 200
        assert matching_repository.calls == {}

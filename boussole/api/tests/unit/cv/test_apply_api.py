"""Tests de POST /cv-documents/{id}/apply 🟡 — fusion proposition → profil.

Invariants (F-B alt. 7, RM-B-1, RM-C-4) : champs existants ``user_input`` /
``user_confirmed`` JAMAIS écrasés ; ajouts en ``cv_extraction`` avec
confidence ; ``version``++ ; ``total_experience_years`` recalculé.
"""

import json
import uuid
from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from app.modules.profiles.cv.models import CvDocument, ExtractionRun
from app.modules.profiles.cv.service import PDF_MIME
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.cv.conftest import InMemoryCvRepository, InMemoryObjectStorage
from tests.unit.cv.test_upload_api import CV_URL, csrf_headers, register
from tests.unit.profiles.conftest import InMemoryProfilesRepository, make_profile

EXTRACTION: dict[str, Any] = {
    "headline": "Développeuse backend senior",
    "summary": "10 ans de Python.",
    "experiences": [
        {
            "title": "Développeuse Python",
            "company": "Acme",
            "start_date": "2020",
            "end_date": "2022-06",
            "description": "API FastAPI",
            "confidence": 0.85,
            "evidence": {"quote": "Développeuse Python chez Acme"},
        },
        {
            # Doublon d'une expérience existante du profil (mêmes titre,
            # entreprise, date de début) — ne doit PAS écraser l'existant.
            "title": "Poste 0",
            "company": "Acme",
            "start_date": "2018-01",
            "end_date": None,
            "description": "version extraite — à ignorer",
            "confidence": 0.5,
            "evidence": {"quote": "Poste 0"},
        },
    ],
    "educations": [
        {
            "degree": "Master Informatique",
            "institution": "Université de Lyon",
            "start_year": 2013,
            "end_year": 2015,
            "confidence": 0.9,
            "evidence": {"quote": "Master Informatique — Lyon"},
        }
    ],
    "skills": [
        {"label": "Python", "confidence": 0.7, "evidence": {"quote": "Python"}},
        {"label": "FastAPI", "confidence": 0.8, "evidence": {"quote": "FastAPI"}},
    ],
    "languages": [
        {"lang_code": "en", "level": "C1", "confidence": 0.75, "evidence": None}
    ],
    "warnings": [],
}


def seed_parsed_document(
    cv_repository: InMemoryCvRepository,
    storage: InMemoryObjectStorage,
    user_id: uuid.UUID,
    extraction: dict[str, Any] | None = None,
) -> CvDocument:
    document = CvDocument(
        id=uuid.uuid4(),
        user_id=user_id,
        file_key=f"cv/{user_id}/doc/original.pdf",
        filename="cv.pdf",
        mime_type=PDF_MIME,
        size_bytes=1234,
        status="parsed",
    )
    cv_repository.documents[document.id] = document
    output_key = f"cv/{user_id}/{document.id}/extraction/run.json"
    storage.put(output_key, json.dumps(extraction or EXTRACTION).encode())
    cv_repository.runs.append(
        ExtractionRun(
            id=uuid.uuid4(),
            cv_document_id=document.id,
            prompt_version="extract_cv/1.0.0",
            model="claude-sonnet-5",
            status="success",
            output_key=output_key,
        )
    )
    return document


def current_user_id(auth_repository: InMemoryAuthRepository) -> uuid.UUID:
    (user_id,) = auth_repository.users_by_id
    return user_id


class TestApply:
    def test_merge_never_overwrites_user_fields_and_bumps_version(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        profiles_repository: InMemoryProfilesRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        register(client)
        user_id = current_user_id(auth_repository)
        # Profil existant : compétence Python (user_input), expérience
        # « Poste 0 @ Acme » (user_confirmed), headline déjà saisie.
        profile = make_profile(
            user_id,
            version=3,
            skills=[("Python", "user_input", 1.0)],
            experiences=[(date(2018, 1, 1), None, "user_confirmed")],
        )
        profile.headline = "Ma headline à moi"
        profiles_repository.add(profile)
        document = seed_parsed_document(cv_repository, storage, user_id)

        response = client.post(
            f"{CV_URL}/{document.id}/apply", headers=csrf_headers(client)
        )
        assert response.status_code == 200
        body = response.json()

        # version++ (RM-C-4), profil inchangé côté statut.
        assert body["version"] == 4

        # headline existante JAMAIS écrasée ; summary vide → posée.
        assert body["headline"] == "Ma headline à moi"
        assert body["summary"] == "10 ans de Python."

        # Compétence existante user_input intacte ; FastAPI ajoutée en
        # cv_extraction avec la confidence de l'extraction.
        skills = {skill["label"]: skill["provenance"] for skill in body["skills"]}
        assert skills["Python"] == {"source": "user_input", "confidence": 1.0}
        assert skills["FastAPI"] == {"source": "cv_extraction", "confidence": 0.8}

        # Expérience doublon ignorée (description existante intacte),
        # nouvelle expérience ajoutée en cv_extraction.
        experiences = body["experiences"]
        assert len(experiences) == 2
        existing = next(e for e in experiences if e["title"] == "Poste 0")
        assert existing["provenance"]["source"] == "user_confirmed"
        assert existing["description"] != "version extraite — à ignorer"
        added = next(e for e in experiences if e["title"] == "Développeuse Python")
        assert added["provenance"] == {"source": "cv_extraction", "confidence": 0.85}
        assert added["start_date"] == "2020-01-01"  # YYYY → 1er janvier 🟡
        assert added["end_date"] == "2022-06-01"

        # Formation et langue ajoutées ; total recalculé (≥ 2018 → ~8 ans).
        assert body["educations"][0]["provenance"]["source"] == "cv_extraction"
        assert body["languages"][0]["lang_code"] == "en"
        assert body["total_experience_years"] is not None

    def test_apply_is_idempotent_on_duplicates(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        profiles_repository: InMemoryProfilesRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        register(client)
        user_id = current_user_id(auth_repository)
        document = seed_parsed_document(cv_repository, storage, user_id)

        first = client.post(f"{CV_URL}/{document.id}/apply", headers=csrf_headers(client))
        second = client.post(f"{CV_URL}/{document.id}/apply", headers=csrf_headers(client))
        assert first.status_code == second.status_code == 200
        # Ré-appliquer ne duplique rien (doublons ignorés), mais version++.
        assert len(second.json()["skills"]) == len(first.json()["skills"]) == 2
        assert len(second.json()["experiences"]) == len(first.json()["experiences"])
        assert second.json()["version"] == first.json()["version"] + 1

    def test_apply_creates_draft_profile_if_missing(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        profiles_repository: InMemoryProfilesRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        register(client)
        user_id = current_user_id(auth_repository)
        document = seed_parsed_document(cv_repository, storage, user_id)
        assert not profiles_repository.profiles_by_user

        response = client.post(
            f"{CV_URL}/{document.id}/apply", headers=csrf_headers(client)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "draft"
        assert {s["label"] for s in body["skills"]} == {"Python", "FastAPI"}
        assert all(
            s["provenance"]["source"] == "cv_extraction" for s in body["skills"]
        )
        # Le profil référence le CV source (D05).
        assert profiles_repository.profiles_by_user[user_id].source_cv_id == document.id

    def test_selective_apply_only_merges_checked_items(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        profiles_repository: InMemoryProfilesRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        """Cases à cocher par item (04 Flux 1 §5) : seuls les items cochés
        sont fusionnés — les autres sont ABSENTS du profil."""
        register(client)
        user_id = current_user_id(auth_repository)
        document = seed_parsed_document(cv_repository, storage, user_id)

        response = client.post(
            f"{CV_URL}/{document.id}/apply",
            headers=csrf_headers(client),
            json={
                "item_ids": ["experience:0", "skill:1"],
                "include_headline": False,
                "include_summary": False,
            },
        )
        assert response.status_code == 200
        body = response.json()

        # Items cochés fusionnés…
        assert [e["title"] for e in body["experiences"]] == ["Développeuse Python"]
        assert [s["label"] for s in body["skills"]] == ["FastAPI"]
        # …items non cochés ABSENTS, headline/summary exclus explicitement.
        assert body["educations"] == []
        assert body["languages"] == []
        assert body["headline"] is None
        assert body["summary"] is None

    def test_selective_apply_unknown_item_id_is_silently_ignored(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        profiles_repository: InMemoryProfilesRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        """Id inconnu (item disparu d'une ré-extraction…) → ignoré 🟡, pas d'erreur."""
        register(client)
        user_id = current_user_id(auth_repository)
        document = seed_parsed_document(cv_repository, storage, user_id)

        response = client.post(
            f"{CV_URL}/{document.id}/apply",
            headers=csrf_headers(client),
            json={"item_ids": ["skill:0", "skill:999", "bogus:0"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert [s["label"] for s in body["skills"]] == ["Python"]
        assert body["experiences"] == []
        # headline/summary incluses par défaut (include_* = True).
        assert body["headline"] == "Développeuse backend senior"
        assert body["summary"] == "10 ans de Python."

    def test_apply_with_empty_json_body_applies_everything(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        profiles_repository: InMemoryProfilesRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        """``{}`` ≡ corps absent : ``item_ids`` None = tout appliquer."""
        register(client)
        user_id = current_user_id(auth_repository)
        document = seed_parsed_document(cv_repository, storage, user_id)

        response = client.post(
            f"{CV_URL}/{document.id}/apply", headers=csrf_headers(client), json={}
        )
        assert response.status_code == 200
        body = response.json()
        assert {s["label"] for s in body["skills"]} == {"Python", "FastAPI"}
        assert len(body["experiences"]) == 2
        assert len(body["educations"]) == 1
        assert len(body["languages"]) == 1

    def test_selective_apply_never_overwrites_user_fields(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        profiles_repository: InMemoryProfilesRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        """La sélection ne change RIEN aux règles de fusion : un item coché
        qui doublonne un champ ``user_confirmed`` existant reste ignoré."""
        register(client)
        user_id = current_user_id(auth_repository)
        profile = make_profile(
            user_id,
            version=1,
            experiences=[(date(2018, 1, 1), None, "user_confirmed")],
        )
        profiles_repository.add(profile)
        document = seed_parsed_document(cv_repository, storage, user_id)

        # experience:1 = doublon « Poste 0 @ Acme » — coché mais jamais écrasé.
        response = client.post(
            f"{CV_URL}/{document.id}/apply",
            headers=csrf_headers(client),
            json={"item_ids": ["experience:1"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["experiences"]) == 1
        existing = body["experiences"][0]
        assert existing["provenance"]["source"] == "user_confirmed"
        assert existing["description"] != "version extraite — à ignorer"

    def test_proposal_item_ids_and_evidence_stable_across_reads(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        """Deux GET successifs → mêmes ``item_id`` (déterministes, indexés sur
        la sortie d'extraction stockée) + ``evidence_quote`` exposée."""
        register(client)
        user_id = current_user_id(auth_repository)
        document = seed_parsed_document(cv_repository, storage, user_id)

        first = client.get(f"{CV_URL}/{document.id}").json()["proposal"]
        second = client.get(f"{CV_URL}/{document.id}").json()["proposal"]
        assert first == second

        assert [e["item_id"] for e in first["experiences"]] == [
            "experience:0",
            "experience:1",
        ]
        assert [e["item_id"] for e in first["educations"]] == ["education:0"]
        assert [s["item_id"] for s in first["skills"]] == ["skill:0", "skill:1"]
        assert [lang["item_id"] for lang in first["languages"]] == ["language:0"]

        # Citation source de l'extraction exposée pour la revue (RM-B-5).
        assert first["experiences"][0]["evidence_quote"] == (
            "Développeuse Python chez Acme"
        )
        assert first["educations"][0]["evidence_quote"] == "Master Informatique — Lyon"
        assert first["skills"][1]["evidence_quote"] == "FastAPI"
        # Langue sans evidence dans l'extraction → None.
        assert first["languages"][0]["evidence_quote"] is None

    def test_apply_on_unparsed_document_is_409(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        cv_repository: InMemoryCvRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        register(client)
        user_id = current_user_id(auth_repository)
        document = seed_parsed_document(cv_repository, storage, user_id)
        document.status = "parsing"

        response = client.post(
            f"{CV_URL}/{document.id}/apply", headers=csrf_headers(client)
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/cv_not_parsed")

    def test_apply_on_foreign_document_is_404(
        self,
        client: TestClient,
        cv_repository: InMemoryCvRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        register(client)
        foreign = seed_parsed_document(cv_repository, storage, uuid.uuid4())
        response = client.post(
            f"{CV_URL}/{foreign.id}/apply", headers=csrf_headers(client)
        )
        assert response.status_code == 404

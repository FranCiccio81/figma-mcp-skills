"""Tests du contrôle d'ancrage (RM-L-2, 08 §5.2) et de la minimisation (D09)."""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.ai.providers.fake import FakeProvider
from app.modules.profiles.models import Profile
from tests.unit.conftest import InMemoryAuthRepository
from tests.unit.generation.conftest import (
    GENERATIONS_URL,
    InMemoryGenerationRepository,
    csrf_headers,
    post_generation,
    run_generation,
    setup_validated_user,
)
from tests.unit.jobs.conftest import make_posting
from tests.unit.profiles.conftest import InMemoryProfilesRepository


def skill_ref(profile: Profile, label: str) -> str:
    (skill,) = [s for s in profile.skills if s.label_raw == label]
    return f"skill:{skill.id}"


def experience_ref(profile: Profile) -> str:
    return f"experience:{profile.experiences[0].id}"


def start_generation(
    client: TestClient,
    generation_repository: InMemoryGenerationRepository,
    *,
    doc_type: str = "email",
) -> uuid.UUID:
    job_id = None
    if doc_type != "cv_optimization":
        job_id = generation_repository.add_job(make_posting()).id
    response = post_generation(client, doc_type=doc_type, job_id=job_id)
    assert response.status_code == 202
    return uuid.UUID(response.json()["id"])


class TestClaimsAnchoring:
    def test_anchored_claims_pass(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {
            "subject": "Candidature",
            "body": "Je maîtrise Python et j'ai une expérience backend.",
            "claims": [
                {"claim": "maîtrise de Python", "profile_ref": skill_ref(profile, "Python")},
                {"claim": "expérience backend", "profile_ref": experience_ref(profile)},
                {"claim": "résumé du parcours", "profile_ref": "summary"},
            ],
        }
        document_id = start_generation(client, generation_repository)
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "draft", "anchoring": "passed"}
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert body["anchoring_check"]["status"] == "passed"
        assert body["anchoring_check"]["unanchored_claims"] == []
        assert len(body["content"]["claims"]) == 3

    def test_unanchored_claim_fails_and_blocks_validation(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        """AC-L-2 : un claim inventé (« expert Kubernetes ») ne passe jamais."""
        setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {
            "subject": "Candidature",
            "body": "Je suis expert Kubernetes.",
            "claims": [
                {"claim": "expert Kubernetes", "profile_ref": f"skill:{uuid.uuid4()}"},
            ],
        }
        document_id = start_generation(client, generation_repository)
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "draft", "anchoring": "failed"}
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert body["status"] == "draft"
        assert body["anchoring_check"]["status"] == "failed"
        assert "expert Kubernetes" in body["anchoring_check"]["unanchored_claims"][0]

        # Jamais présenté comme prêt : validation bloquée…
        validate = client.post(
            f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client)
        )
        assert validate.status_code == 409
        assert validate.json()["type"].endswith("generation_not_anchored")
        # … donc export impossible aussi (jamais exporté tant que failed).
        export = client.post(
            f"{GENERATIONS_URL}/{document_id}/export",
            json={"format": "text"},
            headers=csrf_headers(client),
        )
        assert export.status_code == 409

    def test_summary_ref_invalid_when_profile_has_no_summary(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        profile.summary = None
        canned_outputs["generate_letter"] = {
            "body": "Comme le résume mon parcours…",
            "claims": [{"claim": "résumé", "profile_ref": "summary"}],
        }
        job = generation_repository.add_job(make_posting())
        document_id = uuid.UUID(
            post_generation(client, doc_type="cover_letter", job_id=job.id).json()["id"]
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report["anchoring"] == "failed"


class TestManualEditLiftsAnchoring:
    def test_patch_clears_check_and_allows_validation(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {
            "subject": "Candidature",
            "body": "Je suis expert Kubernetes.",
            "claims": [
                {"claim": "expert Kubernetes", "profile_ref": f"skill:{uuid.uuid4()}"},
            ],
        }
        document_id = start_generation(client, generation_repository)
        run_generation(document_id, generation_repository, profiles_repository, llm_provider)

        patched = client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": {"subject": "Candidature", "body": "Texte repris à la main."}},
            headers=csrf_headers(client),
        )
        assert patched.status_code == 200
        body = patched.json()
        # Q6 🟡 : l'édition manuelle lève le contrôle — check null + note.
        assert body["anchoring_check"] is None
        assert body["manually_edited"] is True
        assert body["anchoring_note"]

        validate = client.post(
            f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client)
        )
        assert validate.status_code == 200
        export = client.post(
            f"{GENERATIONS_URL}/{document_id}/export",
            json={"format": "text"},
            headers=csrf_headers(client),
        )
        assert export.status_code == 200
        assert "Texte repris à la main." in export.json()["content"]


class TestCvTailoring:
    def test_valid_changes_pass(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["tailor_cv"] = {
            "changes": [
                {
                    "kind": "emphasize",
                    "target_ref": skill_ref(profile, "Python"),
                    "new_text": None,
                    "rationale": "Compétence requise par l'offre, remontée en tête.",
                },
                {
                    "kind": "rephrase",
                    "target_ref": experience_ref(profile),
                    "new_text": "Développement d'API backend.",
                    "rationale": "Aligne le vocabulaire sur l'annonce.",
                },
            ]
        }
        document_id = start_generation(
            client, generation_repository, doc_type="cv_variant"
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "draft", "anchoring": "passed"}
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert len(body["content"]["changes"]) == 2

    def test_invalid_kind_rejected_by_schema(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        """kind='create' est structurellement impossible (RM-O-1, schéma fermé)."""
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["tailor_cv"] = {
            "changes": [
                {
                    "kind": "create",
                    "target_ref": skill_ref(profile, "Python"),
                    "new_text": "Kubernetes",
                    "rationale": "Ajout d'une compétence exigée.",
                }
            ]
        }
        document_id = start_generation(
            client, generation_repository, doc_type="cv_variant"
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "failed", "error_code": "schema_error"}
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert body["status"] == "failed"
        assert body["error_code"] == "schema_error"

    def test_unknown_target_ref_dropped_and_check_failed(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["tailor_cv"] = {
            "changes": [
                {
                    "kind": "emphasize",
                    "target_ref": skill_ref(profile, "Python"),
                    "new_text": None,
                    "rationale": "Compétence requise.",
                },
                {
                    "kind": "omit",
                    "target_ref": f"experience:{uuid.uuid4()}",
                    "new_text": None,
                    "rationale": "Expérience inexistante dans le profil.",
                },
            ]
        }
        document_id = start_generation(
            client, generation_repository, doc_type="cv_variant"
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report["anchoring"] == "failed"
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        # F-O scénario 2 : le change rejeté est écarté, le reste conservé,
        # le rejet reste visible (unanchored_claims).
        assert len(body["content"]["changes"]) == 1
        assert len(body["anchoring_check"]["unanchored_claims"]) == 1

    def test_rephrase_without_new_text_is_schema_error(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["tailor_cv"] = {
            "changes": [
                {
                    "kind": "rephrase",
                    "target_ref": experience_ref(profile),
                    "new_text": None,
                    "rationale": "Reformulation sans texte.",
                }
            ]
        }
        document_id = start_generation(
            client, generation_repository, doc_type="cv_variant"
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "failed", "error_code": "schema_error"}


class TestCvOptimization:
    def test_missing_info_question_with_proposal_is_rejected(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        """RM-N-2 : on pose la question, on n'invente JAMAIS la réponse."""
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["optimize_cv"] = {
            "suggestions": [
                {
                    "category": "missing_info_question",
                    "target_ref": experience_ref(profile),
                    "issue": "Aucun résultat chiffré.",
                    "proposal": "Vous avez sûrement augmenté le CA de 20 %.",  # invention
                }
            ]
        }
        document_id = start_generation(
            client, generation_repository, doc_type="cv_optimization"
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "failed", "error_code": "schema_error"}

    def test_question_with_null_proposal_passes(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["optimize_cv"] = {
            "suggestions": [
                {
                    "category": "missing_info_question",
                    "target_ref": experience_ref(profile),
                    "issue": "Aucun résultat chiffré sur cette expérience.",
                    "proposal": None,
                },
                {
                    "category": "wording",
                    "target_ref": skill_ref(profile, "FastAPI"),
                    "issue": "Libellé peu spécifique.",
                    "proposal": "Préciser la version et le contexte d'usage.",
                },
            ]
        }
        document_id = start_generation(
            client, generation_repository, doc_type="cv_optimization"
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "draft", "anchoring": "passed"}
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        suggestions = body["content"]["suggestions"]
        assert len(suggestions) == 2
        assert suggestions[0]["proposal"] is None

    def test_unknown_target_ref_discarded_without_failing_run(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        """AC-N-3 : la suggestion hors profil est écartée, les autres servies."""
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["optimize_cv"] = {
            "suggestions": [
                {
                    "category": "clarity",
                    "target_ref": f"experience:{uuid.uuid4()}",
                    "issue": "Cible inexistante.",
                    "proposal": "Sans objet.",
                },
                {
                    "category": "impact",
                    "target_ref": experience_ref(profile),
                    "issue": "Description sans résultat.",
                    "proposal": "Mettre en avant le résultat obtenu.",
                },
            ]
        }
        document_id = start_generation(
            client, generation_repository, doc_type="cv_optimization"
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "draft", "anchoring": "passed"}
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert len(body["content"]["suggestions"]) == 1
        assert body["content"]["suggestions"][0]["category"] == "impact"


class TestMinimisation:
    def test_prompt_never_contains_identity(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        """D09/RM-T-7 : jamais nom, e-mail ou téléphone du candidat au prompt."""
        user_id, profile = setup_validated_user(
            client, auth_repository, profiles_repository
        )
        document_id = start_generation(client, generation_repository)
        run_generation(document_id, generation_repository, profiles_repository, llm_provider)

        assert llm_provider.calls, "le provider doit avoir été appelé"
        task, prompt = llm_provider.calls[0]
        assert task == "generate_email"
        user = auth_repository.users_by_id[user_id]
        assert user.email not in prompt
        assert "camille" not in prompt.lower()  # partie locale de l'e-mail
        # Le prompt reste ancré : blocs délimités + refs réelles du profil.
        assert "<profile>" in prompt and "<job>" in prompt
        assert f"experience:{profile.experiences[0].id}" in prompt

    def test_unconfirmed_extraction_fields_are_excluded(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        from app.modules.profiles.models import ProfileSkill

        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        profile.skills.append(
            ProfileSkill(
                id=uuid.uuid4(),
                profile_id=profile.id,
                skill_id=None,
                label_raw="CompetenceNonConfirmee",
                source="cv_extraction",
                confidence=0.4,
            )
        )
        document_id = start_generation(client, generation_repository)
        run_generation(document_id, generation_repository, profiles_repository, llm_provider)
        _, prompt = llm_provider.calls[0]
        assert "CompetenceNonConfirmee" not in prompt

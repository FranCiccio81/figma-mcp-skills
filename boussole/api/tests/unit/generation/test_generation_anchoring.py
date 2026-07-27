"""Tests du contrôle d'ancrage (RM-L-2, 08 §5.2) et de la minimisation (D09)."""

import logging
import uuid
from typing import Any, ClassVar

import pytest
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

    def test_unanchored_claim_is_retried_then_fails_cleanly(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        """AC-L-2 / M6 : un claim inventé (« expert Kubernetes ») déclenche
        un retry puis un échec propre — le contenu inventé n'est jamais
        servi au client, la trace du rejet reste auditable."""
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
        assert report == {"status": "failed", "error_code": "grounding_error"}
        assert len(llm_provider.calls) == 2  # 1 appel + 1 retry avec l'erreur
        assert "NON ANCRÉES" in llm_provider.calls[1][1]

        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert body["status"] == "failed"
        assert body["error_code"] == "grounding_error"
        assert body["content"] is None  # jamais le corps inventé
        assert body["anchoring_check"]["status"] == "failed"
        assert any(
            "Kubernetes" in item for item in body["anchoring_check"]["unanchored_claims"]
        )

        # Jamais présenté comme prêt : validation impossible…
        validate = client.post(
            f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client)
        )
        assert validate.status_code == 409
        # … donc export impossible aussi.
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
        assert report == {"status": "failed", "error_code": "grounding_error"}


class TestBodyGrounding:
    """C2 / 08 §5.2.2 : le CORPS est contrôlé pour lui-même — une sortie
    sans aucune claim mais au corps inventé ne doit plus passer."""

    def test_empty_claims_with_invented_body_is_rejected(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {
            "subject": "Candidature",
            "body": (
                "Je suis expert Kubernetes depuis 15 ans et ancien CTO de Google."
            ),
            "claims": [],  # « aucune affirmation » : le corps dit le contraire
        }
        document_id = start_generation(client, generation_repository)
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "failed", "error_code": "grounding_error"}

        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert body["content"] is None
        detected = " ".join(body["anchoring_check"]["unanchored_claims"])
        assert "15 ans" in detected  # durée d'expérience inventée
        assert "Kubernetes" in detected  # technologie absente du profil
        assert "Google" in detected  # entité absente du profil
        assert "expert" in detected  # rôle revendiqué

    def test_body_grounded_on_the_profile_passes(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        """Contre-épreuve : un corps qui ne cite que des faits du profil
        passe (le détecteur n'est pas un refus systématique)."""
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {
            "subject": "Candidature au poste proposé",
            "body": "Mon expérience chez Acme m'a permis de pratiquer Python.",
            "claims": [
                {"claim": "pratique de Python", "profile_ref": skill_ref(profile, "Python")}
            ],
        }
        document_id = start_generation(client, generation_repository)
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "draft", "anchoring": "passed"}

    def test_claim_with_real_ref_but_false_text_is_rejected(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        """M3 : un ``profile_ref`` réel ne blanchit pas un texte mensonger —
        les entités de la claim sont comparées au CONTENU de l'élément."""
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {
            "subject": "Candidature",
            "body": "Bonjour, voici ma candidature.",
            "claims": [
                {
                    "claim": "15 ans d'expérience chez Google",
                    "profile_ref": experience_ref(profile),  # ref RÉEL
                }
            ],
        }
        document_id = start_generation(client, generation_repository)
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "failed", "error_code": "grounding_error"}
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        (detected,) = body["anchoring_check"]["unanchored_claims"]
        assert "contredit l'élément" in detected
        assert experience_ref(profile) in detected


class TestManualEditAndAnchoringTrace:
    """M4 : l'édition manuelle lève le BLOCAGE de validation (Q6 🟡) — mais
    un PATCH no-op ne lève rien, et le verdict d'ancrage n'est jamais
    détruit (sans lui, plus aucune trace des affirmations non ancrées)."""

    ORIGINAL: ClassVar[dict[str, Any]] = {
        "subject": "Candidature",
        "body": "Bonjour, voici ma candidature.",
    }
    VERDICT: ClassVar[dict[str, Any]] = {
        "status": "failed",
        "unanchored_claims": ["expert Kubernetes (profile_ref inconnu : skill:xxx)"],
    }

    def _draft_with_failed_verdict(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> uuid.UUID:
        setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["generate_email"] = {**self.ORIGINAL, "claims": []}
        document_id = start_generation(client, generation_repository)
        run_generation(document_id, generation_repository, profiles_repository, llm_provider)
        document = generation_repository.docs[document_id]
        assert document.status == "draft"
        # Brouillon porteur d'un verdict d'ancrage négatif (rejet partiel).
        document.anchoring_check = dict(self.VERDICT)
        return document_id

    def test_noop_patch_does_not_lift_anchoring(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        """Renvoyer le contenu À L'IDENTIQUE n'est pas une édition : ni
        levée du blocage, ni effacement de la liste des non-ancrées."""
        document_id = self._draft_with_failed_verdict(
            client, auth_repository, profiles_repository,
            generation_repository, llm_provider, canned_outputs,
        )
        # Le client renvoie EXACTEMENT le contenu servi par l'API (relecture
        # sans modification) — le cas de contournement observé en revue.
        current = client.get(f"{GENERATIONS_URL}/{document_id}").json()["content"]
        patched = client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": current},
            headers=csrf_headers(client),
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["manually_edited"] is False
        assert body["anchoring_check"] == self.VERDICT

        validate = client.post(
            f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client)
        )
        assert validate.status_code == 409
        assert validate.json()["type"].endswith("generation_not_anchored")

    def test_real_edit_lifts_blocking_but_keeps_the_verdict(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, Any],
    ) -> None:
        document_id = self._draft_with_failed_verdict(
            client, auth_repository, profiles_repository,
            generation_repository, llm_provider, canned_outputs,
        )
        patched = client.patch(
            f"{GENERATIONS_URL}/{document_id}",
            json={"content": {"subject": "Candidature", "body": "Texte repris à la main."}},
            headers=csrf_headers(client),
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["manually_edited"] is True
        assert body["anchoring_note"]
        # Le verdict d'origine reste LISIBLE (audit) — il n'est pas effacé.
        assert body["anchoring_check"]["status"] == "failed"
        assert body["anchoring_check"]["unanchored_claims"] == (
            self.VERDICT["unanchored_claims"]
        )
        stored = generation_repository.docs[document_id].anchoring_check
        assert stored is not None
        assert stored["lifted_by_manual_edit"] is True
        assert stored["pre_edit"] == self.VERDICT

        # Le blocage de validation, lui, est bien levé (responsabilité assumée).
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
                    "new_text": "Poste 0 chez Acme : développement backend.",
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

    def test_rephrase_inventing_facts_is_rejected(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        canned_outputs: dict[str, dict[str, Any]],
    ) -> None:
        """M7 / RM-O-4 : une reformulation ne crée aucun fait — le change
        est retiré du contenu et le contrôle passe à ``failed`` (validation
        bloquée), au lieu du ``passed`` observé en revue."""
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        canned_outputs["tailor_cv"] = {
            "changes": [
                {
                    "kind": "rephrase",
                    "target_ref": experience_ref(profile),
                    "new_text": "Lead technique chez Google, 15 ans sur Kubernetes.",
                    "rationale": "Reformulation « valorisante » qui invente.",
                }
            ]
        }
        document_id = start_generation(
            client, generation_repository, doc_type="cv_variant"
        )
        report = run_generation(
            document_id, generation_repository, profiles_repository, llm_provider
        )
        assert report == {"status": "draft", "anchoring": "failed"}
        body = client.get(f"{GENERATIONS_URL}/{document_id}").json()
        assert body["content"]["changes"] == []  # le fait neuf n'est pas servi
        (rejected,) = body["anchoring_check"]["unanchored_claims"]
        assert "fait neuf" in rejected

        validate = client.post(
            f"{GENERATIONS_URL}/{document_id}/validate", headers=csrf_headers(client)
        )
        assert validate.status_code == 409
        assert validate.json()["type"].endswith("generation_not_anchored")

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
    #: Coordonnées PLANTÉES dans des champs texte légitimes du profil :
    #: ``extra='forbid'`` ne les empêche pas d'y arriver (elles peuvent
    #: venir d'une extraction CV ou d'une saisie du candidat).
    PLANTED: ClassVar[tuple[str, ...]] = (
        "camille.martin@example.eu",
        "06 12 34 56 78",
        "14/03/1990",
        "rue des Lilas",
        "75011 Paris",
    )

    @staticmethod
    def _plant_pii(profile: Profile) -> None:
        profile.headline = "Ingénieure backend — camille.martin@example.eu"
        profile.summary = (
            "Née le 14/03/1990, mariée, 2 enfants. Joignable au 06 12 34 56 78 "
            "ou à camille.martin@example.eu — 12 rue des Lilas, 75011 Paris."
        )
        profile.experiences[0].description = (
            "Référence : camille.martin@example.eu — tél. 06 12 34 56 78."
        )

    def test_prompt_never_contains_identity(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
    ) -> None:
        """D09/RM-T-7 : aucune coordonnée dans AUCUN des quatre prompts —
        ni l'e-mail de connexion, ni les PII plantées dans headline /
        summary / description."""
        user_id, profile = setup_validated_user(
            client, auth_repository, profiles_repository
        )
        self._plant_pii(profile)

        for doc_type in ("email", "cover_letter", "cv_variant", "cv_optimization"):
            document_id = start_generation(
                client, generation_repository, doc_type=doc_type
            )
            run_generation(
                document_id, generation_repository, profiles_repository, llm_provider
            )

        tasks = [task for task, _ in llm_provider.calls]
        assert set(tasks) == {
            "generate_email", "generate_letter", "tailor_cv", "optimize_cv"
        }
        user = auth_repository.users_by_id[user_id]
        for task, prompt in llm_provider.calls:
            assert user.email not in prompt, task
            assert "camille" not in prompt.lower(), task
            for planted in self.PLANTED:
                assert planted not in prompt, f"{task} : {planted}"
            # La minimisation laisse une trace explicite dans le prompt…
            assert "RETIRÉ" in prompt, task
            # … et ne mutile pas les références d'ancrage (UUID préservés).
            assert f"experience:{profile.experiences[0].id}" in prompt, task
        # Le prompt reste ancré : blocs délimités.
        _, email_prompt = llm_provider.calls[0]
        assert "<profile>" in email_prompt and "<job>" in email_prompt

    def test_scrubbing_is_reported_as_a_warning(
        self,
        client: TestClient,
        auth_repository: InMemoryAuthRepository,
        profiles_repository: InMemoryProfilesRepository,
        generation_repository: InMemoryGenerationRepository,
        llm_provider: FakeProvider,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _, profile = setup_validated_user(client, auth_repository, profiles_repository)
        self._plant_pii(profile)
        document_id = start_generation(client, generation_repository)
        with caplog.at_level(logging.WARNING):
            run_generation(
                document_id, generation_repository, profiles_repository, llm_provider
            )
        messages = [record.getMessage() for record in caplog.records]
        assert any("generation_profile_scrubbed" in message for message in messages)
        # Le journal nomme les CATÉGORIES, jamais les valeurs (D09).
        assert not any("camille.martin@example.eu" in message for message in messages)

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

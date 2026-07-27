"""Tests UNITAIRES des détecteurs déterministes (sans API ni provider).

- :func:`app.ai.scrubbing.scrub_pii` — minimisation D09 (M5) ;
- :func:`app.ai.tasks.generate.check_body_grounding` — ancrage du corps
  (08 §5.2.2, C2) : ce sont les fonctions pures qui portent la promesse
  anti-invention, elles doivent être testables sans HTTP.
"""

import uuid

from app.ai.scrubbing import scrub_payload, scrub_pii
from app.ai.tasks.generate import (
    FAKE_GENERATION_OUTPUTS,
    check_body_grounding,
)

PROFILE = {
    "headline": "Ingénieure backend",
    "summary": {"ref": "summary", "text": "Cinq ans de développement backend Python."},
    "seniority": "confirmé",
    "total_experience_years": 5.0,
    "experiences": [
        {
            "ref": f"experience:{uuid.uuid4()}",
            "title": "Développeuse backend",
            "company": "Acme",
            "start_date": "2020-01-01",
            "end_date": None,
            "description": "Conception de services Python et PostgreSQL.",
        }
    ],
    "educations": [],
    "skills": [{"ref": f"skill:{uuid.uuid4()}", "label": "Python"}],
    "languages": [],
}

JOB = {"title": "Ingénieur backend", "company_name": "Beta", "excerpts": "…"}


class TestScrubPii:
    def test_email_phone_iban_birthdate_and_address_are_removed(self) -> None:
        text = (
            "Contact : camille.martin@example.eu, tél. 06 12 34 56 78 "
            "(ou +33 6 12 34 56 78), IBAN FR7630006000011234567890189, "
            "née le 14/03/1990, 12 rue des Lilas, 75011 Paris, mariée."
        )
        cleaned, removed = scrub_pii(text)
        for value in (
            "camille.martin@example.eu",
            "06 12 34 56 78",
            "+33 6 12 34 56 78",
            "FR7630006000011234567890189",
            "14/03/1990",
            "rue des Lilas",
            "75011 Paris",
            "mariée",
        ):
            assert value not in cleaned, value
        assert {"email", "phone", "iban", "birth_date", "postal_address"} <= set(removed)

    def test_professional_text_is_preserved(self) -> None:
        text = (
            "Développeuse Python chez Acme depuis 01/2020, 5 ans d'expérience, "
            "diplômée en 2015."
        )
        cleaned, removed = scrub_pii(text)
        assert cleaned == text
        assert removed == []

    def test_anchoring_refs_are_never_mutilated(self) -> None:
        """Un UUID contient des suites de chiffres : il ne doit jamais être
        pris pour un numéro de téléphone (le ref serait cassé)."""
        ref = "experience:01234567-89ab-4cde-8123-456789abcdef"
        cleaned, removed = scrub_pii(f"Voir {ref} pour le détail.")
        assert ref in cleaned
        assert removed == []

    def test_scrub_payload_walks_nested_structures(self) -> None:
        payload = {
            "summary": {"ref": "summary", "text": "Joignable : a.b@example.eu"},
            "experiences": [{"description": "Tél. 06 12 34 56 78"}],
            "years": 5,
        }
        cleaned, removed = scrub_payload(payload)
        assert "a.b@example.eu" not in str(cleaned)
        assert "06 12 34 56 78" not in str(cleaned)
        assert cleaned["years"] == 5
        assert set(removed) == {"email", "phone"}

    def test_is_idempotent(self) -> None:
        once, _ = scrub_pii("mail : a.b@example.eu")
        twice, removed = scrub_pii(once)
        assert twice == once
        assert removed == []


class TestCheckBodyGrounding:
    def test_fake_provider_bodies_are_grounded(self) -> None:
        """Les sorties canned M4 n'affirment RIEN sur le candidat : elles
        doivent passer le détecteur (sinon tout le M4 casse)."""
        assert (
            check_body_grounding(
                FAKE_GENERATION_OUTPUTS["generate_email"]["body"], PROFILE, extra_context=JOB
            )
            == []
        )
        assert (
            check_body_grounding(
                FAKE_GENERATION_OUTPUTS["generate_letter"]["body"], PROFILE, extra_context=JOB
            )
            == []
        )

    def test_invented_duration_role_and_entity_are_detected(self) -> None:
        detected = check_body_grounding(
            "Je suis expert Kubernetes depuis 15 ans, ancien CTO de Google.", PROFILE
        )
        joined = " ".join(detected)
        assert "15 ans" in joined
        assert "Kubernetes" in joined
        assert "CTO" in joined
        assert "Google" in joined

    def test_profile_duration_is_accepted(self) -> None:
        assert check_body_grounding("Mes 5 ans chez Acme parlent pour moi.", PROFILE) == []

    def test_written_duration_is_detected(self) -> None:
        assert check_body_grounding("Fort de quinze années de pratique.", PROFILE)

    def test_target_company_from_the_job_is_not_an_invention(self) -> None:
        body = "Rejoindre Beta correspond à mon projet."
        assert check_body_grounding(body, PROFILE, extra_context=JOB) == []
        assert check_body_grounding(body, PROFILE) != []  # sans l'offre : non ancré

    def test_element_content_can_be_a_plain_string(self) -> None:
        """Support du contrôle claim ↔ élément référencé (M3)."""
        assert check_body_grounding("maîtrise de Python", "skill Python") == []
        assert check_body_grounding("maîtrise de Kubernetes", "skill Python") != []

"""Activation des embeddings dans les entrées du moteur (06 §2.1 et §2.3).

Deux fonctionnalités écrites mais inactives faute de vecteurs sont ici
vérifiées de bout en bout (adaptateurs ORM → moteur pur) :

1. ``title_similarity`` (poids 15) — 15 % du poids total était toujours
   « inconnu » (k=0) ;
2. le crédit « compétence proche » 0,5 (seuil 0,75) — le matching était
   en exact-only.

**Non-régression** : sans vecteur d'un côté ou de l'autre, le
comportement doit rester EXACTEMENT celui d'avant (k=0 / exact-only).
"""

import math
import uuid
from typing import Any

import pytest

from app.matching.engine import compute_match
from app.modules.jobs.models import JobSkill as JobSkillRow
from app.modules.matching.adapters import candidate_input_from, job_input_from
from app.modules.profiles.models import ProfileSkill
from app.modules.referentials.models import EMBEDDING_DIM
from tests.unit.matching._calibration import TEST_EMBEDDING_MODEL
from tests.unit.matching_api.conftest import (
    make_job,
    make_preferences,
    make_validated_profile,
)

USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def unit_vector(angle_rad: float, dim: int = EMBEDDING_DIM) -> list[float]:
    """Vecteur unitaire du plan (e0, e1) — cosinus contrôlé au test près."""
    vector = [0.0] * dim
    vector[0] = math.cos(angle_rad)
    vector[1] = math.sin(angle_rad)
    return vector


def vector_at_cosine(cosine: float) -> list[float]:
    """Vecteur dont le cosinus avec ``unit_vector(0)`` vaut ``cosine``."""
    return unit_vector(math.acos(max(-1.0, min(1.0, cosine))))


def dimension(result: Any, name: str) -> Any:
    return next(item for item in result.dimension_scores if item.dimension == name)


def build(job: Any, profile: Any, **kwargs: Any) -> Any:
    """Score une paire (profil, offre) via les adaptateurs réels."""
    taxonomy = kwargs.pop("taxonomy", {})
    candidate = candidate_input_from(
        profile, make_preferences(), taxonomy,
        title_embeddings=kwargs.pop("title_embeddings", ()),
        skill_embeddings=kwargs.pop("candidate_skill_embeddings", None),
    )
    job_input = job_input_from(
        job, job.skills, job.languages, job.locations, skills_taxonomy=taxonomy,
        skill_embeddings=kwargs.pop("job_skill_embeddings", None),
        # Ce que passe le service réel : le modèle du provider actif. Sans
        # lui, le moteur refuse d'interpréter le cosinus (dimension « non
        # calibrée », N14) et rien de ce fichier ne serait exercé.
        embedding_model=kwargs.pop("embedding_model", TEST_EMBEDDING_MODEL),
    )
    return compute_match(candidate, job_input)


# ------------------------------------------------------- 06 §2.3 — dim. métier


class TestSimilariteMetier:
    def test_inconnue_sans_vecteurs_comme_avant(self) -> None:
        """Non-régression : aucune colonne peuplée → k=0, exactement comme
        avant l'arrivée des embeddings."""
        result = build(make_job(), make_validated_profile(USER_ID))
        assert dimension(result, "title_similarity").known is False
        assert "title_similarity" in {
            item.dimension for item in result.unknown_dimensions
        }

    def test_inconnue_si_seule_l_offre_a_un_vecteur(self) -> None:
        job = make_job()
        job.embedding = unit_vector(0.0)
        result = build(job, make_validated_profile(USER_ID))
        assert dimension(result, "title_similarity").known is False

    def test_inconnue_si_seul_le_profil_a_un_vecteur(self) -> None:
        profile = make_validated_profile(USER_ID)
        profile.embedding = unit_vector(0.0)
        result = build(make_job(), profile)
        assert dimension(result, "title_similarity").known is False

    def test_calculee_des_que_les_deux_cotes_ont_un_vecteur(self) -> None:
        job = make_job()
        job.embedding = unit_vector(0.0)
        profile = make_validated_profile(USER_ID)
        profile.embedding = unit_vector(0.0)  # cosinus 1,0

        scored = dimension(build(job, profile), "title_similarity")
        assert scored.known is True
        assert scored.subscore == pytest.approx(1.0)
        assert scored.weight == 15  # les 15 % ne sont plus « inconnus »

    @pytest.mark.parametrize(
        ("cosine", "expected"),
        [
            (0.50, 0.0),   # ≤ 0,55 → 0
            (0.55, 0.0),   # borne basse
            (0.675, 0.5),  # milieu de la rampe 0,55–0,80
            (0.80, 1.0),   # borne haute
            (0.95, 1.0),   # ≥ 0,80 → 1
        ],
    )
    def test_mapping_affine_par_morceaux(self, cosine: float, expected: float) -> None:
        job = make_job()
        job.embedding = unit_vector(0.0)
        profile = make_validated_profile(USER_ID)
        profile.embedding = vector_at_cosine(cosine)

        scored = dimension(build(job, profile), "title_similarity")
        assert scored.subscore == pytest.approx(expected, abs=1e-6)

    def test_max_des_cosinus_sur_les_intitules_cibles(self) -> None:
        """06 §2.3 : c'est le MAX des cosinus qui compte — un intitulé cible
        proche suffit, même si les autres sont éloignés."""
        job = make_job()
        job.embedding = unit_vector(0.0)
        profile = make_validated_profile(USER_ID)
        profile.embedding = vector_at_cosine(0.10)  # vecteur agrégé, éloigné

        result = build(
            job,
            profile,
            title_embeddings=[vector_at_cosine(0.20), vector_at_cosine(0.90)],
        )
        assert dimension(result, "title_similarity").subscore == pytest.approx(1.0)

    def test_vecteur_vide_traite_comme_absent_et_non_comme_cosinus_nul(self) -> None:
        """Un vecteur vide est une donnée MANQUANTE (k=0), jamais un fait
        « métier très éloigné » (score 0 affiché à l'utilisateur)."""
        job = make_job()
        job.embedding = []
        profile = make_validated_profile(USER_ID)
        profile.embedding = unit_vector(0.0)
        assert dimension(build(job, profile), "title_similarity").known is False


# ------------------------------------------------ 06 §2.1 — compétence proche


def with_skill_vectors(cosine: float) -> dict[str, Any]:
    """Offre exigeant « Django », profil portant « Flask » — cosinus imposé."""
    django_id, flask_id = uuid.uuid4(), uuid.uuid4()
    job = make_job(skills=[])
    job.skills = [
        JobSkillRow(
            id=uuid.uuid4(), job_posting_id=job.id, skill_id=django_id,
            label_raw="Django", required=True, confidence=1.0,
        )
    ]
    profile = make_validated_profile(USER_ID)
    profile.skills = [
        ProfileSkill(
            id=uuid.uuid4(), profile_id=profile.id, skill_id=flask_id,
            label_raw="Flask", source="user_input", confidence=1.0,
        )
    ]
    return {
        "job": job,
        "profile": profile,
        "taxonomy": {django_id: "django", flask_id: "flask"},
        "job_skill_embeddings": {django_id: unit_vector(0.0)},
        "candidate_skill_embeddings": {flask_id: vector_at_cosine(cosine)},
    }


class TestCreditCompetenceProche:
    def test_exact_only_sans_vecteurs_comme_avant(self) -> None:
        """Non-régression : sans embeddings, « Flask » ne couvre pas
        « Django » — sous-score 0, exactement comme avant."""
        fixture = with_skill_vectors(0.99)
        result = build(fixture["job"], fixture["profile"], taxonomy=fixture["taxonomy"])
        scored = dimension(result, "skills_required")
        assert scored.subscore == pytest.approx(0.0)
        assert scored.details["missing"] == ["django"]  # label canonique taxonomie

    def test_credit_0_5_au_dessus_du_seuil(self) -> None:
        fixture = with_skill_vectors(0.80)  # ≥ 0,75
        result = build(**fixture)
        scored = dimension(result, "skills_required")
        assert scored.subscore == pytest.approx(0.5)
        assert scored.details["missing"] == []
        related = scored.details["related"]
        assert related[0]["required"] == "django"
        assert related[0]["via"] == "flask"

    def test_pas_de_credit_sous_le_seuil(self) -> None:
        fixture = with_skill_vectors(0.70)  # < 0,75
        scored = dimension(build(**fixture), "skills_required")
        assert scored.subscore == pytest.approx(0.0)
        assert scored.details["missing"] == ["django"]

    def test_seuil_exact_inclusif(self) -> None:
        fixture = with_skill_vectors(0.75)
        assert dimension(build(**fixture), "skills_required").subscore == pytest.approx(
            0.5
        )

    def test_le_match_exact_prime_sur_le_credit_proche(self) -> None:
        fixture = with_skill_vectors(0.99)
        skill_id = next(iter(fixture["job_skill_embeddings"]))
        fixture["profile"].skills[0].skill_id = skill_id  # même compétence canonique
        fixture["candidate_skill_embeddings"] = {skill_id: unit_vector(0.0)}
        scored = dimension(build(**fixture), "skills_required")
        assert scored.subscore == pytest.approx(1.0)
        assert scored.details["matched"] == ["django"]

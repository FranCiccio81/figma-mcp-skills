"""Le rapprochement de modèles : ce qu'il protège, dans les deux sens.

Mesuré avant ce garde-fou, sur les 36 paires du jeu d'évaluation :
``title_similarity`` valait **0,00 partout** et était publiée **connue**.
15 % du poids ne discriminaient rien, et — plus grave — l'indice de confiance
comptait comme acquise une dimension qui ne mesurait rien.

Le sens inverse compte autant, et il viendra plus tard : brancher un provider
sémantique (Q11) sans recalibrer les seuils produirait des sous-scores
**plausibles et faux**, bien plus difficiles à repérer qu'un zéro constant.
C'est le même contrôle qui l'attrape.
"""

import pytest

from app.matching import CandidateInput, JobInput, get_config
from app.matching.dimensions import CANDIDATE_MISSING, JOB_MISSING, UNCALIBRATED, score_dimension
from tests.unit.matching._calibration import TEST_EMBEDDING_MODEL
from tests.unit.matching.factories import E1, job_with_title_cosine, outcome


def _dimension():
    config = get_config()
    return config.dimension("title_similarity"), config


class TestDiscordanceDeModele:
    @pytest.mark.parametrize(
        ("modele", "cas"),
        [
            (None, "vecteur sans provenance déclarée"),
            ("un-autre-modele/2", "vecteur d'un AUTRE modèle"),
            ("", "provenance vide"),
        ],
    )
    def test_la_dimension_devient_inconnue(self, modele: str | None, cas: str) -> None:
        dim, config = _dimension()
        issue = score_dimension(
            dim,
            config,
            CandidateInput(target_titles_embeddings=(E1,)),
            JobInput(title_embedding=E1, title_embedding_model=modele),
        )
        assert issue.known is False, cas
        assert issue.unknown_reason == UNCALIBRATED

    def test_aucun_sous_score_nest_rendu(self) -> None:
        """Le point entier : pas de 0,0 « connu », pas de valeur du tout.

        Un sous-score de 0 est une AFFIRMATION — « ces métiers n'ont rien à
        voir ». Une inconnue est un aveu. Seul le second est vrai ici.
        """
        dim, config = _dimension()
        issue = score_dimension(
            dim,
            config,
            CandidateInput(target_titles_embeddings=(E1,)),
            JobInput(title_embedding=E1, title_embedding_model="autre"),
        )
        assert issue.subscore is None

    def test_le_detail_nomme_les_deux_modeles(self) -> None:
        """Diagnostiquable sans lire le code : qui a produit, pour qui calibré."""
        dim, config = _dimension()
        issue = score_dimension(
            dim,
            config,
            CandidateInput(target_titles_embeddings=(E1,)),
            JobInput(title_embedding=E1, title_embedding_model="autre/3"),
        )
        assert issue.details["embedding_model"] == "autre/3"
        assert issue.details["calibrated_for"] == TEST_EMBEDDING_MODEL


class TestConcordance:
    def test_la_dimension_est_calculee_normalement(self) -> None:
        issue = outcome(
            "title_similarity",
            CandidateInput(target_titles_embeddings=(E1,)),
            job_with_title_cosine(1.0),
        )
        assert issue.known is True
        assert issue.subscore == pytest.approx(1.0)


class TestLOrdreDesControles:
    """Sans vecteur, « absent » renseigne mieux que « non calibré »."""

    def test_vecteur_doffre_absent_reste_job_missing(self) -> None:
        dim, config = _dimension()
        issue = score_dimension(
            dim, config, CandidateInput(target_titles_embeddings=(E1,)), JobInput()
        )
        assert issue.unknown_reason == JOB_MISSING

    def test_vecteur_candidat_absent_reste_candidate_missing(self) -> None:
        issue = outcome("title_similarity", CandidateInput(), job_with_title_cosine(1.0))
        assert issue.unknown_reason == CANDIDATE_MISSING

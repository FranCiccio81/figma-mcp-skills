"""Comportement de la configuration **LIVRÉE**, pas de celle des tests.

Ce fichier est le contre-poids de ``conftest.py`` : le reste de
``tests/unit/matching/`` tourne sur une configuration calibrée, sans quoi le
mapping affine de ``title_similarity`` ne serait jamais exercé. Cette
substitution est légitime — à condition que quelqu'un vérifie ce que fait la
configuration réellement expédiée. C'est ici.

Sans ce fichier, la suite serait verte en validant un mécanisme dont la
configuration de production ne se sert pas : très exactement le motif de
défaut que ce projet a rencontré à chaque jalon.
"""

import json
from pathlib import Path

import pytest

from app.ai.embeddings.hashing import HASHING_MODEL_VERSION
from app.matching import CandidateInput, JobInput, get_config
from app.matching.dimensions import UNCALIBRATED
from tests.unit.matching.factories import E1

SHIPPED = Path(__file__).resolve().parents[3] / "config" / "scoring-config.json"


@pytest.fixture(scope="module")
def shipped():
    """La config du dépôt, chargée par son propre chemin (cache distinct)."""
    return get_config(SHIPPED)


class TestLaConfigLivreeNeCroitPasSesVecteurs:
    def test_title_similarity_nest_calibree_pour_aucun_modele(self) -> None:
        """`null` est un constat, pas un oubli : ces seuils n'ont jamais été
        mesurés contre un modèle (N14, et Q11/Q12 pour la suite)."""
        raw = json.loads(SHIPPED.read_text(encoding="utf-8"))
        assert raw["dimensions"]["title_similarity"]["calibrated_for_model"] is None

    def test_la_dimension_est_donc_inconnue_meme_avec_deux_vecteurs(
        self, shipped
    ) -> None:
        """Le cas qui compte : les vecteurs EXISTENT et sont quand même
        refusés. C'est le cœur de N14 — un cosinus lu avec les seuils d'un
        autre modèle est une mesure fausse, pas imprécise."""
        resultat = shipped.dimension("title_similarity")
        assert resultat.params["calibrated_for_model"] is None

        from app.matching.dimensions import score_dimension

        issue = score_dimension(
            resultat,
            shipped,
            CandidateInput(target_titles_embeddings=(E1,)),
            JobInput(title_embedding=E1, title_embedding_model=HASHING_MODEL_VERSION),
        )
        assert issue.known is False
        assert issue.unknown_reason == UNCALIBRATED

    def test_le_poids_de_la_dimension_est_bien_de_quinze(self, shipped) -> None:
        """Le chiffre qui donne sa gravité à N14 : c'est 15 % du poids total
        qui sort du score ET de l'indice de confiance."""
        assert shipped.dimension("title_similarity").weight == 15.0


class TestLaVersionEstEstampilleeEtSuit:
    def test_le_changement_de_semantique_a_bump_la_version(self, shipped) -> None:
        """Le garde-fou change les scores : il DOIT changer la version.

        C'est ce numéro qui invalide le cache ``match_results`` — sans bump,
        des scores calculés selon l'ancienne sémantique survivraient
        indéfiniment à côté des nouveaux.
        """
        assert shipped.scoring_version == "1.3.0"

"""État MESURÉ du moteur — ce que le harnais trouve aujourd'hui.

Ce fichier ne dit pas ce que le moteur *devrait* faire : il fige ce qu'il
fait, pour que tout changement de ce constat soit visible et discuté. Deux
constats y sont épinglés, tous deux découverts en faisant tourner le harnais
pour la première fois, tous deux consignés en questions ouvertes.

⚠️ Un test qui échoue ici n'est pas forcément une régression — ce peut être
la bonne nouvelle qu'on attend (le provider d'embeddings sémantique arrive,
Q11). Il force simplement à revenir sur ces pages.
"""

import pytest

from app.ai.embeddings.factory import get_embedding_provider
from app.evaluation import load_dataset, run_evaluation
from app.matching import compute_match


@pytest.fixture(scope="module")
def dataset():
    return load_dataset(embedder=get_embedding_provider())


@pytest.fixture(scope="module")
def report(dataset):
    return run_evaluation(dataset)


class TestLeHarnaisMesureVraiment:
    def test_il_couvre_les_trois_profils(self, report) -> None:
        assert [c.candidate_id for c in report.cases] == [
            "cand-backend-senior",
            "cand-devops",
            "cand-junior",
        ]

    def test_les_seuils_viennent_de_la_configuration(self, report) -> None:
        """Recopiés dans le code, ils continueraient de passer sur les
        anciennes valeurs le jour où on les resserre."""
        seuils = {g.name: g.threshold for g in report.gates}
        assert seuils == {
            "spearman_min": 0.6,
            "ndcg_at_10_min": 0.75,
            "blocking_precision_min": 0.95,
            "blocking_recall_min": 0.85,
        }

    def test_le_verdict_est_deterministe(self, dataset) -> None:
        """Le moteur est pur : deux exécutions doivent donner le même chiffre,
        sans quoi aucune comparaison entre versions n'a de sens."""
        premier = run_evaluation(dataset)
        second = run_evaluation(dataset)
        assert [c.spearman for c in premier.cases] == [c.spearman for c in second.cases]


class TestBloquants:
    """Ces deux-là passent, et c'est le résultat le plus rassurant du lot."""

    def test_aucun_rediboire_annonce_a_tort(self, report) -> None:
        assert report.blocking.false_positives == 0

    def test_aucun_rediboire_manque(self, report) -> None:
        assert report.blocking.false_negatives == 0


class TestConstatUnTitleSimilarityInerte:
    """15 % du poids, sous-score 0,00 sur les 36 paires, et compté « connu ».

    Le provider par défaut est lexical (`HashingEmbeddingProvider`, D27) ;
    les seuils `zero_below=0.55` / `one_above=0.80` ont été posés pour des
    vecteurs sémantiques. Résultat : la dimension ne discrimine rien ET pèse
    uniformément sur tous les scores.

    Le plus gênant n'est pas le score, c'est la CONFIANCE : un sous-score de
    0,00 est publié comme un fait connu, donc l'indice de confiance intègre
    une dimension qui ne mesure rien. Voir 17-open-questions.md N14.
    """

    def test_la_dimension_vaut_zero_sur_toutes_les_paires(self, dataset) -> None:
        sous_scores = set()
        for case in dataset.cases:
            for annotation in case.annotations:
                resultat = compute_match(case.candidate, dataset.jobs[annotation.job_ref])
                dimension = next(
                    d for d in resultat.dimension_scores if d.dimension == "title_similarity"
                )
                sous_scores.add((dimension.known, dimension.subscore))
        assert sous_scores == {(True, 0.0)}, (
            "title_similarity n'est plus uniformément nulle — si un provider "
            "sémantique a été branché (Q11), c'est la bonne nouvelle : "
            "recalibrer les seuils (Q12/Q41) et rouvrir N14."
        )


class TestConstatDeuxUneOffreMaigreScoreHaut:
    """`skills_required` en couverture récompense les offres peu exigeantes.

    ``demo-003`` (« Développeur Python Junior », une seule compétence
    requise : `python`) obtient 1,00 sur la dimension la plus lourde — 25 %
    — pour un profil DevOps senior à qui ce poste ne convient pas. Une offre
    pertinente mais listant cinq exigences dont le candidat en a quatre
    plafonne à 0,80.

    Conséquence mesurable : Spearman tombe à 0,570 sur ce profil, sous la
    porte de 0,60. Voir 17-open-questions.md N15.
    """

    def test_une_offre_a_une_seule_exigence_sature_la_dimension(self, dataset) -> None:
        devops = next(c for c in dataset.cases if c.candidate_id == "cand-devops")
        maigre = compute_match(devops.candidate, dataset.jobs["demo-003"])
        pertinente = compute_match(devops.candidate, dataset.jobs["demo-012"])

        def couverture(resultat):
            return next(
                d.subscore for d in resultat.dimension_scores if d.dimension == "skills_required"
            )

        assert couverture(maigre) == 1.0
        assert couverture(pertinente) == 1.0
        # Et l'offre hors sujet finit à un score global élevé pour ce qu'elle est.
        assert maigre.score >= 55

    def test_la_porte_spearman_tombe_sur_le_profil_devops(self, report) -> None:
        """Épinglé volontairement : c'est le constat, pas un objectif.

        Ne PAS faire passer ce test en retouchant les annotations ou les
        poids — un jeu recalé sur la sortie du moteur ne mesure plus rien.
        Il passera le jour où N14/N15 seront traitées.
        """
        porte = next(g for g in report.gates if g.name == "spearman_min")
        assert not porte.passed
        assert porte.detail == "pire profil : cand-devops"
        assert 0.5 < porte.value < 0.6

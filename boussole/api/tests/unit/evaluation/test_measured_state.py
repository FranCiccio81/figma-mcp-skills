"""État MESURÉ du moteur — ce que le harnais trouve aujourd'hui.

Ce fichier ne dit pas ce que le moteur *devrait* faire : il fige ce qu'il
fait, pour que tout changement de ce constat soit visible et discuté. Les
deux constats épinglés ici ont été découverts en faisant tourner le harnais
pour la première fois. N14 est depuis **corrigée** — les chiffres avant/après
sont conservés dans la docstring correspondante, ils sont la mesure de ce que
valait le défaut. N15 reste ouverte.

⚠️ Un test qui échoue ici n'est pas forcément une régression — ce peut être
la bonne nouvelle qu'on attend (le provider d'embeddings sémantique arrive,
Q11, et les seuils sont enfin calibrés). Il force simplement à revenir sur
ces pages.
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


class TestConstatUnTitleSimilarityNestPlusInventee:
    """N14, corrigée. Avant : sous-score 0,00 sur les 36 paires, **connu**.

    Le provider par défaut est lexical (D27) et les seuils 0,55 / 0,80 ont été
    écrits pour des vecteurs sémantiques : la dimension ne discriminait rien,
    abaissait uniformément tous les scores, et — le plus grave — l'indice de
    confiance comptait comme acquise une dimension qui ne mesurait rien.

    Depuis, le moteur rapproche le modèle qui a produit le vecteur du
    ``calibrated_for_model`` de la dimension et rend la dimension INCONNUE en
    cas de discordance. Effet mesuré sur les 36 paires :

    ===============  =======  =======
    Grandeur         avant    après
    ===============  =======  =======
    score moyen         49,1     58,2
    confiance moyenne   97,2     82,2
    confiance max         98       83
    ===============  =======  =======

    Les 15 points de confiance sont l'essentiel : ils étaient revendiqués à
    tort. Aucune paire ne bascule en ``low_data`` — 85 % du poids reste connu,
    bien au-dessus du seuil de 40 %.
    """

    def test_la_dimension_est_inconnue_sur_toutes_les_paires(self, dataset) -> None:
        etats = set()
        for case in dataset.cases:
            for annotation in case.annotations:
                resultat = compute_match(case.candidate, dataset.jobs[annotation.job_ref])
                dimension = next(
                    d for d in resultat.dimension_scores if d.dimension == "title_similarity"
                )
                etats.add((dimension.known, dimension.subscore))
        assert etats == {(False, None)}, (
            "title_similarity n'est plus uniformément inconnue — si les seuils "
            "ont été calibrés contre un modèle (Q11/Q12), c'est la bonne "
            "nouvelle : mettre ce test à jour avec les nouveaux chiffres."
        )

    def test_la_raison_ne_met_en_cause_ni_le_profil_ni_loffre(self, dataset) -> None:
        """C'est NOTRE limite. La replier sur « extraction incertaine »
        accuserait l'offre d'un défaut qu'elle n'a pas."""
        case = dataset.cases[0]
        resultat = compute_match(case.candidate, dataset.jobs[case.annotations[0].job_ref])
        inconnue = next(
            u for u in resultat.unknown_dimensions if u.dimension == "title_similarity"
        )
        assert inconnue.reason == "uncalibrated_embeddings"

    def test_la_confiance_ne_revendique_plus_les_quinze_points(self, dataset) -> None:
        """Avant la correction, la confiance montait à 98 sur ce jeu."""
        confiances = [
            compute_match(case.candidate, dataset.jobs[a.job_ref]).confidence
            for case in dataset.cases
            for a in case.annotations
        ]
        assert max(confiances) <= 85


class TestConstatDeuxLeBiaisDesOffresMaigresEstCorrige:
    """N15, corrigée. ``skills_required`` récompensait les annonces vagues.

    ``demo-003`` (« Développeur Python Junior », une seule exigence : `python`)
    obtenait 1,00 sur la dimension la plus lourde — 25 % — pour un profil
    DevOps senior à qui ce poste ne convient pas, pendant qu'une offre
    pertinente listant cinq exigences dont quatre satisfaites plafonnait à
    0,80. Vu aussi sur l'application réelle : le poste junior sortait en tête
    du profil backend senior, devant l'offre exactement adaptée.

    Depuis, ``k`` est continu : une dimension calculée sur moins de
    ``evidence_full_count`` éléments pèse au prorata (D38). Le sous-score
    n'est pas touché — la couverture est bien de 100 % — mais l'information
    pèse ce qu'elle vaut.

    =================  =======  =======
    Porte Spearman     avant    après
    =================  =======  =======
    pire profil          0,526    0,714
    NDCG@10 pire         0,907    0,956
    =================  =======  =======
    """

    def test_la_couverture_complete_dune_offre_maigre_reste_vraie(
        self, dataset
    ) -> None:
        """On n'a pas menti sur la couverture pour corriger le classement."""
        devops = next(c for c in dataset.cases if c.candidate_id == "cand-devops")
        maigre = compute_match(devops.candidate, dataset.jobs["demo-003"])
        couverture = next(
            d for d in maigre.dimension_scores if d.dimension == "skills_required"
        )
        assert couverture.subscore == 1.0

    def test_mais_elle_ne_pese_plus_le_poids_plein(self, dataset) -> None:
        devops = next(c for c in dataset.cases if c.candidate_id == "cand-devops")
        maigre = compute_match(devops.candidate, dataset.jobs["demo-003"])
        riche = compute_match(devops.candidate, dataset.jobs["demo-012"])

        def poids(resultat):
            return next(
                d.weight for d in resultat.dimension_scores
                if d.dimension == "skills_required"
            )

        assert poids(maigre) < poids(riche)

    def test_toutes_les_portes_passent(self, report) -> None:
        """Le verdict global. Il est passé d'ÉCHEC à succès sans qu'aucune
        annotation ni aucun poids n'ait été retouché pour l'obtenir — seule
        la sémantique de ``k`` a changé, et elle a été vérifiée sur toute la
        plage 2–5 du paramètre."""
        assert report.passed, [
            (g.name, g.value, g.threshold) for g in report.gates if not g.passed
        ]

    def test_le_pire_spearman_depasse_la_porte(self, report) -> None:
        porte = next(g for g in report.gates if g.name == "spearman_min")
        assert porte.passed
        assert porte.value > 0.70

"""Métriques d'évaluation — les formules, avant de s'en servir pour juger.

Un harnais de mesure qui se trompe est pire que pas de harnais : il produit
un chiffre, et un chiffre inspire confiance. D'où des tests sur les cas où
ces formules se trompent le plus souvent — ex æquo, séries constantes,
absence totale de pertinence.
"""

import math

import pytest

from app.evaluation.metrics import (
    MetricError,
    average_ranks,
    blocking_score,
    ndcg_at_k,
    spearman,
)


class TestRangs:
    def test_rangs_simples(self) -> None:
        assert average_ranks([10.0, 30.0, 20.0]) == [1.0, 3.0, 2.0]

    def test_les_ex_aequo_partagent_le_rang_moyen(self) -> None:
        """Sans ça, l'ordre d'entrée de valeurs égales change la corrélation.

        Un jeu où dix offres partagent la note 0 — le cas NORMAL — donnerait
        un Spearman différent selon le tri du fichier.
        """
        assert average_ranks([5.0, 5.0, 9.0]) == [1.5, 1.5, 3.0]

    def test_tous_ex_aequo(self) -> None:
        assert average_ranks([7.0, 7.0, 7.0, 7.0]) == [2.5] * 4


class TestSpearman:
    def test_ordre_parfait(self) -> None:
        assert spearman([1.0, 2.0, 3.0], [10.0, 20.0, 30.0]) == pytest.approx(1.0)

    def test_ordre_inverse(self) -> None:
        assert spearman([1.0, 2.0, 3.0], [30.0, 20.0, 10.0]) == pytest.approx(-1.0)

    def test_insensible_a_lechelle(self) -> None:
        """Un moteur qui donnerait 40 points de moins partout reste parfait.

        C'est voulu : ce que l'utilisateur lit, c'est un ORDRE. Spearman
        mesure le classement, pas l'étalonnage.
        """
        scores = [80.0, 60.0, 40.0]
        decales = [s - 40 for s in scores]
        attendu = [3.0, 2.0, 1.0]
        assert spearman(scores, attendu) == spearman(decales, attendu)

    def test_avec_ex_aequo(self) -> None:
        """Formule de Pearson sur les rangs — la formule courte 1-6Σd²/n(n²-1)
        est FAUSSE dès qu'il y a un ex æquo, et il y en a toujours."""
        rho = spearman([3.0, 1.0, 1.0, 5.0], [3.0, 2.0, 1.0, 4.0])
        assert 0.7 < rho < 1.0

    def test_serie_constante_refusee(self) -> None:
        """Un moteur qui donne le même score à tout n'a pas 0 de corrélation :
        il n'en a aucune. Rendre 0 masquerait exactement cette panne."""
        with pytest.raises(MetricError, match="constante"):
            spearman([50.0, 50.0, 50.0], [3.0, 2.0, 1.0])

    def test_series_de_longueurs_differentes(self) -> None:
        with pytest.raises(MetricError):
            spearman([1.0, 2.0], [1.0])

    def test_une_seule_observation(self) -> None:
        with pytest.raises(MetricError):
            spearman([1.0], [1.0])


class TestNdcg:
    def test_classement_ideal(self) -> None:
        assert ndcg_at_k([9.0, 5.0, 1.0], [3.0, 2.0, 0.0]) == pytest.approx(1.0)

    def test_classement_inverse_est_penalise(self) -> None:
        assert ndcg_at_k([1.0, 5.0, 9.0], [3.0, 2.0, 0.0]) < 0.7

    def test_une_erreur_en_tete_coute_plus_quen_queue(self) -> None:
        """C'est toute la raison d'être de NDCG : personne ne descend au 50ᵉ
        résultat, une erreur en position 2 se paie plus cher qu'en 20ᵉ."""
        pertinences = [3.0, 2.0, 1.0, 0.0, 0.0, 0.0]
        erreur_en_tete = ndcg_at_k([1.0, 6.0, 5.0, 4.0, 3.0, 2.0], pertinences)
        erreur_en_queue = ndcg_at_k([6.0, 5.0, 4.0, 3.0, 1.0, 2.0], pertinences)
        assert erreur_en_tete < erreur_en_queue

    def test_seuls_les_k_premiers_comptent(self) -> None:
        """Une offre parfaite reléguée au-delà de k ne rapporte rien."""
        pertinences = [0.0] * 10 + [3.0]
        scores = [float(10 - i) for i in range(11)]
        assert ndcg_at_k(scores, pertinences, k=10) == pytest.approx(0.0)

    def test_aucune_offre_pertinente_est_refuse(self) -> None:
        """Rendre 0 ferait tomber une porte pour une raison qui ne dit rien
        du moteur — c'est le jeu d'annotations qu'il faut regarder."""
        with pytest.raises(MetricError, match="aucune offre pertinente"):
            ndcg_at_k([3.0, 2.0, 1.0], [0.0, 0.0, 0.0])


class TestBloquants:
    def test_comptage(self) -> None:
        score = blocking_score(
            predicted=[True, True, False, False],
            expected=[True, False, True, False],
        )
        assert (score.true_positives, score.false_positives, score.false_negatives) == (1, 1, 1)
        assert score.precision == pytest.approx(0.5)
        assert score.recall == pytest.approx(0.5)

    def test_aucun_bloquant_annonce_donne_une_precision_parfaite(self) -> None:
        """Le moteur n'a rien affirmé de faux — le rappel, lui, s'effondre.

        La dissymétrie des seuils (0,95 / 0,85) vient de là : annoncer un
        rédhibitoire à tort décourage une candidature légitime, ce qui coûte
        plus cher que d'en rater un.
        """
        score = blocking_score(predicted=[False, False], expected=[True, True])
        assert score.precision == pytest.approx(1.0)
        assert score.recall == pytest.approx(0.0)

    def test_aucun_bloquant_attendu_donne_un_rappel_parfait(self) -> None:
        score = blocking_score(predicted=[False, False], expected=[False, False])
        assert score.recall == pytest.approx(1.0)
        assert score.precision == pytest.approx(1.0)

    def test_longueurs_differentes(self) -> None:
        with pytest.raises(MetricError):
            blocking_score([True], [True, False])


class TestProprietesGenerales:
    @pytest.mark.parametrize("k", [1, 3, 10, 100])
    def test_ndcg_reste_dans_zero_un(self, k: int) -> None:
        scores = [5.0, 1.0, 9.0, 3.0, 7.0]
        pertinences = [1.0, 0.0, 3.0, 2.0, 0.0]
        valeur = ndcg_at_k(scores, pertinences, k=k)
        assert 0.0 <= valeur <= 1.0 or math.isclose(valeur, 1.0)

    def test_spearman_reste_dans_moins_un_un(self) -> None:
        assert -1.0 <= spearman([4.0, 8.0, 1.0, 6.0], [2.0, 3.0, 0.0, 1.0]) <= 1.0

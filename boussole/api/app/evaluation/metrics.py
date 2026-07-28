"""Métriques d'évaluation du matching — calcul pur, sans dépendance.

Les trois métriques des ``evaluation_gates`` de ``scoring-config.json`` :

- **Spearman** — le score suit-il l'ordre attendu ? C'est la métrique qui dit
  si le moteur *classe* correctement, indépendamment de l'échelle. Un moteur
  qui donnerait systématiquement 40 points de moins qu'attendu resterait
  parfait au sens de Spearman, et c'est voulu : ce que l'utilisateur lit,
  c'est un ordre.
- **NDCG@10** — la tête de liste est-elle bonne ? Personne ne descend au
  200ᵉ résultat ; une erreur en position 3 coûte plus qu'une erreur en
  position 50, et NDCG le pondère logarithmiquement.
- **Précision / rappel des bloquants** — quand le moteur déclare un critère
  rédhibitoire, a-t-il raison, et n'en rate-t-il pas ? Les seuils sont
  dissymétriques (0,95 / 0,85) parce que les erreurs le sont : signaler à
  tort un bloquant décourage une candidature légitime.

`numpy` et `scipy` ne sont pas des dépendances du projet et n'ont pas à le
devenir pour trois formules — d'autant qu'écrire le calcul des rangs à la
main force à traiter les ex æquo, que la plupart des jeux de référence
comportent en abondance (beaucoup d'offres « pas du tout pertinentes »).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass


class MetricError(ValueError):
    """Métrique impossible à calculer sur les données fournies."""


def average_ranks(values: Sequence[float]) -> list[float]:
    """Rangs 1..n, **moyennés sur les ex æquo**.

    Le traitement des ex æquo n'est pas un détail : sans lui, l'ordre
    d'apparition de valeurs égales dans la liste influencerait la
    corrélation, et un jeu où dix offres partagent la note 0 donnerait un
    Spearman différent selon le tri d'entrée.
    """
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(indexed):
        fin = position
        while fin + 1 < len(indexed) and values[indexed[fin + 1]] == values[indexed[position]]:
            fin += 1
        rang_moyen = (position + fin) / 2 + 1
        for i in range(position, fin + 1):
            ranks[indexed[i]] = rang_moyen
        position = fin + 1
    return ranks


def spearman(predicted: Sequence[float], expected: Sequence[float]) -> float:
    """Corrélation de rang de Spearman ∈ [-1, 1].

    Calculée comme le Pearson des rangs — la formule courte ``1 - 6Σd²/n(n²-1)``
    est FAUSSE en présence d'ex æquo, et il y en a toujours.
    """
    if len(predicted) != len(expected):
        raise MetricError("les deux séries doivent avoir la même longueur")
    if len(predicted) < 2:
        raise MetricError("Spearman exige au moins deux observations")

    rangs_p = average_ranks(predicted)
    rangs_e = average_ranks(expected)
    moyenne_p = sum(rangs_p) / len(rangs_p)
    moyenne_e = sum(rangs_e) / len(rangs_e)

    paires = zip(rangs_p, rangs_e, strict=True)
    covariance = sum((p - moyenne_p) * (e - moyenne_e) for p, e in paires)
    variance_p = sum((p - moyenne_p) ** 2 for p in rangs_p)
    variance_e = sum((e - moyenne_e) ** 2 for e in rangs_e)
    if variance_p == 0 or variance_e == 0:
        # Une série constante n'a pas d'ordre : la corrélation n'est pas
        # définie. La renvoyer à 0 masquerait un moteur qui donne le même
        # score à tout — exactement la panne qu'on veut voir.
        raise MetricError(
            "série constante : aucun ordre à corréler (moteur muet, ou jeu "
            "d'évaluation sans variation de pertinence)"
        )
    return covariance / math.sqrt(variance_p * variance_e)


def dcg(gains: Sequence[float]) -> float:
    """Discounted Cumulative Gain, convention ``(2^g - 1) / log2(i + 1)``."""
    return sum((2**gain - 1) / math.log2(index + 2) for index, gain in enumerate(gains))


def ndcg_at_k(predicted: Sequence[float], expected: Sequence[float], k: int = 10) -> float:
    """NDCG@k ∈ [0, 1] : qualité du classement produit, sur les k premiers.

    ``predicted`` sert uniquement à ORDONNER ; ce sont les pertinences
    ``expected`` qui font le gain. Un moteur qui remonte les bonnes offres en
    tête obtient 1, quelle que soit la valeur numérique de ses scores.
    """
    if len(predicted) != len(expected):
        raise MetricError("les deux séries doivent avoir la même longueur")
    if not predicted:
        raise MetricError("NDCG exige au moins une observation")

    ordre = sorted(range(len(predicted)), key=lambda i: predicted[i], reverse=True)
    gains_obtenus = [expected[i] for i in ordre[:k]]
    gains_ideaux = sorted(expected, reverse=True)[:k]

    ideal = dcg(gains_ideaux)
    if ideal == 0:
        # Aucune offre pertinente : tout classement se vaut. Rendre 0 ferait
        # échouer une porte pour une raison qui ne dit rien du moteur.
        raise MetricError(
            "aucune offre pertinente dans le jeu : NDCG n'est pas défini "
            "(vérifier les annotations de ce candidat)"
        )
    return dcg(gains_obtenus) / ideal


@dataclass(frozen=True, slots=True)
class BlockingScore:
    """Précision et rappel de la détection des critères rédhibitoires."""

    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        """Parmi les bloquants annoncés, combien étaient réels.

        Aucun bloquant annoncé ⇒ 1,0 : le moteur n'a rien affirmé de faux.
        """
        annonces = self.true_positives + self.false_positives
        return 1.0 if annonces == 0 else self.true_positives / annonces

    @property
    def recall(self) -> float:
        """Parmi les bloquants réels, combien ont été trouvés.

        Aucun bloquant attendu ⇒ 1,0 : il n'y avait rien à rater.
        """
        attendus = self.true_positives + self.false_negatives
        return 1.0 if attendus == 0 else self.true_positives / attendus


def blocking_score(
    predicted: Sequence[bool], expected: Sequence[bool]
) -> BlockingScore:
    """Compte les vrais/faux positifs et les faux négatifs des bloquants."""
    if len(predicted) != len(expected):
        raise MetricError("les deux séries doivent avoir la même longueur")
    return BlockingScore(
        true_positives=sum(1 for p, e in zip(predicted, expected, strict=True) if p and e),
        false_positives=sum(1 for p, e in zip(predicted, expected, strict=True) if p and not e),
        false_negatives=sum(1 for p, e in zip(predicted, expected, strict=True) if not p and e),
    )

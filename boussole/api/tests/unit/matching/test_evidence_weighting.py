"""Quantité de preuve : ``k`` est continu, pas binaire (N15).

**Le défaut.** ``skills_required`` (25 %, la dimension la plus lourde) notait
en couverture : une offre n'exigeant QU'UNE compétence, que le candidat
possède, obtenait 1,00. Une offre pertinente listant cinq exigences dont
quatre satisfaites plafonnait à 0,80. Mesuré sur l'application réelle avec le
corpus de démonstration : un poste « Développeur Python Junior » sur site
passait **devant** le poste exactement adapté, pour un profil senior.

Comme les vraies annonces varient énormément dans le soin de leur rédaction,
le biais favorise systématiquement les plus vagues.

**Le correctif.** Le sous-score ne change pas — 1,00 reste vrai, le candidat
couvre bien tout ce qui est demandé. C'est le **poids** de cette information
qui est atténué : peu d'exigences = peu de preuve. Autrement dit, le facteur
``k`` du modèle (06 §1), jusque-là binaire connu/inconnu, devient **continu** ;
une dimension peut être partiellement connue. Score et confiance suivent la
même règle, ce qui garde une seule histoire à raconter.

**Pourquoi pas un lissage vers une moyenne**, qui est la réponse
statistique habituelle : il interdirait à jamais d'atteindre 1,00, donc de
marquer 100 sur une offre parfaitement couverte. C'est une promesse produit
qu'on ne casse pas pour corriger un biais.

**Mesuré, pas raisonné.** Après correction, `make evaluate` passe de 0,526 à
0,714 sur le pire profil (porte à 0,60), NDCG@10 de 0,907 à 0,956, et les
bloquants restent parfaits. Vérifié aussi que ce n'est pas un réglage ad hoc :
la porte passe pour ``evidence_full_count`` valant 2, 3, 4 **ou** 5 — c'est le
mécanisme qui corrige, pas la constante.
"""

from pathlib import Path

import pytest

from app.matching import CandidateInput, JobInput, JobSkill, compute_match, get_config
from tests.unit.matching.factories import dim, perfect_candidate, perfect_job

#: Configuration LIVRÉE (les tests de ce dossier tournent sur une copie
#: calibrée — voir ``conftest.py``), pour reconstruire une variante.
SHIPPED_CONFIG = Path(__file__).resolve().parents[3] / "config" / "scoring-config.json"


def _seuil() -> float:
    valeur = get_config().dimension("skills_required").params["evidence_full_count"]
    assert isinstance(valeur, int | float)
    return float(valeur)


def _offre(nb_exigences: int) -> JobInput:
    """Offre dont TOUTES les exigences sont satisfaites — sous-score 1,00."""
    labels = ["python", "sql", "docker", "git", "linux"][:nb_exigences]
    return JobInput(skills_required=tuple(JobSkill(label) for label in labels))


CANDIDAT = CandidateInput(skills=("python", "sql", "docker", "git", "linux"))


class TestLeSousScoreNestPasTouche:
    """On ne ment pas sur la couverture : elle est bien de 100 %."""

    @pytest.mark.parametrize("nb", [1, 2, 3, 5])
    def test_la_couverture_complete_vaut_toujours_un(self, nb: int) -> None:
        resultat = compute_match(CANDIDAT, _offre(nb))
        assert dim(resultat, "skills_required").subscore == pytest.approx(1.0)


class TestLePoidsSuitLaPreuve:
    def test_une_exigence_pese_moins_que_le_plein(self) -> None:
        seuil = _seuil()
        maigre = dim(compute_match(CANDIDAT, _offre(1)), "skills_required")
        plein = dim(compute_match(CANDIDAT, _offre(int(seuil))), "skills_required")
        assert maigre.weight == pytest.approx(plein.weight / seuil)

    def test_le_poids_expose_est_le_poids_EFFECTIF(self) -> None:
        """L'utilisateur doit voir ce qui a réellement compté, pas le poids
        déclaré dans la configuration."""
        declare = get_config().dimension("skills_required").weight
        effectif = dim(compute_match(CANDIDAT, _offre(1)), "skills_required").weight
        assert effectif < declare

    def test_au_dela_du_seuil_le_poids_ne_croit_plus(self) -> None:
        """Exiger dix compétences ne rend pas la dimension plus importante
        que la configuration ne le dit."""
        seuil = int(_seuil())
        au_seuil = dim(compute_match(CANDIDAT, _offre(seuil)), "skills_required")
        au_dela = dim(compute_match(CANDIDAT, _offre(5)), "skills_required")
        assert au_dela.weight == pytest.approx(au_seuil.weight)
        assert au_dela.weight == pytest.approx(
            get_config().dimension("skills_required").weight
        )

    def test_le_detail_dit_pourquoi(self) -> None:
        """Diagnosticable sans lire le code : combien d'exigences, quel facteur."""
        details = dim(compute_match(CANDIDAT, _offre(1)), "skills_required").details
        assert details["evidence_count"] == 1
        assert details["weight_factor"] == pytest.approx(1 / _seuil(), abs=1e-4)


class TestLimiteDuCorrectif:
    """À connaître : l'atténuation ne fait RIEN sur une offre isolée.

    Si ``skills_required`` est la seule dimension connue, la renormalisation
    divise par ce seul poids — atténué ou non, il se simplifie et le score
    vaut la couverture. C'est mathématiquement inévitable, et c'est juste :
    quand on ne sait QUE la couverture, le score EST la couverture.

    Conséquence pratique : le correctif joue sur l'influence RELATIVE d'une
    dimension parmi d'autres. Il ne protège pas d'une offre dont on ne sait
    rien d'autre — cas rare avec de vraies annonces, mais réel.
    """

    def test_seule_dimension_connue_le_facteur_se_simplifie(self) -> None:
        maigre = compute_match(CANDIDAT, _offre(1))
        riche = compute_match(CANDIDAT, _offre(3))
        assert maigre.score == riche.score == 100


class TestLeCasQuiAMotiveLeCorrectif:
    """Le cas réel, reproduit et chiffré des deux côtés du correctif.

    À gauche, l'annonce vague : une seule exigence — « python » — mais un
    poste JUNIOR pour un profil senior de six ans. À droite, l'annonce
    soignée : quatre exigences dont trois satisfaites, séniorité et
    expérience alignées.

    Sans atténuation : **88 contre 86**, l'annonce vague passe devant.
    Avec : **80 contre 86**, l'ordre est rétabli.

    Le mécanisme n'abaisse pas l'offre maigre « pour la punir » : il rend
    aux autres dimensions — ici la séniorité, où elle est mauvaise — le poids
    relatif qu'un quart du total accaparait sur la foi d'une seule ligne.
    """

    CANDIDAT_SENIOR = CandidateInput(
        skills=("python", "sql", "docker", "git", "linux"),
        seniority="senior",
        total_experience_years=6.0,
        contract_types=frozenset({"cdi"}),
    )

    def _annonce_vague(self) -> JobInput:
        from app.matching import Confident

        return JobInput(
            skills_required=(JobSkill("python"),),
            seniority=Confident("junior"),
            experience_min=0.0,
            experience_max=2.0,
            contract=Confident("cdi"),
        )

    def _annonce_soignee(self) -> JobInput:
        from app.matching import Confident

        return JobInput(
            skills_required=(
                JobSkill("python"),
                JobSkill("sql"),
                JobSkill("docker"),
                JobSkill("kubernetes"),  # non possédée
            ),
            seniority=Confident("senior"),
            experience_min=4.0,
            experience_max=9.0,
            contract=Confident("cdi"),
        )

    def test_lannonce_soignee_passe_devant_lannonce_vague(self) -> None:
        vague = compute_match(self.CANDIDAT_SENIOR, self._annonce_vague())
        soignee = compute_match(self.CANDIDAT_SENIOR, self._annonce_soignee())
        assert (vague.score, soignee.score) == (80, 86)
        assert soignee.score > vague.score

    def test_sans_attenuation_lordre_sinverse(self, tmp_path) -> None:
        """La preuve que c'est bien CE mécanisme qui corrige, et pas autre chose.

        On recharge la configuration sans ``evidence_full_count`` : l'ordre
        s'inverse. Si ce test venait à passer sans inversion, c'est que le
        correctif ne sert plus à rien — ou qu'il a été neutralisé ailleurs.
        """
        import collections
        import json

        source = json.loads(
            (SHIPPED_CONFIG).read_text(encoding="utf-8"),
            object_pairs_hook=collections.OrderedDict,
        )
        for nom in ("skills_required", "skills_nice"):
            source["dimensions"][nom].pop("evidence_full_count", None)
        chemin = tmp_path / "sans-attenuation.json"
        chemin.write_text(json.dumps(source), encoding="utf-8")
        sans = get_config(chemin)

        vague = compute_match(self.CANDIDAT_SENIOR, self._annonce_vague(), sans)
        soignee = compute_match(self.CANDIDAT_SENIOR, self._annonce_soignee(), sans)
        assert (vague.score, soignee.score) == (88, 86)
        assert vague.score > soignee.score, "le défaut N15 n'est plus reproductible"


class TestUneOffreMaigreIrreprochableResteAcent:
    """Et c'est juste : on ne sait rien de mal d'elle.

    Une offre qui n'exige qu'une compétence, satisfaite, et qui est parfaite
    sur tout ce qu'elle déclare, marque 100. Le correctif ne la punit pas —
    il n'y a rien à lui reprocher. Ce qui la distingue d'une offre bien
    documentée, c'est la CONFIANCE : 27 contre 44 sur ce cas. C'est
    exactement le rôle de l'indice, et la raison pour laquelle il est affiché
    à côté du score et jamais fondu dedans.
    """

    def test_le_score_reste_a_cent_mais_la_confiance_effondre(self) -> None:
        from app.matching import Confident

        candidat = CandidateInput(
            skills=("python", "sql", "docker", "git", "linux"),
            seniority="senior",
            total_experience_years=5.0,
            contract_types=frozenset({"cdi"}),
        )

        def offre(competences: tuple[JobSkill, ...]) -> JobInput:
            return JobInput(
                skills_required=competences,
                seniority=Confident("senior"),
                experience_min=3.0,
                experience_max=8.0,
                contract=Confident("cdi"),
            )

        maigre = compute_match(candidat, offre((JobSkill("python"),)))
        documentee = compute_match(
            candidat, offre((JobSkill("python"), JobSkill("sql"), JobSkill("docker")))
        )
        assert maigre.score == documentee.score == 100
        assert maigre.confidence < documentee.confidence


class TestLaConfianceSuitLaMemeRegle:
    """Une preuve partielle est une connaissance partielle : la confiance
    doit le refléter, sinon on affirme savoir ce qu'on ne sait qu'à moitié —
    exactement le défaut corrigé sur ``title_similarity`` (N14)."""

    def test_moins_dexigences_donne_moins_de_confiance(self) -> None:
        maigre = compute_match(CANDIDAT, _offre(1))
        plein = compute_match(CANDIDAT, _offre(int(_seuil())))
        assert maigre.confidence < plein.confidence

    def test_le_cas_de_reference_a_preuve_pleine_reste_a_cent(self) -> None:
        """UM-01 : douze dimensions connues, preuve pleine → 100/100.

        Le plafond est la raison pour laquelle on atténue le poids plutôt que
        de lisser le sous-score.
        """
        resultat = compute_match(perfect_candidate(), perfect_job())
        assert resultat.score == 100
        assert resultat.confidence == 100


class TestLesExplicationsVoientLePoidsEFFECTIF:
    """Sinon le moteur et l'interface se contredisent sur le même écran.

    La couche d'explication déterministe (06 §6) retient une dimension comme
    « force » si son sous-score dépasse un seuil ET son poids un autre. Elle
    recevait le poids DÉCLARÉ pendant que le résultat exposait l'EFFECTIF.

    Mesuré : une offre n'exigeant qu'une compétence souhaitée, satisfaite,
    voyait `skills_nice` annoncée comme force par le moteur (déclaré 10 ≥ 6)
    alors que le front, qui lit le poids effectif (3,33 < 6), ne l'affichait
    pas. Deux moitiés du même écran en désaccord — et sur le fond, appeler
    « force » une dimension qu'on vient de juger peu documentée contredit
    exactement le correctif de N15.
    """

    CANDIDAT = CandidateInput(
        skills=("python", "docker"), seniority="senior", total_experience_years=5.0
    )

    def _offre_a_une_seule_souhaitee(self) -> JobInput:
        from app.matching import Confident

        return JobInput(
            skills_required=(JobSkill("python"), JobSkill("docker")),
            skills_nice=(JobSkill("python"),),
            seniority=Confident("senior"),
            experience_min=3.0,
            experience_max=8.0,
        )

    def test_une_dimension_peu_documentee_nest_pas_annoncee_comme_force(self) -> None:
        resultat = compute_match(self.CANDIDAT, self._offre_a_une_seule_souhaitee())
        poids = dim(resultat, "skills_nice").weight
        seuil = get_config().explanation.strength_min_weight

        assert poids < seuil, "le cas de test ne reproduit plus l'atténuation"
        assert "skills_nice" not in [f.dimension for f in resultat.explanation_facts.strengths]

    def test_le_moteur_et_le_poids_expose_disent_la_meme_chose(self) -> None:
        """L'invariant général : pour CHAQUE dimension, être annoncée force
        équivaut à dépasser les deux seuils avec le poids exposé."""
        resultat = compute_match(self.CANDIDAT, self._offre_a_une_seule_souhaitee())
        seuils = get_config().explanation
        forces = {f.dimension for f in resultat.explanation_facts.strengths}

        for score in resultat.dimension_scores:
            if not score.known or score.subscore is None:
                continue
            attendu = (
                score.subscore >= seuils.strength_min_subscore
                and score.weight >= seuils.strength_min_weight
            )
            assert (score.dimension in forces) is attendu, score.dimension


class TestLaContrepartieSymetrique:
    """L'atténuation joue dans les DEUX sens, et il faut le dire.

    Réduire le poids d'une dimension ne fait pas que « ne plus sur-récompenser
    une couverture complète » : quand le sous-score vaut 0, cela **retire la
    pénalité**. Le numérateur ne bouge pas, seul le dénominateur diminue.

    Mesuré sur le corpus de démonstration, en comparant avec et sans
    ``evidence_full_count`` : sur 30 paires dont le score change, **22 sont
    des offres de pertinence ≤ 1 et leur score MONTE**. Le pire cas :
    « Chef de projet infrastructure » (une exigence, non couverte) passe de
    **49 à 64** pour une développeuse backend senior.

    Pourquoi on l'assume malgré tout :

    1. le CLASSEMENT s'améliore — c'est ce que mesurent les portes, et elles
       passent toutes désormais ;
    2. la **confiance chute** en même temps (83 → 63 sur ce cas). Le produit
       affiche toujours score ET confiance côte à côte, jamais fusionnés
       (D03) : le couple reste honnête ;
    3. sur le fond, c'est cohérent. Une seule exigence non couverte ne prouve
       pas grand-chose. Prétendre le contraire serait affirmer plus que ce
       que l'offre dit d'elle-même.

    Ce que ça ne rend PAS acceptable : lire le score comme une valeur absolue
    sans regarder la confiance. C'est la limite, elle est ici et dans D38.
    """

    def test_une_offre_non_couverte_voit_son_score_monter(self, tmp_path) -> None:
        """Épinglé pour que ce ne soit pas une surprise le jour où on le voit."""
        import collections
        import json

        from app.matching import Confident

        candidat = CandidateInput(
            skills=("python", "postgresql"),
            seniority="senior",
            total_experience_years=6.0,
            contract_types=frozenset({"cdi"}),
        )
        offre = JobInput(
            skills_required=(JobSkill("gestion de projet"),),  # non couverte
            seniority=Confident("senior"),
            experience_min=5.0,
            experience_max=10.0,
            contract=Confident("cdi"),
        )

        source = json.loads(
            SHIPPED_CONFIG.read_text(encoding="utf-8"),
            object_pairs_hook=collections.OrderedDict,
        )
        for nom in ("skills_required", "skills_nice"):
            source["dimensions"][nom].pop("evidence_full_count", None)
        chemin = tmp_path / "sans.json"
        chemin.write_text(json.dumps(source), encoding="utf-8")

        sans = compute_match(candidat, offre, get_config(chemin))
        avec = compute_match(candidat, offre)

        assert avec.score > sans.score, "la contrepartie n'est plus reproductible"
        # Et la confiance descend : c'est ce qui garde le couple honnête.
        assert avec.confidence < sans.confidence


class TestLInteractionAvecLowData:
    """`low_data` peut basculer sur une offre dont TOUT est connu.

    Le seuil compare la somme ATTÉNUÉE `Σ(w·k)` à `min_known_weight_ratio ×
    Σ(w)`, qui n'est PAS atténué. Une offre dont chaque dimension est
    renseignée, mais qui n'exige qu'une compétence, perd les deux tiers de
    ses 25 points d'un côté de l'inégalité sans que l'autre bouge.

    Ce n'est pas un défaut : le drapeau dit « peu de matière pour juger »,
    ce qui est exactement le cas d'une annonce de trois lignes. Mais il ne
    dit PLUS « peu de dimensions renseignées », et c'est un changement de
    sens qui devait être écrit quelque part (06 §1) plutôt que déduit du
    code par le prochain lecteur.
    """

    def test_le_drapeau_reagit_a_la_maigreur_pas_seulement_aux_trous(self) -> None:
        from app.matching import Confident

        candidat = CandidateInput(
            skills=("python", "sql", "docker"),
            seniority="senior",
            total_experience_years=5.0,
        )

        def offre(nb: int) -> JobInput:
            return JobInput(
                skills_required=tuple(
                    JobSkill(c) for c in ("python", "sql", "docker")[:nb]
                ),
                seniority=Confident("senior"),
                experience_min=3.0,
                experience_max=8.0,
            )

        # Mêmes dimensions connues des deux côtés, seule la MATIÈRE diffère.
        maigre = compute_match(candidat, offre(1))
        pleine = compute_match(candidat, offre(3))

        assert maigre.unknown_dimensions == pleine.unknown_dimensions, (
            "les deux offres doivent avoir exactement les mêmes trous — "
            "sinon le test mesure autre chose que l'atténuation"
        )
        assert maigre.low_data is True
        assert pleine.low_data is False

"""Corpus de démonstration et jeu d'évaluation — les garde-fous d'honnêteté.

Deux familles de vérifications, et elles n'ont rien de cosmétique.

**Le corpus ne doit jamais pouvoir passer pour du réel.** Ses offres sont
inventées. Une URL résolvable ou une activation en staging enverrait un
utilisateur postuler auprès d'une entreprise qui n'existe pas — exactement ce
que le produit s'interdit (« ne jamais transformer une hypothèse en fait »).
Ces deux barrières sont donc du code, pas de la procédure.

**Le jeu d'annotations doit être complet.** Une couverture partielle fausse
NDCG *en silence* : les offres non annotées disparaissent du classement au
lieu de compter pour zéro, et un moteur qui remonte une offre oubliée en tête
n'est jamais pénalisé.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.evaluation.dataset import (
    DEFAULT_EVALUATION_PATH,
    DEFAULT_JOBS_PATH,
    DatasetError,
    load_dataset,
)
from app.modules.ingestion.connectors.demo_corpus import (
    DemoCorpusConnector,
    DemoCorpusUnavailableError,
    build_demo_connector,
)


def _corpus() -> dict[str, Any]:
    return json.loads(DEFAULT_JOBS_PATH.read_text(encoding="utf-8"))


def _evaluation() -> dict[str, Any]:
    return json.loads(DEFAULT_EVALUATION_PATH.read_text(encoding="utf-8"))


def _write(tmp_path: Path, name: str, payload: dict[str, Any]) -> Path:
    chemin = tmp_path / name
    chemin.write_text(json.dumps(payload), encoding="utf-8")
    return chemin


class TestLeCorpusNePeutPasPasserPourDuReel:
    def test_toutes_les_url_sont_sur_le_tld_reserve(self) -> None:
        """`.invalid` (RFC 2606) ne résout jamais, par définition."""
        hotes = [
            item["url"].split("//", 1)[-1].split("/", 1)[0] for item in _corpus()["jobs"]
        ]
        assert hotes, "corpus vide"
        assert all(h.endswith(".invalid") for h in hotes), hotes

    def test_une_url_resolvable_est_refusee_au_chargement(self, tmp_path: Path) -> None:
        """Le contrôle est au CHARGEMENT, pas à la relecture humaine."""
        corpus = _corpus()
        corpus["jobs"] = corpus["jobs"][:1]
        corpus["jobs"][0]["url"] = "https://vraie-entreprise.fr/offres/1"
        chemin = _write(tmp_path, "jobs.json", corpus)

        with pytest.raises(DemoCorpusUnavailableError, match="RFC 2606"):
            DemoCorpusConnector(corpus_path=chemin).fetch(None)

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_activation_refusee_hors_developpement(self, env: str) -> None:
        """Staging compte autant que production : on y montre le produit.

        Le feature flag ne suffit délibérément pas — c'est la variable
        d'environnement oubliée qui provoque ce genre d'accident, donc c'est
        le code qui doit refuser.
        """
        settings = get_settings().model_copy(update={"env": env})
        with pytest.raises(DemoCorpusUnavailableError, match="FICTIVES"):
            build_demo_connector(settings)

    def test_activation_possible_en_developpement(self) -> None:
        settings = get_settings().model_copy(update={"env": "development"})
        assert build_demo_connector(settings).slug == "demo-corpus"


class TestLeConnecteurRendDesOffresExploitables:
    def test_le_cycle_rend_tout_le_corpus_et_est_complet(self) -> None:
        result = DemoCorpusConnector().fetch(None)
        assert len(result.jobs) == len(_corpus()["jobs"])
        assert result.complete is True
        assert result.parse_errors == 0

    def test_le_curseur_porte_la_version_du_corpus(self) -> None:
        """Bumper la version rejoue une ingestion complète."""
        assert DemoCorpusConnector().fetch(None).cursor == _corpus()["corpus_version"]

    def test_les_champs_structures_portent_une_confiance_de_un(self) -> None:
        """Ils sont structurés dans le fichier, pas devinés d'un libellé.

        Mentir ici fausserait l'indice de confiance que la mesure doit
        justement évaluer.
        """
        offre = next(j for j in DemoCorpusConnector().fetch(None).jobs if j.contract)
        assert offre.contract_conf == 1.0

    def test_chaque_offre_porte_une_reference_employeur(self) -> None:
        """C'est la clé de dédup étage 1 (D13) : sans elle, la chaîne
        d'ingestion n'est pas exercée dans les mêmes conditions qu'en réel."""
        assert all(job.employer_ref for job in DemoCorpusConnector().fetch(None).jobs)


class TestLeJeuDannotationsEstComplet:
    def test_le_jeu_livre_se_charge(self) -> None:
        dataset = load_dataset()
        assert len(dataset.cases) >= 3
        assert len(dataset.jobs) == len(_corpus()["jobs"])

    def test_chaque_profil_annote_tout_le_corpus(self) -> None:
        dataset = load_dataset()
        for case in dataset.cases:
            assert {a.job_ref for a in case.annotations} == set(dataset.jobs)

    def test_une_offre_non_annotee_est_refusee(self, tmp_path: Path) -> None:
        """Le cas dangereux : NDCG serait calculé, plus haut, et faux."""
        evaluation = _evaluation()
        evaluation["cases"][0]["annotations"].pop()
        chemin = _write(tmp_path, "eval.json", evaluation)

        with pytest.raises(DatasetError, match="non annotées"):
            load_dataset(evaluation_path=chemin)

    def test_une_annotation_en_double_est_refusee(self, tmp_path: Path) -> None:
        evaluation = _evaluation()
        annotations = evaluation["cases"][0]["annotations"]
        annotations.append(dict(annotations[0]))
        chemin = _write(tmp_path, "eval.json", evaluation)

        with pytest.raises(DatasetError, match="deux fois"):
            load_dataset(evaluation_path=chemin)

    def test_une_annotation_sur_une_offre_inexistante_est_refusee(
        self, tmp_path: Path
    ) -> None:
        evaluation = _evaluation()
        evaluation["cases"][0]["annotations"][0]["job_ref"] = "demo-inexistante"
        chemin = _write(tmp_path, "eval.json", evaluation)

        with pytest.raises(DatasetError, match="offres absentes"):
            load_dataset(evaluation_path=chemin)

    def test_une_pertinence_hors_echelle_est_refusee(self, tmp_path: Path) -> None:
        evaluation = _evaluation()
        evaluation["cases"][0]["annotations"][0]["relevance"] = 7
        chemin = _write(tmp_path, "eval.json", evaluation)

        with pytest.raises(DatasetError, match="hors de 0"):
            load_dataset(evaluation_path=chemin)

    def test_chaque_profil_a_au_moins_une_offre_pertinente(self) -> None:
        """Sans quoi NDCG n'est pas défini pour ce profil (gain idéal nul)."""
        for case in load_dataset().cases:
            assert any(a.relevance > 0 for a in case.annotations), case.candidate_id


class TestLeConnecteurTraduitVersLeVocabulaireCanonique:
    """Traduire est le travail d'un connecteur, pas celui du schéma.

    Le corpus est rédigé comme une annonce française (« cdi », « full ») ;
    la base ne connaît que des énumérations (`permanent`, `full_remote`).
    Sans cette traduction, l'ingestion échouait sur le type PostgreSQL et
    l'offre était **perdue** — trouvé en montant le chemin de bout en bout.
    """

    def test_les_contrats_sont_traduits(self) -> None:
        contrats = {job.contract for job in DemoCorpusConnector().fetch(None).jobs}
        assert contrats <= {"permanent", "fixed_term", "freelance", "internship",
                            "apprenticeship", "other"}
        assert "permanent" in contrats

    def test_les_politiques_de_teletravail_sont_traduites(self) -> None:
        politiques = {job.remote for job in DemoCorpusConnector().fetch(None).jobs}
        assert politiques <= {"onsite", "hybrid", "full_remote"}
        assert "full_remote" in politiques

    def test_un_vocabulaire_inconnu_est_une_erreur_pas_un_defaut_silencieux(
        self, tmp_path: Path
    ) -> None:
        """Retomber sur « other » laisserait une coquille fausser le matching."""
        corpus = _corpus()
        corpus["jobs"] = corpus["jobs"][:1]
        corpus["jobs"][0]["contract"] = "cdi-intermittent-du-spectacle"
        chemin = _write(tmp_path, "jobs.json", corpus)

        with pytest.raises(DemoCorpusUnavailableError, match="contract inconnu"):
            DemoCorpusConnector(corpus_path=chemin).fetch(None)

    def test_les_competences_souhaitees_sont_distinguees_des_exigees(self) -> None:
        """`skills_nice` pèse 10 % : tout mettre en « exigé » fausse 35 % du poids."""
        offres = DemoCorpusConnector().fetch(None).jobs
        avec_souhaitees = [j for j in offres if j.skills_nice]
        assert avec_souhaitees, "aucune offre ne distingue requis et souhaité"
        offre = next(j for j in offres if j.external_ref == "demo-001")
        assert set(offre.skills) == {"python", "postgresql", "fastapi"}
        assert set(offre.skills_nice) == {"docker", "kubernetes"}

    def test_les_secteurs_suivent_le_referentiel(self) -> None:
        """Codes du référentiel `sectors` (lettres NAF), pas des étiquettes.

        Un code hors référentiel viole la clé étrangère et fait perdre
        l'offre ; une valeur absente laisse la dimension secteur inconnue.
        """
        secteurs = {job.sector for job in DemoCorpusConnector().fetch(None).jobs}
        assert None not in secteurs
        assert secteurs <= {"C", "F", "G", "H", "J", "K", "M", "N", "P", "Q"}

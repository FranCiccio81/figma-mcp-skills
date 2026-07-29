"""La liste d'offres porte le score, et « trier par compatibilité » trie.

Défaut trouvé en parcourant l'application pour de vrai avant déploiement :

    GET /jobs?q=python&sort=match     → items[].match = null  (les 6)
    GET /jobs?q=python&sort=relevance → ordre IDENTIQUE, octet pour octet
    GET /matches                      → items[].match = {"score":98,…}

Le code disait pourquoi : « ``sort=match`` retombe sur ``relevance`` tant que
le scoring n'est pas livré (M3) » et « ``JobCard.match`` toujours ``null`` au
M2 ». Le scoring **était** livré — ``/matches`` rendait des scores, le front
affichait un sélecteur « Compatibilité » et un composant ``MatchBadge`` sur
chaque carte, et la carte « Meilleures correspondances » du tableau de bord
renvoyait vers ``/offres?sort=match``.

C'est-à-dire : le produit conduisait l'utilisateur, depuis un écran qui
affiche des scores, vers un écran où ils disparaissent et où le tri annoncé
ne fait rien. Deux commentaires « M2 » oubliés, sur la fonction centrale.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.modules.jobs.repository import MatchRowSummary
from tests.unit.jobs.conftest import InMemoryJobsRepository, make_posting
from tests.unit.jobs.test_jobs_api import JOBS_URL, register


def _resume(score: int, *, bloquant: bool = False) -> MatchRowSummary:
    return MatchRowSummary(
        score=score, confidence=70, low_data=False, has_blocking=bloquant
    )


@pytest.fixture
def connecte(client: TestClient) -> TestClient:
    register(client)
    return client


@pytest.fixture
def profil_valide(
    connecte: TestClient, jobs_repository: InMemoryJobsRepository
) -> uuid.UUID:
    """Un profil VALIDÉ — condition d'existence d'un score.

    Son identifiant d'utilisateur est lu sur ``/me`` plutôt que deviné : la
    jointure porte sur le profil de la personne connectée, et un test qui se
    tromperait d'utilisateur passerait en ne mesurant rien.
    """
    user_id = uuid.UUID(connecte.get("/api/v1/me").json()["id"])
    profile_id = uuid.uuid4()
    jobs_repository.profiles[user_id] = profile_id
    return profile_id


class TestLaCarteDoffrePorteLeScore:
    def test_le_score_de_lutilisateur_est_rendu(
        self, connecte, jobs_repository, profil_valide
    ) -> None:
        offre = jobs_repository.add(make_posting(title="Développeuse Python"))
        jobs_repository.matches[(profil_valide, offre.id)] = _resume(87)

        page = connecte.get(JOBS_URL).json()

        carte = next(i for i in page["items"] if i["id"] == str(offre.id))
        assert carte["match"] == {
            "score": 87,
            "confidence": 70,
            "low_data": False,
            "has_blocking": False,
        }

    def test_une_offre_non_scoree_rend_null_et_reste_visible(
        self, connecte, jobs_repository, profil_valide
    ) -> None:
        """Le scoring est asynchrone : une offre fraîchement ingérée n'a pas
        encore de ligne. Elle ne doit pas disparaître de la recherche pour
        autant — c'est une jointure externe, pas un filtre."""
        offre = jobs_repository.add(make_posting(title="Offre toute neuve"))

        page = connecte.get(JOBS_URL).json()

        carte = next(i for i in page["items"] if i["id"] == str(offre.id))
        assert carte["match"] is None

    def test_sans_profil_valide_aucune_carte_ne_porte_de_score(
        self, connecte, jobs_repository
    ) -> None:
        """Un profil ``draft`` n'a aucun ``match_results`` : joindre pour lui
        coûterait une jointure garantie vide à chaque recherche."""
        jobs_repository.add(make_posting(title="Développeuse Python"))

        page = connecte.get(JOBS_URL).json()

        assert all(item["match"] is None for item in page["items"])

    def test_un_bloquant_est_signale_sur_la_carte(
        self, connecte, jobs_repository, profil_valide
    ) -> None:
        """L'offre reste dans la liste, badgée — jamais retirée (06 §1)."""
        offre = jobs_repository.add(make_posting(title="Poste sur site"))
        jobs_repository.matches[(profil_valide, offre.id)] = _resume(46, bloquant=True)

        page = connecte.get(JOBS_URL).json()

        carte = next(i for i in page["items"] if i["id"] == str(offre.id))
        assert carte["match"]["has_blocking"] is True
        assert carte["match"]["score"] == 46, "un bloquant ne met pas le score à zéro"


class TestTrierParCompatibiliteTrieVraiment:
    def _titres(self, page: dict) -> list[str]:
        return [item["title"] for item in page["items"]]

    def test_lordre_suit_les_scores_decroissants(
        self, connecte, jobs_repository, profil_valide
    ) -> None:
        attendus = {"Faible": 30, "Excellente": 95, "Moyenne": 60}
        for titre, score in attendus.items():
            offre = jobs_repository.add(make_posting(title=titre))
            jobs_repository.matches[(profil_valide, offre.id)] = _resume(score)

        page = connecte.get(f"{JOBS_URL}?sort=match").json()

        assert self._titres(page) == ["Excellente", "Moyenne", "Faible"]

    def test_les_offres_non_scorees_passent_apres(
        self, connecte, jobs_repository, profil_valide
    ) -> None:
        """Et non « avant » ni « n'importe où » : un ``NULL`` en tête ferait
        remonter les offres les moins connues au sommet d'un tri qui promet
        la compatibilité."""
        scoree = jobs_repository.add(make_posting(title="Scorée faiblement"))
        jobs_repository.matches[(profil_valide, scoree.id)] = _resume(20)
        jobs_repository.add(make_posting(title="Jamais scorée"))

        page = connecte.get(f"{JOBS_URL}?sort=match").json()

        assert self._titres(page) == ["Scorée faiblement", "Jamais scorée"]

    def test_le_tri_par_compatibilite_differe_du_tri_par_pertinence(
        self, connecte, jobs_repository, profil_valide
    ) -> None:
        """LE test qui aurait attrapé le défaut : les deux tris rendaient un
        ordre identique, octet pour octet."""
        peu_pertinente = jobs_repository.add(
            make_posting(title="Python", description_text="python python python")
        )
        jobs_repository.matches[(profil_valide, peu_pertinente.id)] = _resume(10)
        tres_compatible = jobs_repository.add(
            make_posting(title="Python", description_text="python")
        )
        jobs_repository.matches[(profil_valide, tres_compatible.id)] = _resume(99)

        par_match = connecte.get(f"{JOBS_URL}?q=python&sort=match").json()
        par_pertinence = connecte.get(f"{JOBS_URL}?q=python&sort=relevance").json()

        assert self._titres(par_match) != self._titres(par_pertinence) or [
            i["id"] for i in par_match["items"]
        ] != [i["id"] for i in par_pertinence["items"]]
        assert par_match["items"][0]["id"] == str(tres_compatible.id)

    def test_sans_profil_valide_le_tri_retombe_proprement(
        self, connecte, jobs_repository
    ) -> None:
        """Le repli demeure là où il a du sens : sans score, trier par
        compatibilité n'en a aucun. Aucune erreur, pas de 422."""
        jobs_repository.add(make_posting(title="Une offre"))

        reponse = connecte.get(f"{JOBS_URL}?sort=match")

        assert reponse.status_code == 200


class TestLaPaginationSurvitAuTriParScore:
    def test_deux_pages_couvrent_tout_sans_doublon(
        self, connecte, jobs_repository, profil_valide
    ) -> None:
        """La pagination keyset compare un tuple ``(score, id)``. Un ``NULL``
        y rendrait toute comparaison indéterminée et la page suivante
        reviendrait vide — d'où la valeur de substitution ``-1`` plutôt qu'un
        ``NULLS LAST``."""
        attendus = []
        for index in range(5):
            offre = jobs_repository.add(make_posting(title=f"Offre {index}"))
            attendus.append(str(offre.id))
            if index % 2 == 0:  # une sur deux reste non scorée
                jobs_repository.matches[(profil_valide, offre.id)] = _resume(
                    50 + index
                )

        page1 = connecte.get(f"{JOBS_URL}?sort=match&limit=2").json()
        page2 = connecte.get(
            f"{JOBS_URL}?sort=match&limit=2&cursor={page1['next_cursor']}"
        ).json()

        vus = [i["id"] for i in page1["items"]] + [i["id"] for i in page2["items"]]
        assert len(vus) == len(set(vus)), "une offre est servie deux fois"
        assert len(vus) == 4


def test_le_scoring_version_est_celui_du_moteur(
    connecte, jobs_repository, profil_valide, monkeypatch
) -> None:
    """Un score calculé par une version PRÉCÉDENTE n'est pas comparable à un
    score courant : l'afficher mélangerait deux échelles sur le même écran.

    La jointure filtre donc sur ``scoring_version``, et la valeur vient du
    moteur — jamais d'une constante recopiée.
    """
    vues: list[str | None] = []
    vraie_recherche = jobs_repository.search

    async def espion(**kwargs):
        vues.append(kwargs.get("scoring_version"))
        return await vraie_recherche(**kwargs)

    monkeypatch.setattr(jobs_repository, "search", espion)
    jobs_repository.add(make_posting(title="Une offre"))

    connecte.get(JOBS_URL)

    from app.matching import get_config

    assert vues == [get_config().scoring_version]


def test_sans_profil_valide_aucune_jointure_nest_demandee(
    connecte, jobs_repository, monkeypatch
) -> None:
    """Économie réelle : la recherche est la requête la plus chaude du
    produit, et joindre ``match_results`` pour un profil qui n'en a aucun
    serait un coût pur."""
    vues: list[uuid.UUID | None] = []
    vraie_recherche = jobs_repository.search

    async def espion(**kwargs):
        vues.append(kwargs.get("profile_id"))
        return await vraie_recherche(**kwargs)

    monkeypatch.setattr(jobs_repository, "search", espion)
    jobs_repository.add(make_posting(title="Une offre"))

    connecte.get(JOBS_URL)

    assert vues == [None]

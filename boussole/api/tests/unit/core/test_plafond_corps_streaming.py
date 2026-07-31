"""Le plafond de corps tient aussi quand le client ne déclare pas sa taille.

Défaut trouvé en revue avant déploiement. ``BodySizeLimitMiddleware`` ne
lisait que ``Content-Length`` — un en-tête *absent* d'une requête en
``Transfer-Encoding: chunked``. Le contrôle vérifiait donc la DÉCLARATION du
client et jamais ce qu'il envoyait : il ne protégeait que d'un attaquant
honnête. Mesuré, sans authentification ::

    Content-Length 12 Mo + 1 octet      → 413        (le seul cas testé)
    chunked 36 Mo, sans Content-Length  → 422        ← reçu en entier
                                          pic mémoire 108 Mo

C'est exactement l'épuisement mémoire que ce middleware existe pour empêcher
(8 requêtes concurrentes de 100 Mo → 1,94 Go, OOMKill sur un conteneur de
1 Go), atteignable par une option de la ligne de commande de curl.

**Pourquoi ces tests parlent ASGI et pas HTTP.** ``TestClient`` livre le
corps entier en UN SEUL message ``http.request``, quelle que soit la façon
dont on l'a produit : un envoi de 300 Mo arrive d'un bloc, le compteur le
voit d'un coup, et le test ne distingue plus « borné au fil de l'eau » de
« refusé après avoir tout accumulé ». Le premier test écrit ici passait au
vert sans rien prouver. Uvicorn, lui, livre des morceaux successifs
(``more_body=True``) — c'est cette forme-là qu'il faut piloter pour vérifier
la propriété qui compte : **l'application ne reçoit jamais plus que le
plafond, quoi que le client envoie.**
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import MAX_REQUEST_BODY_BYTES, BodySizeLimitMiddleware

MO = 1024 * 1024


class _Espion:
    """Application ASGI en aval : lit tout ce qu'on lui donne et compte."""

    def __init__(self) -> None:
        self.recu = 0
        self.appelee = False

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.appelee = True
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            self.recu += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send(
            {"type": "http.response.start", "status": 200, "headers": [], }
        )
        await send({"type": "http.response.body", "body": b"ok"})


def _scope(entetes: list[tuple[bytes, bytes]] | None = None) -> dict[str, Any]:
    return {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/auth/login",
        "raw_path": b"/api/v1/auth/login",
        "query_string": b"",
        "root_path": "",
        "headers": entetes or [(b"content-type", b"application/json")],
        "client": ("203.0.113.9", 51234),
        "server": ("testserver", 80),
    }


def _flux_chunked(total_mo: int) -> Any:
    """``receive`` à la manière d'uvicorn : des morceaux successifs.

    Compte aussi combien de fois il a été appelé — c'est ce nombre qui dit si
    le middleware a réellement CESSÉ de lire, ou s'il a tout absorbé avant de
    se prononcer.
    """
    etat = {"restants": total_mo, "appels": 0}

    async def receive() -> Any:
        etat["appels"] += 1
        if etat["restants"] <= 0:
            return {"type": "http.request", "body": b"", "more_body": False}
        etat["restants"] -= 1
        return {
            "type": "http.request",
            "body": b"x" * MO,
            "more_body": etat["restants"] > 0,
        }

    return receive, etat


async def _jouer(receive: Any, entetes: list[tuple[bytes, bytes]] | None = None):
    espion = _Espion()
    envoyes: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        envoyes.append(message)

    await BodySizeLimitMiddleware(espion)(_scope(entetes), receive, send)
    statut = next(
        (m["status"] for m in envoyes if m["type"] == "http.response.start"), None
    )
    return statut, espion, envoyes


class TestUnCorpsNonDeclareEstBorneAuFilDeLeau:
    async def test_un_envoi_massif_est_refuse(self) -> None:
        receive, _ = _flux_chunked(300)
        statut, _espion, _ = await _jouer(receive)
        assert statut == 413

    async def test_lapplication_ne_recoit_jamais_plus_que_le_plafond(self) -> None:
        """LE test qui aurait attrapé le défaut.

        Répondre 413 ne suffit pas : si les 300 Mo ont transité par la mémoire
        du processus avant le refus, l'OOM a déjà eu lieu et le code de statut
        ne console personne.
        """
        receive, _ = _flux_chunked(300)
        _statut, espion, _ = await _jouer(receive)

        assert espion.recu <= MAX_REQUEST_BODY_BYTES + MO, (
            f"{espion.recu / MO:.0f} Mo ont atteint l'application pour un "
            f"plafond de {MAX_REQUEST_BODY_BYTES / MO:.0f} Mo"
        )

    async def test_la_lecture_sarrete_vraiment(self) -> None:
        """Le middleware doit CESSER d'appeler ``receive``, pas se contenter
        de compter jusqu'au bout."""
        receive, etat = _flux_chunked(300)
        await _jouer(receive)

        assert etat["appels"] <= MAX_REQUEST_BODY_BYTES // MO + 2, (
            f"{etat['appels']} lectures sur 300 : le flux a été absorbé en entier"
        )
        assert etat["restants"] > 250, "la source n'a presque pas été consommée"

    async def test_une_seule_reponse_est_emise(self) -> None:
        """L'application interrompue produit sa propre erreur derrière nous
        (FastAPI rend 400 « error parsing the body »). Deux réponses sur une
        requête, c'est un flux HTTP malformé."""
        receive, _ = _flux_chunked(300)
        _statut, _espion, envoyes = await _jouer(receive)

        debuts = [m for m in envoyes if m["type"] == "http.response.start"]
        assert len(debuts) == 1


class TestLeTraficLegitimePasse:
    """Un plafond qui casse l'usage normal n'est pas un correctif."""

    async def test_un_corps_chunked_sous_le_plafond_arrive_entier(self) -> None:
        receive, _ = _flux_chunked(5)
        statut, espion, _ = await _jouer(receive)

        assert statut == 200
        assert espion.recu == 5 * MO

    async def test_un_import_de_cv_au_maximum_passe(self) -> None:
        """10 Mo est la taille maximale d'un CV ; le plafond doit lui laisser
        la place, enveloppe multipart comprise."""
        receive, _ = _flux_chunked(10)
        statut, espion, _ = await _jouer(receive)

        assert statut == 200
        assert espion.recu == 10 * MO

    async def test_une_requete_sans_corps_passe(self) -> None:
        async def receive() -> Any:
            return {"type": "http.request", "body": b"", "more_body": False}

        statut, espion, _ = await _jouer(receive)
        assert statut == 200 and espion.recu == 0


class TestLaDeclarationResteVerifieeEnPremier:
    """Quand le client annonce sa taille, on refuse sans lire un octet :
    l'attaquant honnête n'occupe jamais de mémoire du tout."""

    async def test_un_content_length_excessif_est_refuse_sans_lecture(self) -> None:
        lectures = {"n": 0}

        async def receive() -> Any:
            lectures["n"] += 1
            return {"type": "http.request", "body": b"x" * MO, "more_body": True}

        statut, espion, _ = await _jouer(
            receive,
            [
                (b"content-type", b"application/json"),
                (b"content-length", str(MAX_REQUEST_BODY_BYTES + 1).encode()),
            ],
        )

        assert statut == 413
        assert lectures["n"] == 0, "le corps n'aurait pas dû être lu du tout"
        assert espion.appelee is False, "l'application n'aurait pas dû être atteinte"

    async def test_un_content_length_illisible_ne_fait_pas_tomber_le_service(
        self,
    ) -> None:
        """Un en-tête forgé ne doit pas produire une 500 : on retombe sur le
        comptage réel, qui ne se laisse pas raconter d'histoire."""
        receive, _ = _flux_chunked(2)
        statut, espion, _ = await _jouer(
            receive,
            [
                (b"content-type", b"application/json"),
                (b"content-length", b"pas-un-nombre"),
            ],
        )

        assert statut == 200 and espion.recu == 2 * MO

    async def test_un_content_length_menteur_ne_debride_pas_le_flux(self) -> None:
        """Annoncer 1 Ko puis envoyer 300 Mo : c'est le comptage réel qui
        tranche, pas la déclaration."""
        receive, _ = _flux_chunked(300)
        statut, espion, _ = await _jouer(
            receive,
            [
                (b"content-type", b"application/json"),
                (b"content-length", b"1024"),
            ],
        )

        assert statut == 413
        assert espion.recu <= MAX_REQUEST_BODY_BYTES + MO


class TestBoutEnBout:
    """Le contrat vu du client, à travers la pile complète.

    ``TestClient`` livre le corps en un seul message : ces tests valident le
    code de statut rendu, pas la borne au fil de l'eau (voir l'en-tête du
    fichier). Ils restent utiles — c'est ici qu'on verrait un middleware
    correct mais mal branché dans ``create_app``.
    """

    def test_un_corps_chunked_excessif_rend_413(self, client: TestClient) -> None:
        def flux():
            for _ in range(3):
                yield b"x" * (MAX_REQUEST_BODY_BYTES // 2)

        reponse = client.post(
            "/api/v1/auth/login",
            content=flux(),
            headers={"content-type": "application/json"},
        )
        assert reponse.status_code == 413
        assert reponse.json()["type"].endswith("payload_too_large")

    def test_le_trafic_legitime_passe_toujours(self, client: TestClient) -> None:
        reponse = client.post(
            "/api/v1/auth/login",
            json={"email": "personne@exemple.fr", "password": "quelconque"},
        )
        assert reponse.status_code == 401  # identifiants faux, pas 413

    @pytest.mark.parametrize("chemin", ["/healthz", "/readyz"])
    def test_les_sondes_ne_sont_pas_genees(self, client: TestClient, chemin: str) -> None:
        """Le middleware est le plus externe : une erreur ici couperait les
        sondes de l'orchestrateur, donc le service entier."""
        assert client.get(chemin).status_code in (200, 503)

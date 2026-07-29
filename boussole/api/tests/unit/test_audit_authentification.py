"""Les événements d'authentification sont journalisés (09 §5.7).

Défaut trouvé en revue finale. 09 §5.7 liste « inscription, **login
(succès/échec)**, logout ». Aucun n'était écrit — mesuré après 700+ échecs
de connexion contre l'API réelle :

    select action, count(*) from audit_log group by action;
     data_export_downloaded|2   privacy_export_requested|2
     privacy_export_ready|2     account_deletion_requested|1
     account_purge_completed|1

Deux conséquences, la seconde pire que la première :

1. le modèle de menace promet une « alerte sur pics d'échecs » — il n'y avait
   rien à alerter, et l'attaque par force brute mesurée dans la même revue
   (500 tentatives, aucun rejet) n'aurait laissé aucune trace ;
2. la justification écrite du fail-open du limiteur de connexion disait « le
   mot de passe reste haché, **l'audit reste écrit** ». Il ne l'était pas :
   un arbitrage de sécurité s'appuyait sur une compensation inexistante.

Ce fichier vérifie autant ce qui EST écrit que ce qui ne l'est pas — un
journal de sécurité qui accumule les adresses tentées devient lui-même la
cible.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.modules.auth.audit import (
    LOGGED_OUT,
    LOGIN_FAILED,
    LOGIN_SUCCEEDED,
    REGISTERED,
    truncate_ip,
)
from tests.unit.conftest import InMemoryAuthRepository

EMAIL = "camille@example.eu"
MOT_DE_PASSE = "un mot de passe très long"


def _inscrire(client: TestClient, email: str = EMAIL) -> None:
    reponse = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": MOT_DE_PASSE,
            "locale": "fr",
            "accepted_terms_version": "2026-07",
            "accepted_privacy_version": "2026-07",
        },
    )
    assert reponse.status_code == 201


def _actions(repo: InMemoryAuthRepository) -> list[str]:
    return [action for _uid, action, _meta in repo.audit]


class TestLesQuatreEvenementsSontEcrits:
    def test_inscription(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        _inscrire(client)
        assert _actions(auth_repository) == [REGISTERED]

    def test_connexion_reussie(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        _inscrire(client)
        auth_repository.audit.clear()

        assert (
            client.post(
                "/api/v1/auth/login", json={"email": EMAIL, "password": MOT_DE_PASSE}
            ).status_code
            == 204
        )
        assert _actions(auth_repository) == [LOGIN_SUCCEEDED]

    def test_connexion_echouee(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        """C'est l'événement que produit une attaque par force brute, en
        rafale. Sans lui, l'alerte promise n'a rien à compter."""
        _inscrire(client)
        auth_repository.audit.clear()

        assert (
            client.post(
                "/api/v1/auth/login", json={"email": EMAIL, "password": "faux"}
            ).status_code
            == 401
        )
        assert _actions(auth_repository) == [LOGIN_FAILED]

    def test_deconnexion(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        _inscrire(client)
        auth_repository.audit.clear()

        assert (
            client.post(
                "/api/v1/auth/logout",
                headers={"X-CSRF-Token": client.cookies["boussole_csrf"]},
            ).status_code
            == 204
        )
        assert _actions(auth_repository) == [LOGGED_OUT]


class TestLEchecEstRattacheAuCompteSansNommerLadresse:
    def test_un_echec_sur_compte_existant_porte_son_identifiant(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        """Compter les échecs PAR COMPTE est ce qui distingue une personne
        qui se trompe d'une attaque ciblée."""
        _inscrire(client)
        user_id = uuid.UUID(client.get("/api/v1/me").json()["id"])
        auth_repository.audit.clear()

        client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "faux"})

        (uid, action, _meta) = auth_repository.audit[0]
        assert (uid, action) == (user_id, LOGIN_FAILED)

    def test_un_echec_sur_compte_inexistant_na_pas_didentifiant(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        client.post(
            "/api/v1/auth/login",
            json={"email": "personne@example.eu", "password": "faux"},
        )

        (uid, action, _meta) = auth_repository.audit[0]
        assert (uid, action) == (None, LOGIN_FAILED)

    @pytest.mark.parametrize("email", [EMAIL, "personne@example.eu"])
    def test_ladresse_tentee_nest_JAMAIS_ecrite(
        self, client: TestClient, auth_repository: InMemoryAuthRepository, email: str
    ) -> None:
        """Sur un échec, l'adresse appartient souvent à quelqu'un qui n'a pas
        de compte ici. La conserver ferait de ce journal une base d'adresses,
        donc une cible."""
        _inscrire(client)
        auth_repository.audit.clear()

        client.post("/api/v1/auth/login", json={"email": email, "password": "faux"})

        for _uid, _action, meta in auth_repository.audit:
            assert email not in str(meta)
            assert "faux" not in str(meta)

    def test_le_mot_de_passe_nest_jamais_ecrit(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        _inscrire(client)
        auth_repository.audit.clear()
        client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "SecretTresLong-42"}
        )
        assert "SecretTresLong-42" not in str(auth_repository.audit)


class TestLIpEstTronquee:
    """Une IP complète est une donnée personnelle qu'on n'a pas besoin de
    conserver pour repérer un pic d'échecs. Le réseau suffit."""

    @pytest.mark.parametrize(
        "brute,attendu",
        [
            ("192.0.2.147", "192.0.2.0/24"),
            ("10.1.2.3", "10.1.2.0/24"),
            ("2001:db8:1234:5678::1", "2001:db8:1234::/48"),
        ],
    )
    def test_troncature(self, brute: str, attendu: str) -> None:
        assert truncate_ip(brute) == attendu

    @pytest.mark.parametrize("brute", [None, "", "pas-une-ip", "999.999.999.999"])
    def test_une_valeur_illisible_ne_produit_rien(self, brute: str | None) -> None:
        """Plutôt qu'un champ à moitié faux, pas de champ."""
        assert truncate_ip(brute) is None

    def test_le_journal_porte_le_reseau_et_la_trace(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        _inscrire(client)
        (_uid, _action, meta) = auth_repository.audit[0]
        assert "trace_id" in meta
        assert "/" in str(meta.get("ip_network", "")) or "ip_network" not in meta


class TestUneInscriptionNeutreEstQuandMemeJournalisee:
    def test_une_rafale_sur_des_adresses_prises_laisse_une_trace(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        """La réponse est neutre pour le CLIENT (anti-énumération), pas pour
        l'exploitant : une rafale d'inscriptions sur des adresses existantes
        est une tentative d'énumération, et c'est le seul endroit où elle se
        voit."""
        _inscrire(client)
        client.cookies.clear()
        auth_repository.audit.clear()

        _inscrire(client)  # même adresse : 201 neutre, aucun compte créé

        (uid, action, meta) = auth_repository.audit[0]
        assert action == REGISTERED
        assert uid is None, "aucun compte créé : pas d'identifiant à rattacher"
        assert meta["created"] is False

    def test_une_inscription_reelle_est_marquee_comme_telle(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        _inscrire(client)
        (uid, _action, meta) = auth_repository.audit[0]
        assert meta["created"] is True
        assert uid is not None


class TestUnJournalIndisponibleNeBloquePersonne:
    def test_la_connexion_aboutit_meme_si_laudit_echoue(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        """Le contraire ferait d'une table de journal une dépendance
        d'authentification : une panne de la table couperait la connexion de
        tout le monde."""
        _inscrire(client)

        async def casse(*_a: object, **_k: object) -> None:
            raise RuntimeError("journal indisponible")

        auth_repository.add_audit = casse  # type: ignore[method-assign]

        reponse = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": MOT_DE_PASSE}
        )
        assert reponse.status_code == 204

"""L'inscription ne dit pas, par sa durée, ce que sa réponse tait.

Défaut trouvé en revue avant déploiement. ``POST /auth/register`` rend un 201
strictement identique que l'adresse soit libre ou déjà prise — c'est la
défense anti-énumération (🟡 Q31). Mais le chemin « adresse prise » revenait
AVANT le hachage du mot de passe. Mesuré, médiane sur 12 tentatives ::

    adresse déjà prise :   7,3 ms
    adresse libre      : 108,0 ms
    rapport            : ×14,8

Un facteur 15 se lit à l'œil nu, même à travers un réseau. La réponse
n'apprenait rien, le chronomètre disait tout — et l'information révélée
n'est pas anodine : « cette personne a un compte sur une plateforme de
recherche d'emploi » se teste adresse par adresse, y compris par un
employeur sur celles de ses salariés.

**Deux tests pour une propriété.** Le test structurel est la garde fiable :
il vérifie que le hachage a lieu sur les deux chemins, ce qui est vrai ou
faux sans dépendre de la machine. Le test chronométré vérifie ce qui compte
vraiment — car on pourrait très bien hacher partout et réintroduire l'écart
ailleurs — avec un seuil large : l'écart mesuré valait ×14,8, il vaut ×1,2
après correctif, et le seuil est à ×4. Une machine chargée ne le fait pas
tomber ; un retour anticipé, si.
"""

import statistics
import time

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.service as service
from tests.unit.conftest import InMemoryAuthRepository

MOT_DE_PASSE = "un mot de passe très long"
OCCUPEE = "occupe@exemple.fr"


def _inscrire(client: TestClient, email: str):
    client.cookies.clear()
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": MOT_DE_PASSE,
            "locale": "fr",
            "accepted_terms_version": "2026-07",
            "accepted_privacy_version": "2026-07",
        },
    )


class TestLeHachageALieuSurLesDeuxChemins:
    """Garde structurelle — déterministe, insensible à la charge machine."""

    @pytest.fixture
    def compteur(self, monkeypatch: pytest.MonkeyPatch) -> list[int]:
        appels = [0]
        vrai = service.hash_password

        def espion(mot_de_passe: str) -> str:
            appels[0] += 1
            return vrai(mot_de_passe)

        monkeypatch.setattr(service, "hash_password", espion)
        return appels

    def test_sur_une_adresse_libre(self, client: TestClient, compteur: list[int]) -> None:
        assert _inscrire(client, "libre@exemple.fr").status_code == 201
        assert compteur[0] == 1

    def test_sur_une_adresse_deja_prise(
        self, client: TestClient, compteur: list[int]
    ) -> None:
        """C'est LE test qui aurait attrapé le défaut : sans hachage sur ce
        chemin, la réponse part quinze fois plus vite."""
        _inscrire(client, OCCUPEE)
        compteur[0] = 0

        assert _inscrire(client, OCCUPEE).status_code == 201
        assert compteur[0] == 1, (
            "le mot de passe n'est pas haché quand l'adresse est prise : la "
            "durée de réponse trahit l'existence du compte"
        )

    def test_le_hachage_ne_sert_a_rien_dautre(
        self, client: TestClient, auth_repository: InMemoryAuthRepository
    ) -> None:
        """Hacher pour égaliser la durée ne doit pas créer de compte ni
        conserver quoi que ce soit du mot de passe tenté."""
        _inscrire(client, OCCUPEE)
        avant = len(auth_repository.users_by_id)

        _inscrire(client, OCCUPEE)

        assert len(auth_repository.users_by_id) == avant, "aucun compte ne doit naître"


class TestLaReponseResteNeutre:
    """La contrepartie : égaliser la durée ne doit rien changer au contrat
    anti-énumération déjà en place."""

    def test_les_deux_chemins_rendent_201(self, client: TestClient) -> None:
        assert _inscrire(client, OCCUPEE).status_code == 201
        assert _inscrire(client, OCCUPEE).status_code == 201
        assert _inscrire(client, "autre@exemple.fr").status_code == 201

    def test_les_cookies_ont_la_meme_forme(self, client: TestClient) -> None:
        """Un jeu de cookies différent serait un oracle aussi sûr qu'une
        durée différente."""
        _inscrire(client, OCCUPEE)
        prise = set(_inscrire(client, OCCUPEE).cookies.keys())
        libre = set(_inscrire(client, "encore@exemple.fr").cookies.keys())
        assert prise == libre and prise


class TestLesDureesSontIndistinguables:
    """Ce qui compte vraiment — hacher partout puis réintroduire l'écart
    ailleurs passerait la garde structurelle."""

    ECHANTILLONS = 9
    #: L'écart mesuré valait ×14,8 avant correctif et ×1,2 après. À ×4, une
    #: machine chargée ne fait pas tomber le test, un retour anticipé si.
    RAPPORT_MAX = 4.0

    @staticmethod
    def _mediane_ms(client: TestClient, emails) -> float:
        durees = []
        for email in emails:
            debut = time.perf_counter()
            reponse = _inscrire(client, email)
            durees.append((time.perf_counter() - debut) * 1000)
            assert reponse.status_code == 201
        return statistics.median(durees)

    def test_le_chronometre_ne_distingue_pas_les_deux_cas(
        self, client: TestClient
    ) -> None:
        _inscrire(client, OCCUPEE)

        prise = self._mediane_ms(client, [OCCUPEE] * self.ECHANTILLONS)
        libre = self._mediane_ms(
            client, [f"libre{i}@exemple.fr" for i in range(self.ECHANTILLONS)]
        )

        rapport = max(prise, libre) / max(min(prise, libre), 0.001)
        assert rapport < self.RAPPORT_MAX, (
            f"adresse prise {prise:.1f} ms contre adresse libre {libre:.1f} ms "
            f"(×{rapport:.1f}) : la durée de réponse révèle l'existence du compte"
        )

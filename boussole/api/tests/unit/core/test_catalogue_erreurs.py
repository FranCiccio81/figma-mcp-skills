"""Tout code d'erreur que l'API sait produire est traduisible côté client.

Défaut trouvé en revue avant déploiement. Cinq points d'appel du front
affichaient ``problem.detail`` — la prose composée ici, en français — et la
préféraient à leur propre traduction. Un utilisateur anglophone lisait
« Validez votre profil avant de générer un contenu. »

Le correctif côté front traduit le CODE et non la prose. Il ne tient que si
le catalogue suit : un code ajouté ici sans entrée dans ``messages/*.json``
retombe silencieusement sur le message générique, et la personne perd
l'information utile — c'est une dégradation muette, exactement le genre que
cette suite existe pour attraper.

La garde est ICI et non côté front parce que c'est ici que les codes
naissent. Le test lit les deux artefacts et les confronte.
"""

import json
import re
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[3]
APP = API / "app"
MESSAGES = API.parent / "web" / "messages"

#: Codes qui ne remontent jamais à un client : produits par des sondes ou des
#: chemins internes, jamais rendus dans une réponse qu'une page affiche.
_HORS_INTERFACE = frozenset({"not_ready"})


def _codes_de_lapi() -> set[str]:
    codes: set[str] = set()
    for chemin in APP.rglob("*.py"):
        codes |= set(re.findall(r'code="([a-z_]+)"', chemin.read_text(encoding="utf-8")))
    return codes - _HORS_INTERFACE


def _catalogue(langue: str) -> dict[str, str]:
    contenu = json.loads((MESSAGES / f"{langue}.json").read_text(encoding="utf-8"))
    return contenu["errors"]["byCode"]


class TestLeCatalogueSuitLApi:
    def test_il_y_a_bien_des_codes_a_couvrir(self) -> None:
        """Sans quoi les tests suivants passeraient sur l'ensemble vide."""
        assert len(_codes_de_lapi()) > 20

    @pytest.mark.parametrize("langue", ["fr", "en"])
    def test_chaque_code_a_son_message(self, langue: str) -> None:
        manquants = sorted(_codes_de_lapi() - set(_catalogue(langue)))
        assert manquants == [], (
            f"codes produits par l'API et absents de messages/{langue}.json : "
            f"{manquants} — l'utilisateur verra le message générique à la "
            f"place de l'information utile, sans que rien ne le signale"
        )

    @pytest.mark.parametrize("langue", ["fr", "en"])
    def test_le_catalogue_ne_decrit_pas_de_code_fantome(self, langue: str) -> None:
        """L'inverse compte aussi : une entrée pour un code supprimé laisse
        croire qu'un cas est traité alors qu'il n'existe plus."""
        fantomes = sorted(set(_catalogue(langue)) - _codes_de_lapi() - _HORS_INTERFACE)
        assert fantomes == [], f"codes catalogués mais jamais produits : {fantomes}"

    def test_les_deux_langues_couvrent_les_memes_codes(self) -> None:
        assert set(_catalogue("fr")) == set(_catalogue("en"))

    def test_aucun_message_anglais_nest_resté_en_francais(self) -> None:
        """La façon la plus discrète de réintroduire le défaut : recopier la
        valeur française dans ``en.json``."""
        fr, en = _catalogue("fr"), _catalogue("en")
        identiques = sorted(code for code in fr if fr[code] == en[code])
        assert identiques == [], identiques

"""Le contrat publié décrit EXACTEMENT ce que l'API sert.

Écart trouvé en revue avant déploiement : **quatorze routes servies et
absentes** de ``cv-job-matching/openapi.yaml`` — dont toute l'édition de
profil (compétences, formations, langues), le détail, la modification et la
suppression d'une candidature, et le téléchargement de l'archive d'export
RGPD. Toutes appelées par le front en production.

Un contrat incomplet n'est pas seulement une documentation en retard : c'est
la seule référence dont dispose quiconque intègre l'API sans lire le code —
et, ici, le seul document lisible depuis que le schéma généré est fermé en
production. Il ne peut pas être approximatif.

La comparaison est faite sur les chemins normalisés : ``{id}``,
``{job_id}``, ``{application_id}`` désignent la même chose côté contrat.
"""

import re
from pathlib import Path

import pytest
import yaml

CONTRAT = Path(__file__).resolve().parents[4] / "cv-job-matching" / "openapi.yaml"
METHODES = ("get", "post", "put", "patch", "delete")


def _normalise(route: str) -> str:
    """``PATCH /profile/skills/{skill_id}`` → ``PATCH /profile/skills/{id}``."""
    return re.sub(r"\{[^}]+\}", "{id}", route)


@pytest.fixture
def routes_documentees() -> set[str]:
    spec = yaml.safe_load(CONTRAT.read_text(encoding="utf-8"))
    return {
        _normalise(f"{methode.upper()} {chemin}")
        for chemin, operations in spec["paths"].items()
        for methode in operations
        if methode in METHODES
    }


@pytest.fixture
def routes_servies(client) -> set[str]:
    schema = client.app.openapi()
    return {
        _normalise(f"{methode.upper()} {chemin.replace('/api/v1', '')}")
        for chemin, operations in schema["paths"].items()
        for methode in operations
        if methode in METHODES
    }


class TestLeContratEtLApiCoincident:
    def test_le_perimetre_du_controle_nest_pas_vide(
        self, routes_servies: set[str]
    ) -> None:
        assert len(routes_servies) >= 40, routes_servies

    def test_aucune_route_servie_nest_absente_du_contrat(
        self, routes_servies: set[str], routes_documentees: set[str]
    ) -> None:
        manquantes = routes_servies - routes_documentees
        assert not manquantes, (
            f"{len(manquantes)} route(s) servies et non documentées : "
            f"{sorted(manquantes)}. Le contrat est la seule référence pour qui "
            "intègre l'API sans lire le code — et le schéma généré est fermé "
            "en production."
        )

    def test_aucune_route_documentee_nest_absente_de_lapi(
        self, routes_servies: set[str], routes_documentees: set[str]
    ) -> None:
        """Le sens inverse compte autant : une route promise et jamais servie
        fait écrire du code d'intégration contre du vide."""
        fantomes = routes_documentees - routes_servies
        assert not fantomes, (
            f"{len(fantomes)} route(s) documentées et non servies : "
            f"{sorted(fantomes)}."
        )

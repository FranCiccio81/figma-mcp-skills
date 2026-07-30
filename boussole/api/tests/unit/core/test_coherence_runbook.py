"""Le runbook décrit le système réellement livré.

Défauts trouvés en revue avant déploiement. Aucun n'est un bug de code : ce
sont des écarts entre ce que le code fait et ce que la documentation
d'exploitation en dit. Ils cassent un déploiement aussi sûrement.

1. **``SENTRY_DSN`` renseigné ⇒ aucun processus ne démarre.**
   ``configure_observability`` refuse le démarrage si le DSN est là et le
   paquet absent — parti pris assumé (« se croire observé est pire que ne pas
   l'être »). Mais ``infra/Dockerfile.api`` faisait ``pip install .``, sans
   l'extra ``[observability]``, alors que le runbook marque cette variable
   « Recommandé ». **Suivre la documentation cassait le démarrage** de l'API,
   du worker et du beat — tous trois bâtis sur cette image. Le paquet n'était
   installé nulle part, pas même dans l'environnement de développement.

2. **Le runbook se contredisait sur cette même variable** : §3 « refus de
   démarrage », §3 bis « déclaré, jamais lu par le code — aucun effet ». Qui
   tombait sur la seconde ligne concluait que la variable était sans risque.

3. **Six migrations documentées, sept livrées.** ``0007_efficiency_indexes``
   n'avait pas de ligne. Un opérateur qui compare ``alembic current`` au
   tableau conclut à une migration parasite ou à un échec.

Ces vérifications sont ici, dans la suite qui tourne en CI, et pas dans une
relecture humaine : c'est la dérive silencieuse qu'on cherche à attraper, et
une relecture humaine est précisément ce qui l'a laissée passer.
"""

import re
from pathlib import Path

import pytest

#: tests/unit/core/… → api → boussole → racine du dépôt.
RACINE = Path(__file__).resolve().parents[5]
RUNBOOK = RACINE / "cv-job-matching" / "18-deployment-runbook.md"
DOCKERFILE_API = RACINE / "boussole" / "infra" / "Dockerfile.api"
REVISIONS = RACINE / "boussole" / "api" / "alembic" / "versions"

_NOMBRES = {
    "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
}


@pytest.fixture(scope="module")
def runbook() -> str:
    assert RUNBOOK.exists(), f"runbook introuvable : {RUNBOOK}"
    return RUNBOOK.read_text(encoding="utf-8")


def _revisions() -> list[str]:
    return sorted(p.stem for p in REVISIONS.glob("[0-9][0-9][0-9][0-9]_*.py"))


class TestLimageHonoreCeQueLeRunbookRecommande:
    def test_lextra_dobservabilite_est_installe(self) -> None:
        """Un DSN renseigné ne doit pas empêcher le démarrage.

        Le refus de démarrer est délibéré côté code ; ce qui ne l'était pas,
        c'est que l'image rende ce refus INÉVITABLE dès qu'on suit la
        recommandation du runbook.
        """
        contenu = DOCKERFILE_API.read_text(encoding="utf-8")
        (ligne,) = [texte for texte in contenu.splitlines() if texte.startswith("RUN pip install")]
        assert "observability" in ligne, (
            "l'image n'installe pas sentry-sdk : renseigner SENTRY_DSN — que le "
            "runbook recommande — fait échouer le démarrage de l'API, du worker "
            "et du beat"
        )

    def test_le_worker_et_le_beat_partagent_cette_image(self) -> None:
        """Le correctif ne vaut que si les trois processus viennent de là."""
        compose = (RACINE / "boussole" / "infra" / "docker-compose.dev.yml").read_text(
            encoding="utf-8"
        )
        assert compose.count("Dockerfile.api") >= 1
        for service in ("worker:", "beat:"):
            assert service in compose


class TestLeRunbookNeSeContreditPas:
    def test_sentry_dsn_na_quune_seule_description(self, runbook: str) -> None:
        """Deux lignes de tableau opposées sur la même variable : celle qui
        rassure l'emporte toujours à la lecture."""
        lignes = [
            ligne
            for ligne in runbook.splitlines()
            if ligne.startswith("| `SENTRY_DSN`")
        ]
        assert len(lignes) == 1, f"{len(lignes)} descriptions de SENTRY_DSN : {lignes}"

    def test_elle_annonce_bien_le_refus_de_demarrage(self, runbook: str) -> None:
        (ligne,) = [texte for texte in runbook.splitlines() if texte.startswith("| `SENTRY_DSN`")]
        assert "démarrage" in ligne

    def test_aucune_variable_nest_declaree_inerte(self, runbook: str) -> None:
        """« Déclaré, jamais lu par le code » a servi de mise en garde tant que
        c'était vrai. Une variable réellement inerte doit être RETIRÉE du code,
        pas documentée comme décorative — c'est la règle déjà appliquée à
        ``OTEL_EXPORTER_OTLP_ENDPOINT``."""
        residus = [
            ligne
            for ligne in runbook.splitlines()
            if ligne.startswith("| `") and "jamais lu par le code" in ligne
        ]
        assert residus == [], residus


class TestLeRunbookDecritToutesLesMigrations:
    def test_le_compte_annonce_est_le_bon(self, runbook: str) -> None:
        attendu = len(_revisions())
        motif = re.search(
            r"\*\*?(\w+)\*\*? révisions, chaînées `(\d{4}) → (\d{4})`", runbook
        )
        assert motif, "la phrase de comptage des révisions a disparu du runbook"
        annonce, premiere, derniere = motif.groups()

        assert _NOMBRES[annonce.lower()] == attendu, (
            f"le runbook annonce {annonce} révisions, {attendu} sont livrées"
        )
        assert premiere == _revisions()[0][:4]
        assert derniere == _revisions()[-1][:4], (
            "la dernière révision de la chaîne n'est pas celle qu'un "
            "`alembic current` affichera après `upgrade head`"
        )

    def test_chaque_revision_a_sa_ligne(self, runbook: str) -> None:
        manquantes = [rev for rev in _revisions() if f"| `{rev}`" not in runbook]
        assert manquantes == [], (
            f"révisions livrées mais non documentées : {manquantes} — un "
            "opérateur qui compare `alembic current` au tableau conclut à un "
            "échec de migration"
        )

    def test_aucune_ligne_ne_decrit_une_revision_absente(self, runbook: str) -> None:
        """L'inverse compte autant : une ligne pour une révision supprimée
        enverrait chercher une migration qui n'existe plus."""
        documentees = set(re.findall(r"\| `(\d{4}_\w+)`", runbook))
        assert documentees - set(_revisions()) == set()

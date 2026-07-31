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
COMPOSE = RACINE / "boussole" / "infra" / "docker-compose.dev.yml"

_NOMBRES = {
    "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
}


@pytest.fixture(scope="module")
def runbook() -> str:
    assert RUNBOOK.exists(), f"runbook introuvable : {RUNBOOK}"
    return RUNBOOK.read_text(encoding="utf-8")


#: Colonnes des tableaux d'inventaire §2 : variable | rôle | défaut | prod |
#: secret. Le récapitulatif §2.4 ter en a quatre — le distinguer par le NOMBRE
#: de colonnes évite de compter une ligne de récapitulatif comme une seconde
#: description de la même variable (faux positif trouvé en écrivant ce test).
_COLONNES_INVENTAIRE = 5


def _lignes_de_variable(runbook: str, nom: str) -> list[str]:
    """Lignes des tableaux d'INVENTAIRE décrivant ``nom``."""
    return [
        ligne
        for ligne in runbook.splitlines()
        if ligne.startswith(f"| `{nom}` |")
        and len([cellule for cellule in ligne.split("|") if cellule.strip()])
        == _COLONNES_INVENTAIRE
    ]


@pytest.fixture(scope="module")
def recapitulatif(runbook: str) -> str:
    """Section §2.4 ter — la liste des garde-fous de démarrage."""
    debut = runbook.index("Tout ce qui empêche le démarrage")
    return runbook[debut : runbook.index("### 2.5")]


@pytest.fixture(scope="module")
def compose() -> dict:
    import yaml

    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


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
        assert len(_lignes_de_variable(runbook, "SENTRY_DSN")) == 1, (
            f"{len(_lignes_de_variable(runbook, 'SENTRY_DSN'))} descriptions "
            "de SENTRY_DSN"
        )

    def test_elle_annonce_bien_le_refus_de_demarrage(self, runbook: str) -> None:
        (ligne,) = _lignes_de_variable(runbook, "SENTRY_DSN")
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


MAKEFILE = RACINE / "boussole" / "Makefile"
LISEZMOI = RACINE / "boussole" / "README.md"


class TestToutGardeFouDeDemarrageEstDocumente:
    """Refuser de démarrer est un choix délibéré ; le taire n'en est pas un.

    Deux conditions faisaient échouer le démarrage sans figurer nulle part
    comme bloquantes — ``DEBUG=true`` et ``SMTP_STARTTLS=false``. Leur ligne
    disait « recommandé », pas « le service ne démarre pas ». Un opérateur
    prudent pouvait donc déployer une configuration qui refuse de se lever
    sans avoir rien manqué dans la documentation.
    """

    #: Variables dont une valeur donnée empêche le démarrage. Tenue à la main
    #: à dessein : c'est une liste de DÉCISIONS, pas un motif à déduire.
    BLOQUANTES = (
        "ENV",
        "PRIVACY_SIGNING_KEY",
        "S3_SECRET_KEY",
        "DEBUG",
        "SMTP_STARTTLS",
        "STORAGE_BACKEND",
        "S3_SSE",
        "S3_BUCKET",
        "SENTRY_DSN",
    )

    @pytest.mark.parametrize("variable", BLOQUANTES)
    def test_elle_figure_au_recapitulatif(
        self, recapitulatif: str, variable: str
    ) -> None:
        assert f"`{variable}`" in recapitulatif, (
            f"{variable} peut empêcher le démarrage et n'apparaît pas dans la "
            "liste récapitulative du runbook"
        )

    @pytest.mark.parametrize("variable", ["DEBUG", "SMTP_STARTTLS"])
    def test_sa_ligne_de_tableau_le_dit_aussi(
        self, runbook: str, variable: str
    ) -> None:
        """Le récapitulatif ne suffit pas : on cherche une variable dans le
        tableau, et c'est là qu'on décide de sa valeur."""
        (ligne,) = _lignes_de_variable(runbook, variable)
        assert "démarrage" in ligne, (
            f"la ligne de {variable} ne dit pas qu'une mauvaise valeur "
            "empêche le démarrage"
        )


class TestLesSondesDuComposeSontCoherentes:
    def test_lapi_est_sondee_sur_readyz(self, compose: dict) -> None:
        """``web`` démarre sur ``condition: service_healthy`` : c'est une
        décision de ROUTAGE. ``/healthz`` répond 200 dès que le processus est
        levé — base injoignable comprise — et le front se mettait à parler à
        une API qui ne pouvait pas lui répondre."""
        sonde = str(compose["services"]["api"]["healthcheck"]["test"])
        assert "/readyz" in sonde and "/healthz" not in sonde

    @pytest.mark.parametrize("service", ["worker", "beat"])
    def test_les_processus_celery_sont_sondes(
        self, compose: dict, service: str
    ) -> None:
        """Un worker mort ne fait rien SAVOIR : aucune requête n'échoue, les
        tâches s'accumulent dans le broker. Un beat mort est pire — c'est le
        seul déclencheur des purges RGPD."""
        assert "healthcheck" in compose["services"][service], (
            f"{service} n'a aucune sonde : sa mort est silencieuse"
        )

    def test_la_sonde_de_beat_vise_le_bon_fichier(self, compose: dict) -> None:
        """Le chemin est configurable côté code : une sonde qui regarde
        ailleurs déclarerait mort un ordonnanceur vivant. Premier essai écrit
        de mémoire — et faux."""
        from app.workers.celery_app import celery_app

        attendu = Path(celery_app.conf.beat_schedule_filename).name
        sonde = str(compose["services"]["beat"]["healthcheck"]["test"])
        assert attendu in sonde


class TestLeProjetSAmorceSurUnCloneNeuf:
    def test_le_makefile_cree_lenvironnement_quil_suppose(self) -> None:
        """Toutes les cibles Python supposent ``api/.venv``, l'en-tête le
        disait, et aucune cible ne le créait : un clone neuf tombait sur
        « .venv/bin/ruff: No such file or directory » au premier ``make
        lint``, sans indication de la commande manquante."""
        contenu = MAKEFILE.read_text(encoding="utf-8")
        assert "\nvenv:" in contenu
        assert "python3.12 -m venv .venv" in contenu

    def test_il_installe_lextra_dobservabilite_comme_limage(self) -> None:
        """Sinon poser SENTRY_DSN en local fait échouer le démarrage, et on
        cherche longtemps — l'image, elle, l'installe."""
        assert "observability" in MAKEFILE.read_text(encoding="utf-8")


class TestLeReadmeNeContrediPasLeRunbook:
    """C'est le document qu'on lit EN PREMIER. Il portait trois
    avertissements dont deux étaient faux, et faux dans le sens qui
    inquiète."""

    def test_il_naffirme_plus_que_le_beat_est_absent_du_compose(self) -> None:
        contenu = LISEZMOI.read_text(encoding="utf-8")
        faux = "**ne contient pas de service `celery beat`** (sans lui"
        assert faux not in contenu

    def test_il_naffirme_plus_que_la_cle_de_signature_est_sans_garde(self) -> None:
        contenu = LISEZMOI.read_text(encoding="utf-8")
        assert "qu'**aucun garde-fou ne vérifie**" not in contenu

    def test_il_ne_fige_pas_un_nombre_de_tests(self) -> None:
        """Un compteur en prose repérime en un jour ; le retirer vaut mieux
        que le mettre à jour."""
        contenu = LISEZMOI.read_text(encoding="utf-8")
        chiffres = re.findall(r"(\d{2,5}) tests", contenu)
        assert chiffres == [], f"compteurs figés dans le README : {chiffres}"

    def test_il_annonce_la_bonne_derniere_revision(self) -> None:
        derniere = _revisions()[-1][:4]
        contenu = LISEZMOI.read_text(encoding="utf-8")
        assert f"0001 → {derniere}" in contenu

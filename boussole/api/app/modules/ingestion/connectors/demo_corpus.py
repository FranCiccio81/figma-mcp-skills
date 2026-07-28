"""Connecteur « corpus de démonstration » — offres FICTIVES, hors production.

**Pourquoi ce connecteur existe.** Les trois sources réelles (France Travail,
Greenhouse, Lever) sont écrites, testées, et désactivées en attendant un
arbitrage juridique (Q2/Q3). Sans offres, rien de ce qui fait le produit ne
peut être exercé de bout en bout : ni la recherche, ni le matching, ni — et
c'est le plus coûteux — la **mesure de qualité du matching**, dont les
`evaluation_gates` sont déclaratifs depuis le premier jour. Ce connecteur
lève ce blocage pour la mesure sans rien préjuger du juridique.

**Ce que ces offres sont.** Des inventions. Aucune entreprise citée n'existe,
aucun poste ne correspond à une annonce réelle. Les URL sont sur le TLD
réservé ``.invalid`` (RFC 2606) : elles ne résolvent pas, par construction.
C'est délibéré — une URL plausible mais fausse enverrait un utilisateur
postuler dans le vide, et le principe produit est que toute offre garde une
source et un lien d'origine véritables.

**Refus d'activation hors développement.** :func:`build_demo_connector` lève
dès que ``ENV`` est durci. Un corpus fictif qui arriverait dans un
environnement où un utilisateur peut le voir violerait frontalement
l'interdiction de présenter des données fabriquées comme authentiques —
c'est le genre d'accident qui se produit par une variable d'environnement
oubliée, donc c'est le code qui doit le refuser, pas la procédure.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.modules.ingestion.connectors.base import FetchResult, RawJob, RawLocation

logger = logging.getLogger(__name__)

SLUG = "demo-corpus"

#: Emplacement du corpus, à côté de ``scoring-config.json``.
DEFAULT_CORPUS_PATH = Path(__file__).resolve().parents[4] / "config" / "demo-corpus" / "jobs.json"

#: Les URL du corpus DOIVENT être sur ce TLD réservé (RFC 2606). Vérifié au
#: chargement : une URL plausible qui se glisserait dans le corpus enverrait
#: un utilisateur postuler auprès d'une entreprise qui n'existe pas.
REQUIRED_URL_SUFFIX_HOST = ".invalid"


class DemoCorpusUnavailableError(RuntimeError):
    """Le corpus de démonstration est demandé là où il ne doit pas exister."""


class DemoCorpusConnector:
    """Lit un fichier local et le rend au format des connecteurs réels.

    Aucun réseau. Le cycle est toujours complet et rend le corpus entier :
    la dédup et la réconciliation en aval sont donc exercées exactement
    comme avec une source réelle, ce qui est tout l'intérêt.
    """

    slug = SLUG

    def __init__(self, corpus_path: Path | None = None) -> None:
        self._path = corpus_path or DEFAULT_CORPUS_PATH

    def fetch(self, state: str | None) -> FetchResult:
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        jobs = [_to_raw_job(item) for item in payload["jobs"]]
        version = str(payload.get("corpus_version", "0"))
        logger.info(
            "demo_corpus_fetch offres=%d version=%s ⚠️ OFFRES FICTIVES",
            len(jobs), version,
        )
        # Le curseur porte la version du corpus : le modifier fait un cycle
        # « nouveau », ce qui permet de rejouer une ingestion complète en
        # bumpant un champ du fichier.
        return FetchResult(jobs=jobs, cursor=version, complete=True)


def build_demo_connector(
    settings: Settings | None = None, corpus_path: Path | None = None
) -> DemoCorpusConnector:
    """Construit le connecteur — et refuse hors développement.

    ``is_hardened`` couvre staging autant que production : un staging est
    régulièrement montré à des utilisateurs, et des offres inventées y
    seraient prises pour argent comptant.
    """
    settings = settings or get_settings()
    if settings.is_hardened:
        raise DemoCorpusUnavailableError(
            "Le corpus de démonstration contient des offres FICTIVES et ne peut "
            f"pas être activé en ENV={settings.env}. Les désactiver : "
            "FEATURE_SOURCE_DEMO=false. Ce refus est délibéré — des offres "
            "inventées visibles par un utilisateur seraient présentées comme "
            "authentiques, ce que le produit s'interdit."
        )
    return DemoCorpusConnector(corpus_path=corpus_path)


def _to_raw_job(item: dict[str, Any]) -> RawJob:
    url = str(item["url"])
    _check_url_is_unreachable(url)
    posted_at = datetime.now(UTC) - timedelta(days=int(item.get("posted_days_ago", 3)))
    return RawJob(
        external_ref=str(item["external_ref"]),
        title=str(item["title"]),
        company=str(item["company"]),
        description=str(item["description"]),
        url=url,
        payload=item,
        employer_ref=item.get("employer_ref"),
        locations=[
            RawLocation(
                label=str(loc["label"]),
                lat=loc.get("lat"),
                lon=loc.get("lon"),
                country_code=loc.get("country_code"),
            )
            for loc in item.get("locations", [])
        ],
        posted_at=posted_at,
        contract=item.get("contract"),
        # Confiance 1.0 : ces champs sont structurés dans le fichier, ils ne
        # sont pas devinés d'un libellé. Mentir ici fausserait l'indice de
        # confiance que la mesure doit justement évaluer.
        contract_conf=1.0 if item.get("contract") else None,
        remote=item.get("remote"),
        remote_conf=1.0 if item.get("remote") else None,
        salary_min=item.get("salary_min"),
        salary_max=item.get("salary_max"),
        salary_currency=item.get("salary_currency"),
        salary_period=item.get("salary_period"),
        salary_conf=1.0 if item.get("salary_min") else None,
        experience_min=item.get("experience_min"),
        experience_max=item.get("experience_max"),
        experience_conf=1.0 if item.get("experience_min") is not None else None,
        languages=[(code, level) for code, level in item.get("languages", [])],
        skills=list(item.get("skills_required", [])) + list(item.get("skills_nice", [])),
        language=item.get("language"),
    )


def _check_url_is_unreachable(url: str) -> None:
    """Refuse une URL qui pourrait être prise pour une annonce réelle."""
    host = url.split("//", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    if not host.endswith(REQUIRED_URL_SUFFIX_HOST):
        raise DemoCorpusUnavailableError(
            f"URL {url!r} : le corpus de démonstration n'accepte que des hôtes "
            f"en {REQUIRED_URL_SUFFIX_HOST} (RFC 2606). Une URL résolvable "
            "enverrait un utilisateur postuler auprès d'une entreprise qui "
            "n'existe pas, ou pire, auprès d'une vraie qui ne recrute pas."
        )

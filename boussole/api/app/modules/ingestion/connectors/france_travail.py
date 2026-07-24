"""Connecteur API France Travail — Offres d'emploi (07 §2.1, R6).

Endpoints réels (plateforme francetravail.io) :

- Token OAuth2 client_credentials :
  ``POST https://entreprise.francetravail.fr/connexion/oauth2/access_token``
  (``realm=/partenaire``, scope ``api_offresdemploiv2 o2dsoffre``) ;
- Recherche :
  ``GET https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search``
  — pagination par paramètre ``range=p-d`` (~150 offres/page), fetch
  incrémental par ``minCreationDate``/``maxCreationDate``.

Curseur (``connector_state.cursor``) : ISO-8601 du dernier cycle réussi ;
la requête repart de ``cursor − 15 min`` (chevauchement volontaire,
l'idempotence absorbe les doublons — 07 §4.3).

Activation : ``sources.active`` + flag ``FEATURE_SOURCE_FRANCE_TRAVAIL``
(défaut false — revue juridique Q1 bloquante).
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.modules.ingestion import extract_rules
from app.modules.ingestion.connectors.base import (
    DEFAULT_TIMEOUT,
    FetchResult,
    RawJob,
    RawLocation,
    get_with_retry,
)

logger = logging.getLogger(__name__)

SLUG = "france-travail"
TOKEN_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    "?realm=%2Fpartenaire"
)
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
PAGE_SIZE = 150  # hypothèse de dimensionnement 07 §2.1 🟡
OVERLAP = timedelta(minutes=15)  # chevauchement volontaire 07 §4.3
MAX_PAGES = 20  # garde-fou par cycle 🟡

# Mapping direct typeContrat → contract_type (07 §5.1, confiance 1.0).
CONTRACT_MAP: dict[str, str] = {
    "CDI": "permanent",
    "CDD": "fixed_term",
    "MIS": "other",  # intérim
    "SAI": "other",  # saisonnier
    "LIB": "freelance",  # profession libérale
    "FRA": "freelance",  # franchise
    "STG": "internship",
    "APP": "apprenticeship",
    "PRO": "apprenticeship",  # contrat de professionnalisation
}

# Libellés de langues FT → ISO 639-1 (niveau par défaut B2 🟡 si « exigé »).
_LANG_MAP = {"anglais": "en", "français": "fr", "francais": "fr", "allemand": "de",
             "espagnol": "es", "italien": "it"}


def parse_offer(offer: dict[str, Any]) -> RawJob:
    """Mappe une offre du payload FT vers :class:`RawJob` (07 §5.1)."""
    entreprise = offer.get("entreprise") or {}
    company = entreprise.get("nom") or "Employeur confidentiel"

    lieu = offer.get("lieuTravail") or {}
    locations: list[RawLocation] = []
    if lieu.get("libelle"):
        locations.append(
            RawLocation(
                label=lieu["libelle"],
                lat=lieu.get("latitude"),
                lon=lieu.get("longitude"),
                country_code="FR",  # couverture France entière (07 §2.1)
            )
        )

    contract_code = offer.get("typeContrat")
    contract = CONTRACT_MAP.get(contract_code) if contract_code else None

    # Salaire : libellé semi-structuré parsé par règles (07 §5.1, conf 0.8).
    salary = None
    salaire_libelle = (offer.get("salaire") or {}).get("libelle")
    if salaire_libelle:
        salary = extract_rules.extract_salary(salaire_libelle)

    # Expérience : libellé « 3 ans », « Débutant accepté »… parsé par règles
    # (07 §5.1, conf 0.8) — contexte « expérience » ajouté pour la règle.
    experience = None
    exp_libelle = offer.get("experienceLibelle")
    if exp_libelle:
        experience = extract_rules.extract_experience(f"expérience : {exp_libelle}")

    languages: list[tuple[str, str]] = []
    for lang in offer.get("langues") or []:
        code = _LANG_MAP.get((lang.get("libelle") or "").strip().lower())
        if code:
            languages.append((code, "B2"))  # niveau non précisé par FT → B2 🟡

    skills = [c["libelle"] for c in offer.get("competences") or [] if c.get("libelle")]

    posted_at = None
    if offer.get("dateCreation"):
        posted_at = datetime.fromisoformat(offer["dateCreation"].replace("Z", "+00:00"))

    origine = offer.get("origineOffre") or {}
    url = origine.get("urlOrigine") or f"https://candidat.francetravail.fr/offres/recherche/detail/{offer['id']}"

    return RawJob(
        external_ref=str(offer["id"]),
        # FT n'expose pas de référence employeur exploitable de façon fiable
        # (D13/Q4) : norm_ref vide — l'étage 2 fait le travail inter-sources.
        employer_ref=None,
        title=offer.get("intitule") or "",
        company=company,
        description=offer.get("description") or "",
        url=url,
        payload=offer,
        locations=locations,
        posted_at=posted_at,
        contract=contract,
        contract_conf=1.0 if contract else None,
        salary_min=salary.salary_min if salary else None,
        salary_max=salary.salary_max if salary else None,
        salary_currency=salary.currency if salary else None,
        salary_period=salary.period if salary else None,
        salary_conf=salary.confidence if salary else None,
        experience_min=experience.minimum if experience else None,
        experience_max=experience.maximum if experience else None,
        experience_conf=experience.confidence if experience else None,
        languages=languages,
        skills=skills,
        language="fr",  # source FR — détection §5.4 confirmée en aval
    )


class FranceTravailConnector:
    """Connecteur France Travail (kind=public_api, OAuth2, incrémental)."""

    slug = SLUG

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http_client or httpx.Client(timeout=DEFAULT_TIMEOUT)

    def _token(self) -> str:
        """Jeton OAuth2 client_credentials (scope offres v2)."""
        response = self._http.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def fetch(self, state: str | None) -> FetchResult:
        """Fetch incrémental depuis ``state − 15 min`` (07 §4.3), paginé.

        Fetch TRONQUÉ (``MAX_PAGES`` atteint) → ``complete=False`` : le
        périmètre observé n'étant pas exhaustif, l'appelant ne doit ni
        avancer le curseur ni compter les absences (mécanisme 2) ce cycle.
        Un item malformé est compté en erreur, le cycle continue (07 §4.5).
        """
        now = datetime.now(UTC)
        headers = {"Authorization": f"Bearer {self._token()}"}
        params: dict[str, Any] = {"sort": "1"}
        if state:
            since = datetime.fromisoformat(state) - OVERLAP
            params["minCreationDate"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["maxCreationDate"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        jobs: list[RawJob] = []
        parse_errors = 0
        complete = True
        for page in range(MAX_PAGES):
            start = page * PAGE_SIZE
            params["range"] = f"{start}-{start + PAGE_SIZE - 1}"
            response = get_with_retry(
                self._http, SEARCH_URL, params=params, headers=headers
            )
            if response.status_code == 204:  # plus de résultats
                break
            payload = response.json()
            offers = payload.get("resultats") or []
            for offer in offers:
                try:
                    jobs.append(parse_offer(offer))
                except Exception:
                    parse_errors += 1
                    logger.exception(
                        "france_travail_offer_parse_error id=%r",
                        offer.get("id") if isinstance(offer, dict) else None,
                    )
            if len(offers) < PAGE_SIZE:
                break
        else:
            complete = False  # tronqué : périmètre non exhaustif ce cycle
            logger.warning("france_travail_max_pages_reached pages=%d", MAX_PAGES)

        # Le curseur n'avance qu'après un cycle complet réussi (07 §4.3) :
        # toute exception au-dessus empêche d'atteindre cette ligne, et un
        # cycle tronqué est signalé via ``complete=False``.
        return FetchResult(
            jobs=jobs, cursor=now.isoformat(), complete=complete, parse_errors=parse_errors
        )

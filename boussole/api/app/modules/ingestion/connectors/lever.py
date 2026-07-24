"""Connecteur Lever Postings API (07 §2.3, kind=ats_feed).

Endpoint réel, par site activé explicitement (jamais de découverte
automatique — D04) :

    GET https://api.lever.co/v0/postings/{site}?mode=json

Fetch complet par cycle (≤ 1 req/s), curseur inutilisé. Champs :
``id`` (external_ref), ``text`` (titre), ``descriptionPlain``,
``categories`` (location, commitment ≈ contrat), ``workplaceType``
(structuré, fiable → conf 1.0), ``hostedUrl``, ``createdAt`` (epoch ms),
parfois ``salaryRange`` structuré (conf 1.0).

Activation : flag ``FEATURE_SOURCE_LEVER`` (défaut false — Q2).
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.modules.ingestion.connectors.base import (
    DEFAULT_TIMEOUT,
    FetchResult,
    RawJob,
    RawLocation,
    get_with_retry,
)
from app.modules.ingestion.normalize import strip_html

logger = logging.getLogger(__name__)

SLUG = "lever"
BASE_URL = "https://api.lever.co/v0/postings/{site}"

# categories.commitment → contract_type, par dictionnaire (07 §5.1, conf 0.9).
COMMITMENT_MAP: dict[str, str] = {
    "full-time": "permanent",
    "full time": "permanent",
    "part-time": "other",
    "part time": "other",
    "contract": "fixed_term",
    "fixed-term": "fixed_term",
    "temporary": "fixed_term",
    "intern": "internship",
    "internship": "internship",
    "apprenticeship": "apprenticeship",
    "freelance": "freelance",
}
COMMITMENT_CONFIDENCE = 0.9

# workplaceType → remote_policy, mapping direct (07 §5.1, conf 1.0).
WORKPLACE_MAP: dict[str, str] = {
    "remote": "full_remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "unspecified": "",
}

# salaryRange.interval → salary_period.
_INTERVAL_MAP = {"year": "year", "month": "month", "day": "day", "hour": "hour"}


def _map_interval(interval: str | None) -> str | None:
    if not interval:
        return None
    lowered = interval.lower()
    return next((p for key, p in _INTERVAL_MAP.items() if key in lowered), None)


def parse_posting(posting: dict[str, Any], company_name: str) -> RawJob:
    """Mappe une offre du payload Lever vers :class:`RawJob`."""
    categories = posting.get("categories") or {}

    commitment = (categories.get("commitment") or "").strip().lower()
    contract = COMMITMENT_MAP.get(commitment)

    workplace = (posting.get("workplaceType") or "").strip().lower()
    remote = WORKPLACE_MAP.get(workplace) or None

    salary_range = posting.get("salaryRange") or {}
    salary_min = salary_range.get("min")
    salary_max = salary_range.get("max")

    posted_at = None
    if posting.get("createdAt"):
        posted_at = datetime.fromtimestamp(posting["createdAt"] / 1000, tz=UTC)

    location_label = categories.get("location")
    locations = [RawLocation(label=location_label)] if location_label else []

    description = posting.get("descriptionPlain") or strip_html(posting.get("description") or "")

    return RawJob(
        external_ref=str(posting["id"]),
        employer_ref=None,  # Lever n'expose pas de référence employeur (D13)
        title=posting.get("text") or "",
        company=company_name,  # nom du site (config, conf 1.0)
        description=description,
        url=posting["hostedUrl"],
        payload=posting,
        locations=locations,
        posted_at=posted_at,
        contract=contract,
        contract_conf=COMMITMENT_CONFIDENCE if contract else None,
        remote=remote,
        remote_conf=1.0 if remote else None,
        salary_min=int(salary_min) if salary_min is not None else None,
        salary_max=int(salary_max) if salary_max is not None else None,
        salary_currency=salary_range.get("currency"),
        salary_period=_map_interval(salary_range.get("interval")),
        salary_conf=1.0 if salary_min is not None or salary_max is not None else None,
    )


class LeverConnector:
    """Fetch complet des sites activés (``[(site, entreprise)]``)."""

    slug = SLUG

    def __init__(
        self,
        sites: list[tuple[str, str]],
        http_client: httpx.Client | None = None,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self._sites = sites
        self._http = http_client or httpx.Client(timeout=DEFAULT_TIMEOUT)
        self._min_interval = min_interval_seconds

    def fetch(self, state: str | None) -> FetchResult:
        """Un GET par site, ≤ 1 req/s ; échec d'un site → cycle continue.

        Un site en échec est signalé dans ``failed_scopes`` (exclusion du
        périmètre ``mark_expired`` du cycle) ; une offre malformée est
        comptée en erreur sans tuer le parsing du site (07 §4.5).
        """
        jobs: list[RawJob] = []
        failed_scopes: list[str] = []
        parse_errors = 0
        for index, (site, company_name) in enumerate(self._sites):
            if index > 0:
                time.sleep(self._min_interval)
            url = BASE_URL.format(site=site)
            try:
                response = get_with_retry(self._http, url, params={"mode": "json"})
            except httpx.HTTPError:
                failed_scopes.append(site)
                logger.exception("lever_site_failed site=%s", site)
                continue
            payload = response.json()
            for posting in payload:
                try:
                    jobs.append(parse_posting(posting, company_name))
                except Exception:
                    parse_errors += 1
                    logger.exception(
                        "lever_posting_parse_error site=%s id=%r",
                        site, posting.get("id") if isinstance(posting, dict) else None,
                    )
        # Pas de curseur : fetch complet par cycle.
        return FetchResult(jobs=jobs, failed_scopes=failed_scopes, parse_errors=parse_errors)

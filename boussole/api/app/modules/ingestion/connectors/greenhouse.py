"""Connecteur Greenhouse Job Board API (07 §2.2, kind=ats_feed).

Endpoint réel, par board activé explicitement (jamais de découverte
automatique — D04) :

    GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

Pas d'incrémental côté API : fetch complet par board et par cycle
(≤ 1 req/s par board — politesse 07 §2.2), diff local par ``updated_at`` +
hash du payload en aval (07 §4.3). Le curseur est inutilisé (``None``).

Champs : ``id`` (external_ref), ``requisition_id`` (référence EMPLOYEUR →
clé de dédup D13 si exposée), ``title``, ``content`` (HTML → texte,
étage 0), ``location.name``, ``absolute_url``, ``updated_at``. Pas de
salaire/contrat structurés → étages 1/2 (07 §5.1).

Activation : flag ``FEATURE_SOURCE_GREENHOUSE`` (défaut false — Q2).
"""

import logging
import time
from datetime import datetime
from typing import Any

import httpx

from app.modules.ingestion.connectors.base import (
    DEFAULT_TIMEOUT,
    RawJob,
    RawLocation,
    get_with_retry,
)
from app.modules.ingestion.normalize import strip_html

logger = logging.getLogger(__name__)

SLUG = "greenhouse"
BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def parse_job(job: dict[str, Any], company_name: str) -> RawJob:
    """Mappe une offre du payload Greenhouse vers :class:`RawJob`."""
    posted_at = None
    for date_field in ("first_published", "updated_at"):
        if job.get(date_field):
            posted_at = datetime.fromisoformat(job[date_field])
            break

    location_name = (job.get("location") or {}).get("name")
    locations = [RawLocation(label=location_name)] if location_name else []

    requisition = job.get("requisition_id")

    return RawJob(
        external_ref=str(job["id"]),
        employer_ref=str(requisition) if requisition else None,  # réf. employeur (D13)
        title=job.get("title") or "",
        company=company_name,  # nom du board (config connector_boards, conf 1.0)
        description=strip_html(job.get("content") or ""),  # étage 0 (07 §5.2)
        url=job["absolute_url"],
        payload=job,
        locations=locations,
        posted_at=posted_at,
    )


class GreenhouseConnector:
    """Fetch complet des boards activés (``[(board_token, entreprise)]``)."""

    slug = SLUG

    def __init__(
        self,
        boards: list[tuple[str, str]],
        http_client: httpx.Client | None = None,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self._boards = boards
        self._http = http_client or httpx.Client(timeout=DEFAULT_TIMEOUT)
        self._min_interval = min_interval_seconds

    def fetch(self, state: str | None) -> tuple[list[RawJob], str | None]:
        """Un GET par board, ≤ 1 req/s ; l'échec d'un board n'arrête pas
        les autres (item en erreur, cycle continue — 07 §4.5)."""
        jobs: list[RawJob] = []
        for index, (board_token, company_name) in enumerate(self._boards):
            if index > 0:
                time.sleep(self._min_interval)
            url = BASE_URL.format(board=board_token)
            try:
                response = get_with_retry(self._http, url, params={"content": "true"})
            except httpx.HTTPError:
                logger.exception("greenhouse_board_failed board=%s", board_token)
                continue
            payload = response.json()
            jobs.extend(parse_job(job, company_name) for job in payload.get("jobs", []))
        return jobs, None  # pas de curseur : fetch complet par cycle

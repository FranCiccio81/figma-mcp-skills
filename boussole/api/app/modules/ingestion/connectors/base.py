"""Contrat commun des connecteurs (07 §4) : ``Connector`` + ``RawJob``.

Un connecteur = une source homologuée (D04). ``fetch(state)`` retourne les
offres brutes mappées en :class:`RawJob` et le nouveau curseur (le curseur
n'avance qu'après un cycle complet réussi — 07 §4.3). Les connecteurs ne
font AUCUNE écriture en base : l'orchestration est dans ``service.py``.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0


@dataclass(slots=True)
class RawLocation:
    """Lieu tel que fourni par la source (géocodage en aval, 07 §5.3)."""

    label: str
    lat: float | None = None
    lon: float | None = None
    country_code: str | None = None


@dataclass(slots=True)
class RawJob:
    """Offre brute mappée depuis le payload d'une source (07 §5.1).

    Les champs structurés (``contract``, ``remote``, ``salary_*``…) ne sont
    renseignés QUE s'ils sont fournis par la source, avec la confiance du
    mapping (1.0 pour un champ structuré, 0.8–0.9 pour un libellé parsé par
    règle). Les champs absents restent ``None`` → étages 1/2 en aval.
    ``payload`` conserve le JSON brut (archivage S3, rejouabilité).
    """

    external_ref: str
    title: str
    company: str
    description: str
    url: str
    payload: dict[str, Any]
    employer_ref: str | None = None  # référence EMPLOYEUR (clé dédup D13), sinon None
    locations: list[RawLocation] = field(default_factory=list)
    posted_at: datetime | None = None
    contract: str | None = None
    contract_conf: float | None = None
    remote: str | None = None
    remote_conf: float | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_conf: float | None = None
    experience_min: float | None = None
    experience_max: float | None = None
    experience_conf: float | None = None
    languages: list[tuple[str, str]] = field(default_factory=list)  # (code, CECRL), conf 1.0
    skills: list[str] = field(default_factory=list)  # libellés EXIGÉS fournis (ex. ROME)
    #: Compétences SOUHAITÉES quand la source les distingue. Sans ce champ,
    #: tout ce qu'une source publie atterrit en « indispensable » et la
    #: dimension ``skills_nice`` (10 % du poids) reste morte pour toute source
    #: à règles — seule l'extraction LLM savait faire la différence.
    skills_nice: list[str] = field(default_factory=list)
    #: Code secteur du référentiel ``sectors`` quand la source le publie.
    #: Sans lui, la dimension ``sector`` (4 %) est inconnue par construction.
    sector: str | None = None
    language: str | None = None  # langue de rédaction si fournie
    expires_at: datetime | None = None  # signal explicite d'expiration (07 §4.6.1)
    withdrawn: bool = False  # signal « annulée/pourvue » (07 §4.6.1)


@dataclass(slots=True)
class FetchResult:
    """Résultat d'un cycle de fetch d'un connecteur (07 §4.3, §4.5).

    - ``complete`` : ``False`` si le fetch est TRONQUÉ (garde-fou
      ``MAX_PAGES`` atteint…) — le périmètre observé n'est pas exhaustif,
      l'expiration par absence (mécanisme 2) doit être sautée ce cycle et
      le curseur ne doit pas avancer ;
    - ``failed_scopes`` : périmètres (board Greenhouse, site Lever) dont le
      fetch a ÉCHOUÉ — leurs job_sources doivent être exclues du périmètre
      ``mark_expired`` du cycle (ni absence, ni remise à zéro) ;
    - ``parse_errors`` : items malformés ignorés (07 §4.5, classe
      « permanente requête » — le cycle continue).
    """

    jobs: list[RawJob]
    cursor: str | None = None
    complete: bool = True
    failed_scopes: list[str] = field(default_factory=list)
    parse_errors: int = 0


class Connector(Protocol):
    """Protocole des connecteurs — implémentations dans ce package."""

    slug: str

    def fetch(self, state: str | None) -> FetchResult:
        """Récupère un cycle d'offres.

        ``state`` : curseur persisté (``connector_state.cursor``) ou ``None``
        au premier cycle. Retourne un :class:`FetchResult` (offres, nouveau
        curseur, complétude du cycle, périmètres en échec).
        """
        ...


def parse_retry_after(value: str) -> float | None:
    """``Retry-After`` : delta en secondes OU date HTTP (RFC 9110 §10.2.3).

    Retourne ``None`` si la valeur est illisible — l'appelant retombe sur
    son backoff exponentiel (jamais de ``ValueError``).
    """
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return max(0.0, (dt - datetime.now(UTC)).total_seconds())


def get_with_retry(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 3,
    backoff_seconds: float = 1.0,
) -> httpx.Response:
    """GET avec retry simple sur erreurs transitoires (429/5xx/réseau).

    Backoff exponentiel court côté connecteur ; le backoff long
    (« min(2^n × 30 s, 30 min) », 07 §4.5) est porté par les retries Celery
    au niveau du cycle. ``Retry-After`` est respecté s'il est fourni.
    """
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.get(url, params=params, headers=headers)
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After")
                delay = parse_retry_after(retry_after) if retry_after else None
                if delay is None:
                    delay = backoff_seconds * (2**attempt)
                logger.warning(
                    "transient_http_error url=%s status=%s attempt=%d",
                    url, response.status_code, attempt + 1,
                )
                time.sleep(min(delay, 30.0))
                continue
            response.raise_for_status()
            return response
        except httpx.TransportError as exc:  # réseau/timeout
            last_error = exc
            logger.warning("transport_error url=%s attempt=%d", url, attempt + 1)
            time.sleep(backoff_seconds * (2**attempt))
    if last_error is not None:
        raise last_error
    raise httpx.HTTPStatusError(
        f"transient errors exhausted for {url}",
        request=httpx.Request("GET", url),
        response=response,
    )

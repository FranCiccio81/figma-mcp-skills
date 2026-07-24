"""Géocodage des libellés de lieux (07 §5.3).

- :class:`StaticGeocoder` : dictionnaire d'~30 villes françaises pour les
  tests et le développement (aucun réseau) ;
- :class:`NominatimGeocoder` : géocodeur OSM auto-hébergeable 🟡
  (obligations d'attribution ODbL à confirmer par revue juridique — Q3),
  httpx + cache Redis volatile (TTL 12 mois) + politesse 1 req/s.

Libellés non résolus (« Remote — EMEA »…) → ``None`` : le moteur traite la
localisation comme inconnue (06 §2 dim. 7).
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Protocol

import httpx
from redis import Redis

from app.modules.ingestion.normalize import norm

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 365 * 24 * 3600  # 12 mois (07 §5.3)


@dataclass(frozen=True)
class GeoPoint:
    """Résultat de géocodage : coordonnées + pays + libellé canonique."""

    lat: float
    lon: float
    country_code: str  # ISO 3166-1 alpha-2, majuscules
    label: str  # libellé canonique de la ville (pour norm_location)


class Geocoder(Protocol):
    """Interface de géocodage — implémentations substituables en tests."""

    def geocode(self, label: str) -> GeoPoint | None:
        """Résout un libellé libre en :class:`GeoPoint`, ou ``None``."""
        ...


# ~30 villes françaises principales — dev/tests uniquement.
_STATIC_CITIES: dict[str, tuple[float, float]] = {
    "paris": (48.8566, 2.3522),
    "marseille": (43.2965, 5.3698),
    "lyon": (45.7640, 4.8357),
    "toulouse": (43.6047, 1.4442),
    "nice": (43.7102, 7.2620),
    "nantes": (47.2184, -1.5536),
    "montpellier": (43.6108, 3.8767),
    "strasbourg": (48.5734, 7.7521),
    "bordeaux": (44.8378, -0.5792),
    "lille": (50.6292, 3.0573),
    "rennes": (48.1173, -1.6778),
    "reims": (49.2583, 4.0317),
    "toulon": (43.1242, 5.9280),
    "saint etienne": (45.4397, 4.3872),
    "le havre": (49.4944, 0.1079),
    "grenoble": (45.1885, 5.7245),
    "dijon": (47.3220, 5.0415),
    "angers": (47.4784, -0.5632),
    "nimes": (43.8367, 4.3601),
    "villeurbanne": (45.7719, 4.8902),
    "clermont ferrand": (45.7772, 3.0870),
    "aix en provence": (43.5297, 5.4474),
    "brest": (48.3904, -4.4861),
    "tours": (47.3941, 0.6848),
    "amiens": (49.8942, 2.2957),
    "limoges": (45.8336, 1.2611),
    "annecy": (45.8992, 6.1294),
    "metz": (49.1193, 6.1757),
    "besancon": (47.2378, 6.0241),
    "orleans": (47.9029, 1.9093),
    "rouen": (49.4432, 1.0999),
    "nancy": (48.6921, 6.1844),
}


class StaticGeocoder:
    """Géocodeur statique FR pour tests/dev — aucun appel réseau."""

    def geocode(self, label: str) -> GeoPoint | None:
        normed = norm(label)
        # Essais successifs : libellé complet, puis chaque token composé
        # (gère « 75 - Paris », « Paris, France », « Lyon (69) »…).
        candidates = [normed]
        tokens = normed.split()
        candidates.extend(" ".join(tokens[i:j]) for i in range(len(tokens))
                          for j in range(i + 1, min(i + 4, len(tokens)) + 1))
        for candidate in candidates:
            hit = _STATIC_CITIES.get(candidate)
            if hit is not None:
                return GeoPoint(lat=hit[0], lon=hit[1], country_code="FR", label=candidate)
        return None


class NominatimGeocoder:
    """Géocodeur Nominatim/Photon (OSM) 🟡 — httpx, cache Redis, 1 req/s.

    ``redis_client`` : instance Redis VOLATILE (D17) ou ``None`` (pas de
    cache — dev). Politesse : au plus une requête par seconde, imposée par
    horloge monotone (07 §5.3, usage policy OSM).
    """

    def __init__(
        self,
        base_url: str = "https://nominatim.openstreetmap.org",
        redis_client: Redis | None = None,
        http_client: httpx.Client | None = None,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._redis = redis_client
        self._http = http_client or httpx.Client(
            timeout=10.0, headers={"User-Agent": "boussole-ingestion/0.1"}
        )
        self._min_interval = min_interval_seconds
        self._last_call = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def geocode(self, label: str) -> GeoPoint | None:
        cache_key = f"geocode:{norm(label)}"
        if self._redis is not None:
            cached = self._redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return GeoPoint(**data) if data else None

        self._throttle()
        try:
            response = self._http.get(
                f"{self._base_url}/search",
                params={"q": label, "format": "jsonv2", "limit": 1, "addressdetails": 1},
            )
            response.raise_for_status()
            results = response.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("geocode_failed label=%r", label)
            return None

        point: GeoPoint | None = None
        if results:
            first = results[0]
            country = (first.get("address") or {}).get("country_code", "")
            point = GeoPoint(
                lat=float(first["lat"]),
                lon=float(first["lon"]),
                country_code=country.upper(),
                label=first.get("name") or label,
            )
        if self._redis is not None:
            payload = json.dumps(point.__dict__ if point else None)
            self._redis.setex(cache_key, _CACHE_TTL_SECONDS, payload)
        return point

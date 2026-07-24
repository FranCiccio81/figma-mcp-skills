"""Primitives géométriques pures : cosinus et distance haversine."""

from __future__ import annotations

import math
from collections.abc import Sequence

__all__ = ["EARTH_RADIUS_KM", "cosine_similarity", "haversine_km"]

EARTH_RADIUS_KM = 6371.0


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosinus entre deux vecteurs de même dimension (0,0 si norme nulle)."""
    if len(a) != len(b):
        raise ValueError(f"dimensions d'embeddings incompatibles : {len(a)} vs {len(b)}")
    if not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance grand-cercle en km entre deux points (lat/lon en degrés)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

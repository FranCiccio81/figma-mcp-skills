"""Routes du module jobs — stub M1.

Module jobs : recherche et consultation des offres (E6, D07).
Implémentation prévue au jalon M2 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", status_code=501, summary="Recherche d'offres (E6) — prévu M2+")
async def not_implemented_stub() -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M2)."""
    raise not_implemented_problem("jobs", "M2")

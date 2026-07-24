"""Routes du module matching — stub M1.

Module matching : scoring déterministe 12 dimensions (E7, D02/D03).
Implémentation prévue au jalon M3 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/matches", tags=["matching"])


@router.get("", status_code=501, summary="Offres classées par score (E7) — prévu M3+")
async def not_implemented_stub() -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M3)."""
    raise not_implemented_problem("matching", "M3")

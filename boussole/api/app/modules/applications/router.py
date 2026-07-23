"""Routes du module applications — stub M1.

Module applications : suivi des candidatures (E11).
Implémentation prévue au jalon M4 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", status_code=501, summary="Suivi des candidatures (E11) — prévu M4+")
async def not_implemented_stub() -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M4)."""
    raise not_implemented_problem("applications", "M4")

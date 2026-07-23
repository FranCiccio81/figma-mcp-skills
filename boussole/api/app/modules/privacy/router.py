"""Routes du module privacy — stub M1.

Module privacy : export RGPD et suppression de compte (E12, D21).
Implémentation prévue au jalon M5 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.post("/export", status_code=501, summary="Export RGPD (E12) — prévu M5")
async def not_implemented_stub() -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M5)."""
    raise not_implemented_problem("privacy", "M5")

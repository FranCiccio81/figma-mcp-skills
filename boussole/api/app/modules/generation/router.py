"""Routes du module generation — stub M1.

Module generation : contenus ancrés au profil validé (E10, D10).
Implémentation prévue au jalon M4 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/generations", tags=["generation"])


@router.get("", status_code=501, summary="Bibliothèque des contenus générés (E10) — prévu M4+")
async def not_implemented_stub() -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M4)."""
    raise not_implemented_problem("generation", "M4")

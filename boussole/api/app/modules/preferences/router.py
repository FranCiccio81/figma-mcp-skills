"""Routes du module preferences — stub M1.

Module preferences : critères de recherche de l'utilisateur (E4).
Implémentation prévue au jalon M2 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", status_code=501, summary="Préférences de recherche (E4) — prévu M2+")
async def not_implemented_stub() -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M2)."""
    raise not_implemented_problem("preferences", "M2")

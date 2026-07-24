"""Routes du module profiles — stub M1.

Module profiles : profil canonique versionné avec provenance (E3, D05).
Implémentation prévue au jalon M2 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/profile", tags=["profiles"])


@router.get("", status_code=501, summary="Profil canonique (E3) — prévu M2+")
async def not_implemented_stub() -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M2)."""
    raise not_implemented_problem("profiles", "M2")

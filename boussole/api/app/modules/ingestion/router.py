"""Routes du module ingestion — stub M1.

Module ingestion : connecteurs de sources et normalisation (E5, D04).
Implémentation prévue au jalon M2 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/sources", tags=["ingestion"])


@router.get("", status_code=501, summary="Registre des sources (E5) — prévu M2+")
async def not_implemented_stub() -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M2)."""
    raise not_implemented_problem("ingestion", "M2")

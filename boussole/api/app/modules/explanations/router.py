"""Routes du module explanations — stub M1.

Module explanations : explication en deux couches (E8, D14).
Implémentation prévue au jalon M3 ; en attendant, la route racine
répond 501 (problem+json) — aucun TODO silencieux.
"""

from fastapi import APIRouter

from app.core.problems import not_implemented_problem

router = APIRouter(prefix="/jobs", tags=["explanations"])


@router.post("/{job_id}/explanation", status_code=501, summary="Explication d'un match (E8) — prévu M3+")
async def not_implemented_stub(job_id: str) -> None:
    """Stub M1 — voir 15-delivery-roadmap.md (jalon M3)."""
    raise not_implemented_problem("explanations", "M3")

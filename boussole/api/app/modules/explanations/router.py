"""Routes du module explanations (E8, D14) : POST /jobs/{id}/explanation.

Session valide requise (401 sinon) ; méthode mutante → middleware CSRF
global. La reformulation LLM part EXCLUSIVEMENT des ``explanation_facts`` du
match_result (D14) et est mise en cache par (profil, offre, scoring_version,
prompt_version).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.providers.base import LLMProvider
from app.ai.providers.fake import FakeProvider
from app.modules.auth.models import User
from app.modules.auth.router import require_current_user
from app.modules.explanations.repository import (
    ExplanationsRepository,
    get_explanations_repository,
)
from app.modules.explanations.schemas import MatchExplanationOut
from app.modules.explanations.service import FAKE_EXPLANATION, ExplanationsService
from app.modules.matching.router import get_matching_service
from app.modules.matching.service import MatchingService

router = APIRouter(prefix="/jobs", tags=["explanations"])


def get_llm_provider() -> LLMProvider:
    """Provider LLM — :class:`FakeProvider` déterministe au M3 🟡 (D08, D22).

    La sortie canned ne contient aucun chiffre : elle passe le contrôle
    numérique quels que soient les facts. Provider réel branché en M4.
    """
    return FakeProvider(canned={"match_explanation": dict(FAKE_EXPLANATION)})


def get_explanations_service(
    matching: MatchingService = Depends(get_matching_service),
    repository: ExplanationsRepository = Depends(get_explanations_repository),
    provider: LLMProvider = Depends(get_llm_provider),
) -> ExplanationsService:
    return ExplanationsService(matching, repository, provider)


CurrentUser = Annotated[User, Depends(require_current_user)]
Service = Annotated[ExplanationsService, Depends(get_explanations_service)]


@router.post(
    "/{job_id}/explanation",
    response_model=MatchExplanationOut,
    summary="Reformulation LLM des faits d'explication (E8, D14) — mise en cache",
)
async def create_explanation(
    job_id: uuid.UUID, user: CurrentUser, service: Service
) -> MatchExplanationOut:
    """Entrée du LLM = uniquement les facts du moteur (jamais l'offre brute) ;
    sortie validée contre ``match_explanation`` + diff numérique (06 §6) —
    502 ``explanation_generation_failed`` en cas de divergence 🟡 ; 409
    ``profile_not_validated`` si le profil n'est pas validé."""
    return await service.explain(user.id, job_id)

"""Routes du module explanations (E8, D14) : POST /jobs/{id}/explanation.

Session valide requise (401 sinon) ; méthode mutante → middleware CSRF
global. La reformulation LLM part EXCLUSIVEMENT des ``explanation_facts`` du
match_result (D14) et est mise en cache par (profil, offre, scoring_version,
prompt_version).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.providers.base import LLMProvider, ProviderUnavailableError
from app.ai.providers.factory import get_llm_provider as provider_factory
from app.ai.providers.fake import FakeProvider
from app.core.config import get_settings
from app.core.problems import Problem
from app.modules.auth.models import User
from app.modules.auth.router import require_current_user
from app.modules.explanations.repository import (
    ExplanationsRepository,
    get_explanations_repository,
)
from app.modules.explanations.schemas import MatchExplanationOut
from app.modules.explanations.service import FAKE_EXPLANATION, TASK, ExplanationsService
from app.modules.matching.router import get_matching_service
from app.modules.matching.service import MatchingService

router = APIRouter(prefix="/jobs", tags=["explanations"])


def get_llm_provider() -> LLMProvider:
    """Provider LLM — sélectionné par configuration (D08).

    ``AI_PROVIDER=fake`` (défaut) : sortie canned sans aucun chiffre, qui
    passe donc le contrôle numérique quels que soient les facts. Sinon la
    fabrique (primaire + fallback + breaker) ; activation d'un provider réel
    conditionnée à Q4/Q38.
    """
    # La sortie canned est indexée sur le nom de TÂCHE (``explain_match``),
    # celui que le service passe à ``complete_json`` — pas sur le nom du
    # schéma de sortie (``match_explanation``), qui n'a jamais été un nom de
    # tâche valide (M6).
    if get_settings().ai_provider == "fake":
        return FakeProvider(canned={TASK: dict(FAKE_EXPLANATION)})
    try:
        return provider_factory(TASK)
    except ProviderUnavailableError as exc:
        # La fabrique ne retombe plus sur le factice (C3) : la fonction est
        # SUSPENDUE avec un message explicite (D18), jamais servie avec une
        # explication vide qui passerait pour un résultat. Le reste de
        # l'application (recherche, scores, facts déterministes) fonctionne.
        raise Problem(
            status=503,
            code="ai_provider_unavailable",
            title="Explication temporairement indisponible",
            detail=(
                "Le service de reformulation est momentanément indisponible. "
                "Le score et les critères détaillés restent accessibles."
            ),
        ) from exc


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

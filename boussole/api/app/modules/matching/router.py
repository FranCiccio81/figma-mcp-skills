"""Routes du module matching (E7, D02/D03) : /jobs/{id}/match et /matches.

Toutes les routes exigent une session valide (cookie ``boussole_session``) —
401 problem+json sinon. Le routeur n'a pas de préfixe : il porte à la fois
``GET /jobs/{id}/match`` (calcul synchrone + cache) et ``GET /matches``
(calcul paresseux M3, tri score décroissant, curseur keyset).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.auth.models import User
from app.modules.auth.router import require_current_user
from app.modules.jobs.schemas import SearchPage
from app.modules.matching.repository import MatchingRepository, get_matching_repository
from app.modules.matching.schemas import MatchResultOut
from app.modules.matching.service import MatchEngine, MatchingService, compute_match
from app.modules.preferences.repository import (
    PreferencesRepository,
    get_preferences_repository,
)
from app.modules.profiles.repository import ProfilesRepository, get_profiles_repository

router = APIRouter(tags=["matching"])


def get_match_engine() -> MatchEngine:
    """Moteur de matching — surchargé par les tests (compteur d'appels)."""
    return compute_match


def get_matching_service(
    profiles: ProfilesRepository = Depends(get_profiles_repository),
    preferences: PreferencesRepository = Depends(get_preferences_repository),
    repository: MatchingRepository = Depends(get_matching_repository),
    engine: MatchEngine = Depends(get_match_engine),
) -> MatchingService:
    return MatchingService(profiles, preferences, repository, engine)


CurrentUser = Annotated[User, Depends(require_current_user)]
Service = Annotated[MatchingService, Depends(get_matching_service)]


@router.get(
    "/jobs/{job_id}/match",
    response_model=MatchResultOut,
    summary="Résultat de matching pour le profil courant (E7)",
)
async def get_job_match(
    job_id: uuid.UUID, user: CurrentUser, service: Service
) -> MatchResultOut:
    """Calcul synchrone via le moteur pur (cible < 50 ms, aucun réseau) avec
    cache ``match_results`` ; 409 ``profile_not_validated`` si le profil n'est
    pas validé, 404 si l'offre est inconnue ou retirée."""
    return await service.get_match(user.id, job_id)


@router.get(
    "/matches",
    response_model=SearchPage,
    summary="Offres classées par score pour le profil courant (E7)",
)
async def list_matches(
    user: CurrentUser,
    service: Service,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    include_blocked: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> SearchPage:
    """Liste triée par score décroissant (JobCard avec ``match`` rempli).

    M3 : calcul paresseux plafonné aux 200 offres actives les plus récentes du
    pré-filtre (contrat accepté) 🟡 — le re-scoring asynchrone complet arrive
    avec les embeddings (M4). ``include_blocked=false`` retire les offres avec
    critère rédhibitoire (par défaut elles restent listées, badgées).
    """
    return await service.list_matches(
        user.id,
        min_score=min_score,
        include_blocked=include_blocked,
        limit=limit,
        cursor=cursor,
    )

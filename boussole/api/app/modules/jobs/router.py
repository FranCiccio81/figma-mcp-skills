"""Routes du module jobs (E6, D07) : /jobs, /jobs/{id}, saved-state, /sources.

Toutes les routes exigent une session valide (cookie ``boussole_session``) —
401 problem+json sinon. Les mutations passent par le middleware CSRF global.
Le routeur n'a pas de préfixe : il porte aussi ``GET /sources`` (transparence,
domaine Meta du contrat) qui vit hors de ``/jobs``.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.problems import Problem
from app.modules.auth.models import User
from app.modules.auth.router import require_current_user
from app.modules.jobs.repository import JobsRepository, get_jobs_repository
from app.modules.jobs.schemas import (
    ContractType,
    JobDetail,
    RemotePolicy,
    SavedStateInput,
    SearchPage,
    SortMode,
    SourceOut,
)
from app.modules.jobs.service import JobsService

router = APIRouter(tags=["jobs"])


def get_jobs_service(
    repository: JobsRepository = Depends(get_jobs_repository),
) -> JobsService:
    return JobsService(repository)


@router.get("/jobs", response_model=SearchPage, summary="Recherche d'offres (E6, D07)")
async def search_jobs(
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    remote: Annotated[list[RemotePolicy] | None, Query()] = None,
    contract: Annotated[list[ContractType] | None, Query()] = None,
    salary_min: Annotated[int | None, Query(ge=0)] = None,
    posted_since: Annotated[int | None, Query(ge=1, description="jours")] = None,
    language: Annotated[str | None, Query(min_length=2, max_length=5)] = None,
    country: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[int, Query(ge=1, le=500)] = 30,
    include_blocked: Annotated[bool, Query()] = True,
    include_hidden: Annotated[bool, Query()] = False,
    saved_only: Annotated[bool, Query()] = False,
    sort: Annotated[SortMode, Query()] = "match",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> SearchPage:
    """Recherche d'offres — filtres durs SQL + full-text + rerank (D07).

    Notes M2 :
    - ``sort=match`` (défaut du contrat) retombe sur ``relevance`` tant que le
      scoring n'est pas livré (M3) — accepté sans erreur ;
    - ``include_blocked`` est accepté mais sans effet au M2 : les critères
      bloquants proviennent du scoring (M3). Défaut ``true`` conforme au
      contrat (les offres bloquées seront badgées, jamais retirées) ;
    - ``lat``/``lon`` vont ensemble (``radius_km`` défaut 30, §3 des contrats).
    """
    if (lat is None) != (lon is None):
        raise Problem(
            status=422,
            code="validation_error",
            title="Données invalides",
            detail="lat et lon doivent être fournis ensemble.",
            errors=[
                {
                    "field": "lat" if lat is None else "lon",
                    "code": "missing_pair",
                    "message": "lat et lon doivent être fournis ensemble.",
                }
            ],
        )
    return await service.search(
        user.id,
        q=q,
        remote=tuple(remote or ()),
        contract=tuple(contract or ()),
        salary_min=salary_min,
        posted_since=posted_since,
        language=language,
        country=country,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        include_hidden=include_hidden,
        saved_only=saved_only,
        sort=sort,
        limit=limit,
        cursor=cursor,
    )


@router.get("/jobs/{job_id}", response_model=JobDetail, summary="Détail d'une offre")
async def get_job_detail(
    job_id: uuid.UUID,
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
) -> JobDetail:
    """Détail d'une offre avec ses sources et liens d'origine.

    404 si l'offre n'existe pas, a été retirée, ou est expirée depuis plus de
    12 mois (rétention RM-E-4). Une offre expirée récente reste lisible :
    son ``status`` permet le bandeau « offre expirée » côté front.
    """
    return await service.get_detail(job_id, user.id)


@router.put(
    "/jobs/{job_id}/saved-state",
    status_code=204,
    summary="Sauvegarder ou masquer une offre",
)
async def put_saved_state(
    job_id: uuid.UUID,
    payload: SavedStateInput,
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
) -> Response:
    """Pose l'état ``saved`` ou ``hidden`` (upsert) — 404 si offre inconnue."""
    await service.set_saved_state(user.id, job_id, payload.state)
    return Response(status_code=204)


@router.delete(
    "/jobs/{job_id}/saved-state",
    status_code=204,
    summary="Retirer la sauvegarde / le masquage",
)
async def delete_saved_state(
    job_id: uuid.UUID,
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
) -> Response:
    """Retire l'état saved/hidden — idempotent (204 même sans état préalable)."""
    await service.clear_saved_state(user.id, job_id)
    return Response(status_code=204)


@router.get(
    "/sources",
    response_model=list[SourceOut],
    tags=["meta"],
    summary="Sources d'offres actives (transparence)",
)
async def list_sources(
    _user: Annotated[User, Depends(require_current_user)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
) -> list[SourceOut]:
    """Sources actives : slug, nom, nature, fraîcheur (``last_sync_at`` 🟡 null
    tant que ``connector_state`` n'est pas peuplée par l'ingestion)."""
    return await service.list_sources()

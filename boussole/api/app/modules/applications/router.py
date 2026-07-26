"""Routes du module applications (F-P, jalon M4) : suivi des candidatures.

Toutes les routes exigent une session valide (cookie ``boussole_session``) —
401 problem+json sinon. Les mutations passent par le middleware CSRF global
(en-tête ``X-CSRF-Token`` = cookie ``boussole_csrf``, sinon 403).

Contrat : GET/POST /applications, GET/PATCH/DELETE /applications/{id},
POST /applications/{id}/status (transition libre Q29, historisée RM-P-3).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response

from app.modules.applications.repository import (
    ApplicationsRepository,
    get_applications_repository,
)
from app.modules.applications.schemas import (
    ApplicationInput,
    ApplicationOut,
    ApplicationPage,
    ApplicationPatch,
    ApplicationStatus,
    StatusChangeInput,
)
from app.modules.applications.service import ApplicationsService
from app.modules.auth.models import User
from app.modules.auth.router import require_current_user

router = APIRouter(prefix="/applications", tags=["applications"])


def get_applications_service(
    repository: ApplicationsRepository = Depends(get_applications_repository),
) -> ApplicationsService:
    return ApplicationsService(repository)


@router.get("", response_model=ApplicationPage, summary="Lister les candidatures")
async def list_applications(
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
    status: Annotated[ApplicationStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> ApplicationPage:
    """Tableau de bord des candidatures de l'utilisateur.

    Filtre ``status`` optionnel (index ``applications(user_id, status)``),
    pagination par curseur opaque keyset ``(created_at, id)`` décroissant —
    curseur corrompu → 422 ``invalid_cursor``.
    """
    return await service.list(user.id, status=status, limit=limit, cursor=cursor)


@router.post(
    "",
    response_model=ApplicationOut,
    status_code=201,
    summary="Créer une candidature (offre interne ou externe)",
)
async def create_application(
    payload: ApplicationInput,
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
    idempotency_key: Annotated[
        uuid.UUID | None,
        Header(alias="Idempotency-Key", description="Rejeu sans double création 🟡"),
    ] = None,
) -> ApplicationOut:
    """Crée une candidature en statut ``draft``.

    - ``job_posting_id`` OU (``external_title`` ET ``external_company``),
      sinon 422 listant les champs requis (RM-P-2, AC-P-2) ;
    - ``job_posting_id`` fourni → l'offre doit exister, sinon 404 ;
    - ``Idempotency-Key`` optionnelle 🟡 : le rejeu de la même clé renvoie la
      candidature déjà créée (201, même corps) au lieu d'en créer une seconde ;
      ignorée si absente.
    """
    return await service.create(
        user.id,
        payload,
        idempotency_key=str(idempotency_key) if idempotency_key is not None else None,
    )


@router.get(
    "/{application_id}", response_model=ApplicationOut, summary="Détail d'une candidature"
)
async def get_application(
    application_id: uuid.UUID,
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
) -> ApplicationOut:
    """Fiche complète avec l'historique ``events[]`` en ordre chronologique.

    404 si la candidature n'existe pas OU appartient à un autre utilisateur
    (scoping : la ressource d'autrui est introuvable, jamais 403).
    """
    return await service.get(application_id, user.id)


@router.patch(
    "/{application_id}", response_model=ApplicationOut, summary="Éditer une candidature"
)
async def patch_application(
    application_id: uuid.UUID,
    payload: ApplicationPatch,
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
) -> ApplicationOut:
    """Édite ``notes`` et les champs ``external_*`` (champs fournis seulement).

    Le statut n'est PAS éditable ici : POST /applications/{id}/status
    (historisation RM-P-3). 422 si l'édition viderait le couple externe d'une
    candidature sans offre interne (RM-P-2).
    """
    return await service.patch(application_id, user.id, payload)


@router.delete(
    "/{application_id}", status_code=204, summary="Supprimer une candidature"
)
async def delete_application(
    application_id: uuid.UUID,
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
) -> Response:
    """Supprime la candidature et son historique d'événements (F-P alt. 3)."""
    await service.delete(application_id, user.id)
    return Response(status_code=204)


@router.post(
    "/{application_id}/status",
    response_model=ApplicationOut,
    summary="Changer le statut (transition historisée)",
)
async def change_application_status(
    application_id: uuid.UUID,
    payload: StatusChangeInput,
    user: Annotated[User, Depends(require_current_user)],
    service: Annotated[ApplicationsService, Depends(get_applications_service)],
) -> ApplicationOut:
    """Transition LIBRE (Q29) avec note optionnelle, historisée append-only.

    ``applied_at`` est posé à la première transition vers ``applied`` ;
    ``to_status`` égal au statut courant est permis (« note seule »).
    """
    return await service.change_status(application_id, user.id, payload)

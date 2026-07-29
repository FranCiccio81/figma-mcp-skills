"""Routes du module generation (E10, F-L/M/N/O, D10) — jalon M4.

Contrat : ``GET/POST /generations``, ``GET/PATCH /generations/{id}``,
``POST .../validate``, ``POST .../export``. Session valide requise (401
sinon) ; méthodes mutantes → middleware CSRF global. La génération est
asynchrone (202 + polling) : la tâche ``ai.generate`` est enfilée sur la
file ``ai`` via ``send_task`` (aucun import du module worker — l'enqueuer
est une dépendance injectable, substituée dans les tests).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response
from redis.asyncio import Redis

from app.core.enqueue import enqueue as enqueue_task
from app.core.redis import get_redis_cache
from app.modules.auth.models import User
from app.modules.auth.router import require_current_user
from app.modules.generation.repository import (
    GenerationRepository,
    get_generation_repository,
)
from app.modules.generation.schemas import (
    DocStatus,
    DocType,
    ExportOut,
    ExportRequest,
    GeneratedDocumentOut,
    GenerationCreate,
    GenerationPage,
    GenerationPatch,
)
from app.modules.generation.service import Enqueuer, GenerationService
from app.modules.profiles.repository import ProfilesRepository, get_profiles_repository

router = APIRouter(prefix="/generations", tags=["generation"])


def get_generation_enqueuer() -> Enqueuer:
    """Enfile ``ai.generate`` (file ``ai``, D16) — surchargé par les tests.

    ``send_task`` (par nom) évite d'importer ``app.workers`` dans le chemin
    API : le worker reste le seul à charger le code des tâches.
    """
    def enqueue(document_id: uuid.UUID) -> None:
        # Voir ``app.core.enqueue`` : publication bornée, échec remonté.
        enqueue_task("ai.generate", document_id, queue="ai")

    return enqueue


def get_generation_service(
    repository: GenerationRepository = Depends(get_generation_repository),
    profiles: ProfilesRepository = Depends(get_profiles_repository),
    cache: Redis = Depends(get_redis_cache),
    enqueue: Enqueuer = Depends(get_generation_enqueuer),
) -> GenerationService:
    return GenerationService(repository, profiles, cache, enqueue)


CurrentUser = Annotated[User, Depends(require_current_user)]
Service = Annotated[GenerationService, Depends(get_generation_service)]


@router.post(
    "",
    status_code=202,
    response_model=GeneratedDocumentOut,
    summary="Créer un contenu (email, lettre, variante CV, optimisation) — asynchrone",
)
async def create_generation(
    payload: GenerationCreate,
    user: CurrentUser,
    service: Service,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> GeneratedDocumentOut:
    """202 + document ``pending`` ; préconditions : profil validé (409
    ``profile_not_validated``), offre lisible (404) et non expirée (409
    ``job_expired``), quotas 10/h et 40/j (429 + ``Retry-After``).
    Idempotency-Key UUID obligatoire (TTL 24 h) : rejeu → réponse d'origine
    avec ``Idempotent-Replay: true``."""
    out, replayed = await service.create(user.id, payload, idempotency_key)
    if replayed:
        response.headers["Idempotent-Replay"] = "true"
    return out


@router.get(
    "",
    response_model=GenerationPage,
    summary=(
        "Bibliothèque des contenus générés "
        "(filtres doc_type/status/job_id/application_id)"
    ),
)
async def list_generations(
    user: CurrentUser,
    service: Service,
    doc_type: Annotated[DocType | None, Query()] = None,
    status: Annotated[DocStatus | None, Query()] = None,
    job_id: Annotated[uuid.UUID | None, Query()] = None,
    application_id: Annotated[
        uuid.UUID | None,
        Query(
            description="Filtre additif (12 §1) : documents rattachés à cette "
            "candidature (SCR-41, 04 Flux 7 §3) — pendant de "
            "``GenerationCreate.application_id``.",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> GenerationPage:
    """Liste scopée utilisateur, tri création décroissante, curseur keyset.

    Les filtres se cumulent (ET) et restent scopés à l'utilisateur : un
    ``application_id`` appartenant à autrui ne remonte simplement aucun
    document (page vide, jamais 403/404 — anti-énumération).
    """
    return await service.list(
        user.id,
        doc_type=doc_type,
        status=status,
        job_id=job_id,
        application_id=application_id,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/{document_id}",
    response_model=GeneratedDocumentOut,
    summary="Statut et contenu d'une génération (claims + anchoring_check)",
)
async def get_generation(
    document_id: uuid.UUID, user: CurrentUser, service: Service
) -> GeneratedDocumentOut:
    """Document scopé utilisateur (autrui → 404, anti-énumération)."""
    return await service.get(user.id, document_id)


@router.patch(
    "/{document_id}",
    response_model=GeneratedDocumentOut,
    summary="Éditer manuellement le brouillon (lève le contrôle d'ancrage)",
)
async def patch_generation(
    document_id: uuid.UUID,
    payload: GenerationPatch,
    user: CurrentUser,
    service: Service,
) -> GeneratedDocumentOut:
    """Brouillon uniquement (409 ``generation_not_editable`` sinon) ;
    ``anchoring_check`` passe à null + note de responsabilité (Q6 🟡)."""
    return await service.patch(user.id, document_id, payload)


@router.post(
    "/{document_id}/validate",
    response_model=GeneratedDocumentOut,
    summary="Validation humaine du contenu — obligatoire avant export (D10)",
)
async def validate_generation(
    document_id: uuid.UUID, user: CurrentUser, service: Service
) -> GeneratedDocumentOut:
    """draft → validated (``validated_at`` posé) ; un ancrage ``failed`` non
    levé par une édition manuelle bloque (409 ``generation_not_anchored``)."""
    return await service.validate(user.id, document_id)


@router.post(
    "/{document_id}/export",
    response_model=ExportOut,
    summary="Exporter le contenu — exige le statut validated (RM-L-3)",
)
async def export_generation(
    document_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
    payload: ExportRequest | None = None,
) -> ExportOut:
    """409 ``generation_not_validated`` sans validation humaine ; format
    ``text`` servi inline (copie) ; ``pdf``/``docx`` → 501 (M5 🟡)."""
    export_format = payload.format if payload is not None else "text"
    return await service.export(user.id, document_id, export_format)

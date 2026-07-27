"""Routes du sous-package CV (F-B) : /cv-documents.

Conformes à openapi.yaml (POST multipart ≤ 10 Mo → 202 ; GET statut +
résultat) avec UN écart documenté 🟡 : ``POST /cv-documents/{id}/apply``
est ABSENT d'openapi.yaml mais nécessaire au flux de fusion (F-B
alternatif 7 : la proposition est revue puis appliquée explicitement —
jamais d'écrasement silencieux). À reporter au contrat lors de la
prochaine revue (ajout additif d'endpoint, versionnement 12 §1).

Toutes les routes exigent une session valide ; les mutations passent par
le middleware CSRF global. Ressources scopées utilisateur : autrui → 404
(anti-énumération, 12 §5).
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from redis.asyncio import Redis

from app.core.ratelimit import FixedWindowRateLimiter
from app.core.redis import get_redis_cache
from app.core.storage import ObjectStorage, get_object_storage
from app.modules.auth.models import User
from app.modules.auth.router import require_current_user
from app.modules.profiles.cv.repository import (
    CvDocumentsRepository,
    get_cv_documents_repository,
)
from app.modules.profiles.cv.schemas import ApplyInput, CvDocumentOut
from app.modules.profiles.cv.service import MAX_UPLOAD_BYTES, CvService
from app.modules.profiles.repository import ProfilesRepository, get_profiles_repository
from app.modules.profiles.schemas import ProfileOut

router = APIRouter(prefix="/cv-documents", tags=["cv"])


def get_parse_enqueuer() -> Callable[[uuid.UUID], None]:
    """Enqueue de ``ai.parse_cv`` (file ``ai``, D12/D16) — injectable tests.

    Import paresseux : l'app FastAPI n'importe pas Celery au démarrage.
    ``send_task`` par nom : aucun import du module worker (frontières D01).
    """

    def enqueue(cv_document_id: uuid.UUID) -> None:
        from app.workers.celery_app import celery_app

        celery_app.send_task("ai.parse_cv", args=[str(cv_document_id)], queue="ai")

    return enqueue


def get_cv_service(
    repository: CvDocumentsRepository = Depends(get_cv_documents_repository),
    profiles_repository: ProfilesRepository = Depends(get_profiles_repository),
    storage: ObjectStorage = Depends(get_object_storage),
    cache: Redis = Depends(get_redis_cache),
    enqueue_parse: Callable[[uuid.UUID], None] = Depends(get_parse_enqueuer),
) -> CvService:
    return CvService(
        repository,
        profiles_repository,
        storage,
        FixedWindowRateLimiter(cache),
        enqueue_parse,
    )


CurrentUser = Annotated[User, Depends(require_current_user)]
Service = Annotated[CvService, Depends(get_cv_service)]


@router.post(
    "",
    status_code=202,
    response_model=CvDocumentOut,
    summary="Importer un CV (PDF/DOCX, ≤ 10 Mo) — parsing asynchrone",
)
async def upload_cv(file: UploadFile, user: CurrentUser, service: Service) -> CvDocumentOut:
    """202 : upload accepté, parsing en file ``ai`` (F-B nominal).

    Validations synchrones AVANT stockage : taille ≤ 10 Mo (413
    ``too_large``), MIME réel par magic bytes (415 ``unsupported_format``),
    quota 5/jour (429 ``rate_limited`` + Retry-After). Scan antivirus 🟡
    ClamAV : hors périmètre M4 (12 §5).
    """
    # Lecture bornée : au plus MAX+1 octets suffisent à détecter le dépassement.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    return await service.upload(user.id, file.filename or "cv", data)


@router.get(
    "/{document_id}",
    response_model=CvDocumentOut,
    summary="Statut du parsing et résultat d'extraction (proposition de profil)",
)
async def get_cv_document(
    document_id: uuid.UUID, user: CurrentUser, service: Service
) -> CvDocumentOut:
    """Statut + ``error_code`` + ``extraction_warnings`` ; si ``parsed``,
    ``proposal`` porte les champs extraits avec provenance ``cv_extraction``
    et confidence — PAS encore écrits dans le profil (RM-B-1)."""
    return await service.get(user.id, document_id)


@router.post(
    "/{document_id}/apply",
    response_model=ProfileOut,
    summary="Appliquer la proposition au profil (fusion sans écrasement) 🟡",
)
async def apply_cv_proposal(
    document_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
    selection: ApplyInput | None = None,
) -> ProfileOut:
    """Écart openapi documenté 🟡 (voir module docstring) : fusionne la
    proposition dans le profil — champs ``user_input``/``user_confirmed``
    JAMAIS écrasés, ajouts en ``cv_extraction``, ``version``++ (RM-C-4).

    Corps JSON OPTIONNEL (``ApplyInput``) : sélection par ``item_id`` issue
    de la revue (04 Flux 1 §5). Corps absent = tout appliquer
    (rétrocompatible) ; id inconnu ignoré silencieusement 🟡."""
    return await service.apply(user.id, document_id, selection)

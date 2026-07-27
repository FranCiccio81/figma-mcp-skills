"""Routes du module privacy (F-Q, jalon M5).

- ``POST /privacy/export`` : demande d'export RGPD — 202, Idempotency-Key,
  quota 2/jour (RM-Q-3) ;
- ``GET /privacy/exports/{id}`` : statut pending/ready/expired + lien signé ;
- ``GET /privacy/exports/{id}/download`` : téléchargement authentifié via le
  lien signé HMAC (stub 🟡 du pré-signé S3), 410 ``export_expired`` au-delà
  de 7 jours ;
- ``DELETE /account`` : soft delete immédiat + purge planifiée ≤ 30 j (D09).
"""

import importlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query, Response
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.problems import Problem
from app.core.ratelimit import FixedWindowRateLimiter
from app.core.redis import get_redis_cache, get_redis_persistent
from app.core.security import SessionStore
from app.core.storage import ObjectNotFoundError, ObjectStorage, get_object_storage
from app.modules.auth.models import User
from app.modules.auth.router import get_session_store, require_current_user
from app.modules.privacy.repository import (
    ExportRecord,
    PrivacyRepository,
    get_privacy_repository,
)
from app.modules.privacy.schemas import (
    DeleteAccountRequest,
    ExportRequestedResponse,
    ExportStatus,
    ExportStatusResponse,
)
from app.modules.privacy.service import PrivacyService
from app.modules.privacy.signing import make_download_url, verify_export_signature

logger = logging.getLogger("boussole.privacy")

router = APIRouter(tags=["privacy"])

#: Quota d'export (RM-Q-3, 09 §5) — 🟡 à déplacer dans Settings (hors périmètre).
EXPORT_DAILY_LIMIT = 2
EXPORT_QUOTA_WINDOW_SECONDS = 24 * 3600
#: TTL du rejeu idempotent (aligné sur la fenêtre de quota).
IDEMPOTENCY_TTL_SECONDS = 24 * 3600

#: Limite dédiée de DELETE /account (M4) — 5 tentatives/heure par utilisateur.
#: Le middleware global ne suffit pas : il est contournable et fail-OPEN, ce
#: qui laissait la route jouer les oracles de mot de passe (401 vs 204).
ACCOUNT_DELETE_LIMIT = 5
ACCOUNT_DELETE_WINDOW_SECONDS = 3600

EnqueueExport = Callable[[uuid.UUID], None]


def get_export_enqueuer() -> EnqueueExport:
    """Enfile la tâche Celery ``maintenance.privacy_export``.

    Import paresseux : l'API n'importe pas les workers à froid et les tests
    substituent un espion via ``dependency_overrides``.
    """

    def enqueue(export_id: uuid.UUID) -> None:
        tasks = importlib.import_module("app.workers.privacy_tasks")
        tasks.privacy_export.delay(str(export_id))

    return enqueue


def get_storage() -> ObjectStorage:
    """Dépendance stockage objet (surchargée par un fake dans les tests)."""
    return get_object_storage()


def _idempotency_redis_key(user_id: uuid.UUID, idempotency_key: str) -> str:
    return f"privacy:export:idem:{user_id}:{idempotency_key}"


def _effective_status(record: ExportRecord, now: datetime) -> ExportStatus:
    """« expired » est dérivé de ``expires_at`` — jamais stocké en base."""
    if (
        record.status == "ready"
        and record.expires_at is not None
        and record.expires_at <= now
    ):
        return "expired"
    return "ready" if record.status == "ready" else "pending"


_NOT_FOUND = {
    "status": 404,
    "code": "not_found",
    "title": "Ressource introuvable",
    "detail": "Export inexistant.",
}


@router.post("/privacy/export", status_code=202, response_model=ExportRequestedResponse)
async def request_export(
    user: User = Depends(require_current_user),
    repository: PrivacyRepository = Depends(get_privacy_repository),
    cache: Redis = Depends(get_redis_cache),
    persistent: Redis = Depends(get_redis_persistent),
    enqueue: EnqueueExport = Depends(get_export_enqueuer),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ExportRequestedResponse:
    """Demande un export RGPD (archive JSON) — asynchrone, 202."""
    # Rejeu idempotent AVANT le quota : rejouer une demande ne la consomme pas.
    if idempotency_key:
        replayed = await persistent.get(_idempotency_redis_key(user.id, idempotency_key))
        if replayed:
            record = await repository.get_export(uuid.UUID(str(replayed)))
            if record is not None and record.user_id == user.id:
                return ExportRequestedResponse(
                    id=record.id, status=_effective_status(record, datetime.now(UTC))
                )

    # Quota RGPD sur le Redis VOLATILE (allkeys-lru, D17) : sous pression
    # mémoire, la clé de quota peut être ÉVINCÉE avant la fin des 24 h — le
    # quota est alors réinitialisé prématurément (risque accepté et documenté,
    # à déplacer sur le Redis persistant si l'abus devient réel 🟡).
    #
    # Choix fail-CLOSED (écart ASSUMÉ à D18, qui prescrit le fail-open pour le
    # rate limiting best-effort) : ici le compteur n'est pas une protection
    # anti-abus mais un QUOTA RGPD garantissant qu'un utilisateur ne peut pas
    # déclencher des dumps personnels complets en boucle. Redis indisponible →
    # aucun quota vérifiable → on refuse proprement (503, réessayable) plutôt
    # que d'ouvrir une fabrique d'archives non plafonnée.
    limiter = FixedWindowRateLimiter(cache)
    try:
        result = await limiter.hit(
            "privacy_export",
            str(user.id),
            limit=EXPORT_DAILY_LIMIT,
            window_seconds=EXPORT_QUOTA_WINDOW_SECONDS,
        )
    except Exception as exc:
        logger.error(
            "privacy_export_quota_unavailable",
            extra={"detail": "Redis volatile indisponible — refus fail-closed"},
        )
        raise Problem(
            status=503,
            code="service_unavailable",
            title="Service temporairement indisponible",
            detail=(
                "Le quota d'exports ne peut pas être vérifié pour le moment. "
                "Réessayez dans quelques instants."
            ),
            headers={"Retry-After": "60"},
        ) from exc
    if not result.allowed:
        raise Problem(
            status=429,
            code="rate_limited",
            title="Trop de requêtes",
            detail="Quota d'exports atteint (2 par jour). Réessayez plus tard.",
            headers={"Retry-After": str(result.retry_after)},
        )

    record = await repository.create_export(user.id, datetime.now(UTC))
    if idempotency_key:
        await persistent.set(
            _idempotency_redis_key(user.id, idempotency_key),
            str(record.id),
            ex=IDEMPOTENCY_TTL_SECONDS,
        )
    await repository.add_audit(
        user.id, "privacy_export_requested", entity="privacy_export", entity_id=record.id
    )
    enqueue(record.id)
    return ExportRequestedResponse(id=record.id, status="pending")


@router.get("/privacy/exports/{export_id}", response_model=ExportStatusResponse)
async def get_export_status(
    export_id: uuid.UUID,
    user: User = Depends(require_current_user),
    repository: PrivacyRepository = Depends(get_privacy_repository),
) -> ExportStatusResponse:
    """Statut de l'export et lien signé (validité 7 jours)."""
    record = await repository.get_export(export_id)
    if record is None or record.user_id != user.id:
        raise Problem(**_NOT_FOUND)  # type: ignore[arg-type]
    status = _effective_status(record, datetime.now(UTC))
    download_url = None
    if status == "ready" and record.expires_at is not None:
        download_url = make_download_url(record.id, record.expires_at)
    return ExportStatusResponse(id=record.id, status=status, download_url=download_url)


@router.get("/privacy/exports/{export_id}/download")
async def download_export(
    export_id: uuid.UUID,
    expires: int = Query(),
    sig: str = Query(),
    user: User = Depends(require_current_user),
    repository: PrivacyRepository = Depends(get_privacy_repository),
    storage: ObjectStorage = Depends(get_storage),
) -> Response:
    """Téléchargement de l'archive via lien signé HMAC (stub 🟡 pré-signé S3).

    À usage authentifié (F-Q 🟡) : session valide + propriété + signature.
    """
    record = await repository.get_export(export_id)
    if record is None or record.user_id != user.id:
        raise Problem(**_NOT_FOUND)  # type: ignore[arg-type]
    # Signature invalide → 404 volontaire (pas d'oracle sur l'existence).
    if not verify_export_signature(export_id, expires, sig):
        raise Problem(**_NOT_FOUND)  # type: ignore[arg-type]
    now = datetime.now(UTC)
    if int(now.timestamp()) >= expires or _effective_status(record, now) != "ready":
        raise Problem(
            status=410,
            code="export_expired",
            title="Lien d'export expiré",
            detail="Le lien de téléchargement a expiré (7 jours). Demandez un nouvel export.",
        )
    if not record.file_key:
        raise Problem(**_NOT_FOUND)  # type: ignore[arg-type]
    # ``ObjectStorage`` (app/core/storage.py) est SYNCHRONE et signale l'absence
    # par ``ObjectNotFoundError`` — jamais par ``None``.
    try:
        data = storage.get(record.file_key)
    except ObjectNotFoundError:
        # Archive absente (purgée, ou jamais écrite) → 404, sans oracle.
        logger.warning(
            "privacy_export_object_missing",
            extra={"detail": f"export={record.id} key={record.file_key}"},
        )
        raise Problem(**_NOT_FOUND) from None  # type: ignore[arg-type]
    await repository.add_audit(
        user.id, "data_export_downloaded", entity="privacy_export", entity_id=record.id
    )
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="boussole-export-{record.id}.json"'
        },
    )


@router.delete("/account", status_code=204)
async def delete_account(
    payload: DeleteAccountRequest,
    user: User = Depends(require_current_user),
    repository: PrivacyRepository = Depends(get_privacy_repository),
    sessions: SessionStore = Depends(get_session_store),
    cache: Redis = Depends(get_redis_cache),
) -> Response:
    """Supprime le compte : soft delete immédiat, purge sous 30 jours (D09).

    Limiteur DÉDIÉ 5/h par ``user_id`` (M4) en **fail-closed** : la route
    vérifie un mot de passe et distingue 401 / 204, c'est donc un oracle de
    mot de passe pour quiconque a volé un cookie de session. Le middleware
    global ne la protège pas (identité contournable, fail-open D18) : si le
    compteur est indisponible, on REFUSE (503) plutôt que d'ouvrir un oracle
    non plafonné — écart à D18 assumé, cohérent avec le quota d'export.
    """
    limiter = FixedWindowRateLimiter(cache)
    try:
        attempt = await limiter.hit(
            "account_delete",
            str(user.id),
            limit=ACCOUNT_DELETE_LIMIT,
            window_seconds=ACCOUNT_DELETE_WINDOW_SECONDS,
        )
    except Exception as exc:
        logger.error(
            "account_delete_rate_limit_unavailable",
            extra={"detail": "Redis volatile indisponible — refus fail-closed"},
        )
        raise Problem(
            status=503,
            code="service_unavailable",
            title="Service temporairement indisponible",
            detail=(
                "La suppression de compte est momentanément indisponible. "
                "Réessayez dans quelques instants."
            ),
            headers={"Retry-After": "60"},
        ) from exc
    if not attempt.allowed:
        await repository.add_audit(
            user.id, "account_deletion_rate_limited", entity="user", entity_id=user.id
        )
        raise Problem(
            status=429,
            code="rate_limited",
            title="Trop de tentatives",
            detail="Trop de tentatives de suppression de compte. Réessayez plus tard.",
            headers={"Retry-After": str(attempt.retry_after)},
        )

    service = PrivacyService(repository, sessions)
    outcome = await service.delete_account(user, payload.password)
    if outcome is None:
        # Audit de l'ÉCHEC (M4) : un mot de passe erroné sur cette route est un
        # signal de compromission de session — il doit être traçable (D20).
        await repository.add_audit(
            user.id,
            "account_deletion_failed",
            entity="user",
            entity_id=user.id,
            meta={"reason": "invalid_password"},
        )
        raise Problem(
            status=401,
            code="invalid_credentials",
            title="Identifiants invalides",
            detail="Mot de passe incorrect — la suppression n'a pas été effectuée.",
        )
    logger.info(
        "account_deletion_requested",
        extra={"detail": f"purge_after={outcome.deletion.purge_after.isoformat()}"},
    )
    response = Response(status_code=204)
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return response

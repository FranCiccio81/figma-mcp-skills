"""Application FastAPI Boussole.

- préfixe /api/v1 ;
- middleware trace_id + logs JSON structurés (D20) ;
- middleware CSRF double-submit sur toute méthode mutante ;
- erreurs RFC 9457 (application/problem+json) ;
- /healthz (liveness) et /readyz (readiness : DB + deux Redis).
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings, get_settings
from app.core.db import check_database
from app.core.problems import problem_response, register_problem_handlers
from app.core.ratelimit import FixedWindowRateLimiter
from app.core.redis import check_redis, get_redis_cache, get_redis_persistent
from app.core.security import SessionStore, csrf_tokens_match
from app.core.storage import (
    StorageConfigurationError,
    check_storage_configuration,
    probe_object_storage,
)
from app.modules.applications.router import router as applications_router
from app.modules.auth.router import router as auth_router
from app.modules.explanations.router import router as explanations_router
from app.modules.generation.router import router as generation_router
from app.modules.ingestion.router import router as ingestion_router
from app.modules.jobs.router import router as jobs_router
from app.modules.matching.router import router as matching_router
from app.modules.preferences.router import router as preferences_router
from app.modules.privacy.router import router as privacy_router
from app.modules.profiles.cv.router import router as cv_documents_router
from app.modules.profiles.router import router as profiles_router

logger = logging.getLogger("boussole.http")

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_LOG_EXTRA_FIELDS = ("trace_id", "method", "path", "status_code", "duration_ms", "detail")

#: Fabrique de client Redis (injectée au ``create_app`` — voir M2 ci-dessous).
RedisFactory = Callable[[], Redis]

#: Proxies de confiance pour ``X-Forwarded-For`` (M1).
#:
#: L'API tourne DERRIÈRE le proxy Next.js : sans configuration, l'adresse vue
#: par uvicorn est celle du proxy et TOUT le trafic anonyme partage un unique
#: seau de 60 req/min → auto-DoS trivial (un seul visiteur bruyant bloque tout
#: le monde). Le correctif a deux moitiés, indissociables :
#:
#: 1. uvicorn est lancé avec ``--proxy-headers --forwarded-allow-ips=<liste>``
#:    (voir ``infra/Dockerfile.api`` et ``infra/docker-compose.dev.yml``) ;
#: 2. ``X-Forwarded-For`` n'est lu QUE si le pair immédiat figure dans cette
#:    même liste, et on retient le DERNIER SAUT DE CONFIANCE : on parcourt la
#:    chaîne de DROITE à GAUCHE et on garde la première adresse qui n'est pas
#:    un proxy de confiance. Prendre l'entrée de gauche (usage naïf) laisserait
#:    n'importe quel client forger son identité en préfixant l'en-tête.
#:
#: Défaut volontairement restrictif : ``127.0.0.1``. En l'absence de variable
#: d'environnement, aucun en-tête transmis n'est cru — on retombe sur l'IP du
#: pair, comportement sûr (mais partagé) plutôt que falsifiable.
TRUSTED_PROXIES_ENV = "FORWARDED_ALLOW_IPS"
DEFAULT_TRUSTED_PROXIES = "127.0.0.1"


def trusted_proxies() -> frozenset[str]:
    """Liste des proxies de confiance (``FORWARDED_ALLOW_IPS``, style uvicorn)."""
    raw = os.getenv(TRUSTED_PROXIES_ENV, DEFAULT_TRUSTED_PROXIES)
    return frozenset(entry.strip() for entry in raw.split(",") if entry.strip())


def client_ip(request: Request, trusted: frozenset[str]) -> str:
    """IP cliente réelle — ``X-Forwarded-For`` cru UNIQUEMENT derrière un proxy sûr."""
    peer = request.client.host if request.client else None
    if peer is None:
        return "unknown"
    if peer not in trusted and "*" not in trusted:
        # Pair non fiable : son en-tête XFF est ignoré (il serait forgeable).
        return peer
    forwarded = request.headers.get("X-Forwarded-For")
    if not forwarded:
        return peer
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    for hop in reversed(hops):
        if hop not in trusted:
            return hop  # dernier saut de confiance
    return peer


class JsonLogFormatter(logging.Formatter):
    """Logs JSON structurés minimaux avec trace_id (D20)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _LOG_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class TraceMiddleware(BaseHTTPMiddleware):
    """Pose request.state.trace_id, le renvoie en en-tête et journalise."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "http_request",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class CsrfMiddleware(BaseHTTPMiddleware):
    """CSRF double-submit : X-CSRF-Token doit égaler le cookie boussole_csrf.

    Exemptions : /auth/register et /auth/login (aucune session — c'est eux
    qui posent le cookie CSRF).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        exempt = {
            f"{settings.api_prefix}/auth/register",
            f"{settings.api_prefix}/auth/login",
        }
        if request.method in _MUTATING_METHODS and request.url.path not in exempt:
            header = request.headers.get(settings.csrf_header_name)
            cookie = request.cookies.get(settings.csrf_cookie_name)
            if not csrf_tokens_match(header, cookie):
                return problem_response(
                    request,
                    status=403,
                    code="csrf_invalid",
                    title="Jeton CSRF invalide",
                    detail=(
                        "L'en-tête X-CSRF-Token est absent ou ne correspond pas "
                        "au cookie CSRF."
                    ),
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limites contractuelles 12 §1 : global 60 req/min, recherche 30/min.

    **Identité (C3)** : la session doit être RÉELLEMENT VALIDÉE dans le store
    Redis persistant. L'implémentation précédente hachait le cookie
    ``boussole_session`` SANS le vérifier : il suffisait d'envoyer une valeur
    aléatoire différente à chaque requête pour obtenir un seau neuf à chaque
    fois — 200 requêtes, 0 rejet. Désormais :

    - cookie présent ET session connue du store → identité = ``user:<uuid>``
      (un seau par utilisateur, quel que soit le nombre de sessions) ;
    - cookie absent, inconnu, expiré ou store injoignable → ANONYME, identité
      = ``ip:<ip cliente>``. Un cookie arbitraire ne crée donc plus de seau :
      il retombe dans celui de son IP.

    **Injection (M2)** : le client Redis vient de ``app.state`` (posé par
    :func:`create_app`) et non plus d'un appel direct à ``get_redis_cache()``
    hors DI — les tests peuvent enfin exercer le limiteur pour de vrai.

    Best-effort assumé (fail-open D18) : Redis volatile indisponible → la
    requête passe et l'incident est logué. Le rate limiting est une
    protection, jamais un point de panne. (Les routes qui ne PEUVENT pas
    s'ouvrir — quota d'export RGPD, DELETE /account — portent leur propre
    limiteur fail-closed ; voir ``modules/privacy/router.py``.) Les sondes
    /healthz|/readyz et les fichiers statiques ne sont pas comptés.
    """

    async def _identity(self, request: Request, settings: Settings) -> str:
        """Identité de seau : utilisateur authentifié, sinon IP cliente."""
        token = request.cookies.get(settings.session_cookie_name)
        if token:
            try:
                store = SessionStore(
                    request.app.state.redis_persistent_factory(),
                    settings.session_ttl_seconds,
                )
                user_id = await store.get_user_id(token)
            except Exception:
                # Store de sessions injoignable → on ne devine pas : anonyme.
                logger.warning("rate_limit_session_lookup_failed")
                user_id = None
            if user_id is not None:
                return f"user:{user_id}"
        return f"ip:{client_ip(request, trusted_proxies())}"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        if not path.startswith(settings.api_prefix):
            return await call_next(request)
        identity = await self._identity(request, settings)
        try:
            limiter = FixedWindowRateLimiter(request.app.state.redis_cache_factory())
            result = await limiter.hit("global", identity, limit=60, window_seconds=60)
            if result.allowed and request.method == "GET" and path == f"{settings.api_prefix}/jobs":
                result = await limiter.hit("search", identity, limit=30, window_seconds=60)
        except Exception:  # fail-open volontaire (D18)
            logger.warning("rate_limit_unavailable", extra={"path": path})
            return await call_next(request)
        if not result.allowed:
            response = problem_response(
                request,
                status=429,
                code="rate_limited",
                title="Trop de requêtes",
                detail="Limite de requêtes atteinte. Réessayez dans un instant.",
            )
            response.headers["Retry-After"] = str(result.retry_after)
            return response
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """En-têtes de sécurité de base côté API (le front/edge pose CSP/HSTS —
    12 §5) : anti-sniffing, anti-framing, référeur minimal."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response


#: Borne d'attente de la sonde de stockage dans ``/readyz`` 🟡. Le client
#: botocore a déjà ses propres timeouts (``S3_*_TIMEOUT_SECONDS`` ×
#: ``S3_MAX_ATTEMPTS``), mais leur produit peut dépasser la minute : la sonde
#: de readiness doit répondre bien avant l'orchestrateur.
READYZ_STORAGE_TIMEOUT_SECONDS = 3.0


async def _storage_ready() -> bool:
    """Readiness du stockage objet : configuration **puis** joignabilité (13).

    L'ancienne sonde ne relisait que la configuration : un bucket supprimé,
    une clé révoquée ou un MinIO éteint laissaient ``/readyz`` vert pendant
    que tous les imports de CV et exports RGPD échouaient. On ajoute un
    ``HeadBucket`` réel, exécuté dans un threadpool (boto3 est bloquant) et
    borné par :data:`READYZ_STORAGE_TIMEOUT_SECONDS`.
    """
    try:
        check_storage_configuration()
    except StorageConfigurationError:
        logger.error("storage_misconfigured")
        return False
    try:
        await asyncio.wait_for(
            run_in_threadpool(probe_object_storage),
            timeout=READYZ_STORAGE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        # ``wait_for`` n'interrompt pas le thread : la sonde continue en
        # arrière-plan mais /readyz ne l'attend plus (fail-closed).
        logger.error("storage_probe_timeout")
        return False
    except Exception:
        logger.error("storage_unreachable")
        return False
    return True


def create_app(
    *,
    redis_cache_factory: RedisFactory | None = None,
    redis_persistent_factory: RedisFactory | None = None,
) -> FastAPI:
    """Construit l'application FastAPI.

    ``redis_cache_factory`` / ``redis_persistent_factory`` (M2) : les
    middlewares ne passent PAS par l'injection de dépendances FastAPI —
    ``dependency_overrides`` ne les atteint pas. Les fabriques sont donc
    posées sur ``app.state`` ici et lues par les middlewares, ce qui rend le
    rate limiting réellement testable (fakeredis) au lieu de n'exercer que sa
    branche fail-open.
    """
    configure_logging()
    settings = get_settings()

    # Refus de démarrer plutôt que de perdre des données : en production, un
    # stockage local signifie que le worker écrit sur SON disque et l'API lit
    # LE SIEN — exports RGPD et CV introuvables dès que les conteneurs sont
    # distincts (défaut relevé en revue M5).
    check_storage_configuration(settings)

    app = FastAPI(
        title="Boussole API",
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs" if not settings.is_production else None,
    )

    app.state.redis_cache_factory = redis_cache_factory or get_redis_cache
    app.state.redis_persistent_factory = redis_persistent_factory or get_redis_persistent

    register_problem_handlers(app)
    # add_middleware empile : CSRF d'abord (interne), puis rate limit,
    # en-têtes de sécurité, et trace en dernier (externe)
    # → le trace_id existe quand le CSRF répond 403.
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TraceMiddleware)

    api = APIRouter(prefix=settings.api_prefix)
    api.include_router(auth_router)
    api.include_router(cv_documents_router)
    api.include_router(profiles_router)
    api.include_router(preferences_router)
    # jobs avant ingestion : GET /sources (M2, module jobs, domaine Meta du
    # contrat) doit précéder le stub 501 « /sources » du module ingestion.
    api.include_router(jobs_router)
    api.include_router(ingestion_router)
    api.include_router(matching_router)
    api.include_router(explanations_router)
    api.include_router(generation_router)
    api.include_router(applications_router)
    api.include_router(privacy_router)
    app.include_router(api)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(request: Request) -> Response:
        checks = {
            "database": await check_database(),
            "redis_persistent": await check_redis(app.state.redis_persistent_factory()),
            "redis_cache": await check_redis(app.state.redis_cache_factory()),
            "storage": await _storage_ready(),
        }
        if all(checks.values()):
            return JSONResponse({"status": "ready", "checks": checks})
        return problem_response(
            request,
            status=503,
            code="not_ready",
            title="Service indisponible",
            detail=f"Dépendances indisponibles : {[k for k, v in checks.items() if not v]}",
        )

    return app


app = create_app()

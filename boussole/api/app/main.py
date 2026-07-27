"""Application FastAPI Boussole.

- préfixe /api/v1 ;
- middleware trace_id + logs JSON structurés (D20) ;
- middleware CSRF double-submit sur toute méthode mutante ;
- erreurs RFC 9457 (application/problem+json) ;
- /healthz (liveness) et /readyz (readiness : DB + deux Redis).
"""

import hashlib
import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.db import check_database
from app.core.problems import problem_response, register_problem_handlers
from app.core.ratelimit import FixedWindowRateLimiter
from app.core.redis import check_redis, get_redis_cache, get_redis_persistent
from app.core.security import csrf_tokens_match
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

    Identité : hash du cookie de session si présent, sinon IP cliente.
    Best-effort assumé (fail-open D18) : Redis volatile indisponible →
    la requête passe et l'incident est logué — le rate limiting est une
    protection, jamais un point de panne. Les sondes /healthz|/readyz et
    les fichiers statiques ne sont pas comptés.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        if not path.startswith(settings.api_prefix):
            return await call_next(request)
        session_token = request.cookies.get(settings.session_cookie_name)
        if session_token:
            identity = hashlib.sha256(session_token.encode()).hexdigest()[:32]
        else:
            identity = request.client.host if request.client else "unknown"
        try:
            limiter = FixedWindowRateLimiter(get_redis_cache())
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


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Boussole API",
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs" if not settings.is_production else None,
    )

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
            "redis_persistent": await check_redis(get_redis_persistent()),
            "redis_cache": await check_redis(get_redis_cache()),
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

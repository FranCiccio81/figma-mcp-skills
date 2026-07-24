"""Application FastAPI Boussole.

- préfixe /api/v1 ;
- middleware trace_id + logs JSON structurés (D20) ;
- middleware CSRF double-submit sur toute méthode mutante ;
- erreurs RFC 9457 (application/problem+json) ;
- /healthz (liveness) et /readyz (readiness : DB + deux Redis).
"""

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
    # add_middleware empile : CSRF d'abord (interne), trace ensuite (externe)
    # → le trace_id existe quand le CSRF répond 403.
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(TraceMiddleware)

    api = APIRouter(prefix=settings.api_prefix)
    api.include_router(auth_router)
    api.include_router(profiles_router)
    api.include_router(preferences_router)
    api.include_router(ingestion_router)
    api.include_router(jobs_router)
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

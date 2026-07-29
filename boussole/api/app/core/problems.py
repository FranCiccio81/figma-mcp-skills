"""Erreurs RFC 9457 (``application/problem+json``).

Champs : ``type``, ``title``, ``status``, ``detail``, ``errors[]`` (violations
de champ), ``trace_id``. Codes stables sous ``https://api.boussole.eu/errors/``.
"""

import logging
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.enqueue import EnqueueError

logger = logging.getLogger("boussole.problems")

PROBLEM_CONTENT_TYPE = "application/problem+json"
ERROR_TYPE_BASE = "https://api.boussole.eu/errors/"




class Problem(Exception):
    """Exception métier sérialisée en RFC 9457."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str | None = None,
        errors: Sequence[Mapping[str, str]] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.errors = list(errors) if errors is not None else None
        self.headers = dict(headers) if headers is not None else None


def not_implemented_problem(module: str, milestone: str = "M2+") -> Problem:
    """501 documenté pour les stubs de modules (aucun TODO silencieux)."""
    return Problem(
        status=501,
        code="not_implemented",
        title="Fonctionnalité non disponible",
        detail=f"Module « {module} » : prévu au jalon {milestone}.",
    )


def get_trace_id(request: Request | None) -> str:
    if request is not None:
        trace_id = getattr(request.state, "trace_id", None)
        if isinstance(trace_id, str) and trace_id:
            return trace_id
    return uuid.uuid4().hex


def problem_response(
    request: Request | None,
    *,
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    errors: Sequence[Mapping[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{ERROR_TYPE_BASE}{code}",
        "title": title,
        "status": status,
        "trace_id": get_trace_id(request),
    }
    if detail is not None:
        body["detail"] = detail
    if errors is not None:
        body["errors"] = list(errors)
    return JSONResponse(
        status_code=status,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
        headers=dict(headers) if headers else None,
    )


_HTTP_TITLES_FR: dict[int, str] = {
    400: "Requête invalide",
    401: "Authentification requise",
    403: "Accès refusé",
    404: "Ressource introuvable",
    405: "Méthode non autorisée",
    409: "Conflit",
    413: "Contenu trop volumineux",
    415: "Format non supporté",
    422: "Données invalides",
    429: "Trop de requêtes",
    500: "Erreur interne",
    501: "Fonctionnalité non disponible",
    503: "Service indisponible",
}

_HTTP_CODES: dict[int, str] = {
    400: "bad_request",
    401: "authentication_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "not_ready",
}


def _handle_enqueue_error(request: Request, exc: Exception) -> JSONResponse:
    """Courtier injoignable → 503, jamais 500.

    La distinction n'est pas cosmétique : un 500 dit « bug », un 503 dit
    « réessayez », et c'est le second qui est vrai. Le front peut proposer de
    relancer l'import ; sur un 500 il ne peut que s'excuser. ``Retry-After``
    borne la ré-émission pour ne pas transformer une panne de courtier en
    tempête de requêtes.
    """
    logger.warning("enqueue_unavailable path=%s", request.url.path)
    return _handle_problem(
        request,
        Problem(
            status=503,
            code="service_unavailable",
            title="Traitement momentanément indisponible",
            detail=(
                "La demande n'a pas pu être mise en file de traitement. "
                "Réessayez dans quelques instants — rien n'a été perdu."
            ),
            headers={"Retry-After": "30"},
        ),
    )


def _handle_problem(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, Problem)
    return problem_response(
        request,
        status=exc.status,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        errors=exc.errors,
        headers=exc.headers,
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {
            "field": ".".join(str(loc) for loc in err.get("loc", []) if loc != "body"),
            "code": str(err.get("type", "invalid")),
            "message": str(err.get("msg", "Valeur invalide")),
        }
        for err in exc.errors()
    ]
    return problem_response(
        request,
        status=422,
        code="validation_error",
        title="Données invalides",
        detail="Un ou plusieurs champs sont invalides.",
        errors=errors,
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    status = exc.status_code
    detail = exc.detail if isinstance(exc.detail, str) else None
    return problem_response(
        request,
        status=status,
        code=_HTTP_CODES.get(status, "http_error"),
        title=_HTTP_TITLES_FR.get(status, "Erreur"),
        detail=detail,
        headers=getattr(exc, "headers", None),
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", extra={"trace_id": get_trace_id(request)})
    return problem_response(
        request,
        status=500,
        code="internal_error",
        title="Erreur interne",
        detail="Une erreur inattendue s'est produite. Réessayez plus tard.",
    )


def register_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Problem, _handle_problem)
    app.add_exception_handler(EnqueueError, _handle_enqueue_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)

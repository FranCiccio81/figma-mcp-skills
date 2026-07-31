"""Routes du module auth : /auth/register, /auth/login, /auth/logout, /me."""

import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.degradation import signal_degradation
from app.core.problems import Problem
from app.core.ratelimit import FixedWindowRateLimiter
from app.core.redis import get_redis_cache, get_redis_persistent
from app.core.security import SessionStore
from app.modules.auth.audit import (
    LOGGED_OUT,
    LOGIN_FAILED,
    LOGIN_SUCCEEDED,
    REGISTERED,
    build_meta,
    record,
)
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository, get_auth_repository
from app.modules.auth.schemas import (
    LoginRequest,
    MeResponse,
    OnboardingState,
    RegisterRequest,
    RegisterResponse,
)
from app.modules.auth.service import AuthCookies, AuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


def get_session_store(redis: Redis = Depends(get_redis_persistent)) -> SessionStore:
    return SessionStore(redis, get_settings().session_ttl_seconds)


def get_auth_service(
    repository: AuthRepository = Depends(get_auth_repository),
    sessions: SessionStore = Depends(get_session_store),
) -> AuthService:
    return AuthService(repository, sessions)


async def require_current_user(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> User:
    """Dépendance : session valide requise, sinon 401 (problem+json)."""
    token = request.cookies.get(get_settings().session_cookie_name)
    user = await service.get_current_user(token) if token else None
    if user is None:
        raise Problem(
            status=401,
            code="authentication_required",
            title="Authentification requise",
            detail="Connectez-vous pour accéder à cette ressource.",
        )
    return user


def _set_auth_cookies(response: Response, cookies: AuthCookies, settings: Settings) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        cookies.session_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    # Cookie CSRF lisible par le front (double-submit).
    response.set_cookie(
        settings.csrf_cookie_name,
        cookies.csrf_token,
        max_age=settings.session_ttl_seconds,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


@router.post("/auth/register", status_code=201, response_model=RegisterResponse)
async def register(
    payload: RegisterRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    repository: AuthRepository = Depends(get_auth_repository),
) -> JSONResponse:
    """Crée un compte et ouvre une session.

    Réponse neutre anti-énumération (🟡 Q31) : si l'e-mail existe déjà, la
    réponse est identique (201, mêmes cookies de forme) mais aucun compte
    n'est créé et le jeton de session posé est un leurre invalide.
    """
    outcome = await service.register(payload)
    # Journalisé même quand aucun compte n'a été créé (adresse déjà prise) :
    # une rafale d'inscriptions sur des adresses existantes est une tentative
    # d'énumération, et c'est le seul endroit où elle se voit. `created` le
    # distingue sans révéler quelle adresse était prise.
    await record(repository,
        outcome.user_id,
        REGISTERED,
        meta=build_meta(
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            trace_id=getattr(request.state, "trace_id", None),
            created=outcome.created,
        ),
    )
    response = JSONResponse(
        status_code=201,
        content={"message": "Compte créé. Un e-mail de confirmation vous a été envoyé."},
    )
    _set_auth_cookies(response, outcome.cookies, get_settings())
    return response


@router.post("/auth/login", status_code=204)
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    cache: Redis = Depends(get_redis_cache),
    repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    """Ouvre une session (cookie httpOnly + cookie CSRF). Rate-limité 5/min 🟡."""
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    limiter = FixedWindowRateLimiter(cache)
    try:
        result = await limiter.hit(
            "login",
            f"{payload.email.lower()}:{client_ip}",
            limit=settings.login_rate_limit,
            window_seconds=settings.login_rate_window_seconds,
        )
    except Exception:
        # Redis de cache injoignable : on LAISSE PASSER, comme le limiteur
        # global (D18), au lieu de rendre 500.
        #
        # Le compteur n'était pas gardé : une panne du Redis volatile — dont
        # D17 dit explicitement que la perte est acceptable — rendait la
        # CONNEXION ENTIÈREMENT IMPOSSIBLE. Mesuré en revue : 12 tentatives,
        # 12 × 500, pendant que le limiteur global partait en fail-open. Le
        # pire des deux mondes : plus de protection anti-flood, et plus
        # d'accès légitime.
        #
        # Laisser passer affaiblit la protection anti-force-brute le temps de
        # la panne — mais le mot de passe reste haché, l'audit reste écrit, et
        # une panne de cache ne doit pas devenir une panne d'authentification.
        signal_degradation("rate_limit_login")
        result = None

    if result is not None and not result.allowed:
        raise Problem(
            status=429,
            code="rate_limited",
            title="Trop de tentatives",
            detail="Trop de tentatives de connexion. Réessayez dans un instant.",
            headers={"Retry-After": str(result.retry_after)},
        )

    issue = await service.login(payload.email, payload.password)
    meta = build_meta(
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent"),
        trace_id=getattr(request.state, "trace_id", None),
    )
    if not issue.succeeded:
        # Écrit AVANT de lever : 09 §5.7 demande les échecs, et c'est
        # précisément l'événement qu'une attaque par force brute produit en
        # rafale. `user_id` est renseigné quand le compte existe — jamais
        # l'adresse tentée.
        await record(repository, issue.user_id, LOGIN_FAILED, meta=meta)
        raise Problem(
            status=401,
            code="invalid_credentials",
            title="Identifiants invalides",
            detail="E-mail ou mot de passe incorrect.",
        )
    await record(repository, issue.user_id, LOGIN_SUCCEEDED, meta=meta)
    response = Response(status_code=204)
    assert issue.cookies is not None
    _set_auth_cookies(response, issue.cookies, settings)
    return response


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    _user: User = Depends(require_current_user),
    service: AuthService = Depends(get_auth_service),
    repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    """Ferme la session courante et efface les cookies."""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await service.logout(token)
    await record(repository,
        _user.id,
        LOGGED_OUT,
        meta=build_meta(
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            trace_id=getattr(request.state, "trace_id", None),
        ),
    )
    response = Response(status_code=204)
    _clear_auth_cookies(response, settings)
    return response


@router.get("/me", response_model=MeResponse)
async def me(
    user: User = Depends(require_current_user),
    repository: AuthRepository = Depends(get_auth_repository),
) -> MeResponse:
    """Utilisateur courant + état d'onboarding RÉEL.

    Les trois indicateurs étaient des littéraux ``False`` : le tableau de bord
    invitait indéfiniment à importer un CV déjà importé.
    """
    cv_imported, profile_validated, preferences_set = await repository.onboarding_state(
        user.id
    )
    return MeResponse(
        id=user.id,
        email=user.email,
        locale=user.locale,
        onboarding=OnboardingState(
            cv_imported=cv_imported,
            profile_validated=profile_validated,
            preferences_set=preferences_set,
        ),
    )

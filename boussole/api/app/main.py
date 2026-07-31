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
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings, get_settings
from app.core.db import check_database
from app.core.degradation import signal_degradation
from app.core.observability import configure_observability
from app.core.problems import problem_response, register_problem_handlers
from app.core.ratelimit import FixedWindowRateLimiter
from app.core.redaction import redact_traceback, strip_query
from app.core.redis import check_redis, get_redis_cache, get_redis_persistent
from app.core.secrets import check_hardening_configuration, check_secrets_configuration
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
            # La pile porte le message de l'exception, et deux exceptions
            # courantes y mettent des données personnelles : le ``DETAIL:``
            # de PostgreSQL sur une collision d'adresse, le dictionnaire des
            # destinataires de ``SMTPRecipientsRefused``. Le journal local
            # part chez un agrégateur : c'est une conservation, pas un
            # affichage. Les cadres restent, les valeurs partent.
            payload["exc_info"] = redact_traceback(
                self.formatException(record.exc_info)
            )
        return json.dumps(payload, ensure_ascii=False)


class StripQueryStringFilter(logging.Filter):
    """Retire la chaîne de requête du journal d'accès d'uvicorn.

    Uvicorn tourne avec son journal d'accès actif (voir ``infra/Dockerfile.api``)
    et écrit le chemin BRUT ::

        GET /api/v1/jobs?q=teletravail+apres+burn-out HTTP/1.1
        GET /api/v1/privacy/exports/{id}/download?expires=…&sig=9f3ac1… HTTP/1.1

    La première ligne est exactement ce que le nettoyeur Sentry retire
    explicitement — « une information de santé, un handicap, une reconversion
    après un burn-out ». La barrière était posée du côté du sous-traitant
    tiers et absente du côté de nos propres journaux, qui sont pourtant
    conservés plus longtemps.

    La seconde est pire et n'est pas une question de vie privée : ``sig`` est
    la signature HMAC du lien de téléchargement d'export, valable sept jours.
    Qui lit le journal peut retélécharger l'archive RGPD complète d'une
    personne — toutes ses données, par construction.

    **Filtrer plutôt que couper.** ``--no-access-log`` supprimerait la fuite
    et le signal : le journal d'uvicorn porte l'adresse du pair, que le
    ``TraceMiddleware`` ne journalise pas. Et un journal désactivé par un
    drapeau de ligne de commande revient au premier changement d'image de
    base, sans qu'aucun test ne puisse le voir. Le filtre, lui, est posé dans
    le code et vérifié par la suite.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Gabarit d'uvicorn : ('%s - "%s %s HTTP/%s" %d', pair, methode,
        # chemin_brut, version, statut). Le chemin est le 3ᵉ argument.
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], strip_query(args[2]), *args[3:])
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Posé sur le LOGGER et non sur un gestionnaire : ``uvicorn.access`` a ses
    # propres gestionnaires et ``propagate = False``, donc il ne passe jamais
    # par la racine. Un filtre de logger s'applique quoi qu'il en soit.
    #
    # Uvicorn configure SON journal avant d'importer l'application (``Config.load``
    # appelle ``configure_logging`` puis ``import_from_string``) : le filtre
    # arrive donc après, ce qui est le bon ordre.
    acces = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, StripQueryStringFilter) for f in acces.filters):
        acces.addFilter(StripQueryStringFilter())


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
            # ERROR étouffé plutôt que WARNING par requête : une limitation
            # de débit qui s'efface doit réveiller quelqu'un (voir
            # ``app/core/degradation``), sans noyer l'alerte sous mille
            # copies d'elle-même.
            signal_degradation("rate_limit_global", detail=path)
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


#: Plafond de corps de requête, toutes routes confondues.
#:
#: Rien ne bornait la taille d'un corps — ni l'API, ni le proxy BFF. Mesuré en
#: revue, API en production, RSS de base 129 Mo :
#:
#:     8 requêtes concurrentes de 100 Mo sur /auth/login (non authentifié)
#:     → RSS max 1,73 Go, pic mémoire 1,94 Go
#:
#: Sur un conteneur limité à 512 Mo ou 1 Go, c'est un OOMKill déclenché par
#: une ligne de shell, sans compte. Le plafond de 10 Mo de l'import de CV
#: protégeait la base de données, pas l'infrastructure : il s'applique APRÈS
#: réception complète (mesuré : un envoi de 300 Mo rendait bien 413, mais
#: après avoir écrit 300 Mo sur le disque du conteneur).
#:
#: 12 Mo laisse la marge du plus gros usage légitime — un CV de 10 Mo plus
#: l'enveloppe multipart — et rien de plus.
MAX_REQUEST_BODY_BYTES = 12 * 1024 * 1024


#: Dépendances SANS lesquelles l'instance ne peut pas servir correctement.
#:
#: ``redis_cache`` n'en fait délibérément PAS partie. D17 pose que sa perte
#: est acceptable — il ne porte que du cache, de la limitation de débit et
#: des quotas, rien de durable. Il figurait pourtant dans cette liste, et une
#: readiness en échec retire l'instance du service : une panne de cache ne
#: dégradait pas le service, elle le COUPAIT, sur toutes les instances à la
#: fois. C'est très exactement la panne totale que le fail-open du limiteur
#: de connexion existe pour éviter — son commentaire dit « une panne de cache
#: ne doit pas devenir une panne d'authentification », et la sonde en faisait
#: une panne de tout.
DEPENDANCES_VITALES = ("database", "redis_persistent", "storage")


def readiness_verdict(checks: Mapping[str, bool]) -> tuple[bool, str, list[str]]:
    """(l'instance peut-elle servir, statut à publier, dépendances manquantes).

    Fonction pure, extraite de la route : la règle « ce qui coupe le service »
    est trop conséquente pour n'être vérifiable qu'à travers un serveur HTTP
    disposant d'une vraie base de données.
    """
    manquantes = [nom for nom in DEPENDANCES_VITALES if not checks.get(nom, False)]
    if manquantes:
        return False, "not_ready", manquantes
    return True, "ready" if checks.get("redis_cache", False) else "degraded", []


def _payload_too_large(request: Request | None) -> JSONResponse:
    return problem_response(
        request,
        status=413,
        code="payload_too_large",
        title="Requête trop volumineuse",
        detail=(
            "Le corps de la requête dépasse la limite de "
            f"{MAX_REQUEST_BODY_BYTES // (1024 * 1024)} Mo."
        ),
    )


class BodySizeLimitMiddleware:
    """Refuse un corps trop gros — sur l'en-tête ET sur le flux réel.

    **Ce que ça corrige.** La première version ne lisait que
    ``Content-Length``. Or cet en-tête est *absent* d'une requête en
    ``Transfer-Encoding: chunked``, et le middleware laissait alors passer un
    corps de taille quelconque. Mesuré, sans authentification ::

        Content-Length 12 Mo + 1 octet   → 413        (le cas testé)
        chunked, 36 Mo, sans Content-Length → 422     ← reçu en entier
                                           pic mémoire 108 Mo

    C'est très exactement l'épuisement mémoire que ce middleware existe pour
    empêcher, accessible par une option de la ligne de commande de curl. Le
    contrôle vérifiait la DÉCLARATION du client, jamais ce qu'il envoyait :
    il ne protégeait que d'un attaquant honnête.

    **Pourquoi ce n'est plus un ``BaseHTTPMiddleware``.** Celui-ci ne donne
    accès qu'à un ``Request`` déjà constitué ; borner un corps demande de
    s'interposer sur ``receive`` pour compter les morceaux À MESURE et couper
    avant que l'accumulation n'ait lieu. C'est une opération ASGI, pas une
    opération HTTP — d'où l'écriture directe en middleware ASGI.

    **Pourquoi le 413 est envoyé depuis ``receive`` et non par une exception.**
    Premier essai : lever depuis le lecteur borné et rattraper plus haut. Il
    rendait **400** et non 413 — FastAPI enveloppe *toute* exception survenue
    pendant la lecture du corps dans un ``HTTPException(400, "There was an
    error parsing the body")``, bien avant que l'exception ne remonte
    jusqu'ici. On répond donc soi-même, puis on rend un ``http.disconnect``
    pour débloquer l'application et on ignore ce qu'elle enverra ensuite :
    le client a déjà sa réponse, et une seconde réponse sur la même requête
    serait malformée.

    Le plafond déclaré reste vérifié en premier : quand le client annonce sa
    taille, on refuse sans lire un octet, et l'attaquant honnête n'occupe
    jamais de mémoire du tout.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        declaree = request.headers.get("content-length")
        if declaree is not None:
            try:
                taille = int(declaree)
            except ValueError:
                taille = 0
            if taille > MAX_REQUEST_BODY_BYTES:
                logger.warning(
                    "request_body_too_large path=%s declared=%s", request.url.path, taille
                )
                await _payload_too_large(request)(scope, receive, send)
                return

        recu = 0
        depasse = False

        async def receive_borne() -> Any:
            nonlocal recu, depasse
            if depasse:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                recu += len(message.get("body", b""))
                if recu > MAX_REQUEST_BODY_BYTES:
                    depasse = True
                    logger.warning(
                        "request_body_too_large path=%s streamed=%s",
                        request.url.path,
                        recu,
                    )
                    await _payload_too_large(request)(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def send_filtre(message: Any) -> None:
            # Le 413 est parti : ce que l'application produit ensuite (un 400
            # de FastAPI, un 500 de son gestionnaire d'erreurs) n'a plus de
            # destinataire et écraserait une réponse déjà émise.
            if not depasse:
                await send(message)

        try:
            await self.app(scope, receive_borne, send_filtre)
        except Exception:
            # Une application interrompue en pleine lecture a le droit de
            # lever ; la requête est déjà tranchée. Toute autre erreur suit
            # son chemin normal.
            if not depasse:
                raise


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
    configure_observability(settings)
    # Même parti pris pour les secrets : un défaut de développement en
    # production rendrait forgeables les liens d'export RGPD (D23).
    check_secrets_configuration(settings)
    check_hardening_configuration(settings)

    # Documentation interactive ET schéma : fermés dès que l'environnement est
    # durci, staging compris.
    #
    # Deux écarts mesurés en revue avant déploiement. (1) `docs_url` était
    # conditionnée à `is_production` alors que tous les autres garde-fous ont
    # migré vers `is_hardened` : Swagger UI était **entièrement exposé en
    # staging**. (2) `openapi_url` n'était conditionnée à rien — 73 Ko et 36
    # routes servis sans authentification en production, docstrings comprises.
    # Or ces docstrings sont franches sur ce qui n'est pas fini :
    # « scan antivirus hors périmètre », « le jeton de session posé est un
    # leurre invalide », « oracle de mot de passe pour quiconque a volé un
    # cookie ». C'est la carte des faiblesses connues, offerte à qui la
    # demande. Le contrat public vit dans `cv-job-matching/openapi.yaml`, qui
    # est fait pour être lu.
    expose_schema = not settings.is_hardened
    app = FastAPI(
        title="Boussole API",
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json" if expose_schema else None,
        docs_url=f"{settings.api_prefix}/docs" if expose_schema else None,
    )

    app.state.redis_cache_factory = redis_cache_factory or get_redis_cache
    app.state.redis_persistent_factory = redis_persistent_factory or get_redis_persistent

    register_problem_handlers(app)
    # add_middleware empile : CSRF d'abord (interne), puis rate limit,
    # en-têtes de sécurité, et trace en dernier (externe)
    # → le trace_id existe quand le CSRF répond 403.
    app.add_middleware(CsrfMiddleware)
    app.add_middleware(RateLimitMiddleware)
    # Avant le rate limit dans l'empilement (donc évalué APRÈS lui à l'appel) :
    # un corps énorme d'un client déjà limité n'a pas à être lu du tout.
    app.add_middleware(BodySizeLimitMiddleware)
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
            "storage": await _storage_ready(),
            "redis_cache": await check_redis(app.state.redis_cache_factory()),
        }
        pret, statut, manquantes = readiness_verdict(checks)
        if not checks["redis_cache"]:
            signal_degradation(
                "redis_cache", detail="limitation de débit et quotas inactifs"
            )
        if pret:
            return JSONResponse({"status": statut, "checks": checks})
        return problem_response(
            request,
            status=503,
            code="not_ready",
            title="Service indisponible",
            detail=f"Dépendances indisponibles : {manquantes}",
        )

    return app


app = create_app()

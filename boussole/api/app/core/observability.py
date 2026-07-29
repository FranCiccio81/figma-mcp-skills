"""Export d'erreurs — pour que les alertes atteignent quelqu'un.

**Ce que ça corrige.** ``SENTRY_DSN`` était déclarée dans la configuration et
**lue par personne**. Le système émet pourtant des alertes qui n'ont de sens
que si un humain les reçoit : ``purge_backlog_detected`` signale une purge
RGPD en retard, c'est-à-dire un engagement légal en train d'être rompu. Elle
partait sur stdout, au milieu du reste, et n'alertait rien.

**Le parti pris : bruyant plutôt qu'inerte.** Si un DSN est configuré et que
le paquet n'est pas installé, le démarrage **échoue**. Une observabilité
configurée qui ne remonte rien est pire que pas d'observabilité : on croit
être couvert. Même logique que les garde-fous de stockage et de secrets.

**Confidentialité — la partie difficile.** Ce produit manipule des CV, des
requêtes de recherche d'emploi et des adresses. Sentry est un sous-traitant
tiers : tout ce qui part est un transfert. La première version se contentait
de ``send_default_pii=False`` et d'un nettoyage de trois champs. Une revue a
montré, en exécutant le vrai SDK, que **l'adresse d'un utilisateur et le
sujet « demande de suppression de compte » partaient quand même** — par les
fils d'Ariane construits à partir des logs INFO, puis rattachés à n'importe
quelle erreur ultérieure du processus. Et que huit autres chemins portaient
des données : ``request.query_string`` (la requête de recherche d'emploi,
qui peut révéler une santé ou une reconversion), ``extra``, ``contexts``,
``tags``, ``user``, ``message``, ``logentry``, les fils d'Ariane.

D'où deux décisions :

1. **aucun fil d'Ariane issu des journaux** (``level=None``) — la source du
   défaut, coupée net. On perd le contexte des lignes précédant l'erreur ;
   c'est le prix, et il est bas devant une fuite d'adresse ;
2. **liste blanche, pas liste noire.** ``scrub_event`` ne conserve que des
   champs dont on sait qu'ils ne portent pas de données, et **retire tout le
   reste**. Énumérer ce qu'on retire est une course perdue : chaque nouveau
   champ du SDK, chaque nouveau ``extra`` ajouté par un développeur, passe à
   travers. Énumérer ce qu'on garde échoue, au pire, du côté d'un rapport
   d'erreur moins riche.

Le principe conservé : **garder la forme, jeter les valeurs**. Le gabarit
``"mail_envoi_echoue destinataire=%s"`` reste ; l'adresse, non.

**Traces distribuées** : pas exportées, et la variable
``OTEL_EXPORTER_OTLP_ENDPOINT`` a été **retirée** de la configuration plutôt
que laissée inerte — une variable qui ne fait rien induit en erreur plus
sûrement qu'une variable absente.
"""

import logging
from typing import Any

from app.core.config import Settings, get_settings
from app.core.redaction import redact_message, strip_query

logger = logging.getLogger(__name__)

#: Champs de l'événement conservés tels quels — aucun ne porte de donnée
#: utilisateur : identité de l'événement, niveau, horodatage, plateforme,
#: environnement, version, empreinte de regroupement.
_SAFE_TOP_LEVEL = frozenset(
    {
        "event_id", "timestamp", "platform", "level", "logger", "transaction",
        "environment", "release", "server_name", "sdk", "fingerprint", "type",
        "modules", "exception", "threads", "request", "contexts", "logentry",
    }
)

#: En-têtes conservés : ni identité, ni adresse, ni contenu.
_SAFE_HEADERS = frozenset({"content-type", "content-length", "accept", "user-agent"})

#: Contextes techniques du SDK, sans rapport avec l'utilisateur.
_SAFE_CONTEXTS = frozenset({"runtime", "os", "device", "trace"})


class ObservabilityConfigurationError(RuntimeError):
    """Observabilité demandée mais impossible à activer."""


def _scrub_request(requete: dict[str, Any]) -> dict[str, Any]:
    """Garde la route et la méthode ; jette tout ce qui peut porter du contenu.

    ``query_string`` est le piège : sur ``GET /jobs``, le paramètre ``q`` est
    la requête de recherche d'emploi de la personne. Elle peut porter une
    information de santé, un handicap, une reconversion après un burn-out.
    Elle ne sort pas.

    ``url`` est le même piège par une autre porte : selon l'intégration et la
    version du SDK, il arrive complet, chaîne de requête comprise. On ne
    dépend pas de la version installée — la requête est coupée ici.
    """
    entetes = requete.get("headers")
    propre: dict[str, Any] = {
        cle: valeur
        for cle, valeur in requete.items()
        if cle in {"method", "url"}
    }
    if "url" in propre:
        propre["url"] = strip_query(propre["url"])
    if isinstance(entetes, dict):
        propre["headers"] = {
            nom: valeur
            for nom, valeur in entetes.items()
            if nom.lower() in _SAFE_HEADERS
        }
    return propre


def _scrub_exception(exception: dict[str, Any]) -> dict[str, Any]:
    """Retire les variables locales, puis nettoie le message de l'exception.

    Les variables locales contiennent volontiers le texte en cours de
    traitement — un CV, une lettre, un profil entier.

    Le **message** était l'angle mort : la liste blanche gardait
    ``exception.values[].value`` entier, et deux exceptions courantes y
    mettent des données personnelles sans qu'on ait rien écrit.
    ``SMTPRecipientsRefused`` porte le dictionnaire des destinataires, donc
    l'adresse, à chaque rebond d'e-mail ; une violation d'unicité sur
    ``users.email`` porte l'adresse dans le ``DETAIL:`` de PostgreSQL et les
    paramètres liés dans le bloc ``[parameters:]`` de SQLAlchemy. Mesuré :
    les deux traversaient ``scrub_event`` intacts.
    """
    for valeur in exception.get("values") or []:
        for frame in (valeur.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
        if "value" in valeur:
            valeur["value"] = redact_message(valeur["value"])
    return exception


def _scrub_logentry(logentry: dict[str, Any]) -> dict[str, Any]:
    """Garde le GABARIT, jette les paramètres.

    ``"mail_envoi_echoue destinataire=%s"`` reste — c'est ce qui permet de
    diagnostiquer. ``"…destinataire=jean@exemple.fr"`` ne sort pas.

    Le gabarit lui-même passe par le nettoyage : rien n'empêche d'écrire un
    ``logger.error(f"echec pour {adresse}")``, et une barrière qui suppose la
    discipline de l'appelant n'en est pas une.
    """
    message = redact_message(logentry.get("message"))
    return {"message": message} if message else {}


def scrub_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any] | None:
    """Ne laisse passer que ce dont on sait qu'il ne porte pas de données.

    Liste BLANCHE délibérée. Appelé par Sentry avant chaque envoi, et testé
    sans Sentry installé : c'est une fonction pure sur un dictionnaire, et
    c'est le point — une barrière de confidentialité ne doit pas dépendre
    d'un paquet optionnel pour être vérifiable en CI.
    """
    propre: dict[str, Any] = {
        cle: valeur for cle, valeur in event.items() if cle in _SAFE_TOP_LEVEL
    }

    if isinstance(propre.get("request"), dict):
        propre["request"] = _scrub_request(propre["request"])
    if isinstance(propre.get("exception"), dict):
        propre["exception"] = _scrub_exception(propre["exception"])
    if isinstance(propre.get("logentry"), dict):
        propre["logentry"] = _scrub_logentry(propre["logentry"])
    if isinstance(propre.get("contexts"), dict):
        # Seuls les contextes techniques du SDK. Un contexte applicatif ajouté
        # par du code métier porterait des données par construction.
        propre["contexts"] = {
            nom: valeur
            for nom, valeur in propre["contexts"].items()
            if nom in _SAFE_CONTEXTS
        }
    return propre


def configure_observability(settings: Settings | None = None) -> bool:
    """Active l'export d'erreurs si un DSN est configuré.

    Retourne ``True`` si l'export est actif. Lève si un DSN est fourni mais
    inutilisable : mieux vaut ne pas démarrer que se croire observé.
    """
    conf = settings or get_settings()
    dsn = conf.sentry_dsn.strip()
    if not dsn:
        logger.info(
            "observabilite_desactivee — aucun SENTRY_DSN. Les alertes "
            "(purges RGPD en retard, erreurs) restent sur stdout uniquement."
        )
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError as exc:  # pragma: no cover - dépend de l'installation
        raise ObservabilityConfigurationError(
            "SENTRY_DSN est configuré mais le paquet 'sentry-sdk' n'est pas "
            "installé : les erreurs ne partiraient nulle part et vous vous "
            "croiriez couvert. Installer l'extra : pip install -e '.[observability]', "
            "ou retirer SENTRY_DSN."
        ) from exc

    sentry_sdk.init(
        dsn=dsn,
        environment=conf.env,
        # ⚠️ Ne JAMAIS activer : ce produit manipule des CV, et l'envoi
        # automatique d'identifiants utilisateur constituerait un transfert
        # de données personnelles non prévu au registre.
        send_default_pii=False,
        before_send=scrub_event,
        # Les fils d'Ariane du SDK (requêtes HTTP sortantes, SQL) ne sont pas
        # filtrés par ``before_send`` de façon fiable : on les coupe aussi.
        max_breadcrumbs=0,
        integrations=[
            # ``level=None`` : AUCUN fil d'Ariane construit à partir des
            # journaux. C'était la fuite : un `logger.info` mentionnant une
            # adresse devenait un fil d'Ariane, rattaché ensuite à n'importe
            # quelle erreur ultérieure du processus — et ``before_send`` ne
            # nettoyait pas cette partie de l'enveloppe.
            #
            # ``event_level=ERROR`` reste : c'est lui qui fait remonter les
            # alertes de conformité. Sans ça, `purge_backlog_detected`
            # resterait une ligne de stdout.
            LoggingIntegration(level=None, event_level=logging.ERROR)
        ],
    )
    logger.info("observabilite_active env=%s", conf.env)
    return True

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

**Confidentialité.** Ce produit manipule des CV. Un rapport d'erreur mal
réglé exfiltre des données personnelles vers un tiers — ce serait un
transfert non prévu au registre. D'où trois verrous : ``send_default_pii``
désactivé, corps de requête jamais joint, et un filtre qui retire les
en-têtes porteurs de session ou d'authentification avant l'envoi.

**Traces distribuées** : pas exportées, et la variable
``OTEL_EXPORTER_OTLP_ENDPOINT`` a été **retirée** de la configuration plutôt
que laissée inerte — une variable qui ne fait rien induit en erreur plus
sûrement qu'une variable absente.
"""

import logging
from typing import Any

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

#: En-têtes retirés de tout rapport : ils portent l'identité de session.
_SENSITIVE_HEADERS = frozenset(
    {"cookie", "set-cookie", "authorization", "x-csrf-token", "proxy-authorization"}
)


class ObservabilityConfigurationError(RuntimeError):
    """Observabilité demandée mais impossible à activer."""


def scrub_event(event: dict[str, Any], _hint: Any = None) -> dict[str, Any] | None:
    """Retire de l'événement tout ce qui peut porter des données personnelles.

    Appelé par Sentry avant chaque envoi. Testé sans Sentry installé : c'est
    une fonction pure sur un dictionnaire, et c'est délibéré — la barrière de
    confidentialité ne doit pas dépendre d'un paquet optionnel pour être
    vérifiable.
    """
    requete = event.get("request")
    if isinstance(requete, dict):
        # Le corps peut contenir un CV, une lettre, un profil entier.
        requete.pop("data", None)
        requete.pop("cookies", None)
        entetes = requete.get("headers")
        if isinstance(entetes, dict):
            requete["headers"] = {
                nom: valeur
                for nom, valeur in entetes.items()
                if nom.lower() not in _SENSITIVE_HEADERS
            }
    # Les variables locales d'une pile d'appels contiennent volontiers le
    # texte en cours de traitement.
    for exception in (event.get("exception") or {}).get("values") or []:
        for frame in (exception.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    return event


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
        integrations=[
            # C'est CETTE intégration qui fait remonter les alertes de
            # conformité : un logger.error devient un événement. Sans elle,
            # `purge_backlog_detected` resterait une ligne de stdout.
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        ],
    )
    logger.info("observabilite_active env=%s", conf.env)
    return True

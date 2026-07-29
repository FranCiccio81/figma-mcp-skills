"""Garde-fou des secrets de configuration (D23).

Les valeurs par défaut de ``Settings`` sont des valeurs de DÉVELOPPEMENT,
publiques par construction puisqu'elles sont dans le dépôt. Rien n'empêchait
jusqu'ici un déploiement de démarrer avec elles — et la plus sensible,
``PRIVACY_SIGNING_KEY``, signe à elle seule les liens de téléchargement des
archives d'export RGPD : quiconque connaît la valeur par défaut peut forger
un lien valide vers le dump personnel complet de n'importe quel compte
(l'``export_id`` est un UUID, mais il fuit dans les journaux, l'historique du
navigateur, un ticket de support).

Même parti pris que ``check_storage_configuration`` : hors développement, on
REFUSE DE DÉMARRER plutôt que de servir avec un secret public. Un service qui
ne démarre pas se voit ; une signature forgeable, non.
"""

import logging

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class SecretConfigurationError(RuntimeError):
    """Un secret de production a gardé sa valeur de développement."""


#: Secrets dont la valeur par défaut est publique (présente dans le dépôt).
#: Chaque entrée : attribut de ``Settings``, variable d'environnement, et ce
#: qui est compromis si la valeur par défaut survit en production.
_DEV_DEFAULTS: tuple[tuple[str, str, str], ...] = (
    (
        "privacy_signing_key",
        "PRIVACY_SIGNING_KEY",
        "les liens signés d'export RGPD deviennent forgeables : accès au dump "
        "personnel complet de n'importe quel compte",
    ),
    (
        "s3_secret_key",
        "S3_SECRET_KEY",
        "les identifiants du stockage objet (CV, archives d'export) sont publics",
    ),
)


def check_secrets_configuration(settings: Settings | None = None) -> None:
    """Refuse les secrets par défaut hors développement.

    Appelée au démarrage de l'API et au niveau module des workers Celery,
    comme :func:`app.core.storage.check_storage_configuration`. En
    développement, se contente d'un avertissement — c'est le mode où ces
    valeurs sont légitimes.
    """
    settings = settings if settings is not None else get_settings()
    defaults = _default_values()

    faibles = [
        (attribut, variable, risque)
        for attribut, variable, risque in _DEV_DEFAULTS
        if getattr(settings, attribut, None) == defaults.get(attribut)
    ]
    if not faibles:
        return

    if not getattr(settings, "is_hardened", False):
        logger.info(
            "secrets_de_developpement_actifs variables=%s",
            ",".join(variable for _, variable, _ in faibles),
        )
        return

    env = getattr(settings, "env", "production")
    detail = " ; ".join(
        f"{variable} (défaut du dépôt — {risque})" for _, variable, risque in faibles
    )
    raise SecretConfigurationError(
        f"Secret(s) de développement en {env} : {detail}. "
        "Fournir des valeurs issues du vault (D23) avant de démarrer."
    )


def _default_values() -> dict[str, object]:
    """Valeurs par défaut déclarées dans ``Settings`` (source de vérité).

    Lues sur le modèle plutôt que recopiées : une rotation du défaut de
    développement ne doit pas silencieusement désarmer ce contrôle.
    """
    return {
        name: field.default
        for name, field in Settings.model_fields.items()
        if field.default is not None
    }


def check_hardening_configuration(settings: Settings | None = None) -> None:
    """Refuse de démarrer sur une configuration qui expose des données.

    Deux réglages, deux fuites mesurées en revue :

    - **``SMTP_STARTTLS`` à faux avec authentification** : le mot de passe du
      compte d'envoi et l'adresse de chaque destinataire transitent en clair.
      Qui a ce mot de passe peut écrire au nom du service — à une base
      d'utilisateurs qui attendent précisément des messages sur la suppression
      de leur compte ;
    - **``DEBUG`` à vrai** : ``create_async_engine(echo=debug)`` journalise
      chaque requête AVEC ses paramètres liés. Contenus de profil, adresses,
      extraits de CV se retrouvent dans les journaux, et de là dans tout
      export d'erreurs.

    Même parti pris que les autres garde-fous : un service qui ne démarre pas
    se voit ; une fuite, non.
    """
    conf = settings or get_settings()
    if not conf.is_hardened:
        return

    manquements: list[str] = []
    if conf.smtp_host.strip() and conf.smtp_username and not conf.smtp_starttls:
        manquements.append(
            "SMTP_STARTTLS=false avec authentification : le mot de passe SMTP "
            "et l'adresse de chaque destinataire transitent EN CLAIR"
        )
    if conf.debug:
        manquements.append(
            "DEBUG=true : SQLAlchemy journalise chaque requête avec ses "
            "paramètres liés (profils, adresses, extraits de CV)"
        )
    if manquements:
        raise SecretConfigurationError(
            f"Configuration refusée en ENV={conf.env} :\n  - "
            + "\n  - ".join(manquements)
        )

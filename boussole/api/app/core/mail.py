"""Envoi d'e-mail transactionnel — SMTP, sans dépendance supplémentaire.

**Ce que ça corrige.** Aucun e-mail n'était envoyé. ``mailpit`` figurait dans
le compose de développement et personne ne lui écrivait ; trois envois
contractuels étaient des TODO, dont la **confirmation de suppression de
compte**, qui est la seule trace qu'un utilisateur reçoit d'une demande aux
conséquences irréversibles.

**Pourquoi SMTP et pas une API de fournisseur.** Le choix du fournisseur est
une question ouverte (Q15) et suppose un arbitrage — hébergement UE, contrat
de sous-traitance, registre des transferts. SMTP est le dénominateur commun :
tous les fournisseurs l'exposent, mailpit aussi, et rien n'est préempté. Le
jour où un fournisseur est retenu, seul le transport change.

**Un échec d'envoi ne casse jamais l'action.** Une suppression de compte
enregistrée dont l'e-mail n'est pas parti reste une suppression valide ; lever
ici ferait échouer un ``DELETE`` que l'utilisateur a le droit d'obtenir. Les
échecs sont journalisés en ERROR — donc remontés par l'export d'erreurs.

**Confidentialité.** Aucun contenu de CV, de lettre ou de profil ne transite
par ces messages, et ce n'est pas une politique mais une conséquence de la
forme : les gabarits sont des chaînes fixes avec au plus une date.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Message:
    """Un message sortant. Volontairement pauvre : texte simple, un
    destinataire, pas de pièce jointe — rien qui puisse porter un CV."""

    to: str
    subject: str
    body: str


class Mailer(Protocol):
    """Contrat d'envoi — substituable en test comme en production."""

    def send(self, message: Message) -> bool:
        """Envoie ; retourne ``False`` sur échec, ne lève jamais."""
        ...


class NullMailer:
    """Ne fait rien, et le DIT. Défaut quand aucun hôte SMTP n'est configuré.

    C'est le comportement historique — aucun e-mail — mais rendu visible : la
    ligne de journal permet de constater qu'un message aurait dû partir, ce
    qui n'était pas le cas avec un TODO en commentaire.
    """

    def send(self, message: Message) -> bool:
        logger.info(
            "mail_non_envoye_aucun_smtp destinataire=%s sujet=%r", message.to, message.subject
        )
        return False


class SmtpMailer:
    """Envoi SMTP synchrone et borné."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: Message) -> bool:
        conf = self._settings
        courriel = EmailMessage()
        courriel["From"] = conf.mail_from
        courriel["To"] = message.to
        courriel["Subject"] = message.subject
        courriel.set_content(message.body)
        try:
            with smtplib.SMTP(
                conf.smtp_host, conf.smtp_port, timeout=conf.smtp_timeout_seconds
            ) as serveur:
                if conf.smtp_starttls:
                    serveur.starttls()
                if conf.smtp_username:
                    serveur.login(conf.smtp_username, conf.smtp_password)
                serveur.send_message(courriel)
        except Exception:
            # ERROR, donc remonté par l'export d'erreurs : un e-mail
            # contractuel qui ne part pas doit se voir. Mais on ne lève pas —
            # une suppression de compte enregistrée dont l'e-mail échoue reste
            # une suppression valide, et l'utilisateur a droit à son 204.
            logger.exception(
                "mail_envoi_echoue destinataire=%s sujet=%r", message.to, message.subject
            )
            return False
        logger.info("mail_envoye destinataire=%s sujet=%r", message.to, message.subject)
        return True


def get_mailer(settings: Settings | None = None) -> Mailer:
    """Expéditeur effectif — SMTP si un hôte est configuré, sinon aucun."""
    conf = settings or get_settings()
    return SmtpMailer(conf) if conf.smtp_host.strip() else NullMailer()

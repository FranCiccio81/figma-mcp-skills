"""Logique métier du module privacy : suppression de compte (F-Q).

L'export asynchrone vit dans ``export_builder.py`` (exécuté par le worker) ;
la purge planifiée dans ``purge_runner.py``.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.mail import Mailer, Message
from app.core.security import SessionStore, verify_password, waste_time_like_verify
from app.modules.auth.models import User
from app.modules.privacy.repository import DeletionRecord, PrivacyRepository

logger = logging.getLogger("boussole.privacy")

#: Fenêtre de purge RGPD (D09) : purge physique ≤ 30 jours après soft delete.
PURGE_DELAY_DAYS = 30


@dataclass(frozen=True, slots=True)
class AccountDeletionOutcome:
    deletion: DeletionRecord


#: Gabarit de la confirmation de suppression. Volontairement pauvre : aucune
#: donnée du profil, du CV ou des candidatures n'y figure — la seule variable
#: est la date de purge. Ce n'est pas une règle qu'on s'impose, c'est une
#: propriété de la forme du message.
DELETION_SUBJECT = "Votre demande de suppression de compte Boussole"
DELETION_BODY = """Bonjour,

Nous avons bien enregistré votre demande de suppression de compte.

Votre compte est dès à présent inaccessible et toutes vos sessions ont été
fermées. La suppression définitive de vos données interviendra le {date}.

Si vous n'êtes pas à l'origine de cette demande, contactez-nous sans attendre.

L'équipe Boussole
"""


class PrivacyService:
    def __init__(
        self,
        repository: PrivacyRepository,
        sessions: SessionStore,
        mailer: Mailer | None = None,
    ) -> None:
        self._repository = repository
        self._sessions = sessions
        # Sans expéditeur, aucun e-mail : c'est le comportement d'avant, et il
        # reste acceptable. Ce qui ne l'était pas, c'est qu'il soit invisible.
        self._mailer = mailer

    async def delete_account(self, user: User, password: str) -> AccountDeletionOutcome | None:
        """Soft delete immédiat + planification de purge (AC-Q-1).

        Retourne ``None`` si le mot de passe est invalide (→ 401, aucun effet).
        """
        if user.password_hash is None:
            # Compte OAuth (post-MVP) : pas de mot de passe local — refus.
            #
            # TODO(post-MVP, à ne PAS implémenter ici) : un compte sans mot de
            # passe local est aujourd'hui IMPOSSIBLE à supprimer par son
            # titulaire — la seule voie de sortie est le support. C'est un
            # écart RGPD (art. 17) qui devra être fermé EN MÊME TEMPS que
            # l'ouverture de l'authentification OAuth : réauthentification par
            # le fournisseur d'identité (ou par e-mail de confirmation signé)
            # en remplacement de la vérification de mot de passe. Tant qu'aucun
            # compte OAuth n'existe, la branche est morte — mais elle ne doit
            # pas être oubliée le jour où OAuth est activé.
            waste_time_like_verify(password)
            return None
        if not verify_password(password, user.password_hash):
            return None

        now = datetime.now(UTC)
        deletion = await self._repository.execute_account_deletion(
            user.id, now=now, purge_after=now + timedelta(days=PURGE_DELAY_DAYS)
        )
        # Révocation globale des sessions : le compte est inaccessible
        # immédiatement (RM-Q-1) — les dépendances d'auth rejettent par
        # ailleurs tout compte deleted_at non nul (repository auth).
        await self._sessions.delete_all_for_user(user.id)
        self._send_deletion_confirmation(user, deletion)
        return AccountDeletionOutcome(deletion=deletion)

    def _send_deletion_confirmation(self, user: User, deletion: object) -> None:
        """Confirme la demande — la seule trace que l'utilisateur en reçoit.

        L'envoi ne peut pas faire échouer la suppression : elle est déjà
        enregistrée et l'utilisateur y a droit. Un échec est journalisé en
        ERROR par l'expéditeur, donc remonté par l'export d'erreurs.
        """
        if self._mailer is None:
            return
        echeance = getattr(deletion, "purge_after", None)
        try:
            self._mailer.send(
                Message(
                    to=user.email,
                    subject=DELETION_SUBJECT,
                    body=DELETION_BODY.format(
                        date=echeance.strftime("%d/%m/%Y") if echeance else "sous 30 jours"
                    ),
                )
            )
        except Exception:
            # Le contrat de ``Mailer`` dit « ne lève jamais » ; on ne s'y fie
            # pas pour autant. Le droit à l'effacement ne peut pas dépendre du
            # bon comportement d'un expéditeur.
            logger.exception("account_deletion_email_failed")

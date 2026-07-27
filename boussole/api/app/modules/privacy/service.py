"""Logique métier du module privacy : suppression de compte (F-Q).

L'export asynchrone vit dans ``export_builder.py`` (exécuté par le worker) ;
la purge planifiée dans ``purge_runner.py``.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.security import SessionStore, verify_password, waste_time_like_verify
from app.modules.auth.models import User
from app.modules.privacy.repository import DeletionRecord, PrivacyRepository

logger = logging.getLogger("boussole.privacy")

#: Fenêtre de purge RGPD (D09) : purge physique ≤ 30 jours après soft delete.
PURGE_DELAY_DAYS = 30


@dataclass(frozen=True, slots=True)
class AccountDeletionOutcome:
    deletion: DeletionRecord


class PrivacyService:
    def __init__(self, repository: PrivacyRepository, sessions: SessionStore) -> None:
        self._repository = repository
        self._sessions = sessions

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
        # TODO(M5, 🟡) : e-mail de confirmation de suppression (date de purge)
        # via le service e-mail — journalisé pour ne pas être un TODO silencieux.
        logger.info(
            "account_deletion_email_todo",
            extra={"detail": "e-mail de confirmation de suppression à envoyer (TODO M5 🟡)"},
        )
        return AccountDeletionOutcome(deletion=deletion)

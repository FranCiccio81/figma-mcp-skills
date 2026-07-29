"""Confirmation de suppression de compte — la seule trace que l'utilisateur a.

Avant : un TODO et une ligne de journal. Une demande aux conséquences
irréversibles ne laissait aucune trace côté utilisateur, et une demande faite
depuis une session volée passait donc totalement inaperçue de son titulaire.

Trois propriétés, dans l'ordre d'importance :

1. l'e-mail part, avec la date de purge — c'est l'information utile ;
2. un échec d'envoi ne fait **jamais** échouer la suppression : elle est
   enregistrée et l'utilisateur y a droit ;
3. le message ne contient **aucune donnée personnelle** au-delà de l'adresse
   du destinataire — ni profil, ni CV, ni candidature.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.mail import Message, NullMailer
from app.modules.auth.models import User
from app.modules.privacy.repository import DeletionRecord
from app.modules.privacy.service import DELETION_SUBJECT, PrivacyService
from tests.unit.privacy.conftest import InMemoryPrivacyRepository


class MailerEspion:
    def __init__(self, *, echoue: bool = False) -> None:
        self.envoyes: list[Message] = []
        self._echoue = echoue

    def send(self, message: Message) -> bool:
        self.envoyes.append(message)
        return not self._echoue


class MailerQuiLeve:
    """Un expéditeur défaillant qui LÈVE — le pire cas pour l'appelant."""

    def send(self, message: Message) -> bool:
        raise RuntimeError("serveur SMTP injoignable")


class SessionsEspion:
    def __init__(self) -> None:
        self.revoques: list[uuid.UUID] = []

    async def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        self.revoques.append(user_id)


@pytest.fixture
def utilisateur() -> User:
    from app.core.security import hash_password

    user = User(id=uuid.uuid4(), email="camille@example.eu")
    user.password_hash = hash_password("un mot de passe très long")
    user.deleted_at = None
    return user


@pytest.fixture
def depot(utilisateur: User) -> InMemoryPrivacyRepository:
    depot = InMemoryPrivacyRepository()

    async def _execute(user_id, *, now, purge_after):
        record = DeletionRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            requested_at=now,
            purge_after=purge_after,
            status="pending",
        )
        depot.deletion_requests[record.id] = record
        return record

    depot.execute_account_deletion = _execute  # type: ignore[method-assign]
    return depot


class TestLEmailPart:
    async def test_un_message_est_envoye_au_titulaire(
        self, depot, utilisateur: User
    ) -> None:
        mailer = MailerEspion()
        service = PrivacyService(depot, SessionsEspion(), mailer)

        await service.delete_account(utilisateur, "un mot de passe très long")

        assert len(mailer.envoyes) == 1
        assert mailer.envoyes[0].to == utilisateur.email
        assert mailer.envoyes[0].subject == DELETION_SUBJECT

    async def test_le_message_porte_la_date_de_purge(
        self, depot, utilisateur: User
    ) -> None:
        """C'est l'information utile : à partir de quand est-ce irréversible."""
        mailer = MailerEspion()
        service = PrivacyService(depot, SessionsEspion(), mailer)

        await service.delete_account(utilisateur, "un mot de passe très long")

        attendue = (datetime.now(UTC) + timedelta(days=30)).strftime("%d/%m/%Y")
        assert attendue in mailer.envoyes[0].body

    async def test_aucun_envoi_sur_mot_de_passe_invalide(
        self, depot, utilisateur: User
    ) -> None:
        """Pas de suppression, pas d'e-mail — sinon on offrirait un moyen
        d'envoyer des messages à une adresse sans en connaître le mot de passe."""
        mailer = MailerEspion()
        service = PrivacyService(depot, SessionsEspion(), mailer)

        resultat = await service.delete_account(utilisateur, "mauvais mot de passe")

        assert resultat is None
        assert mailer.envoyes == []


class TestUnEchecDenvoiNeCassePasLaSuppression:
    async def test_envoi_en_echec_la_suppression_reste_enregistree(
        self, depot, utilisateur: User
    ) -> None:
        service = PrivacyService(depot, SessionsEspion(), MailerEspion(echoue=True))
        resultat = await service.delete_account(utilisateur, "un mot de passe très long")
        assert resultat is not None

    async def test_sans_expediteur_la_suppression_fonctionne(
        self, depot, utilisateur: User
    ) -> None:
        """Comportement d'avant — aucun e-mail — mais il reste valide."""
        service = PrivacyService(depot, SessionsEspion(), None)
        assert await service.delete_account(utilisateur, "un mot de passe très long")

    async def test_un_expediteur_qui_LEVE_ne_casse_pas_la_suppression(
        self, depot, utilisateur: User
    ) -> None:
        """Le contrat dit « ne lève jamais » ; on ne s'y fie pas.

        Le droit à l'effacement ne peut pas dépendre du bon comportement d'un
        expéditeur — a fortiori d'un futur fournisseur tiers (Q15).
        """
        service = PrivacyService(depot, SessionsEspion(), MailerQuiLeve())
        assert await service.delete_account(utilisateur, "un mot de passe très long")

    async def test_lexpediteur_par_defaut_ne_leve_jamais(self) -> None:
        assert NullMailer().send(Message(to="a@b.eu", subject="s", body="b")) is False


class TestAucuneDonneePersonnelleDansLeMessage:
    async def test_le_corps_ne_contient_que_la_date(
        self, depot, utilisateur: User
    ) -> None:
        """Ce n'est pas une règle qu'on s'impose, c'est une propriété de la
        forme : le gabarit est une chaîne fixe avec une seule variable."""
        mailer = MailerEspion()
        service = PrivacyService(depot, SessionsEspion(), mailer)

        await service.delete_account(utilisateur, "un mot de passe très long")
        corps = mailer.envoyes[0].body

        # Ni l'adresse, ni un identifiant technique ne figurent dans le corps.
        assert utilisateur.email not in corps
        assert str(utilisateur.id) not in corps

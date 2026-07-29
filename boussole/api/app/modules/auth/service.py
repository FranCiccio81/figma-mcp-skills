"""Logique métier du module auth : register, login, logout, utilisateur courant."""

import logging
import uuid
from dataclasses import dataclass

from app.core.security import (
    SessionStore,
    generate_csrf_token,
    generate_session_token,
    hash_password,
    verify_password,
    waste_time_like_verify,
)
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import RegisterRequest

logger = logging.getLogger("boussole.auth")


@dataclass(frozen=True, slots=True)
class AuthCookies:
    """Jetons à poser en cookies (session httpOnly + CSRF lisible)."""

    session_token: str
    csrf_token: str


@dataclass(frozen=True, slots=True)
class RegisterOutcome:
    created: bool
    cookies: AuthCookies
    #: Identifiant du compte créé — ``None`` quand l'adresse était déjà prise
    #: (réponse neutre). Permet de rattacher la ligne d'audit sans écrire
    #: l'adresse tentée.
    user_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class LoginOutcome:
    """Issue d'une tentative de connexion.

    ``user_id`` est renseigné dès que le COMPTE existe — y compris sur un
    échec de mot de passe. C'est ce qui permet de compter les échecs par
    compte sans jamais écrire l'adresse tentée dans le journal.
    """

    cookies: AuthCookies | None
    user_id: uuid.UUID | None

    @property
    def succeeded(self) -> bool:
        return self.cookies is not None


class AuthService:
    def __init__(self, repository: AuthRepository, sessions: SessionStore) -> None:
        self._repository = repository
        self._sessions = sessions

    async def register(self, data: RegisterRequest) -> RegisterOutcome:
        """Crée un compte — réponse neutre anti-énumération (🟡 Q31).

        Si l'e-mail existe déjà : aucun compte n'est créé, la réponse HTTP est
        strictement identique (201 + cookies de même forme, jeton de session
        « leurre » jamais stocké — donc invalide) et un e-mail « un compte
        existe déjà » doit être envoyé au titulaire.
        """
        # ``email_taken`` et non ``get_user_by_email`` : l'index unique de
        # ``users.email`` ignore ``deleted_at``, donc l'adresse d'un compte
        # supprimé reste occupée jusqu'à sa purge (J+30).
        if await self._repository.email_taken(data.email):
            # TODO(M2, E2) : envoyer l'e-mail « un compte existe déjà » via le
            # service e-mail (mailpit en dev). Journalisé pour ne pas être un
            # TODO silencieux — aucune information ne fuit vers le client.
            logger.info(
                "register_existing_email",
                extra={"detail": "e-mail « compte existant » à envoyer (TODO M2)"},
            )
            return RegisterOutcome(
                created=False,
                cookies=AuthCookies(
                    session_token=generate_session_token(),  # leurre, non stocké
                    csrf_token=generate_csrf_token(),
                ),
            )

        user = await self._repository.create_user(
            email=data.email,
            password_hash=hash_password(data.password),
            locale=data.locale,
            consents=[
                ("terms", data.accepted_terms_version),
                ("privacy", data.accepted_privacy_version),
            ],
        )
        token = await self._sessions.create(user.id)
        return RegisterOutcome(
            created=True,
            cookies=AuthCookies(session_token=token, csrf_token=generate_csrf_token()),
            user_id=user.id,
        )

    async def login(self, email: str, password: str) -> LoginOutcome:
        """Ouvre une session ; issue détaillée pour le journal d'audit.

        Rend un :class:`LoginOutcome` et non ``AuthCookies | None`` : le
        journal de sécurité (09 §5.7) doit pouvoir rattacher un échec au
        COMPTE visé quand il existe, sans que l'appelant ait à refaire la
        recherche — ni à écrire l'adresse tentée, ce qu'on ne veut pas.

        Le temps de réponse reste constant : ``waste_time_like_verify``
        conserve le coût d'un hachage quand le compte n'existe pas.
        """
        user = await self._repository.get_user_by_email(email)
        if user is None or user.password_hash is None:
            waste_time_like_verify(password)
            return LoginOutcome(cookies=None, user_id=None)
        if not verify_password(password, user.password_hash):
            return LoginOutcome(cookies=None, user_id=user.id)
        token = await self._sessions.create(user.id)
        return LoginOutcome(
            cookies=AuthCookies(session_token=token, csrf_token=generate_csrf_token()),
            user_id=user.id,
        )

    async def logout(self, session_token: str) -> None:
        await self._sessions.delete(session_token)

    async def get_current_user(self, session_token: str) -> User | None:
        user_id = await self._sessions.get_user_id(session_token)
        if user_id is None:
            return None
        return await self._repository.get_user_by_id(user_id)

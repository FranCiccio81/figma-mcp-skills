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
        existing = await self._repository.get_user_by_email(data.email)
        if existing is not None:
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
        )

    async def login(self, email: str, password: str) -> AuthCookies | None:
        """Ouvre une session ; None si identifiants invalides (temps constant)."""
        user = await self._repository.get_user_by_email(email)
        if user is None or user.password_hash is None:
            waste_time_like_verify(password)
            return None
        if not verify_password(password, user.password_hash):
            return None
        token = await self._sessions.create(user.id)
        return AuthCookies(session_token=token, csrf_token=generate_csrf_token())

    async def logout(self, session_token: str) -> None:
        await self._sessions.delete(session_token)

    async def get_current_user(self, session_token: str) -> User | None:
        user_id = await self._sessions.get_user_id(session_token)
        if user_id is None:
            return None
        return await self._repository.get_user_by_id(user_id)

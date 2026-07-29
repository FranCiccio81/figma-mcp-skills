"""Accès aux données du module auth.

Le protocole ``AuthRepository`` permet de substituer une implémentation en
mémoire dans les tests unitaires (pas de PostgreSQL requis).
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.modules.auth.models import Consent, User


class AuthRepository(Protocol):
    async def get_user_by_email(self, email: str) -> User | None: ...

    async def email_taken(self, email: str) -> bool: ...

    async def onboarding_state(self, user_id: uuid.UUID) -> tuple[bool, bool, bool]: ...

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        locale: str,
        consents: Sequence[tuple[str, str]],  # (kind, version)
    ) -> User: ...


class SqlAlchemyAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def email_taken(self, email: str) -> bool:
        """Adresse occupée, y compris par un compte SUPPRIMÉ mais non purgé.

        ``users.email`` porte un index unique qui ne connaît pas
        ``deleted_at`` : l'adresse reste réservée pendant les 30 jours de
        rétention. ``get_user_by_email`` filtre les comptes supprimés — c'est
        juste pour la connexion, faux pour l'inscription.

        Sans cette distinction, se réinscrire après avoir supprimé son compte
        rendait **500** (``UniqueViolationError``) pendant un mois, sans la
        moindre explication. Et le 500 était un oracle d'énumération à
        l'envers : il distinguait « adresse jamais vue » (201 neutre) de
        « adresse d'un compte récemment supprimé » (500), exactement ce que
        la réponse neutre existe pour empêcher.
        """
        stmt = select(User.id).where(User.email == email).limit(1)
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def onboarding_state(self, user_id: uuid.UUID) -> tuple[bool, bool, bool]:
        """(CV importé, profil validé, préférences définies) — une seule requête.

        Les trois indicateurs étaient des littéraux ``False``, avec pour
        commentaire « M1 : tant que les modules profiles/preferences (M2+) ne
        fournissent pas leurs services ». Ils les fournissent depuis longtemps.

        Conséquence visible : la carte « Mon CV » du tableau de bord affichait
        à vie « Aucun CV importé pour le moment » et proposait « Importer mon
        CV » au lieu de « Réimporter », quel que soit le nombre de CV
        réellement importés. Le composant note pourtant qu'il lit ``GET /me``
        « jamais d'état local seul » — la source de vérité choisie était
        justement celle qui mentait.

        Trois ``EXISTS`` dans une requête plutôt que trois allers-retours :
        cette route est appelée à chaque chargement de page.
        """
        resultat = await self._session.execute(
            text(
                "SELECT "
                " EXISTS (SELECT 1 FROM cv_documents WHERE user_id = :uid),"
                " EXISTS (SELECT 1 FROM profiles WHERE user_id = :uid"
                "         AND status = 'validated'),"
                " EXISTS (SELECT 1 FROM preferences WHERE user_id = :uid)"
            ),
            {"uid": user_id},
        )
        cv, profil, preferences = resultat.one()
        return bool(cv), bool(profil), bool(preferences)

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        locale: str,
        consents: Sequence[tuple[str, str]],
    ) -> User:
        user = User(email=email, password_hash=password_hash, locale=locale)
        self._session.add(user)
        await self._session.flush()
        for kind, version in consents:
            self._session.add(Consent(user_id=user.id, kind=kind, version=version))
        await self._session.commit()
        return user


async def get_auth_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AuthRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyAuthRepository(session)

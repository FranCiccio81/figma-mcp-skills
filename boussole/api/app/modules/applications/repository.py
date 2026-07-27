"""Accès aux données du module applications (F-P).

Pagination : curseur opaque base64 encodant le tuple keyset
``(created_at, id)`` en ordre décroissant — jamais d'OFFSET (§1 des
contrats). Le protocole ``ApplicationsRepository`` permet de substituer une
implémentation en mémoire dans les tests unitaires (pas de PostgreSQL requis,
patterns du module jobs).

Le repository ne porte aucune règle métier : le service construit et mute les
instances ``Application`` / ``ApplicationEvent`` ; le repository persiste.

Libellés de l'offre interne (``JobRef``) : ``ApplicationOut`` expose
``job_title``/``job_company`` (champs additifs, 12 §1) pour que le front
puisse nommer l'« offre liée » — et pour que l'aria-label des contrôles
diffère d'une candidature à l'autre. Ces libellés vivent dans
``job_postings`` : ils sont résolus par :meth:`job_refs` en UNE requête pour
TOUTE la page (anti N+1), jamais offre par offre. ``Application`` ne porte
volontairement pas de ``relationship`` vers ``JobPosting`` : sous
``AsyncSession`` un chargement paresseux involontaire lève ``MissingGreenlet``
— la résolution explicite ci-dessous rend le coût en requêtes lisible.
"""

import base64
import binascii
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from fastapi import Depends
from sqlalchemy import delete, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db_session
from app.modules.applications.models import Application, ApplicationEvent
from app.modules.jobs.models import JobPosting

# ---------------------------------------------------------------- curseur


class InvalidCursorError(ValueError):
    """Curseur opaque illisible ou corrompu."""


@dataclass(frozen=True, slots=True)
class ApplicationCursor:
    """Tuple keyset décodé : (created_at, id) du dernier élément servi."""

    created_at: datetime
    last_id: uuid.UUID


def encode_cursor(created_at: datetime, last_id: uuid.UUID) -> str:
    """Encode le tuple keyset en curseur opaque base64 URL-safe."""
    payload = json.dumps({"v": created_at.isoformat(), "id": str(last_id)})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(raw: str) -> ApplicationCursor:
    """Décode et valide un curseur opaque.

    Toute anomalie (base64 invalide, JSON corrompu, clés manquantes, valeur
    intypable) lève ``InvalidCursorError`` — convertie en 422 problem+json
    par le service.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        created_at = datetime.fromisoformat(payload["v"])
        last_id = uuid.UUID(payload["id"])
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, KeyError,
            TypeError, ValueError) as exc:
        raise InvalidCursorError("curseur illisible") from exc
    return ApplicationCursor(created_at=created_at, last_id=last_id)


# ---------------------------------------------------------------- libellés offre


@dataclass(frozen=True, slots=True)
class JobRef:
    """Libellés de l'offre interne référencée par une candidature.

    Projection minimale de ``job_postings`` (``title``, ``company_name``) —
    l'entité complète n'est jamais chargée pour un simple affichage.
    """

    title: str
    company: str


# ---------------------------------------------------------------- protocole


class ApplicationsRepository(Protocol):
    async def list_for_user(
        self,
        *,
        user_id: uuid.UUID,
        status: str | None,
        limit: int,
        cursor: ApplicationCursor | None,
    ) -> list[Application]:
        """Jusqu'à ``limit + 1`` candidatures (détection de page suivante),
        événements chargés, tri ``(created_at, id)`` décroissant."""
        ...

    async def get_for_user(
        self, application_id: uuid.UUID, user_id: uuid.UUID
    ) -> Application | None:
        """Candidature de CET utilisateur (scoping : autrui → None → 404),
        événements chargés en ordre chronologique."""
        ...

    async def get_job_ref(self, job_posting_id: uuid.UUID) -> JobRef | None:
        """Libellés de l'offre, ``None`` si elle n'existe pas.

        Sert à la fois le contrôle d'existence de la création (Q26 : le suivi
        reste autorisé sur une offre expirée — seule l'existence compte) et
        les champs ``job_title``/``job_company`` de la réponse : UNE requête
        pour les deux besoins."""
        ...

    async def job_refs(
        self, job_posting_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, JobRef]:
        """Libellés de PLUSIEURS offres en UNE requête (anti N+1).

        Les identifiants absents de ``job_postings`` (offre purgée depuis, la
        FK est ``ON DELETE SET NULL`` mais la course existe) sont simplement
        absents du dictionnaire → ``job_title``/``job_company`` à ``None``."""
        ...

    async def create(self, application: Application) -> Application:
        """Persiste une candidature construite par le service."""
        ...

    async def save(self, application: Application) -> None:
        """Persiste les mutations du service (PATCH, transition de statut)."""
        ...

    async def add_event(self, application: Application, event: ApplicationEvent) -> None:
        """Ajoute un événement d'historique (append-only, RM-P-3) et persiste
        les mutations associées de la candidature (status, applied_at,
        updated_at)."""
        ...

    async def delete(self, application: Application) -> None:
        """Supprime la candidature ET ses événements (données utilisateur)."""
        ...

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        """Purge RGPD (D21) : supprime toutes les candidatures de l'utilisateur."""
        ...

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[Application]:
        """Toutes les candidatures (événements chargés) — export RGPD (D21)."""
        ...


# ---------------------------------------------------------------- SQLAlchemy


class SqlAlchemyApplicationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self,
        *,
        user_id: uuid.UUID,
        status: str | None,
        limit: int,
        cursor: ApplicationCursor | None,
    ) -> list[Application]:
        conditions = [Application.user_id == user_id]
        if status is not None:
            # Sert l'index idx_applications_user (user_id, status).
            conditions.append(Application.status == status)
        if cursor is not None:
            # Keyset descendant : strictement « après » le dernier élément servi.
            conditions.append(
                tuple_(Application.created_at, Application.id)
                < (cursor.created_at, cursor.last_id)
            )
        stmt = (
            select(Application)
            .where(*conditions)
            .order_by(Application.created_at.desc(), Application.id.desc())
            .limit(limit + 1)
            .options(selectinload(Application.events))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_for_user(
        self, application_id: uuid.UUID, user_id: uuid.UUID
    ) -> Application | None:
        stmt = (
            select(Application)
            .where(Application.id == application_id, Application.user_id == user_id)
            .options(selectinload(Application.events))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_job_ref(self, job_posting_id: uuid.UUID) -> JobRef | None:
        stmt = select(JobPosting.title, JobPosting.company_name).where(
            JobPosting.id == job_posting_id
        )
        row = (await self._session.execute(stmt)).first()
        return None if row is None else JobRef(title=row[0], company=row[1])

    async def job_refs(
        self, job_posting_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, JobRef]:
        # dict.fromkeys : dédoublonne en conservant l'ordre (plusieurs
        # candidatures peuvent viser la même offre).
        wanted = list(dict.fromkeys(job_posting_ids))
        if not wanted:
            return {}  # aucune candidature interne dans la page : zéro requête
        stmt = select(JobPosting.id, JobPosting.title, JobPosting.company_name).where(
            JobPosting.id.in_(wanted)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: JobRef(title=row[1], company=row[2]) for row in rows}

    async def create(self, application: Application) -> Application:
        self._session.add(application)
        await self._session.commit()
        return application

    async def save(self, application: Application) -> None:
        self._session.add(application)
        await self._session.commit()

    async def add_event(self, application: Application, event: ApplicationEvent) -> None:
        application.events.append(event)
        self._session.add(application)
        await self._session.commit()

    async def delete(self, application: Application) -> None:
        # Les événements suivent : cascade ORM + FK ON DELETE CASCADE.
        await self._session.delete(application)
        await self._session.commit()

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        application_ids = select(Application.id).where(
            Application.user_id == user_id
        ).scalar_subquery()
        # Événements supprimés explicitement (la FK ON DELETE CASCADE du
        # schéma couvre déjà le cas — ceinture et bretelles, pattern matching).
        await self._session.execute(
            delete(ApplicationEvent).where(ApplicationEvent.application_id.in_(application_ids))
        )
        await self._session.execute(delete(Application).where(Application.user_id == user_id))
        await self._session.commit()

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[Application]:
        stmt = (
            select(Application)
            .where(Application.user_id == user_id)
            .order_by(Application.created_at, Application.id)
            .options(selectinload(Application.events))
        )
        return list((await self._session.execute(stmt)).scalars().all())


async def get_applications_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationsRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyApplicationsRepository(session)

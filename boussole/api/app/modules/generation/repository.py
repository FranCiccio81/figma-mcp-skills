"""Accès aux données du module generation.

Le protocole ``GenerationRepository`` couvre : CRUD scopé utilisateur des
``generated_documents`` (autrui → 404, anti-énumération), liste keyset
(created_at DESC, id DESC) avec filtres contractuels, chargement d'une offre
pour les préconditions et le prompt (lecture seule du module jobs, D01), et
les interfaces purge/export (D21). Les tests unitaires substituent une
implémentation en mémoire.
"""

import uuid
from datetime import datetime
from typing import Protocol

from fastapi import Depends
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db_session
from app.modules.generation.models import GeneratedDocument
from app.modules.jobs.models import JobPosting


class GenerationRepository(Protocol):
    async def add(self, document: GeneratedDocument) -> None:
        """Persiste un nouveau document (commit inclus)."""
        ...

    async def get_for_user(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocument | None:
        """Document scopé utilisateur — None (→ 404) pour autrui."""
        ...

    async def get_by_id(self, document_id: uuid.UUID) -> GeneratedDocument | None:
        """Accès interne (worker) — non scopé."""
        ...

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        doc_type: str | None,
        status: str | None,
        job_id: uuid.UUID | None,
        application_id: uuid.UUID | None = None,
        before: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[GeneratedDocument]:
        """Page keyset (created_at DESC, id DESC) ; ``status`` est l'état
        CONTRACTUEL (pending/draft/validated/exported/failed).

        ``application_id`` : même patron que ``job_id`` — égalité stricte sur
        la colonne, cumulée au scope utilisateur (index
        ``generated_documents(user_id, created_at)``)."""
        ...

    async def get_job(self, job_id: uuid.UUID) -> JobPosting | None:
        """Offre avec compétences chargées (préconditions + prompt)."""
        ...

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        """Purge RGPD (D21)."""
        ...

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[GeneratedDocument]:
        """Export RGPD (D21) — tous les documents, sans pagination."""
        ...

    async def commit(self) -> None:
        """Persiste les mutations faites sur les documents chargés."""
        ...


def _status_conditions(status: str) -> list[object]:
    """Filtre SQL de l'état contractuel (voir ``models.api_status``)."""
    if status == "pending":
        return [GeneratedDocument.processing_status.in_(("pending", "processing"))]
    if status == "failed":
        return [GeneratedDocument.processing_status == "failed"]
    return [
        GeneratedDocument.processing_status == "ready",
        GeneratedDocument.status == status,
    ]


class SqlAlchemyGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: GeneratedDocument) -> None:
        self._session.add(document)
        await self._session.commit()

    async def get_for_user(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocument | None:
        stmt = select(GeneratedDocument).where(
            GeneratedDocument.id == document_id,
            GeneratedDocument.user_id == user_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, document_id: uuid.UUID) -> GeneratedDocument | None:
        return await self._session.get(GeneratedDocument, document_id)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        doc_type: str | None,
        status: str | None,
        job_id: uuid.UUID | None,
        application_id: uuid.UUID | None = None,
        before: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[GeneratedDocument]:
        conditions: list[object] = [GeneratedDocument.user_id == user_id]
        if doc_type is not None:
            conditions.append(GeneratedDocument.doc_type == doc_type)
        if status is not None:
            conditions.extend(_status_conditions(status))
        if job_id is not None:
            conditions.append(GeneratedDocument.job_posting_id == job_id)
        if application_id is not None:
            conditions.append(GeneratedDocument.application_id == application_id)
        if before is not None:
            before_at, before_id = before
            conditions.append(
                or_(
                    GeneratedDocument.created_at < before_at,
                    and_(
                        GeneratedDocument.created_at == before_at,
                        GeneratedDocument.id < before_id,
                    ),
                )
            )
        stmt = (
            select(GeneratedDocument)
            .where(*conditions)  # type: ignore[arg-type]
            .order_by(GeneratedDocument.created_at.desc(), GeneratedDocument.id.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_job(self, job_id: uuid.UUID) -> JobPosting | None:
        stmt = (
            select(JobPosting)
            .where(JobPosting.id == job_id)
            .options(selectinload(JobPosting.skills))
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(GeneratedDocument).where(GeneratedDocument.user_id == user_id)
        )
        await self._session.commit()

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[GeneratedDocument]:
        stmt = (
            select(GeneratedDocument)
            .where(GeneratedDocument.user_id == user_id)
            .order_by(GeneratedDocument.created_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def commit(self) -> None:
        await self._session.commit()


async def get_generation_repository(
    session: AsyncSession = Depends(get_db_session),
) -> GenerationRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyGenerationRepository(session)

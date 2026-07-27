"""Accès aux données du sous-package CV (cv_documents + extraction_runs).

Protocole étroit, même pattern que ``profiles/repository.py`` : le service
mute les instances ORM chargées et ``commit()`` persiste. L'implémentation
en mémoire des tests manipule les mêmes instances détachées.
"""

import uuid
from typing import Protocol

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.modules.profiles.cv.models import CvDocument, ExtractionRun


class CvDocumentsRepository(Protocol):
    async def add(self, document: CvDocument) -> CvDocument:
        """Persiste un nouveau document (statut ``uploaded``)."""
        ...

    async def get_for_user(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> CvDocument | None:
        """Document de l'utilisateur — None si absent OU appartenant à autrui
        (anti-énumération : 404 côté routes, 12 §5)."""
        ...

    async def list_for_user(self, user_id: uuid.UUID) -> list[CvDocument]:
        """Tous les documents de l'utilisateur (purge / export RGPD, D21)."""
        ...

    async def latest_success_run(self, document_id: uuid.UUID) -> ExtractionRun | None:
        """Dernier run d'extraction en succès (sortie validée stockée)."""
        ...

    async def runs_for_document(self, document_id: uuid.UUID) -> list[ExtractionRun]:
        """Tous les runs du document (purge des sorties stockées)."""
        ...

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        """Supprime documents + runs de l'utilisateur (cascade SQL)."""
        ...

    async def commit(self) -> None:
        """Persiste les mutations faites sur les instances chargées."""
        ...


class SqlAlchemyCvDocumentsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: CvDocument) -> CvDocument:
        self._session.add(document)
        await self._session.commit()
        return document

    async def get_for_user(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> CvDocument | None:
        stmt = select(CvDocument).where(
            CvDocument.id == document_id, CvDocument.user_id == user_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[CvDocument]:
        stmt = (
            select(CvDocument)
            .where(CvDocument.user_id == user_id)
            .order_by(CvDocument.created_at)
        )
        return list((await self._session.execute(stmt)).scalars())

    async def latest_success_run(self, document_id: uuid.UUID) -> ExtractionRun | None:
        stmt = (
            select(ExtractionRun)
            .where(
                ExtractionRun.cv_document_id == document_id,
                ExtractionRun.status == "success",
            )
            .order_by(ExtractionRun.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def runs_for_document(self, document_id: uuid.UUID) -> list[ExtractionRun]:
        stmt = select(ExtractionRun).where(ExtractionRun.cv_document_id == document_id)
        return list((await self._session.execute(stmt)).scalars())

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        # Les runs cascadent via la FK ON DELETE CASCADE de la migration ;
        # suppression explicite pour rester correct hors PostgreSQL.
        doc_ids = select(CvDocument.id).where(CvDocument.user_id == user_id)
        await self._session.execute(
            delete(ExtractionRun).where(ExtractionRun.cv_document_id.in_(doc_ids))
        )
        await self._session.execute(delete(CvDocument).where(CvDocument.user_id == user_id))
        await self._session.commit()

    async def commit(self) -> None:
        await self._session.commit()


async def get_cv_documents_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CvDocumentsRepository:
    """Dépendance FastAPI — substituée par un repo en mémoire dans les tests."""
    return SqlAlchemyCvDocumentsRepository(session)

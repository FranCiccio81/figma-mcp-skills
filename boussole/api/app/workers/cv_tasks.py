"""Tâche Celery du parsing CV — ``ai.parse_cv`` (file ``ai``, F-B, D12/D16).

Chaîne (F-B nominal 3-5) :

1. ``cv_documents.status`` → ``parsing`` ;
2. extraction du texte : pypdf (couche texte PDF) ou python-docx —
   PDF illisible/corrompu → ``unreadable`` ; PDF sans couche texte →
   ``image_only_pdf`` (OCR hors MVP 🟡 Q1) ; DOCX vide/corrompu →
   ``unreadable`` ; texte stocké par clé objet (``raw_text_key``, RM-B-7) ;
3. appel :func:`app.ai.tasks.extract_cv.extract_cv` (FakeProvider par
   défaut 🟡 — provider réel M5) : validation stricte + ancrage des
   evidences, 1 retry, sinon ``extraction_failed`` (RM-B-3) ;
4. ``extraction_runs`` enregistré (prompt_version, model, status, sortie
   JSON validée stockée par clé objet) ; statut final ``parsed``/``failed``.

Boucle d'événements : UNE seule coroutine par tâche via ``asyncio.run``,
sur un moteur dédié ``NullPool`` (:func:`app.core.db.create_worker_engine`)
disposé en fin de coroutine — jamais le moteur global poolé.
"""

import asyncio
import io
import logging
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai.providers.base import LLMProvider
from app.ai.providers.fake import FakeProvider
from app.ai.tasks.extract_cv import (
    DEFAULT_MODEL,
    PROMPT_VERSION,
    CvExtraction,
    CvExtractionError,
    extract_cv,
)
from app.core.db import create_worker_engine
from app.core.storage import ObjectStorage, get_object_storage
from app.modules.profiles.cv.models import CvDocument, ExtractionRun
from app.modules.profiles.cv.service import DOCX_MIME, PDF_MIME
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run[T](coro: Awaitable[T]) -> T:
    """Pont sync Celery → code async SQLAlchemy (UNE coroutine par tâche)."""
    return asyncio.run(coro)  # type: ignore[arg-type]


def _get_provider() -> LLMProvider:
    """Provider LLM de la tâche — FakeProvider 🟡 (Anthropic + fallback M5, D08)."""
    return FakeProvider()


# ------------------------------------------------------------ extraction texte


def extract_pdf_text(data: bytes) -> str:
    """Couche texte d'un PDF via pypdf — lève sur document corrompu."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_docx_text(data: bytes) -> str:
    """Texte d'un DOCX via python-docx (paragraphes + tableaux)."""
    from docx import Document

    document = Document(io.BytesIO(data))
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def extract_text(data: bytes, mime_type: str) -> tuple[str | None, str | None]:
    """``(texte, None)`` ou ``(None, error_code)`` — fonction pure.

    Codes (enum openapi) : ``image_only_pdf`` (PDF lisible sans couche
    texte), ``unreadable`` (corrompu ou vide), ``unsupported_format``
    (défensif — normalement rejeté en amont par le router, 415).
    """
    if mime_type == PDF_MIME:
        try:
            text = extract_pdf_text(data)
        except Exception:
            return None, "unreadable"
        if not text.strip():
            return None, "image_only_pdf"  # scan sans couche texte (F-B alt. 1)
        return text, None
    if mime_type == DOCX_MIME:
        try:
            text = extract_docx_text(data)
        except Exception:
            return None, "unreadable"
        if not text.strip():
            return None, "unreadable"
        return text, None
    return None, "unsupported_format"


# ------------------------------------------------------------ orchestration


@dataclass(frozen=True, slots=True)
class ParseOutcome:
    """Résultat pur du parsing d'un document (avant persistance)."""

    document_status: str  # 'parsed' | 'failed'
    error_code: str | None
    run_status: str | None  # 'success' | 'schema_error' | 'failed' | None (pas d'appel LLM)
    raw_text: str | None
    extraction: CvExtraction | None


def run_cv_extraction(data: bytes, mime_type: str, provider: LLMProvider) -> ParseOutcome:
    """Extraction texte + appel ``extract_cv`` — fonction pure (testable sans DB)."""
    text, error_code = extract_text(data, mime_type)
    if text is None:
        return ParseOutcome(
            document_status="failed",
            error_code=error_code,
            run_status=None,  # aucun appel LLM : pas de run (R7)
            raw_text=None,
            extraction=None,
        )
    try:
        extraction = extract_cv(text, provider)
    except CvExtractionError:
        # RM-B-3 : retry + échec propre déjà joués dans extract_cv.
        return ParseOutcome(
            document_status="failed",
            error_code="extraction_failed",
            run_status="schema_error",
            raw_text=text,
            extraction=None,
        )
    except Exception:
        logger.exception("cv_extraction_provider_error")
        return ParseOutcome(
            document_status="failed",
            error_code="extraction_failed",
            run_status="failed",
            raw_text=text,
            extraction=None,
        )
    return ParseOutcome(
        document_status="parsed",
        error_code=None,
        run_status="success",
        raw_text=text,
        extraction=extraction,
    )


async def _parse_cv_cycle(
    cv_document_id: str,
    *,
    storage: ObjectStorage | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Cycle complet dans UNE coroutine : moteur NullPool dédié, disposé en fin."""
    storage = storage if storage is not None else get_object_storage()
    provider = provider if provider is not None else _get_provider()
    engine = create_worker_engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            document = await session.get(CvDocument, uuid.UUID(cv_document_id))
            if document is None:
                logger.warning("parse_cv_document_missing id=%s", cv_document_id)
                return {"status": "missing"}
            document.status = "parsing"
            document.error_code = None
            await session.commit()  # statut visible pendant le parsing (polling front)

            data = storage.get(document.file_key)
            outcome = run_cv_extraction(data, document.mime_type, provider)

            if outcome.raw_text is not None:
                raw_text_key = f"cv/{document.user_id}/{document.id}/raw_text.txt"
                storage.put(raw_text_key, outcome.raw_text.encode("utf-8"))
                document.raw_text_key = raw_text_key

            if outcome.run_status is not None:
                run = ExtractionRun(
                    id=uuid.uuid4(),
                    cv_document_id=document.id,
                    prompt_version=PROMPT_VERSION,
                    model=DEFAULT_MODEL,
                    status=outcome.run_status,
                    output_key=None,
                )
                if outcome.extraction is not None:
                    output_key = (
                        f"cv/{document.user_id}/{document.id}/extraction/{run.id}.json"
                    )
                    storage.put(
                        output_key, outcome.extraction.model_dump_json().encode("utf-8")
                    )
                    run.output_key = output_key
                session.add(run)

            document.status = outcome.document_status
            document.error_code = outcome.error_code
            await session.commit()
            return {"status": document.status, "error_code": document.error_code}
    finally:
        await engine.dispose()


@celery_app.task(
    name="ai.parse_cv",
    bind=True,
    max_retries=3,  # retries infra (DB/stockage indisponible) — D08 🟡
    autoretry_for=(Exception,),
    retry_backoff=10,
    retry_backoff_max=300,
    retry_jitter=True,
)
def parse_cv(self: Any, cv_document_id: str) -> dict[str, Any]:
    """Parsing asynchrone d'un CV importé (F-B) — file ``ai``.

    Les échecs MÉTIER (illisible, PDF image, extraction invalide) sont
    persistés sur la ressource (``status='failed'`` + ``error_code``) et ne
    déclenchent PAS de retry Celery ; seuls les incidents d'infrastructure
    (exceptions) sont rejoués avec backoff exponentiel.
    """
    report = _run(_parse_cv_cycle(cv_document_id))
    logger.info("parse_cv_done id=%s report=%s", cv_document_id, report)
    return report

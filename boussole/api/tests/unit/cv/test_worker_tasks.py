"""Tests de la tâche worker ``ai.parse_cv`` (F-B nominal 3-5).

Parties pures : extraction de texte pypdf/python-docx sur fixtures bytes
minimales, mapping des ``error_code`` (``image_only_pdf``, ``unreadable``),
issue ``ParseOutcome``. Cycle DB : session/engine factices (aucune base) —
statuts persistés, ``extraction_runs`` enregistré, sortie stockée, moteur
disposé.
"""

import json
import uuid
from typing import Any

from app.ai.providers.fake import FakeProvider
from app.ai.tasks.extract_cv import DEFAULT_MODEL, PROMPT_VERSION
from app.modules.profiles.cv.models import CvDocument, ExtractionRun
from app.modules.profiles.cv.service import DOCX_MIME, PDF_MIME
from app.workers import cv_tasks
from tests.unit.cv.conftest import (
    InMemoryObjectStorage,
    make_docx_bytes,
    make_image_only_pdf_bytes,
    make_pdf_bytes,
)

#: Le texte par défaut de ``make_pdf_bytes`` sert de citation d'ancrage :
#: la citation doit être exacte, ≥ MIN_QUOTE_CHARS et porter le libellé.
PDF_TEXT = "Developpeuse Python chez Acme depuis 2020"

VALID_OUTPUT: dict[str, Any] = {
    "headline": None,
    "summary": None,
    "experiences": [],
    "educations": [],
    "skills": [
        {"label": "Python", "confidence": 0.8, "evidence": {"quote": PDF_TEXT}}
    ],
    "languages": [],
    "warnings": [],
}


class TestTextExtraction:
    def test_pdf_text_layer_is_extracted(self) -> None:
        text = cv_tasks.extract_pdf_text(make_pdf_bytes("Developpeuse Python chez Acme"))
        assert "Developpeuse Python chez Acme" in text

    def test_docx_paragraphs_are_extracted(self) -> None:
        text = cv_tasks.extract_docx_text(make_docx_bytes(["Ligne 1", "Ligne 2"]))
        assert "Ligne 1" in text
        assert "Ligne 2" in text

    def test_image_only_pdf_maps_to_image_only_pdf(self) -> None:
        text, error = cv_tasks.extract_text(make_image_only_pdf_bytes(), PDF_MIME)
        assert text is None
        assert error == "image_only_pdf"

    def test_corrupt_pdf_maps_to_unreadable(self) -> None:
        text, error = cv_tasks.extract_text(b"%PDF-1.4 pas un vrai pdf", PDF_MIME)
        assert text is None
        assert error == "unreadable"

    def test_empty_docx_maps_to_unreadable(self) -> None:
        text, error = cv_tasks.extract_text(make_docx_bytes([]), DOCX_MIME)
        assert text is None
        assert error == "unreadable"

    def test_corrupt_docx_maps_to_unreadable(self) -> None:
        text, error = cv_tasks.extract_text(b"PK\x03\x04 pas un vrai zip", DOCX_MIME)
        assert text is None
        assert error == "unreadable"

    def test_unknown_mime_is_defensive_unsupported_format(self) -> None:
        text, error = cv_tasks.extract_text(b"...", "text/plain")
        assert text is None
        assert error == "unsupported_format"


class TestRunCvExtraction:
    def test_success_returns_parsed_with_extraction_and_raw_text(self) -> None:
        provider = FakeProvider(canned={"extract_cv": VALID_OUTPUT})
        outcome = cv_tasks.run_cv_extraction(
            make_pdf_bytes(PDF_TEXT), PDF_MIME, provider
        )
        assert outcome.document_status == "parsed"
        assert outcome.error_code is None
        assert outcome.run_status == "success"
        assert outcome.raw_text is not None and "Python" in outcome.raw_text
        assert outcome.extraction is not None
        assert outcome.extraction.skills[0].label == "Python"

    def test_image_only_pdf_fails_without_llm_call(self) -> None:
        provider = FakeProvider(canned={"extract_cv": VALID_OUTPUT})
        outcome = cv_tasks.run_cv_extraction(
            make_image_only_pdf_bytes(), PDF_MIME, provider
        )
        assert outcome.document_status == "failed"
        assert outcome.error_code == "image_only_pdf"
        assert outcome.run_status is None  # aucun appel LLM (R7)
        assert provider.calls == []

    def test_invalid_llm_output_maps_to_extraction_failed(self) -> None:
        provider = FakeProvider(canned={"extract_cv": {"garbage": True}})
        outcome = cv_tasks.run_cv_extraction(make_pdf_bytes(), PDF_MIME, provider)
        assert outcome.document_status == "failed"
        assert outcome.error_code == "extraction_failed"
        assert outcome.run_status == "schema_error"
        assert outcome.extraction is None
        assert len(provider.calls) == 2  # 1 appel + 1 retry (RM-B-3)

    def test_provider_crash_maps_to_extraction_failed(self) -> None:
        class ExplodingProvider:
            def complete_json(self, task: str, prompt: str, schema: Any) -> dict[str, Any]:
                raise ConnectionError("provider down")

        outcome = cv_tasks.run_cv_extraction(
            make_pdf_bytes(), PDF_MIME, ExplodingProvider()
        )
        assert outcome.document_status == "failed"
        assert outcome.error_code == "extraction_failed"
        assert outcome.run_status == "failed"


# ------------------------------------------------------------ cycle DB factice


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeSession:
    """Session minimale : ``get`` par identité, ``add``/``commit`` comptés."""

    def __init__(self, document: CvDocument | None) -> None:
        self._document = document
        self.added: list[Any] = []
        self.commits = 0

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get(self, model: type, key: uuid.UUID) -> CvDocument | None:
        assert model is CvDocument
        if self._document is not None and self._document.id == key:
            return self._document
        return None

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


class TestParseCvCycle:
    def _patch_db(self, monkeypatch: Any, session: FakeSession) -> FakeEngine:
        engine = FakeEngine()
        monkeypatch.setattr(cv_tasks, "create_worker_engine", lambda: engine)
        monkeypatch.setattr(
            cv_tasks, "async_sessionmaker", lambda eng, **kw: lambda: session
        )
        return engine

    async def test_successful_parse_persists_run_and_output(
        self, monkeypatch: Any, storage: InMemoryObjectStorage
    ) -> None:
        document = CvDocument(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            file_key="cv/u/d/original.pdf",
            filename="cv.pdf",
            mime_type=PDF_MIME,
            size_bytes=1000,
            status="uploaded",
        )
        storage.put(document.file_key, make_pdf_bytes(PDF_TEXT))
        session = FakeSession(document)
        engine = self._patch_db(monkeypatch, session)

        report = await cv_tasks._parse_cv_cycle(
            str(document.id),
            storage=storage,
            provider=FakeProvider(canned={"extract_cv": VALID_OUTPUT}),
        )

        assert report == {"status": "parsed", "error_code": None}
        assert document.status == "parsed"
        assert document.raw_text_key is not None
        assert "Python" in storage.objects[document.raw_text_key].decode()
        (run,) = [obj for obj in session.added if isinstance(obj, ExtractionRun)]
        assert run.status == "success"
        assert run.prompt_version == PROMPT_VERSION
        assert run.model == DEFAULT_MODEL
        assert run.output_key is not None
        stored = json.loads(storage.objects[run.output_key])
        assert stored["skills"][0]["label"] == "Python"
        assert session.commits == 2  # statut parsing puis résultat final
        assert engine.disposed  # moteur NullPool disposé en fin de coroutine

    async def test_image_only_pdf_persists_failed_without_run(
        self, monkeypatch: Any, storage: InMemoryObjectStorage
    ) -> None:
        document = CvDocument(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            file_key="cv/u/d/original.pdf",
            filename="scan.pdf",
            mime_type=PDF_MIME,
            size_bytes=1000,
            status="uploaded",
        )
        storage.put(document.file_key, make_image_only_pdf_bytes())
        session = FakeSession(document)
        engine = self._patch_db(monkeypatch, session)

        report = await cv_tasks._parse_cv_cycle(
            str(document.id), storage=storage, provider=FakeProvider()
        )

        assert report == {"status": "failed", "error_code": "image_only_pdf"}
        assert document.status == "failed"
        assert document.error_code == "image_only_pdf"
        assert document.raw_text_key is None
        assert session.added == []  # aucun run : pas d'appel LLM
        assert engine.disposed

    async def test_missing_document_is_a_logged_noop(
        self, monkeypatch: Any, storage: InMemoryObjectStorage
    ) -> None:
        session = FakeSession(None)
        engine = self._patch_db(monkeypatch, session)
        report = await cv_tasks._parse_cv_cycle(
            str(uuid.uuid4()), storage=storage, provider=FakeProvider()
        )
        assert report == {"status": "missing"}
        assert engine.disposed

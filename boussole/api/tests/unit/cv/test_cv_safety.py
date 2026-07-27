"""Tests des garde-fous de sûreté du parsing CV (bombe de décompression).

Scénario reproduit (revue) : un DOCX VALIDE de quelques centaines de Ko se
décompresse en centaines de Mo — le worker part en OOM et, avec
``acks_late`` + retries, boucle. Le garde-fou doit refuser l'archive AVANT
toute décompression (``python-docx`` n'est jamais appelé), sans exception :
le document part en ``failed`` / ``unreadable`` (erreur permanente).
"""

import io
import zipfile
from typing import Any

import pytest

from app.ai.providers.fake import FakeProvider
from app.modules.profiles.cv.safety import (
    MAX_COMPRESSION_RATIO,
    MAX_PDF_PAGES,
    MAX_UNCOMPRESSED_BYTES,
    TEXT_LIMIT,
    UnsafeDocumentError,
    assert_archive_safe,
    assert_pdf_pages_safe,
    truncate_text,
)
from app.modules.profiles.cv.service import DOCX_MIME, PDF_MIME, sniff_mime
from app.workers import cv_tasks
from tests.unit.cv.conftest import make_docx_bytes, make_pdf_bytes

#: Charge décompressée de la bombe (8 Mo de texte répété → quelques Ko
#: compressés, ratio ≫ 100:1). Suffisant pour le contrôle, sans faire
#: exploser la mémoire du test.
BOMB_PAYLOAD_BYTES = 8 * 1024 * 1024


def make_zip_bomb_docx_bytes() -> bytes:
    """DOCX structurellement VALIDE (``word/document.xml``) mais hostile."""
    payload = "A" * BOMB_PAYLOAD_BYTES
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", payload)
    return buffer.getvalue()


class TestAssertArchiveSafe:
    def test_regular_docx_is_accepted(self) -> None:
        assert_archive_safe(make_docx_bytes(["Ingénieure QA chez Beta"]))

    def test_decompression_bomb_is_refused_on_ratio(self) -> None:
        data = make_zip_bomb_docx_bytes()
        ratio = BOMB_PAYLOAD_BYTES / len(data)
        assert ratio > MAX_COMPRESSION_RATIO, "la fixture doit être une vraie bombe"
        with pytest.raises(UnsafeDocumentError) as excinfo:
            assert_archive_safe(data)
        assert "ratio" in excinfo.value.reason

    def test_total_uncompressed_size_is_capped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Règle de TAILLE isolée de la règle de ratio (50 Mo 🟡 en production).
        monkeypatch.setattr(
            "app.modules.profiles.cv.safety.MAX_UNCOMPRESSED_BYTES", 100
        )
        monkeypatch.setattr(
            "app.modules.profiles.cv.safety.MAX_COMPRESSION_RATIO", 1e9
        )
        with pytest.raises(UnsafeDocumentError) as excinfo:
            assert_archive_safe(make_docx_bytes(["Ingénieure QA chez Beta"]))
        assert "décompressés" in excinfo.value.reason

    def test_corrupt_archive_is_refused(self) -> None:
        with pytest.raises(UnsafeDocumentError):
            assert_archive_safe(b"PK\x03\x04 pas un vrai zip")

    def test_documented_thresholds(self) -> None:
        assert MAX_UNCOMPRESSED_BYTES == 50 * 1024 * 1024  # 🟡
        assert MAX_COMPRESSION_RATIO == 100.0  # 🟡


class TestPdfBounds:
    def test_page_count_is_capped(self) -> None:
        assert_pdf_pages_safe(MAX_PDF_PAGES)
        with pytest.raises(UnsafeDocumentError):
            assert_pdf_pages_safe(MAX_PDF_PAGES + 1)

    def test_pdf_beyond_page_bound_maps_to_unreadable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("app.modules.profiles.cv.safety.MAX_PDF_PAGES", 0)
        text, error = cv_tasks.extract_text(make_pdf_bytes(), PDF_MIME)
        assert text is None
        assert error == "unreadable"


class TestTruncateText:
    def test_short_text_is_untouched(self) -> None:
        text, truncated = truncate_text("court")
        assert text == "court"
        assert truncated is False

    def test_long_text_is_bounded_and_flagged(self) -> None:
        text, truncated = truncate_text("a" * (TEXT_LIMIT + 10))
        assert len(text) == TEXT_LIMIT
        assert truncated is True

    def test_custom_limit(self) -> None:
        assert truncate_text("abcdef", 3) == ("abc", True)


class TestWorkerRejectsBomb:
    def test_bomb_never_reaches_python_docx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _explode(data: bytes) -> str:
            raise AssertionError("la décompression ne doit JAMAIS être atteinte")

        monkeypatch.setattr(cv_tasks, "extract_docx_text", _explode)
        text, error = cv_tasks.extract_text(make_zip_bomb_docx_bytes(), DOCX_MIME)
        assert text is None
        assert error == "unreadable"

    def test_bomb_is_a_permanent_business_failure(self) -> None:
        """Aucune exception (donc aucun retry Celery) : statut ``failed`` +
        ``error_code='unreadable'``, et aucun appel LLM."""
        provider = FakeProvider()
        outcome = cv_tasks.run_cv_extraction(
            make_zip_bomb_docx_bytes(), DOCX_MIME, provider
        )
        assert outcome.document_status == "failed"
        assert outcome.error_code == "unreadable"
        assert outcome.run_status is None
        assert outcome.raw_text is None
        assert provider.calls == []

    def test_sniffer_rejects_the_bomb_at_upload(self) -> None:
        """Le refus intervient DÈS l'upload : ``sniff_mime`` applique le même
        garde-fou (catalogue seul, aucune décompression) et lève, ce que le
        service traduit en 415 — plutôt qu'un 202 suivi d'un échec asynchrone."""
        with pytest.raises(UnsafeDocumentError):
            sniff_mime(make_zip_bomb_docx_bytes())

    def test_sniffer_still_accepts_a_legitimate_docx(self) -> None:
        assert sniff_mime(make_docx_bytes(["Développeuse backend"])) == DOCX_MIME


class TestStorageReadFailure:
    """Défaut mineur 13 : une lecture de stockage en échec laissait le
    document en ``parsing`` indéfiniment."""

    async def test_read_failure_switches_document_to_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import uuid

        from app.modules.profiles.cv.models import CvDocument
        from tests.unit.cv.test_worker_tasks import FakeEngine, FakeSession

        document = CvDocument(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            file_key="cv/u/d/original.pdf",
            filename="cv.pdf",
            mime_type=PDF_MIME,
            size_bytes=1000,
            status="uploaded",
        )
        session = FakeSession(document)
        engine = FakeEngine()
        monkeypatch.setattr(cv_tasks, "create_worker_engine", lambda: engine)
        monkeypatch.setattr(
            cv_tasks, "async_sessionmaker", lambda eng, **kw: lambda: session
        )

        class ExplodingStorage:
            def get(self, key: str) -> bytes:
                raise RuntimeError("stockage indisponible")

            def put(self, key: str, data: bytes) -> None:  # pragma: no cover
                raise AssertionError("aucune écriture attendue")

            def delete(self, key: str) -> None:  # pragma: no cover
                raise AssertionError("aucune suppression attendue")

        report: dict[str, Any] = await cv_tasks._parse_cv_cycle(
            str(document.id), storage=ExplodingStorage(), provider=FakeProvider()
        )

        assert report == {"status": "failed", "error_code": "unreadable"}
        assert document.status == "failed"  # jamais bloqué en « parsing »
        assert document.error_code == "unreadable"
        assert engine.disposed

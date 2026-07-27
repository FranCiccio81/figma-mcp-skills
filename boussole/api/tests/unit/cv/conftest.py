"""Fixtures des tests du sous-package CV (F-B).

- fixtures FICHIERS construites en bytes : PDF minimal avec couche texte
  (offsets xref calculés), PDF « image seule » (page sans texte), DOCX
  minimal (python-docx en mémoire), zip non-DOCX ;
- ``InMemoryObjectStorage`` / ``InMemoryCvRepository`` : implémentations en
  mémoire des protocoles ``ObjectStorage`` / ``CvDocumentsRepository`` ;
- ``client`` : étend le client commun avec les overrides cv + profiles +
  stockage + enqueue factice.
"""

import io
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.storage import ObjectNotFoundError, get_object_storage
from app.modules.profiles.cv.models import CvDocument, ExtractionRun
from app.modules.profiles.cv.repository import get_cv_documents_repository
from app.modules.profiles.cv.router import get_parse_enqueuer
from app.modules.profiles.repository import get_profiles_repository
from tests.unit.profiles.conftest import InMemoryProfilesRepository

# ------------------------------------------------------------ fichiers (bytes)


def make_pdf_bytes(text: str = "Developpeuse Python chez Acme depuis 2020") -> bytes:
    """PDF 1 page minimal AVEC couche texte — offsets xref exacts.

    Le texte est émis en Helvetica via un opérateur ``Tj`` : extractible
    par pypdf. Caractères ASCII uniquement (chaîne littérale PDF).
    """
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref_position = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_position).encode("ascii")
        + b"\n%%EOF"
    )
    return bytes(out)


def make_image_only_pdf_bytes() -> bytes:
    """PDF valide sans AUCUN opérateur de texte (scan simulé, F-B alt. 1)."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref_position = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_position).encode("ascii")
        + b"\n%%EOF"
    )
    return bytes(out)


def make_docx_bytes(paragraphs: list[str] | None = None) -> bytes:
    """DOCX minimal en mémoire (zip ``PK`` + ``word/document.xml``)."""
    from docx import Document

    document = Document()
    for paragraph in paragraphs if paragraphs is not None else ["Ingénieure QA chez Beta"]:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_plain_zip_bytes() -> bytes:
    """Zip valide qui n'est PAS un DOCX (pas de ``word/document.xml``)."""
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "pas un docx")
    return buffer.getvalue()


# ------------------------------------------------------------ doublures


class InMemoryObjectStorage:
    """Implémentation en mémoire du protocole ``ObjectStorage``."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise ObjectNotFoundError(key)
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class InMemoryCvRepository:
    """Implémentation en mémoire du protocole ``CvDocumentsRepository``."""

    def __init__(self) -> None:
        self.documents: dict[uuid.UUID, CvDocument] = {}
        self.runs: list[ExtractionRun] = []

    async def add(self, document: CvDocument) -> CvDocument:
        self.documents[document.id] = document
        return document

    async def get_for_user(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> CvDocument | None:
        document = self.documents.get(document_id)
        if document is None or document.user_id != user_id:
            return None
        return document

    async def list_for_user(self, user_id: uuid.UUID) -> list[CvDocument]:
        return [doc for doc in self.documents.values() if doc.user_id == user_id]

    async def latest_success_run(self, document_id: uuid.UUID) -> ExtractionRun | None:
        matching = [
            run
            for run in self.runs
            if run.cv_document_id == document_id and run.status == "success"
        ]
        return matching[-1] if matching else None

    async def runs_for_document(self, document_id: uuid.UUID) -> list[ExtractionRun]:
        return [run for run in self.runs if run.cv_document_id == document_id]

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        doc_ids = {
            doc_id for doc_id, doc in self.documents.items() if doc.user_id == user_id
        }
        self.runs = [run for run in self.runs if run.cv_document_id not in doc_ids]
        for doc_id in doc_ids:
            del self.documents[doc_id]

    async def commit(self) -> None:
        return None


# ------------------------------------------------------------ fixtures


@pytest.fixture
def storage() -> InMemoryObjectStorage:
    return InMemoryObjectStorage()


@pytest.fixture
def cv_repository() -> InMemoryCvRepository:
    return InMemoryCvRepository()


@pytest.fixture
def profiles_repository() -> InMemoryProfilesRepository:
    return InMemoryProfilesRepository()


@pytest.fixture
def enqueued() -> list[uuid.UUID]:
    """Identifiants passés à l'enqueue Celery factice (aucun broker)."""
    return []


@pytest.fixture
def client(
    client: TestClient,
    cv_repository: InMemoryCvRepository,
    profiles_repository: InMemoryProfilesRepository,
    storage: InMemoryObjectStorage,
    enqueued: list[uuid.UUID],
) -> Iterator[TestClient]:
    """Étend le client commun (tests/unit/conftest.py) avec les doublures CV."""
    overrides = client.app.dependency_overrides
    overrides[get_cv_documents_repository] = lambda: cv_repository
    overrides[get_profiles_repository] = lambda: profiles_repository
    overrides[get_object_storage] = lambda: storage
    overrides[get_parse_enqueuer] = lambda: enqueued.append
    yield client

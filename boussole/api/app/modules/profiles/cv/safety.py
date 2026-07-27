"""Garde-fous de sûreté des documents CV importés (F-B, D16, R7).

Un document VALIDE au sens du format peut rester hostile : une archive DOCX
de quelques centaines de kilo-octets peut se décompresser en centaines de
méga-octets (« zip bomb » / bombe de décompression) et tuer le worker par
OOM — avec ``acks_late`` + retries, la tâche est alors rejouée en boucle et
consomme toute la file ``ai``.

Ce module est PUR (aucune dépendance applicative, aucune E/S) :

- :func:`assert_archive_safe` — refuse une archive zip (conteneur DOCX)
  dont la taille décompressée annoncée dépasse
  :data:`MAX_UNCOMPRESSED_BYTES` 🟡 ou dont le ratio décompressé/compressé
  dépasse :data:`MAX_COMPRESSION_RATIO` 🟡, AVANT toute décompression ;
- :func:`assert_pdf_pages_safe` — borne le nombre de pages PDF
  (:data:`MAX_PDF_PAGES` 🟡) ;
- :func:`truncate_text` — borne la taille du texte transmis au LLM
  (:data:`TEXT_LIMIT` 🟡) et signale la troncature.

Toute violation lève :class:`UnsafeDocumentError` : c'est une erreur
PERMANENTE (le document ne deviendra jamais lisible) — l'appelant persiste
``status='failed'`` + ``error_code='unreadable'`` et ne rejoue PAS la tâche.
"""

import io
import zipfile

#: Taille décompressée cumulée maximale d'une archive DOCX (50 Mo 🟡).
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024

#: Ratio décompressé/compressé maximal toléré (100:1 🟡 — un DOCX
#: bureautique reste très en dessous ; la bombe observée était à 912:1).
MAX_COMPRESSION_RATIO = 100.0

#: Nombre de pages PDF maximal (🟡 — un CV plausible reste sous cette borne).
MAX_PDF_PAGES = 200

#: Borne dure de l'accumulation de texte pendant l'extraction (mémoire).
MAX_EXTRACTED_CHARS = 2_000_000

#: Taille de texte transmise au LLM (🟡 — coûts, fenêtre de contexte).
TEXT_LIMIT = 100_000


class UnsafeDocumentError(ValueError):
    """Document refusé par un garde-fou — erreur PERMANENTE (``unreadable``).

    ``reason`` : message explicite destiné aux journaux et à l'avertissement
    porté par le résultat de parsing (jamais de contenu du document).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def assert_archive_safe(data: bytes) -> None:
    """Refuse une archive hostile AVANT toute décompression (bombe zip).

    Contrôles, sur le seul CATALOGUE de l'archive (aucune donnée n'est
    décompressée ici) :

    1. archive illisible → refus (``unreadable``) ;
    2. somme des ``file_size`` annoncés > :data:`MAX_UNCOMPRESSED_BYTES` ;
    3. ratio ``décompressé / compressé`` > :data:`MAX_COMPRESSION_RATIO`.

    Les tailles annoncées peuvent mentir dans une archive forgée ; l'appelant
    borne DONC AUSSI le texte accumulé (:data:`MAX_EXTRACTED_CHARS`) — les
    deux garde-fous sont complémentaires.
    """
    if not data:
        raise UnsafeDocumentError("archive vide")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
    except (zipfile.BadZipFile, OSError) as exc:  # archive corrompue/tronquée
        raise UnsafeDocumentError("archive illisible") from exc

    uncompressed = sum(entry.file_size for entry in entries)
    if uncompressed > MAX_UNCOMPRESSED_BYTES:
        raise UnsafeDocumentError(
            f"archive refusée : {uncompressed} octets décompressés annoncés "
            f"(maximum {MAX_UNCOMPRESSED_BYTES})"
        )
    ratio = uncompressed / len(data)
    if ratio > MAX_COMPRESSION_RATIO:
        raise UnsafeDocumentError(
            f"archive refusée : ratio de décompression {ratio:.0f}:1 "
            f"(maximum {MAX_COMPRESSION_RATIO:.0f}:1)"
        )


def assert_pdf_pages_safe(page_count: int) -> None:
    """Refuse un PDF au-delà de :data:`MAX_PDF_PAGES` 🟡 (coût d'extraction)."""
    if page_count > MAX_PDF_PAGES:
        raise UnsafeDocumentError(
            f"PDF refusé : {page_count} pages (maximum {MAX_PDF_PAGES})"
        )


def truncate_text(text: str, limit: int = TEXT_LIMIT) -> tuple[str, bool]:
    """``(texte borné, tronqué ?)`` — borne la taille transmise au LLM.

    Fonction pure : la troncature est faite sur le nombre de CARACTÈRES
    (borne de coût et de contexte, pas d'octets) ; l'appelant ajoute un
    avertissement explicite quand ``tronqué`` est vrai.
    """
    if limit < 0:
        raise ValueError("limit doit être positif")
    if len(text) <= limit:
        return text, False
    return text[:limit], True

"""Tests du curseur keyset (created_at, id) du module applications."""

import base64
import uuid
from datetime import UTC, datetime

import pytest

from app.modules.applications.repository import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)


class TestCursorRoundtrip:
    def test_encode_decode_roundtrip(self) -> None:
        created_at = datetime(2026, 7, 26, 12, 30, 45, 123456, tzinfo=UTC)
        last_id = uuid.uuid4()
        decoded = decode_cursor(encode_cursor(created_at, last_id))
        assert decoded.created_at == created_at
        assert decoded.last_id == last_id

    def test_cursor_is_opaque_base64(self) -> None:
        cursor = encode_cursor(datetime.now(UTC), uuid.uuid4())
        # URL-safe, décodable sans exception.
        base64.urlsafe_b64decode(cursor.encode())


class TestCursorRejection:
    @pytest.mark.parametrize(
        "raw",
        [
            "n'importe quoi",
            "",
            base64.urlsafe_b64encode(b"pas du json").decode(),
            base64.urlsafe_b64encode(b'{"v": "2026-01-01T00:00:00"}').decode(),  # id absent
            base64.urlsafe_b64encode(b'{"v": "pas une date", "id": "x"}').decode(),
            base64.urlsafe_b64encode(
                b'{"v": "2026-01-01T00:00:00", "id": "pas-un-uuid"}'
            ).decode(),
        ],
    )
    def test_corrupted_cursor_raises(self, raw: str) -> None:
        with pytest.raises(InvalidCursorError):
            decode_cursor(raw)

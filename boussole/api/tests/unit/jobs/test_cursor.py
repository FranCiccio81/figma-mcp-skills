"""Tests du curseur opaque de pagination (encode/decode, robustesse, API 422)."""

import base64
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.modules.jobs.repository import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)


class TestCursorCodec:
    def test_roundtrip_date_sort(self) -> None:
        value = datetime(2026, 7, 20, 12, 30, tzinfo=UTC)
        last_id = uuid.uuid4()
        cursor = decode_cursor(encode_cursor("date", value, last_id), expected_sort="date")
        assert cursor.sort == "date"
        assert cursor.value == value
        assert cursor.last_id == last_id

    def test_roundtrip_relevance_sort_preserves_float(self) -> None:
        last_id = uuid.uuid4()
        cursor = decode_cursor(
            encode_cursor("relevance", 0.123456789, last_id), expected_sort="relevance"
        )
        assert cursor.value == 0.123456789  # repr() garantit l'aller-retour exact
        assert cursor.last_id == last_id

    def test_cursor_is_opaque_base64(self) -> None:
        raw = encode_cursor("date", datetime.now(UTC), uuid.uuid4())
        # Décodable en base64 URL-safe, mais opaque pour le client.
        assert base64.urlsafe_b64decode(raw.encode())

    @pytest.mark.parametrize(
        "corrupted",
        [
            "n'importe quoi %%%",
            "",
            base64.urlsafe_b64encode(b"pas du json").decode(),
            base64.urlsafe_b64encode(b'{"s": "date"}').decode(),  # clés manquantes
            base64.urlsafe_b64encode(b'{"s": "date", "v": "x", "id": "pas-un-uuid"}').decode(),
            base64.urlsafe_b64encode(b'[1, 2, 3]').decode(),  # pas un objet
        ],
    )
    def test_corrupted_cursor_raises(self, corrupted: str) -> None:
        with pytest.raises(InvalidCursorError):
            decode_cursor(corrupted, expected_sort="date")

    def test_sort_mismatch_raises(self) -> None:
        raw = encode_cursor("date", datetime.now(UTC), uuid.uuid4())
        with pytest.raises(InvalidCursorError):
            decode_cursor(raw, expected_sort="relevance")

    def test_untypeable_value_raises(self) -> None:
        # Curseur 'date' dont la valeur n'est pas un horodatage ISO.
        bad = base64.urlsafe_b64encode(
            b'{"s": "date", "v": "0.5x", "id": "00000000-0000-0000-0000-000000000001"}'
        ).decode()
        with pytest.raises(InvalidCursorError):
            decode_cursor(bad, expected_sort="date")


class TestCursorApi:
    def test_corrupted_cursor_is_422_problem(self, client: TestClient) -> None:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "camille@example.eu",
                "password": "un mot de passe très long",
                "locale": "fr",
                "accepted_terms_version": "2026-07",
                "accepted_privacy_version": "2026-07",
            },
        )
        response = client.get("/api/v1/jobs", params={"cursor": "n'importe quoi"})
        assert response.status_code == 422
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["type"].endswith("/invalid_cursor")

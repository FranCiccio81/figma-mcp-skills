"""Outils communs aux tests de la couche IA — AUCUN appel réseau.

Le client Anthropic est construit sur un transport httpx simulé
(:class:`httpx.MockTransport`) : les objets d'erreur (429, timeout, 400…)
sont donc les vrais objets du SDK, pas des doubles approximatifs.
"""

import json
from collections.abc import Callable

import anthropic
import httpx
import pytest

from app.ai.calls import AiCallRecord
from app.ai.providers import factory
from app.core.config import Settings

Handler = Callable[[httpx.Request], httpx.Response]


class RecordingJournal:
    """Journal en mémoire — capture les lignes ``ai_calls`` sans base."""

    def __init__(self) -> None:
        self.records: list[AiCallRecord] = []

    def record(self, record: AiCallRecord) -> None:
        self.records.append(record)


class RecordingSleeper:
    """Remplace ``time.sleep`` : mémorise les attentes au lieu de dormir."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def message_payload(text: str, *, input_tokens: int = 11, output_tokens: int = 22) -> dict:
    """Réponse Messages API minimale mais réaliste."""
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-4-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def error_payload(message: str, kind: str = "invalid_request_error") -> dict:
    return {"type": "error", "error": {"type": kind, "message": message}}


class FakeTransport:
    """Transport httpx scripté : une réponse (ou exception) par appel."""

    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("appel provider inattendu (script épuisé)")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def body(self, index: int = 0) -> dict:
        return json.loads(self.requests[index].content)


def make_client(transport: FakeTransport) -> anthropic.Anthropic:
    """Client SDK branché sur le transport simulé (aucun réseau)."""
    return anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,  # la politique de retry testée est la nôtre
        http_client=httpx.Client(transport=httpx.MockTransport(transport)),
    )


def settings(**overrides: object) -> Settings:
    """Configuration de test — valeurs explicites, jamais l'environnement."""
    base: dict[str, object] = {
        "anthropic_api_key": "test-key",
        "ai_provider": "anthropic",
        "ai_max_retries": 2,
        "ai_structured_outputs": True,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


#: Schéma de sortie réaliste : généré par Pydantic, il porte des contraintes
#: (pattern, maxLength, bornes) que la sortie structurée ne supporte pas.
SAMPLE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "lang_code": {"type": "string", "pattern": "^[a-z]{2}$"},
        "label": {"type": "string", "maxLength": 100},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "warnings": {"type": "array", "items": {"type": "string"}, "default": []},
    },
    "required": ["lang_code"],
}


@pytest.fixture(autouse=True)
def _reset_provider_cache() -> None:
    """Instances et disjoncteurs sont globaux : jamais de fuite entre tests."""
    factory.reset_provider_cache()


class FakeClock:
    """Horloge monotone pilotée — réarmements et délais sans ``sleep``."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

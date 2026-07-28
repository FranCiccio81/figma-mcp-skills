"""Le provider réel est-il ATTEIGNABLE depuis les points d'appel métier ?

La fabrique (primaire + fallback + breaker) peut être parfaite : si les
tâches et routes construisent leur ``FakeProvider`` en dur, aucune
configuration ne peut activer un provider réel. Ces tests vérifient le
câblage lui-même, pas la fabrique.
"""

import pytest

from app.ai.providers.fake import FakeProvider
from app.core.config import Settings, get_settings


class _Sentinel:
    """Provider factice distinct de ``FakeProvider`` — prouve que la fabrique
    a bien été consultée."""

    def complete_json(self, *args: object, **kwargs: object) -> dict[str, object]:
        return {}


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _settings_with_provider(name: str) -> Settings:
    settings = get_settings()
    return settings.model_copy(update={"ai_provider": name})


class TestProviderSelection:
    """``AI_PROVIDER=fake`` (défaut) → provider déterministe ; toute autre
    valeur → la fabrique décide."""

    def test_generation_worker_uses_fake_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.workers import generation_tasks

        monkeypatch.setattr(
            generation_tasks, "get_settings", lambda: _settings_with_provider("fake")
        )
        assert isinstance(generation_tasks.get_generation_provider(), FakeProvider)

    def test_generation_worker_delegates_to_factory_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.workers import generation_tasks

        monkeypatch.setattr(
            generation_tasks, "get_settings", lambda: _settings_with_provider("anthropic")
        )
        monkeypatch.setattr(
            generation_tasks, "get_llm_provider", lambda task: _Sentinel()
        )
        assert isinstance(generation_tasks.get_generation_provider(), _Sentinel)

    def test_cv_worker_delegates_to_factory_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.workers import cv_tasks

        monkeypatch.setattr(
            cv_tasks, "get_settings", lambda: _settings_with_provider("anthropic")
        )
        monkeypatch.setattr(cv_tasks, "get_llm_provider", lambda task: _Sentinel())
        assert isinstance(cv_tasks._get_provider(), _Sentinel)

    def test_explanations_route_delegates_to_factory_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.modules.explanations import router as explanations_router

        monkeypatch.setattr(
            explanations_router, "get_settings", lambda: _settings_with_provider("anthropic")
        )
        monkeypatch.setattr(
            explanations_router, "provider_factory", lambda task: _Sentinel()
        )
        assert isinstance(explanations_router.get_llm_provider(), _Sentinel)

    def test_default_configuration_never_activates_a_real_provider(self) -> None:
        """Garde-fou Q4/Q38 : sans configuration explicite, aucun appel réseau
        n'est possible — l'activation relève d'une décision juridique."""
        assert get_settings().ai_provider == "fake"

    def test_ingestion_uses_fake_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.modules.ingestion import service as ingestion_service

        monkeypatch.setattr(
            ingestion_service, "get_settings", lambda: _settings_with_provider("fake")
        )
        assert isinstance(ingestion_service.get_extraction_provider(), FakeProvider)

    def test_ingestion_delegates_to_factory_when_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """M8 — ``extract_job`` n'atteignait JAMAIS la fabrique.

        ``normalize_raw`` construisait ``FakeProvider()`` en dur, sans jamais
        consulter ``AI_PROVIDER`` : aucune configuration ne pouvait activer un
        provider réel sur le plus gros volume du système (≤ 10 k appels/jour,
        08 §2.2), et le secours LLM de 07 §5.2 retournait systématiquement une
        extraction vide.
        """
        from app.modules.ingestion import service as ingestion_service

        monkeypatch.setattr(
            ingestion_service, "get_settings", lambda: _settings_with_provider("anthropic")
        )
        monkeypatch.setattr(
            ingestion_service, "get_llm_provider", lambda task: _Sentinel()
        )
        assert isinstance(ingestion_service.get_extraction_provider(), _Sentinel)

    def test_normalize_raw_uses_the_configured_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le câblage doit tenir au POINT D'APPEL, pas seulement dans un
        helper que personne n'utilise."""
        from app.modules.ingestion import service as ingestion_service
        from app.modules.ingestion.connectors.base import RawJob

        vus: list[str] = []

        class _Recording:
            def complete_json(self, task: str, *args: object, **kwargs: object) -> dict:
                vus.append(task)
                return {
                    "skills_required": [],
                    "skills_nice": [],
                    "languages": [],
                    "warnings": [],
                }

        monkeypatch.setattr(
            ingestion_service, "get_settings", lambda: _settings_with_provider("anthropic")
        )
        monkeypatch.setattr(
            ingestion_service, "get_llm_provider", lambda task: _Recording()
        )

        ingestion_service.normalize_raw(
            RawJob(
                external_ref="ref-1",
                title="Développeuse Python senior",
                company="Acme",
                description="Poste chez Acme, stack Python et PostgreSQL.",
                url="https://example.test/offres/ref-1",
                payload={},
            ),
            source_slug="france-travail",
        )

        # Sans le correctif, `vus` reste vide : le FakeProvider en dur avait
        # absorbé l'appel.
        assert vus == ["extract_job"]

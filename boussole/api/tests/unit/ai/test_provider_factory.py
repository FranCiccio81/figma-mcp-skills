"""Fabrique de providers : défaut fake, sélection, fallback, circuit breaker.

Le point dur testé ici est D18 : après N échecs consécutifs le circuit
s'ouvre, la fabrique bascule sur le second provider, puis le circuit se
referme après T secondes — et si plus rien n'est disponible, l'échec est
propre (l'application reste utilisable sans LLM).
"""

from collections.abc import Mapping
from typing import Any

import pytest

from app.ai.providers import factory
from app.ai.providers.base import (
    LLMProviderError,
    LLMTimeoutError,
    ProviderUnavailableError,
)
from app.ai.providers.factory import (
    CircuitBreaker,
    RoutedProvider,
    build_provider,
    get_llm_provider,
)
from app.ai.providers.fake import FakeProvider
from tests.unit.ai.conftest import FakeClock, settings


class StubProvider:
    """Provider scripté : lève ou répond, et compte ses appels."""

    def __init__(self, *, error: Exception | None = None, payload: dict | None = None) -> None:
        self.error = error
        self.payload = payload if payload is not None else {"ok": True}
        self.calls = 0

    def complete_json(
        self, task: str, prompt: str, schema: Mapping[str, Any]
    ) -> dict[str, Any]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return dict(self.payload)


class TestSelectionParConfiguration:
    def test_le_defaut_est_le_provider_factice(self) -> None:
        # Le provider réel n'est JAMAIS actif implicitement (§5 périmètre).
        provider = get_llm_provider("extract_job", settings(ai_provider="fake"))

        assert isinstance(provider, RoutedProvider)
        assert [name for name, _ in provider.candidates] == ["fake"]
        assert isinstance(provider.candidates[0][1], FakeProvider)

    def test_le_provider_reel_est_selectionne_quand_il_est_configure(self) -> None:
        provider = get_llm_provider(
            "extract_job", settings(ai_provider="anthropic", anthropic_api_key="k")
        )

        assert [name for name, _ in provider.candidates] == ["anthropic"]

    def test_sans_cle_le_provider_reel_n_est_pas_active(self) -> None:
        # Jamais d'appel réseau sans clé — mais surtout : JAMAIS de repli
        # silencieux sur le factice (C3). L'utilisateur doit voir un échec,
        # pas un CV « analysé » vide.
        with pytest.raises(ProviderUnavailableError) as excinfo:
            get_llm_provider(
                "extract_job", settings(ai_provider="anthropic", anthropic_api_key="")
            )

        assert excinfo.value.error_code == "provider_unavailable"
        assert "fake" in str(excinfo.value).lower()

    def test_un_provider_inconnu_suspend_la_fonction_au_lieu_de_mentir(self) -> None:
        # Une faute de frappe dans AI_PROVIDER ne doit pas se traduire par des
        # sorties vides présentées comme des résultats (C3).
        with pytest.raises(ProviderUnavailableError):
            get_llm_provider("extract_job", settings(ai_provider="mistral-maison"))

    def test_le_factice_reste_disponible_s_il_est_demande_explicitement(self) -> None:
        # La seule porte d'entrée du factice : AI_PROVIDER=fake.
        provider = get_llm_provider("extract_job", settings(ai_provider="fake"))

        assert isinstance(provider.candidates[0][1], FakeProvider)

    def test_un_fallback_factice_derriere_un_provider_reel_est_refuse(self) -> None:
        # C3 : `AI_FALLBACK_PROVIDER=fake` transformait chaque ouverture de
        # circuit en panne MASQUÉE (sorties vides, rien dans ai_calls).
        provider = get_llm_provider(
            "extract_job",
            settings(ai_provider="anthropic", anthropic_api_key="k", ai_fallback_provider="fake"),
        )

        assert [name for name, _ in provider.candidates] == ["anthropic"]
        assert not any(isinstance(p, FakeProvider) for _, p in provider.candidates)

    def test_le_fallback_configure_est_ajoute_comme_second_candidat(self) -> None:
        # Un VRAI second provider, lui, est bien chaîné.
        factory.PROVIDER_BUILDERS["autre-reel"] = lambda conf: StubProvider()
        try:
            provider = get_llm_provider(
                "extract_job",
                settings(
                    ai_provider="anthropic",
                    anthropic_api_key="k",
                    ai_fallback_provider="autre-reel",
                ),
            )
            assert [name for name, _ in provider.candidates] == ["anthropic", "autre-reel"]
        finally:
            del factory.PROVIDER_BUILDERS["autre-reel"]

    def test_les_instances_sont_mutualisees_par_processus(self) -> None:
        conf = settings(ai_provider="fake")

        assert build_provider("fake", conf) is build_provider("fake", conf)

        factory.reset_provider_cache()
        assert build_provider("fake", conf) is not None


class TestFallback:
    def test_l_echec_du_primaire_bascule_sur_le_second_provider(self) -> None:
        primaire = StubProvider(error=LLMTimeoutError("timeout"))
        secours = StubProvider(payload={"depuis": "secours"})
        routed = RoutedProvider(
            candidates=(("primaire", primaire), ("secours", secours)),
            breakers={
                "primaire": CircuitBreaker(threshold=5, reset_seconds=60),
                "secours": CircuitBreaker(threshold=5, reset_seconds=60),
            },
        )

        assert routed.complete_json("extract_job", "p", {}) == {"depuis": "secours"}
        assert primaire.calls == 1 and secours.calls == 1

    def test_sans_fallback_l_erreur_remonte_avec_son_code(self) -> None:
        primaire = StubProvider(error=LLMTimeoutError("t"))
        routed = RoutedProvider(candidates=(("primaire", primaire),))

        with pytest.raises(LLMTimeoutError) as excinfo:
            routed.complete_json("extract_job", "p", {})
        assert excinfo.value.error_code == "timeout"

    def test_l_echec_des_deux_providers_remonte_la_derniere_erreur(self) -> None:
        routed = RoutedProvider(
            candidates=(
                ("primaire", StubProvider(error=LLMTimeoutError("t"))),
                ("secours", StubProvider(error=LLMProviderError("boom"))),
            )
        )

        with pytest.raises(LLMProviderError) as excinfo:
            routed.complete_json("extract_job", "p", {})
        assert excinfo.value.error_code == "provider_error"


class TestCircuitBreaker:
    def test_il_s_ouvre_apres_n_echecs_consecutifs(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=3, reset_seconds=60, clock=clock)

        for _ in range(2):
            breaker.record_failure()
        assert breaker.allow() and breaker.state == "closed"

        breaker.record_failure()
        assert not breaker.allow()
        assert breaker.state == "open"

    def test_un_succes_remet_le_compteur_a_zero(self) -> None:
        breaker = CircuitBreaker(threshold=2, reset_seconds=60, clock=FakeClock())

        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()

        assert breaker.allow()  # les échecs doivent être CONSÉCUTIFS

    def test_il_se_referme_apres_le_delai_puis_un_succes(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=1, reset_seconds=30, clock=clock)

        breaker.record_failure()
        assert not breaker.allow()

        clock.advance(30)
        assert breaker.state == "half_open"
        assert breaker.allow()  # appel d'essai autorisé

        breaker.record_success()
        assert breaker.state == "closed"

    def test_un_echec_en_demi_ouvert_rouvre_pour_un_cycle_complet(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=1, reset_seconds=30, clock=clock)

        breaker.record_failure()
        clock.advance(30)
        assert breaker.state == "half_open"

        breaker.record_failure()
        assert breaker.state == "open"
        clock.advance(29)
        assert not breaker.allow()

    def test_le_circuit_ouvert_bascule_sur_le_fallback_sans_appeler_le_primaire(self) -> None:
        clock = FakeClock()
        primaire = StubProvider(error=LLMProviderError("boom"))
        secours = StubProvider(payload={"depuis": "secours"})
        routed = RoutedProvider(
            candidates=(("primaire", primaire), ("secours", secours)),
            breakers={
                "primaire": CircuitBreaker(threshold=2, reset_seconds=60, clock=clock),
                "secours": CircuitBreaker(threshold=2, reset_seconds=60, clock=clock),
            },
        )

        for _ in range(2):
            routed.complete_json("extract_job", "p", {})
        assert primaire.calls == 2

        # Circuit ouvert : le primaire n'est PLUS appelé du tout.
        routed.complete_json("extract_job", "p", {})
        assert primaire.calls == 2
        assert secours.calls == 3

        # …et il est réessayé une fois le délai écoulé (demi-ouvert).
        clock.advance(60)
        primaire.error = None
        assert routed.complete_json("extract_job", "p", {}) == {"ok": True}
        assert primaire.calls == 3

    def test_tous_circuits_ouverts_donne_un_echec_propre(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=1, reset_seconds=60, clock=clock)
        breaker.record_failure()
        routed = RoutedProvider(
            candidates=(("primaire", StubProvider()),), breakers={"primaire": breaker}
        )

        # D18 : l'échec est explicite et typé — l'application reste
        # fonctionnelle sans LLM, elle n'est pas bloquée.
        with pytest.raises(ProviderUnavailableError) as excinfo:
            routed.complete_json("extract_job", "p", {})
        assert excinfo.value.error_code == "provider_unavailable"


class TestCompatibiliteDesTaches:
    def test_le_provider_route_respecte_le_protocole_a_l_identique(self) -> None:
        from app.ai.tasks.extract_job import extract_job

        provider = get_llm_provider("extract_job", settings(ai_provider="fake"))

        # La tâche existante fonctionne sans aucune modification.
        extraction = extract_job("Développeuse Python senior", provider)
        assert extraction.skills_required == []
        assert extraction.warnings


class TestDemiOuvertJetonUnique:
    """(11) Le « demi-ouvert » doit être UN essai, pas une réouverture."""

    def test_un_seul_appel_passe_pendant_le_demi_ouvert(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=1, reset_seconds=30, clock=clock)
        breaker.record_failure()
        clock.advance(30)

        assert breaker.state == "half_open"
        # Régression mesurée : allow() répondait True 1000 fois sur 1000 —
        # toute la charge repartait d'un coup sur un provider encore en panne.
        assert breaker.allow() is True
        assert [breaker.allow() for _ in range(999)] == [False] * 999

    def test_l_echec_de_l_essai_rouvre_et_rend_le_jeton_au_cycle_suivant(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=1, reset_seconds=30, clock=clock)
        breaker.record_failure()
        clock.advance(30)

        assert breaker.allow() is True  # essai consommé
        breaker.record_failure()  # l'essai échoue → réouverture complète
        assert breaker.allow() is False

        clock.advance(30)  # nouveau cycle : un nouvel essai est disponible
        assert breaker.allow() is True
        assert breaker.allow() is False

    def test_le_succes_de_l_essai_referme_et_laisse_tout_passer(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=1, reset_seconds=30, clock=clock)
        breaker.record_failure()
        clock.advance(30)

        assert breaker.allow() is True
        breaker.record_success()

        assert breaker.state == "closed"
        assert all(breaker.allow() for _ in range(100))

    def test_le_provider_en_demi_ouvert_n_est_essaye_qu_une_fois(self) -> None:
        clock = FakeClock()
        primaire = StubProvider(error=LLMProviderError("boom"))
        secours = StubProvider(payload={"depuis": "secours"})
        routed = RoutedProvider(
            candidates=(("primaire", primaire), ("secours", secours)),
            breakers={"primaire": CircuitBreaker(threshold=1, reset_seconds=30, clock=clock)},
        )

        routed.complete_json("extract_job", "p", {})  # ouvre le circuit
        assert primaire.calls == 1

        clock.advance(30)  # demi-ouvert : UN essai, qui échoue
        for _ in range(50):
            routed.complete_json("extract_job", "p", {})
        assert primaire.calls == 2


class TestErreursInattenduesDuProvider:
    """(14) Un provider qui CASSE est un provider en panne, pas une exception
    qui traverse fallback, disjoncteur et journalisation."""

    def test_une_exception_non_typee_bascule_sur_le_fallback(self) -> None:
        primaire = StubProvider(error=TypeError("réponse inattendue du SDK"))
        secours = StubProvider(payload={"depuis": "secours"})
        routed = RoutedProvider(
            candidates=(("primaire", primaire), ("secours", secours)),
            breakers={
                "primaire": CircuitBreaker(threshold=5, reset_seconds=60),
                "secours": CircuitBreaker(threshold=5, reset_seconds=60),
            },
        )

        assert routed.complete_json("extract_job", "p", {}) == {"depuis": "secours"}
        assert secours.calls == 1

    def test_une_exception_non_typee_compte_dans_le_disjoncteur(self) -> None:
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=2, reset_seconds=60, clock=clock)
        primaire = StubProvider(error=AttributeError("boom"))
        routed = RoutedProvider(
            candidates=(("primaire", primaire),), breakers={"primaire": breaker}
        )

        for _ in range(2):
            with pytest.raises(LLMProviderError):
                routed.complete_json("extract_job", "p", {})

        assert breaker.state == "open"
        # Le circuit ouvert protège désormais le provider fautif.
        with pytest.raises(ProviderUnavailableError):
            routed.complete_json("extract_job", "p", {})
        assert primaire.calls == 2

    def test_l_exception_est_traduite_dans_le_vocabulaire_ferme(self) -> None:
        routed = RoutedProvider(candidates=(("primaire", StubProvider(error=KeyError("x"))),))

        with pytest.raises(LLMProviderError) as excinfo:
            routed.complete_json("extract_job", "p", {})

        # Un code d'erreur du vocabulaire fermé (08 §5.1), donc journalisable.
        assert excinfo.value.error_code == "provider_error"
        assert isinstance(excinfo.value.__cause__, KeyError)

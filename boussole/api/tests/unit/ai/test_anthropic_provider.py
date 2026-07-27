"""Provider Anthropic — transport simulé, AUCUN appel réseau.

Couvre le contrat de 08 §5 : sortie valide, sortie non-JSON réparée
(repair-parse AVANT de consommer le retry), sortie irréparable → retry puis
échec propre, 429 avec ``Retry-After`` respecté, timeout, et la
journalisation ``ai_calls`` de chaque cas.
"""

import json

import httpx
import pytest

from app.ai.calls import UNKNOWN_PROMPT_VERSION
from app.ai.providers.anthropic import (
    AnthropicProvider,
    repair_json,
    schema_for_structured_output,
)
from app.ai.providers.base import (
    LLMResponseError,
    LLMTimeoutError,
    ProviderConfigurationError,
)
from tests.unit.ai.conftest import (
    SAMPLE_SCHEMA,
    FakeTransport,
    RecordingJournal,
    RecordingSleeper,
    error_payload,
    make_client,
    message_payload,
    settings,
)

PROMPT = "Extrais les attributs de cette offre. Texte confidentiel : Ada Lovelace, 06 11 22 33 44."


def build_provider(
    responses: list[httpx.Response | Exception],
    **overrides: object,
) -> tuple[AnthropicProvider, FakeTransport, RecordingJournal, RecordingSleeper]:
    transport = FakeTransport(responses)
    journal = RecordingJournal()
    sleeper = RecordingSleeper()
    provider = AnthropicProvider(
        settings=settings(**overrides),
        client=make_client(transport),
        journal=journal,
        sleeper=sleeper,
    )
    return provider, transport, journal, sleeper


def ok(text: str) -> httpx.Response:
    return httpx.Response(200, json=message_payload(text))


class TestSortieValide:
    def test_le_json_est_retourne_tel_quel_et_journalise_success(self) -> None:
        provider, transport, journal, _ = build_provider(
            [ok('{"skills_required": [], "warnings": []}')]
        )

        result = provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        assert result == {"skills_required": [], "warnings": []}
        assert len(transport.requests) == 1
        (record,) = journal.records
        assert record.task == "extract_job"
        assert record.status == "success"
        assert record.error_code is None
        assert record.input_tokens == 11
        assert record.output_tokens == 22
        assert record.latency_ms is not None and record.latency_ms >= 0

    def test_le_modele_vient_de_la_configuration_par_tache(self) -> None:
        provider, transport, journal, _ = build_provider([ok("{}")])

        provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        # 08 §2.1 : extract_job → haiku (volume), extract_cv → sonnet.
        assert transport.body()["model"] == "claude-haiku-4-5"
        assert journal.records[0].model == "claude-haiku-4-5"
        assert provider.model_for("extract_cv") == "claude-sonnet-5"

    def test_le_timeout_est_explicite_et_suit_les_cibles_p95(self) -> None:
        provider, _, _, _ = build_provider([ok("{}")])

        # 08 §2.2 : explain_match 4 s (synchrone), extract_cv 30 s.
        assert provider.timeout_for("explain_match") == 4.0
        assert provider.timeout_for("extract_cv") == 30.0
        assert provider.timeout_for("tache_inconnue") == 30.0

    def test_la_sortie_est_contrainte_par_un_schema_assaini(self) -> None:
        provider, transport, _, _ = build_provider([ok("{}")])

        provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        body = transport.body()
        sent = body["output_config"]["format"]
        assert sent["type"] == "json_schema"
        serialized = json.dumps(sent["schema"])
        # Contraintes non supportées retirées de la COPIE envoyée…
        assert "pattern" not in serialized
        assert "maxLength" not in serialized
        # …et objet fermé, comme l'exige la sortie structurée.
        assert sent["schema"]["additionalProperties"] is False


class TestRepairParse:
    def test_une_sortie_encadree_est_reparee_sans_consommer_le_retry(self) -> None:
        bavard = 'Voici le JSON demandé :\n```json\n{"a": 1, "b": [1, 2,],}\n```\nBonne journée !'
        provider, transport, journal, _ = build_provider([ok(bavard)])

        result = provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        assert result == {"a": 1, "b": [1, 2]}
        # UN seul appel : la réparation est déterministe et précède le retry.
        assert len(transport.requests) == 1
        assert journal.records[0].status == "schema_retry"

    def test_une_sortie_irreparable_declenche_un_retry_puis_un_echec_propre(self) -> None:
        provider, transport, journal, _ = build_provider(
            [ok("désolé, je ne peux pas"), ok("toujours pas de JSON")],
            ai_max_retries=2,
        )

        with pytest.raises(LLMResponseError):
            provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        assert len(transport.requests) == 2
        (record,) = journal.records
        assert record.status == "failed"
        assert record.error_code == "parse_error"

    def test_le_retry_reformule_la_consigne_sans_recopier_la_sortie(self) -> None:
        provider, transport, _, _ = build_provider(
            [ok("blabla non JSON"), ok('{"ok": true}')], ai_max_retries=2
        )

        assert provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA) == {"ok": True}

        second = transport.body(1)["messages"][0]["content"]
        assert "objet JSON" in second
        # La sortie fautive n'est jamais renvoyée au modèle ni journalisée.
        assert "blabla non JSON" not in second

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ('{"a": 1}', {"a": 1}),
            ('```json\n{"a": 1}\n```', {"a": 1}),
            ('bruit avant {"a": {"b": "}"}} bruit après', {"a": {"b": "}"}}),
            ('{"a": [1, 2,],}', {"a": [1, 2]}),
            ("[1, 2]", None),  # tableau : pas un objet de sortie valide
            ("aucun json ici", None),
            ("", None),
        ],
    )
    def test_repair_json_est_deterministe(self, raw: str, expected: dict | None) -> None:
        assert repair_json(raw) == expected


class TestErreursProvider:
    def test_un_429_respecte_retry_after_puis_rejoue(self) -> None:
        provider, transport, journal, sleeper = build_provider(
            [
                httpx.Response(
                    429, json=error_payload("slow down", "rate_limit_error"),
                    headers={"retry-after": "2"},
                ),
                ok('{"ok": true}'),
            ]
        )

        assert provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA) == {"ok": True}

        assert sleeper.delays == [2.0]  # l'en-tête prime sur le backoff
        assert len(transport.requests) == 2
        assert journal.records[0].status == "success"

    def test_un_retry_after_demesure_echoue_proprement_sans_bloquer(self) -> None:
        provider, _, journal, sleeper = build_provider(
            [
                httpx.Response(
                    429, json=error_payload("slow down", "rate_limit_error"),
                    headers={"retry-after": "900"},
                )
            ],
            ai_retry_after_max_seconds=30.0,
        )

        with pytest.raises(Exception) as excinfo:
            provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        assert getattr(excinfo.value, "error_code", None) == "rate_limited"
        assert sleeper.delays == []  # aucun worker bloqué 15 minutes
        assert journal.records[0].error_code == "rate_limited"

    def test_un_timeout_est_retente_puis_mappe_sur_llm_timeout_error(self) -> None:
        provider, transport, journal, sleeper = build_provider(
            [
                httpx.ReadTimeout("timeout", request=httpx.Request("POST", "https://x")),
                httpx.ReadTimeout("timeout", request=httpx.Request("POST", "https://x")),
            ],
            ai_max_retries=2,
        )

        with pytest.raises(LLMTimeoutError):
            provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        assert len(transport.requests) == 2
        assert sleeper.delays  # backoff exponentiel entre les tentatives
        assert journal.records[0].error_code == "timeout"

    def test_un_500_est_retente_puis_mappe_sur_provider_error(self) -> None:
        provider, transport, journal, _ = build_provider(
            [
                httpx.Response(500, json=error_payload("boom", "api_error")),
                ok('{"ok": true}'),
            ]
        )

        assert provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA) == {"ok": True}
        assert len(transport.requests) == 2
        assert journal.records[0].status == "success"

    def test_un_401_echoue_immediatement_sans_retry(self) -> None:
        provider, transport, journal, _ = build_provider(
            [httpx.Response(401, json=error_payload("bad key", "authentication_error"))]
        )

        with pytest.raises(Exception) as excinfo:
            provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        assert getattr(excinfo.value, "error_code", None) == "provider_error"
        assert len(transport.requests) == 1  # une clé invalide ne se retente pas
        assert journal.records[0].status == "failed"

    def test_un_schema_refuse_degrade_vers_prompt_plus_extraction(self) -> None:
        provider, transport, _, _ = build_provider(
            [
                httpx.Response(400, json=error_payload("output_config.format: unsupported")),
                ok('{"ok": true}'),
            ]
        )

        assert provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA) == {"ok": True}

        assert "output_config" in transport.body(0)
        degraded = transport.body(1)
        assert "output_config" not in degraded
        assert "UNIQUEMENT avec un objet JSON" in degraded["messages"][0]["content"]

    def test_un_400_sans_rapport_avec_le_schema_ne_degrade_pas(self) -> None:
        provider, transport, _, _ = build_provider(
            [httpx.Response(400, json=error_payload("max_tokens is too large"))]
        )

        with pytest.raises(Exception) as excinfo:
            provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)

        assert getattr(excinfo.value, "error_code", None) == "provider_error"
        assert len(transport.requests) == 1


class TestActivationControlee:
    def test_sans_cle_le_provider_reel_ne_peut_pas_exister(self) -> None:
        with pytest.raises(ProviderConfigurationError):
            AnthropicProvider(settings=settings(anthropic_api_key=""))


class TestJournalSansContenu:
    def test_aucun_champ_du_journal_ne_porte_de_prompt_ni_de_reponse(self) -> None:
        secret_sortie = '{"headline": "Ada Lovelace, 06 11 22 33 44"}'
        provider, _, journal, _ = build_provider([ok(secret_sortie)])

        provider.complete_json("extract_cv", PROMPT, SAMPLE_SCHEMA)

        (record,) = journal.records
        champs = {f: getattr(record, f) for f in record.__dataclass_fields__}
        # Assertion explicite (11 §3) : ni prompt, ni réponse, ni fragment.
        assert set(champs) == {
            "task", "prompt_version", "model", "status", "user_id",
            "input_tokens", "output_tokens", "latency_ms", "error_code",
        }
        serialise = json.dumps(champs, default=str)
        for fragment in ("Ada Lovelace", "06 11 22 33 44", "headline", PROMPT[:20]):
            assert fragment not in serialise

    def test_la_version_de_prompt_est_lue_depuis_la_tache(self) -> None:
        provider, _, journal, _ = build_provider([ok("{}")])

        provider.complete_json("extract_cv", PROMPT, SAMPLE_SCHEMA)

        assert journal.records[0].prompt_version == "extract_cv/1.0.0"

    def test_une_tache_inconnue_journalise_une_version_explicite(self) -> None:
        provider, _, journal, _ = build_provider([ok("{}"), ok("{}")])

        provider.complete_json("extract_job", PROMPT, SAMPLE_SCHEMA)
        assert journal.records[0].prompt_version == "extract_job/1.0.0"

        provider.complete_json("tache_inconnue", PROMPT, SAMPLE_SCHEMA)
        assert journal.records[1].prompt_version == UNKNOWN_PROMPT_VERSION


class TestAssainissementDeSchema:
    def test_les_contraintes_non_supportees_sont_retirees_en_profondeur(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "maxItems": 15,
                    "items": {
                        "type": "object",
                        "properties": {"quote": {"type": "string", "maxLength": 500}},
                    },
                }
            },
        }

        cleaned = schema_for_structured_output(schema)

        serialized = json.dumps(cleaned)
        assert "maxItems" not in serialized
        assert "maxLength" not in serialized
        assert cleaned["additionalProperties"] is False
        assert cleaned["required"] == ["items"]
        nested = cleaned["properties"]["items"]["items"]
        assert nested["additionalProperties"] is False

    def test_le_schema_source_n_est_jamais_modifie(self) -> None:
        original = json.dumps(SAMPLE_SCHEMA, sort_keys=True)

        schema_for_structured_output(SAMPLE_SCHEMA)

        assert json.dumps(SAMPLE_SCHEMA, sort_keys=True) == original

"""Tests de parsing des connecteurs sur fixtures réalistes (aucun réseau —
les fetch passent par ``httpx.MockTransport``)."""

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.modules.ingestion.connectors import base as connectors_base
from app.modules.ingestion.connectors import france_travail as ft
from app.modules.ingestion.connectors.base import get_with_retry, parse_retry_after
from app.modules.ingestion.connectors.france_travail import (
    FranceTravailConnector,
    parse_offer,
)
from app.modules.ingestion.connectors.greenhouse import GreenhouseConnector, parse_job
from app.modules.ingestion.connectors.lever import LeverConnector, parse_posting

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aucune attente réelle dans les retries/politesse des connecteurs."""
    monkeypatch.setattr(connectors_base.time, "sleep", lambda _s: None)


class TestFranceTravail:
    def test_parse_offre_complete(self) -> None:
        offer = _load("france_travail.json")["resultats"][0]
        raw = parse_offer(offer)

        assert raw.external_ref == "185XYZW"
        assert raw.title == "Développeur Full Stack (H/F)"
        assert raw.company == "ACME SAS"
        assert raw.url.endswith("/185XYZW")
        # typeContrat CDI → permanent, mapping direct conf 1.0 (07 §5.1)
        assert raw.contract == "permanent"
        assert raw.contract_conf == 1.0
        # lat/lon fournis par FT (conf 1.0)
        assert raw.locations[0].lat == 45.764
        assert raw.locations[0].country_code == "FR"
        # salaire : libellé parsé par règles (conf 0.8)
        assert (raw.salary_min, raw.salary_max) == (42000, 48000)
        assert raw.salary_period == "year"
        assert raw.salary_conf == 0.8
        # expérience « 3 ans » (libellé)
        assert raw.experience_min == 3.0
        # langues et compétences ROME
        assert ("en", "B2") in raw.languages
        assert "JavaScript" in raw.skills
        assert raw.posted_at == datetime(2026, 7, 20, 8, 15, tzinfo=UTC)
        assert raw.payload is offer

    def test_parse_offre_employeur_confidentiel(self) -> None:
        offer = _load("france_travail.json")["resultats"][1]
        raw = parse_offer(offer)
        assert raw.company == "Employeur confidentiel"
        assert raw.contract == "fixed_term"
        assert (raw.salary_min, raw.salary_max) == (1900, 1900)
        assert raw.salary_period == "month"


class TestGreenhouse:
    def test_parse_job_html_echappe(self) -> None:
        job = _load("greenhouse.json")["jobs"][0]
        raw = parse_job(job, company_name="ACME Corp")

        assert raw.external_ref == "4567890"
        assert raw.title == "Senior Backend Engineer"
        assert raw.company == "ACME Corp"  # nom du board (config)
        assert raw.url == "https://boards.greenhouse.io/acmecorp/jobs/4567890"
        # requisition_id → référence EMPLOYEUR pour la clé de dédup (D13)
        assert raw.employer_ref == "REQ-2026-118"
        # content HTML échappé → texte (étage 0)
        assert "<" not in raw.description
        assert "Senior Backend Engineer" in raw.description
        assert "5+ years of experience" in raw.description
        assert raw.locations[0].label == "Paris, France"
        # pas de champs structurés salaire/contrat (07 §5.1) → étages 1/2
        assert raw.contract is None
        assert raw.salary_min is None

    def test_parse_job_sans_requisition(self) -> None:
        job = _load("greenhouse.json")["jobs"][1]
        raw = parse_job(job, company_name="ACME Corp")
        assert raw.employer_ref is None
        assert raw.locations[0].label == "Remote - France"


class TestLever:
    def test_parse_posting_complet(self) -> None:
        posting = _load("lever.json")[0]
        raw = parse_posting(posting, company_name="Globex")

        assert raw.external_ref == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert raw.title == "Data Engineer"
        assert raw.company == "Globex"
        assert raw.url.startswith("https://jobs.lever.co/globex/")
        # commitment « Full-time » → permanent par dictionnaire (conf 0.9)
        assert raw.contract == "permanent"
        assert raw.contract_conf == 0.9
        # workplaceType structuré et fiable → conf 1.0
        assert raw.remote == "hybrid"
        assert raw.remote_conf == 1.0
        # salaryRange structuré → conf 1.0
        assert (raw.salary_min, raw.salary_max) == (50000, 60000)
        assert raw.salary_currency == "EUR"
        assert raw.salary_period == "year"
        assert raw.salary_conf == 1.0
        # createdAt epoch ms → datetime UTC
        assert raw.posted_at == datetime.fromtimestamp(1753008000, tz=UTC)
        assert raw.locations[0].label == "Bordeaux"

    def test_parse_posting_minimal(self) -> None:
        posting = _load("lever.json")[1]
        raw = parse_posting(posting, company_name="Globex")
        assert raw.contract == "internship"
        assert raw.remote == "onsite"
        assert raw.salary_min is None
        assert raw.salary_conf is None


# ------------------------------------------------- correctifs revue M2
class TestRetryAfter:
    def test_delta_secondes(self) -> None:
        assert parse_retry_after("120") == 120.0

    def test_date_http_rfc9110(self) -> None:
        future = datetime.now(UTC) + timedelta(seconds=90)
        delay = parse_retry_after(format_datetime(future, usegmt=True))
        assert delay is not None
        assert 0 <= delay <= 91

    def test_date_http_passee_delai_nul(self) -> None:
        past = datetime.now(UTC) - timedelta(seconds=90)
        assert parse_retry_after(format_datetime(past, usegmt=True)) == 0.0

    def test_valeur_illisible_fallback_none(self) -> None:
        assert parse_retry_after("n'importe quoi") is None

    def test_get_with_retry_date_http_sans_valueerror(self) -> None:
        """Correctif 11 : un Retry-After au format date HTTP ne lève plus."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                retry_at = datetime.now(UTC) + timedelta(seconds=1)
                return httpx.Response(
                    429, headers={"Retry-After": format_datetime(retry_at, usegmt=True)}
                )
            return httpx.Response(200, json={"ok": True})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        response = get_with_retry(client, "https://api.example/x")
        assert response.status_code == 200
        assert attempts == 2


class TestFetchParOffre:
    """Correctif 12 : try/except PAR OFFRE — un item malformé est compté en
    erreur, le cycle continue (07 §4.5)."""

    def test_greenhouse_item_malforme_et_board_en_echec(self) -> None:
        good_board = _load("greenhouse.json")
        good_board["jobs"].append({"title": "Sans id ni absolute_url"})  # malformé

        def handler(request: httpx.Request) -> httpx.Response:
            if "/boards/acme/" in request.url.path:
                return httpx.Response(200, json=good_board)
            return httpx.Response(500)  # board globex en échec (tous les retries)

        connector = GreenhouseConnector(
            boards=[("acme", "ACME Corp"), ("globex", "Globex")],
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            min_interval_seconds=0.0,
        )
        result = connector.fetch(None)

        assert len(result.jobs) == 2  # les 2 offres valides du board acme
        assert result.parse_errors == 1  # l'offre malformée est comptée
        assert result.failed_scopes == ["globex"]  # correctif 5a : périmètre exclu
        assert result.cursor is None
        assert result.complete is True

    def test_lever_item_malforme_et_site_en_echec(self) -> None:
        postings = _load("lever.json")
        postings.append({"text": "Sans id ni hostedUrl"})  # malformé

        def handler(request: httpx.Request) -> httpx.Response:
            if "/postings/globex" in request.url.path:
                return httpx.Response(200, json=postings)
            return httpx.Response(503)

        connector = LeverConnector(
            sites=[("globex", "Globex"), ("initech", "Initech")],
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            min_interval_seconds=0.0,
        )
        result = connector.fetch(None)

        assert len(result.jobs) == 2
        assert result.parse_errors == 1
        assert result.failed_scopes == ["initech"]

    def test_france_travail_item_malforme(self) -> None:
        resultats = _load("france_travail.json")["resultats"]
        resultats.insert(0, {"intitule": "Offre sans id"})  # malformé (KeyError id)

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(200, json={"access_token": "tok"})
            return httpx.Response(200, json={"resultats": resultats})

        connector = FranceTravailConnector(
            client_id="id", client_secret="secret",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        result = connector.fetch(None)

        assert [raw.external_ref for raw in result.jobs] == ["185XYZW", "185ABCD"]
        assert result.parse_errors == 1
        assert result.complete is True
        assert result.cursor is not None

    def test_france_travail_fetch_tronque_complete_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Correctif 5b : MAX_PAGES atteint → ``complete=False`` (pas de
        mark_expired, curseur inchangé ce cycle)."""
        monkeypatch.setattr(ft, "PAGE_SIZE", 2)
        monkeypatch.setattr(ft, "MAX_PAGES", 2)
        page = {"resultats": [{"id": "a"}, {"id": "b"}]}  # toujours une page pleine

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                return httpx.Response(200, json={"access_token": "tok"})
            return httpx.Response(200, json=page)

        connector = FranceTravailConnector(
            client_id="id", client_secret="secret",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        result = connector.fetch(None)

        assert result.complete is False
        assert len(result.jobs) == 4  # 2 pages fetchées malgré la troncature

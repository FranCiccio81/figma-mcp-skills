"""Tests de parsing des connecteurs sur fixtures réalistes (aucun réseau)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.modules.ingestion.connectors.france_travail import parse_offer
from app.modules.ingestion.connectors.greenhouse import parse_job
from app.modules.ingestion.connectors.lever import parse_posting

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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

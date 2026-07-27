"""Étage 2 de déduplication : décision cosinus opérante (D13, 07 §6.2).

La requête trigram existait, la décision cosinus était inopérante faute de
vecteurs. On vérifie ici le comportement produit attendu :

- fusion AU-DESSUS du seuil (0,92 🟡, configurable — Q12) ;
- **pas** de fusion en dessous : D13 assume les faux négatifs (« doublons
  non fusionnés préférés aux faux positifs ») ;
- aucune décision quand un vecteur manque — le pipeline ne doit jamais
  fusionner « au hasard » ;
- les filtres de compatibilité dure (pays, contrat, statut) restent
  prioritaires sur le cosinus.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.ai.embeddings.hashing import HashingEmbeddingProvider
from app.modules.ingestion.connectors.base import RawJob, RawLocation
from app.modules.ingestion.service import (
    STAGE2_COSINE_THRESHOLD,
    NormalizedJob,
    _stage2_match,
    ingest_batch,
)
from app.modules.jobs.models import JobPosting
from app.modules.referentials.models import EMBEDDING_DIM
from tests.unit.ingestion.conftest import InMemoryJobStore

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def vector(*values: float) -> list[float]:
    """Vecteur unitaire de dimension du schéma, construit à la main."""
    padded = list(values) + [0.0] * (EMBEDDING_DIM - len(values))
    norm = sum(value * value for value in padded) ** 0.5
    return [value / norm for value in padded]


def cosine_vector(cosine: float) -> list[float]:
    """Vecteur dont le cosinus avec ``vector(1.0)`` vaut ``cosine``."""
    return vector(cosine, (1.0 - cosine * cosine) ** 0.5)


def make_candidate(**overrides: object) -> JobPosting:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "dedup_hash": uuid.uuid4().hex,
        "title": "Développeur backend Python",
        "company_name": "Boussole SAS",
        "description_text": "FastAPI et PostgreSQL.",
        "language": "fr",
        "status": "active",
        "country_code": "FR",
        "contract": "permanent",
        "first_seen_at": NOW,
        "last_seen_at": NOW,
        "embedding": vector(1.0),
    }
    values.update(overrides)
    return JobPosting(**values)  # type: ignore[arg-type]


def incoming(**overrides: object) -> NormalizedJob:
    values: dict[str, object] = {
        "title": "Développeur backend Python",
        "company": "Boussole SAS",
        "description": "FastAPI et PostgreSQL.",
        "language": "fr",
        "dedup_hash": uuid.uuid4().hex,
        "country_code": "FR",
        "contract": "permanent",
    }
    values.update(overrides)
    return NormalizedJob(**values)  # type: ignore[arg-type]


def raw_job(external_ref: str) -> RawJob:
    return RawJob(
        external_ref=external_ref,
        title="Développeur backend Python",
        company="Boussole SAS",
        description="FastAPI et PostgreSQL.",
        url=f"https://ft.example.eu/{external_ref}",
        payload={"id": external_ref},
        locations=[RawLocation(label="Lyon")],
    )


class StubStore:
    """Store minimal : ne sert que les candidats trigram de l'étage 2."""

    def __init__(self, candidates: list[JobPosting]) -> None:
        self.candidates = candidates
        self.queries: list[tuple[str, str]] = []

    async def stage2_candidates(self, company_name: str, title: str) -> list[JobPosting]:
        self.queries.append((company_name, title))
        return self.candidates


class TestDecisionCosinus:
    async def test_fusionne_au_dessus_du_seuil(self) -> None:
        candidate = make_candidate()
        store = StubStore([candidate])
        matched = await _stage2_match(store, incoming(), cosine_vector(0.95))  # type: ignore[arg-type]
        assert matched is candidate

    async def test_fusionne_au_seuil_exact(self) -> None:
        candidate = make_candidate()
        store = StubStore([candidate])
        matched = await _stage2_match(
            store,  # type: ignore[arg-type]
            incoming(),
            cosine_vector(STAGE2_COSINE_THRESHOLD),
        )
        assert matched is candidate

    async def test_ne_fusionne_pas_sous_le_seuil(self) -> None:
        store = StubStore([make_candidate()])
        assert await _stage2_match(store, incoming(), cosine_vector(0.90)) is None  # type: ignore[arg-type]

    async def test_choisit_le_meilleur_candidat(self) -> None:
        proche = make_candidate(embedding=cosine_vector(0.99))
        moins_proche = make_candidate(embedding=cosine_vector(0.93))
        store = StubStore([moins_proche, proche])
        assert await _stage2_match(store, incoming(), vector(1.0)) is proche  # type: ignore[arg-type]

    async def test_seuil_configurable(self) -> None:
        """Q12 : le seuil est calibrable sans redéploiement."""
        store = StubStore([make_candidate()])
        assert await _stage2_match(store, incoming(), cosine_vector(0.85)) is None  # type: ignore[arg-type]
        assert await _stage2_match(  # type: ignore[arg-type]
            store, incoming(), cosine_vector(0.85), threshold=0.80
        ) is not None


class TestAbsenceDeVecteur:
    async def test_aucune_decision_sans_vecteur_entrant(self) -> None:
        store = StubStore([make_candidate()])
        assert await _stage2_match(store, incoming(), None) is None  # type: ignore[arg-type]

    async def test_aucune_decision_sans_vecteur_candidat(self) -> None:
        store = StubStore([make_candidate(embedding=None)])
        assert await _stage2_match(store, incoming(), vector(1.0)) is None  # type: ignore[arg-type]

    async def test_dimensions_heterogenes_refusees(self) -> None:
        """Deux modèles différents en base : la comparaison n'a pas de sens
        (08 §8 impose un re-embedding complet)."""
        store = StubStore([make_candidate(embedding=[1.0, 0.0, 0.0])])
        assert await _stage2_match(store, incoming(), vector(1.0)) is None  # type: ignore[arg-type]


class TestFiltresDursPrioritaires:
    @pytest.mark.parametrize(
        "override",
        [
            {"status": "expired"},
            {"country_code": "DE"},
            {"contract": "internship"},
        ],
    )
    async def test_un_candidat_incompatible_n_est_jamais_fusionne(
        self, override: dict[str, object]
    ) -> None:
        # Cosinus parfait, mais compatibilité dure violée (07 §6.2.2).
        store = StubStore([make_candidate(**override)])
        assert await _stage2_match(store, incoming(), vector(1.0)) is None  # type: ignore[arg-type]


class TestPipelineComplet:
    async def test_l_offre_ingérée_porte_son_embedding(self) -> None:
        """Sans vecteur écrit à l'ingestion, l'étage 2 resterait inopérant
        et ``title_similarity`` inconnue."""
        store = InMemoryJobStore()
        source = store.add_source("france-travail")
        report = await ingest_batch(
            source.slug,
            [raw_job("ft-1")],
            store,
            embedder=HashingEmbeddingProvider(dimension=EMBEDDING_DIM),
            now=NOW,
        )
        assert report.created == 1
        posting = next(iter(store.postings.values()))
        assert posting.embedding is not None
        assert len(posting.embedding) == EMBEDDING_DIM

    async def test_ingestion_sans_fournisseur_reste_fonctionnelle(self) -> None:
        """Panne du fournisseur : l'offre est créée sans vecteur (l'étage 2
        ne décide rien) — jamais d'ingestion en échec."""
        store = InMemoryJobStore()
        source = store.add_source("france-travail")
        report = await ingest_batch(
            source.slug, [raw_job("ft-2")], store, embedder=None, now=NOW
        )
        assert report.created == 1
        assert report.errors == 0

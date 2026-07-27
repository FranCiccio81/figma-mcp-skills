"""Rerank vectoriel de la recherche hybride (D07, étape 3) — et pagination.

Le risque principal de cette fonctionnalité n'est pas la pertinence : c'est
la PAGINATION. Le curseur keyset est construit par le service à partir de
``(sort_value, id)`` de la DERNIÈRE ligne servie ; un rerank qui réordonne
librement la page émettrait une borne fausse → doublons ou lignes sautées.

Ces tests verrouillent donc trois invariants, dans cet ordre d'importance :

1. la COMPOSITION de chaque page est inchangée (c'est le SQL qui décide) ;
2. la BORNE du curseur est identique à celle d'avant le rerank ;
3. l'ordre intra-page suit bien le score combiné full-text + cosinus.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.modules.jobs.repository import (
    JobSearchRow,
    RerankWeights,
    SearchFilters,
    _query_embedding,
    rerank_with_embeddings,
)
from tests.unit.jobs.conftest import make_posting

DIM = 8


def vec(*values: float) -> list[float]:
    padded = list(values) + [0.0] * (DIM - len(values))
    norm = sum(value * value for value in padded) ** 0.5
    return [value / norm for value in padded] if norm else padded


def row(rank: float, embedding: list[float] | None = None) -> JobSearchRow:
    posting = make_posting()
    posting.embedding = embedding
    return JobSearchRow(posting=posting, saved_state=None, sort_value=rank)


def ids(rows: list[JobSearchRow]) -> list[uuid.UUID]:
    return [item.posting.id for item in rows]


class TestNeutralite:
    """Le rerank ne doit RIEN changer tant qu'il n'a pas de quoi décider."""

    def test_sans_embedding_de_requete(self) -> None:
        rows = [row(0.9, vec(1.0)), row(0.5, vec(0.0, 1.0))]
        assert rerank_with_embeddings(rows, limit=10) == rows

    def test_embedding_de_requete_vide(self) -> None:
        rows = [row(0.9, vec(1.0)), row(0.5, vec(0.0, 1.0))]
        assert rerank_with_embeddings(rows, limit=10, query_embedding=[]) == rows

    def test_aucune_offre_embarquee(self) -> None:
        rows = [row(0.9), row(0.5), row(0.1)]
        assert rerank_with_embeddings(rows, limit=10, query_embedding=vec(1.0)) == rows

    def test_une_seule_ligne(self) -> None:
        rows = [row(0.9, vec(0.0, 1.0))]
        assert rerank_with_embeddings(rows, limit=10, query_embedding=vec(1.0)) == rows

    def test_tri_chronologique_jamais_reordonne(self) -> None:
        """En ``sort=date``, l'utilisateur a demandé un ordre explicite."""
        now = datetime.now(UTC)
        rows = [
            JobSearchRow(posting=make_posting(), saved_state=None, sort_value=now),
            JobSearchRow(
                posting=make_posting(), saved_state=None,
                sort_value=now - timedelta(days=1),
            ),
        ]
        for item in rows:
            item.posting.embedding = vec(1.0)
        assert rerank_with_embeddings(rows, limit=10, query_embedding=vec(1.0)) == rows


class TestPagination:
    """Invariants de compatibilité keyset — le cœur du sujet."""

    def build(self, count: int, limit: int) -> tuple[list[JobSearchRow], int]:
        # Le SQL rend ``limit + 1`` lignes triées par (rang DESC, id DESC).
        rows = [
            row(1.0 - index * 0.1, vec(0.0, 1.0) if index % 2 else vec(1.0))
            for index in range(count)
        ]
        return rows, limit

    def test_la_composition_de_la_page_est_inchangee(self) -> None:
        rows, limit = self.build(11, 10)
        reranked = rerank_with_embeddings(
            rows, limit=limit, query_embedding=vec(1.0)
        )
        assert set(ids(reranked[:limit])) == set(ids(rows[:limit]))
        assert len(reranked) == len(rows)

    def test_la_ligne_de_detection_de_page_suivante_reste_a_sa_place(self) -> None:
        rows, limit = self.build(11, 10)
        reranked = rerank_with_embeddings(
            rows, limit=limit, query_embedding=vec(1.0)
        )
        assert reranked[limit].posting.id == rows[limit].posting.id

    def test_la_borne_du_curseur_est_identique_a_celle_d_avant_le_rerank(self) -> None:
        """La dernière ligne SERVIE porte le curseur : elle est épinglée."""
        rows, limit = self.build(11, 10)
        reranked = rerank_with_embeddings(
            rows, limit=limit, query_embedding=vec(1.0)
        )
        avant = (rows[limit - 1].sort_value, rows[limit - 1].posting.id)
        apres = (reranked[limit - 1].sort_value, reranked[limit - 1].posting.id)
        assert apres == avant

    def test_aucun_sort_value_n_est_modifie(self) -> None:
        rows, limit = self.build(11, 10)
        avant = sorted(float(item.sort_value) for item in rows)
        reranked = rerank_with_embeddings(rows, limit=limit, query_embedding=vec(1.0))
        assert sorted(float(item.sort_value) for item in reranked) == avant

    def test_pages_successives_sans_doublon_ni_saut(self) -> None:
        """Simulation de deux pages : les lignes servies forment exactement
        l'ensemble attendu, chacune une seule fois."""
        limit = 4
        corpus = [
            row(1.0 - index * 0.1, vec(0.0, 1.0) if index % 2 else vec(1.0))
            for index in range(9)
        ]
        page1 = rerank_with_embeddings(
            corpus[: limit + 1], limit=limit, query_embedding=vec(1.0)
        )[:limit]
        # Le service coupe au curseur porté par la dernière ligne servie.
        boundary = corpus.index(page1[-1])
        page2 = rerank_with_embeddings(
            corpus[boundary + 1 : boundary + 1 + limit + 1],
            limit=limit,
            query_embedding=vec(1.0),
        )[:limit]
        served = ids(page1) + ids(page2)
        assert len(served) == len(set(served))  # aucun doublon
        assert set(served) == set(ids(corpus[: 2 * limit]))  # aucun saut

    def test_page_terminale_entierement_reordonnee(self) -> None:
        """Sans page suivante, aucun curseur n'est émis : rien à épingler."""
        rows = [row(0.9, vec(0.0, 1.0)), row(0.8, vec(1.0))]
        reranked = rerank_with_embeddings(
            rows, limit=10, query_embedding=vec(1.0),
            weights=RerankWeights(fulltext=0.0, vector=1.0),
        )
        # La 2e ligne remonte en tête : rien n'est épinglé sur une page
        # terminale (le service n'émet aucun curseur).
        assert ids(reranked) == [rows[1].posting.id, rows[0].posting.id]


class TestScoreCombine:
    def test_le_cosinus_remonte_une_offre_moins_bien_classee(self) -> None:
        faible_rang_bon_cosinus = row(0.1, vec(1.0))
        bon_rang_cosinus_nul = row(1.0, vec(0.0, 1.0))
        rows = [bon_rang_cosinus_nul, faible_rang_bon_cosinus]
        reranked = rerank_with_embeddings(
            rows, limit=10, query_embedding=vec(1.0),
            weights=RerankWeights(fulltext=0.0, vector=1.0),
        )
        assert reranked[0].posting.id == faible_rang_bon_cosinus.posting.id

    def test_poids_full_text_seul_conserve_l_ordre_sql(self) -> None:
        rows = [row(1.0, vec(0.0, 1.0)), row(0.5, vec(1.0)), row(0.2, vec(1.0))]
        reranked = rerank_with_embeddings(
            rows, limit=10, query_embedding=vec(1.0),
            weights=RerankWeights(fulltext=1.0, vector=0.0),
        )
        assert ids(reranked) == ids(rows)

    def test_offre_sans_vecteur_ni_promue_ni_releguee(self) -> None:
        """« L'inconnu n'est pas un fait négatif » : cosinus moyen de la page."""
        meilleur = row(0.9, vec(1.0))
        sans_vecteur = row(0.6, None)
        pire = row(0.3, vec(-1.0))
        reranked = rerank_with_embeddings(
            [meilleur, sans_vecteur, pire],
            limit=10,
            query_embedding=vec(1.0),
            weights=RerankWeights(fulltext=0.0, vector=1.0),
        )
        assert ids(reranked) == [
            meilleur.posting.id, sans_vecteur.posting.id, pire.posting.id
        ]

    def test_poids_nuls_ne_cassent_rien(self) -> None:
        rows = [row(0.9, vec(1.0)), row(0.5, vec(0.0, 1.0))]
        reranked = rerank_with_embeddings(
            rows, limit=10, query_embedding=vec(1.0),
            weights=RerankWeights(fulltext=0.0, vector=0.0),
        )
        assert ids(reranked) == ids(rows)

    def test_dimensions_incompatibles_ignorees_sans_erreur(self) -> None:
        rows = [row(0.9, [1.0, 0.0]), row(0.5, [0.0, 1.0])]
        reranked = rerank_with_embeddings(rows, limit=10, query_embedding=vec(1.0))
        assert ids(reranked) == ids(rows)

    def test_pondération_par_defaut_normalisee(self) -> None:
        assert RerankWeights(fulltext=2.0, vector=2.0).normalized() == (0.5, 0.5)
        assert RerankWeights(fulltext=3.0, vector=1.0).normalized() == (0.75, 0.25)
        assert RerankWeights(fulltext=0.0, vector=0.0).normalized() == (1.0, 0.0)


class TestEmbeddingDeRequete:
    """Le rerank ne coûte un appel provider que quand il peut servir."""

    async def test_pas_d_embedding_sans_q(self) -> None:
        assert await _query_embedding(
            SearchFilters(q=None, sort="date"), Settings()
        ) is None

    async def test_pas_d_embedding_en_tri_date(self) -> None:
        assert await _query_embedding(
            SearchFilters(q="python", sort="date"), Settings()
        ) is None

    async def test_pas_d_embedding_si_le_rerank_est_coupe(self) -> None:
        assert await _query_embedding(
            SearchFilters(q="python", sort="relevance"),
            Settings(search_rerank_enabled=False),
        ) is None

    async def test_embedding_calcule_en_pertinence_avec_q(self) -> None:
        embedding = await _query_embedding(
            SearchFilters(q="développeur python", sort="relevance"), Settings()
        )
        assert embedding is not None
        assert len(embedding) == Settings().embeddings_dim

    async def test_une_panne_du_fournisseur_degrade_en_rerank_neutre(self) -> None:
        class BrokenProvider:
            dimension = DIM
            model = "broken"

            def embed_texts(self, texts: list[str]) -> list[list[float]]:
                from app.ai.embeddings.base import EmbeddingProviderUnavailableError

                raise EmbeddingProviderUnavailableError("incident simulé")

        assert await _query_embedding(
            SearchFilters(q="python", sort="relevance"),
            Settings(),
            provider=BrokenProvider(),
        ) is None


@pytest.mark.parametrize("limit", [1, 2, 5, 20])
def test_aucun_plantage_sur_les_tailles_de_page_limites(limit: int) -> None:
    rows = [row(1.0 - index * 0.1, vec(1.0)) for index in range(3)]
    reranked = rerank_with_embeddings(rows, limit=limit, query_embedding=vec(1.0))
    assert set(ids(reranked)) == set(ids(rows))

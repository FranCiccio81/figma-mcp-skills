"""Trigger ``tsv`` de la migration 0001 + recherche ``websearch_to_tsquery``.

``job_postings.tsv`` n'est JAMAIS écrit par l'application : il est calculé par
``trg_job_postings_tsv`` (BEFORE INSERT OR UPDATE OF title, company_name,
description_text, language), avec ``unaccent()`` et trois poids (A titre,
B entreprise, C description). Rien de tout cela n'existe hors d'un vrai
PostgreSQL : les tests unitaires approximent le full-text par une recherche
de sous-chaîne en Python.
"""

import uuid

import httpx
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import JobPosting
from tests.integration.factories import make_posting

pytestmark = pytest.mark.integration


class TestTriggerTsv:
    async def test_insert_peuple_tsv_avec_poids_et_sans_accents(
        self, db_session: AsyncSession
    ) -> None:
        """INSERT → le trigger remplit ``tsv`` : lexèmes pondérés, désaccentués."""
        posting = await make_posting(
            db_session,
            title="Développeur Sénior Python",
            company_name="Acme",
            description_text="Ingénierie logicielle et opérations.",
        )

        tsv = await db_session.scalar(
            select(JobPosting.tsv).where(JobPosting.id == posting.id)
        )

        assert tsv, "le trigger doit peupler tsv (jamais l'application)"
        assert "'developpeur':1A" in tsv, "titre désaccentué et pondéré A"
        assert "'acme':4B" in tsv, "entreprise pondérée B"
        assert "'logiciel'" in tsv, "description pondérée C, radicalisée (french)"

    async def test_update_du_titre_rejoue_le_trigger(
        self, db_session: AsyncSession
    ) -> None:
        """UPDATE OF title → ``tsv`` recalculé : l'ancien terme n'est plus trouvable."""
        posting = await make_posting(db_session, title="Développeur backend")

        await db_session.execute(
            update(JobPosting).where(JobPosting.id == posting.id).values(title="Data engineer")
        )
        await db_session.commit()

        tsv = await db_session.scalar(
            select(JobPosting.tsv).where(JobPosting.id == posting.id)
        )
        assert "'engine':2A" in tsv, "nouveau titre indexé, radicalisé et pondéré A"
        assert "developpeur" not in tsv, "l'ancien titre ne doit plus être trouvable"

    async def test_recherche_full_text_remonte_l_offre(
        self, db_session: AsyncSession
    ) -> None:
        """SQL direct : ``tsv @@ websearch_to_tsquery`` retrouve bien l'offre."""
        posting = await make_posting(
            db_session,
            title="Développeur backend",
            description_text="Python, FastAPI, PostgreSQL au quotidien.",
        )
        await make_posting(
            db_session, title="Chef de projet", description_text="Budget et planning."
        )

        rows = await db_session.execute(
            text(
                "SELECT id FROM job_postings "
                "WHERE tsv @@ websearch_to_tsquery('french', :q)"
            ),
            {"q": "python"},
        )

        assert [row[0] for row in rows] == [posting.id]

    async def test_recherche_par_expression_exacte(self, db_session: AsyncSession) -> None:
        """``websearch_to_tsquery`` gère les guillemets (recherche de phrase)."""
        await make_posting(
            db_session,
            title="Ingénieur plateforme",
            description_text="Ingénierie logicielle et fiabilité.",
        )

        trouvee = await db_session.scalar(
            text(
                "SELECT count(*) FROM job_postings "
                "WHERE tsv @@ websearch_to_tsquery('french', :q)"
            ),
            {"q": '"ingenierie logicielle"'},
        )
        absente = await db_session.scalar(
            text(
                "SELECT count(*) FROM job_postings "
                "WHERE tsv @@ websearch_to_tsquery('french', :q)"
            ),
            {"q": '"logicielle ingenierie"'},
        )

        assert trouvee == 1
        assert absente == 0, "l'ordre des mots d'une phrase doit compter"


class TestRechercheApi:
    async def test_q_traverse_la_route_jusqu_au_tsv(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """``GET /jobs?q=`` : de la route au trigger, sans aucune approximation."""
        attendue = await make_posting(
            db_session,
            title="Développeur backend Python",
            description_text="FastAPI, PostgreSQL, Redis.",
        )
        await make_posting(
            db_session,
            title="Assistant commercial",
            description_text="Prospection téléphonique.",
        )

        response = await api_client.get("/api/v1/jobs", params={"q": "fastapi"})

        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["items"]] == [str(attendue.id)]

    async def test_offre_anglaise_indexee_en_anglais(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """``language='en'`` → le trigger indexe avec la config ``english``."""
        await make_posting(
            db_session,
            title="Backend engineer",
            description_text="Building reliable services.",
            language="en",
        )

        response = await api_client.get(
            "/api/v1/jobs", params={"q": "building", "language": "en"}
        )

        assert response.status_code == 200, response.text
        assert len(response.json()["items"]) == 1, "radicalisation anglaise attendue"


async def test_requete_accentuee_trouve_l_offre(
    db_session: AsyncSession,
) -> None:
    """Régression : le trigger désaccentue le TEXTE INDEXÉ, la requête doit
    l'être aussi.

    Sans ``unaccent`` côté requête, ``websearch_to_tsquery('french',
    'développeur')`` produit un lexème accentué qui ne rencontre jamais
    ``developpeur`` : un francophone tapant ses accents — le cas nominal —
    ne trouvait rien. Anomalie découverte par cette suite d'intégration.
    """
    await make_posting(db_session, title="Développeur Sénior", description_text="Python.")

    trouvee = await db_session.scalar(
        text(
            "SELECT count(*) FROM job_postings "
            "WHERE tsv @@ websearch_to_tsquery('french', unaccent(:q))"
        ),
        {"q": "développeur"},
    )

    assert trouvee == 1


async def test_recherche_api_avec_accents(
    api_client: httpx.AsyncClient,
    authenticated_user: uuid.UUID,
    db_session: AsyncSession,
) -> None:
    """Le même scénario à travers l'API réelle (build_search_statement)."""
    await make_posting(
        db_session,
        title="Développeur Sénior",
        description_text="Python, FastAPI.",
    )
    response = await api_client.get("/api/v1/jobs", params={"q": "développeur"})
    assert response.status_code == 200, response.text
    titles = [item["title"] for item in response.json()["items"]]
    assert any("Développeur" in title for title in titles), (
        "la recherche accentuée doit remonter l'offre — unaccent des deux côtés"
    )

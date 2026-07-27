"""Filtre ``salary_min`` avec périodes non annuelles — SQL ``CASE`` réel.

Le filtre annualise en SQL (mois ×12, jour ×220, heure ×1600 🟡) avant de
comparer, et laisse passer les offres sans salaire (Q32 : l'inconnu n'est pas
un fait négatif). L'arithmétique est faite par PostgreSQL sur des colonnes
``int`` : seul un vrai serveur dit si le ``CASE`` s'applique au bon opérande.
"""

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.factories import make_posting

pytestmark = pytest.mark.integration


async def _titres(client: httpx.AsyncClient, **params: object) -> set[str]:
    response = await client.get("/api/v1/jobs", params=params)
    assert response.status_code == 200, response.text
    return {item["title"] for item in response.json()["items"]}


class TestSalaireAnnualise:
    async def test_periodes_non_annuelles_converties_avant_comparaison(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """4 000 €/mois ≈ 48 k€/an : l'offre passe un filtre à 45 000."""
        await make_posting(
            db_session,
            title="Mensuel suffisant",
            salary_min=3500,
            salary_max=4000,
            salary_period="month",
        )
        await make_posting(
            db_session,
            title="Journalier suffisant",
            salary_min=200,
            salary_max=250,
            salary_period="day",
        )
        await make_posting(
            db_session,
            title="Horaire suffisant",
            salary_min=25,
            salary_max=30,
            salary_period="hour",
        )
        await make_posting(
            db_session,
            title="Annuel suffisant",
            salary_min=46000,
            salary_max=52000,
            salary_period="year",
        )

        titres = await _titres(api_client, salary_min=45000)

        assert titres == {
            "Mensuel suffisant",
            "Journalier suffisant",
            "Horaire suffisant",
            "Annuel suffisant",
        }

    async def test_periodes_non_annuelles_insuffisantes_exclues(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """2 000 €/mois (24 k€/an) et 10 €/h (16 k€/an) sont bien écartées."""
        await make_posting(
            db_session, title="Mensuel faible", salary_min=1900, salary_max=2000,
            salary_period="month",
        )
        await make_posting(
            db_session, title="Horaire faible", salary_min=10, salary_max=10,
            salary_period="hour",
        )
        await make_posting(
            db_session, title="Annuel faible", salary_min=30000, salary_max=32000,
            salary_period="year",
        )
        await make_posting(
            db_session, title="Mensuel suffisant", salary_min=4000, salary_max=4500,
            salary_period="month",
        )

        titres = await _titres(api_client, salary_min=45000)

        assert titres == {"Mensuel suffisant"}

    async def test_salaire_inconnu_reste_inclus(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """Q32 : sans salaire renseigné, l'offre n'est jamais exclue par le filtre."""
        await make_posting(
            db_session,
            title="Non communiqué",
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            salary_period=None,
        )
        await make_posting(
            db_session, title="Annuel faible", salary_min=30000, salary_max=30000,
            salary_period="year",
        )

        titres = await _titres(api_client, salary_min=45000)

        assert titres == {"Non communiqué"}

    async def test_periode_hors_vocabulaire_refusee_par_le_check_sql(
        self, db_session: AsyncSession
    ) -> None:
        """CHECK ``salary_period IN ('year','month','day','hour')`` (migration 0001)."""
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            await make_posting(db_session, title="Période absurde", salary_period="week")
        await db_session.rollback()

    async def test_libelle_de_salaire_conserve_la_periode(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """Le montant affiché reste celui de la source (jamais l'annualisation)."""
        await make_posting(
            db_session, title="Mensuel", salary_min=4000, salary_max=4500,
            salary_period="month",
        )

        response = await api_client.get("/api/v1/jobs", params={"salary_min": 45000})

        assert response.status_code == 200, response.text
        assert response.json()["items"][0]["salary_label"] == "4000–4500 €/mois"

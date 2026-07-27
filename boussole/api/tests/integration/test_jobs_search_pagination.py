"""``GET /jobs`` contre un VRAI PostgreSQL — pagination, fraîcheur, tri.

Régression visée (bug critique M2) : les colonnes ``datetime`` étaient mappées
``TIMESTAMP WITHOUT TIME ZONE``. asyncpg refuse alors tout bind de datetime
*aware* — et le curseur keyset de la page 2 comme le seuil ``posted_since``
en envoient un. Résultat : 500 sur toute pagination par date. La suite
unitaire ne pouvait pas le voir : son repository en mémoire compare des
``datetime`` Python, et ``test_search_sql.py`` ne fait que COMPILER le SQL.

Tout ce qui suit passe par la route réelle, le vrai service, le vrai
repository SQLAlchemy et le vrai serveur PostgreSQL.
"""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.factories import make_posting

pytestmark = pytest.mark.integration


async def _page(
    client: httpx.AsyncClient, **params: object
) -> tuple[list[dict[str, object]], str | None]:
    """Une page de ``GET /jobs`` — échoue bruyamment sur tout statut ≠ 200."""
    response = await client.get("/api/v1/jobs", params=params)
    assert response.status_code == 200, f"{response.status_code} : {response.text}"
    body = response.json()
    return body["items"], body["next_cursor"]


class TestPaginationParDate:
    """Curseur keyset ``(last_seen_at, id)`` — le bug du fuseau vivait ici."""

    async def test_page_2_par_curseur_de_date(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """Page 2 : 200 et non 500 (bind d'un datetime *aware* dans le keyset)."""
        now = datetime.now(UTC)
        for index in range(5):
            await make_posting(
                db_session,
                title=f"Offre {index}",
                last_seen_at=now - timedelta(hours=index),
            )

        first_items, cursor = await _page(api_client, limit=2, sort="date")
        assert len(first_items) == 2
        assert cursor is not None, "une 2e page doit être annoncée (5 offres, limit=2)"

        second_items, _ = await _page(api_client, limit=2, sort="date", cursor=cursor)

        assert len(second_items) == 2
        first_ids = {item["id"] for item in first_items}
        assert first_ids.isdisjoint({item["id"] for item in second_items})

    async def test_balayage_complet_sans_doublon_ni_omission(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """Sept offres, pages de 2 : chaque offre servie exactement une fois."""
        now = datetime.now(UTC)
        expected = {
            str(
                (
                    await make_posting(
                        db_session,
                        title=f"Offre {index}",
                        last_seen_at=now - timedelta(minutes=index),
                    )
                ).id
            )
            for index in range(7)
        }

        seen: list[str] = []
        cursor: str | None = None
        for _ in range(6):  # garde-fou anti-boucle infinie
            items, cursor = await _page(
                api_client, limit=2, sort="date", **({"cursor": cursor} if cursor else {})
            )
            seen.extend(str(item["id"]) for item in items)
            if cursor is None:
                break

        assert cursor is None, "la pagination doit se terminer"
        assert len(seen) == len(set(seen)), "aucune offre ne doit être servie deux fois"
        assert set(seen) == expected

    async def test_curseur_de_date_egalites_sur_last_seen_at(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """``last_seen_at`` identiques : l'id départage, aucune ligne perdue."""
        instant = datetime.now(UTC) - timedelta(hours=1)
        expected = {
            str((await make_posting(db_session, title=f"Ex æquo {i}", last_seen_at=instant)).id)
            for i in range(4)
        }

        seen: list[str] = []
        cursor: str | None = None
        for _ in range(5):
            items, cursor = await _page(
                api_client, limit=2, sort="date", **({"cursor": cursor} if cursor else {})
            )
            seen.extend(str(item["id"]) for item in items)
            if cursor is None:
                break

        assert set(seen) == expected
        assert len(seen) == len(expected)


class TestFraicheur:
    """``posted_since`` : comparaison d'un seuil *aware* à ``last_seen_at``."""

    async def test_posted_since_exclut_les_offres_anciennes(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        now = datetime.now(UTC)
        recente = await make_posting(
            db_session, title="Offre récente", last_seen_at=now - timedelta(days=1)
        )
        await make_posting(
            db_session, title="Offre ancienne", last_seen_at=now - timedelta(days=45)
        )

        items, _ = await _page(api_client, posted_since=7, sort="date")

        assert [item["id"] for item in items] == [str(recente.id)]

    async def test_posted_since_page_2(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """Filtre de fraîcheur ET curseur : deux binds *aware* dans la même requête."""
        now = datetime.now(UTC)
        for index in range(4):
            await make_posting(
                db_session, title=f"Fraîche {index}", last_seen_at=now - timedelta(hours=index)
            )

        _items, cursor = await _page(api_client, limit=2, sort="date", posted_since=7)
        assert cursor is not None
        items, _ = await _page(api_client, limit=2, sort="date", posted_since=7, cursor=cursor)

        assert len(items) == 2


class TestTriRelevance:
    """Tri ``relevance`` : rang ``ts_rank_cd`` réel, égalités comprises."""

    async def test_relevance_remonte_l_offre_pertinente(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        pertinente = await make_posting(
            db_session,
            title="Développeur Python",
            description_text="Python, FastAPI, PostgreSQL au quotidien.",
        )
        await make_posting(
            db_session,
            title="Chef de projet marketing",
            description_text="Campagnes, budgets, réseaux sociaux.",
        )

        items, _ = await _page(api_client, q="python", sort="relevance")

        assert [item["id"] for item in items] == [str(pertinente.id)]

    async def test_pagination_relevance_avec_egalites_de_rang(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """Rangs strictement égaux (textes identiques) : l'id départage le keyset.

        Sans second terme de tri, une page 2 sur des rangs ex æquo ré-affiche
        ou saute des offres. Le curseur porte ``(rang, id)`` : la couverture
        n'est possible qu'avec un vrai ``ts_rank_cd``.
        """
        expected = {
            str(
                (
                    await make_posting(
                        db_session,
                        title="Développeur Python",
                        description_text="Python, FastAPI, PostgreSQL au quotidien.",
                        company_name=f"Entreprise {index}",
                    )
                ).id
            )
            for index in range(5)
        }

        seen: list[str] = []
        cursor: str | None = None
        for _ in range(5):
            items, cursor = await _page(
                api_client,
                q="python",
                sort="relevance",
                limit=2,
                **({"cursor": cursor} if cursor else {}),
            )
            seen.extend(str(item["id"]) for item in items)
            if cursor is None:
                break

        assert cursor is None
        assert len(seen) == len(set(seen)), "égalités de rang : aucune offre en double"
        assert set(seen) == expected

    async def test_curseur_incoherent_avec_le_tri_rejete_en_422(
        self,
        api_client: httpx.AsyncClient,
        authenticated_user: uuid.UUID,
        db_session: AsyncSession,
    ) -> None:
        """Curseur de date rejoué sur un tri ``relevance`` → 422, jamais 500."""
        now = datetime.now(UTC)
        for index in range(3):
            await make_posting(
                db_session,
                title=f"Python {index}",
                description_text="Python partout.",
                last_seen_at=now - timedelta(hours=index),
            )

        _items, date_cursor = await _page(api_client, limit=1, sort="date")
        assert date_cursor is not None

        response = await api_client.get(
            "/api/v1/jobs", params={"q": "python", "sort": "relevance", "cursor": date_cursor}
        )

        assert response.status_code == 422, response.text
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["type"].endswith("invalid_cursor")

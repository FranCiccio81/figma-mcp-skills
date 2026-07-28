"""Rétention 13 mois d'``ai_calls`` — contre le VRAI PostgreSQL.

Les tests unitaires de :mod:`app.modules.ai_calls.retention` valident la
boucle de lots contre un fake : ils ne disent rien du SQL. Or ce SQL est
inhabituel — PostgreSQL n'accepte pas de ``LIMIT`` sur un ``DELETE``, la
suppression bornée passe donc par ``DELETE … WHERE id IN (SELECT … LIMIT n)``.
C'est exactement le genre de requête qui passe la relecture, passe les tests
à fake, et ne supprime rien (ou tout) en production.

Vérifié ici : la borne temporelle est respectée, le lot est réellement borné,
et la boucle converge.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_calls.repository import SqlAlchemyAiCallsRepository
from app.modules.ai_calls.retention import enforce_retention, months_before

pytestmark = pytest.mark.integration

MAINTENANT = datetime(2026, 7, 28, 5, 30, tzinfo=UTC)


async def _insert_calls(session: AsyncSession, ages_en_jours: list[int]) -> None:
    """Insère une ligne ``ai_calls`` par âge, relatif à ``MAINTENANT``."""
    for age in ages_en_jours:
        await session.execute(
            text(
                "INSERT INTO ai_calls "
                "(task, prompt_version, model, status, created_at) "
                "VALUES ('extract_cv', 'extract_cv/1.0.0', 'fake', 'success', "
                ":created_at)"
            ),
            {"created_at": MAINTENANT - timedelta(days=age)},
        )
    await session.commit()


async def _count(session: AsyncSession) -> int:
    return int((await session.execute(text("SELECT count(*) FROM ai_calls"))).scalar_one())


class TestBorneTemporelle:
    async def test_seules_les_lignes_au_dela_de_treize_mois_partent(
        self, db_session: AsyncSession
    ) -> None:
        borne = months_before(MAINTENANT, 13)
        age_borne = (MAINTENANT - borne).days
        # Une ligne juste en deçà de la borne, une juste au-delà.
        await _insert_calls(db_session, [age_borne - 1, age_borne + 1])

        outcome = await enforce_retention(
            repository=SqlAlchemyAiCallsRepository(db_session), now=MAINTENANT
        )

        assert outcome.deleted == 1
        assert await _count(db_session) == 1

    async def test_une_table_entierement_recente_nest_pas_touchee(
        self, db_session: AsyncSession
    ) -> None:
        await _insert_calls(db_session, [0, 30, 200])
        outcome = await enforce_retention(
            repository=SqlAlchemyAiCallsRepository(db_session), now=MAINTENANT
        )
        assert outcome.deleted == 0
        assert await _count(db_session) == 3


class TestSuppressionBornee:
    async def test_le_lot_est_reellement_borne_par_le_sql(
        self, db_session: AsyncSession
    ) -> None:
        """Le point du test : ``DELETE`` n'a pas de ``LIMIT`` en PostgreSQL.

        Si la sous-requête était mal construite, ce ``DELETE`` emporterait
        les 12 lignes d'un coup — le verrou long que le lotissement existe
        précisément pour éviter.
        """
        await _insert_calls(db_session, [500 + n for n in range(12)])

        supprimees = await SqlAlchemyAiCallsRepository(db_session).delete_older_than(
            months_before(MAINTENANT, 13), batch=5
        )

        assert supprimees == 5
        assert await _count(db_session) == 7

    async def test_la_boucle_converge_sur_plusieurs_lots(
        self, db_session: AsyncSession
    ) -> None:
        await _insert_calls(db_session, [500 + n for n in range(12)])

        outcome = await enforce_retention(
            repository=SqlAlchemyAiCallsRepository(db_session),
            now=MAINTENANT,
            batch=5,
        )

        assert outcome.deleted == 12
        assert outcome.truncated is False
        assert await _count(db_session) == 0

    async def test_le_plafond_laisse_le_reste_pour_le_prochain_passage(
        self, db_session: AsyncSession
    ) -> None:
        await _insert_calls(db_session, [500 + n for n in range(12)])

        outcome = await enforce_retention(
            repository=SqlAlchemyAiCallsRepository(db_session),
            now=MAINTENANT,
            batch=5,
            max_batches=1,
        )

        assert outcome.deleted == 5
        assert outcome.truncated is True
        assert await _count(db_session) == 7

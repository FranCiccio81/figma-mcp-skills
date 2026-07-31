"""Les migrations concurrentes survivent à une transaction ouverte.

Défaut trouvé en revue avant déploiement, reproduit contre un PostgreSQL
réel. ``alembic/env.py`` pose ``lock_timeout = 5s`` sur la connexion de
migration, avec une justification juste — « un lecteur long transforme une
migration de 4 s en 58 s d'écritures bloquées » — mais une PORTÉE fausse.

Un simple ``SELECT`` **en lecture seule** sur ``users``, une table sans aucun
rapport, tenu trois secondes, faisait échouer 0007 dès son premier index ::

    asyncpg.exceptions.LockNotAvailableError:
      canceling statement due to lock timeout
    [SQL: CREATE INDEX CONCURRENTLY ... ON ai_calls (created_at)]

``CREATE INDEX CONCURRENTLY`` attend la fin des transactions en cours au
moment où il démarre, et cette attente est soumise au ``lock_timeout``. Sur
une base en production — ``pg_dump``, requête analytique, ``idle in
transaction`` oublié — la condition est permanente. Onze index, chacun
devant franchir la même porte.

Et la borne ne protégeait rien : ``CREATE INDEX CONCURRENTLY`` ne prend qu'un
``SHARE UPDATE EXCLUSIVE`` et **ne bloque aucune écriture**. Elle n'évitait
aucune indisponibilité, elle ne coûtait que l'échec du déploiement.

Ce test ne peut pas exister en unitaire : il lui faut deux connexions
simultanées à un vrai serveur, dont une qui tient une transaction ouverte.
C'est exactement le genre de propriété qu'une doublure en mémoire déclare
vraie sans l'avoir vérifiée.
"""

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration

#: Plus long que le ``lock_timeout`` de 5 s : sans correctif, la migration
#: renonce avant que ce lecteur ait fini.
MAINTIEN_SECONDES = 8


class TestUnLecteurLongNeFaitPasEchouerLaMigration:
    async def test_creer_un_index_concurrent_attend_au_lieu_de_renoncer(
        self, database_url: str
    ) -> None:
        """Reproduit la condition exacte : une transaction en LECTURE SEULE,
        sur une table sans rapport avec l'index visé."""
        lecteur = create_async_engine(database_url, poolclass=None)
        migrateur = create_async_engine(database_url, poolclass=None)

        async def tenir_une_transaction() -> None:
            async with lecteur.connect() as connexion:
                await connexion.execute(text("SELECT count(*) FROM users"))
                await asyncio.sleep(MAINTIEN_SECONDES)

        async def creer_lindex() -> None:
            async with migrateur.connect() as connexion:
                await connexion.execution_options(isolation_level="AUTOCOMMIT")
                # Ce que pose ``env.py`` sur la connexion de migration.
                await connexion.execute(text("SET lock_timeout = '5s'"))
                # Ce que fait 0007 dans son ``autocommit_block``.
                await connexion.execute(text("SET lock_timeout = 0"))
                await connexion.execute(
                    text(
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                        "ix_test_contention ON ai_calls (created_at)"
                    )
                )

        try:
            tenue = asyncio.create_task(tenir_une_transaction())
            await asyncio.sleep(1)  # la transaction est ouverte avant qu'on crée
            await creer_lindex()
            await tenue

            async with migrateur.connect() as connexion:
                invalide = (
                    await connexion.execute(
                        text(
                            "SELECT NOT i.indisvalid FROM pg_class c "
                            "JOIN pg_index i ON i.indexrelid = c.oid "
                            "WHERE c.relname = 'ix_test_contention'"
                        )
                    )
                ).scalar_one()
                assert invalide is False, "index créé mais INVALIDE"
        finally:
            async with migrateur.connect() as connexion:
                await connexion.execution_options(isolation_level="AUTOCOMMIT")
                await connexion.execute(
                    text("DROP INDEX CONCURRENTLY IF EXISTS ix_test_contention")
                )
            await lecteur.dispose()
            await migrateur.dispose()

    async def test_sans_la_levee_la_creation_echoue_bien(
        self, database_url: str
    ) -> None:
        """La contrepartie : ce test vaut ce que vaut sa prémisse.

        S'il ne prouvait pas que le ``lock_timeout`` fait ÉCHOUER la création
        quand on ne le lève pas, le test précédent pourrait passer au vert
        pour une raison sans rapport — un serveur sans contention, une
        version de PostgreSQL qui n'attend plus.
        """
        lecteur = create_async_engine(database_url, poolclass=None)
        migrateur = create_async_engine(database_url, poolclass=None)

        async def tenir_une_transaction() -> None:
            async with lecteur.connect() as connexion:
                await connexion.execute(text("SELECT count(*) FROM users"))
                await asyncio.sleep(MAINTIEN_SECONDES)

        try:
            tenue = asyncio.create_task(tenir_une_transaction())
            await asyncio.sleep(1)

            with pytest.raises(Exception, match="lock timeout"):
                async with migrateur.connect() as connexion:
                    await connexion.execution_options(isolation_level="AUTOCOMMIT")
                    await connexion.execute(text("SET lock_timeout = '5s'"))
                    await connexion.execute(
                        text(
                            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                            "ix_test_contention_ko ON ai_calls (created_at)"
                        )
                    )
            await tenue
        finally:
            async with migrateur.connect() as connexion:
                await connexion.execution_options(isolation_level="AUTOCOMMIT")
                await connexion.execute(
                    text("DROP INDEX CONCURRENTLY IF EXISTS ix_test_contention_ko")
                )
            await lecteur.dispose()
            await migrateur.dispose()

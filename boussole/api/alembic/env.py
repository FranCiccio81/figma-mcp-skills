"""Environnement Alembic (async, asyncpg)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Importe les modèles pour peupler Base.metadata (autogenerate).
#
# ⚠️ TOUS les modules, et ce n'est pas du zèle. Seul ``auth`` était importé :
# ``Base.metadata`` ne connaissait que 3 tables sur 37, et les 34 autres
# passaient pour « supprimées du code ». Un simple
#
#     alembic revision --autogenerate -m "..."
#
# produisait un ``upgrade()`` contenant **33 ``drop_table``** — job_postings,
# profiles, match_results, applications, audit_log… La commande qu'on tape
# pour écrire la migration suivante écrivait la destruction de la base.
# Reproduit en revue avant déploiement.
#
# La liste vit dans ``app/models_registry.py`` — un seul endroit, partagé avec
# le processus Celery, qui souffrait exactement du même oubli.
from app import models_registry as _models  # noqa: F401
from app.core.config import get_settings
from app.core.db import Base
from app.core.migration_policy import include_object

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Mode offline : émet le SQL sans connexion."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    # Une migration ne doit JAMAIS attendre un verrou indéfiniment.
    #
    # Mesuré en revue : une requête de lecture de 60 s sur ``ai_calls`` — un
    # `pg_dump`, une requête analytique — suffit à transformer une migration
    # de 4 s en **58 s d'écritures bloquées**. Ce n'est pas le lecteur qui
    # bloque l'écrivain : c'est la demande d'ACCESS EXCLUSIVE de la migration
    # qui crée la file d'attente derrière elle. Sans borne, un
    # ``idle in transaction`` oublié fige l'application sans limite.
    #
    # Échouer vite est le bon comportement : le déploiement est rejoué, alors
    # qu'une indisponibilité en écriture ne se rattrape pas.
    connection.exec_driver_sql("SET lock_timeout = '5s'")
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine = create_async_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

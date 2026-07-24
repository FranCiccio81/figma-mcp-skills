"""Schéma initial Boussole — exécute initial-schema.sql (source de vérité).

Revision ID: 0001
Revises: None

Le fichier ``sql/0001_initial.sql`` est la copie conforme de
``docs`` / ``cv-job-matching/initial-schema.sql`` (extensions pgvector,
pg_trgm, unaccent, citext + schéma complet + trigger tsvector).

Le driver asyncpg n'accepte pas plusieurs commandes dans une même requête
préparée : le script est découpé en instructions individuelles en respectant
les blocs dollar-quotés (``$$ … $$`` des fonctions plpgsql).
"""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).parent / "sql" / "0001_initial.sql"


def _split_sql_statements(sql: str) -> list[str]:
    """Découpe un script SQL sur ';' hors blocs dollar-quotés ($$ … $$)."""
    statements: list[str] = []
    buffer: list[str] = []
    in_dollar = False
    i = 0
    while i < len(sql):
        if sql.startswith("$$", i):
            in_dollar = not in_dollar
            buffer.append("$$")
            i += 2
            continue
        char = sql[i]
        if char == ";" and not in_dollar:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
        else:
            buffer.append(char)
        i += 1
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def upgrade() -> None:
    for statement in _split_sql_statements(_SQL_FILE.read_text(encoding="utf-8")):
        op.execute(statement)


def downgrade() -> None:
    """DEV-ONLY — détruit tout le schéma public (données comprises).

    Jamais exécuté en production : le rollback prod se fait par restauration
    (PITR, D19). Documenté dans le runbook de déploiement.
    """
    op.execute("DROP SCHEMA public CASCADE")
    op.execute("CREATE SCHEMA public")
    op.execute("GRANT ALL ON SCHEMA public TO public")

"""La portée du ``lock_timeout`` des migrations.

``alembic/env.py`` pose ``lock_timeout = 5s`` sur la connexion de migration.
La justification est juste — un ``ALTER TABLE`` qui attend un verrou met
toutes les écritures en file derrière lui — mais la PORTÉE était fausse.

Mesuré en revue avant déploiement, contre un PostgreSQL réel : un ``SELECT``
en lecture seule sur ``users``, table sans rapport, tenu trois secondes,
faisait échouer 0007 dès son premier index ::

    asyncpg.exceptions.LockNotAvailableError:
      canceling statement due to lock timeout
    [SQL: CREATE INDEX CONCURRENTLY ... ON ai_calls (created_at)]

``CREATE INDEX CONCURRENTLY`` attend la fin des transactions en cours, et
cette attente est soumise au ``lock_timeout``. Or il ne prend qu'un
``SHARE UPDATE EXCLUSIVE`` et **ne bloque aucune écriture** : la borne
n'évitait aucune indisponibilité et ne coûtait que l'échec du déploiement.

Le comportement lui-même est vérifié contre un vrai serveur dans
``tests/integration/test_migration_sous_contention.py`` — deux connexions
simultanées, dont une qui tient une transaction. Ce fichier-ci est la garde
rapide : il tourne à chaque ``make test`` et attrape la disparition de la
levée, ou une future migration concurrente qui l'oublierait.
"""

import re
from pathlib import Path

import pytest

VERSIONS = Path(__file__).resolve().parents[3] / "alembic" / "versions"

#: Ce qui, dans une migration, attend la fin des transactions en cours.
_CONCURRENT = re.compile(r"(CREATE|DROP) INDEX CONCURRENTLY", re.IGNORECASE)

_LEVEE = 'op.execute("SET lock_timeout = 0")'


def _migrations_concurrentes() -> list[Path]:
    return [
        chemin
        for chemin in sorted(VERSIONS.glob("[0-9][0-9][0-9][0-9]_*.py"))
        if _CONCURRENT.search(chemin.read_text(encoding="utf-8"))
    ]


class TestTouteMigrationConcurrenteLeveLaBorne:
    def test_il_y_en_a_au_moins_une(self) -> None:
        """Sans quoi les tests ci-dessous passeraient sur l'ensemble vide."""
        assert _migrations_concurrentes()

    @pytest.mark.parametrize(
        "chemin", _migrations_concurrentes(), ids=lambda p: p.stem
    )
    def test_elle_leve_le_lock_timeout(self, chemin: Path) -> None:
        source = chemin.read_text(encoding="utf-8")
        assert _LEVEE in source, (
            f"{chemin.name} crée un index CONCURRENTLY sans lever le "
            "lock_timeout de 5 s posé par env.py : la migration échouera dès "
            "qu'une transaction de plus de 5 s est ouverte, y compris un "
            "SELECT en lecture seule sur une table sans rapport"
        )

    @pytest.mark.parametrize(
        "chemin", _migrations_concurrentes(), ids=lambda p: p.stem
    )
    def test_laller_et_le_retour_sont_traites_pareil(self, chemin: Path) -> None:
        """``downgrade`` fait la même attente pour la même raison."""
        source = chemin.read_text(encoding="utf-8")
        appels = len(re.findall(r"^\s+_sans_lock_timeout\(\)", source, re.MULTILINE))
        assert appels == 2, f"{chemin.name} : {appels} appel(s), attendu 2"


class TestLaBorneResteEnVigueurAilleurs:
    """C'est la portée qui était fausse, pas le principe : une migration
    transactionnelle qui attend un ACCESS EXCLUSIVE doit toujours renoncer
    vite plutôt que mettre les écritures en file."""

    def test_env_py_pose_toujours_la_borne(self) -> None:
        env = (VERSIONS.parent / "env.py").read_text(encoding="utf-8")
        assert "SET lock_timeout = '5s'" in env

    def test_la_nuance_est_ecrite_la_ou_elle_se_lit(self) -> None:
        """Le commentaire d'origine justifiait les 5 s par un cas qui ne
        s'applique pas aux index concurrents. Sans la nuance, quelqu'un
        retirera la levée en la prenant pour une négligence."""
        env = (VERSIONS.parent / "env.py").read_text(encoding="utf-8")
        assert "CONCURRENTLY" in env

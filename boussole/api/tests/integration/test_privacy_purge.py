"""Purge RGPD de bout en bout — plus AUCUNE ligne personnelle en base.

Régression visée : le ``purge_user`` du module ``jobs`` a longtemps été un
stub. Les tests unitaires du registre vérifiaient que chaque module était
APPELÉ ; aucun ne vérifiait l'EFFET. Un compte supprimé conservait donc ses
``saved_jobs`` — une donnée personnelle survivant à l'exercice du droit à
l'effacement (art. 17), invisible pour toute la suite unitaire.

La vérification ici ne fait AUCUNE liste en dur : l'inventaire des tables est
lu dans ``information_schema`` sur le schéma réellement migré, et le test
échoue dès qu'une table portant une colonne ``user_id`` conserve la moindre
ligne de l'utilisateur purgé. Une future table personnelle oubliée dans le
registre fait tomber ce test le jour de sa migration.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.storage import LocalDiskStorage, ObjectNotFoundError
from app.modules.privacy.purge_runner import purge_due_accounts
from app.modules.privacy.registry import DATA_MODULE_NAMES, DEFAULT_REGISTRY
from app.modules.privacy.repository import SqlAlchemyPrivacyRepository
from tests.integration.conftest import DEFAULT_PASSWORD, register_and_login
from tests.integration.factories import (
    POPULATED_TABLES,
    make_due_deletion_request,
    make_posting,
    make_user,
    populate_all_modules,
)

pytestmark = pytest.mark.integration

#: Tables portant ``user_id`` et CONSERVÉES sciemment après la purge — toute
#: autre table doit être vide. Chaque entrée est une décision documentée, pas
#: une tolérance : ajouter une ligne ici doit coûter une justification.
TABLES_CONSERVEES: dict[str, str] = {
    # auth/purge.py : les consentements sont une preuve légale ; ils ne
    # référencent plus qu'un identifiant technique anonymisé.
    "consents": "preuve légale du consentement (auth/purge.py)",
    # La demande de suppression elle-même est la trace de l'effacement
    # (statut « purged ») — elle ne porte aucune donnée personnelle.
    "deletion_requests": "trace de l'exercice du droit à l'effacement",
}

#: Tables personnelles SANS colonne ``user_id`` (rattachées par profile_id,
#: application_id, cv_document_id…) — invisibles de l'inventaire automatique,
#: donc vérifiées nommément.
TABLES_ENFANTS = (
    "profile_experiences",
    "profile_educations",
    "profile_skills",
    "profile_languages",
    "extraction_runs",
    "application_events",
    "match_results",
    "match_explanations",
)


async def _tables_avec_user_id(engine: AsyncEngine) -> tuple[str, ...]:
    """Inventaire RÉEL : toute table du schéma portant une colonne ``user_id``."""
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = 'user_id' "
                "ORDER BY table_name"
            )
        )
        return tuple(row[0] for row in rows)


async def _count(engine: AsyncEngine, sql: str, **params: object) -> int:
    async with engine.connect() as conn:
        value = await conn.scalar(text(sql), params)
    return int(value or 0)


@pytest.fixture
async def compte_complet(
    db_session: AsyncSession, object_storage: LocalDiskStorage
) -> dict[str, object]:
    """Un compte avec des données dans TOUS les modules du registre + purge échue."""
    user = await make_user(db_session)
    posting = await make_posting(db_session, title="Data Engineer")
    identifiants = await populate_all_modules(
        db_session, user, storage=object_storage, posting=posting
    )
    await make_due_deletion_request(db_session, user.id)
    return {"user_id": user.id, "posting_id": posting.id, **identifiants}


class TestInventaireDeDepart:
    """Sans données de départ, le test de purge ne prouverait rien."""

    def test_le_jeu_de_donnees_couvre_tout_le_registre(self) -> None:
        couverts = set(POPULATED_TABLES) - {"privacy"}
        assert couverts == set(DATA_MODULE_NAMES), (
            "chaque module du registre doit avoir des données avant la purge — "
            "sinon la purge « réussit » sur du vide"
        )

    async def test_les_tables_personnelles_sont_bien_peuplees(
        self, db_engine: AsyncEngine, compte_complet: dict[str, object]
    ) -> None:
        user_id = compte_complet["user_id"]
        for tables in POPULATED_TABLES.values():
            for table in tables:
                total = await _count(db_engine, f'SELECT count(*) FROM "{table}"')
                assert total > 0, f"{table} devrait contenir des données avant la purge"
        assert user_id is not None


class TestPurgeDeBoutEnBout:
    async def test_aucune_ligne_personnelle_ne_subsiste(
        self,
        db_engine: AsyncEngine,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_complet: dict[str, object],
    ) -> None:
        """Le test qui aurait attrapé le stub ``jobs.purge_user``."""
        user_id = compte_complet["user_id"]

        outcomes = await purge_due_accounts(
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        assert len(outcomes) == 1
        assert outcomes[0].failed_modules == (), "aucun module ne doit échouer"
        assert outcomes[0].purged is True

        restantes: dict[str, int] = {}
        for table in await _tables_avec_user_id(db_engine):
            if table in TABLES_CONSERVEES:
                continue
            restantes[table] = await _count(
                db_engine,
                f'SELECT count(*) FROM "{table}" WHERE user_id = :user_id',
                user_id=user_id,
            )

        assert restantes, "l'inventaire information_schema ne doit pas être vide"
        assert all(total == 0 for total in restantes.values()), (
            "des données personnelles survivent à la purge : "
            f"{ {table: n for table, n in restantes.items() if n} }"
        )

    async def test_les_tables_enfants_sont_vides(
        self,
        db_engine: AsyncEngine,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_complet: dict[str, object],
    ) -> None:
        """Sous-ressources rattachées par profile_id/application_id/cv_document_id."""
        await purge_due_accounts(
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        restantes = {
            table: await _count(db_engine, f'SELECT count(*) FROM "{table}"')
            for table in TABLES_ENFANTS
        }

        assert all(total == 0 for total in restantes.values()), (
            f"sous-ressources personnelles restantes : "
            f"{ {t: n for t, n in restantes.items() if n} }"
        )

    async def test_la_ligne_users_est_anonymisee_et_l_audit_delie(
        self,
        db_engine: AsyncEngine,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_complet: dict[str, object],
    ) -> None:
        """``users`` survit anonymisée (RM-Q-2) ; ``audit_log`` perd le lien."""
        user_id = compte_complet["user_id"]

        await purge_due_accounts(
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        async with db_engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT email, password_hash, deleted_at FROM users WHERE id = :id"
                    ),
                    {"id": user_id},
                )
            ).one()
            lies = await conn.scalar(
                text("SELECT count(*) FROM audit_log WHERE user_id = :id"), {"id": user_id}
            )
            anonymises = await conn.scalar(
                text("SELECT count(*) FROM audit_log WHERE subject_key IS NOT NULL")
            )

        email, password_hash, deleted_at = row
        assert email == f"purged+{user_id}@purged.invalid"
        assert password_hash is None
        assert deleted_at is not None
        assert lies == 0, "aucune ligne d'audit ne doit rester reliée à l'utilisateur"
        assert anonymises >= 1, "les lignes d'audit conservées portent un subject_key"

    async def test_les_objets_stockes_sont_supprimes(
        self,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_complet: dict[str, object],
    ) -> None:
        """Fichiers CV, texte extrait, sorties d'extraction et archives d'export."""
        user_id = compte_complet["user_id"]
        cles = (
            f"cv/{user_id}/original.pdf",
            f"cv/{user_id}/texte.txt",
            f"cv/{user_id}/extraction.json",
            f"privacy-exports/{user_id}/archive.json",
        )
        for cle in cles:
            assert object_storage.get(cle), "objet attendu avant la purge"

        await purge_due_accounts(
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        for cle in cles:
            with pytest.raises(ObjectNotFoundError):
                object_storage.get(cle)

    async def test_les_donnees_mutualisees_survivent(
        self,
        db_engine: AsyncEngine,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_complet: dict[str, object],
    ) -> None:
        """Offres, sources et référentiels sont publics : jamais supprimés."""
        await purge_due_accounts(
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        for table in ("job_postings", "sectors", "skills"):
            assert await _count(db_engine, f'SELECT count(*) FROM "{table}"') > 0, (
                f"{table} contient des données mutualisées : la purge d'un compte "
                "ne doit pas y toucher"
            )

    async def test_purge_idempotente(
        self,
        db_engine: AsyncEngine,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_complet: dict[str, object],
    ) -> None:
        """Second passage : la demande est ``purged``, plus rien à faire."""
        await purge_due_accounts(
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )
        secondes = await purge_due_accounts(
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        assert secondes == []
        statut = await _count(
            db_engine, "SELECT count(*) FROM deletion_requests WHERE status = 'purged'"
        )
        assert statut == 1


async def test_ai_calls_anonymise_sans_perdre_les_metriques(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    object_storage: LocalDiskStorage,
    compte_complet: dict[str, object],
) -> None:
    """``ai_calls`` : anonymisation (``user_id → NULL``), pas suppression.

    Choix documenté (``app/modules/ai_calls/purge.py``) : la ligne ne porte
    aucune donnée personnelle hors ce lien, et les métriques agrégées (coût,
    latence, taux d'échec) restent nécessaires à l'exploitation. Le test
    vérifie donc les DEUX moitiés : plus aucun lien vers la personne, et la
    ligne toujours là.
    """
    user_id = compte_complet["user_id"]
    avant = await _count(db_engine, "SELECT count(*) FROM ai_calls")
    assert avant == 1

    await purge_due_accounts(
        repository=SqlAlchemyPrivacyRepository(db_session),
        storage=object_storage,
        registry=DEFAULT_REGISTRY,
    )

    assert (
        await _count(
            db_engine,
            "SELECT count(*) FROM ai_calls WHERE user_id = :user_id",
            user_id=user_id,
        )
        == 0
    )
    assert await _count(db_engine, "SELECT count(*) FROM ai_calls") == 1


class TestSuppressionDeCompteViaApi:
    """La demande de suppression passe par la route réelle (DELETE /account)."""

    async def test_delete_account_cree_une_demande_pending(
        self, api_client, db_engine: AsyncEngine
    ) -> None:
        user_id = await register_and_login(api_client)
        headers = {"X-CSRF-Token": api_client.cookies["boussole_csrf"]}

        response = await api_client.request(
            "DELETE",
            "/api/v1/account",
            json={"password": DEFAULT_PASSWORD},
            headers=headers,
        )

        assert response.status_code == 204, response.text
        pending = await _count(
            db_engine,
            "SELECT count(*) FROM deletion_requests "
            "WHERE user_id = :user_id AND status = 'pending'",
            user_id=user_id,
        )
        assert pending == 1
        deleted_at = await _count(
            db_engine,
            "SELECT count(*) FROM users WHERE id = :user_id AND deleted_at IS NOT NULL",
            user_id=user_id,
        )
        assert deleted_at == 1

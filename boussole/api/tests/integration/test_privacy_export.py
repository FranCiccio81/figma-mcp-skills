"""Export RGPD de bout en bout : demande → archive → relecture → purge.

Le chemin complet n'existe qu'en intégration : la demande passe par la route
réelle (quota, idempotence), l'archive est assemblée par le VRAI registre
(chaque module lit ses tables en base), écrite par le VRAI ``LocalDiskStorage``,
puis relue via le lien signé de la route de téléchargement. Les tests
unitaires du module privacy n'exercent que des fakes des deux côtés :
repository en mémoire ET modules du registre remplacés par des callables.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import LocalDiskStorage, ObjectNotFoundError
from app.modules.auth.models import User
from app.modules.privacy.export_builder import build_export
from app.modules.privacy.models import PrivacyExport
from app.modules.privacy.purge_runner import purge_expired_exports
from app.modules.privacy.registry import DATA_MODULE_NAMES, DEFAULT_REGISTRY
from app.modules.privacy.repository import SqlAlchemyPrivacyRepository
from app.modules.privacy.router import get_export_enqueuer
from tests.integration.conftest import register_and_login
from tests.integration.factories import make_posting, populate_all_modules

pytestmark = pytest.mark.integration


@pytest.fixture
def exports_enqueues(api_app: FastAPI) -> list[uuid.UUID]:
    """Espion de mise en file : le worker Celery n'est pas démarré ici 🟡."""
    enqueued: list[uuid.UUID] = []

    def spy(export_id: uuid.UUID) -> None:
        enqueued.append(export_id)

    api_app.dependency_overrides[get_export_enqueuer] = lambda: spy
    return enqueued


@pytest.fixture
async def compte_avec_donnees(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    object_storage: LocalDiskStorage,
) -> uuid.UUID:
    """Compte créé par la vraie route ``/auth/register``, peuplé dans tous les modules."""
    user_id = await register_and_login(api_client)
    user = await db_session.get(User, user_id)
    assert user is not None
    posting = await make_posting(db_session, title="Data Engineer")
    await populate_all_modules(db_session, user, storage=object_storage, posting=posting)
    return user_id


class TestExportDeBoutEnBout:
    async def test_demande_puis_archive_relue_par_le_lien_signe(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        exports_enqueues: list[uuid.UUID],
        compte_avec_donnees: uuid.UUID,
    ) -> None:
        """POST /privacy/export → build_export → GET statut → GET téléchargement."""
        demande = await api_client.post(
            "/api/v1/privacy/export",
            headers={"X-CSRF-Token": api_client.cookies["boussole_csrf"]},
        )
        assert demande.status_code == 202, demande.text
        export_id = uuid.UUID(demande.json()["id"])
        assert exports_enqueues == [export_id], "la tâche d'assemblage doit être mise en file"

        resultat = await build_export(
            export_id,
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        assert resultat.status == "ready"
        assert resultat.incomplete_modules == (), (
            "un module du registre a échoué à exporter ses données en base"
        )

        statut = await api_client.get(f"/api/v1/privacy/exports/{export_id}")
        assert statut.status_code == 200, statut.text
        assert statut.json()["status"] == "ready"
        download_url = statut.json()["download_url"]
        assert download_url

        telechargement = await api_client.get(download_url)
        assert telechargement.status_code == 200, telechargement.text
        archive = json.loads(telechargement.content)

        assert archive["user_id"] == str(compte_avec_donnees)
        assert set(archive["modules"]) == set(DATA_MODULE_NAMES)
        assert "incomplete_modules" not in archive

    async def test_l_archive_contient_les_donnees_de_chaque_module(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_avec_donnees: uuid.UUID,
    ) -> None:
        """Art. 20 : les données réellement en base se retrouvent dans l'archive."""
        record = await SqlAlchemyPrivacyRepository(db_session).create_export(
            compte_avec_donnees, datetime.now(UTC)
        )

        await build_export(
            record.id,
            repository=SqlAlchemyPrivacyRepository(db_session),
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        archive = json.loads(
            object_storage.get(f"privacy-exports/{compte_avec_donnees}/{record.id}.json")
        )
        modules = archive["modules"]

        assert modules["auth"]["user"]["email"] == "camille@example.eu"
        kinds = {consent["kind"] for consent in modules["auth"]["consents"]}
        assert kinds == {"terms", "privacy"}
        assert modules["profiles"]["profile"]["headline"] == "Développeuse backend"
        assert modules["profiles"]["cv_documents"][0]["filename"] == "cv-camille.pdf"
        assert modules["preferences"]["preferences"]["salary_min"] == 45000
        assert len(modules["jobs"]["saved_jobs"]) == 1, (
            "les offres sauvegardées sont des données personnelles (art. 20)"
        )
        assert len(modules["matching"]["match_results"]) == 1
        assert len(modules["explanations"]["match_explanations"]) == 1
        assert len(modules["generation"]["generated_documents"]) == 1
        assert len(modules["applications"]["applications"]) == 1
        assert modules["applications"]["applications"][0]["events"], "historique inclus"

    async def test_export_marque_pret_avec_expiration(
        self,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_avec_donnees: uuid.UUID,
    ) -> None:
        """La ligne ``privacy_exports`` porte le statut, la clé et l'expiration J+7."""
        repository = SqlAlchemyPrivacyRepository(db_session)
        record = await repository.create_export(compte_avec_donnees, datetime.now(UTC))

        await build_export(
            record.id,
            repository=repository,
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        relu = await repository.get_export(record.id)
        assert relu is not None
        assert relu.status == "ready"
        assert relu.file_key == f"privacy-exports/{compte_avec_donnees}/{record.id}.json"
        assert relu.expires_at is not None
        assert relu.expires_at > datetime.now(UTC) + timedelta(days=6)


class TestPurgeDesArchives:
    async def test_archive_expiree_supprimee_objet_et_ligne(
        self,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_avec_donnees: uuid.UUID,
    ) -> None:
        """Le lien expire à J+7 : l'OBJET doit disparaître aussi (minimisation D09)."""
        repository = SqlAlchemyPrivacyRepository(db_session)
        # Le compte de test porte déjà une archive de démonstration : on isole
        # le cas pour pouvoir compter exactement ce que la tâche supprime.
        await repository.delete_exports_for_user(compte_avec_donnees)
        record = await repository.create_export(compte_avec_donnees, datetime.now(UTC))
        resultat = await build_export(
            record.id,
            repository=repository,
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )
        assert resultat.file_key is not None

        outcome = await purge_expired_exports(
            repository=repository,
            storage=object_storage,
            now=datetime.now(UTC) + timedelta(days=8),
        )

        assert (outcome.deleted_objects, outcome.deleted_rows) == (1, 1)
        assert outcome.failed_keys == ()
        with pytest.raises(ObjectNotFoundError):
            object_storage.get(resultat.file_key)
        restantes = (
            (
                await db_session.execute(
                    select(PrivacyExport).where(PrivacyExport.id == record.id)
                )
            )
            .scalars()
            .all()
        )
        assert restantes == []

    async def test_archive_encore_valide_conservee(
        self,
        db_session: AsyncSession,
        object_storage: LocalDiskStorage,
        compte_avec_donnees: uuid.UUID,
    ) -> None:
        repository = SqlAlchemyPrivacyRepository(db_session)
        record = await repository.create_export(compte_avec_donnees, datetime.now(UTC))
        await build_export(
            record.id,
            repository=repository,
            storage=object_storage,
            registry=DEFAULT_REGISTRY,
        )

        outcome = await purge_expired_exports(
            repository=repository, storage=object_storage, now=datetime.now(UTC)
        )

        assert (outcome.deleted_objects, outcome.deleted_rows) == (0, 0)
        assert await repository.get_export(record.id) is not None

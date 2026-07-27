"""Tests purge / export RGPD (D21) — cv_documents inclus dans le module profiles.

Repositories et stockage injectés (fakes en mémoire) ; le chemin par défaut
(session SQLAlchemy via la fabrique globale) relève des tests d'intégration.
"""

import uuid
from datetime import date

from app.modules.profiles import purge as profiles_purge
from app.modules.profiles.cv.models import CvDocument, ExtractionRun
from app.modules.profiles.cv.service import PDF_MIME
from tests.unit.cv.conftest import InMemoryCvRepository, InMemoryObjectStorage
from tests.unit.profiles.conftest import InMemoryProfilesRepository, make_profile


def _seed_user(
    profiles: InMemoryProfilesRepository,
    cv_repository: InMemoryCvRepository,
    storage: InMemoryObjectStorage,
    user_id: uuid.UUID,
) -> CvDocument:
    profiles.add(
        make_profile(
            user_id,
            skills=[("Python", "user_input", 1.0)],
            experiences=[(date(2020, 1, 1), None, "user_input")],
        )
    )
    document = CvDocument(
        id=uuid.uuid4(),
        user_id=user_id,
        file_key=f"cv/{user_id}/doc/original.pdf",
        filename="cv.pdf",
        mime_type=PDF_MIME,
        size_bytes=1000,
        status="parsed",
        raw_text_key=f"cv/{user_id}/doc/raw_text.txt",
    )
    run = ExtractionRun(
        id=uuid.uuid4(),
        cv_document_id=document.id,
        prompt_version="extract_cv/1.0.0",
        model="claude-sonnet-5",
        status="success",
        output_key=f"cv/{user_id}/doc/extraction/run.json",
    )
    cv_repository.documents[document.id] = document
    cv_repository.runs.append(run)
    storage.put(document.file_key, b"%PDF- fichier")
    assert document.raw_text_key is not None
    storage.put(document.raw_text_key, b"texte brut")
    assert run.output_key is not None
    storage.put(run.output_key, b"{}")
    return document


class TestProfilesPurgeWithCv:
    async def test_purge_removes_documents_runs_storage_and_profile(
        self,
        profiles_repository: InMemoryProfilesRepository,
        cv_repository: InMemoryCvRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        user, other = uuid.uuid4(), uuid.uuid4()
        _seed_user(profiles_repository, cv_repository, storage, user)
        other_doc = _seed_user(profiles_repository, cv_repository, storage, other)

        await profiles_purge.purge_user(
            user,
            cv_repository=cv_repository,
            profiles_repository=profiles_repository,
            storage=storage,
        )

        # Documents + runs + profil de l'utilisateur purgés…
        assert await cv_repository.list_for_user(user) == []
        assert len(cv_repository.runs) == 1  # seul le run de l'autre utilisateur reste
        assert await profiles_repository.get_by_user(user) is None
        # … objets stockés supprimés (fichier, texte brut RM-B-7, sortie)…
        assert not any(str(user) in key for key in storage.objects)
        # … et RIEN de l'autre utilisateur n'est touché.
        assert len(await cv_repository.list_for_user(other)) == 1
        assert storage.objects[other_doc.file_key] == b"%PDF- fichier"
        assert await profiles_repository.get_by_user(other) is not None

    async def test_purge_is_idempotent(
        self,
        profiles_repository: InMemoryProfilesRepository,
        cv_repository: InMemoryCvRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        user = uuid.uuid4()
        _seed_user(profiles_repository, cv_repository, storage, user)
        for _ in range(2):  # double purge : aucun échec
            await profiles_purge.purge_user(
                user,
                cv_repository=cv_repository,
                profiles_repository=profiles_repository,
                storage=storage,
            )
        assert await cv_repository.list_for_user(user) == []

    async def test_export_includes_cv_documents_metadata_only(
        self,
        profiles_repository: InMemoryProfilesRepository,
        cv_repository: InMemoryCvRepository,
        storage: InMemoryObjectStorage,
    ) -> None:
        user = uuid.uuid4()
        document = _seed_user(profiles_repository, cv_repository, storage, user)

        export = await profiles_purge.export_user(
            user,
            cv_repository=cv_repository,
            profiles_repository=profiles_repository,
        )

        assert export["profile"]["skills"][0]["label"] == "Python"
        (cv_export,) = export["cv_documents"]
        assert cv_export["id"] == str(document.id)
        assert cv_export["filename"] == "cv.pdf"
        assert cv_export["status"] == "parsed"
        # Métadonnées uniquement : jamais le binaire ni les clés de stockage.
        assert "file_key" not in cv_export
        assert "raw_text_key" not in cv_export

    async def test_export_without_data_is_empty(
        self,
        profiles_repository: InMemoryProfilesRepository,
        cv_repository: InMemoryCvRepository,
    ) -> None:
        export = await profiles_purge.export_user(
            uuid.uuid4(),
            cv_repository=cv_repository,
            profiles_repository=profiles_repository,
        )
        assert export == {}

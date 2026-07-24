"""Tests du service d'ingestion : idempotence, dédup étage 1, fusion,
expiration (07 §4.4, §4.6, §6) — store en mémoire, aucun réseau ni base."""

import uuid
from datetime import UTC, datetime, timedelta

from app.ai.providers.fake import FakeProvider
from app.modules.ingestion.connectors.base import RawJob, RawLocation
from app.modules.ingestion.geocode import StaticGeocoder
from app.modules.ingestion.service import ingest_batch, mark_expired
from tests.unit.ingestion.conftest import InMemoryJobStore

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _raw(
    external_ref: str = "ft-1",
    *,
    company: str = "ACME SAS",
    title: str = "Data Engineer",
    description: str = "Nous recherchons un Data Engineer en CDI à Lyon. 45-55k€.",
    url: str = "https://example.test/ft-1",
    employer_ref: str | None = None,
    location: str = "Lyon",
    **overrides: object,
) -> RawJob:
    return RawJob(
        external_ref=external_ref,
        title=title,
        company=company,
        description=description,
        url=url,
        payload={"id": external_ref},
        employer_ref=employer_ref,
        locations=[RawLocation(label=location)],
        **overrides,  # type: ignore[arg-type]
    )


async def test_creation_offre_canonique(store: InMemoryJobStore) -> None:
    store.add_source("france-travail")
    report = await ingest_batch(
        "france-travail", [_raw()], store, geocoder=StaticGeocoder(), now=NOW
    )

    assert report.seen == 1
    assert report.created == 1
    assert report.errors == 0
    posting = next(iter(store.postings.values()))
    assert posting.contract == "permanent"  # règle CDI, conf 0.9
    assert float(posting.contract_conf) == 0.9
    assert (posting.salary_min, posting.salary_max) == (45000, 55000)
    assert posting.country_code == "FR"
    assert posting.status == "active"
    # job_source créée avec l'original_url (garantie produit)
    job_source = next(iter(store.job_sources.values()))
    assert job_source.original_url == "https://example.test/ft-1"


async def test_idempotence_meme_external_ref(store: InMemoryJobStore) -> None:
    store.add_source("france-travail")
    batch = [_raw()]
    await ingest_batch("france-travail", batch, store, now=NOW)
    report2 = await ingest_batch("france-travail", batch, store, now=NOW + timedelta(hours=2))

    # Rejouer le flux ne crée ni doublon d'offre ni doublon de job_source.
    assert report2.updated == 1
    assert report2.created == 0
    assert len(store.postings) == 1
    assert len(store.job_sources) == 1
    posting = next(iter(store.postings.values()))
    assert posting.last_seen_at == NOW + timedelta(hours=2)


async def test_dedup_etage1_rattache_une_deuxieme_source(store: InMemoryJobStore) -> None:
    store.add_source("greenhouse", kind="ats_feed")
    store.add_source("lever", kind="ats_feed")

    # Même employeur, même titre, même ville, même référence employeur
    # → même dedup_hash malgré des external_ref et URLs différents.
    job_a = _raw("gh-1", employer_ref="REQ-7", url="https://boards.example/gh-1")
    job_b = _raw("lv-9", company="Groupe ACME", employer_ref="REQ-7",
                 url="https://jobs.example/lv-9")

    await ingest_batch("greenhouse", [job_a], store, now=NOW)
    report = await ingest_batch("lever", [job_b], store, now=NOW + timedelta(hours=1))

    assert report.attached_stage1 == 1
    assert len(store.postings) == 1  # une seule offre canonique
    assert len(store.job_sources) == 2  # deux job_sources rattachées
    # Les DEUX liens d'origine sont conservés (07 §6.3.1).
    urls = {js.original_url for js in store.job_sources.values()}
    assert urls == {"https://boards.example/gh-1", "https://jobs.example/lv-9"}


async def test_fusion_champ_plus_riche_gagne(store: InMemoryJobStore) -> None:
    store.add_source("greenhouse", kind="ats_feed")
    store.add_source("lever", kind="ats_feed")

    # Source A : description courte, pas de remote ni salaire.
    job_a = _raw(
        "gh-1", employer_ref="REQ-7",
        description="Data Engineer role. CDI.",
        url="https://boards.example/gh-1",
    )
    # Source B : description plus longue, remote structuré (conf 1.0).
    long_description = (
        "We are hiring a Data Engineer to build pipelines with Python and "
        "Airflow. This is a long and rich description of the role. CDI."
    )
    job_b = _raw(
        "lv-9", employer_ref="REQ-7",
        description=long_description,
        url="https://jobs.example/lv-9",
        remote="hybrid", remote_conf=1.0,
        salary_min=50000, salary_max=60000,
        salary_currency="EUR", salary_period="year", salary_conf=1.0,
    )

    await ingest_batch("greenhouse", [job_a], store, now=NOW)
    await ingest_batch("lever", [job_b], store, now=NOW + timedelta(hours=1))

    posting = next(iter(store.postings.values()))
    # NULL ← valeur entrante ; description la plus longue conservée.
    assert posting.remote == "hybrid"
    assert (posting.salary_min, posting.salary_max) == (50000, 60000)
    assert "Airflow" in posting.description_text


async def test_fusion_conflit_confiance_superieure_gagne(store: InMemoryJobStore) -> None:
    store.add_source("greenhouse", kind="ats_feed")
    store.add_source("lever", kind="ats_feed")

    # A : contrat par règle (0.9) ; B : contrat structuré divergent (1.0).
    job_a = _raw("gh-1", employer_ref="REQ-7",
                 description="Fixed-term contract, 12 months.",
                 url="https://a.example")
    job_b = _raw("lv-9", employer_ref="REQ-7",
                 description="Data Engineer role.",
                 url="https://b.example",
                 contract="permanent", contract_conf=1.0)

    await ingest_batch("greenhouse", [job_a], store, now=NOW)
    await ingest_batch("lever", [job_b], store, now=NOW + timedelta(hours=1))

    posting = next(iter(store.postings.values()))
    assert posting.contract == "permanent"  # 1.0 > 0.9 + epsilon
    assert float(posting.contract_conf) == 1.0


async def test_skills_et_langues_fusionnes_sans_doublon(store: InMemoryJobStore) -> None:
    store.add_source("france-travail")
    skill_id = uuid.uuid4()
    store.skill_aliases["javascript"] = skill_id

    job = _raw(skills=["JavaScript"], languages=[("en", "B2")])
    await ingest_batch("france-travail", [job], store, now=NOW)
    await ingest_batch("france-travail", [job], store, now=NOW + timedelta(hours=1))

    assert len(store.skills) == 1
    assert store.skills[0].skill_id == skill_id  # résolu via skill_aliases
    assert store.skills[0].label_raw == "JavaScript"  # label_raw conservé
    assert len(store.languages) == 1


async def test_erreur_item_narrete_pas_le_batch(store: InMemoryJobStore) -> None:
    store.add_source("france-travail")
    bad = _raw("bad")
    bad.title = None  # type: ignore[assignment]  # provoque une erreur de normalisation
    good = _raw("good", url="https://example.test/good")

    report = await ingest_batch("france-travail", [bad, good], store, now=NOW)

    assert report.errors == 1
    assert report.created == 1  # le second item passe (07 §4.5)


async def test_provider_fake_appele_en_secours(store: InMemoryJobStore) -> None:
    store.add_source("greenhouse", kind="ats_feed")
    provider = FakeProvider()
    # Aucun attribut résoluble par règles → étage 2 sollicité.
    job = _raw("gh-1", description="An opportunity to join our wonderful office.")
    await ingest_batch("greenhouse", [job], store, provider=provider, now=NOW)

    assert provider.calls
    assert provider.calls[0][0] == "extract_job"
    posting = next(iter(store.postings.values()))
    assert posting.contract is None  # FakeProvider : extraction vide → inconnu


# ------------------------------------------------------------------ expiration
async def test_expiration_mecanisme1_expires_at(store: InMemoryJobStore) -> None:
    store.add_source("france-travail")
    job = _raw(expires_at=NOW - timedelta(days=1))
    await ingest_batch("france-travail", [job], store, now=NOW - timedelta(days=10))

    report = await mark_expired(store, now=NOW)

    assert report.by_signal == 1
    posting = next(iter(store.postings.values()))
    assert posting.status == "expired"


async def test_expiration_mecanisme2_absence_deux_reconciliations(
    store: InMemoryJobStore,
) -> None:
    source = store.add_source("france-travail")
    await ingest_batch("france-travail", [_raw()], store, now=NOW)
    posting = next(iter(store.postings.values()))

    # 1re réconciliation sans l'offre : pas encore éteinte (seuil = 2).
    report1 = await mark_expired(
        store, now=NOW, source_id=source.id, present_external_refs=set()
    )
    assert report1.by_absence == 0
    assert posting.status == "active"

    # 2e réconciliation consécutive sans l'offre : mono-source → expirée.
    report2 = await mark_expired(
        store, now=NOW, source_id=source.id, present_external_refs=set()
    )
    assert report2.by_absence == 1
    assert posting.status == "expired"


async def test_expiration_multi_source_protege(store: InMemoryJobStore) -> None:
    source_a = store.add_source("greenhouse", kind="ats_feed")
    store.add_source("lever", kind="ats_feed")
    await ingest_batch(
        "greenhouse", [_raw("gh-1", employer_ref="REQ-7", url="https://a.example")],
        store, now=NOW,
    )
    await ingest_batch(
        "lever", [_raw("lv-9", employer_ref="REQ-7", url="https://b.example")],
        store, now=NOW,
    )
    posting = next(iter(store.postings.values()))

    # L'offre disparaît de Greenhouse (2 réconciliations) mais reste sur
    # Lever → l'offre canonique reste active (D13, 07 §4.6.2).
    for _ in range(2):
        await mark_expired(
            store, now=NOW, source_id=source_a.id, present_external_refs=set()
        )
    assert posting.status == "active"


async def test_expiration_presence_remet_le_compteur_a_zero(
    store: InMemoryJobStore,
) -> None:
    source = store.add_source("france-travail")
    await ingest_batch("france-travail", [_raw()], store, now=NOW)
    posting = next(iter(store.postings.values()))

    await mark_expired(store, now=NOW, source_id=source.id, present_external_refs=set())
    # L'offre réapparaît : compteur remis à zéro.
    await mark_expired(
        store, now=NOW, source_id=source.id, present_external_refs={"ft-1"}
    )
    await mark_expired(store, now=NOW, source_id=source.id, present_external_refs=set())

    assert posting.status == "active"  # jamais 2 absences consécutives


async def test_expiration_mecanisme3_recheck(store: InMemoryJobStore) -> None:
    store.add_source("france-travail")
    await ingest_batch("france-travail", [_raw()], store, now=NOW)
    posting = next(iter(store.postings.values()))
    job_source = next(iter(store.job_sources.values()))

    # GET unitaire → 404/410 : extinction immédiate, mono-source → expirée.
    report = await mark_expired(store, now=NOW, gone_job_source_ids={job_source.id})

    assert report.by_recheck == 1
    assert posting.status == "expired"


async def test_offre_withdrawn_au_signal_source(store: InMemoryJobStore) -> None:
    store.add_source("france-travail")
    job = _raw(withdrawn=True)
    await ingest_batch("france-travail", [job], store, now=NOW)
    posting = next(iter(store.postings.values()))
    assert posting.status == "withdrawn"

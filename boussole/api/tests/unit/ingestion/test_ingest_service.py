"""Tests du service d'ingestion : idempotence, dédup étage 1, fusion,
expiration (07 §4.4, §4.6, §6) — store en mémoire, aucun réseau ni base."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.ai.providers.fake import FakeProvider
from app.modules.ingestion.connectors.base import RawJob, RawLocation
from app.modules.ingestion.geocode import StaticGeocoder
from app.modules.ingestion.service import (
    DataIntegrityError,
    IngestReport,
    _ingest_one,
    ingest_batch,
    mark_expired,
)
from app.modules.ingestion.taxonomy import SkillResolver
from app.modules.jobs.models import JobSource
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


# ----------------------------------------------- correctifs revue M2


async def test_offre_republiee_reactive_le_posting_expire(
    store: InMemoryJobStore,
) -> None:
    """Correctif 2 : offre entrante ACTIVE sur posting expired → active."""
    source = store.add_source("france-travail")
    await ingest_batch("france-travail", [_raw()], store, now=NOW)
    posting = next(iter(store.postings.values()))
    job_source = next(iter(store.job_sources.values()))

    # Expirée par absence (2 réconciliations), compteur au seuil.
    for _ in range(2):
        await mark_expired(
            store, now=NOW, source_id=source.id, present_external_refs=set()
        )
    assert posting.status == "expired"
    assert await store.absence_count(job_source.id) >= 2

    # L'offre est republiée par la même source (idempotence, dedup_hash UNIQUE).
    report = await ingest_batch(
        "france-travail", [_raw()], store, now=NOW + timedelta(days=3)
    )
    assert report.updated == 1
    assert posting.status == "active"
    # Compteurs d'absence remis à zéro : pas d'extinction fantôme au cycle suivant.
    assert await store.absence_count(job_source.id) == 0


async def test_offre_republiee_reactive_posting_withdrawn_via_etage1(
    store: InMemoryJobStore,
) -> None:
    """Correctif 2 : rattachement étage 1 d'une offre active → réactivation."""
    store.add_source("greenhouse", kind="ats_feed")
    store.add_source("lever", kind="ats_feed")
    await ingest_batch(
        "greenhouse",
        [_raw("gh-1", employer_ref="REQ-7", url="https://a.example", withdrawn=True)],
        store, now=NOW,
    )
    posting = next(iter(store.postings.values()))
    assert posting.status == "withdrawn"

    # Autre source, même dedup_hash, offre active → le posting redevient actif.
    await ingest_batch(
        "lever", [_raw("lv-9", employer_ref="REQ-7", url="https://b.example")],
        store, now=NOW + timedelta(hours=1),
    )
    assert posting.status == "active"


async def test_reactivation_reset_expires_at_depasse(store: InMemoryJobStore) -> None:
    """Correctif 2 : une deadline dépassée est purgée à la republication,
    sinon le mécanisme 1 ré-expirerait l'offre au cycle suivant."""
    store.add_source("france-travail")
    await ingest_batch(
        "france-travail", [_raw(expires_at=NOW - timedelta(days=1))],
        store, now=NOW - timedelta(days=10),
    )
    posting = next(iter(store.postings.values()))
    await mark_expired(store, now=NOW)
    assert posting.status == "expired"

    await ingest_batch("france-travail", [_raw()], store, now=NOW + timedelta(days=1))
    assert posting.status == "active"
    report = await mark_expired(store, now=NOW + timedelta(days=2))
    assert report.by_signal == 0
    assert posting.status == "active"


async def test_maj_meme_source_remplace_sans_arbitrage(
    store: InMemoryJobStore,
) -> None:
    """Correctif 3 : la MÊME source remplace directement ses champs (07 §4.4),
    l'arbitrage de confiance §6.3 ne vaut qu'entre sources concurrentes."""
    store.add_source("france-travail")
    initial = _raw(
        description="Longue description initiale du poste de Data Engineer en CDI.",
        contract="permanent", contract_conf=1.0,
        salary_min=50000, salary_max=60000,
        salary_currency="EUR", salary_period="year", salary_conf=1.0,
    )
    await ingest_batch("france-travail", [initial], store, now=NOW)
    posting = next(iter(store.postings.values()))
    assert posting.contract == "permanent"

    # Re-publication corrigée par la même source : CDD (conf 0.9 < 1.0),
    # description PLUS COURTE, salaire revu à la baisse, titre corrigé.
    updated = _raw(
        title="Data Engineer (H/F)",
        description="CDD de 12 mois.",
        salary_min=42000, salary_max=45000,
        salary_currency="EUR", salary_period="year", salary_conf=1.0,
        contract="fixed_term", contract_conf=0.9,
    )
    report = await ingest_batch(
        "france-travail", [updated], store, now=NOW + timedelta(days=1)
    )
    assert report.updated == 1
    # Remplacement direct : pas d'arbitrage 1.0 vs 0.9, pas de « plus longue gagne ».
    assert posting.contract == "fixed_term"
    assert posting.title == "Data Engineer (H/F)"
    assert posting.description_text == "CDD de 12 mois."
    assert (posting.salary_min, posting.salary_max) == (42000, 45000)


async def test_maj_meme_source_champ_absent_conserve(store: InMemoryJobStore) -> None:
    """Correctif 3 : un champ que la source ne fournit plus reste en place
    (il peut provenir d'une autre source du posting)."""
    store.add_source("france-travail")
    await ingest_batch(
        "france-travail",
        [_raw(remote="hybrid", remote_conf=1.0,
              description="Data Engineer. Aucun autre attribut.")],
        store, now=NOW,
    )
    posting = next(iter(store.postings.values()))
    await ingest_batch(
        "france-travail",
        [_raw(description="Data Engineer. Toujours aucun autre attribut.")],
        store, now=NOW + timedelta(days=1),
    )
    assert posting.remote == "hybrid"  # non fourni → conservé


async def test_expires_at_jamais_ecrase_par_plus_ancien(
    store: InMemoryJobStore,
) -> None:
    """Correctif 4 : expires_at = max des valeurs non NULL."""
    store.add_source("greenhouse", kind="ats_feed")
    store.add_source("lever", kind="ats_feed")
    late = NOW + timedelta(days=30)
    early = NOW + timedelta(days=5)
    await ingest_batch(
        "greenhouse",
        [_raw("gh-1", employer_ref="REQ-7", url="https://a.example", expires_at=late)],
        store, now=NOW,
    )
    posting = next(iter(store.postings.values()))

    # Une source concurrente avec une deadline plus courte ne raccourcit rien.
    await ingest_batch(
        "lever",
        [_raw("lv-9", employer_ref="REQ-7", url="https://b.example", expires_at=early)],
        store, now=NOW + timedelta(hours=1),
    )
    assert posting.expires_at == late

    # Une deadline plus lointaine, elle, est prise.
    later = NOW + timedelta(days=60)
    await ingest_batch(
        "lever",
        [_raw("lv-9", employer_ref="REQ-7", url="https://b.example", expires_at=later)],
        store, now=NOW + timedelta(hours=2),
    )
    assert posting.expires_at == later


async def test_first_seen_at_min_lors_du_rattachement(
    store: InMemoryJobStore,
) -> None:
    """Correctif 13 : first_seen_at = min (07 §6.3.3)."""
    store.add_source("greenhouse", kind="ats_feed")
    store.add_source("lever", kind="ats_feed")
    await ingest_batch(
        "greenhouse",
        [_raw("gh-1", employer_ref="REQ-7", url="https://a.example",
              posted_at=NOW - timedelta(days=2))],
        store, now=NOW,
    )
    posting = next(iter(store.postings.values()))
    assert posting.first_seen_at == NOW - timedelta(days=2)

    # Rattachement d'une source qui avait publié l'offre AVANT.
    await ingest_batch(
        "lever",
        [_raw("lv-9", employer_ref="REQ-7", url="https://b.example",
              posted_at=NOW - timedelta(days=10))],
        store, now=NOW + timedelta(hours=1),
    )
    assert posting.first_seen_at == NOW - timedelta(days=10)
    assert posting.last_seen_at == NOW + timedelta(hours=1)


async def test_job_source_orpheline_erreur_explicite(
    store: InMemoryJobStore,
) -> None:
    """Correctif 14 : plus d'assert — exception métier explicite."""
    source = store.add_source("france-travail")
    # job_source pointant vers un posting inexistant (corruption FK simulée).
    orphan = JobSource(
        id=uuid.uuid4(), job_posting_id=uuid.uuid4(), source_id=source.id,
        external_ref="ft-1", original_url="https://example.test/ft-1",
        posted_at=None, ingested_at=NOW,
    )
    await store.add(orphan)

    with pytest.raises(DataIntegrityError):
        await _ingest_one(
            store, source, _raw(), IngestReport(),
            geocoder=StaticGeocoder(), resolver=SkillResolver(),
            provider=None, now=NOW,
        )
    # Via le batch : l'erreur est comptée, le cycle continue (07 §4.5).
    report = await ingest_batch(
        "france-travail", [_raw(), _raw("ft-2", url="https://example.test/ft-2")],
        store, now=NOW,
    )
    assert report.errors == 1
    assert report.created == 1


async def test_needs_llm_inclut_salaire_experience_langues(
    store: InMemoryJobStore,
) -> None:
    """Correctif 10 : salaire/expérience/langues manquants sollicitent le LLM."""
    store.add_source("greenhouse", kind="ats_feed")
    provider = FakeProvider()
    complete = _raw(
        "gh-1", title="Senior Data Engineer",
        description="Poste complet.", url="https://a.example",
        contract="permanent", contract_conf=1.0,
        remote="onsite", remote_conf=1.0,
        salary_min=50000, salary_max=60000,
        salary_currency="EUR", salary_period="year", salary_conf=1.0,
        experience_min=3.0, experience_max=5.0,
        languages=[("en", "B2")], skills=["Python"],
    )
    await ingest_batch("greenhouse", [complete], store, provider=provider, now=NOW)
    assert provider.calls == []  # rien ne manque → pas d'appel LLM

    missing_salary = _raw(
        "gh-2", title="Senior Data Engineer",
        description="Poste sans salaire.", url="https://b.example",
        contract="permanent", contract_conf=1.0,
        remote="onsite", remote_conf=1.0,
        experience_min=3.0, experience_max=5.0,
        languages=[("en", "B2")], skills=["Python"],
    )
    await ingest_batch("greenhouse", [missing_salary], store, provider=provider, now=NOW)
    assert len(provider.calls) == 1  # salaire manquant → LLM sollicité


async def test_savepoint_isole_lechec_dun_item(store: InMemoryJobStore) -> None:
    """Correctif 9 : un échec DB (flush) est annulé au savepoint de l'item,
    le reste du batch n'est pas empoisonné."""

    class FailingFlushStore(InMemoryJobStore):
        def __init__(self) -> None:
            super().__init__()
            self.flush_calls = 0
            self.savepoints_opened = 0

        async def flush(self) -> None:
            self.flush_calls += 1
            if self.flush_calls == 1:  # 1er item : IntegrityError simulée
                raise RuntimeError("duplicate key value violates unique constraint")

        def savepoint(self):  # type: ignore[override]
            self.savepoints_opened += 1
            return super().savepoint()

    failing_store = FailingFlushStore()
    failing_store.add_source("france-travail")
    report = await ingest_batch(
        "france-travail",
        [_raw("ft-1"), _raw("ft-2", url="https://example.test/ft-2")],
        failing_store, now=NOW,
    )

    assert failing_store.savepoints_opened == 2  # un savepoint PAR item
    assert report.errors == 1
    assert report.created == 1
    # Les écritures de l'item échoué ont été annulées (rollback savepoint).
    assert len(failing_store.postings) == 1
    assert len(failing_store.job_sources) == 1
    assert next(iter(failing_store.job_sources.values())).external_ref == "ft-2"


async def test_mark_expired_skip_refs_perimetre_non_verifie(
    store: InMemoryJobStore,
) -> None:
    """Correctif 5a : les job_sources d'un périmètre en échec de fetch ne sont
    ni comptées absentes, ni remises à zéro."""
    source = store.add_source("greenhouse", kind="ats_feed")
    await ingest_batch(
        "greenhouse",
        [_raw("gh-1", url="https://boards.greenhouse.io/acme/jobs/1"),
         _raw("gh-2", title="Backend Engineer",
              url="https://boards.greenhouse.io/globex/jobs/2")],
        store, now=NOW,
    )
    gh1 = next(js for js in store.job_sources.values() if js.external_ref == "gh-1")
    gh2 = next(js for js in store.job_sources.values() if js.external_ref == "gh-2")

    # Board globex en échec : gh-2 est hors périmètre — 2 cycles où gh-1 et
    # gh-2 sont absents du flux, mais seul gh-1 est réellement vérifié.
    for _ in range(2):
        await mark_expired(
            store, now=NOW, source_id=source.id,
            present_external_refs=set(), skip_external_refs={"gh-2"},
        )
    assert await store.absence_count(gh1.id) == 2
    assert await store.absence_count(gh2.id) == 0  # jamais compté absent
    posting_gh2 = store.postings[gh2.job_posting_id]
    assert posting_gh2.status == "active"

    # Compteur préexistant : le skip ne remet PAS à zéro non plus.
    await store.note_source_absence(gh2.id)
    await mark_expired(
        store, now=NOW, source_id=source.id,
        present_external_refs={"gh-2"}, skip_external_refs={"gh-2"},
    )
    assert await store.absence_count(gh2.id) == 1  # intact (ni clear ni +1)

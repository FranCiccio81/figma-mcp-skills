"""Orchestration de l'ingestion : normalisation, dédup, fusion, expiration.

Implémente 07 §4–§6 : idempotence par ``(source_id, external_ref)``,
déduplication étage 1 (``dedup_hash``) et étage 2 (candidats trigram +
décision cosinus ≥ ``DEDUP_STAGE2_COSINE_THRESHOLD``, D13), fusion « la
donnée la plus riche et la plus récente gagne » (07 §6.3), expiration
selon les 3 mécanismes de 07 §4.6.

**Embeddings (M4)** — l'étage 2 était écrit mais inopérant faute de
vecteurs. Le pipeline calcule désormais l'embedding « intitulé + 1er
paragraphe » (06 §2.3, 07 §5.6) de chaque offre entrante et l'écrit sur
``job_postings.embedding`` :

- la décision cosinus de l'étage 2 devient effective (seuil 0,92 depuis
  la configuration — 🟡 **Q12**, à calibrer en alpha) ;
- l'embedding est RECALCULÉ quand la fusion change l'intitulé ou la
  description : la fraîcheur est portée par le point d'écriture, pas par
  le batch (aucune colonne du schéma ne porte le condensat du texte
  source — voir :mod:`app.ai.embeddings.backfill`) ;
- toute panne du fournisseur est absorbée : sans vecteur, l'étage 2 ne
  décide rien (biais assumé vers les faux négatifs, D13) et l'ingestion
  se poursuit. Le beat quotidien ``ai.embeddings.backfill_jobs``
  rattrape les offres restées sans vecteur.

La persistance passe par le protocole :class:`JobStore` : implémentation
SQLAlchemy pour la prod, fake en mémoire dans les tests unitaires.
"""

import logging
import math
import uuid
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.embeddings.base import EmbeddingError, EmbeddingProvider
from app.ai.embeddings.factory import get_embedding_provider
from app.ai.embeddings.text import job_embedding_text
from app.ai.providers.base import LLMProvider
from app.ai.providers.factory import get_llm_provider
from app.ai.providers.fake import FakeProvider
from app.ai.tasks.extract_job import JobExtractionError, extract_job
from app.core.config import get_settings
from app.modules.ingestion import extract_rules
from app.modules.ingestion.connectors.base import RawJob
from app.modules.ingestion.geocode import Geocoder, StaticGeocoder
from app.modules.ingestion.models import ConnectorState
from app.modules.ingestion.normalize import (
    compute_dedup_hash,
    norm,
    norm_location,
    strip_html,
)
from app.modules.ingestion.taxonomy import SkillResolver, canonicalize
from app.modules.jobs.models import (
    JobLanguage,
    JobLocation,
    JobPosting,
    JobSkill,
    JobSource,
    Source,
)
from app.modules.referentials.models import Skill, SkillAlias

logger = logging.getLogger(__name__)

# Seuils étage 2 (07 §6.2) — 🟡 à calibrer en alpha (Q5).
STAGE2_COMPANY_SIMILARITY = 0.55
STAGE2_TITLE_SIMILARITY = 0.45
#: Seuil cosinus par DÉFAUT (D13) — la valeur effective vient de la
#: configuration (``DEDUP_STAGE2_COSINE_THRESHOLD``), calibrable sans
#: redéploiement en alpha (🟡 Q12).
STAGE2_COSINE_THRESHOLD = 0.92
STAGE2_CANDIDATE_LIMIT = 50
# Absence de 2 réconciliations complètes consécutives avant extinction 🟡.
ABSENCE_THRESHOLD = 2
# Égalité de confiance à ±0,05 (07 §6.3).
CONFIDENCE_EPSILON = 0.05

_CEFR_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


class DataIntegrityError(RuntimeError):
    """Incohérence détectée en base (ex. job_source sans job_posting)."""


# ------------------------------------------------------------------ protocole
class JobStore(Protocol):
    """Port de persistance du pipeline — substituable en mémoire (tests)."""

    async def get_source_by_slug(self, slug: str) -> Source | None: ...

    async def get_job_source(
        self, source_id: uuid.UUID, external_ref: str
    ) -> JobSource | None: ...

    async def get_posting(self, posting_id: uuid.UUID) -> JobPosting | None: ...

    async def get_posting_by_dedup_hash(self, dedup_hash: str) -> JobPosting | None: ...

    async def stage2_candidates(
        self, company_name: str, title: str
    ) -> list[JobPosting]: ...

    async def skill_lookup(
        self,
    ) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID]]: ...

    async def locations_for(self, posting_id: uuid.UUID) -> list[JobLocation]: ...

    async def skills_for(self, posting_id: uuid.UUID) -> list[JobSkill]: ...

    async def languages_for(self, posting_id: uuid.UUID) -> list[JobLanguage]: ...

    async def job_sources_for_source(self, source_id: uuid.UUID) -> list[JobSource]: ...

    async def job_sources_for_posting(self, posting_id: uuid.UUID) -> list[JobSource]: ...

    async def posting_id_of_job_source(
        self, job_source_id: uuid.UUID
    ) -> uuid.UUID | None: ...

    async def postings_with_expired_deadline(self, now: datetime) -> list[JobPosting]: ...

    async def note_source_absence(self, job_source_id: uuid.UUID) -> int: ...

    async def clear_source_absence(self, job_source_id: uuid.UUID) -> None: ...

    async def absence_count(self, job_source_id: uuid.UUID) -> int: ...

    async def add(self, obj: object) -> None: ...

    async def flush(self) -> None: ...

    def savepoint(self) -> AbstractAsyncContextManager[object]:
        """Point de reprise par item : l'échec DB d'un item (IntegrityError)
        est annulé sans empoisonner la transaction du reste du batch."""
        ...


# ------------------------------------------------------------- normalisation
@dataclass(slots=True)
class _ResolvedLocation:
    raw_label: str
    lat: float | None
    lon: float | None
    country_code: str | None
    city_label: str | None  # libellé canonique géocodé (norm_location)


@dataclass(slots=True)
class NormalizedJob:
    """Résultat de la normalisation d'un :class:`RawJob` (07 §5)."""

    title: str
    company: str
    description: str
    language: str
    dedup_hash: str
    country_code: str | None
    contract: str | None = None
    contract_conf: float | None = None
    remote: str | None = None
    remote_conf: float | None = None
    seniority: str | None = None
    seniority_conf: float | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_conf: float | None = None
    experience_min: float | None = None
    experience_max: float | None = None
    locations: list[_ResolvedLocation] = field(default_factory=list)
    skills: list[tuple[uuid.UUID | None, str, bool, float]] = field(default_factory=list)
    languages: list[tuple[str, str, float]] = field(default_factory=list)
    sector_code: str | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    withdrawn: bool = False


def get_extraction_provider() -> LLMProvider:
    """Provider LLM de l'extraction d'offres — sélectionné par configuration.

    Même patron que ``app/workers/cv_tasks.py`` et
    ``app/modules/explanations/router.py`` : ``AI_PROVIDER=fake`` (défaut)
    conserve le provider déterministe, toute autre valeur passe par la
    fabrique (primaire + fallback + circuit breaker D18).

    ⚠️ Ce point d'appel construisait un ``FakeProvider()`` EN DUR, sans jamais
    consulter ``AI_PROVIDER`` : ``extract_job`` — le plus gros volume du
    système (≤ 10 k appels/jour, 08 §2.2) — n'atteignait jamais la fabrique.
    Aucune configuration ne pouvait l'activer, et le secours LLM de 07 §5.2
    retournait systématiquement une extraction vide (M8).
    """
    if get_settings().ai_provider == "fake":
        return FakeProvider()
    return get_llm_provider("extract_job")


def normalize_raw(
    raw: RawJob,
    *,
    source_slug: str,
    geocoder: Geocoder | None = None,
    resolver: SkillResolver | None = None,
    provider: LLMProvider | None = None,
) -> NormalizedJob:
    """Normalise une offre brute : étage 0 → source → règles → LLM secours.

    Priorités (07 §5.2) : champ structuré source (conf 1.0 ou conf du
    mapping) > règles déterministes > LLM de secours. Ce dernier vient de
    :func:`get_extraction_provider` (donc de ``AI_PROVIDER``) : ``fake`` par
    défaut 🟡 — extraction vide, l'offre est publiée avec les seuls attributs
    déterministes.
    """
    geocoder = geocoder or StaticGeocoder()
    resolver = resolver or SkillResolver()
    provider = provider if provider is not None else get_extraction_provider()

    description = strip_html(raw.description)
    rule_text = f"{raw.title}\n{description}"

    # --- attributs : source puis règles ---
    contract, contract_conf = raw.contract, raw.contract_conf
    if contract is None:
        rule = extract_rules.extract_contract(rule_text)
        if rule:
            contract, contract_conf = rule.value, rule.confidence

    remote, remote_conf = raw.remote, raw.remote_conf
    if remote is None:
        remote_rule = extract_rules.extract_remote(rule_text)
        if remote_rule:
            remote, remote_conf = remote_rule.value, remote_rule.confidence

    salary_min, salary_max = raw.salary_min, raw.salary_max
    salary_currency, salary_period = raw.salary_currency, raw.salary_period
    salary_conf = raw.salary_conf
    if salary_min is None and salary_max is None:
        salary_rule = extract_rules.extract_salary(rule_text)
        if salary_rule:
            salary_min, salary_max = salary_rule.salary_min, salary_rule.salary_max
            salary_currency, salary_period = salary_rule.currency, salary_rule.period
            salary_conf = salary_rule.confidence

    experience_min, experience_max = raw.experience_min, raw.experience_max
    if experience_min is None and experience_max is None:
        exp_rule = extract_rules.extract_experience(rule_text)
        if exp_rule:
            experience_min, experience_max = exp_rule.minimum, exp_rule.maximum

    seniority_rule = extract_rules.extract_seniority(raw.title)
    seniority, seniority_conf = (
        (seniority_rule.value, seniority_rule.confidence) if seniority_rule else (None, None)
    )

    languages: list[tuple[str, str, float]] = [
        (code, level, 1.0) for code, level in raw.languages
    ]
    if not languages:
        languages = [
            (r.lang_code, r.min_level, r.confidence)
            for r in extract_rules.extract_languages(rule_text)
        ]

    # Requis et souhaités séparés : la source fait la différence quand elle
    # le peut, et le moteur pèse les deux à 25 % et 10 %.
    skills: list[tuple[uuid.UUID | None, str, bool, float]] = [
        (resolver.resolve(label), label, True, 0.9)  # référentiel source (ROME) : 0.9
        for label in raw.skills
    ] + [
        (resolver.resolve(label), label, False, 0.9)
        for label in raw.skills_nice
    ]

    # --- étage 2 LLM en secours : uniquement les trous (07 §5.2) ---
    # TODO 🟡 (07 §4.3/§5.2, REPORTÉ — avant de brancher un provider réel) :
    #  - hash du payload brut pour court-circuiter toute la re-normalisation
    #    quand l'offre n'a pas changé entre deux cycles ;
    #  - cache LLM par (offre, prompt_version) pour ne jamais payer deux fois
    #    la même extraction.
    needs_llm = (
        contract is None
        or remote is None
        or seniority is None
        or not skills
        or (salary_min is None and salary_max is None)
        or (experience_min is None and experience_max is None)
        or not languages
    )
    if needs_llm:
        try:
            extraction = extract_job(rule_text, provider)
        except JobExtractionError:
            logger.warning("job_extraction_failed external_ref=%s", raw.external_ref)
            extraction = None
        if extraction is not None:
            if contract is None and extraction.contract is not None:
                contract = extraction.contract
                contract_conf = extraction.contract_confidence
            if remote is None and extraction.remote is not None:
                remote = extraction.remote
                remote_conf = extraction.remote_confidence
            if seniority is None and extraction.seniority is not None:
                seniority = extraction.seniority
                seniority_conf = extraction.seniority_confidence
            if salary_min is None and extraction.salary_min is not None:
                salary_min, salary_max = extraction.salary_min, extraction.salary_max
                salary_currency = extraction.salary_currency
                salary_period = extraction.salary_period
            if experience_min is None and extraction.experience_min_years is not None:
                experience_min = extraction.experience_min_years
                experience_max = extraction.experience_max_years
            if not skills:
                skills = [
                    (resolver.resolve(s.label), s.label, required, s.confidence)
                    for s, required in [
                        *((s, True) for s in extraction.skills_required),
                        *((s, False) for s in extraction.skills_nice),
                    ]
                ]
            if not languages:
                languages = [
                    (lang.lang_code, lang.min_level, lang.confidence)
                    for lang in extraction.languages
                ]

    # --- langue de rédaction (07 §5.4) ---
    if raw.language:
        language = raw.language
    else:
        language, lang_conf = extract_rules.detect_language(rule_text)
        if lang_conf < 0.7:
            language = "fr" if source_slug == "france-travail" else "en"
            logger.warning(
                "language_detection_low_confidence external_ref=%s fallback=%s",
                raw.external_ref, language,
            )

    # --- localisations + géocodage (07 §5.3) ---
    resolved: list[_ResolvedLocation] = []
    for loc in raw.locations:
        if loc.lat is not None and loc.lon is not None:
            resolved.append(
                _ResolvedLocation(loc.label, loc.lat, loc.lon, loc.country_code, None)
            )
        else:
            point = geocoder.geocode(loc.label)
            if point is not None:
                resolved.append(
                    _ResolvedLocation(
                        loc.label, point.lat, point.lon, point.country_code, point.label
                    )
                )
            else:
                # non résolu : localisation inconnue côté moteur (06 §2 dim. 7)
                resolved.append(
                    _ResolvedLocation(loc.label, None, None, loc.country_code, None)
                )

    country_code = next((r.country_code for r in resolved if r.country_code), None)

    # --- clé de dédup étage 1 (07 §6.1) ---
    primary = resolved[0] if resolved else None
    if primary is None:
        location_norm = norm_location(full_remote=remote == "full_remote",
                                      country_code=country_code)
    elif primary.city_label:
        location_norm = norm_location(city=primary.city_label,
                                      country_code=primary.country_code)
    else:
        location_norm = norm_location(raw_label=primary.raw_label)
    dedup_hash = compute_dedup_hash(raw.company, raw.title, location_norm, raw.employer_ref)

    return NormalizedJob(
        title=raw.title,
        company=raw.company,
        description=description,
        language=language,
        dedup_hash=dedup_hash,
        country_code=country_code,
        contract=contract,
        contract_conf=contract_conf,
        remote=remote,
        remote_conf=remote_conf,
        seniority=seniority,
        seniority_conf=seniority_conf,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        salary_period=salary_period,
        salary_conf=salary_conf,
        experience_min=experience_min,
        experience_max=experience_max,
        locations=resolved,
        skills=skills,
        languages=languages,
        sector_code=raw.sector,
        posted_at=raw.posted_at,
        expires_at=raw.expires_at,
        withdrawn=raw.withdrawn,
    )


# ------------------------------------------------------------------- fusion
def _merge_confidence_field(
    posting: JobPosting,
    attr: str,
    conf_attr: str,
    new_value: str | None,
    new_conf: float | None,
    incoming_newer: bool,
) -> None:
    """Règle champ par champ de 07 §6.3 (attributs avec colonne de confiance)."""
    if new_value is None:
        return
    current = getattr(posting, attr)
    current_conf = float(getattr(posting, conf_attr) or 0.0)
    incoming_conf = float(new_conf or 0.0)
    if current is None:
        setattr(posting, attr, new_value)
        setattr(posting, conf_attr, new_conf)
    elif current == new_value:
        setattr(posting, conf_attr, max(current_conf, incoming_conf))
    else:
        replace = incoming_conf > current_conf + CONFIDENCE_EPSILON or (
            abs(incoming_conf - current_conf) <= CONFIDENCE_EPSILON and incoming_newer
        )
        # Conflit journalisé pour calibrage (audit_log 🟡 en intégration M2).
        logger.info(
            "job_field_conflict posting=%s field=%s current=%r(%.2f) incoming=%r(%.2f) kept=%r",
            posting.id, attr, current, current_conf, new_value, incoming_conf,
            new_value if replace else current,
        )
        if replace:
            setattr(posting, attr, new_value)
            setattr(posting, conf_attr, new_conf)


def _apply_same_source_fields(posting: JobPosting, incoming: NormalizedJob) -> None:
    """Re-normalisation d'une mise à jour de la MÊME source (07 §4.4).

    La règle d'arbitrage §6.3 ne vaut qu'ENTRE sources concurrentes : quand
    la même ``(source_id, external_ref)`` republie l'offre, ses champs
    remplacent directement les valeurs précédentes (titre, description,
    salaire…). Un champ que la source ne fournit plus (``None``) est
    conservé : il peut provenir d'une autre source rattachée au posting.
    """
    posting.title = incoming.title
    posting.description_text = incoming.description
    posting.language = incoming.language
    if incoming.contract is not None:
        posting.contract = incoming.contract
        posting.contract_conf = incoming.contract_conf
    if incoming.remote is not None:
        posting.remote = incoming.remote
        posting.remote_conf = incoming.remote_conf
    if incoming.seniority is not None:
        posting.seniority = incoming.seniority
        posting.seniority_conf = incoming.seniority_conf
    if incoming.salary_min is not None or incoming.salary_max is not None:
        posting.salary_min = incoming.salary_min
        posting.salary_max = incoming.salary_max
        posting.salary_currency = incoming.salary_currency
        posting.salary_period = incoming.salary_period
    if incoming.experience_min is not None or incoming.experience_max is not None:
        posting.experience_min = incoming.experience_min
        posting.experience_max = incoming.experience_max
    if incoming.country_code is not None:
        posting.country_code = incoming.country_code


async def _merge_posting(
    store: JobStore,
    posting: JobPosting,
    incoming: NormalizedJob,
    now: datetime,
    *,
    same_source: bool = False,
) -> None:
    """Fusion 07 §6.3 : « la donnée la plus riche et la plus récente gagne ».

    ``same_source=True`` : mise à jour par la même ``(source_id,
    external_ref)`` → remplacement direct des champs (07 §4.4), PAS
    d'arbitrage de fusion inter-sources (§6.3).
    """
    incoming_newer = (incoming.posted_at or now) >= (posting.last_seen_at or now)

    if same_source:
        _apply_same_source_fields(posting, incoming)
    else:
        # description_text : la plus longue gagne 🟡 (proxy « plus riche », Q8).
        # Le recalcul tsv est porté par le trigger SQL ; l'embedding est
        # recalculé par la chaîne embed+index (07 §5.6) 🟡 M3.
        if len(incoming.description) > len(posting.description_text or ""):
            posting.description_text = incoming.description

        _merge_confidence_field(posting, "contract", "contract_conf",
                                incoming.contract, incoming.contract_conf, incoming_newer)
        _merge_confidence_field(posting, "remote", "remote_conf",
                                incoming.remote, incoming.remote_conf, incoming_newer)
        _merge_confidence_field(posting, "seniority", "seniority_conf",
                                incoming.seniority, incoming.seniority_conf, incoming_newer)

        # Salaire : pas de colonne de confiance dans le schéma → remplissage
        # des NULL, remplacement uniquement par un champ structuré source
        # (conf 1.0) plus récent ; conflit journalisé 🟡.
        if incoming.salary_min is not None or incoming.salary_max is not None:
            if posting.salary_min is None and posting.salary_max is None:
                posting.salary_min = incoming.salary_min
                posting.salary_max = incoming.salary_max
                posting.salary_currency = incoming.salary_currency
                posting.salary_period = incoming.salary_period
            elif (incoming.salary_min, incoming.salary_max) != (
                posting.salary_min, posting.salary_max
            ):
                replace = float(incoming.salary_conf or 0.0) >= 0.99 and incoming_newer
                logger.info(
                    "job_field_conflict posting=%s field=salary current=%r incoming=%r "
                    "kept=%r",
                    posting.id, (posting.salary_min, posting.salary_max),
                    (incoming.salary_min, incoming.salary_max),
                    "incoming" if replace else "current",
                )
                if replace:
                    posting.salary_min = incoming.salary_min
                    posting.salary_max = incoming.salary_max
                    posting.salary_currency = incoming.salary_currency
                    posting.salary_period = incoming.salary_period

        if posting.experience_min is None and incoming.experience_min is not None:
            posting.experience_min = incoming.experience_min
            posting.experience_max = incoming.experience_max

        if posting.country_code is None and incoming.country_code is not None:
            posting.country_code = incoming.country_code

    # Satellites : union (labels normalisés pour éviter les doublons).
    existing_locations = {norm(x.raw_label) for x in await store.locations_for(posting.id)}
    for loc in incoming.locations:
        if norm(loc.raw_label) not in existing_locations:
            await store.add(JobLocation(
                id=uuid.uuid4(), job_posting_id=posting.id, raw_label=loc.raw_label,
                lat=loc.lat, lon=loc.lon, country_code=loc.country_code,
            ))

    existing_skills = await store.skills_for(posting.id)
    known = {canonicalize(x.label_raw) for x in existing_skills}
    for skill_id, label_raw, required, confidence in incoming.skills:
        key = canonicalize(label_raw)
        if key in known:
            for existing in existing_skills:
                if canonicalize(existing.label_raw) == key:
                    existing.confidence = max(float(existing.confidence), confidence)
        else:
            await store.add(JobSkill(
                id=uuid.uuid4(), job_posting_id=posting.id, skill_id=skill_id,
                label_raw=label_raw, required=required, confidence=confidence,
            ))
            known.add(key)

    existing_languages = {x.lang_code: x for x in await store.languages_for(posting.id)}
    for code, level, confidence in incoming.languages:
        existing_lang = existing_languages.get(code)
        if existing_lang is None:
            await store.add(JobLanguage(
                job_posting_id=posting.id, lang_code=code,
                min_level=level, confidence=confidence,
            ))
        elif existing_lang.min_level == level:
            existing_lang.confidence = max(float(existing_lang.confidence), confidence)
        elif confidence > float(existing_lang.confidence) + CONFIDENCE_EPSILON:
            logger.info("job_field_conflict posting=%s field=language:%s", posting.id, code)
            existing_lang.min_level = level
            existing_lang.confidence = confidence

    # Dates (07 §6.3.3) : first_seen = min, last_seen = max.
    posting.last_seen_at = max(posting.last_seen_at or now, now)
    if incoming.posted_at is not None and (
        posting.first_seen_at is None or incoming.posted_at < posting.first_seen_at
    ):
        posting.first_seen_at = incoming.posted_at
    # expires_at : max des valeurs non NULL — jamais écrasé par une date
    # plus ancienne (une source retardataire ne raccourcit pas la vie de
    # l'offre canonique).
    if incoming.expires_at is not None:
        posting.expires_at = (
            incoming.expires_at
            if posting.expires_at is None
            else max(posting.expires_at, incoming.expires_at)
        )

    if incoming.withdrawn:
        if posting.status == "active":
            posting.status = "withdrawn"
    elif posting.status in ("expired", "withdrawn") and (
        incoming.expires_at is None or incoming.expires_at > now
    ):
        # Offre republiée : un posting éteint rattaché (étage 1 ou
        # idempotence) à une offre entrante ACTIVE redevient actif — sinon
        # l'offre resterait invisible à jamais (dedup_hash UNIQUE). Les
        # compteurs d'absence repartent de zéro.
        posting.status = "active"
        if posting.expires_at is not None and posting.expires_at <= now:
            # Deadline dépassée d'une publication antérieure : sans reset,
            # le mécanisme 1 ré-expirerait l'offre au prochain cycle.
            posting.expires_at = incoming.expires_at
        for sibling in await store.job_sources_for_posting(posting.id):
            await store.clear_source_absence(sibling.id)


# ----------------------------------------------------------------- étage 2
def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


#: Providers dont les vecteurs portent assez de sémantique pour décider
#: d'une fusion. ``hashing`` (lexical) en est volontairement exclu.
SEMANTIC_EMBEDDING_PROVIDERS = frozenset({"managed"})

#: Seuil rendu inatteignable : aucun cosinus ne dépasse 1,0.
STAGE2_DISABLED_THRESHOLD = 1.5

#: Distance maximale entre deux offres réputées identiques (07 §6.2.2).
STAGE2_MAX_DISTANCE_KM = 50.0


def _distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distance haversine en kilomètres entre deux points géocodés."""
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def _too_far_apart(candidate: JobPosting, incoming: "NormalizedJob") -> bool:
    """Deux offres géocodées trop éloignées pour être le même poste.

    Conservateur : si l'un des deux côtés n'est pas géocodé, on ne conclut
    pas (le biais de D13 va vers le faux négatif). La comparaison retient la
    distance MINIMALE entre les lieux, une offre pouvant en porter plusieurs.
    """
    candidate_points = [
        (loc.lat, loc.lon)
        for loc in candidate.locations
        if loc.lat is not None and loc.lon is not None
    ]
    incoming_points = [
        (loc.lat, loc.lon)
        for loc in incoming.locations
        if loc.lat is not None and loc.lon is not None
    ]
    if not candidate_points or not incoming_points:
        return False
    closest = min(
        _distance_km(c_lat, c_lon, i_lat, i_lon)
        for c_lat, c_lon in candidate_points
        for i_lat, i_lon in incoming_points
    )
    return closest > STAGE2_MAX_DISTANCE_KM


def _stage2_threshold() -> float:
    """Seuil cosinus effectif de l'étage 2 (configuration, D13 / 🟡 Q12).

    GARDE DE CALIBRATION : le seuil 0,92 de D13 a été fixé pour des vecteurs
    SÉMANTIQUES. Le provider ``hashing`` (défaut tant que Q11 n'est pas
    tranchée) produit des vecteurs LEXICAUX, sur lesquels ce seuil fusionne
    des offres réellement distinctes — mesuré en revue : « Développeur
    Backend Python » et « … Java » de la même entreprise à 0,955, et deux
    offres au même titre et même premier paragraphe à 1,0000. La fusion
    étant irréversible pour l'utilisateur (l'offre absorbée disparaît),
    l'étage 2 est NEUTRALISÉ hors provider sémantique : le seuil devient
    inatteignable et seul l'étage 1 (hash exact) déduplique.

    À réactiver avec le provider managé, après calibration sur données
    réelles (Q12) — et non l'inverse.
    """
    settings = get_settings()
    if settings.embeddings_provider not in SEMANTIC_EMBEDDING_PROVIDERS:
        return STAGE2_DISABLED_THRESHOLD
    return float(settings.dedup_stage2_cosine_threshold)


def _embed_job(
    embedder: EmbeddingProvider | None, title: str, description: str
) -> list[float] | None:
    """Embedding « intitulé + 1er paragraphe » d'une offre (06 §2.3, 07 §5.6).

    Jamais bloquant : toute erreur du fournisseur est journalisée et rend
    ``None`` — l'offre est ingérée sans vecteur (étage 2 sans décision,
    ``title_similarity`` inconnue), et le beat quotidien la rattrape.
    """
    if embedder is None:
        return None
    text = job_embedding_text(title, description)
    if not text:
        return None
    try:
        vectors = embedder.embed_texts([text])
    except EmbeddingError as exc:
        logger.warning("job_embedding_failed error_code=%s", exc.error_code)
        return None
    if not vectors or not any(vectors[0]):
        return None
    return list(vectors[0])


def _refresh_embedding(
    posting: JobPosting,
    incoming: NormalizedJob,
    incoming_embedding: list[float] | None,
    embedder: EmbeddingProvider | None,
) -> None:
    """Garde ``job_postings.embedding`` cohérent avec le texte APRÈS fusion.

    Le vecteur d'une offre doit décrire le texte réellement stocké. Or la
    fusion (07 §6.3) peut conserver la description existante (« la plus
    longue gagne ») ou en adopter une nouvelle : on compare donc le texte
    final au texte entrant.

    - texte final == texte entrant → on réutilise le vecteur déjà calculé
      (aucun appel supplémentaire, donc aucun coût provider) ;
    - texte final différent → recalcul depuis le posting fusionné ;
    - recalcul impossible (provider en panne) → l'ancien vecteur est
      CONSERVÉ plutôt qu'effacé : un vecteur légèrement périmé vaut mieux
      qu'une dimension redevenue inconnue (k=0).

    🟡 C'est ce point d'écriture — et non le backfill — qui porte la
    détection « le texte source a changé » : aucune colonne du schéma ne
    stocke le condensat du texte ayant produit le vecteur
    (:func:`app.ai.embeddings.text.source_text_hash`).
    """
    if (posting.title, posting.description_text) == (incoming.title, incoming.description):
        if incoming_embedding is not None:
            posting.embedding = incoming_embedding
        return
    refreshed = _embed_job(embedder, posting.title, posting.description_text)
    if refreshed is not None:
        posting.embedding = refreshed


async def _stage2_match(
    store: JobStore,
    incoming: NormalizedJob,
    embedding: list[float] | None,
    threshold: float | None = None,
) -> JobPosting | None:
    """Étage 2 (07 §6.2, D13) — candidats trigram puis décision cosinus.

    Candidats trigram (requête de :class:`SqlAlchemyJobStore`), filtre de
    compatibilité dure, puis fusion avec le MEILLEUR candidat dont le
    cosinus atteint le seuil (0,92 🟡 par défaut, configurable — Q12).

    Sans embedding d'un côté ou de l'autre, aucune fusion n'est décidée :
    biais assumé vers les faux négatifs (D13 — « doublons non fusionnés
    préférés aux faux positifs »).
    """
    cosine_threshold = _stage2_threshold() if threshold is None else threshold
    candidates = await store.stage2_candidates(incoming.company, incoming.title)
    best: tuple[float, JobPosting] | None = None
    for candidate in candidates:
        if candidate.status != "active":
            continue  # jamais de fusion avec une offre expirée
        # Filtre de compatibilité dure (07 §6.2.2).
        if (
            candidate.country_code is not None
            and incoming.country_code is not None
            and candidate.country_code != incoming.country_code
        ):
            continue
        if (
            candidate.contract is not None
            and incoming.contract is not None
            and candidate.contract != incoming.contract
        ):
            continue
        # Filtre géographique dur (07 §6.2.2) : deux offres géocodées à
        # plus de STAGE2_MAX_DISTANCE_KM ne sont JAMAIS le même poste. Sans
        # ce filtre, un titre et un premier paragraphe identiques suffisaient
        # à fusionner une offre parisienne et une offre lyonnaise (cosinus
        # 1,0000 mesuré en revue) — perte irréversible pour l'utilisateur.
        if _too_far_apart(candidate, incoming):
            continue
        if embedding is None or candidate.embedding is None:
            continue  # pas de décision sans embeddings (faux négatif préféré)
        candidate_vector = list(candidate.embedding)
        if len(candidate_vector) != len(embedding):
            # Dimensions hétérogènes = vecteurs issus de deux modèles
            # différents : la comparaison n'a aucun sens (08 §8 impose un
            # re-embedding complet à tout changement de modèle).
            logger.error(
                "dedup_stage2_dimension_mismatch posting=%s stored=%d incoming=%d",
                candidate.id, len(candidate_vector), len(embedding),
            )
            continue
        score = _cosine(candidate_vector, embedding)
        if score >= cosine_threshold and (best is None or score > best[0]):
            best = (score, candidate)
    if best is not None:
        logger.info(
            "dedup_stage2_hit posting=%s cosine=%.4f threshold=%.2f",
            best[1].id, best[0], cosine_threshold,
        )
    return best[1] if best else None


# ------------------------------------------------------------------- ingest
@dataclass(slots=True)
class IngestReport:
    """Compteurs d'un batch (métriques 07 §7.3)."""

    seen: int = 0
    created: int = 0  # dedup_new_posting_total
    updated: int = 0  # idempotence (source_id, external_ref)
    attached_stage1: int = 0  # dedup_stage1_hit_total
    attached_stage2: int = 0  # dedup_stage2_hit_total
    errors: int = 0  # ingestion_item_error_total


async def ingest_batch(
    source_slug: str,
    raw_jobs: list[RawJob],
    store: JobStore,
    *,
    geocoder: Geocoder | None = None,
    provider: LLMProvider | None = None,
    embedder: EmbeddingProvider | None = None,
    now: datetime | None = None,
) -> IngestReport:
    """Ingestion d'un batch d'offres brutes d'une source (07 §4.4, §6).

    Idempotente : rejouer le même batch ne crée ni doublon ni effet de
    bord. Une erreur sur un item n'arrête pas le batch (07 §4.5, classe
    « permanente requête »).

    ``embedder`` : fournisseur d'embeddings ; résolu par la fabrique quand
    il n'est pas passé (défaut local et déterministe, sans réseau — voir
    :mod:`app.ai.embeddings`). Un fournisseur inutilisable ne fait PAS
    échouer l'ingestion : les offres sont créées sans vecteur.
    """
    now = now or datetime.now(UTC)
    source = await store.get_source_by_slug(source_slug)
    if source is None:
        raise ValueError(f"source inconnue ou inactive : {source_slug!r}")

    if embedder is None:
        try:
            embedder = get_embedding_provider()
        except EmbeddingError:
            # Dimension incompatible ou aucun provider : l'ingestion reste
            # prioritaire sur les embeddings (D18) — trace bruyante, pas
            # d'interruption.
            logger.exception("embedding_provider_unavailable_for_ingestion")
            embedder = None

    aliases, canonicals = await store.skill_lookup()
    resolver = SkillResolver(aliases, canonicals)
    report = IngestReport()

    for raw in raw_jobs:
        report.seen += 1
        counters_before = (
            report.created, report.updated, report.attached_stage1, report.attached_stage2
        )
        try:
            # Savepoint par item : un échec DB (IntegrityError…) est annulé
            # au niveau de l'item sans invalider la session pour la suite
            # du batch (rollback du savepoint, pas de la transaction).
            async with store.savepoint():
                await _ingest_one(
                    store, source, raw, report,
                    geocoder=geocoder, resolver=resolver, provider=provider,
                    embedder=embedder, now=now,
                )
                await store.flush()
        except Exception:
            # Les compteurs suivent le rollback : l'item en erreur n'est pas
            # aussi compté created/updated/attached (métriques 07 §7.3).
            (report.created, report.updated,
             report.attached_stage1, report.attached_stage2) = counters_before
            report.errors += 1
            logger.exception(
                "ingestion_item_error source=%s external_ref=%s",
                source_slug, raw.external_ref,
            )
    return report


async def _ingest_one(
    store: JobStore,
    source: Source,
    raw: RawJob,
    report: IngestReport,
    *,
    geocoder: Geocoder | None,
    resolver: SkillResolver,
    provider: LLMProvider | None,
    now: datetime,
    #: ``None`` = offre ingérée sans vecteur (étage 2 sans décision) —
    #: défaut explicite pour rester appelable sans embeddings.
    embedder: EmbeddingProvider | None = None,
) -> None:
    normalized = normalize_raw(
        raw, source_slug=source.slug, geocoder=geocoder,
        resolver=resolver, provider=provider,
    )
    # Vecteur de l'offre ENTRANTE : il sert à la décision de l'étage 2 puis
    # à peupler ``job_postings.embedding`` (07 §5.6).
    embedding = _embed_job(embedder, normalized.title, normalized.description)

    # Idempotence (source_id, external_ref) — 07 §4.4 : mise à jour par la
    # MÊME source → re-normalisation directe (same_source=True), l'arbitrage
    # de fusion §6.3 ne vaut qu'entre sources concurrentes.
    existing_source = await store.get_job_source(source.id, raw.external_ref)
    if existing_source is not None:
        posting = await store.get_posting(existing_source.job_posting_id)
        if posting is None:
            raise DataIntegrityError(
                f"job_source {existing_source.id} orpheline : job_posting "
                f"{existing_source.job_posting_id} introuvable (intégrité FK)"
            )
        existing_source.original_url = raw.url
        if raw.posted_at is not None:
            existing_source.posted_at = raw.posted_at
        await _merge_posting(store, posting, normalized, now, same_source=True)
        _refresh_embedding(posting, normalized, embedding, embedder)
        report.updated += 1
        return

    # Dédup étage 1 : clé exacte (07 §6.1).
    posting = await store.get_posting_by_dedup_hash(normalized.dedup_hash)
    stage = 1
    if posting is None:
        # Étage 2 : candidats trigram + décision cosinus (D13) — opérant
        # dès que les deux offres portent un vecteur.
        posting = await _stage2_match(store, normalized, embedding)
        stage = 2

    if posting is not None:
        await _merge_posting(store, posting, normalized, now)
        _refresh_embedding(posting, normalized, embedding, embedder)
        if stage == 1:
            report.attached_stage1 += 1
        else:
            report.attached_stage2 += 1
    else:
        posting = JobPosting(
            id=uuid.uuid4(),
            dedup_hash=normalized.dedup_hash,
            title=normalized.title,
            company_name=normalized.company,
            description_text=normalized.description,
            language=normalized.language,
            sector_code=normalized.sector_code,
            seniority=normalized.seniority,
            seniority_conf=normalized.seniority_conf,
            experience_min=normalized.experience_min,
            experience_max=normalized.experience_max,
            contract=normalized.contract,
            contract_conf=normalized.contract_conf,
            remote=normalized.remote,
            remote_conf=normalized.remote_conf,
            salary_min=normalized.salary_min,
            salary_max=normalized.salary_max,
            salary_currency=normalized.salary_currency,
            salary_period=normalized.salary_period,
            status="withdrawn" if normalized.withdrawn else "active",
            country_code=normalized.country_code,
            first_seen_at=normalized.posted_at or now,
            last_seen_at=now,
            expires_at=normalized.expires_at,
            embedding=embedding,
        )
        await store.add(posting)
        for loc in normalized.locations:
            await store.add(JobLocation(
                id=uuid.uuid4(), job_posting_id=posting.id, raw_label=loc.raw_label,
                lat=loc.lat, lon=loc.lon, country_code=loc.country_code,
            ))
        for skill_id, label_raw, required, confidence in normalized.skills:
            await store.add(JobSkill(
                id=uuid.uuid4(), job_posting_id=posting.id, skill_id=skill_id,
                label_raw=label_raw, required=required, confidence=confidence,
            ))
        for code, level, confidence in normalized.languages:
            await store.add(JobLanguage(
                job_posting_id=posting.id, lang_code=code,
                min_level=level, confidence=confidence,
            ))
        report.created += 1

    # job_sources : chaque source conserve son original_url (07 §6.3.1).
    await store.add(JobSource(
        id=uuid.uuid4(),
        job_posting_id=posting.id,
        source_id=source.id,
        external_ref=raw.external_ref,
        original_url=raw.url,
        posted_at=raw.posted_at,
        ingested_at=now,
        raw_payload_key=None,  # renseigné par la tâche worker (S3 stub 🟡)
    ))


# --------------------------------------------------------------- expiration
@dataclass(slots=True)
class ExpirationReport:
    """Compteurs d'expiration par mécanisme (jobs_expired_total 07 §7.3)."""

    by_signal: int = 0  # mécanisme 1 : expires_at / withdrawn
    by_absence: int = 0  # mécanisme 2 : disparition du flux
    by_recheck: int = 0  # mécanisme 3 : re-check ciblé
    extinct_sources: int = 0


async def mark_expired(
    store: JobStore,
    *,
    now: datetime | None = None,
    source_id: uuid.UUID | None = None,
    present_external_refs: set[str] | None = None,
    skip_external_refs: set[str] | None = None,
    gone_job_source_ids: set[uuid.UUID] | None = None,
    absence_threshold: int = ABSENCE_THRESHOLD,
) -> ExpirationReport:
    """Expiration des offres selon les 3 mécanismes de 07 §4.6.

    1. Signal explicite : ``expires_at`` dépassé → ``expired`` (le signal
       « annulée/pourvue » est appliqué dès l'ingestion, statut
       ``withdrawn``) ;
    2. Disparition du flux : ``source_id`` + ``present_external_refs``
       fournis après une réconciliation complète RÉUSSIE — une job_source
       absente de ``absence_threshold`` (2 🟡) réconciliations consécutives
       est éteinte ; l'offre ne passe ``expired`` que si TOUTES ses
       job_sources sont éteintes (le multi-source protège, D13).
       ``skip_external_refs`` : job_sources d'un périmètre NON vérifié ce
       cycle (board/site en échec de fetch) — ni comptées absentes, ni
       remises à zéro (07 §4.5) ;
    3. Re-check ciblé : ``gone_job_source_ids`` = job_sources dont le GET
       unitaire a retourné 404/410 → éteintes immédiatement, même règle.
    """
    now = now or datetime.now(UTC)
    report = ExpirationReport()

    # Mécanisme 1 — job périodique sur expires_at.
    for posting in await store.postings_with_expired_deadline(now):
        if posting.status == "active":
            posting.status = "expired"
            report.by_signal += 1

    candidate_postings: dict[uuid.UUID, str] = {}  # posting_id → mécanisme

    # Mécanisme 2 — réconciliation complète.
    if source_id is not None and present_external_refs is not None:
        skip_external_refs = skip_external_refs or set()
        for job_source in await store.job_sources_for_source(source_id):
            if job_source.external_ref in skip_external_refs:
                continue  # périmètre non fetché ce cycle : compteur intact
            if job_source.external_ref in present_external_refs:
                await store.clear_source_absence(job_source.id)
            else:
                misses = await store.note_source_absence(job_source.id)
                if misses >= absence_threshold:
                    report.extinct_sources += 1
                    candidate_postings.setdefault(job_source.job_posting_id, "absence")

    # Mécanisme 3 — re-check ciblé (404/410 sur original_url) :
    # extinction immédiate de la job_source (compteur porté au seuil).
    for gone_id in gone_job_source_ids or set():
        while await store.absence_count(gone_id) < absence_threshold:
            await store.note_source_absence(gone_id)
        posting_id = await store.posting_id_of_job_source(gone_id)
        if posting_id is not None:
            candidate_postings.setdefault(posting_id, "recheck")

    # Décision : expired ssi TOUTES les job_sources du posting sont éteintes.
    for posting_id, mechanism in candidate_postings.items():
        candidate = await store.get_posting(posting_id)
        if candidate is None or candidate.status != "active":
            continue
        siblings = await store.job_sources_for_posting(posting_id)
        all_extinct = True
        for sibling in siblings:
            if await store.absence_count(sibling.id) < absence_threshold:
                all_extinct = False
                break
        if all_extinct:
            candidate.status = "expired"
            if mechanism == "absence":
                report.by_absence += 1
            else:
                report.by_recheck += 1
    await store.flush()
    return report


# ------------------------------------------------------- implémentation SQL
class SqlAlchemyJobStore:
    """Implémentation PostgreSQL du :class:`JobStore` (production).

    Les requêtes étage 2 (trigram) sont ÉCRITES mais non testées
    unitairement 🟡 (nécessitent pg_trgm — validation en intégration M2).
    Les compteurs d'absence (07 §4.6.2) sont persistés dans
    ``connector_state.absence_counters`` (jsonb, migration 0003) : ils
    survivent aux redémarrages des workers et restent cohérents entre
    cycles de réconciliation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_source_by_slug(self, slug: str) -> Source | None:
        result = await self._session.execute(select(Source).where(Source.slug == slug))
        return result.scalar_one_or_none()

    async def get_job_source(
        self, source_id: uuid.UUID, external_ref: str
    ) -> JobSource | None:
        result = await self._session.execute(
            select(JobSource).where(
                JobSource.source_id == source_id,
                JobSource.external_ref == external_ref,
            )
        )
        return result.scalar_one_or_none()

    async def get_posting(self, posting_id: uuid.UUID) -> JobPosting | None:
        return await self._session.get(JobPosting, posting_id)

    async def get_posting_by_dedup_hash(self, dedup_hash: str) -> JobPosting | None:
        result = await self._session.execute(
            select(JobPosting).where(JobPosting.dedup_hash == dedup_hash)
        )
        return result.scalar_one_or_none()

    async def stage2_candidates(self, company_name: str, title: str) -> list[JobPosting]:
        # Index trigram existants : idx_jobs_title_trgm, idx_jobs_company_trgm.
        result = await self._session.execute(
            text(
                """
                SELECT id FROM job_postings
                WHERE status = 'active'
                  AND similarity(company_name, :company) > :company_threshold
                  AND similarity(title, :title) > :title_threshold
                LIMIT :limit
                """
            ),
            {
                "company": company_name,
                "title": title,
                "company_threshold": STAGE2_COMPANY_SIMILARITY,
                "title_threshold": STAGE2_TITLE_SIMILARITY,
                "limit": STAGE2_CANDIDATE_LIMIT,
            },
        )
        ids = [row[0] for row in result]
        if not ids:
            return []
        # ``selectinload(locations)`` n'est PAS une optimisation : le filtre
        # géographique de l'étage 2 (``_too_far_apart``) lit
        # ``candidate.locations``. En SQLAlchemy async, un chargement
        # paresseux lève ``MissingGreenlet`` — l'exception remonte au
        # gestionnaire par item, qui la journalise et **abandonne l'offre**.
        # Résultat mesuré sur le corpus de démonstration : toute offre
        # atteignant ce filtre était PERDUE, avec pour seule trace une ligne
        # ``ingestion_item_error``. Or atteindre ce filtre est le cas NORMAL
        # avec de vraies sources : c'est précisément la situation que la
        # dédup existe pour traiter.
        postings = await self._session.execute(
            select(JobPosting)
            .where(JobPosting.id.in_(ids))
            .options(selectinload(JobPosting.locations))
        )
        return list(postings.scalars())

    async def skill_lookup(self) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID]]:
        aliases = await self._session.execute(select(SkillAlias.alias, SkillAlias.skill_id))
        canonicals = await self._session.execute(select(Skill.canonical_label, Skill.id))
        return dict(aliases.all()), dict(canonicals.all())  # type: ignore[arg-type]

    async def locations_for(self, posting_id: uuid.UUID) -> list[JobLocation]:
        result = await self._session.execute(
            select(JobLocation).where(JobLocation.job_posting_id == posting_id)
        )
        return list(result.scalars())

    async def skills_for(self, posting_id: uuid.UUID) -> list[JobSkill]:
        result = await self._session.execute(
            select(JobSkill).where(JobSkill.job_posting_id == posting_id)
        )
        return list(result.scalars())

    async def languages_for(self, posting_id: uuid.UUID) -> list[JobLanguage]:
        result = await self._session.execute(
            select(JobLanguage).where(JobLanguage.job_posting_id == posting_id)
        )
        return list(result.scalars())

    async def job_sources_for_source(self, source_id: uuid.UUID) -> list[JobSource]:
        result = await self._session.execute(
            select(JobSource).where(JobSource.source_id == source_id)
        )
        return list(result.scalars())

    async def job_sources_for_posting(self, posting_id: uuid.UUID) -> list[JobSource]:
        result = await self._session.execute(
            select(JobSource).where(JobSource.job_posting_id == posting_id)
        )
        return list(result.scalars())

    async def posting_id_of_job_source(self, job_source_id: uuid.UUID) -> uuid.UUID | None:
        result = await self._session.execute(
            select(JobSource.job_posting_id).where(JobSource.id == job_source_id)
        )
        return result.scalar_one_or_none()

    async def postings_with_expired_deadline(self, now: datetime) -> list[JobPosting]:
        result = await self._session.execute(
            select(JobPosting).where(
                JobPosting.status == "active",
                JobPosting.expires_at.is_not(None),
                JobPosting.expires_at <= now,
            )
        )
        return list(result.scalars())

    # -- compteurs d'absence persistés (connector_state.absence_counters) --
    async def _state_of_job_source(self, job_source_id: uuid.UUID) -> ConnectorState | None:
        """``connector_state`` de la source d'une job_source (créé si absent)."""
        source_id = await self._session.scalar(
            select(JobSource.source_id).where(JobSource.id == job_source_id)
        )
        if source_id is None:
            return None
        state = await self._session.get(ConnectorState, source_id)
        if state is None:
            state = ConnectorState(source_id=source_id, absence_counters={})
            self._session.add(state)
        return state

    async def note_source_absence(self, job_source_id: uuid.UUID) -> int:
        state = await self._state_of_job_source(job_source_id)
        if state is None:
            return 0  # job_source disparue entre-temps
        counters = dict(state.absence_counters or {})
        key = str(job_source_id)
        counters[key] = int(counters.get(key, 0)) + 1
        state.absence_counters = counters  # réaffectation → dirty tracking
        return counters[key]

    async def clear_source_absence(self, job_source_id: uuid.UUID) -> None:
        state = await self._state_of_job_source(job_source_id)
        if state is None:
            return
        counters = dict(state.absence_counters or {})
        if counters.pop(str(job_source_id), None) is not None:
            state.absence_counters = counters

    async def absence_count(self, job_source_id: uuid.UUID) -> int:
        state = await self._state_of_job_source(job_source_id)
        if state is None:
            return 0
        return int((state.absence_counters or {}).get(str(job_source_id), 0))

    async def add(self, obj: object) -> None:
        self._session.add(obj)

    async def flush(self) -> None:
        await self._session.flush()

    def savepoint(self) -> AbstractAsyncContextManager[object]:
        """SAVEPOINT (``begin_nested``) : l'échec d'un item est annulé sans
        invalider la transaction englobante du batch (07 §4.5)."""
        return self._session.begin_nested()

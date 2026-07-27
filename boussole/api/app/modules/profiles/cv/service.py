"""Logique métier du sous-package CV (F-B, D05).

Règles portées ici :

- upload : taille ≤ 10 Mo (413 ``too_large``), MIME réel par MAGIC BYTES
  (``%PDF-`` / zip DOCX contenant ``word/document.xml``) — jamais le
  Content-Type déclaré (415 ``unsupported_format``, 12 §5) ; quota
  5 uploads/jour (429 ``rate_limited`` + Retry-After, 12 §1) VÉRIFIÉ AVANT
  stockage (AC-B-4) ; puis stockage objet + ligne ``cv_documents`` statut
  ``uploaded`` + tâche Celery ``ai.parse_cv`` (file ``ai``) ;
- lecture : statut + si ``parsed``, la sortie d'extraction transformée en
  PROPOSITION de profil (provenance ``cv_extraction`` + confidence par
  champ) — RIEN n'est écrit dans le profil (RM-B-1) ;
- apply 🟡 : fusion explicite dans le profil — les champs existants
  ``user_input``/``user_confirmed`` ne sont JAMAIS écrasés (F-B alt. 7),
  les ajouts portent ``source='cv_extraction'``, ``version``++ ;
- ``trace_id`` (champ additif, 04 Flux 1) : identifiant de corrélation
  renvoyé sur un échec d'extraction, pour le bloc repliable « détails
  techniques » de l'écran d'import — voir :func:`failure_trace_id`.

Hypothèses 🟡 : ordre de validation taille → magic bytes → quota (un
fichier invalide ne consomme pas le quota) ; un upload dont l'extraction
échoue reste décompté du quota (F-B alt. 5 propose l'inverse — à trancher).
"""

import io
import json
import uuid
import zipfile
from collections.abc import Callable
from datetime import date
from typing import cast

from pydantic import ValidationError

from app.ai.tasks.extract_cv import CvExtraction
from app.core.problems import Problem
from app.core.ratelimit import FixedWindowRateLimiter
from app.core.storage import ObjectNotFoundError, ObjectStorage
from app.modules.profiles.cv.models import CvDocument, ExtractionRun
from app.modules.profiles.cv.repository import CvDocumentsRepository
from app.modules.profiles.cv.safety import UnsafeDocumentError, assert_archive_safe
from app.modules.profiles.cv.schemas import (
    ApplyInput,
    CvDocumentOut,
    CvErrorCode,
    CvProposal,
    CvStatus,
    ProposedEducation,
    ProposedExperience,
    ProposedLanguage,
    ProposedSkill,
)
from app.modules.profiles.models import (
    Profile,
    ProfileEducation,
    ProfileExperience,
    ProfileLanguage,
    ProfileSkill,
)
from app.modules.profiles.repository import ProfilesRepository
from app.modules.profiles.schemas import ProfileOut, Provenance
from app.modules.profiles.service import (
    ProfilesService,
    compute_total_experience_years,
    to_profile_out,
)

#: Limites normatives (F-B, 12 §1) — 10 Mo, 5 uploads/jour.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_DAILY_LIMIT = 5
UPLOAD_WINDOW_SECONDS = 24 * 3600

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

#: Signature d'enqueue de la tâche Celery ``ai.parse_cv`` (injectable tests).
ParseEnqueuer = Callable[[uuid.UUID], None]


def sniff_mime(data: bytes) -> str | None:
    """MIME réel par magic bytes (12 §5) — jamais le Content-Type déclaré.

    - PDF : préfixe ``%PDF-`` ;
    - DOCX : archive zip (``PK\\x03\\x04``) contenant ``word/document.xml``
      (un zip quelconque n'est PAS un DOCX) ;
    - sinon : ``None`` (415 ``unsupported_format``).
    """
    if data.startswith(b"%PDF-"):
        return PDF_MIME
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "word/document.xml" in archive.namelist():
                    # Bombe de décompression : refusée DÈS L'UPLOAD (415) plutôt
                    # que d'accepter un 202 puis de mettre le worker à terre.
                    # Le contrôle ne lit que le catalogue, jamais les données.
                    assert_archive_safe(data)
                    return DOCX_MIME
        except zipfile.BadZipFile:
            return None
    return None


def _not_found() -> Problem:
    """404 anti-énumération (12 §5) : document absent OU d'un autre utilisateur."""
    return Problem(
        status=404,
        code="not_found",
        title="Ressource introuvable",
        detail="Document CV introuvable.",
    )


def _partial_date(value: str) -> date:
    """``YYYY`` → 1er janvier, ``YYYY-MM`` → 1er du mois 🟡 (schéma cv_extraction)."""
    parts = value.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    return date(year, month, 1)


#: Statuts d'``extraction_runs`` traduisant un échec d'appel LLM (RM-B-3) —
#: le succès est ``success``, les autres valeurs sont des échecs.
FAILED_RUN_STATUSES = ("schema_error", "failed")


def failure_trace_id(runs: list[ExtractionRun]) -> str | None:
    """Identifiant de corrélation du dernier échec d'extraction (04 Flux 1).

    Fonction pure. 🟡 HYPOTHÈSE DOCUMENTÉE : aucune colonne de corrélation
    n'existe aujourd'hui (``cv_documents`` porte ``error_code``, pas de
    ``trace_id``) et le correctif ne crée PAS de migration. L'``id`` du
    dernier ``extraction_run`` en échec fait donc office de trace_id : il est
    stable, unique, déjà persisté, et corrèle la réponse API aux journaux du
    worker (qui logguent l'exception au moment du run). À remplacer par le
    ``trace_id`` de la requête (D20) le jour où une colonne dédiée est
    ajoutée à ``extraction_runs``.

    ``None`` s'il n'y a aucun run en échec : les autres ``error_code``
    (``unreadable``, ``image_only_pdf``, …) échouent AVANT tout appel LLM et
    ne créent donc pas de run — il n'y a rien à corréler.
    """
    failures = [run for run in runs if run.status in FAILED_RUN_STATUSES]
    if not failures:
        return None
    # ``created_at`` est posé par PostgreSQL (``server_default now()``) : il
    # n'est absent que sur une instance jamais persistée — on retombe alors
    # sur l'ordre de lecture plutôt que de lever une comparaison impossible.
    dated = [run for run in failures if run.created_at is not None]
    latest = max(dated, key=lambda run: run.created_at) if dated else failures[-1]
    return str(latest.id)


def build_proposal(extraction: CvExtraction) -> CvProposal:
    """Sortie d'extraction → proposition de profil (provenance cv_extraction).

    Fonction pure : chaque item porte ``Provenance(source='cv_extraction',
    confidence=…)`` (D05), un ``item_id`` DÉTERMINISTE et stable
    (``<type>:<index dans la sortie d'extraction stockée>`` — deux GET sur le
    même run produisent les mêmes ids) et ``evidence_quote`` (citation source,
    ``None`` pour les langues sans evidence). Les items dont les dates
    converties seraient incohérentes (fin < début) sont écartés défensivement
    — l'index d'origine est conservé pour les items suivants (stabilité).
    """
    experiences: list[ProposedExperience] = []
    for index, exp in enumerate(extraction.experiences):
        start = _partial_date(exp.start_date)
        end = _partial_date(exp.end_date) if exp.end_date is not None else None
        if end is not None and end < start:
            continue
        experiences.append(
            ProposedExperience(
                item_id=f"experience:{index}",
                title=exp.title,
                company=exp.company,
                start_date=start,
                end_date=end,
                description=exp.description,
                evidence_quote=exp.evidence.quote,
                provenance=Provenance(source="cv_extraction", confidence=exp.confidence),
            )
        )
    return CvProposal(
        headline=extraction.headline,
        summary=extraction.summary,
        experiences=experiences,
        educations=[
            ProposedEducation(
                item_id=f"education:{index}",
                degree=edu.degree,
                institution=edu.institution,
                start_year=edu.start_year,
                end_year=edu.end_year,
                evidence_quote=edu.evidence.quote,
                provenance=Provenance(source="cv_extraction", confidence=edu.confidence),
            )
            for index, edu in enumerate(extraction.educations)
        ],
        skills=[
            ProposedSkill(
                item_id=f"skill:{index}",
                label=skill.label,
                evidence_quote=skill.evidence.quote,
                provenance=Provenance(source="cv_extraction", confidence=skill.confidence),
            )
            for index, skill in enumerate(extraction.skills)
        ],
        languages=[
            ProposedLanguage(
                item_id=f"language:{index}",
                lang_code=lang.lang_code,
                level=lang.level,
                evidence_quote=lang.evidence.quote if lang.evidence is not None else None,
                provenance=Provenance(source="cv_extraction", confidence=lang.confidence),
            )
            for index, lang in enumerate(extraction.languages)
        ],
    )


def filter_proposal(proposal: CvProposal, selection: ApplyInput) -> CvProposal:
    """Restreint la proposition à la sélection de revue (04 Flux 1 §5).

    Fonction pure :
    - ``item_ids is None`` → tous les items sont conservés ;
    - sinon seuls les items dont ``item_id`` est coché sont conservés ; un id
      inconnu (item disparu d'une ré-extraction, faute de frappe) est ignoré
      silencieusement 🟡 — la fusion reste best-effort, sans erreur ;
    - ``include_headline`` / ``include_summary`` à ``False`` retirent les
      champs racine correspondants.
    """
    selected = None if selection.item_ids is None else set(selection.item_ids)

    def _keep(item_id: str) -> bool:
        return selected is None or item_id in selected

    return CvProposal(
        headline=proposal.headline if selection.include_headline else None,
        summary=proposal.summary if selection.include_summary else None,
        experiences=[exp for exp in proposal.experiences if _keep(exp.item_id)],
        educations=[edu for edu in proposal.educations if _keep(edu.item_id)],
        skills=[skill for skill in proposal.skills if _keep(skill.item_id)],
        languages=[lang for lang in proposal.languages if _keep(lang.item_id)],
    )


def merge_proposal(profile: Profile, proposal: CvProposal, cv_document_id: uuid.UUID) -> None:
    """Fusionne la proposition dans le profil (F-B alt. 7) — mutation en place.

    Invariants :
    - un champ existant ``user_input``/``user_confirmed`` n'est JAMAIS écrasé ;
    - headline/summary ne sont posés que s'ils sont vides (pas de provenance
      en base sur les champs racine — l'existant est réputé saisi 🟡) ;
    - doublons ignorés : expérience (titre+entreprise+date de début),
      formation (diplôme+établissement), compétence (label, casse ignorée),
      langue (lang_code — contrainte d'unicité SQL) ;
    - les ajouts portent ``source='cv_extraction'`` + confidence (RM-B-1).

    L'appelant incrémente la version et commit.
    """
    if profile.headline is None and proposal.headline is not None:
        profile.headline = proposal.headline
    if profile.summary is None and proposal.summary is not None:
        profile.summary = proposal.summary

    existing_experiences = {
        (exp.title.casefold(), exp.company.casefold(), exp.start_date)
        for exp in profile.experiences
    }
    for prop_exp in proposal.experiences:
        key = (prop_exp.title.casefold(), prop_exp.company.casefold(), prop_exp.start_date)
        if key in existing_experiences:
            continue  # jamais d'écrasement — l'existant prime, quelle que soit sa source
        existing_experiences.add(key)
        profile.experiences.append(
            ProfileExperience(
                id=uuid.uuid4(),
                profile_id=profile.id,
                title=prop_exp.title,
                company=prop_exp.company,
                sector_code=None,
                start_date=prop_exp.start_date,
                end_date=prop_exp.end_date,
                description=prop_exp.description,
                position=len(profile.experiences),
                source="cv_extraction",
                confidence=prop_exp.provenance.confidence,
            )
        )

    existing_educations = {
        (edu.degree.casefold(), edu.institution.casefold()) for edu in profile.educations
    }
    for prop_edu in proposal.educations:
        edu_key = (prop_edu.degree.casefold(), prop_edu.institution.casefold())
        if edu_key in existing_educations:
            continue
        existing_educations.add(edu_key)
        profile.educations.append(
            ProfileEducation(
                id=uuid.uuid4(),
                profile_id=profile.id,
                degree=prop_edu.degree,
                institution=prop_edu.institution,
                start_year=prop_edu.start_year,
                end_year=prop_edu.end_year,
                source="cv_extraction",
                confidence=prop_edu.provenance.confidence,
            )
        )

    existing_skills = {skill.label_raw.casefold() for skill in profile.skills}
    for prop_skill in proposal.skills:
        label_key = prop_skill.label.casefold()
        if label_key in existing_skills:
            continue
        existing_skills.add(label_key)
        profile.skills.append(
            ProfileSkill(
                id=uuid.uuid4(),
                profile_id=profile.id,
                skill_id=None,  # rapprochement taxonomie 🟡 (RM-C-6, hors périmètre M4)
                label_raw=prop_skill.label,
                source="cv_extraction",
                confidence=prop_skill.provenance.confidence,
            )
        )

    existing_langs = {lang.lang_code for lang in profile.languages}
    for prop_lang in proposal.languages:
        if prop_lang.lang_code in existing_langs:
            continue
        existing_langs.add(prop_lang.lang_code)
        profile.languages.append(
            ProfileLanguage(
                id=uuid.uuid4(),
                profile_id=profile.id,
                lang_code=prop_lang.lang_code,
                level=prop_lang.level,
                source="cv_extraction",
                confidence=prop_lang.provenance.confidence,
            )
        )

    profile.total_experience_years = compute_total_experience_years(
        (exp.start_date, exp.end_date) for exp in profile.experiences
    )
    profile.source_cv_id = cv_document_id


class CvService:
    def __init__(
        self,
        repository: CvDocumentsRepository,
        profiles_repository: ProfilesRepository,
        storage: ObjectStorage,
        rate_limiter: FixedWindowRateLimiter,
        enqueue_parse: ParseEnqueuer,
    ) -> None:
        self._repository = repository
        self._profiles = profiles_repository
        self._storage = storage
        self._rate_limiter = rate_limiter
        self._enqueue_parse = enqueue_parse

    # ------------------------------------------------------------ upload

    async def upload(self, user_id: uuid.UUID, filename: str, data: bytes) -> CvDocumentOut:
        """POST /cv-documents : validations synchrones puis 202 (F-B nominal 1-2)."""
        if len(data) > MAX_UPLOAD_BYTES:
            raise Problem(
                status=413,
                code="too_large",
                title="Fichier trop volumineux",
                detail="Le fichier dépasse la taille maximale de 10 Mo.",
            )
        try:
            mime = sniff_mime(data)
        except UnsafeDocumentError as exc:
            raise Problem(
                status=415,
                code="unsupported_format",
                title="Document refusé",
                detail=(
                    "Ce document ne peut pas être traité en toute sécurité "
                    "(archive anormalement compressée)."
                ),
            ) from exc
        if mime is None:
            raise Problem(
                status=415,
                code="unsupported_format",
                title="Format non supporté",
                detail=(
                    "Seuls les fichiers PDF et DOCX sont acceptés "
                    "(vérification par magic bytes, pas par extension)."
                ),
            )
        quota = await self._rate_limiter.hit(
            "cv_upload",
            str(user_id),
            limit=UPLOAD_DAILY_LIMIT,
            window_seconds=UPLOAD_WINDOW_SECONDS,
        )
        if not quota.allowed:
            # AC-B-4 : 429 + Retry-After, aucun fichier stocké.
            raise Problem(
                status=429,
                code="rate_limited",
                title="Quota d'upload atteint",
                detail=f"Maximum {UPLOAD_DAILY_LIMIT} imports de CV par jour.",
                headers={"Retry-After": str(quota.retry_after)},
            )

        document_id = uuid.uuid4()
        extension = "pdf" if mime == PDF_MIME else "docx"
        file_key = f"cv/{user_id}/{document_id}/original.{extension}"
        self._storage.put(file_key, data)
        document = await self._repository.add(
            CvDocument(
                id=document_id,
                user_id=user_id,
                file_key=file_key,
                filename=filename,
                mime_type=mime,
                size_bytes=len(data),
                status="uploaded",
                raw_text_key=None,
                error_code=None,
            )
        )
        self._enqueue_parse(document.id)
        return self._to_out(document, proposal=None, warnings=[])

    # ------------------------------------------------------------ lecture

    async def get(self, user_id: uuid.UUID, document_id: uuid.UUID) -> CvDocumentOut:
        """GET /cv-documents/{id} : statut + proposition si ``parsed`` (RM-B-1).

        Sur un document ``failed``, ``trace_id`` porte l'identifiant de
        corrélation de l'échec d'extraction (04 Flux 1) — ``null`` sinon.
        """
        document = await self._repository.get_for_user(user_id, document_id)
        if document is None:
            raise _not_found()
        extraction = await self._load_extraction(document)
        proposal = build_proposal(extraction) if extraction is not None else None
        warnings = list(extraction.warnings) if extraction is not None else []
        trace_id = await self._failure_trace_id(document)
        return self._to_out(
            document, proposal=proposal, warnings=warnings, trace_id=trace_id
        )

    # ------------------------------------------------------------ apply 🟡

    async def apply(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        selection: ApplyInput | None = None,
    ) -> ProfileOut:
        """POST /cv-documents/{id}/apply 🟡 : fusion explicite dans le profil.

        Précondition : document ``parsed`` avec une sortie d'extraction
        disponible, sinon 409 ``cv_not_parsed``. ``selection`` restreint la
        fusion aux items cochés en revue (:func:`filter_proposal` — ``None``
        ou corps absent = tout appliquer, rétrocompatible ; id inconnu ignoré
        silencieusement 🟡). Fusion sans écrasement (:func:`merge_proposal`,
        règles inchangées) + ``version``++ (RM-C-4).
        """
        document = await self._repository.get_for_user(user_id, document_id)
        if document is None:
            raise _not_found()
        extraction = await self._load_extraction(document)
        if document.status != "parsed" or extraction is None:
            raise Problem(
                status=409,
                code="cv_not_parsed",
                title="Extraction non disponible",
                detail=(
                    "La proposition ne peut être appliquée que sur un CV au "
                    f"statut « parsed » (statut actuel : {document.status})."
                ),
            )
        profile = await self._profiles.get_by_user(user_id)
        if profile is None:
            profile = await self._profiles.create_draft(user_id)
        proposal = build_proposal(extraction)
        if selection is not None:
            proposal = filter_proposal(proposal, selection)
        merge_proposal(profile, proposal, document.id)
        # Réutilise la règle RM-C-4 du service profiles (version++, updated_at).
        ProfilesService._bump_version(profile)
        await self._profiles.commit()
        return to_profile_out(profile)

    # ------------------------------------------------------------ interne

    async def _failure_trace_id(self, document: CvDocument) -> str | None:
        """trace_id de l'échec d'extraction — aucune requête si non ``failed``."""
        if document.status != "failed":
            return None
        return failure_trace_id(await self._repository.runs_for_document(document.id))

    async def _load_extraction(self, document: CvDocument) -> CvExtraction | None:
        """Sortie validée du dernier run en succès — None si indisponible."""
        if document.status != "parsed":
            return None
        run = await self._repository.latest_success_run(document.id)
        if run is None or run.output_key is None:
            return None
        try:
            raw = self._storage.get(run.output_key)
            return CvExtraction.model_validate(json.loads(raw.decode("utf-8")))
        except (ObjectNotFoundError, ValueError, ValidationError):
            # Sortie disparue ou corrompue : statut conservé, proposition vide.
            return None

    @staticmethod
    def _to_out(
        document: CvDocument,
        *,
        proposal: CvProposal | None,
        warnings: list[str],
        trace_id: str | None = None,
    ) -> CvDocumentOut:
        return CvDocumentOut(
            id=document.id,
            filename=document.filename,
            status=cast(CvStatus, document.status),
            error_code=cast(CvErrorCode | None, document.error_code),
            extraction_warnings=warnings,
            proposal=proposal,
            trace_id=trace_id,
        )

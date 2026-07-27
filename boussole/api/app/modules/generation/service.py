"""Logique métier du module generation (F-L/M/N/O, D10) — jalon M4.

Règles portées ici :

- ``POST /generations`` : Idempotency-Key UUID OBLIGATOIRE (RM-L-4, 422
  ``validation_error`` sinon — l'openapi la marque optionnelle au niveau du
  paramètre partagé, la règle F-L prime 🟡), rejeu ≤ 24 h → réponse d'origine
  + ``Idempotent-Replay: true`` (clé scopée utilisateur, Redis volatile
  D17) ; préconditions : profil validé (409 ``profile_not_validated``),
  ``job_id`` requis sauf ``cv_optimization`` (422), offre lisible selon la
  règle du module jobs (404 — withdrawn ou expirée > 12 mois), offre expirée
  lisible → 409 ``job_expired`` (RM-L-6) ; quotas 10/h et 40/j (RM-L-4,
  429 + ``Retry-After``) → ligne ``pending`` + tâche ``ai.generate`` en file ;
- ``PATCH`` : brouillon uniquement (409 ``generation_not_editable`` 🟡
  sinon) ; l'édition manuelle LÈVE le contrôle d'ancrage (Q6 🟡) :
  ``manually_edited = true``, ``anchoring_check`` → null + note de
  responsabilité dans la réponse ;
- ``validate`` : draft → validated (D10) ; un contrôle d'ancrage ``failed``
  non levé par une édition manuelle bloque la validation (409
  ``generation_not_anchored`` 🟡 — « jamais présenté comme prêt ») ;
- ``export`` : exige ``validated`` (409 ``generation_not_validated``) ET
  ``validated_at`` renseigné — vérification APPLICATIVE du CHECK SQL
  ``status <> 'exported' OR validated_at IS NOT NULL`` (RM-L-3) ; format
  ``text`` servi inline ; ``pdf``/``docx`` → 501 documenté (M5 🟡, D10 :
  export = copie/téléchargement, jamais d'envoi) ;
- quotas : compteurs fenêtre fixe sur le Redis volatile — scope « générations »
  seul 🟡 (Q5 : partage avec les explications non arbitré, les explications
  ne consomment pas ce quota au M4).

L'orchestration worker (:func:`execute_generation`) vit ici pour être
exécutable à l'identique par la tâche Celery (session SQL) et par les tests
(fakes en mémoire) : statuts ``processing`` → ``draft``/``failed``.
"""

import base64
import binascii
import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from app.ai.providers.base import LLMProvider
from app.ai.tasks.generate import (
    JOB_EXCERPT_LIMITS,
    PROMPT_VERSIONS,
    TASK_BY_DOC_TYPE,
    GenerationTaskError,
    run_generation_task,
)
from app.core.problems import Problem
from app.core.ratelimit import FixedWindowRateLimiter
from app.modules.generation.models import GeneratedDocument, api_status
from app.modules.generation.repository import GenerationRepository
from app.modules.generation.schemas import (
    AnchoringCheckOut,
    ExportOut,
    GeneratedDocumentOut,
    GenerationCreate,
    GenerationPage,
    GenerationPatch,
)
from app.modules.jobs.models import JobPosting
from app.modules.jobs.service import EXPIRED_RETENTION
from app.modules.profiles.models import Profile
from app.modules.profiles.repository import ProfilesRepository

logger = logging.getLogger(__name__)

#: Quotas LLM (RM-L-4, 12-api-contracts §1) — fenêtre fixe Redis volatile.
QUOTA_PER_HOUR = 10
QUOTA_PER_DAY = 40

#: TTL des clés d'idempotence (RM-L-4) : 24 h.
IDEMPOTENCY_TTL_SECONDS = 24 * 3600

#: Tri du curseur keyset de GET /generations (created_at DESC, id DESC).
_CURSOR_SORT = "generations"

#: Note de responsabilité après édition manuelle (Q6 🟡, D10).
MANUAL_EDIT_NOTE = (
    "Contenu édité manuellement : le contrôle d'ancrage automatique est levé — "
    "le texte est sous votre responsabilité, relisez-le avant validation."
)

#: Fabrique d'enfilement de la tâche ``ai.generate`` — injectable (tests).
Enqueuer = Callable[[uuid.UUID], None]


# ---------------------------------------------------------------- problems


def _profile_not_validated() -> Problem:
    return Problem(
        status=409,
        code="profile_not_validated",
        title="Profil non validé",
        detail="Validez votre profil avant de générer un contenu.",
    )


def _job_not_found() -> Problem:
    return Problem(
        status=404,
        code="not_found",
        title="Ressource introuvable",
        detail="Offre introuvable.",
    )


def _job_expired() -> Problem:
    return Problem(
        status=409,
        code="job_expired",
        title="Offre expirée",
        detail="Cette offre est expirée : aucune génération possible (RM-L-6).",
    )


def _generation_not_found() -> Problem:
    return Problem(
        status=404,
        code="not_found",
        title="Ressource introuvable",
        detail="Document généré introuvable.",
    )


def _generation_not_validated() -> Problem:
    return Problem(
        status=409,
        code="generation_not_validated",
        title="Validation requise",
        detail="Ce document doit être relu et validé avant export.",
    )


def _rate_limited(retry_after: int, window_label: str) -> Problem:
    return Problem(
        status=429,
        code="rate_limited",
        title="Trop de requêtes",
        detail=f"Quota de générations atteint ({window_label}). Réessayez plus tard.",
        headers={"Retry-After": str(retry_after)},
    )


# ---------------------------------------------------------------- curseur
# Même principe que le module jobs (base64 URL-safe d'un tuple keyset), mais
# codec LOCAL : le décodeur jobs ne type les valeurs datetime que pour son
# tri « date » — le tri de la bibliothèque est (created_at DESC, id DESC).


def _encode_generation_cursor(created_at: datetime, last_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"s": _CURSOR_SORT, "v": created_at.isoformat(), "id": str(last_id)}
    )
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _invalid_cursor() -> Problem:
    return Problem(
        status=422,
        code="invalid_cursor",
        title="Curseur invalide",
        detail="Le curseur de pagination est illisible ou périmé. "
        "Relancez la requête sans curseur.",
    )


def _decode_generation_cursor(raw: str) -> tuple[datetime, uuid.UUID]:
    """Décode le curseur opaque — toute anomalie → 422 ``invalid_cursor``."""
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        if payload["s"] != _CURSOR_SORT:
            raise ValueError("curseur incompatible avec cette liste")
        created_at = datetime.fromisoformat(payload["v"])
        last_id = uuid.UUID(payload["id"])
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, KeyError,
            TypeError, ValueError) as exc:
        raise _invalid_cursor() from exc
    return created_at, last_id


# ---------------------------------------------------------------- règle jobs


def job_is_readable(posting: JobPosting) -> bool:
    """Règle de lisibilité du module jobs (RM-E-4), réutilisée à l'identique.

    ``withdrawn`` → illisible (404) ; ``expired`` → lisible 12 mois
    (:data:`app.modules.jobs.service.EXPIRED_RETENTION`) puis 404.
    """
    if posting.status == "withdrawn":
        return False
    if posting.status == "expired":
        reference = posting.expires_at or posting.last_seen_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return datetime.now(UTC) - reference <= EXPIRED_RETENTION
    return True


# ---------------------------------------------------------------- payloads IA


def collect_profile_refs(profile: Profile) -> frozenset[str]:
    """Références RÉELLES du profil — seule vérité du contrôle d'ancrage.

    Cohérent avec :func:`build_profile_payload` : les éléments non confirmés
    (``source='cv_extraction'``) n'entrent pas au prompt, ils ne sont donc
    pas des ancres valides non plus. ``summary`` n'est une référence valide
    que si le résumé existe : une claim fondée sur un résumé vide serait une
    invention.
    """
    refs = {f"experience:{e.id}" for e in profile.experiences if e.source != "cv_extraction"}
    refs |= {f"skill:{s.id}" for s in profile.skills if s.source != "cv_extraction"}
    refs |= {f"education:{e.id}" for e in profile.educations if e.source != "cv_extraction"}
    if profile.summary:
        refs.add("summary")
    return frozenset(refs)


def build_profile_payload(profile: Profile) -> dict[str, Any]:
    """Payload profil MINIMISÉ pour le prompt (08 §2.2, D09, RM-T-7).

    Uniquement les données professionnelles structurées du profil validé,
    chaque élément avec son ``ref`` — JAMAIS nom, e-mail, téléphone ou
    adresse (ces champs ne vivent d'ailleurs pas dans les tables profil).
    Les éléments ``source='cv_extraction'`` non confirmés sont exclus
    (défensif : la validation du profil promeut normalement tout en
    ``user_confirmed``, D05).
    """

    def _confirmed(source: str) -> bool:
        return source != "cv_extraction"

    return {
        "headline": profile.headline,
        "summary": {"ref": "summary", "text": profile.summary} if profile.summary else None,
        "seniority": profile.seniority,
        "total_experience_years": (
            float(profile.total_experience_years)
            if profile.total_experience_years is not None
            else None
        ),
        "experiences": [
            {
                "ref": f"experience:{e.id}",
                "title": e.title,
                "company": e.company,
                "start_date": e.start_date.isoformat(),
                "end_date": e.end_date.isoformat() if e.end_date else None,
                "description": e.description,
            }
            for e in profile.experiences
            if _confirmed(e.source)
        ],
        "educations": [
            {
                "ref": f"education:{e.id}",
                "degree": e.degree,
                "institution": e.institution,
                "start_year": e.start_year,
                "end_year": e.end_year,
            }
            for e in profile.educations
            if _confirmed(e.source)
        ],
        "skills": [
            {"ref": f"skill:{s.id}", "label": s.label_raw}
            for s in profile.skills
            if _confirmed(s.source)
        ],
        "languages": [
            {"lang_code": lang.lang_code, "level": lang.level}
            for lang in profile.languages
            if _confirmed(lang.source)
        ],
    }


def build_job_payload(job: JobPosting, *, excerpt_limit: int) -> dict[str, Any]:
    """Payload offre structuré pour le prompt : titre, entreprise, extraits
    tronqués, compétences extraites — jamais de contact recruteur (08 §2.2)."""
    return {
        "title": job.title,
        "company_name": job.company_name,
        "language": job.language,
        "excerpts": job.description_text[:excerpt_limit],
        "skills_required": [s.label_raw for s in job.skills if s.required],
        "skills_nice": [s.label_raw for s in job.skills if not s.required],
    }


# ---------------------------------------------------------------- service


class GenerationService:
    def __init__(
        self,
        repository: GenerationRepository,
        profiles: ProfilesRepository,
        cache: Redis,
        enqueue: Enqueuer,
    ) -> None:
        self._repository = repository
        self._profiles = profiles
        self._cache = cache
        self._enqueue = enqueue

    # ------------------------------------------------------------ création

    async def create(
        self,
        user_id: uuid.UUID,
        payload: GenerationCreate,
        idempotency_key: str | None,
    ) -> tuple[GeneratedDocumentOut, bool]:
        """POST /generations → (réponse, rejouée ?) — 202 dans les deux cas."""
        key = self._require_idempotency_key(idempotency_key)
        redis_key = f"idem:generations:{user_id}:{key}"
        stored = await self._cache.get(redis_key)
        if stored is not None:
            # Rejeu : réponse d'ORIGINE, aucune double génération facturée
            # (F-L scénario 5) — ni précondition ni quota re-consommé.
            return GeneratedDocumentOut.model_validate_json(stored), True

        profile = await self._profiles.get_by_user(user_id)
        if profile is None or profile.status != "validated":
            raise _profile_not_validated()

        job = await self._resolve_job(payload)
        await self._enforce_quotas(user_id)

        options = dict(payload.options.model_dump())
        if options.get("language") is None:
            # RM-L-5 / D15 : langue de l'offre par défaut, sinon fr.
            options["language"] = (
                job.language if job is not None and job.language in ("fr", "en") else "fr"
            )

        now = datetime.now(UTC)
        document = GeneratedDocument(
            id=uuid.uuid4(),
            user_id=user_id,
            application_id=payload.application_id,
            job_posting_id=job.id if job is not None else None,
            doc_type=payload.doc_type,
            status="draft",
            content={},
            based_on_profile_version=profile.version,
            prompt_version=PROMPT_VERSIONS[TASK_BY_DOC_TYPE[payload.doc_type]],
            created_at=now,
            validated_at=None,
            processing_status="pending",
            error_code=None,
            anchoring_check=None,
            manually_edited=False,
            options=options,
        )
        await self._repository.add(document)
        self._enqueue(document.id)

        out = self._to_out(document)
        # SET NX : en cas de course sur la même clé, la première réponse
        # stockée gagne (le doublon marginal est assumé et documenté 🟡).
        await self._cache.set(
            redis_key, out.model_dump_json(), ex=IDEMPOTENCY_TTL_SECONDS, nx=True
        )
        return out, False

    @staticmethod
    def _require_idempotency_key(raw: str | None) -> uuid.UUID:
        """Idempotency-Key UUID obligatoire (RM-L-4) — 422 sinon."""
        if raw is None:
            raise Problem(
                status=422,
                code="validation_error",
                title="Données invalides",
                detail="L'en-tête Idempotency-Key (UUID) est obligatoire.",
                errors=[
                    {
                        "field": "Idempotency-Key",
                        "code": "missing",
                        "message": "En-tête obligatoire pour POST /generations.",
                    }
                ],
            )
        try:
            return uuid.UUID(raw)
        except ValueError as exc:
            raise Problem(
                status=422,
                code="validation_error",
                title="Données invalides",
                detail="L'en-tête Idempotency-Key doit être un UUID.",
                errors=[
                    {
                        "field": "Idempotency-Key",
                        "code": "invalid_uuid",
                        "message": "Format UUID attendu.",
                    }
                ],
            ) from exc

    async def _resolve_job(self, payload: GenerationCreate) -> JobPosting | None:
        """Préconditions offre : requise sauf cv_optimization (F-N est
        indépendante de toute offre — un job_id fourni est ignoré 🟡)."""
        if payload.doc_type == "cv_optimization":
            return None
        if payload.job_id is None:
            raise Problem(
                status=422,
                code="validation_error",
                title="Données invalides",
                detail=f"job_id est requis pour doc_type={payload.doc_type}.",
                errors=[
                    {
                        "field": "job_id",
                        "code": "missing",
                        "message": "Requis sauf pour cv_optimization.",
                    }
                ],
            )
        job = await self._repository.get_job(payload.job_id)
        if job is None or not job_is_readable(job):
            raise _job_not_found()
        if job.status == "expired":
            raise _job_expired()
        return job

    async def _enforce_quotas(self, user_id: uuid.UUID) -> None:
        """Quotas 10/h puis 40/j (RM-L-4) — 429 + Retry-After, aucune tâche
        créée (AC-L-3). Un refus horaire ne consomme pas le compteur jour ;
        l'inverse consomme un jeton horaire (fenêtres fixes, assumé 🟡)."""
        limiter = FixedWindowRateLimiter(self._cache)
        hour = await limiter.hit(
            "generations:hour", str(user_id), limit=QUOTA_PER_HOUR, window_seconds=3600
        )
        if not hour.allowed:
            raise _rate_limited(hour.retry_after, "10 par heure")
        day = await limiter.hit(
            "generations:day", str(user_id), limit=QUOTA_PER_DAY, window_seconds=86400
        )
        if not day.allowed:
            raise _rate_limited(day.retry_after, "40 par jour")

    # ------------------------------------------------------------ lecture

    async def get(self, user_id: uuid.UUID, document_id: uuid.UUID) -> GeneratedDocumentOut:
        """GET /generations/{id} — contenu + anchoring_check ; autrui → 404."""
        document = await self._repository.get_for_user(user_id, document_id)
        if document is None:
            raise _generation_not_found()
        return self._to_out(document)

    async def list(
        self,
        user_id: uuid.UUID,
        *,
        doc_type: str | None,
        status: str | None,
        job_id: uuid.UUID | None,
        limit: int,
        cursor: str | None,
    ) -> GenerationPage:
        """GET /generations — bibliothèque paginée par curseur keyset."""
        before: tuple[datetime, uuid.UUID] | None = None
        if cursor is not None:
            before = _decode_generation_cursor(cursor)

        rows = await self._repository.list_for_user(
            user_id,
            doc_type=doc_type,
            status=status,
            job_id=job_id,
            before=before,
            limit=limit + 1,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = _encode_generation_cursor(last.created_at, last.id)
        return GenerationPage(
            items=[self._to_out(row) for row in page], next_cursor=next_cursor
        )

    # ------------------------------------------------------------ cycle de vie

    async def patch(
        self, user_id: uuid.UUID, document_id: uuid.UUID, payload: GenerationPatch
    ) -> GeneratedDocumentOut:
        """PATCH /generations/{id} — édition manuelle du brouillon (Q6 🟡).

        Brouillon uniquement (409 sinon) ; lève le contrôle d'ancrage :
        ``anchoring_check`` → null, ``manually_edited`` → true, note de
        responsabilité dans la réponse — le document reste en relecture.
        """
        document = await self._require_document(user_id, document_id)
        if api_status(document) != "draft":
            raise Problem(
                status=409,
                code="generation_not_editable",
                title="Document non éditable",
                detail="Seul un brouillon (status=draft) peut être édité manuellement.",
            )
        document.content = payload.content
        document.manually_edited = True
        document.anchoring_check = None
        await self._repository.commit()
        return self._to_out(document)

    async def validate(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocumentOut:
        """POST /generations/{id}/validate — validation humaine (D10)."""
        document = await self._require_document(user_id, document_id)
        if api_status(document) != "draft":
            raise Problem(
                status=409,
                code="generation_invalid_state",
                title="Transition invalide",
                detail="Seul un brouillon (status=draft) peut être validé.",
            )
        check = document.anchoring_check
        if (
            not document.manually_edited
            and isinstance(check, dict)
            and check.get("status") == "failed"
        ):
            # « Jamais présenté comme prêt » tant que l'ancrage échoue
            # (RM-L-2) — sauf reprise manuelle assumée par l'utilisateur.
            raise Problem(
                status=409,
                code="generation_not_anchored",
                title="Contenu non ancré",
                detail=(
                    "Des affirmations ne sont pas ancrées sur votre profil : "
                    "relancez la génération ou éditez le contenu avant validation."
                ),
            )
        document.status = "validated"
        document.validated_at = datetime.now(UTC)
        await self._repository.commit()
        return self._to_out(document)

    async def export(
        self, user_id: uuid.UUID, document_id: uuid.UUID, export_format: str
    ) -> ExportOut:
        """POST /generations/{id}/export — exige ``validated`` (RM-L-3)."""
        document = await self._require_document(user_id, document_id)
        if api_status(document) not in ("validated", "exported"):
            raise _generation_not_validated()
        if document.validated_at is None:
            # Vérification applicative du CHECK SQL « exported ⇒ validated_at »
            # (RM-L-3) : jamais d'export sans horodatage de validation.
            raise _generation_not_validated()
        if export_format in ("pdf", "docx"):
            raise Problem(
                status=501,
                code="not_implemented",
                title="Fonctionnalité non disponible",
                detail=(
                    f"Export {export_format.upper()} : prévu au jalon M5 🟡 — "
                    "utilisez format=text (copie) en attendant."
                ),
            )
        text = _assemble_text(document)
        document.status = "exported"
        await self._repository.commit()
        return ExportOut(format="text", content=text, download_url=None)

    async def _require_document(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocument:
        document = await self._repository.get_for_user(user_id, document_id)
        if document is None:
            raise _generation_not_found()
        return document

    # ------------------------------------------------------------ mapping

    @staticmethod
    def _to_out(document: GeneratedDocument) -> GeneratedDocumentOut:
        status = api_status(document)
        content = document.content or None
        if status in ("pending", "failed"):
            content = None  # le contrat sert null tant que rien n'est prêt
        check = document.anchoring_check
        anchoring = (
            AnchoringCheckOut(
                status=check.get("status", "failed"),
                unanchored_claims=list(check.get("unanchored_claims", [])),
            )
            if isinstance(check, dict)
            else None
        )
        return GeneratedDocumentOut(
            id=document.id,
            doc_type=document.doc_type,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            job_id=document.job_posting_id,
            application_id=document.application_id,
            based_on_profile_version=document.based_on_profile_version,
            prompt_version=document.prompt_version,
            content=content,
            anchoring_check=anchoring,
            anchoring_note=MANUAL_EDIT_NOTE if document.manually_edited else None,
            manually_edited=document.manually_edited,
            error_code=document.error_code if status == "failed" else None,
            created_at=document.created_at,
            validated_at=document.validated_at,
        )


# ---------------------------------------------------------------- export texte


def _assemble_text(document: GeneratedDocument) -> str:
    """Contenu texte assemblé pour l'export ``format=text`` (copie, D10).

    Tolérant aux contenus édités manuellement (clés absentes → repli JSON
    lisible plutôt qu'une 500).
    """
    content: dict[str, Any] = document.content or {}
    if document.doc_type == "email" and "body" in content:
        subject = content.get("subject")
        body = str(content.get("body", ""))
        return f"Objet : {subject}\n\n{body}" if subject else body
    if document.doc_type == "cover_letter" and "body" in content:
        return str(content.get("body", ""))
    if document.doc_type == "cv_variant" and isinstance(content.get("changes"), list):
        lines = ["Variante de CV — changements proposés :"]
        for change in content["changes"]:
            if not isinstance(change, dict):
                continue
            line = (
                f"- [{change.get('kind', '?')}] {change.get('target_ref', '?')} — "
                f"{change.get('rationale', '')}"
            )
            if change.get("new_text"):
                line += f"\n  Nouveau texte : {change['new_text']}"
            lines.append(line)
        return "\n".join(lines)
    if document.doc_type == "cv_optimization" and isinstance(
        content.get("suggestions"), list
    ):
        lines = ["Optimisation du CV — suggestions :"]
        for item in content["suggestions"]:
            if not isinstance(item, dict):
                continue
            line = (
                f"- [{item.get('category', '?')}] {item.get('target_ref', '?')} — "
                f"{item.get('issue', '')}"
            )
            proposal = item.get("proposal")
            line += (
                f"\n  Proposition : {proposal}"
                if proposal
                else "\n  (question — réponse à saisir par vos soins)"
            )
            lines.append(line)
        return "\n".join(lines)
    return json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True)


# ---------------------------------------------------------------- worker


async def execute_generation(
    document_id: uuid.UUID,
    repository: GenerationRepository,
    profiles: ProfilesRepository,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Orchestration d'une génération (tâche ``ai.generate``).

    Statuts : ``pending`` → ``processing`` → ``ready`` (draft) ou ``failed``
    (+ ``error_code``). Idempotente sur re-livraison (acks_late D16) : un
    document déjà traité est ignoré. Exécutée par la tâche Celery (repos SQL)
    et par les tests (fakes en mémoire) avec la même sémantique.
    """
    document = await repository.get_by_id(document_id)
    if document is None:
        logger.warning("generation_document_missing id=%s", document_id)
        return {"status": "missing"}
    if document.processing_status not in ("pending", "processing"):
        logger.info("generation_already_processed id=%s", document_id)
        return {"status": "skipped"}

    document.processing_status = "processing"
    await repository.commit()

    try:
        outcome = await _run_document_generation(document, repository, profiles, provider)
    except GenerationTaskError as exc:
        document.processing_status = "failed"
        document.error_code = exc.error_code
        await repository.commit()
        logger.warning(
            "generation_failed id=%s error_code=%s detail=%s",
            document_id, exc.error_code, exc.detail,
        )
        return {"status": "failed", "error_code": exc.error_code}
    except Exception:
        # Échec inattendu → échec propre persisté (jamais de document bloqué
        # en processing), l'exception est journalisée pour Sentry (D20).
        document.processing_status = "failed"
        document.error_code = "provider_error"
        await repository.commit()
        logger.exception("generation_unexpected_error id=%s", document_id)
        return {"status": "failed", "error_code": "provider_error"}

    document.content = outcome.content
    document.anchoring_check = {
        "status": outcome.anchoring_status,
        "unanchored_claims": list(outcome.unanchored_claims),
    }
    document.processing_status = "ready"
    document.status = "draft"
    document.error_code = None
    await repository.commit()
    if outcome.anchoring_status == "failed":
        # Avertissement journalisé (AC-L-2) : jamais présenté comme prêt.
        logger.warning(
            "generation_anchoring_failed id=%s unanchored=%d",
            document_id, len(outcome.unanchored_claims),
        )
    return {"status": "draft", "anchoring": outcome.anchoring_status}


async def _run_document_generation(
    document: GeneratedDocument,
    repository: GenerationRepository,
    profiles: ProfilesRepository,
    provider: LLMProvider,
) -> Any:
    """Charge profil/offre, construit le prompt ancré et exécute la tâche IA."""
    profile = await profiles.get_by_user(document.user_id)
    if profile is None or profile.status != "validated":
        # Le profil a pu être supprimé entre le POST et l'exécution.
        raise GenerationTaskError(
            "profile_not_validated", "profil absent ou non validé à l'exécution"
        )

    task = TASK_BY_DOC_TYPE[document.doc_type]
    job_payload = None
    if document.doc_type != "cv_optimization":
        job = (
            await repository.get_job(document.job_posting_id)
            if document.job_posting_id is not None
            else None
        )
        if job is None:
            raise GenerationTaskError("job_not_found", "offre absente à l'exécution")
        job_payload = build_job_payload(
            job, excerpt_limit=JOB_EXCERPT_LIMITS.get(task, 1500)
        )

    return run_generation_task(
        task,
        profile=build_profile_payload(profile),
        job=job_payload,
        options=document.options,
        valid_refs=collect_profile_refs(profile),
        provider=provider,
    )

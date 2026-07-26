"""Logique métier du module applications (F-P, jalon M4).

Règles portées ici (le repository ne fait que persister) :
- CHECK applicatif RM-P-2 : ``job_posting_id`` OU (``external_title`` ET
  ``external_company``) — sinon 422 listant les champs requis (AC-P-2).
  Le miroir SQL (CHECK de ``applications``) reste la ceinture de sécurité ;
  fournir les deux formes n'est pas rejeté 🟡 (aligné sur le CHECK SQL) ;
- ``job_posting_id`` fourni → l'offre doit exister, sinon 404 (Q26 : le suivi
  reste autorisé sur une offre expirée — seule l'existence compte) ;
- transitions LIBRES (Q29) mais toutes historisées dans
  ``application_events`` (from_status → to_status, note, horodatage) —
  y compris ``to_status`` égal au statut courant (« note seule », F-P) ;
- ``applied_at`` posé à la PREMIÈRE transition vers ``applied`` uniquement
  (D10 : déclaratif) — jamais modifié ensuite ;
- ``updated_at`` maintenu à chaque mutation (PATCH, transition) ;
- scoping utilisateur : la candidature d'autrui est introuvable → 404 ;
- curseur corrompu → 422 problem+json ``invalid_cursor`` ;
- Idempotency-Key 🟡 simple : cache en mémoire de processus (clé → id de
  candidature) ; ignorée si non fournie, best-effort mono-processus — une
  table dédiée arrive avec le module privacy/infra si besoin.
"""

import uuid
from datetime import UTC, datetime
from typing import cast

from app.core.problems import Problem
from app.modules.applications.models import Application, ApplicationEvent
from app.modules.applications.repository import (
    ApplicationsRepository,
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from app.modules.applications.schemas import (
    ApplicationEventOut,
    ApplicationInput,
    ApplicationOut,
    ApplicationPage,
    ApplicationPatch,
    ApplicationStatus,
    StatusChangeInput,
)

#: Cache d'idempotence 🟡 (user_id, clé) → id de candidature — mémoire de
#: processus, best-effort (perdu au redémarrage, non partagé entre workers).
_IDEMPOTENCY_CACHE: dict[tuple[uuid.UUID, str], uuid.UUID] = {}


def _not_found() -> Problem:
    return Problem(
        status=404,
        code="not_found",
        title="Ressource introuvable",
        detail="Candidature introuvable.",
    )


def _missing_reference_problem(payload: ApplicationInput) -> Problem:
    """422 AC-P-2 : ni offre interne ni couple externe complet."""
    errors = [
        {
            "field": field,
            "code": "missing_reference",
            "message": "Renseignez job_posting_id ou le couple "
            "(external_title, external_company).",
        }
        for field, value in (
            ("job_posting_id", payload.job_posting_id),
            ("external_title", payload.external_title),
            ("external_company", payload.external_company),
        )
        if value is None
    ]
    return Problem(
        status=422,
        code="validation_error",
        title="Données invalides",
        detail="Une candidature référence une offre interne (job_posting_id) "
        "ou une offre externe (external_title et external_company).",
        errors=errors,
    )


class ApplicationsService:
    def __init__(self, repository: ApplicationsRepository) -> None:
        self._repository = repository

    # ------------------------------------------------------------ liste

    async def list(
        self,
        user_id: uuid.UUID,
        *,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> ApplicationPage:
        """Tableau de bord paginé par curseur keyset (created_at, id) DESC."""
        decoded = None
        if cursor is not None:
            try:
                decoded = decode_cursor(cursor)
            except InvalidCursorError as exc:
                raise Problem(
                    status=422,
                    code="invalid_cursor",
                    title="Curseur invalide",
                    detail="Le curseur de pagination est illisible ou périmé. "
                    "Relancez la requête sans curseur.",
                ) from exc
        rows = await self._repository.list_for_user(
            user_id=user_id, status=status, limit=limit, cursor=decoded
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = encode_cursor(last.created_at, last.id)
        return ApplicationPage(
            items=[self._to_out(row) for row in page_rows], next_cursor=next_cursor
        )

    # ------------------------------------------------------------ création

    async def create(
        self,
        user_id: uuid.UUID,
        payload: ApplicationInput,
        *,
        idempotency_key: str | None = None,
    ) -> ApplicationOut:
        """Crée une candidature (offre interne ou externe) — statut ``draft``.

        Aucun événement n'est historisé à la création : l'historique ne trace
        que les transitions de statut (RM-P-3) ; le statut initial est porté
        par la candidature elle-même.
        """
        if idempotency_key is not None:
            cached_id = _IDEMPOTENCY_CACHE.get((user_id, idempotency_key))
            if cached_id is not None:
                existing = await self._repository.get_for_user(cached_id, user_id)
                if existing is not None:
                    return self._to_out(existing)

        if payload.job_posting_id is None and (
            payload.external_title is None or payload.external_company is None
        ):
            raise _missing_reference_problem(payload)
        if payload.job_posting_id is not None and not await self._repository.job_exists(
            payload.job_posting_id
        ):
            raise Problem(
                status=404,
                code="not_found",
                title="Ressource introuvable",
                detail="Offre introuvable.",
            )

        now = datetime.now(UTC)
        application = Application(
            id=uuid.uuid4(),
            user_id=user_id,
            job_posting_id=payload.job_posting_id,
            external_title=payload.external_title,
            external_company=payload.external_company,
            external_url=payload.external_url,
            status="draft",
            applied_at=None,
            notes=payload.notes,
            created_at=now,
            updated_at=now,
        )
        application.events = []
        created = await self._repository.create(application)
        if idempotency_key is not None:
            _IDEMPOTENCY_CACHE[(user_id, idempotency_key)] = created.id
        return self._to_out(created)

    # ------------------------------------------------------------ détail

    async def get(self, application_id: uuid.UUID, user_id: uuid.UUID) -> ApplicationOut:
        application = await self._repository.get_for_user(application_id, user_id)
        if application is None:
            raise _not_found()
        return self._to_out(application)

    # ------------------------------------------------------------ édition

    async def patch(
        self, application_id: uuid.UUID, user_id: uuid.UUID, payload: ApplicationPatch
    ) -> ApplicationOut:
        """Édite notes / champs externes — seuls les champs fournis changent.

        Effacer ``external_title`` ou ``external_company`` d'une candidature
        externe (sans offre interne) violerait RM-P-2 → 422 avant persistance.
        """
        application = await self._repository.get_for_user(application_id, user_id)
        if application is None:
            raise _not_found()
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._to_out(application)

        new_title = updates.get("external_title", application.external_title)
        new_company = updates.get("external_company", application.external_company)
        if application.job_posting_id is None and (new_title is None or new_company is None):
            raise Problem(
                status=422,
                code="validation_error",
                title="Données invalides",
                detail="Une candidature externe doit conserver external_title "
                "et external_company (RM-P-2).",
                errors=[
                    {
                        "field": field,
                        "code": "missing_reference",
                        "message": "Champ requis pour une candidature externe.",
                    }
                    for field, value in (
                        ("external_title", new_title),
                        ("external_company", new_company),
                    )
                    if value is None
                ],
            )
        for field, value in updates.items():
            setattr(application, field, value)
        application.updated_at = datetime.now(UTC)
        await self._repository.save(application)
        return self._to_out(application)

    # ------------------------------------------------------------ suppression

    async def delete(self, application_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Supprime candidature + événements (F-P alt. 3) — autrui → 404."""
        application = await self._repository.get_for_user(application_id, user_id)
        if application is None:
            raise _not_found()
        await self._repository.delete(application)

    # ------------------------------------------------------------ statut

    async def change_status(
        self, application_id: uuid.UUID, user_id: uuid.UUID, payload: StatusChangeInput
    ) -> ApplicationOut:
        """Transition LIBRE (Q29) historisée dans ``application_events``.

        ``to_status`` égal au statut courant est permis (« note seule ») et
        historisé comme les autres. ``applied_at`` n'est posé qu'à la première
        transition vers ``applied``.
        """
        application = await self._repository.get_for_user(application_id, user_id)
        if application is None:
            raise _not_found()
        now = datetime.now(UTC)
        event = ApplicationEvent(
            application_id=application.id,
            from_status=application.status,
            to_status=payload.to_status,
            note=payload.note,
            at=now,
        )
        application.status = payload.to_status
        if payload.to_status == "applied" and application.applied_at is None:
            application.applied_at = now
        application.updated_at = now
        await self._repository.add_event(application, event)
        return self._to_out(application)

    # ------------------------------------------------------------ mapping

    @staticmethod
    def _to_out(application: Application) -> ApplicationOut:
        # Les casts vers les Literal sont sûrs : colonnes ENUM PostgreSQL.
        return ApplicationOut(
            id=application.id,
            job_posting_id=application.job_posting_id,
            external_title=application.external_title,
            external_company=application.external_company,
            external_url=application.external_url,
            notes=application.notes,
            status=cast(ApplicationStatus, application.status),
            applied_at=application.applied_at,
            events=[
                ApplicationEventOut(
                    from_status=cast(ApplicationStatus | None, event.from_status),
                    to_status=cast(ApplicationStatus, event.to_status),
                    at=event.at,
                    note=event.note,
                )
                for event in application.events
            ],
            created_at=application.created_at,
            updated_at=application.updated_at,
        )

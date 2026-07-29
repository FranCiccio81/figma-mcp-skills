"""Logique métier du module jobs : recherche, détail, saved-state, sources.

Règles portées ici (le repository ne fait que des requêtes) :
- ``sort=match`` retombe sur ``relevance`` au M2 (le scoring arrive au M3 —
  documenté, le paramètre est accepté sans erreur pour ne pas casser le front) ;
- ``relevance`` sans ``q`` retombe sur ``date`` (aucun rang full-text) ;
- curseur corrompu ou incohérent → 422 problem+json ``invalid_cursor`` ;
- offre inexistante, retirée (withdrawn 🟡) ou expirée depuis plus de 12 mois
  (rétention RM-E-4) → 404 ; une offre expirée récente reste lisible, son
  ``status`` permet le bandeau « offre expirée » côté front ;
- ``PUT/DELETE saved-state`` sur une offre inconnue → 404 (les états d'autres
  utilisateurs ne sont jamais adressables : clé (user_id, job_id) implicite).
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from app.core.problems import Problem
from app.matching import get_config
from app.modules.jobs.models import JobPosting
from app.modules.jobs.repository import (
    InvalidCursorError,
    JobDetailRow,
    JobSearchRow,
    JobsRepository,
    SearchFilters,
    decode_cursor,
    encode_cursor,
)
from app.modules.jobs.schemas import (
    ContractType,
    JobCard,
    JobDetail,
    JobSourceOut,
    JobStatus,
    MatchSummary,
    RemotePolicy,
    SavedState,
    SearchPage,
    SeniorityLevel,
    SourceKind,
    SourceOut,
)

logger = logging.getLogger(__name__)

#: Rétention des offres expirées (RM-E-4) : lisibles 12 mois puis 404.
EXPIRED_RETENTION = timedelta(days=365)

_PERIOD_SUFFIX_FR = {"month": "/mois", "day": "/jour", "hour": "/h"}


def format_salary_label(
    salary_min: int | None,
    salary_max: int | None,
    currency: str | None,
    period: str | None,
) -> str | None:
    """Libellé de salaire pour affichage — ``'45–55 k€'`` ou None (Q32).

    None signifie « non communiqué » : le front affiche un badge, l'offre
    n'est jamais exclue pour autant (Q32).
    """
    if salary_min is None and salary_max is None:
        return None
    symbol = "€" if currency in (None, "EUR") else str(currency)
    if period in (None, "year"):  # annuel : en milliers, « 45–55 k€ »
        low = None if salary_min is None else round(salary_min / 1000)
        high = None if salary_max is None else round(salary_max / 1000)
        suffix = f" k{symbol}"
    else:
        low, high = salary_min, salary_max
        suffix = f" {symbol}{_PERIOD_SUFFIX_FR.get(period, '')}"
    if low is not None and high is not None and low != high:
        return f"{low}–{high}{suffix}"
    return f"{low if low is not None else high}{suffix}"


def _not_found() -> Problem:
    return Problem(
        status=404,
        code="not_found",
        title="Ressource introuvable",
        detail="Offre introuvable.",
    )


class JobsService:
    def __init__(self, repository: JobsRepository) -> None:
        self._repository = repository

    # ------------------------------------------------------------ recherche

    async def search(
        self,
        user_id: uuid.UUID,
        *,
        q: str | None,
        remote: tuple[str, ...],
        contract: tuple[str, ...],
        salary_min: int | None,
        posted_since: int | None,
        language: str | None,
        country: str | None,
        lat: float | None,
        lon: float | None,
        radius_km: int,
        include_hidden: bool,
        saved_only: bool,
        sort: str,
        limit: int,
        cursor: str | None,
    ) -> SearchPage:
        """Recherche paginée par curseur opaque (pipeline D07)."""
        # Le profil validé conditionne tout : sans lui, aucun score n'existe.
        # Sa VERSION aussi : une ligne de cache calculée sur une version
        # antérieure est périmée, et doit rendre `null` plutôt qu'un chiffre.
        profil = await self._repository.validated_profile(user_id)
        profile_id = profil[0] if profil else None
        effective_sort = self._effective_sort(sort, q, scored=profil is not None)
        decoded = None
        if cursor is not None:
            try:
                decoded = decode_cursor(cursor, expected_sort=effective_sort)
            except InvalidCursorError as exc:
                raise Problem(
                    status=422,
                    code="invalid_cursor",
                    title="Curseur invalide",
                    detail="Le curseur de pagination est illisible ou périmé. "
                    "Relancez la recherche sans curseur.",
                ) from exc

        filters = SearchFilters(
            q=q,
            remote=remote,
            contract=contract,
            salary_min=salary_min,
            posted_since_days=posted_since,
            language=language,
            country=country,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            include_hidden=include_hidden,
            saved_only=saved_only,
            sort=effective_sort,
        )
        rows = await self._repository.search(
            user_id=user_id,
            filters=filters,
            limit=limit,
            cursor=decoded,
            profile_id=profile_id,
            scoring_version=get_config().scoring_version if profil else None,
            profile_version=profil[1] if profil else None,
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = encode_cursor(effective_sort, last.sort_value, last.posting.id)
        return SearchPage(items=[self._to_card(row) for row in page_rows],
                          next_cursor=next_cursor)

    @staticmethod
    def _effective_sort(sort: str, q: str | None, *, scored: bool) -> str:
        """Tri effectif.

        ``sort=match`` retombait TOUJOURS sur la pertinence full-text, avec
        pour commentaire « tant que le scoring n'est pas livré (M3) ». Il
        l'était : ``/matches`` rendait des scores, le front affichait un
        sélecteur « Compatibilité », et cette page-ci ne triait rien et
        n'affichait aucun score. Le tableau de bord y renvoyait pourtant
        explicitement pour ça.

        Le repli demeure quand l'utilisateur n'a **pas** de profil validé :
        il n'a alors aucun score, et trier par compatibilité n'aurait aucun
        sens. La pertinence est le meilleur substitut disponible.
        """
        if sort == "match":
            if scored:
                return "match"
            return "relevance" if q else "date"
        if sort == "relevance":
            return "relevance" if q else "date"
        return "date"

    # ------------------------------------------------------------ détail

    async def get_detail(self, job_id: uuid.UUID, user_id: uuid.UUID) -> JobDetail:
        row = await self._repository.get_detail(job_id, user_id)
        if row is None or not self._is_readable(row):
            raise _not_found()
        return self._to_detail(row)

    @staticmethod
    def _is_readable(row: JobDetailRow) -> bool:
        """Lisibilité d'une offre non active.

        - ``withdrawn`` : 404 🟡 (offre retirée à la demande de la source) ;
        - ``expired`` : lisible pendant 12 mois (bandeau côté front via
          ``status``), 404 au-delà (rétention RM-E-4). Référence temporelle :
          ``expires_at`` si présent, sinon ``last_seen_at``.
        """
        posting = row.posting
        if posting.status == "withdrawn":
            return False
        if posting.status == "expired":
            reference = posting.expires_at or posting.last_seen_at
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=UTC)
            return datetime.now(UTC) - reference <= EXPIRED_RETENTION
        return True

    # ------------------------------------------------------------ saved-state

    async def set_saved_state(
        self, user_id: uuid.UUID, job_id: uuid.UUID, state: str
    ) -> None:
        """Upsert saved/hidden — 404 selon la même règle de lisibilité que le
        détail (anti-énumération : une ressource illisible en GET ne doit pas
        être mutable, sinon le 204 révèle son existence)."""
        await self._readable_or_404(user_id, job_id)
        await self._repository.set_saved_state(user_id, job_id, state)

    async def clear_saved_state(self, user_id: uuid.UUID, job_id: uuid.UUID) -> None:
        """Retire saved/hidden — idempotent si aucun état n'existait (204)."""
        await self._readable_or_404(user_id, job_id)
        await self._repository.clear_saved_state(user_id, job_id)

    async def _readable_or_404(self, user_id: uuid.UUID, job_id: uuid.UUID) -> None:
        row = await self._repository.get_detail(job_id, user_id)
        if row is None or not self._is_readable(row):
            raise _not_found()

    # ------------------------------------------------------------ sources

    async def list_sources(self) -> list[SourceOut]:
        rows = await self._repository.list_sources()
        # sources.kind est du texte libre en base (pas de CHECK) : une valeur
        # hors vocabulaire est ignorée plutôt que de casser tout GET /sources
        # par une ResponseValidationError.
        #
        # ⚠️ Mais JAMAIS en silence. Une source active a disparu de la page de
        # transparence sans un mot pendant tout un démarrage à froid, parce
        # que sa nature ne figurait pas dans cette liste — le symptôme était
        # « la page des sources est vide », très loin de la cause.
        valid_kinds: tuple[SourceKind, ...] = ("public_api", "ats_feed", "partner", "demo")
        for row in rows:
            if row.kind not in valid_kinds:
                logger.warning(
                    "source_masquee_nature_inconnue slug=%s kind=%r attendues=%s",
                    row.slug, row.kind, valid_kinds,
                )
        return [
            SourceOut(
                slug=r.slug,
                name=r.name,
                kind=r.kind,
                last_sync_at=r.last_sync_at,
            )
            for r in rows
            if r.kind in valid_kinds
        ]

    # ------------------------------------------------------------ mapping

    @staticmethod
    def _earliest_posted_at(posting: JobPosting) -> datetime | None:
        dates = [js.posted_at for js in posting.job_sources if js.posted_at is not None]
        return min(dates) if dates else None

    def _to_card(self, row: JobSearchRow) -> JobCard:
        # Les casts vers les Literal sont sûrs : colonnes ENUM PostgreSQL.
        posting = row.posting
        return JobCard(
            id=posting.id,
            title=posting.title,
            company_name=posting.company_name,
            locations=[loc.raw_label for loc in posting.locations],
            remote=cast(RemotePolicy | None, posting.remote),
            contract=cast(ContractType | None, posting.contract),
            salary_label=format_salary_label(
                posting.salary_min,
                posting.salary_max,
                posting.salary_currency,
                posting.salary_period,
            ),
            posted_at=self._earliest_posted_at(posting),
            match=(
                MatchSummary(
                    score=row.match.score,
                    confidence=row.match.confidence,
                    low_data=row.match.low_data,
                    has_blocking=row.match.has_blocking,
                )
                if row.match is not None
                else None
            ),
            saved_state=cast(SavedState | None, row.saved_state),
        )

    def _to_detail(self, row: JobDetailRow) -> JobDetail:
        # Les casts vers les Literal sont sûrs : colonnes ENUM PostgreSQL.
        posting = row.posting
        return JobDetail(
            id=posting.id,
            title=posting.title,
            company_name=posting.company_name,
            locations=[loc.raw_label for loc in posting.locations],
            remote=cast(RemotePolicy | None, posting.remote),
            contract=cast(ContractType | None, posting.contract),
            salary_label=format_salary_label(
                posting.salary_min,
                posting.salary_max,
                posting.salary_currency,
                posting.salary_period,
            ),
            posted_at=self._earliest_posted_at(posting),
            # Le détail a sa propre route de matching (GET /jobs/{id}/match),
            # qui rend le score ET le détail par dimension. Le dupliquer ici
            # ferait deux chemins de calcul pour le même chiffre.
            match=None,
            saved_state=cast(SavedState | None, row.saved_state),
            description_text=posting.description_text,
            language=posting.language,
            seniority=cast(SeniorityLevel | None, posting.seniority),
            skills_required=[s.label_raw for s in posting.skills if s.required],
            skills_nice=[s.label_raw for s in posting.skills if not s.required],
            status=cast(JobStatus, posting.status),
            expires_at=posting.expires_at,
            # Garantie produit (07-job-ingestion) : au moins une source avec
            # lien d'origine — minItems 1 vérifié par le schéma de réponse.
            sources=[
                JobSourceOut(
                    name=js.source.name,
                    original_url=js.original_url,
                    posted_at=js.posted_at,
                )
                for js in posting.job_sources
            ],
        )

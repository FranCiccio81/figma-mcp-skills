"""Journal des appels LLM — table ``ai_calls`` (11 §1, 08 §7.3).

Ce que le journal contient : **des métadonnées, rien d'autre** — tâche,
version de prompt, modèle, utilisateur (nullable), tokens entrée/sortie,
latence, statut, code d'erreur. Il permet le monitoring de 08 §7.3
(``ai_calls_total{status}``, latence, coût/jour) et l'audit d'un artefact
généré (attribution à une version exacte de prompt, 08 §7.1).

Ce que le journal NE CONTIENT JAMAIS (11 §3, D09) : le prompt, la réponse
du modèle, un extrait de CV ou d'offre, un message d'erreur recopiant l'une
de ces choses. ``error_code`` est un identifiant fermé (voir
:data:`ERROR_CODES`), pas un message. Cette contrainte est vérifiée par
test (``tests/unit/ai/test_calls_journal.py``) : la revue a déjà trouvé une
fuite de sortie LLM dans les journaux applicatifs — elle ne doit pas être
reproduite ici.

**Rétention : 13 mois** (11 §3, aligné sur ``audit_log``). La purge par
âge n'est pas encore planifiée (TODO M6 : tâche beat de suppression des
lignes ``created_at < now() - interval '13 months'``) ; la purge RGPD par
utilisateur, elle, est implémentée : anonymisation ``user_id → NULL``
(:mod:`app.modules.ai_calls.purge`, RM-Q-2), jamais suppression — les
métadonnées agrégées (coût, latence, taux d'échec) restent exploitables.

Écriture depuis un appelant SYNCHRONE : l'interface ``LLMProvider`` est
synchrone (``complete_json``) alors que la base est async. La journalisation
(:class:`DatabaseJournal`) est donc exécutée jusqu'à son terme par
:func:`_schedule` — sur une boucle éphémère, dans un thread dédié si une
boucle tourne déjà dans le thread appelant — et **ne peut jamais faire
échouer l'appel IA** : toute exception d'écriture est journalisée et avalée.
"""

import asyncio
import contextlib
import importlib
import logging
import uuid
from collections.abc import Callable, Coroutine, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import BigInteger, Identity, Integer, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, get_session_factory

logger = logging.getLogger(__name__)

#: Tâches de l'enum SQL ``ai_task`` (migration 0001, 08 §2.2).
AI_TASKS: tuple[str, ...] = (
    "extract_cv",
    "extract_job",
    "explain_match",
    "generate_email",
    "generate_letter",
    "tailor_cv",
    "optimize_cv",
)

#: Statuts journalisés (initial-schema.sql, contrainte ajoutée par 0006).
#:
#: - ``success``      : sortie exploitable au premier essai ;
#: - ``schema_retry`` : sortie obtenue au prix d'une réparation déterministe
#:   (repair-parse) ou d'un retry — signal de dérive de prompt/modèle
#:   (alerte 08 §7.3 : > 5 % sur 1 h) ;
#: - ``failed``       : échec propre, rien n'est persisté côté métier.
CALL_STATUSES: tuple[str, ...] = ("success", "schema_retry", "failed")

#: Codes d'erreur fermés (08 §5.1) — jamais de message libre.
ERROR_CODES: tuple[str, ...] = (
    "schema_error",
    "parse_error",
    "grounding_error",
    "provider_error",
    "provider_unavailable",
    "rate_limited",
    "timeout",
)

#: Enum PostgreSQL créé par la migration 0001 (create_type=False).
ai_task_enum = ENUM(*AI_TASKS, name="ai_task", create_type=False)


class AiCall(Base):
    """Une ligne du journal ``ai_calls`` — métadonnées uniquement (11 §3)."""

    __tablename__ = "ai_calls"

    id: Mapped[int] = mapped_column(BigInteger(), Identity(always=True), primary_key=True)
    task: Mapped[str] = mapped_column(ai_task_enum, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text(), nullable=False)
    model: Mapped[str] = mapped_column(Text(), nullable=False)
    #: Nullable **par conception** : anonymisation à la purge du compte
    #: (``ON DELETE SET NULL`` + purge applicative), et appels sans
    #: utilisateur rattaché (``extract_job`` est indépendante de tout
    #: candidat, 08 §2.2).
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    input_tokens: Mapped[int | None] = mapped_column(Integer())
    output_tokens: Mapped[int | None] = mapped_column(Integer())
    latency_ms: Mapped[int | None] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(Text(), nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


@dataclass(frozen=True, slots=True)
class AiCallRecord:
    """Métadonnées d'un appel — structure fermée : aucun champ de contenu.

    Aucun ``prompt``, ``response`` ou ``detail`` n'existe ici : il est
    STRUCTURELLEMENT impossible de journaliser du contenu (11 §3).
    """

    task: str
    prompt_version: str
    model: str
    status: str
    user_id: uuid.UUID | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.task not in AI_TASKS:
            # La colonne ``task`` est l'enum SQL ``ai_task`` : une valeur hors
            # vocabulaire ne peut PAS être insérée. Sans ce contrôle, l'erreur
            # ne se manifestait qu'au COMMIT — dans ``persist_ai_call``, qui
            # avale tout — et la ligne disparaissait en silence. C'est ainsi
            # que ``match_explanation`` (au lieu de ``explain_match``) a fait
            # perdre 100 % du journal des explications, sans compter le
            # mauvais modèle et le mauvais timeout côté provider (M6).
            raise ValueError(
                f"tâche IA hors vocabulaire fermé : {self.task!r} (connues : {list(AI_TASKS)})"
            )
        if self.status not in CALL_STATUSES:
            raise ValueError(f"statut d'appel inconnu : {self.status!r}")
        if self.error_code is not None and self.error_code not in ERROR_CODES:
            raise ValueError(f"code d'erreur hors vocabulaire fermé : {self.error_code!r}")


class CallJournal(Protocol):
    """Destination d'une ligne de journal — synchrone (appelée par le provider)."""

    def record(self, record: AiCallRecord) -> None:
        """Enregistre ``record``. Ne doit JAMAIS lever : un journal en panne
        ne fait pas échouer l'appel IA (D18)."""
        ...


class NullJournal:
    """Journal inerte — provider factice, tests, et environnements sans base."""

    def record(self, record: AiCallRecord) -> None:
        return None


class DatabaseJournal:
    """Journal SQL : planifie l'écriture de la ligne ``ai_calls``.

    ``session_factory`` est injectable (tests) ; par défaut la fabrique
    globale est résolue AU MOMENT de l'écriture (jamais à l'import), pour
    respecter ``override_engine`` côté workers Celery.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        scheduler: Callable[[Coroutine[Any, Any, None]], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._scheduler = scheduler or _schedule

    def record(self, record: AiCallRecord) -> None:
        try:
            self._scheduler(persist_ai_call(record, self._session_factory))
        except Exception:  # pragma: no cover - garde-fou : jamais bloquant
            logger.exception("ai_call_journal_schedule_failed task=%s", record.task)


async def persist_ai_call(
    record: AiCallRecord,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Écrit une ligne ``ai_calls``. Avale toute erreur (jamais bloquante)."""
    try:
        factory = session_factory or get_session_factory()
        async with factory() as session:
            session.add(
                AiCall(
                    task=record.task,
                    prompt_version=record.prompt_version,
                    model=record.model,
                    user_id=record.user_id,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    latency_ms=record.latency_ms,
                    status=record.status,
                    error_code=record.error_code,
                )
            )
            await session.commit()
    except Exception:
        # Le journal est une dette d'observabilité, pas une dépendance dure :
        # son échec ne doit ni casser l'appel IA ni remonter à l'utilisateur.
        logger.warning(
            "ai_call_journal_write_failed task=%s status=%s", record.task, record.status
        )


#: Références fortes aux tâches de journalisation en vol. :func:`_schedule`
#: n'en crée plus (voir sa docstring) ; le jeu reste le point de rendez-vous
#: des ordonnanceurs INJECTÉS (tests, intégrations qui préfèrent une écriture
#: réellement différée) et alimente :func:`drain_pending_writes`.
_PENDING: set[asyncio.Task[None]] = set()


def _schedule(coro: Coroutine[Any, Any, None]) -> None:
    """Exécute ``coro`` — TOUJOURS jusqu'à son terme, sans réentrer la boucle.

    Le provider est synchrone ; l'écriture est async. Trois contextes
    d'appel, un seul comportement attendu : la ligne est écrite.

    ⚠️ Ne PAS revenir à ``loop.create_task(...)`` (M7). Les tâches Celery
    exécutent tout leur cycle dans un ``asyncio.run`` et appellent le
    provider SYNCHRONEMENT depuis cette coroutine : une tâche planifiée y
    est annulée par ``asyncio.run`` à la fermeture de la boucle, avant
    d'avoir pu écrire — et l'annulation est avalée par
    :func:`persist_ai_call`. Vérifié sur PostgreSQL réel : ``ai_calls``
    restait VIDE pour ``extract_cv``, ``extract_job`` et toutes les
    ``generate_*``, c'est-à-dire l'intégralité du volume des workers.

    Quand une boucle tourne déjà DANS ce thread, on ne peut ni ``await``
    (l'appelant est synchrone) ni réentrer la boucle : la coroutine est
    exécutée dans un thread dédié, avec sa propre boucle, et l'appelant
    l'attend. Le coût (une écriture bornée, après un appel LLM de plusieurs
    secondes) est négligeable devant la perte totale du journal.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Hors boucle (script, thread de threadpool côté API) : exécution
        # immédiate sur une boucle éphémère.
        asyncio.run(coro)
        return
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-journal") as pool:
        pool.submit(asyncio.run, coro).result()


async def drain_pending_writes() -> None:
    """Attend les écritures planifiées (tests, arrêt propre d'un worker)."""
    while _PENDING:
        await asyncio.gather(*tuple(_PENDING), return_exceptions=True)


# ------------------------------------------------------- contexte utilisateur

#: Utilisateur courant, propagé au journal SANS élargir l'interface
#: ``LLMProvider`` (dont la signature reste inchangée, D08). Non renseigné =
#: ``user_id NULL``, ce qui est un état valide (``extract_job`` n'a pas
#: d'utilisateur). TODO(M6) : poser ce contexte dans les tâches Celery et
#: les routes qui déclenchent une génération, pour que le coût par
#: utilisateur soit attribuable.
_current_user: ContextVar[uuid.UUID | None] = ContextVar("boussole_ai_user", default=None)


@contextlib.contextmanager
def ai_user_context(user_id: uuid.UUID | None) -> Iterator[None]:
    """Attache ``user_id`` aux appels IA effectués dans le bloc."""
    token = _current_user.set(user_id)
    try:
        yield
    finally:
        _current_user.reset(token)


def current_ai_user() -> uuid.UUID | None:
    """Utilisateur attaché au contexte courant (``None`` si aucun)."""
    return _current_user.get()


# ------------------------------------------------------- versions de prompt

#: Où lire la version de prompt de chaque tâche. Import PARESSEUX : la
#: couche provider ne dépend pas des tâches à l'import (pas de cycle), et
#: les constantes ne sont pas dupliquées (source unique : la tâche).
_PROMPT_VERSION_SOURCES: dict[str, tuple[str, str]] = {
    "extract_cv": ("app.ai.tasks.extract_cv", "PROMPT_VERSION"),
    "extract_job": ("app.ai.tasks.extract_job", "PROMPT_VERSION"),
    "explain_match": ("app.modules.explanations.service", "PROMPT_VERSION"),
    "generate_email": ("app.ai.tasks.generate", "PROMPT_VERSIONS"),
    "generate_letter": ("app.ai.tasks.generate", "PROMPT_VERSIONS"),
    "tailor_cv": ("app.ai.tasks.generate", "PROMPT_VERSIONS"),
    "optimize_cv": ("app.ai.tasks.generate", "PROMPT_VERSIONS"),
}

#: Valeur journalisée quand la version reste introuvable — jamais NULL
#: (colonne NOT NULL) et jamais silencieuse (warning).
UNKNOWN_PROMPT_VERSION = "unknown"


def prompt_version_for(task: str) -> str:
    """Version du prompt servie pour ``task`` (08 §7.1), lue depuis la tâche."""
    source = _PROMPT_VERSION_SOURCES.get(task)
    if source is None:
        logger.warning("ai_prompt_version_unknown_task task=%s", task)
        return UNKNOWN_PROMPT_VERSION
    module_path, attribute = source
    try:
        value = getattr(importlib.import_module(module_path), attribute)
    except Exception:
        logger.warning("ai_prompt_version_unresolved task=%s", task)
        return UNKNOWN_PROMPT_VERSION
    if isinstance(value, dict):
        resolved = value.get(task)
        return str(resolved) if resolved else UNKNOWN_PROMPT_VERSION
    return str(value)

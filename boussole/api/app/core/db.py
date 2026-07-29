"""Moteur SQLAlchemy async + fabrique de sessions.

Le moteur est créé paresseusement : l'import du module ne tente aucune
connexion (les tests unitaires substituent les dépendances).
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import ClassVar

from sqlalchemy import DateTime, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles.

    Le schéma SQL n'utilise que ``timestamptz`` : tout ``datetime`` Python doit
    être mappé ``TIMESTAMP(timezone=True)``, sans quoi asyncpg caste les binds
    en ``TIMESTAMP WITHOUT TIME ZONE`` et rejette les datetimes aware
    (pagination par date, ``posted_since``).
    """

    type_annotation_map: ClassVar[dict[type, object]] = {datetime: DateTime(timezone=True)}


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

#: Garde de réentrance de :func:`override_engine` — le contexte substitue des
#: globales et restaure « l'état précédent » : deux substitutions imbriquées
#: (ou concurrentes dans le même processus) restaureraient un moteur déjà
#: disposé. Le viol est signalé BRUYAMMENT plutôt que corrompu en silence.
_override_active = False


class EngineOverrideError(RuntimeError):
    """``override_engine`` réentrant : substitution déjà active dans ce processus."""


#: Les paramètres liés ne sortent JAMAIS dans le texte d'une erreur.
#:
#: Sans ça, le ``str()`` d'une ``IntegrityError`` embarque ``[SQL: …]`` **et**
#: ``[parameters: …]`` — quel que soit ``echo``, quel que soit ``DEBUG``. Or
#: ces paramètres sont le contenu du produit : intitulés de poste, employeurs,
#: descriptions d'expérience. Mesuré en revue : une expérience portant « arrêt
#: de travail longue durée suite à burn-out » ressortait en clair sur stdout en
#: ``ENV=production``, sur une simple violation de clé étrangère — déclenchable
#: à volonté par n'importe quel utilisateur authentifié — et repartait telle
#: quelle vers Sentry, dans ``exception.values[].value`` que la liste blanche
#: conserve par construction.
#:
#: ``check_hardening_configuration`` refuse ``DEBUG=true`` pour exactement ce
#: motif. Il couvrait le cas nominal et ratait le cas d'erreur.
_HIDE_PARAMETERS = True


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url, echo=settings.debug, hide_parameters=_HIDE_PARAMETERS
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


def create_worker_engine() -> AsyncEngine:
    """Moteur DÉDIÉ aux workers Celery : ``NullPool``, à disposer par tâche.

    Chaque tâche Celery exécute sa coroutine via ``asyncio.run`` (nouvelle
    boucle d'événements à chaque exécution) : le moteur global poolé
    lierait des connexions asyncpg à une boucle déjà fermée → ``RuntimeError``
    au cycle suivant. ``NullPool`` = une connexion par usage, fermée au
    retour — aucun état ne survit à la boucle. L'appelant DOIT
    ``await engine.dispose()`` en fin de coroutine (et ne jamais partager ce
    moteur entre deux ``asyncio.run``).

    N'altère pas le moteur global de l'API (:func:`get_engine`).
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        poolclass=NullPool,
        hide_parameters=_HIDE_PARAMETERS,
    )


@contextmanager
def override_engine(engine: AsyncEngine) -> Iterator[async_sessionmaker[AsyncSession]]:
    """Substitue temporairement le moteur/la fabrique GLOBAUX par ``engine``.

    Usage workers Celery : le code des modules (``purge_user``/``export_user``
    du registre privacy notamment) ouvre ses sessions via
    :func:`get_session_factory` ; dans une coroutine lancée par
    ``asyncio.run``, la fabrique globale poolée lierait ses connexions à une
    boucle éphémère. En enveloppant la coroutine de la tâche::

        engine = create_worker_engine()
        with override_engine(engine):
            ...  # tout get_session_factory() utilise le moteur NullPool
        await engine.dispose()

    l'état global est restauré quoi qu'il arrive.

    NON RÉENTRANT — et la garde est désormais EXPLICITE : une seconde entrée
    alors qu'une substitution est déjà active lève :class:`EngineOverrideError`
    au lieu de laisser la sortie du contexte interne restaurer un moteur
    intermédiaire (et la sortie externe, un moteur déjà disposé — sessions
    liées à une boucle morte, diagnostic impossible). À n'utiliser que dans
    les workers, une tâche à la fois par processus.
    """
    global _engine, _session_factory, _override_active
    if _override_active:
        raise EngineOverrideError(
            "override_engine est déjà actif dans ce processus : la substitution "
            "du moteur global n'est pas réentrante (une tâche Celery à la fois)."
        )
    previous = (_engine, _session_factory)
    _engine = engine
    _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    _override_active = True
    try:
        yield _session_factory
    finally:
        _override_active = False
        _engine, _session_factory = previous


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Dépendance FastAPI : une session par requête."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def check_database() -> bool:
    """Sonde de readiness : SELECT 1."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # sonde volontairement large
        return False

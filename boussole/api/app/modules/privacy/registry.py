"""Registre déclaratif des modules de données (D21).

Chaque module de données expose ``purge_user(user_id)`` / ``export_user(user_id)``
dans ``app.modules.<nom>.purge`` (transaction gérée PAR le module : chaque
implémentation ouvre sa propre session — voir ``app/modules/auth/purge.py``).

Le registre est :

- **déclaratif** : la liste des modules est une donnée (tuple de
  :class:`ModuleEntry`), contrôlée par un test d'exhaustivité qui compare une
  liste EN DUR — aucun module ne peut être oublié silencieusement (D21) ;
- **paresseux** : les modules réels ne sont importés qu'au moment de
  l'exécution (``importlib`` dans ``resolve_*``), jamais à l'import de ce
  fichier — les modules encore en chantier (generation, applications) ne
  cassent ni l'API ni les tests ;
- **injectable** : les tests construisent un :class:`PurgeRegistry` dont les
  entrées portent des callables directs (fakes), sans aucun import des vrais
  modules de données.
"""

import importlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

PurgeFn = Callable[[uuid.UUID], Awaitable[None]]
ExportFn = Callable[[uuid.UUID], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ModuleEntry:
    """Un module de données du registre.

    Soit ``module_path`` est fourni (résolution paresseuse par importlib),
    soit ``purge`` / ``export`` sont fournis directement (fakes de test).
    """

    name: str
    module_path: str | None = None
    purge: PurgeFn | None = None
    export: ExportFn | None = None

    def _module(self) -> Any:
        if self.module_path is None:
            raise ValueError(f"Entrée « {self.name} » sans module_path ni callables")
        return importlib.import_module(self.module_path)

    def resolve_purge(self) -> PurgeFn:
        """Callable ``purge_user`` — import paresseux au moment de l'appel."""
        if self.purge is not None:
            return self.purge
        fn: PurgeFn = self._module().purge_user
        return fn

    def resolve_export(self) -> ExportFn:
        """Callable ``export_user`` — import paresseux au moment de l'appel."""
        if self.export is not None:
            return self.export
        fn: ExportFn = self._module().export_user
        return fn


@dataclass(frozen=True, slots=True)
class PurgeRegistry:
    """Ensemble ordonné des modules de données orchestrés par privacy."""

    entries: tuple[ModuleEntry, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(entry.name for entry in self.entries)


#: Modules de données du monolithe (D01) — « profiles » inclut les CV,
#: « jobs » inclut les offres sauvegardées (saved_jobs). Le module privacy
#: lui-même n'y figure pas : ses propres données (privacy_exports) sont
#: purgées directement par l'orchestrateur (purge_runner).
DATA_MODULE_NAMES: tuple[str, ...] = (
    "auth",
    "profiles",
    "preferences",
    "jobs",
    "matching",
    "explanations",
    "generation",
    "applications",
)

DEFAULT_REGISTRY = PurgeRegistry(
    entries=tuple(
        ModuleEntry(name=name, module_path=f"app.modules.{name}.purge")
        for name in DATA_MODULE_NAMES
    )
)

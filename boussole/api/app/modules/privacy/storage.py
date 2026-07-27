"""Stockage objet pour les archives d'export RGPD.

``app/core/storage.py`` (ObjectStorage commun, MinIO/S3) est en cours de
création par un autre chantier : au moment où ce module a été écrit il
n'existait pas encore 🟡. Interface locale IDENTIQUE (``put/get/delete``) +
résolution paresseuse : si ``app.core.storage`` expose ``get_object_storage``
au runtime, il est utilisé ; sinon, repli sur un stockage en mémoire de
développement (loggé, jamais silencieux).

Intégration coordinateur : quand ``app/core/storage.py`` est livré, vérifier
la compatibilité de signature puis supprimer le repli mémoire.
"""

import importlib
import logging
from typing import Protocol

logger = logging.getLogger("boussole.privacy")


class ObjectStorage(Protocol):
    """Interface minimale attendue — identique à app/core/storage.py (cible)."""

    async def put(self, key: str, data: bytes) -> None: ...

    async def get(self, key: str) -> bytes | None: ...

    async def delete(self, key: str) -> None: ...


class InMemoryObjectStorage:
    """Repli de développement (process-local). PAS un stockage durable."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self._objects[key] = data

    async def get(self, key: str) -> bytes | None:
        return self._objects.get(key)

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)


_fallback: InMemoryObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
    """Résout le stockage objet : app.core.storage si présent, sinon repli.

    Sert aussi de dépendance FastAPI (surchargée par un fake dans les tests).
    """
    try:
        core_storage = importlib.import_module("app.core.storage")
    except ImportError:
        core_storage = None
    if core_storage is not None:
        factory = getattr(core_storage, "get_object_storage", None)
        if callable(factory):
            storage: ObjectStorage = factory()
            return storage
    global _fallback
    if _fallback is None:
        logger.warning(
            "privacy_storage_fallback",
            extra={"detail": "app.core.storage absent — stockage mémoire de dev 🟡"},
        )
        _fallback = InMemoryObjectStorage()
    return _fallback

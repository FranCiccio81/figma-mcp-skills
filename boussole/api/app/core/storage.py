"""Stockage objet par clé (D09, RM-B-7) — abstraction ``ObjectStorage``.

Le contrat est volontairement minimal : ``put`` / ``get`` / ``delete`` par
clé opaque (``cv/{user_id}/{doc_id}/…``). Deux implémentations :

- :class:`LocalDiskStorage` — répertoire local (``STORAGE_LOCAL_PATH`` 🟡),
  utilisée en dev et dans les tests ; aucune dépendance réseau ;
- :class:`S3ObjectStorage` — stub documenté : le backend S3/MinIO UE
  (bucket versionné, SSE) est branché au jalon M5. TODO(M5).

Les clés sont validées contre la traversée de répertoires : une clé est une
suite de segments ``[A-Za-z0-9._-]`` séparés par ``/`` (jamais ``..``).

⚠️ TODO(M5+) — BLOQUANT DÉPLOIEMENT : tant que :class:`S3ObjectStorage` est
un stub, le SEUL backend utilisable est :class:`LocalDiskStorage`, dont la
racine est un répertoire LOCAL au conteneur. En conséquence **F-Q (export
RGPD) n'est PAS déployable en multi-conteneur** : le worker Celery écrit
l'archive sur SON disque, l'API la relit depuis le SIEN → tout téléchargement
répond 404. Le déploiement M5 exige soit un volume partagé entre API et
workers, soit — cible — :class:`S3ObjectStorage` branché sur le bucket UE
(SSE, versionnement, D09). Ce n'est pas un détail de confort : c'est la
condition d'existence de la fonctionnalité en production.
"""

import re
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageKeyError(ValueError):
    """Clé d'objet invalide (segment vide, caractère interdit ou ``..``)."""


class ObjectNotFoundError(KeyError):
    """Objet absent du stockage pour la clé demandée."""


def validate_key(key: str) -> str:
    """Valide une clé d'objet (anti-traversée) et la retourne inchangée."""
    segments = key.split("/")
    if not segments or any(
        not segment or segment == ".." or not _KEY_SEGMENT.match(segment)
        for segment in segments
    ):
        raise StorageKeyError(f"clé d'objet invalide : {key!r}")
    return key


class ObjectStorage(Protocol):
    """Contrat minimal d'un stockage objet par clé."""

    def put(self, key: str, data: bytes) -> None:
        """Écrit (ou remplace) l'objet ``key``."""
        ...

    def get(self, key: str) -> bytes:
        """Lit l'objet ``key`` — :class:`ObjectNotFoundError` s'il n'existe pas."""
        ...

    def delete(self, key: str) -> None:
        """Supprime l'objet ``key`` — silencieux s'il n'existe pas (idempotent)."""
        ...


class LocalDiskStorage:
    """Stockage sur disque local (dev/tests) — un fichier par clé.

    Racine : ``Settings.storage_local_path`` 🟡 (répertoire créé à la
    demande). Les clés sont validées par :func:`validate_key` : le chemin
    résolu reste toujours sous la racine.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        return self._root / validate_key(key)

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)


class S3ObjectStorage:
    """Stub S3/MinIO — TODO(M5).

    Le backend réel (bucket ``Settings.s3_bucket``, endpoint UE, SSE,
    versionnement — D09) sera branché au jalon M5 avec un client S3
    (aioboto3/minio 🟡). D'ici là toute utilisation échoue explicitement :
    aucun TODO silencieux.

    Rappel du blocage déploiement décrit en tête de module : sans cette classe
    (ou un volume partagé), les archives d'export écrites par les workers sont
    invisibles de l'API. Voir aussi ``app/modules/privacy/export_builder.py``.
    """

    def put(self, key: str, data: bytes) -> None:
        raise NotImplementedError("S3ObjectStorage : prévu au jalon M5 (TODO(M5))")

    def get(self, key: str) -> bytes:
        raise NotImplementedError("S3ObjectStorage : prévu au jalon M5 (TODO(M5))")

    def delete(self, key: str) -> None:
        raise NotImplementedError("S3ObjectStorage : prévu au jalon M5 (TODO(M5))")


def get_object_storage() -> ObjectStorage:
    """Dépendance FastAPI / fabrique workers — LocalDiskStorage en M4 🟡.

    Substituée par un stockage en mémoire dans les tests unitaires ;
    remplacée par :class:`S3ObjectStorage` au M5 (TODO(M5)).
    """
    return LocalDiskStorage(get_settings().storage_local_path)

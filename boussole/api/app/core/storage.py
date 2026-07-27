"""Stockage objet par clé (D09, RM-B-7) — abstraction ``ObjectStorage``.

Le contrat est volontairement minimal et **SYNCHRONE** : ``put`` / ``get`` /
``delete`` par clé opaque (``cv/{user_id}/{doc_id}/…``). Deux implémentations,
qui doivent se comporter à l'identique (cf. le test de contrat partagé
``tests/unit/core/test_storage_s3.py``) :

- :class:`LocalDiskStorage` — répertoire local (``STORAGE_LOCAL_PATH`` 🟡) ;
- :class:`S3ObjectStorage` — bucket S3/MinIO UE (D09), chiffrement au repos
  côté serveur (SSE-KMS, ou SSE-S3/AES256 comme minimum acceptable 🟡).

Les clés sont validées contre la traversée de répertoires : une clé est une
suite de segments ``[A-Za-z0-9._-]`` séparés par ``/`` (jamais ``..``).

⚠️ CHOIX DU BACKEND — ``STORAGE_BACKEND`` (``local`` | ``s3``)
-------------------------------------------------------------
``local`` écrit sur le disque **du conteneur courant**. Il est réservé au
développement et aux tests **mono-processus**. Dès que l'API et les workers
Celery sont deux conteneurs distincts — c'est-à-dire en production, en staging
et dans le compose de dev — ``local`` casse F-Q (export RGPD) : le worker écrit
l'archive sur SON disque, l'API la relit depuis le SIEN et tout téléchargement
répond 404 ; les CV disparaissent au redémarrage. **La production DOIT utiliser
``s3``.**

:func:`check_storage_configuration` refuse explicitement cette combinaison
(``ENV=production`` + ``STORAGE_BACKEND=local``) : mieux vaut ne pas démarrer
que perdre des exports. Elle est destinée à être appelée au démarrage / dans
``/readyz`` (branchement dans ``app/main.py`` — hors périmètre de ce module).

Chiffrement au repos (09-security-and-privacy §5.6, D09/D23) : ``S3_SSE``
sélectionne ``aws:kms`` (avec ``S3_KMS_KEY_ID`` si une clé gérée est fournie),
``AES256`` (SSE-S3 — minimum acceptable) ou ``none``. ``none`` n'est toléré
qu'en dev (MinIO sans KES ne sait pas chiffrer côté serveur) et est refusé en
production par :func:`check_storage_configuration`.
"""

import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings, get_settings

_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")

# Codes d'erreur S3 signifiant « objet absent ». ``NoSuchBucket`` en est
# volontairement exclu : un bucket manquant est une ERREUR DE CONFIGURATION,
# pas un objet absent — la masquer en 404 reproduirait le bug d'origine.
_NOT_FOUND_CODES = frozenset({"NoSuchKey", "NotFound", "404"})

# Bornes réseau par défaut (botocore) — un worker ne doit jamais rester
# suspendu indéfiniment sur le stockage objet.
_DEFAULT_CONNECT_TIMEOUT = 5.0
_DEFAULT_READ_TIMEOUT = 30.0
_DEFAULT_MAX_ATTEMPTS = 3


class StorageKeyError(ValueError):
    """Clé d'objet invalide (segment vide, caractère interdit ou ``..``)."""


class ObjectNotFoundError(KeyError):
    """Objet absent du stockage pour la clé demandée."""


class StorageConfigurationError(RuntimeError):
    """Configuration de stockage inutilisable pour l'environnement courant."""


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

    ⚠️ Mono-processus uniquement : le disque n'est pas partagé entre l'API et
    les workers. Voir l'avertissement en tête de module.
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


def _is_not_found(exc: Any) -> bool:
    """``True`` si un ``ClientError`` botocore signale un objet absent."""
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    code = str(response.get("Error", {}).get("Code", ""))
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in _NOT_FOUND_CODES or status == 404


class S3ObjectStorage:
    """Stockage objet S3 / MinIO (D09) — implémentation synchrone boto3.

    Le client boto3 est construit **paresseusement** (au premier appel) et
    **réutilisé** ensuite : construire un client par requête coûterait la
    résolution de credentials et l'ouverture d'un pool de connexions à chaque
    upload de CV. La construction est protégée par un verrou : les workers
    Celery sont multi-threads.

    Compatible MinIO en dev via ``endpoint_url`` + ``addressing_style="path"``
    (MinIO n'expose pas de virtual-host buckets par défaut).

    Chiffrement au repos : voir ``sse`` / ``kms_key_id`` et §5.6 de
    09-security-and-privacy.md.
    """

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        region: str = "eu-west-1",
        access_key: str | None = None,
        secret_key: str | None = None,
        sse: str = "AES256",
        kms_key_id: str | None = None,
        addressing_style: str = "auto",
        connect_timeout: float = _DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = _DEFAULT_READ_TIMEOUT,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        if not bucket:
            raise StorageConfigurationError("S3ObjectStorage : bucket requis (S3_BUCKET)")
        self._bucket = bucket
        self._endpoint_url = endpoint_url or None
        self._region = region
        self._access_key = access_key or None
        self._secret_key = secret_key or None
        self._sse = sse
        self._kms_key_id = kms_key_id or None
        # Un endpoint explicite désigne, en pratique, un S3 auto-hébergé
        # (MinIO) : le style « path » est le seul universellement supporté.
        if addressing_style == "auto" and self._endpoint_url:
            addressing_style = "path"
        self._addressing_style = addressing_style
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._max_attempts = max_attempts
        self._client: Any = None
        self._client_lock = threading.Lock()

    # ------------------------------------------------------------ client

    def _build_client(self) -> Any:
        # Import paresseux : botocore est lourd et n'est pas nécessaire quand
        # le backend « local » est actif (tests unitaires).
        import boto3
        from botocore.config import Config as BotoConfig

        config = BotoConfig(
            region_name=self._region,
            signature_version="s3v4",
            s3={"addressing_style": self._addressing_style},
            connect_timeout=self._connect_timeout,
            read_timeout=self._read_timeout,
            # Retries BORNÉS : au-delà, on préfère l'échec explicite de la
            # tâche Celery (qui a sa propre politique de reprise) à un worker
            # bloqué sur un backend en panne.
            retries={"max_attempts": self._max_attempts, "mode": "standard"},
        )
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=self._region,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=config,
        )

    @property
    def client(self) -> Any:
        """Client boto3 partagé — construit une seule fois (double-checked)."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = self._build_client()
        return self._client

    # -------------------------------------------------------- chiffrement

    def encryption_params(self) -> dict[str, str]:
        """En-têtes de chiffrement au repos envoyés à chaque ``put_object``.

        - une clé KMS fournie ⇒ ``aws:kms`` + ``SSEKMSKeyId`` (cible D09/D23) ;
        - ``sse="aws:kms"`` sans clé ⇒ clé KMS gérée par le fournisseur ;
        - ``sse="AES256"`` ⇒ SSE-S3, minimum acceptable 🟡 ;
        - ``sse="none"`` ⇒ aucun en-tête (dev/MinIO sans KES uniquement).
        """
        if self._sse == "none":
            return {}
        if self._kms_key_id:
            return {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self._kms_key_id}
        if self._sse == "aws:kms":
            return {"ServerSideEncryption": "aws:kms"}
        return {"ServerSideEncryption": "AES256"}

    # ------------------------------------------------------------ contrat

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(
            Bucket=self._bucket,
            Key=validate_key(key),
            Body=data,
            **self.encryption_params(),
        )

    def get(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        validated = validate_key(key)
        try:
            response = self.client.get_object(Bucket=self._bucket, Key=validated)
        except ClientError as exc:
            if _is_not_found(exc):
                raise ObjectNotFoundError(key) from exc
            raise
        data: bytes = response["Body"].read()
        return data

    def delete(self, key: str) -> None:
        from botocore.exceptions import ClientError

        validated = validate_key(key)
        try:
            self.client.delete_object(Bucket=self._bucket, Key=validated)
        except ClientError as exc:
            # ``DeleteObject`` est déjà idempotent sur S3 ; certains backends
            # compatibles répondent tout de même 404 — le contrat impose le
            # silence (cf. purge RGPD, qui rejoue les suppressions).
            if _is_not_found(exc):
                return
            raise


# --------------------------------------------------------------- fabrique


@lru_cache(maxsize=8)
def _build_local_storage(root: str) -> LocalDiskStorage:
    return LocalDiskStorage(root)


@lru_cache(maxsize=8)
def _build_s3_storage(
    *,
    bucket: str,
    endpoint_url: str | None,
    region: str,
    access_key: str | None,
    secret_key: str | None,
    sse: str,
    kms_key_id: str | None,
    addressing_style: str,
    connect_timeout: float,
    read_timeout: float,
    max_attempts: int,
) -> S3ObjectStorage:
    return S3ObjectStorage(
        bucket,
        endpoint_url=endpoint_url,
        region=region,
        access_key=access_key,
        secret_key=secret_key,
        sse=sse,
        kms_key_id=kms_key_id,
        addressing_style=addressing_style,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_attempts=max_attempts,
    )


def reset_object_storage_cache() -> None:
    """Vide le cache des instances (tests, ou rotation de configuration)."""
    _build_local_storage.cache_clear()
    _build_s3_storage.cache_clear()


def check_storage_configuration(settings: Settings | None = None) -> None:
    """Valide la configuration de stockage — à appeler au démarrage / readyz.

    Lève :class:`StorageConfigurationError` si :

    - ``ENV=production`` avec ``STORAGE_BACKEND=local`` : l'API et les workers
      ne partagent pas de disque, F-Q (export RGPD) répondrait 404 et les CV
      seraient perdus au redémarrage. Refuser de démarrer est le comportement
      sûr ;
    - ``ENV=production`` avec ``S3_SSE=none`` : D09/§5.6 imposent le
      chiffrement au repos ;
    - ``STORAGE_BACKEND=s3`` sans bucket configuré.

    ⚠️ Non branchée dans ``app/main.py`` (hors périmètre) : à appeler dans le
    ``lifespan`` de démarrage et/ou ``/readyz``.
    """
    settings = settings if settings is not None else get_settings()
    backend = getattr(settings, "storage_backend", "local")

    if backend not in {"local", "s3"}:
        raise StorageConfigurationError(f"STORAGE_BACKEND inconnu : {backend!r}")

    if backend == "s3" and not getattr(settings, "s3_bucket", ""):
        raise StorageConfigurationError("STORAGE_BACKEND=s3 exige un S3_BUCKET non vide")

    if not getattr(settings, "is_production", False):
        return

    if backend == "local":
        raise StorageConfigurationError(
            "STORAGE_BACKEND=local est interdit en production : le disque n'est pas "
            "partagé entre l'API et les workers Celery — les exports RGPD seraient "
            "introuvables (404) et les CV perdus au redémarrage. Configurer "
            "STORAGE_BACKEND=s3 (bucket UE, D09)."
        )
    if getattr(settings, "s3_sse", "AES256") == "none":
        raise StorageConfigurationError(
            "S3_SSE=none est interdit en production : le chiffrement au repos est "
            "exigé (D09, 09-security-and-privacy §5.6). Utiliser aws:kms "
            "(S3_KMS_KEY_ID) ou, au minimum, AES256."
        )


def get_object_storage() -> ObjectStorage:
    """Dépendance FastAPI / fabrique workers — backend selon ``STORAGE_BACKEND``.

    L'instance est mise en cache par configuration : le client boto3 sous-jacent
    (pool de connexions, credentials résolus) est ainsi partagé par toutes les
    requêtes et toutes les tâches du processus.

    ⚠️ ``local`` est réservé au dev/test mono-processus — voir l'avertissement
    en tête de module et :func:`check_storage_configuration`.
    """
    settings = get_settings()
    # ``getattr`` : certains tests substituent un double de configuration
    # partiel (seul ``storage_local_path`` est fourni) — le défaut reste
    # « local », qui est aussi le défaut de ``Settings``.
    backend = getattr(settings, "storage_backend", "local")
    if backend == "s3":
        return _build_s3_storage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint or None,
            region=settings.s3_region,
            access_key=settings.s3_access_key or None,
            secret_key=settings.s3_secret_key or None,
            sse=settings.s3_sse,
            kms_key_id=settings.s3_kms_key_id or None,
            addressing_style=settings.s3_addressing_style,
            connect_timeout=settings.s3_connect_timeout_seconds,
            read_timeout=settings.s3_read_timeout_seconds,
            max_attempts=settings.s3_max_attempts,
        )
    return _build_local_storage(str(settings.storage_local_path))

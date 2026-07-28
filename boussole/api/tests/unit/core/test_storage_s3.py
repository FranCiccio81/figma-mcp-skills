"""Stockage objet S3 réel (D09) — backend, sélection par config, contrat.

Contexte de régression : ``S3ObjectStorage`` était un stub ``NotImplementedError``
et ``get_object_storage()`` retournait TOUJOURS ``LocalDiskStorage``. En
multi-conteneur, le worker Celery écrivait l'archive d'export RGPD sur SON
disque et l'API la relisait depuis LE SIEN → 404 systématique, et perte des CV
au redémarrage.

Deux familles de tests :

1. le backend S3 lui-même (moto), y compris le chiffrement au repos (§5.6) ;
2. un **contrat partagé paramétré** sur les DEUX implémentations : c'est la
   divergence de contrat (async/sync, ``None`` vs exception) qui avait cassé
   l'export ; toute nouvelle divergence doit échouer ici.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import boto3
import pytest
from moto import mock_aws
from pydantic import ValidationError

from app.core.config import Settings
from app.core.storage import (
    LocalDiskStorage,
    ObjectNotFoundError,
    ObjectStorage,
    S3ObjectStorage,
    StorageConfigurationError,
    StorageKeyError,
    check_storage_configuration,
    get_object_storage,
    probe_object_storage,
    reset_object_storage_cache,
)

BUCKET = "boussole-test"
REGION = "eu-west-1"  # D09 : hébergement UE
CREDENTIALS = {"access_key": "test-key", "secret_key": "test-secret"}


def _create_bucket() -> None:
    client = boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id=CREDENTIALS["access_key"],
        aws_secret_access_key=CREDENTIALS["secret_key"],
    )
    client.create_bucket(
        Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION}
    )


def _inspection_client() -> Any:
    """Client indépendant du SUT, pour vérifier l'état côté serveur."""
    return boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id=CREDENTIALS["access_key"],
        aws_secret_access_key=CREDENTIALS["secret_key"],
    )


@pytest.fixture(autouse=True)
def _clean_storage_cache() -> Iterator[None]:
    """Aucune instance ne fuit d'un test à l'autre (le cache est global)."""
    reset_object_storage_cache()
    yield
    reset_object_storage_cache()


@pytest.fixture
def s3_storage() -> Iterator[S3ObjectStorage]:
    with mock_aws():
        _create_bucket()
        yield S3ObjectStorage(
            BUCKET,
            region=REGION,
            access_key=CREDENTIALS["access_key"],
            secret_key=CREDENTIALS["secret_key"],
        )


# --------------------------------------------------------------- backend S3


class TestBackendS3:
    def test_put_get_delete_de_bout_en_bout(self, s3_storage: S3ObjectStorage) -> None:
        key = "privacy-exports/user-1/export.json"
        s3_storage.put(key, b'{"ok": true}')

        assert s3_storage.get(key) == b'{"ok": true}'

        s3_storage.delete(key)
        with pytest.raises(ObjectNotFoundError):
            s3_storage.get(key)

    def test_get_sur_cle_absente_leve_object_not_found(
        self, s3_storage: S3ObjectStorage
    ) -> None:
        # Régression : sans traduction du ClientError, l'API remontait un 500
        # botocore au lieu du 404 attendu par le routeur privacy.
        with pytest.raises(ObjectNotFoundError):
            s3_storage.get("privacy-exports/inexistant.json")

    def test_delete_est_idempotent(self, s3_storage: S3ObjectStorage) -> None:
        # La purge RGPD rejoue les suppressions : un objet déjà parti ne doit
        # pas faire échouer la purge du compte.
        s3_storage.delete("privacy-exports/inexistant.json")
        s3_storage.delete("privacy-exports/inexistant.json")

    def test_put_remplace_l_objet(self, s3_storage: S3ObjectStorage) -> None:
        s3_storage.put("cv/a/b.pdf", b"v1")
        s3_storage.put("cv/a/b.pdf", b"v2")
        assert s3_storage.get("cv/a/b.pdf") == b"v2"

    def test_bucket_vide_refuse_a_la_construction(self) -> None:
        with pytest.raises(StorageConfigurationError):
            S3ObjectStorage("")


class TestChiffrementAuRepos:
    """D09 / 09-security-and-privacy §5.6 — SSE demandée à chaque écriture."""

    def test_sse_s3_aes256_par_defaut(self, s3_storage: S3ObjectStorage) -> None:
        s3_storage.put("cv/a/b.pdf", b"contenu")
        head = _inspection_client().head_object(Bucket=BUCKET, Key="cv/a/b.pdf")
        assert head["ServerSideEncryption"] == "AES256"

    def test_sse_kms_quand_une_cle_est_fournie(self) -> None:
        with mock_aws():
            _create_bucket()
            storage = S3ObjectStorage(
                BUCKET,
                region=REGION,
                access_key=CREDENTIALS["access_key"],
                secret_key=CREDENTIALS["secret_key"],
                sse="aws:kms",
                kms_key_id="arn:aws:kms:eu-west-1:000000000000:key/boussole",
            )
            storage.put("cv/a/b.pdf", b"contenu")
            head = _inspection_client().head_object(Bucket=BUCKET, Key="cv/a/b.pdf")

        assert head["ServerSideEncryption"] == "aws:kms"
        assert "boussole" in head["SSEKMSKeyId"]

    def test_une_cle_kms_force_aws_kms_meme_si_sse_vaut_aes256(self) -> None:
        storage = S3ObjectStorage(BUCKET, sse="AES256", kms_key_id="k-1")
        assert storage.encryption_params() == {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": "k-1",
        }

    def test_sse_none_n_envoie_aucun_en_tete(self) -> None:
        # MinIO sans KES : dev uniquement, refusé en production (cf. plus bas).
        assert S3ObjectStorage(BUCKET, sse="none").encryption_params() == {}

    def test_sse_none_ecrit_quand_meme(self) -> None:
        with mock_aws():
            _create_bucket()
            storage = S3ObjectStorage(
                BUCKET,
                region=REGION,
                access_key=CREDENTIALS["access_key"],
                secret_key=CREDENTIALS["secret_key"],
                sse="none",
            )
            storage.put("cv/a/b.pdf", b"contenu")
            head = _inspection_client().head_object(Bucket=BUCKET, Key="cv/a/b.pdf")

        assert "ServerSideEncryption" not in head


class TestClesInvalides:
    """``validate_key`` s'applique comme sur LocalDisk (anti-traversée)."""

    @pytest.mark.parametrize(
        "key",
        [
            "../etc/passwd",
            "cv/../../secret",
            "cv//b.pdf",
            "",
            "cv/a b.pdf",
            "cv/a\\b.pdf",
        ],
    )
    def test_put_get_delete_refusent_la_cle(
        self, s3_storage: S3ObjectStorage, key: str
    ) -> None:
        with pytest.raises(StorageKeyError):
            s3_storage.put(key, b"x")
        with pytest.raises(StorageKeyError):
            s3_storage.get(key)
        with pytest.raises(StorageKeyError):
            s3_storage.delete(key)


class TestClientReutilise:
    def test_le_client_boto3_est_construit_une_seule_fois(self) -> None:
        with mock_aws():
            _create_bucket()
            storage = S3ObjectStorage(
                BUCKET,
                region=REGION,
                access_key=CREDENTIALS["access_key"],
                secret_key=CREDENTIALS["secret_key"],
            )
            premier = storage.client
            storage.put("cv/a/b.pdf", b"x")
            storage.get("cv/a/b.pdf")

            assert storage.client is premier

    def test_le_client_est_paresseux(self) -> None:
        # Aucune construction (ni résolution de credentials) tant qu'aucune
        # opération n'est demandée : instancier le storage doit rester gratuit.
        storage = S3ObjectStorage(BUCKET)
        assert storage._client is None


# ------------------------------------------------- sélection par configuration


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "storage_backend": "local",
        "storage_local_path": ".storage-test",
        "s3_bucket": BUCKET,
        "s3_endpoint": "",
        "s3_region": REGION,
        "s3_access_key": CREDENTIALS["access_key"],
        "s3_secret_key": CREDENTIALS["secret_key"],
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def use_settings(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Settings]:
    def _apply(**overrides: object) -> Settings:
        settings = _settings(**overrides)
        monkeypatch.setattr("app.core.storage.get_settings", lambda: settings)
        return settings

    return _apply


class TestSelectionParConfiguration:
    def test_backend_local_par_defaut(
        self, use_settings: Callable[..., Settings], tmp_path: Path
    ) -> None:
        use_settings(storage_backend="local", storage_local_path=str(tmp_path))
        assert isinstance(get_object_storage(), LocalDiskStorage)

    def test_backend_s3_quand_demande(self, use_settings: Callable[..., Settings]) -> None:
        use_settings(storage_backend="s3")
        assert isinstance(get_object_storage(), S3ObjectStorage)

    def test_l_instance_est_mise_en_cache(self, use_settings: Callable[..., Settings]) -> None:
        # Sinon chaque requête FastAPI reconstruirait un client boto3.
        use_settings(storage_backend="s3")
        assert get_object_storage() is get_object_storage()

    def test_le_cache_est_indexe_sur_la_configuration(
        self,
        use_settings: Callable[..., Settings],
        tmp_path: Path,
    ) -> None:
        use_settings(storage_backend="local", storage_local_path=str(tmp_path / "a"))
        premier = get_object_storage()
        use_settings(storage_backend="local", storage_local_path=str(tmp_path / "b"))
        assert get_object_storage() is not premier

    def test_le_backend_s3_recoit_bien_l_endpoint_minio(
        self, use_settings: Callable[..., Settings]
    ) -> None:
        use_settings(storage_backend="s3", s3_endpoint="http://minio:9000")
        storage = get_object_storage()
        assert isinstance(storage, S3ObjectStorage)
        assert storage._endpoint_url == "http://minio:9000"
        # Endpoint explicite ⇒ addressing style « path » (MinIO).
        assert storage._addressing_style == "path"


class TestVerificationAuDemarrage:
    def test_production_avec_backend_local_refuse_de_demarrer(self) -> None:
        # Mieux vaut ne pas démarrer que perdre silencieusement les exports.
        with pytest.raises(StorageConfigurationError, match="production"):
            check_storage_configuration(_settings(env="production", storage_backend="local"))

    def test_production_avec_s3_et_sse_passe(self) -> None:
        check_storage_configuration(
            _settings(env="production", storage_backend="s3", s3_sse="aws:kms")
        )

    def test_production_sans_chiffrement_refuse(self) -> None:
        with pytest.raises(StorageConfigurationError, match="S3_SSE"):
            check_storage_configuration(
                _settings(env="production", storage_backend="s3", s3_sse="none")
            )

    def test_developpement_avec_backend_local_est_tolere(self) -> None:
        check_storage_configuration(_settings(env="development", storage_backend="local"))

    def test_s3_sans_bucket_refuse(self) -> None:
        with pytest.raises(StorageConfigurationError, match="S3_BUCKET"):
            check_storage_configuration(_settings(storage_backend="s3", s3_bucket=""))


# ------------------------------------------------------- contrat partagé


@pytest.fixture(params=["local", "s3"])
def storage(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[ObjectStorage]:
    """La MÊME batterie d'assertions sur les deux implémentations."""
    if request.param == "local":
        yield LocalDiskStorage(tmp_path)
        return
    with mock_aws():
        _create_bucket()
        yield S3ObjectStorage(
            BUCKET,
            region=REGION,
            access_key=CREDENTIALS["access_key"],
            secret_key=CREDENTIALS["secret_key"],
        )


class TestContratPartage:
    """Local et S3 doivent être INTERCHANGEABLES (c'était le bug d'origine)."""

    def test_put_puis_get_rend_les_octets_ecrits(self, storage: ObjectStorage) -> None:
        storage.put("cv/u1/doc.pdf", b"\x00binaire\xff")
        assert storage.get("cv/u1/doc.pdf") == b"\x00binaire\xff"

    def test_les_operations_sont_synchrones(self, storage: ObjectStorage) -> None:
        # Aucune coroutine : un `await` ici lèverait TypeError — bug C2.
        assert storage.put("cv/u1/doc.pdf", b"x") is None
        assert isinstance(storage.get("cv/u1/doc.pdf"), bytes)
        assert storage.delete("cv/u1/doc.pdf") is None

    def test_objet_vide_supporte(self, storage: ObjectStorage) -> None:
        storage.put("cv/u1/vide.bin", b"")
        assert storage.get("cv/u1/vide.bin") == b""

    def test_cle_profonde_supportee(self, storage: ObjectStorage) -> None:
        key = "privacy-exports/2026/07/27/user-1/export.json"
        storage.put(key, b"{}")
        assert storage.get(key) == b"{}"

    def test_put_ecrase(self, storage: ObjectStorage) -> None:
        storage.put("k/a.bin", b"v1")
        storage.put("k/a.bin", b"v2")
        assert storage.get("k/a.bin") == b"v2"

    def test_get_absent_leve_object_not_found(self, storage: ObjectStorage) -> None:
        with pytest.raises(ObjectNotFoundError):
            storage.get("k/absent.bin")

    def test_get_apres_delete_leve_object_not_found(self, storage: ObjectStorage) -> None:
        storage.put("k/a.bin", b"v")
        storage.delete("k/a.bin")
        with pytest.raises(ObjectNotFoundError):
            storage.get("k/a.bin")

    def test_delete_absent_est_silencieux(self, storage: ObjectStorage) -> None:
        storage.delete("k/absent.bin")

    def test_delete_deux_fois_est_silencieux(self, storage: ObjectStorage) -> None:
        storage.put("k/a.bin", b"v")
        storage.delete("k/a.bin")
        storage.delete("k/a.bin")

    @pytest.mark.parametrize("key", ["../evade", "k/../../evade", "k//a", "", "k/a b"])
    def test_cle_invalide_rejetee_identiquement(
        self, storage: ObjectStorage, key: str
    ) -> None:
        with pytest.raises(StorageKeyError):
            storage.put(key, b"x")
        with pytest.raises(StorageKeyError):
            storage.get(key)
        with pytest.raises(StorageKeyError):
            storage.delete(key)

    def test_object_not_found_reste_un_key_error(self, storage: ObjectStorage) -> None:
        # Les consommateurs (router privacy, service CV) attrapent parfois
        # KeyError : la hiérarchie d'exceptions fait partie du contrat.
        with pytest.raises(KeyError):
            storage.get("k/absent.bin")


# ------------------------------------------- bucket absent / droits refusés


def _client_error(code: str, status: int, operation: str = "GetObject") -> Any:
    """``ClientError`` botocore réaliste — S3 répond 404 sur ``NoSuchBucket``."""
    from botocore.exceptions import ClientError

    return ClientError(
        {
            "Error": {"Code": code, "Message": code},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        operation,
    )


class _ExplodingClient:
    """Client boto3 minimal qui lève toujours la même erreur S3."""

    def __init__(self, error: Any) -> None:
        self.error = error
        self.calls: list[str] = []

    def _raise(self, operation: str) -> Any:
        self.calls.append(operation)
        raise self.error

    def get_object(self, **_: object) -> Any:
        return self._raise("GetObject")

    def put_object(self, **_: object) -> Any:
        return self._raise("PutObject")

    def delete_object(self, **_: object) -> Any:
        return self._raise("DeleteObject")

    def head_bucket(self, **_: object) -> Any:
        return self._raise("HeadBucket")


def _storage_with_error(code: str, status: int = 404) -> S3ObjectStorage:
    storage = S3ObjectStorage(BUCKET, region=REGION, **CREDENTIALS)
    storage._client = _ExplodingClient(_client_error(code, status))
    return storage


class TestBucketAbsentEtDroitsRefuses:
    """M4 — un bucket manquant N'EST PAS un objet absent.

    ``_is_not_found`` testait ``code in _NOT_FOUND_CODES **or** status == 404``.
    Or S3 et MinIO répondent HTTP 404 sur ``NoSuchBucket`` : le repli sur le
    statut annulait l'exclusion pourtant documentée du code. Conséquences
    vérifiées : export RGPD « archive absente », CV marqué ``unreadable``, et
    purge RGPD rapportant un succès sans avoir rien supprimé.
    """

    def test_get_sur_bucket_absent_est_une_erreur_de_configuration(self) -> None:
        storage = _storage_with_error("NoSuchBucket", status=404)

        with pytest.raises(StorageConfigurationError, match="NoSuchBucket"):
            storage.get("privacy-exports/user-1/export.json")

    def test_get_sur_bucket_absent_n_est_pas_un_object_not_found(self) -> None:
        storage = _storage_with_error("NoSuchBucket", status=404)

        # Le point exact de la régression : traduit en ObjectNotFoundError,
        # l'incident devenait un 404 métier « archive introuvable ».
        with pytest.raises(Exception) as excinfo:
            storage.get("privacy-exports/user-1/export.json")
        assert not isinstance(excinfo.value, ObjectNotFoundError)
        assert not isinstance(excinfo.value, KeyError)

    def test_delete_sur_bucket_absent_ne_rapporte_pas_un_faux_succes(self) -> None:
        # Le plus grave : la purge RGPD rejoue les suppressions et considérait
        # « bucket absent » comme « déjà supprimé » — succès rapporté, données
        # toujours en place.
        storage = _storage_with_error("NoSuchBucket", status=404)

        with pytest.raises(StorageConfigurationError):
            storage.delete("cv/user-1/doc.pdf")

    def test_droits_refuses_remontent_en_erreur_de_configuration(self) -> None:
        storage = _storage_with_error("AccessDenied", status=403)

        with pytest.raises(StorageConfigurationError, match="AccessDenied"):
            storage.get("cv/user-1/doc.pdf")

    def test_droits_refuses_sur_delete_ne_sont_pas_avales(self) -> None:
        storage = _storage_with_error("AccessDenied", status=403)

        with pytest.raises(StorageConfigurationError):
            storage.delete("cv/user-1/doc.pdf")

    def test_droits_refuses_sur_put_remontent(self) -> None:
        storage = _storage_with_error("AccessDenied", status=403)

        with pytest.raises(StorageConfigurationError):
            storage.put("cv/user-1/doc.pdf", b"x")

    @pytest.mark.parametrize("code", ["InvalidAccessKeyId", "SignatureDoesNotMatch"])
    def test_credentials_invalides_remontent_en_configuration(self, code: str) -> None:
        with pytest.raises(StorageConfigurationError):
            _storage_with_error(code, status=403).get("cv/a/b.pdf")

    def test_une_cle_reellement_absente_reste_un_object_not_found(self) -> None:
        # Contre-épreuve : le correctif ne doit pas casser le cas nominal.
        storage = _storage_with_error("NoSuchKey", status=404)

        with pytest.raises(ObjectNotFoundError):
            storage.get("cv/user-1/absent.pdf")

    def test_un_404_nu_sans_code_connu_n_est_plus_traduit_en_absent(self) -> None:
        # Le statut HTTP ne décide plus de rien : seul le code compte.
        storage = _storage_with_error("SomeUnknownError", status=404)

        with pytest.raises(Exception) as excinfo:
            storage.get("cv/user-1/doc.pdf")
        assert not isinstance(excinfo.value, ObjectNotFoundError)


class TestSondeDeJoignabilite:
    """(13) ``/readyz`` ne testait que la configuration — un bucket supprimé
    laissait le service « ready » pendant que tout échouait."""

    def test_ping_passe_sur_un_bucket_existant(self, s3_storage: S3ObjectStorage) -> None:
        assert s3_storage.ping() is None

    def test_ping_echoue_sur_bucket_absent(self) -> None:
        with pytest.raises(StorageConfigurationError):
            _storage_with_error("NoSuchBucket", status=404).ping()

    def test_ping_echoue_sur_droits_refuses(self) -> None:
        with pytest.raises(StorageConfigurationError):
            _storage_with_error("AccessDenied", status=403).ping()

    def test_ping_local_cree_la_racine(self, tmp_path: Path) -> None:
        storage = LocalDiskStorage(tmp_path / "absent")
        storage.ping()
        assert (tmp_path / "absent").is_dir()

    def test_ping_local_refuse_une_racine_qui_est_un_fichier(self, tmp_path: Path) -> None:
        fichier = tmp_path / "pas-un-repertoire"
        fichier.write_bytes(b"x")

        with pytest.raises(StorageConfigurationError):
            LocalDiskStorage(fichier).ping()

    def test_probe_object_storage_suit_la_configuration(
        self, use_settings: Callable[..., Settings], tmp_path: Path
    ) -> None:
        use_settings(storage_backend="local", storage_local_path=str(tmp_path / "racine"))
        probe_object_storage()
        assert (tmp_path / "racine").is_dir()


class TestSeuilDeDurcissementParEnvironnement:
    """M5 — le refus de démarrer était contournable par une chaîne."""

    @pytest.mark.parametrize("env", ["staging", "production"])
    def test_le_backend_local_est_refuse_des_qu_on_quitte_le_developpement(
        self, env: str
    ) -> None:
        # `staging` n'était couvert par AUCUN contrôle : mêmes conteneurs
        # distincts, mêmes exports perdus.
        with pytest.raises(StorageConfigurationError):
            check_storage_configuration(_settings(env=env, storage_backend="local"))

    @pytest.mark.parametrize("env", ["staging", "production"])
    def test_le_chiffrement_au_repos_est_exige_des_qu_on_quitte_le_developpement(
        self, env: str
    ) -> None:
        with pytest.raises(StorageConfigurationError, match="S3_SSE"):
            check_storage_configuration(
                _settings(env=env, storage_backend="s3", s3_sse="none")
            )

    @pytest.mark.parametrize("valeur", ["prod", "Production", "PRODUCTION", " production "])
    def test_aucune_variante_d_orthographe_ne_desactive_les_controles(
        self, valeur: str
    ) -> None:
        """Le cœur du contournement : ``is_production`` comparait par égalité
        exacte sur un ``str`` libre. ``ENV=prod`` désactivait TOUS les
        garde-fous — stockage local accepté, chiffrement facultatif, docs
        OpenAPI exposées — sans le moindre message."""
        try:
            settings = _settings(env=valeur, storage_backend="local")
        except ValidationError:
            return  # vocabulaire fermé : la valeur est rejetée en amont
        # …ou bien elle a été normalisée vers `production` : dans les deux cas
        # le stockage local doit être refusé.
        assert settings.env == "production"
        with pytest.raises(StorageConfigurationError):
            check_storage_configuration(settings)

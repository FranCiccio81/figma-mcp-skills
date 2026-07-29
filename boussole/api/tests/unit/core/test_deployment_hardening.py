"""Ce qui doit tenir le jour où l'application est vraiment exposée.

Revue avant déploiement. Chaque garantie ici a été trouvée **absente** en
faisant tourner l'application pour de vrai, pas en lisant le code — et
plusieurs étaient contredites par la documentation qui les promettait.
"""

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.secrets import SecretConfigurationError, check_secrets_configuration
from app.main import MAX_REQUEST_BODY_BYTES, create_app


def _app(**env: str):
    fake = lambda: fakeredis.aioredis.FakeRedis(decode_responses=True)  # noqa: E731
    return TestClient(create_app(redis_cache_factory=fake, redis_persistent_factory=fake))


class TestUnCorpsEnormeEstRefuseAvantDEtreLu:
    """8 requêtes concurrentes de 100 Mo faisaient monter le processus à
    1,94 Go, depuis un client **non authentifié**. Sur un conteneur limité à
    512 Mo ou 1 Go, c'est un OOMKill déclenché par une ligne de shell.

    Le plafond de 10 Mo de l'import de CV ne protégeait que la base : il
    s'applique après réception complète (mesuré, un envoi de 300 Mo rendait
    bien 413 — après avoir écrit 300 Mo sur le disque du conteneur).
    """

    def test_un_corps_au_dela_du_plafond_est_refuse(self, client: TestClient) -> None:
        reponse = client.post(
            "/api/v1/auth/login",
            content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
            headers={"content-type": "application/json"},
        )
        assert reponse.status_code == 413
        assert reponse.json()["type"].endswith("payload_too_large")

    def test_le_trafic_legitime_passe(self, client: TestClient) -> None:
        """Un plafond qui casse l'usage normal ne serait pas un correctif."""
        reponse = client.post(
            "/api/v1/auth/login",
            json={"email": "personne@exemple.fr", "password": "quelconque"},
        )
        assert reponse.status_code == 401  # identifiants faux, pas 413

    def test_le_plafond_laisse_passer_un_cv_au_maximum(self) -> None:
        """10 Mo est la taille maximale d'un CV : le plafond doit lui laisser
        la place, enveloppe multipart comprise."""
        assert MAX_REQUEST_BODY_BYTES > 10 * 1024 * 1024


class TestLeSchemaNestPasServiEnProduction:
    """73 Ko et 36 routes servis sans authentification, docstrings comprises.

    Elles sont franches sur ce qui n'est pas fini : « scan antivirus hors
    périmètre », « le jeton de session posé est un leurre invalide »,
    « oracle de mot de passe pour quiconque a volé un cookie ». C'est la
    carte des faiblesses connues, offerte à qui la demande.
    """

    @pytest.mark.parametrize("env", ["staging", "production"])
    def test_schema_et_docs_fermes_des_que_lenvironnement_est_durci(
        self, env: str, monkeypatch
    ) -> None:
        """`docs_url` était conditionnée à `is_production`, pas à
        `is_hardened` : Swagger UI était entièrement exposé en **staging**,
        alors que tous les autres garde-fous ont migré vers `is_hardened`."""
        monkeypatch.setenv("ENV", env)
        monkeypatch.setenv("STORAGE_BACKEND", "s3")
        monkeypatch.setenv("S3_SSE", "aws:kms")
        monkeypatch.setenv("PRIVACY_SIGNING_KEY", "k" * 40)
        monkeypatch.setenv("S3_SECRET_KEY", "s" * 40)
        from app.core.config import get_settings

        get_settings.cache_clear()

        client = _app()
        assert client.get("/api/v1/openapi.json").status_code == 404
        assert client.get("/api/v1/docs").status_code == 404
        get_settings.cache_clear()

    def test_en_developpement_le_schema_reste_disponible(
        self, client: TestClient
    ) -> None:
        """Le fermer partout gênerait le développement sans rien protéger."""
        assert client.get("/api/v1/openapi.json").status_code == 200


class TestUnSecretVideNePassePas:
    """Le contrôle ne comparait QUE l'égalité stricte avec le défaut du dépôt.

    Toute autre valeur passait, **y compris la chaîne vide**. Mesuré :
    ``PRIVACY_SIGNING_KEY=`` démarrait en ``ENV=production``, et le pseudonyme
    conservé dans ``audit_log`` après purge devenait recalculable sans aucun
    secret — donc la ré-identification d'une personne supprimée, à partir
    d'une sauvegarde, en testant un UUID candidat.

    Cas réalistes, tous silencieux avant : secret monté mais vide, lecture de
    vault qui échoue, clé absente d'un ``Secret`` Kubernetes.
    """

    def _prod(self, **secrets: str) -> Settings:
        return Settings(
            env="production", storage_backend="s3", s3_sse="aws:kms", **secrets
        )

    @pytest.mark.parametrize(
        "cle,motif",
        [("", "vide"), ("   ", "vide"), ("x", "trop court"), ("changeme", "trop court")],
    )
    def test_une_cle_de_signature_faible_empeche_le_demarrage(
        self, cle: str, motif: str
    ) -> None:
        with pytest.raises(SecretConfigurationError, match="PRIVACY_SIGNING_KEY"):
            check_secrets_configuration(
                self._prod(privacy_signing_key=cle, s3_secret_key="s" * 40)
            )

    def test_une_cle_de_stockage_vide_empeche_le_demarrage(self) -> None:
        with pytest.raises(SecretConfigurationError, match="S3_SECRET_KEY"):
            check_secrets_configuration(
                self._prod(privacy_signing_key="k" * 40, s3_secret_key="")
            )

    def test_des_secrets_corrects_demarrent(self) -> None:
        """La contrepartie : le contrôle ne doit pas bloquer une vraie prod."""
        check_secrets_configuration(
            self._prod(privacy_signing_key="k" * 40, s3_secret_key="s" * 40)
        )

    def test_en_developpement_les_defauts_restent_tolerés(self) -> None:
        check_secrets_configuration(Settings(env="development"))


class TestSmtpEnClairSansAuthentification:
    """La condition portait « ET une authentification est configurée ».

    Or un relais interne sans auth est une configuration courante, et le motif
    du refus — « l'adresse de chaque destinataire transite EN CLAIR » —
    s'applique exactement pareil. Capture socket en revue : sujet « Votre
    demande de suppression de compte » et adresse du destinataire lisibles sur
    le fil, garde-fous passés en ``ENV=production``.
    """

    def _prod(self, **extra: object) -> Settings:
        return Settings(
            env="production",
            storage_backend="s3",
            s3_sse="aws:kms",
            privacy_signing_key="k" * 40,
            s3_secret_key="s" * 40,
            **extra,  # type: ignore[arg-type]
        )

    def test_sans_authentification_le_demarrage_est_refuse(self) -> None:
        from app.core.secrets import check_hardening_configuration

        with pytest.raises(SecretConfigurationError, match="SMTP_STARTTLS"):
            check_hardening_configuration(
                self._prod(smtp_host="relais.interne", smtp_starttls=False)
            )

    def test_avec_starttls_le_demarrage_passe(self) -> None:
        from app.core.secrets import check_hardening_configuration

        check_hardening_configuration(
            self._prod(smtp_host="relais.interne", smtp_starttls=True)
        )


class TestLOrdonnanceurPeutEcrireSonEtat:
    """``celery beat`` sortait en code 1 **immédiatement** dans l'image livrée.

    Le ``PersistentScheduler`` crée son fichier d'état dans le répertoire
    courant ; celui de l'image est ``/srv/boussole``, créé root et non
    inscriptible par l'utilisateur ``boussole`` :

        _dbm.error: [Errno 13] Permission denied: 'celerybeat-schedule'

    Donc boucle de redémarrage, et **rien n'était jamais planifié** —
    ``maintenance.purge_due_accounts`` compris, c'est-à-dire l'engagement RGPD
    des 30 jours. Aucun healthcheck ne couvre ``beat`` : la panne était muette.
    """

    def test_le_fichier_detat_est_hors_du_repertoire_de_travail(self) -> None:
        from app.workers.celery_app import celery_app

        chemin = celery_app.conf.beat_schedule_filename
        assert chemin.startswith("/"), (
            f"{chemin!r} est relatif, donc résolu dans le CWD — c'est le défaut"
        )


class TestUnWorkerPerduRendSonTravail:
    """``acks_late`` seul ne suffit pas.

    Le message n'est rendu à la file qu'au bout du ``visibility_timeout`` de
    kombu-redis, dont le défaut est d'UNE HEURE. Mesuré : worker tué net
    pendant un import de CV, worker neuf relancé, message jamais redélivré
    après 105 s — et le document restait ``parsing``, l'utilisateur devant une
    roue qui tourne.
    """

    def test_le_delai_de_redelivrance_est_borne(self) -> None:
        from app.workers.celery_app import celery_app

        timeout = celery_app.conf.broker_transport_options["visibility_timeout"]
        assert timeout < 3600, "le défaut d'une heure est le défaut constaté"

    def test_le_delai_depasse_la_limite_dure_dune_tache(self) -> None:
        """Sinon le courtier rend le message pendant que la tâche tourne
        encore, et deux workers traitent le même CV."""
        from app.workers.celery_app import celery_app

        assert (
            celery_app.conf.broker_transport_options["visibility_timeout"]
            > celery_app.conf.task_time_limit
        )

    def test_une_tache_ne_retient_pas_son_worker_indefiniment(self) -> None:
        from app.workers.celery_app import celery_app

        assert celery_app.conf.task_time_limit is not None
        assert celery_app.conf.task_soft_time_limit < celery_app.conf.task_time_limit

    def test_un_worker_perdu_ne_fait_pas_attendre(self) -> None:
        from app.workers.celery_app import celery_app

        assert celery_app.conf.task_reject_on_worker_lost is True

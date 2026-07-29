"""Garde-fous de démarrage : worker Celery (C2) et readiness stockage (13).

C2 — Le garde-fou du worker était un **no-op vérifié**. Il était branché sur
``@worker_ready.connect``, or :

- ``celery.utils.dispatch.Signal.send`` attrape toute exception levée par un
  receveur, la journalise et poursuit ;
- ``worker_ready`` est émis APRÈS le début de la consommation de la file.

Un worker en ``ENV=production`` + ``STORAGE_BACKEND=local`` démarrait donc
normalement et écrivait archives d'export et CV sur SON disque — que l'API ne
relit jamais. Le contrôle est désormais au niveau MODULE : l'import échoue.

Le test lance un vrai sous-processus : c'est le seul moyen d'observer ce que
fait ``celery -A app.workers.celery_app worker`` au démarrage, sans polluer
l'état d'import de la session pytest.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.storage import StorageConfigurationError

API_ROOT = Path(__file__).resolve().parents[3]

#: On importe le module ET on émet le signal `worker_ready` : si la garde
#: était (re)devenue un simple receveur de signal, l'import passerait et
#: l'émission ne lèverait pas davantage — Celery avale les exceptions des
#: receveurs. Le test échouerait alors, comme il le doit.
_BOOT_SNIPPET = (
    "import app.workers.celery_app as m\n"
    "from celery.signals import worker_ready\n"
    "worker_ready.send(sender=None)\n"
    "print('WORKER_DEMARRE')\n"
)


def _boot_worker(**env_overrides: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(
        {
            "ENV": "development",
            "STORAGE_BACKEND": "local",
            "PYTHONPATH": str(API_ROOT),
        }
    )
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", _BOOT_SNIPPET],
        cwd=str(API_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestRefusDeDemarrageDuWorker:
    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_le_worker_refuse_de_demarrer_en_stockage_local(self, env: str) -> None:
        result = _boot_worker(ENV=env, STORAGE_BACKEND="local")

        assert result.returncode != 0, (
            "le worker a démarré malgré un stockage local — il écrira les CV et "
            "les archives d'export sur un disque que l'API ne lit jamais"
        )
        assert "WORKER_DEMARRE" not in result.stdout
        assert "StorageConfigurationError" in result.stderr

    def test_le_worker_refuse_de_demarrer_sans_chiffrement_au_repos(self) -> None:
        result = _boot_worker(
            ENV="production", STORAGE_BACKEND="s3", S3_BUCKET="b", S3_SSE="none"
        )

        assert result.returncode != 0
        assert "StorageConfigurationError" in result.stderr

    def test_le_worker_refuse_un_secret_de_developpement(self) -> None:
        """Le stockage peut être irréprochable : un secret par défaut suffit à
        rendre forgeables les liens d'export RGPD (D23)."""
        result = _boot_worker(
            ENV="production", STORAGE_BACKEND="s3", S3_BUCKET="b", S3_SSE="AES256"
        )

        assert result.returncode != 0
        assert "SecretConfigurationError" in result.stderr
        assert "PRIVACY_SIGNING_KEY" in result.stderr

    def test_le_worker_demarre_avec_une_configuration_valide(self) -> None:
        """« Valide » inclut les secrets : stockage chiffré ET secrets fournis."""
        result = _boot_worker(
            ENV="production",
            STORAGE_BACKEND="s3",
            S3_BUCKET="b",
            S3_SSE="AES256",
            PRIVACY_SIGNING_KEY="cle-issue-du-vault-" + "x" * 20,
            S3_SECRET_KEY="secret-s3-issu-du-vault-" + "y" * 20,
        )

        assert result.returncode == 0, result.stderr
        assert "WORKER_DEMARRE" in result.stdout

    def test_le_developpement_local_reste_utilisable(self) -> None:
        result = _boot_worker(ENV="development", STORAGE_BACKEND="local")

        assert result.returncode == 0, result.stderr
        assert "WORKER_DEMARRE" in result.stdout

    def test_la_garde_n_est_plus_un_receveur_de_signal(self) -> None:
        """Contrôle structurel : ``Signal.send`` avale les exceptions de ses
        receveurs — un garde-fou branché là ne peut PAS empêcher un démarrage.
        """
        from celery.signals import worker_ready

        from app.workers import celery_app as module

        assert not hasattr(module, "_check_storage_on_boot")
        noms = {
            getattr(receiver, "__name__", str(receiver))
            for _key, receiver in worker_ready.receivers
        }
        assert not any("storage" in nom for nom in noms), (
            f"garde-fou de stockage rebranché sur worker_ready : {noms}"
        )


class TestReadinessDuStockage:
    """(13) ``/readyz`` ne relisait que la configuration."""

    async def test_readyz_est_rouge_quand_le_bucket_est_injoignable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import main

        def _boom() -> None:
            raise StorageConfigurationError("bucket supprimé")

        monkeypatch.setattr(main, "probe_object_storage", _boom)

        # Régression : configuration valide + backend mort = « ready » vert,
        # pendant que tous les imports de CV et exports RGPD échouaient.
        assert await main._storage_ready() is False

    async def test_readyz_est_rouge_quand_la_sonde_ne_repond_pas(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import time

        from app import main

        monkeypatch.setattr(main, "READYZ_STORAGE_TIMEOUT_SECONDS", 0.05)
        monkeypatch.setattr(main, "probe_object_storage", lambda: time.sleep(5))

        # La sonde est BORNÉE : /readyz ne peut pas rester suspendu sur un
        # stockage qui ne répond plus (les timeouts botocore cumulés peuvent
        # dépasser la minute).
        assert await main._storage_ready() is False

    async def test_readyz_est_vert_quand_le_stockage_repond(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import main

        monkeypatch.setattr(main, "probe_object_storage", lambda: None)

        assert await main._storage_ready() is True

    async def test_la_sonde_reelle_est_bien_appelee(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import main

        appels: list[int] = []
        monkeypatch.setattr(main, "probe_object_storage", lambda: appels.append(1))

        await main._storage_ready()

        assert appels == [1], "/readyz ne sonde toujours que la configuration"

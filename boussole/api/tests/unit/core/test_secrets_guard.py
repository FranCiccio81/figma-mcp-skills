"""Refus de démarrer avec un secret de développement (D23).

Contexte : ``PRIVACY_SIGNING_KEY`` a une valeur par défaut présente dans le
dépôt, donc publique, et elle signe à elle seule les liens de téléchargement
des archives d'export RGPD. Rien ne vérifiait qu'elle avait été changée : un
déploiement pouvait servir en production avec une signature forgeable par
quiconque a lu le code.

Même parti pris que le garde-fou de stockage : on refuse de démarrer. Un
service qui ne démarre pas se voit ; une signature forgeable, non.
"""

import pytest

from app.core.config import get_settings
from app.core.secrets import SecretConfigurationError, check_secrets_configuration


def _settings(**overrides: object):
    base = {"storage_backend": "s3", "s3_bucket": "boussole"}
    return get_settings().model_copy(update={**base, **overrides})


REAL_SECRETS = {
    # ≥ 32 caractères : le garde-fou refuse désormais aussi les secrets
    # trop courts et les secrets VIDES, pas seulement le défaut du dépôt.
    "privacy_signing_key": "cle-issue-du-vault-" + "x" * 20,
    "s3_secret_key": "secret-s3-issu-du-vault-" + "y" * 20,
}


class TestRefusEnProduction:
    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_secret_par_defaut_empeche_le_demarrage(self, env: str) -> None:
        """Le seuil est ``is_hardened`` : staging est couvert comme production
        — un staging accessible avec une signature publique expose de vraies
        données de test, et souvent de vraies données tout court."""
        with pytest.raises(SecretConfigurationError) as excinfo:
            check_secrets_configuration(_settings(env=env))
        assert "PRIVACY_SIGNING_KEY" in str(excinfo.value)

    def test_le_message_dit_ce_qui_est_compromis(self) -> None:
        """Un refus de démarrage doit être actionnable sans lire le code."""
        with pytest.raises(SecretConfigurationError) as excinfo:
            check_secrets_configuration(_settings(env="production"))
        message = str(excinfo.value)
        assert "audit_log" in message
        assert "vault" in message

    def test_secrets_fournis_autorisent_le_demarrage(self) -> None:
        check_secrets_configuration(_settings(env="production", **REAL_SECRETS))

    def test_un_seul_secret_change_ne_suffit_pas(self) -> None:
        """Changer la clé de signature sans changer celle du stockage laisse
        les identifiants du bucket (CV, archives) publics."""
        with pytest.raises(SecretConfigurationError) as excinfo:
            check_secrets_configuration(
                _settings(env="production", privacy_signing_key="v" * 40)
            )
        assert "S3_SECRET_KEY" in str(excinfo.value)


class TestDeveloppement:
    def test_les_defauts_sont_legitimes_en_developpement(self) -> None:
        """C'est le mode où ces valeurs existent — pas de blocage, le
        démarrage local doit rester sans friction."""
        check_secrets_configuration(_settings(env="development"))


class TestSourceDeVerite:
    def test_les_defauts_sont_lus_sur_le_modele_pas_recopies(self) -> None:
        """Une rotation de la valeur de développement ne doit pas désarmer
        silencieusement le contrôle : les défauts viennent de ``Settings``.

        Si les valeurs étaient recopiées dans ``secrets.py``, changer le
        défaut ici laisserait passer l'ancienne valeur en production.
        """
        from app.core.config import Settings

        defaut = Settings.model_fields["privacy_signing_key"].default
        with pytest.raises(SecretConfigurationError):
            check_secrets_configuration(
                _settings(env="production", privacy_signing_key=defaut, **{
                    "s3_secret_key": REAL_SECRETS["s3_secret_key"]
                })
            )

"""Refus de démarrer sur une configuration qui expose des données (D42).

Deux réglages, deux fuites mesurées en revue :

- ``SMTP_STARTTLS=false`` avec authentification : le mot de passe du compte
  d'envoi et l'adresse de chaque destinataire transitent en clair. Qui a ce
  mot de passe peut écrire au nom du service — à une base d'utilisateurs qui
  attendent précisément des messages sur la suppression de leur compte ;
- ``DEBUG=true`` : SQLAlchemy journalise chaque requête AVEC ses paramètres
  liés. Contenus de profil, adresses, extraits de CV se retrouvent dans les
  journaux, et de là dans tout export d'erreurs.

Même parti pris que les garde-fous de stockage et de secrets : un service qui
ne démarre pas se voit ; une fuite, non.
"""

import pytest

from app.core.config import get_settings
from app.core.secrets import SecretConfigurationError, check_hardening_configuration


def _settings(**overrides: object):
    return get_settings().model_copy(update=overrides)


class TestSmtpEnClair:
    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_authentification_sans_starttls_empeche_le_demarrage(self, env: str) -> None:
        with pytest.raises(SecretConfigurationError) as excinfo:
            check_hardening_configuration(
                _settings(
                    env=env, smtp_host="smtp.exemple.eu", smtp_username="boussole",
                    smtp_password="secret", smtp_starttls=False,
                )
            )
        assert "EN CLAIR" in str(excinfo.value)

    def test_starttls_actif_autorise_le_demarrage(self) -> None:
        check_hardening_configuration(
            _settings(
                env="production", smtp_host="smtp.exemple.eu", smtp_username="boussole",
                smtp_password="secret", smtp_starttls=True,
            )
        )

    def test_sans_authentification_le_controle_ne_sapplique_pas(self) -> None:
        """Un relais interne sans mot de passe n'expose pas d'identifiant.
        Le contenu reste en clair, mais ce n'est pas ce contrôle-ci."""
        check_hardening_configuration(
            _settings(env="production", smtp_host="relais.interne", smtp_username="")
        )


class TestDebugEnProduction:
    def test_debug_actif_empeche_le_demarrage(self) -> None:
        """``create_async_engine(echo=debug)`` journalise les paramètres liés."""
        with pytest.raises(SecretConfigurationError) as excinfo:
            check_hardening_configuration(_settings(env="production", debug=True))
        message = str(excinfo.value)
        assert "DEBUG=true" in message
        assert "paramètres liés" in message

    def test_les_deux_manquements_sont_signales_ensemble(self) -> None:
        """Corriger l'un pour découvrir l'autre au redémarrage suivant serait
        une perte de temps évitable."""
        with pytest.raises(SecretConfigurationError) as excinfo:
            check_hardening_configuration(
                _settings(
                    env="production", debug=True, smtp_host="smtp.exemple.eu",
                    smtp_username="u", smtp_password="p", smtp_starttls=False,
                )
            )
        message = str(excinfo.value)
        assert "DEBUG=true" in message and "EN CLAIR" in message


class TestDeveloppement:
    def test_aucun_controle_en_developpement(self) -> None:
        """mailpit n'a ni TLS ni authentification, et DEBUG y est utile."""
        check_hardening_configuration(
            _settings(env="development", debug=True, smtp_host="mailpit",
                      smtp_username="u", smtp_password="p", smtp_starttls=False)
        )

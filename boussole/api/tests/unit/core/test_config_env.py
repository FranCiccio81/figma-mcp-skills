"""Vocabulaire fermé de ``ENV`` (M5) — le contournement par une chaîne.

``Settings.env`` était un ``str`` libre et ``is_production`` une égalité
exacte. Toute valeur qui n'était pas *exactement* ``"production"`` — ``prod``,
``Production``, ``PRODUCTION``, ``"production "`` — désactivait donc, en
silence et d'un seul coup :

- le refus de démarrer avec ``STORAGE_BACKEND=local`` (exports RGPD perdus) ;
- l'exigence de chiffrement au repos (``S3_SSE``, D09 §5.6) ;
- le masquage des docs OpenAPI (``docs_url``) ;
- la garde D22 des seeds (``app/seeds.py``).

Et ``staging`` — un environnement pourtant multi-conteneurs — n'était couvert
par AUCUN de ces contrôles, puisqu'il n'était pas ``production``.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


class TestVocabulaireFerme:
    @pytest.mark.parametrize("env", ["development", "staging", "production"])
    def test_les_trois_environnements_normatifs_sont_acceptes(self, env: str) -> None:
        assert _settings(env=env).env == env

    @pytest.mark.parametrize(
        "env", ["prod", "dev", "preprod", "prd", "productionn", "", "local"]
    )
    def test_toute_autre_valeur_fait_echouer_le_demarrage(self, env: str) -> None:
        # Refuser de démarrer > démarrer avec tous les garde-fous désactivés.
        with pytest.raises(ValidationError):
            _settings(env=env)

    @pytest.mark.parametrize(
        "brut", ["Production", "PRODUCTION", " production ", "\tProduction\n"]
    )
    def test_la_casse_et_les_espaces_sont_normalises(self, brut: str) -> None:
        # 🟡 Tolérance délibérée et bornée : elle ne change pas le SENS de la
        # valeur (copier-coller, indentation YAML). Elle ne s'étend pas aux
        # alias : `prod` reste refusé (test ci-dessus).
        settings = _settings(env=brut)

        assert settings.env == "production"
        assert settings.is_production is True

    def test_l_environnement_se_lit_depuis_la_variable_d_environnement(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENV", "STAGING")
        assert Settings(_env_file=None).env == "staging"

        monkeypatch.setenv("ENV", "prod")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


class TestSeuilDeDurcissement:
    """``is_hardened`` : tout ce qui n'est pas ``development``."""

    @pytest.mark.parametrize(
        ("env", "hardened", "production"),
        [
            ("development", False, False),
            ("staging", True, False),
            ("production", True, True),
        ],
    )
    def test_staging_est_durci_sans_etre_la_production(
        self, env: str, hardened: bool, production: bool
    ) -> None:
        settings = _settings(env=env)

        # Les contrôles de stockage/chiffrement s'appuient sur `is_hardened` :
        # `staging` était auparavant traité exactement comme un poste de dev.
        assert settings.is_hardened is hardened
        # `is_production` reste distinct (docs OpenAPI, garde D22 des seeds).
        assert settings.is_production is production

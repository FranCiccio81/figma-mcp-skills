"""Export d'erreurs : refus bruyant, et barrière de confidentialité.

Ce qui est corrigé : ``SENTRY_DSN`` était déclarée et lue par personne. Le
système émet pourtant ``purge_backlog_detected`` quand une purge RGPD est en
retard — un engagement légal en train d'être rompu — et cette alerte partait
sur stdout, au milieu du reste.

Deux propriétés sont testées, parce que ce sont les deux façons de rater
cette fonctionnalité : croire être observé quand on ne l'est pas, et
exfiltrer des données personnelles en croyant bien faire.

``OTEL_EXPORTER_OTLP_ENDPOINT`` a été **retirée** de la configuration : elle
était déclarée et inerte. Une variable qui ne fait rien induit en erreur plus
sûrement qu'une variable absente — c'est aussi vérifié ici.
"""

import pytest

from app.core.config import Settings, get_settings
from app.core.observability import (
    ObservabilityConfigurationError,
    configure_observability,
    scrub_event,
)


def _settings(**overrides: object) -> Settings:
    return get_settings().model_copy(update=overrides)


class TestRefusBruyant:
    def test_un_dsn_sans_le_paquet_fait_echouer_le_demarrage(self) -> None:
        """Se croire observé est pire que ne pas l'être : on ne regarde plus.

        Le paquet ``sentry-sdk`` est un extra optionnel et n'est pas installé
        dans l'environnement de test — ce test vérifie donc le cas réel d'un
        déploiement où l'on a renseigné le DSN sans installer l'extra.
        """
        try:
            import sentry_sdk  # noqa: F401
        except ImportError:
            with pytest.raises(ObservabilityConfigurationError) as excinfo:
                configure_observability(_settings(sentry_dsn="https://x@sentry.invalid/1"))
            message = str(excinfo.value)
            assert "sentry-sdk" in message
            assert "observability" in message  # la commande pour s'en sortir
        else:  # pragma: no cover - dépend de l'environnement
            assert configure_observability(
                _settings(sentry_dsn="https://x@sentry.invalid/1")
            )

    def test_sans_dsn_lapplication_demarre_normalement(self) -> None:
        assert configure_observability(_settings(sentry_dsn="")) is False

    def test_un_dsn_despaces_vaut_absence(self) -> None:
        assert configure_observability(_settings(sentry_dsn="   ")) is False


class TestLaVariableInerteAEteRetiree:
    def test_otel_nest_plus_declaree(self) -> None:
        """Elle promettait un export de traces qui n'existait pas."""
        assert "otel_exporter_otlp_endpoint" not in Settings.model_fields


class TestBarriereDeConfidentialite:
    """Ce produit manipule des CV. Un rapport d'erreur mal réglé les exfiltre.

    ``scrub_event`` est volontairement une fonction pure sur un dictionnaire :
    la barrière est vérifiable **sans** le paquet Sentry installé. Faire
    dépendre un contrôle de confidentialité d'une dépendance optionnelle
    reviendrait à ne pas le tester du tout dans la CI.
    """

    def test_le_corps_de_requete_est_retire(self) -> None:
        """Il peut contenir un CV entier, une lettre, un profil."""
        evenement = {"request": {"data": {"cv": "Camille Martin, 12 rue…"}}}
        assert "data" not in (scrub_event(evenement) or {})["request"]

    def test_les_cookies_sont_retires(self) -> None:
        evenement = {"request": {"cookies": {"boussole_session": "abc"}}}
        assert "cookies" not in (scrub_event(evenement) or {})["request"]

    @pytest.mark.parametrize(
        "entete", ["Cookie", "authorization", "X-CSRF-Token", "Set-Cookie"]
    )
    def test_les_entetes_didentite_sont_retires(self, entete: str) -> None:
        """Une session volée dans un rapport d'erreur est une session volée."""
        evenement = {"request": {"headers": {entete: "secret", "User-Agent": "curl"}}}
        entetes = (scrub_event(evenement) or {})["request"]["headers"]
        assert entete not in entetes
        assert entetes["User-Agent"] == "curl"

    def test_les_variables_locales_des_piles_sont_retirees(self) -> None:
        """Elles contiennent volontiers le texte en cours de traitement."""
        evenement = {
            "exception": {
                "values": [
                    {"stacktrace": {"frames": [{"vars": {"texte_cv": "…"}, "lineno": 12}]}}
                ]
            }
        }
        frame = (scrub_event(evenement) or {})["exception"]["values"][0]["stacktrace"][
            "frames"
        ][0]
        assert "vars" not in frame
        assert frame["lineno"] == 12

    def test_un_evenement_sans_requete_passe_sans_erreur(self) -> None:
        assert scrub_event({"message": "purge_backlog_detected"}) is not None

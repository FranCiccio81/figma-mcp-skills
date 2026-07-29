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
    """Liste BLANCHE : on garde ce qu'on sait sûr, on jette le reste.

    Ce produit manipule des CV et des requêtes de recherche d'emploi. Sentry
    est un sous-traitant tiers : tout ce qui part est un transfert.

    La première version nettoyait trois champs. Une revue, en exécutant le
    VRAI SDK, a montré que l'adresse d'un utilisateur et le sujet « demande
    de suppression de compte » partaient quand même — par les fils d'Ariane
    construits depuis les logs INFO — et que huit autres chemins portaient des
    données. Énumérer ce qu'on retire est une course perdue : chaque nouveau
    champ du SDK, chaque nouveau ``extra`` ajouté par un développeur, passe à
    travers. Énumérer ce qu'on garde échoue du côté d'un rapport plus pauvre.

    ``scrub_event`` est volontairement une fonction pure sur un dictionnaire :
    la barrière est vérifiable **sans** le paquet Sentry installé. Faire
    dépendre un contrôle de confidentialité d'une dépendance optionnelle
    reviendrait à ne pas le tester du tout en CI.
    """

    def _evenement_charge(self) -> dict:
        """Un événement portant TOUTES les formes de fuite constatées."""
        return {
            "event_id": "abc", "level": "error", "logger": "boussole.mail",
            "message": "echec extraction CV de jean.dupont@exemple-prive.fr",
            "logentry": {
                "message": "mail_envoi_echoue destinataire=%s sujet=%r",
                "formatted": "mail_envoi_echoue destinataire=jean.dupont@exemple-prive.fr",
                "params": ["jean.dupont@exemple-prive.fr", "Suppression de compte"],
            },
            "breadcrumbs": {
                "values": [{"message": "mail_envoye destinataire=jean.dupont@exemple-prive.fr"}]
            },
            "extra": {"cv_text": "Jean DUPONT — 12 rue…", "key": "exports/cv-jean-dupont.json"},
            "contexts": {
                "runtime": {"name": "CPython"},
                "profil": {"telephone": "+33 6 12 34 56 78"},
            },
            "tags": {"user_email": "jean.dupont@exemple-prive.fr"},
            "user": {"email": "jean.dupont@exemple-prive.fr", "ip_address": "88.120.4.7"},
            "request": {
                "method": "GET", "url": "http://x/api/v1/jobs",
                "query_string": "q=depression%20amiante&lat=48.85",
                "cookies": {"boussole_session": "abc"},
                "data": {"cv": "Jean DUPONT…"},
                "headers": {"Cookie": "s", "X-Forwarded-For": "88.120.4.7", "User-Agent": "curl"},
            },
            "exception": {
                "values": [{"stacktrace": {"frames": [{"vars": {"cv": "…"}, "lineno": 3}]}}]
            },
        }

    @pytest.mark.parametrize(
        ("aiguille", "quoi"),
        [
            ("jean.dupont@exemple-prive.fr", "adresse e-mail"),
            ("depression", "requête de recherche d'emploi"),
            ("88.120.4.7", "adresse IP"),
            ("Jean DUPONT", "contenu de CV"),
            ("+33 6", "numéro de téléphone"),
            ("cv-jean-dupont", "nom de fichier d'export"),
            ("Suppression de compte", "sujet révélant une demande de suppression"),
        ],
    )
    def test_aucune_donnee_personnelle_ne_survit(self, aiguille: str, quoi: str) -> None:
        import json

        propre = scrub_event(self._evenement_charge())
        assert aiguille not in json.dumps(propre, ensure_ascii=False), quoi

    def test_la_requete_de_recherche_demploi_ne_sort_pas(self) -> None:
        """Le piège le plus discret : ``q`` sur ``GET /jobs`` peut révéler une
        santé, un handicap, une reconversion après un burn-out."""
        propre = scrub_event(self._evenement_charge()) or {}
        assert "query_string" not in propre["request"]

    def test_le_gabarit_de_journal_reste_pour_diagnostiquer(self) -> None:
        """On garde la FORME, on jette les valeurs : sans le gabarit, un
        rapport d'erreur ne sert plus à rien."""
        propre = scrub_event(self._evenement_charge()) or {}
        assert propre["logentry"] == {"message": "mail_envoi_echoue destinataire=%s sujet=%r"}

    def test_la_route_et_la_methode_restent(self) -> None:
        propre = scrub_event(self._evenement_charge()) or {}
        assert propre["request"]["method"] == "GET"
        assert propre["request"]["url"].endswith("/api/v1/jobs")

    def test_un_champ_inconnu_est_jete_par_defaut(self) -> None:
        """LE point de la liste blanche : ce qu'on n'a pas prévu ne passe pas.

        Un ``extra`` ajouté demain par un développeur pressé n'a pas besoin
        d'être connu de ce module pour être retenu.
        """
        propre = scrub_event({"event_id": "x", "champ_invente_demain": "secret"}) or {}
        assert "champ_invente_demain" not in propre

    def test_les_contextes_techniques_du_sdk_sont_conserves(self) -> None:
        propre = scrub_event(self._evenement_charge()) or {}
        assert "runtime" in propre["contexts"]
        assert "profil" not in propre["contexts"]

    def test_les_variables_locales_des_piles_sont_retirees(self) -> None:
        propre = scrub_event(self._evenement_charge()) or {}
        frame = propre["exception"]["values"][0]["stacktrace"]["frames"][0]
        assert "vars" not in frame
        assert frame["lineno"] == 3

    def test_un_evenement_sans_requete_passe_sans_erreur(self) -> None:
        assert scrub_event({"message": "purge_backlog_detected"}) is not None


class TestAucunFilDArianeIssuDesJournaux:
    """La fuite d'origine venait de là, pas de ``before_send``.

    ``LoggingIntegration(level=INFO)`` transformait chaque log INFO en fil
    d'Ariane, rattaché ensuite à n'importe quelle erreur ultérieure du même
    processus — et cette partie de l'enveloppe n'était pas nettoyée. Un
    ``logger.info("mail_envoye destinataire=%s", ...)`` suffisait.
    """

    def test_le_module_desactive_les_fils_dariane_de_journaux(self) -> None:
        import inspect

        from app.core import observability

        source = inspect.getsource(observability.configure_observability)
        assert "level=None" in source, (
            "les fils d'Ariane issus des journaux sont réactivés — c'est par là "
            "que l'adresse des utilisateurs partait vers Sentry"
        )
        assert "event_level=logging.ERROR" in source, (
            "sans event_level=ERROR, les alertes de conformité n'atteignent "
            "plus personne"
        )
        assert "max_breadcrumbs=0" in source

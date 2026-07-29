"""Aucune donnée personnelle ne sort par un canal de diagnostic.

Défaut trouvé en revue finale. Le nettoyeur Sentry retire explicitement
``request.query_string`` parce qu'une requête de recherche d'emploi « peut
révéler une santé ou une reconversion ». Trois canaux la contournaient, ou
laissaient passer autre chose. Mesuré avant correctif :

    A. journal d'accès uvicorn   ?q=teletravail+apres+burn-out   → écrit
                                  ?sig=<HMAC de l'export>        → écrit
    B. exception.values[].value   SMTPRecipientsRefused          → adresse
    C. idem + exc_info local      DETAIL: Key (email)=(…)        → adresse

Le canal A n'est pas seulement une affaire de vie privée : ``sig`` est la
signature du lien de téléchargement de l'export RGPD, valable sept jours.
Qui lit le journal retélécharge l'archive complète d'une personne.

Les canaux B et C ne demandent aucune imprudence de notre part : c'est
PostgreSQL qui compose le ``DETAIL:``, SQLAlchemy qui ajoute
``[parameters:]``, et ``smtplib`` qui met les destinataires dans le message.
Il suffisait d'une inscription en collision ou d'un rebond d'e-mail.

Ce fichier vérifie les deux sens : ce qui ne doit plus sortir, et ce qui doit
continuer de sortir — un nettoyeur qui vide les rapports d'erreur se fait
désactiver au premier incident qu'on n'arrive pas à diagnostiquer.
"""

import json
import logging
import smtplib

import pytest

from app.core.observability import scrub_event
from app.core.redaction import (
    redact,
    redact_message,
    redact_traceback,
    strip_query,
)
from app.main import JsonLogFormatter, StripQueryStringFilter, configure_logging

ADRESSE = "camille.durand@exemple.fr"
SIGNATURE = "9f3ac1e0b7d2445a8c1e9f3ac1e0b7d2445a8c1e9f3ac1e0b7d2445a8c1e9f3a"

#: Message réel d'une inscription en collision, tel que SQLAlchemy le compose
#: au-dessus d'asyncpg. Les trois lignes portent l'adresse.
COLLISION_UNICITE = (
    'duplicate key value violates unique constraint "users_email_key"\n'
    f"DETAIL:  Key (email)=({ADRESSE}) already exists.\n"
    f"[parameters: {{'email': '{ADRESSE}', 'password_hash': '$argon2id$v=19$m=65536'}}]"
)


def _evenement_exception(valeur: str) -> dict:
    return {"exception": {"values": [{"type": "X", "value": valeur}]}}


def _sortie(evenement: dict) -> str:
    return json.dumps(scrub_event(evenement), ensure_ascii=False)


class TestLeMessageDeLexceptionNeSortPlusEntier:
    """C'était l'angle mort de la liste blanche : elle gardait ``exception``,
    donc le message, donc ce que le pilote y avait mis."""

    def test_un_rebond_demail_nemporte_pas_ladresse(self) -> None:
        try:
            raise smtplib.SMTPRecipientsRefused({ADRESSE: (550, b"5.1.1 unknown")})
        except smtplib.SMTPRecipientsRefused as exc:
            valeur = str(exc)
        assert ADRESSE in valeur, "prémisse : smtplib met bien l'adresse dans le message"

        assert ADRESSE not in _sortie(_evenement_exception(valeur))

    def test_une_collision_dunicite_nemporte_ni_adresse_ni_parametres(self) -> None:
        sortie = _sortie(_evenement_exception(COLLISION_UNICITE))
        assert ADRESSE not in sortie
        assert "argon2id" not in sortie, "les paramètres liés portent le hachage"
        assert "users_email_key" in sortie, "le nom de la contrainte reste diagnostique"

    @pytest.mark.parametrize("section", ["DETAIL:", "HINT:", "[SQL:", "[parameters:"])
    def test_les_sections_composees_par_la_base_sont_coupees(self, section: str) -> None:
        """Ces sections contiennent la ligne concernée par construction :
        aucune reconnaissance de forme ne saurait les filtrer, on les coupe."""
        message = f"erreur\n{section} valeur-sensible-quelconque"
        assert "valeur-sensible" not in str(redact_message(message))

    def test_les_variables_locales_des_cadres_partent_toujours(self) -> None:
        """Propriété préexistante — vérifiée ici pour qu'elle ne se perde pas
        en modifiant ``_scrub_exception``."""
        evenement = {
            "exception": {
                "values": [
                    {
                        "type": "X",
                        "value": "erreur",
                        "stacktrace": {"frames": [{"vars": {"cv": "texte du CV"}}]},
                    }
                ]
            }
        }
        assert "texte du CV" not in _sortie(evenement)


class TestLeJournalDaccesUvicornNecritPlusLaRequete:
    """Uvicorn tourne avec son journal d'accès actif et écrit le chemin BRUT.
    La barrière existait côté sous-traitant tiers et pas côté nos journaux,
    qui sont pourtant conservés plus longtemps."""

    @staticmethod
    def _ligne(chemin: str) -> str:
        record = logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            __file__,
            1,
            '%s - "%s %s HTTP/%s" %d',
            ("10.0.0.4:52341", "GET", chemin, "1.1", 200),
            None,
        )
        assert StripQueryStringFilter().filter(record) is True
        return record.getMessage()

    def test_la_recherche_demploi_ne_sinscrit_pas(self) -> None:
        ligne = self._ligne("/api/v1/jobs?q=teletravail+apres+burn-out")
        assert "burn-out" not in ligne
        assert "/api/v1/jobs" in ligne, "la route reste — c'est l'intérêt du journal"

    def test_la_signature_du_lien_dexport_ne_sinscrit_pas(self) -> None:
        """``sig`` autorise le téléchargement de l'archive RGPD complète
        pendant sept jours. Ce n'est pas de la vie privée, c'est un secret
        d'authentification."""
        ligne = self._ligne(f"/api/v1/privacy/exports/abc/download?expires=1&sig={SIGNATURE}")
        assert SIGNATURE not in ligne

    def test_le_pair_la_methode_et_le_statut_restent(self) -> None:
        ligne = self._ligne("/api/v1/jobs?q=x")
        assert "10.0.0.4:52341" in ligne and "GET" in ligne and "200" in ligne

    def test_un_enregistrement_de_forme_inattendue_passe_intact(self) -> None:
        """Le filtre ne doit jamais faire disparaître une ligne : uvicorn peut
        changer son gabarit, un journal muet serait pire que bavard."""
        record = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1, "message simple", (), None
        )
        assert StripQueryStringFilter().filter(record) is True
        assert record.getMessage() == "message simple"

    def test_le_filtre_est_pose_par_configure_logging(self) -> None:
        """Posé dans le code et non par un drapeau de ligne de commande :
        un ``--no-access-log`` revient au premier changement d'image de base,
        sans qu'aucun test ne puisse le voir."""
        acces = logging.getLogger("uvicorn.access")
        acces.filters = [f for f in acces.filters if not isinstance(f, StripQueryStringFilter)]

        configure_logging()
        assert any(isinstance(f, StripQueryStringFilter) for f in acces.filters)

        configure_logging()  # idempotent : pas d'empilement à chaque create_app
        assert sum(isinstance(f, StripQueryStringFilter) for f in acces.filters) == 1


class TestLeJournalLocalNeConserveNiAdresseNiSecret:
    """Un journal local part chez un agrégateur : c'est une conservation,
    pas un affichage."""

    def test_la_pile_est_nettoyee(self) -> None:
        record = logging.LogRecord(
            "app", logging.ERROR, __file__, 1, "unhandled_error", (), None
        )
        try:
            raise RuntimeError(COLLISION_UNICITE)
        except RuntimeError:
            import sys

            record.exc_info = sys.exc_info()

        ligne = JsonLogFormatter().format(record)
        assert ADRESSE not in ligne
        assert "argon2id" not in ligne
        assert "Traceback" in ligne, "les cadres restent — c'est ce qui diagnostique"
        assert "RuntimeError" in ligne

    def test_une_ligne_sans_exception_reste_inchangee(self) -> None:
        record = logging.LogRecord(
            "app", logging.INFO, __file__, 1, "http_request", (), None
        )
        assert json.loads(JsonLogFormatter().format(record))["message"] == "http_request"


class TestLurlEtLeGabaritPassentAussiParLeNettoyage:
    def test_la_requete_est_coupee_de_lurl(self) -> None:
        """Selon l'intégration et la version du SDK, ``request.url`` arrive
        complet. On ne dépend pas de la version installée."""
        evenement = {"request": {"method": "GET", "url": "https://x/jobs?q=burn-out"}}
        assert "burn-out" not in _sortie(evenement)

    def test_un_gabarit_imprudent_est_nettoye(self) -> None:
        """Une barrière qui suppose la discipline de l'appelant n'en est pas
        une : rien n'empêche d'écrire ``logger.error(f"echec {adresse}")``."""
        evenement = {"logentry": {"message": f"mail_envoi_echoue destinataire={ADRESSE}"}}
        sortie = _sortie(evenement)
        assert ADRESSE not in sortie
        assert "mail_envoi_echoue" in sortie


class TestCeQuiDoitContinuerDeSortir:
    """La contrepartie. Un nettoyeur qui vide les rapports d'erreur se fait
    désactiver au premier incident qu'on n'arrive pas à diagnostiquer."""

    @pytest.mark.parametrize(
        "message",
        [
            "expected 3 columns, got 5",
            "connection refused to redis:6379",
            'null value in column "status" violates not-null constraint',
            "division by zero",
        ],
    )
    def test_un_message_technique_survit_intact(self, message: str) -> None:
        assert redact_message(message) == message

    def test_un_identifiant_python_long_nest_pas_pris_pour_un_secret(self) -> None:
        """Le motif d'un jeton ``token_urlsafe`` attraperait aussi les noms en
        snake_case, qui dépassent volontiers 40 caractères dans une pile. La
        casse mixte tranche."""
        nom = "test_une_rafale_sur_des_adresses_prises_laisse_une_trace"
        assert len(nom) > 40 and redact(nom) == nom

    def test_un_jeton_de_session_est_bien_pris_pour_un_secret(self) -> None:
        import secrets

        jeton = secrets.token_urlsafe(32)
        assert redact(f"session={jeton}") == "session=[secret]"

    def test_une_empreinte_hmac_est_prise_pour_un_secret(self) -> None:
        assert redact(SIGNATURE) == "[secret]"

    def test_un_message_demesure_est_borne(self) -> None:
        """Un message qui embarque un CV est long par construction."""
        assert len(str(redact_message("x" * 5000))) < 600

    def test_une_pile_garde_ses_cadres(self) -> None:
        pile = 'Traceback (most recent call last):\n  File "a.py", line 3\nValueError: x'
        assert redact_traceback(pile) == pile


class TestLesFonctionsSontTotales:
    """Appelées dans un chemin d'erreur : elles ne doivent jamais lever."""

    @pytest.mark.parametrize("valeur", [None, ""])
    def test_une_valeur_vide_est_rendue_telle_quelle(self, valeur: str | None) -> None:
        assert redact_message(valeur) == valeur
        assert strip_query(valeur) == valeur

    def test_un_chemin_sans_requete_est_inchange(self) -> None:
        assert strip_query("/api/v1/jobs") == "/api/v1/jobs"

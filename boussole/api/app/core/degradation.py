"""Ce qui se passe quand le Redis volatile tombe — dit à un seul endroit.

**Ce que ça corrige.** D17 pose que la perte du Redis « cache » est
acceptable : il ne porte que du cache, du rate limiting et des quotas, rien
de durable. Quatre points d'appel en tiraient trois conclusions différentes,
chacune écrite indépendamment et défendable seule :

===========================  ==========================================
limiteur global (D18)        laisse passer, ``logger.warning``
limiteur de connexion        laisse passer, ``logger.warning``
quota d'explications         laisse passer, ``logger.warning``
quota de génération          **aucune garde** → 500 sur chaque appel
===========================  ==========================================

Et une cinquième décision les annulait toutes : ``/readyz`` comptait
``redis_cache`` parmi ses dépendances obligatoires. Sous un orchestrateur,
une sonde de readiness en échec retire l'instance du service. Une panne de
cache ne dégradait donc pas le service — **elle le coupait entièrement**,
sur toutes les instances à la fois, ce qui est très exactement la panne
totale que le fail-open du limiteur de connexion existe pour éviter. Le
commentaire de ce fail-open dit « une panne de cache ne doit pas devenir une
panne d'authentification » ; la sonde en faisait une panne de tout.

**Les deux règles retenues.**

1. *Une dégradation n'est pas une indisponibilité.* ``/readyz`` ne juge que
   ce sans quoi l'application ne peut pas servir correctement — la base, le
   Redis persistant (sessions et broker), le stockage. Le cache est reporté
   comme dégradé, l'instance reste en service.

2. *Une protection qui s'efface doit se voir.* Chaque garde journalisait en
   ``WARNING``, et l'intégration Sentry ne crée d'événement qu'à partir de
   ``ERROR`` : le système pouvait tourner des heures sans aucune limitation
   de débit ni quota, sans que personne l'apprenne. ``signal_degradation``
   journalise en ``ERROR`` — donc remonté — mais **au plus une fois par
   minute et par processus** : pendant une panne, une alerte est un signal,
   mille sont un déni de service contre l'exploitant.

**Ce qui reste volontairement différent.** Le quota de génération ne laisse
PAS passer (voir ``_enforce_quotas``) : les autres gardes protègent la
disponibilité, celle-là protège une dépense réelle chez un fournisseur de
LLM. Laisser passer pendant une panne, c'est un plafond de coût qui
disparaît. Ce point-là échoue donc fermé — mais proprement, par un 503
explicite au lieu du 500 accidentel qu'il rendait.
"""

import logging
import time

logger = logging.getLogger("boussole.degradation")

#: Intervalle minimal entre deux signalements d'une même dégradation.
INTERVALLE_SECONDES = 60.0

#: Dernier signalement par nom. Par processus : chaque instance signale la
#: sienne, ce qui est l'information utile (« combien d'instances touchées »).
_dernier: dict[str, float] = {}


def signal_degradation(nom: str, *, detail: str = "") -> bool:
    """Signale une protection tombée. ``True`` si la ligne a été émise.

    ``ERROR`` et non ``WARNING`` : c'est le niveau que l'export d'erreurs
    remonte (``event_level=ERROR``, voir ``app/core/observability.py``). Une
    protection désactivée qui ne réveille personne n'est pas une dégradation,
    c'est un angle mort.
    """
    maintenant = time.monotonic()
    precedent = _dernier.get(nom)
    if precedent is not None and maintenant - precedent < INTERVALLE_SECONDES:
        return False
    _dernier[nom] = maintenant
    logger.error(
        "degradation_active protection=%s detail=%s "
        "(prochain signalement dans %ds au plus tôt)",
        nom,
        detail or "-",
        int(INTERVALLE_SECONDES),
    )
    return True


def reset_degradations() -> None:
    """Vide l'état d'étouffement — pour les tests uniquement."""
    _dernier.clear()

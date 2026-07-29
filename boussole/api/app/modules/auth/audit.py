"""Journal d'authentification (09 §5.7).

**Ce que ça corrige.** 09 §5.7 liste les événements à journaliser :
« inscription, **login (succès/échec)**, logout, … ». Aucun n'était écrit.
Mesuré en revue finale, après 700+ échecs de connexion et une trentaine
d'inscriptions contre l'API réelle :

    select action, count(*) from audit_log group by action;
     data_export_downloaded|2   privacy_export_requested|2
     privacy_export_ready|2     account_deletion_requested|1
     account_purge_completed|1

Zéro ligne d'authentification. Deux conséquences, et la seconde est pire que
la première :

1. le modèle de menace (09 §3) promet une « alerte sur pics d'échecs » — il
   n'y avait rien à alerter, et l'attaque par force brute mesurée dans la
   même revue (500 tentatives, 0 rejet) serait passée sans laisser de trace ;
2. la justification écrite du fail-open du limiteur de connexion disait « le
   mot de passe reste haché, **l'audit reste écrit** ». Il ne l'était pas :
   un arbitrage de sécurité reposait sur une compensation inexistante.

**Ce qui est écrit, et ce qui ne l'est pas.** L'IP est tronquée (/24 en IPv4,
/48 en IPv6) : elle sert à repérer une rafale, pas à suivre une personne. Le
user-agent est conservé tel quel — il n'identifie pas à lui seul et il
distingue un navigateur d'un script. **L'adresse e-mail tentée n'est jamais
écrite** : sur un échec, elle appartient souvent à quelqu'un qui n'a pas de
compte ici, et la conserver ferait de ce journal une base d'adresses. La
corrélation par compte passe par ``user_id`` quand le compte existe.

Comme toute ligne d'``audit_log``, celles-ci sont anonymisées à la purge
(``user_id`` → NULL, ``subject_key`` = HMAC irréversible — RM-Q-2).
"""

import ipaddress
import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

#: Actions du journal. Nommées au passé : ce sont des faits, pas des ordres.
REGISTERED = "auth_registered"
LOGIN_SUCCEEDED = "auth_login_succeeded"
LOGIN_FAILED = "auth_login_failed"
LOGGED_OUT = "auth_logged_out"

#: Masques de troncature. /24 et /48 sont les granularités usuelles d'un
#: journal de sécurité respectueux : assez fines pour voir une rafale venir
#: d'un même réseau, trop grossières pour désigner un abonné.
_IPV4_PREFIX = 24
_IPV6_PREFIX = 48


def truncate_ip(raw: str | None) -> str | None:
    """Réseau d'origine plutôt qu'adresse exacte — ``None`` si illisible.

    Une IP complète est une donnée personnelle qu'on n'a pas besoin de
    conserver pour détecter un pic d'échecs. Le réseau suffit.
    """
    if not raw:
        return None
    try:
        adresse = ipaddress.ip_address(raw.strip())
    except ValueError:
        return None
    prefixe = _IPV4_PREFIX if adresse.version == 4 else _IPV6_PREFIX
    reseau = ipaddress.ip_network(f"{adresse}/{prefixe}", strict=False)
    return str(reseau)


async def record(
    repository: Any, user_id: Any, action: str, *, meta: Mapping[str, Any]
) -> None:
    """Écrit une ligne d'audit sans jamais faire échouer l'appelant.

    La garde est ICI et non dans l'implémentation du dépôt, parce que c'est
    l'APPELANT qu'il faut protéger : mon premier essai l'avait placée dans
    ``SqlAlchemyAuthRepository.add_audit``, et le test « la connexion aboutit
    même si l'audit échoue » est tombé — toute erreur venant d'ailleurs (dépôt
    substitué, sérialisation des métadonnées, indisponibilité du moteur)
    remontait au routeur et coupait la connexion.

    Faire d'une table de journal une dépendance d'authentification serait un
    échange perdant : on couperait l'accès de tout le monde pour préserver la
    trace d'un incident. L'échec est signalé en ERROR — donc remonté par
    l'export d'erreurs — et la requête poursuit.
    """
    try:
        await repository.add_audit(user_id, action, meta=meta)
    except Exception:
        logger.exception("audit_write_failed action=%s", action)


def build_meta(
    *,
    client_ip: str | None,
    user_agent: str | None,
    trace_id: str | None,
    **extra: Any,
) -> dict[str, Any]:
    """Métadonnées d'un événement d'authentification.

    Ne porte JAMAIS d'adresse e-mail ni de mot de passe, y compris tronqués :
    un journal de sécurité qui accumule les adresses tentées devient
    lui-même la cible.
    """
    meta: dict[str, Any] = {
        "ip_network": truncate_ip(client_ip),
        "user_agent": (user_agent or "")[:200] or None,
        "trace_id": trace_id,
    }
    meta.update(extra)
    return {cle: valeur for cle, valeur in meta.items() if valeur is not None}

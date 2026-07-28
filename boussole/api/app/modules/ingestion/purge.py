"""Purge / export RGPD du module ingestion (D21).

Le module ingestion ne détient **aucune donnée personnelle** : il manipule
des offres publiques (``job_postings``, ``job_sources``, ``job_locations``,
``job_skills``, ``job_languages``) et l'état de synchronisation des
connecteurs (``connector_state`` : curseur, compteurs d'absence). Aucune de
ces tables ne porte de ``user_id`` ni de référence transitive vers ``users``
— l'inventaire par clés étrangères de ``tests/integration/test_privacy_purge``
le vérifie.

Les interfaces sont donc des **no-op explicites**, PAS des stubs qui lèvent.
La différence est structurante : un module absent du registre (ou dont la
purge lève) est silencieusement exclu de l'orchestration, et le test
d'exhaustivité — qui résout et appelle chaque purge du registre — ne peut
rien détecter. En enregistrant ce module avec un no-op documenté, le jour où
l'ingestion stockera une donnée rattachée à un utilisateur (une alerte
sauvegardée, un historique de recherche), le point d'ancrage existe déjà et
la revue portera sur son contenu, pas sur son absence.
"""

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


async def purge_user(user_id: uuid.UUID) -> None:
    """No-op : aucune donnée personnelle dans le périmètre ingestion.

    Ne PAS transformer en suppression d'offres : ``job_postings`` est un bien
    commun mutualisé entre tous les utilisateurs (D13). Supprimer les offres
    d'un compte supprimé priverait tous les autres.
    """
    logger.debug("ingestion_purge_noop user=%s", user_id)


async def export_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Export RGPD (art. 20) : rien à exporter côté ingestion.

    Les offres consultées ou sauvegardées par l'utilisateur relèvent du
    module ``jobs`` (``saved_jobs``), qui les exporte.
    """
    return {}

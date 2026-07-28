"""Routes du module ingestion — volontairement AUCUNE.

L'ingestion n'expose pas d'API publique : elle est pilotée par les tâches
Celery ``ingestion.sync_source`` / ``ingestion.reconcile`` et par la
planification beat (D04, D16). Le registre des sources visible par
l'utilisateur (``GET /sources``, transparence produit) est servi par le
module ``jobs``, qui possède déjà la lecture des offres et de leurs sources.

Ce fichier ne déclare donc qu'un routeur vide. Il en portait auparavant un
stub ``GET /sources`` répondant 501 : comme le routeur ``jobs`` est monté en
premier et déclare la même route, ce stub était **inatteignable** — un
faux témoin, qui laissait croire à une fonctionnalité non livrée alors
qu'elle l'était ailleurs. Un routeur vide dit la vérité.
"""

from fastapi import APIRouter

#: Routeur sans route : conservé pour que le montage dans ``app/main.py``
#: reste explicite et que l'ajout d'une éventuelle route d'administration
#: (déclenchement manuel d'une synchronisation, par exemple) ait un point
#: d'ancrage évident.
router = APIRouter(tags=["ingestion"])

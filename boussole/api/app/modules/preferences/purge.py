"""Purge / export RGPD du module preferences (D21) — stub M1.

Le module ``privacy`` orchestrera ces interfaces en M5 ; un test de registre
vérifiera qu'aucun module n'est oublié.
"""

import uuid
from typing import Any


async def purge_user(user_id: uuid.UUID) -> None:
    """Non implémenté avant M2 : le module preferences ne gère aucune donnée en M1."""
    raise NotImplementedError(
        "preferences.purge_user : prévu au jalon M2 (aucune donnée gérée en M1)"
    )


async def export_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Non implémenté avant M2 : le module preferences ne gère aucune donnée en M1."""
    raise NotImplementedError(
        "preferences.export_user : prévu au jalon M2 (aucune donnée gérée en M1)"
    )

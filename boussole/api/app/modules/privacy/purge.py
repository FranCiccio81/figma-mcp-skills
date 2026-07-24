"""Purge / export RGPD du module privacy (D21) — stub M1.

Le module ``privacy`` orchestrera ces interfaces en M5 ; un test de registre
vérifiera qu'aucun module n'est oublié.
"""

import uuid
from typing import Any


async def purge_user(user_id: uuid.UUID) -> None:
    """Non implémenté avant M5 : le module privacy ne gère aucune donnée en M1."""
    raise NotImplementedError(
        "privacy.purge_user : prévu au jalon M5 (aucune donnée gérée en M1)"
    )


async def export_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Non implémenté avant M5 : le module privacy ne gère aucune donnée en M1."""
    raise NotImplementedError(
        "privacy.export_user : prévu au jalon M5 (aucune donnée gérée en M1)"
    )

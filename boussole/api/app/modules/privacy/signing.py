"""Liens signés d'export RGPD + hachage irréversible des sujets purgés.

Lien signé STUB 🟡 : jeton HMAC-SHA256 sur ``{export_id}:{expires_epoch}``,
vérifié par le GET dédié ``/privacy/exports/{id}/download``. Le vrai lien
pré-signé S3 (SSE-KMS, 09 §5) arrivera avec le stockage S3 réel — seule
cette unité changera.

Clé de signature : ``settings.privacy_signing_key`` (réglage dédié — rotation
indépendante du stockage, vault en prod, D23).
"""

import hashlib
import hmac
import uuid
from datetime import datetime

from app.core.config import get_settings

EXPORT_LINK_TTL_DAYS = 7  # RM-Q-3 : lien signé valable 7 jours


def _secret() -> bytes:
    return get_settings().privacy_signing_key.encode()


def sign_export(export_id: uuid.UUID, expires_epoch: int) -> str:
    """Signature HMAC du couple (export, expiration)."""
    message = f"{export_id}:{expires_epoch}".encode()
    return hmac.new(_secret(), message, hashlib.sha256).hexdigest()


def verify_export_signature(export_id: uuid.UUID, expires_epoch: int, signature: str) -> bool:
    """Vérification en temps constant du jeton signé."""
    expected = sign_export(export_id, expires_epoch)
    return hmac.compare_digest(expected, signature)


def make_download_url(export_id: uuid.UUID, expires_at: datetime) -> str:
    """URL relative signée (servie via le proxy Next, même origine — D11)."""
    expires_epoch = int(expires_at.timestamp())
    signature = sign_export(export_id, expires_epoch)
    prefix = get_settings().api_prefix
    return (
        f"{prefix}/privacy/exports/{export_id}/download"
        f"?expires={expires_epoch}&sig={signature}"
    )


def subject_key_for(user_id: uuid.UUID) -> str:
    """Hash irréversible du sujet, conservé dans audit_log après purge (F-Q).

    HMAC (clé serveur) plutôt que SHA brut : l'espace des UUID n'est pas
    devinable, mais la clé interdit toute ré-identification hors plateforme.
    """
    return hmac.new(_secret(), str(user_id).encode(), hashlib.sha256).hexdigest()

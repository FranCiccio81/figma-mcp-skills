"""Sécurité : hachage argon2id, sessions opaques Redis, CSRF double-submit.

- Mots de passe : argon2id (argon2-cffi, paramètres par défaut RFC 9106 low-memory).
- Sessions : jeton opaque (32 octets URL-safe) stocké côté serveur dans le
  Redis persistant, TTL 30 jours glissants (rafraîchi à chaque lecture).
  Un index par utilisateur permet la révocation globale (purge RGPD, D21).
- CSRF : double-submit token — cookie lisible + en-tête ``X-CSRF-Token``,
  comparés en temps constant. Aucun état serveur.
"""

import contextlib
import hmac
import json
import secrets
import time
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from redis.asyncio import Redis

_hasher = PasswordHasher()  # argon2id par défaut

# Hachage factice : égalise le temps de réponse quand l'utilisateur n'existe
# pas (anti-énumération par timing sur /auth/login).
_DUMMY_HASH = _hasher.hash("boussole-timing-equalizer")

SESSION_KEY_PREFIX = "session:"
USER_SESSIONS_KEY_PREFIX = "user_sessions:"


def hash_password(password: str) -> str:
    """Hache un mot de passe en argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe ; toute erreur (hash invalide inclus) → False."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def waste_time_like_verify(password: str) -> None:
    """Consomme le même temps qu'une vérification réelle (anti-timing)."""
    with contextlib.suppress(VerificationError):
        _hasher.verify(_DUMMY_HASH, password)


def generate_session_token() -> str:
    """Jeton de session opaque, 256 bits d'entropie."""
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    """Jeton CSRF (double-submit), 256 bits d'entropie."""
    return secrets.token_urlsafe(32)


def csrf_tokens_match(header_value: str | None, cookie_value: str | None) -> bool:
    """Comparaison en temps constant du double-submit token."""
    if not header_value or not cookie_value:
        return False
    return hmac.compare_digest(header_value, cookie_value)


class SessionStore:
    """Sessions opaques dans le Redis persistant (TTL glissant)."""

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _key(token: str) -> str:
        return f"{SESSION_KEY_PREFIX}{token}"

    @staticmethod
    def _user_index_key(user_id: uuid.UUID) -> str:
        return f"{USER_SESSIONS_KEY_PREFIX}{user_id}"

    async def create(self, user_id: uuid.UUID) -> str:
        """Crée une session et retourne son jeton opaque."""
        token = generate_session_token()
        payload = json.dumps({"user_id": str(user_id), "created_at": int(time.time())})
        pipe = self._redis.pipeline()
        pipe.set(self._key(token), payload, ex=self._ttl)
        pipe.sadd(self._user_index_key(user_id), token)
        pipe.expire(self._user_index_key(user_id), self._ttl)
        await pipe.execute()
        return token

    async def get_user_id(self, token: str) -> uuid.UUID | None:
        """Résout un jeton en user_id et rafraîchit le TTL (30 j glissants)."""
        raw = await self._redis.get(self._key(token))
        if raw is None:
            return None
        data = json.loads(raw)
        user_id = uuid.UUID(str(data["user_id"]))
        pipe = self._redis.pipeline()
        pipe.expire(self._key(token), self._ttl)
        pipe.expire(self._user_index_key(user_id), self._ttl)
        await pipe.execute()
        return user_id

    async def delete(self, token: str) -> None:
        """Révoque une session (logout)."""
        raw = await self._redis.get(self._key(token))
        pipe = self._redis.pipeline()
        pipe.delete(self._key(token))
        if raw is not None:
            data = json.loads(raw)
            pipe.srem(self._user_index_key(uuid.UUID(str(data["user_id"]))), token)
        await pipe.execute()

    async def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        """Révoque toutes les sessions d'un utilisateur (purge RGPD, D21)."""
        index_key = self._user_index_key(user_id)
        members = await self._redis.smembers(index_key)
        tokens: set[str] = {m.decode() if isinstance(m, bytes) else str(m) for m in members}
        pipe = self._redis.pipeline()
        for token in tokens:
            pipe.delete(self._key(token))
        pipe.delete(index_key)
        await pipe.execute()

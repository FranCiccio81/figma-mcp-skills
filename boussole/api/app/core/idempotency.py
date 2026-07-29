"""Idempotence des créations : mémoire partagée, pas mémoire de processus.

Le rejeu d'un ``POST`` — bouton cliqué deux fois, requête relancée par un
client mobile après une coupure — ne doit pas créer deux candidatures. La
première version tenait un dictionnaire en mémoire de processus : perdu au
redémarrage, et surtout **jamais partagé** entre instances. Derrière deux
répliques d'API, un double-clic tombait une fois sur deux sur l'instance qui
n'avait rien vu, et créait le doublon que la clé existait pour empêcher.

Le stockage est le Redis **volatile** : perdre une entrée n'est pas une
faute, la fenêtre de rejeu est courte et le pire cas est le doublon qu'on
avait déjà avant. Le Redis persistant n'apporterait rien ici et coûterait de
la place sur l'instance qui garde les sessions.

⚠️ Ce mécanisme ne prétend PAS empêcher deux requêtes **simultanées** de
créer deux lignes : c'est un cache de rejeu, pas un verrou distribué. La
garantie ferme contre le doublon reste au niveau SQL quand elle existe.
"""

import logging
import uuid

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

#: Durée de vie d'une clé d'idempotence. Assez longue pour couvrir un rejeu
#: réseau ou un utilisateur qui insiste ; assez courte pour qu'une clé
#: réutilisée des jours plus tard ne ressuscite pas une vieille ressource.
DEFAULT_TTL_SECONDS = 24 * 3600


class IdempotencyStore:
    """Associe ``(utilisateur, clé)`` à l'identifiant déjà créé."""

    def __init__(
        self, redis: Redis, *, prefix: str = "idem", ttl_seconds: int = DEFAULT_TTL_SECONDS
    ) -> None:
        self._redis = redis
        self._prefix = prefix
        self._ttl = ttl_seconds

    def _key(self, scope: str, user_id: uuid.UUID, key: str) -> str:
        # L'utilisateur fait partie de la clé : deux comptes qui choisissent
        # la même valeur ne doivent jamais se voir l'un l'autre.
        return f"{self._prefix}:{scope}:{user_id}:{key}"

    async def get(self, scope: str, user_id: uuid.UUID, key: str) -> uuid.UUID | None:
        """Identifiant déjà créé pour cette clé, ou ``None``.

        Best-effort : une panne du cache fait retomber sur une création
        normale — dégradation vers le comportement d'avant l'idempotence,
        jamais vers une erreur rendue à l'utilisateur.
        """
        try:
            brut = await self._redis.get(self._key(scope, user_id, key))
        except Exception:  # pragma: no cover - dépend de l'infra Redis
            logger.warning("idempotency_lookup_failed scope=%s", scope)
            return None
        if brut is None:
            return None
        # ``decode_responses`` est vrai sur nos clients, mais le typage de
        # redis-py laisse la porte ouverte aux octets : on ne suppose pas.
        texte = brut.decode() if isinstance(brut, bytes) else str(brut)
        try:
            return uuid.UUID(texte)
        except ValueError:
            # Valeur corrompue : on l'ignore plutôt que de faire échouer la
            # création. Rien ne justifie de refuser un POST pour ça.
            logger.warning("idempotency_value_invalid scope=%s valeur=%r", scope, texte)
            return None

    async def remember(
        self, scope: str, user_id: uuid.UUID, key: str, created_id: uuid.UUID
    ) -> None:
        """Mémorise l'identifiant créé. Un échec ne remonte jamais."""
        try:
            await self._redis.set(
                self._key(scope, user_id, key), str(created_id), ex=self._ttl
            )
        except Exception:  # pragma: no cover - dépend de l'infra Redis
            logger.warning("idempotency_store_failed scope=%s", scope)

"""Tests unitaires de app.core.security : argon2, sessions, CSRF."""

import uuid

from redis.asyncio import Redis

from app.core.security import (
    SESSION_KEY_PREFIX,
    SessionStore,
    csrf_tokens_match,
    generate_csrf_token,
    generate_session_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"
        assert hashed.startswith("$argon2id$")
        assert verify_password("correct horse battery staple", hashed)

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("un mot de passe long")
        assert not verify_password("un autre mot de passe", hashed)

    def test_invalid_hash_fails_without_raising(self) -> None:
        assert not verify_password("peu importe", "pas-un-hash-argon2")

    def test_hashes_are_salted(self) -> None:
        assert hash_password("même mot de passe !") != hash_password("même mot de passe !")


class TestSessionStore:
    async def test_create_get_delete_cycle(self, fake_redis: Redis) -> None:
        store = SessionStore(fake_redis, ttl_seconds=3600)
        user_id = uuid.uuid4()

        token = await store.create(user_id)
        assert len(token) >= 32
        assert await store.get_user_id(token) == user_id

        await store.delete(token)
        assert await store.get_user_id(token) is None

    async def test_unknown_token_returns_none(self, fake_redis: Redis) -> None:
        store = SessionStore(fake_redis, ttl_seconds=3600)
        assert await store.get_user_id(generate_session_token()) is None

    async def test_sliding_ttl_refreshed_on_get(self, fake_redis: Redis) -> None:
        ttl = 3600
        store = SessionStore(fake_redis, ttl_seconds=ttl)
        token = await store.create(uuid.uuid4())
        key = f"{SESSION_KEY_PREFIX}{token}"

        # Simule une session proche de l'expiration puis une lecture.
        await fake_redis.expire(key, 10)
        assert await fake_redis.ttl(key) <= 10
        await store.get_user_id(token)
        assert await fake_redis.ttl(key) > ttl - 5  # TTL 30 j glissants — rafraîchi

    async def test_delete_all_for_user(self, fake_redis: Redis) -> None:
        store = SessionStore(fake_redis, ttl_seconds=3600)
        user_id = uuid.uuid4()
        tokens = [await store.create(user_id) for _ in range(3)]
        other = await store.create(uuid.uuid4())

        await store.delete_all_for_user(user_id)

        for token in tokens:
            assert await store.get_user_id(token) is None
        assert await store.get_user_id(other) is not None


class TestCsrf:
    def test_matching_tokens(self) -> None:
        token = generate_csrf_token()
        assert csrf_tokens_match(token, token)

    def test_mismatched_tokens(self) -> None:
        assert not csrf_tokens_match(generate_csrf_token(), generate_csrf_token())

    def test_missing_values(self) -> None:
        token = generate_csrf_token()
        assert not csrf_tokens_match(None, token)
        assert not csrf_tokens_match(token, None)
        assert not csrf_tokens_match("", "")

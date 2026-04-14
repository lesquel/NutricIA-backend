"""Tests for refresh token creation and hash verification."""

import hashlib

from app.shared.infrastructure.security import (
    create_refresh_token,
    verify_refresh_token_hash,
)


class TestCreateRefreshToken:
    def test_returns_tuple_of_token_and_hash(self):
        token, token_hash = create_refresh_token("user-123")
        assert isinstance(token, str)
        assert isinstance(token_hash, str)

    def test_token_is_non_empty(self):
        token, _ = create_refresh_token("user-123")
        assert len(token) > 0

    def test_hash_is_sha256_of_token(self):
        token, token_hash = create_refresh_token("user-123")
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert token_hash == expected

    def test_each_call_produces_unique_token(self):
        token1, _ = create_refresh_token("user-123")
        token2, _ = create_refresh_token("user-123")
        assert token1 != token2


class TestVerifyRefreshTokenHash:
    def test_matches_correct_hash(self):
        token, token_hash = create_refresh_token("user-123")
        assert verify_refresh_token_hash(token, token_hash) is True

    def test_rejects_wrong_hash(self):
        token, _ = create_refresh_token("user-123")
        assert verify_refresh_token_hash(token, "wrong-hash") is False

    def test_rejects_wrong_token(self):
        _, token_hash = create_refresh_token("user-123")
        assert verify_refresh_token_hash("wrong-token", token_hash) is False

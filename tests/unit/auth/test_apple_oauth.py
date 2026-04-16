"""Unit tests for Apple JWKS verification."""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest
from jose.exceptions import JWTError

from app.auth.domain import InvalidTokenError
from app.auth.infrastructure import apple_jwks


def _make_jwt(header: dict[str, Any], payload: dict[str, Any]) -> str:
    """Return a fake JWT with the given header+payload (signature not verifiable)."""
    header_b64 = (
        base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    )
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    return f"{header_b64}.{payload_b64}.fake-signature"


@pytest.fixture(autouse=True)
def _reset_jwks_cache() -> None:
    """Ensure JWKS cache is clean between tests."""
    apple_jwks._invalidate_cache()
    yield
    apple_jwks._invalidate_cache()


@pytest.fixture
def fake_jwks_keys() -> list[dict[str, str]]:
    """Minimal JWKS-shape keys for monkeypatching _fetch_jwks."""
    return [
        {
            "kid": "apple-key-1",
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "n": "0vx7agoebGcQSuuPiLJXZptN",  # not a real key — tests never verify
            "e": "AQAB",
        }
    ]


# ── Format + cache behaviour ──────────────────────


@pytest.mark.asyncio
async def test_verify_apple_token_invalid_format_raises() -> None:
    with pytest.raises(InvalidTokenError):
        await apple_jwks.verify_apple_token("not-a-jwt")


@pytest.mark.asyncio
async def test_verify_apple_token_unknown_kid_raises(
    monkeypatch: pytest.MonkeyPatch,
    fake_jwks_keys: list[dict[str, str]],
) -> None:
    async def fake_fetch() -> list[dict[str, str]]:
        return fake_jwks_keys

    monkeypatch.setattr(apple_jwks, "_fetch_jwks", fake_fetch)

    token = _make_jwt(
        {"alg": "RS256", "kid": "not-in-jwks"},
        {"sub": "someone", "aud": "app.id", "iss": apple_jwks.APPLE_ISSUER},
    )

    with pytest.raises(InvalidTokenError, match="signing key not found"):
        await apple_jwks.verify_apple_token(token)


@pytest.mark.asyncio
async def test_verify_apple_token_network_error_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    async def fake_fetch() -> list[dict[str, str]]:
        raise httpx.RequestError("network down")

    monkeypatch.setattr(apple_jwks, "_fetch_jwks", fake_fetch)

    token = _make_jwt({"alg": "RS256", "kid": "x"}, {"sub": "y"})

    with pytest.raises(InvalidTokenError, match="unavailable"):
        await apple_jwks.verify_apple_token(token)


# ── Decode failures are correctly mapped ──────────────────────


@pytest.mark.asyncio
async def test_verify_apple_token_expired_raises(
    monkeypatch: pytest.MonkeyPatch,
    fake_jwks_keys: list[dict[str, str]],
) -> None:
    async def fake_fetch() -> list[dict[str, str]]:
        return fake_jwks_keys

    def fake_construct(*args: Any, **kwargs: Any) -> Any:
        return object()

    def fake_decode(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise JWTError("token is expired")

    monkeypatch.setattr(apple_jwks, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(apple_jwks.jose_jwk, "construct", fake_construct)
    monkeypatch.setattr(apple_jwks.jose_jwt, "decode", fake_decode)

    token = _make_jwt(
        {"alg": "RS256", "kid": "apple-key-1"},
        {"sub": "someone", "aud": "app.id", "iss": apple_jwks.APPLE_ISSUER},
    )

    with pytest.raises(InvalidTokenError, match="expired"):
        await apple_jwks.verify_apple_token(token)


@pytest.mark.asyncio
async def test_verify_apple_token_wrong_audience_raises(
    monkeypatch: pytest.MonkeyPatch,
    fake_jwks_keys: list[dict[str, str]],
) -> None:
    async def fake_fetch() -> list[dict[str, str]]:
        return fake_jwks_keys

    def fake_construct(*args: Any, **kwargs: Any) -> Any:
        return object()

    def fake_decode(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise JWTError("invalid audience")

    monkeypatch.setattr(apple_jwks, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(apple_jwks.jose_jwk, "construct", fake_construct)
    monkeypatch.setattr(apple_jwks.jose_jwt, "decode", fake_decode)

    token = _make_jwt(
        {"alg": "RS256", "kid": "apple-key-1"},
        {"sub": "someone", "aud": "wrong.client", "iss": apple_jwks.APPLE_ISSUER},
    )

    with pytest.raises(InvalidTokenError, match="audience"):
        await apple_jwks.verify_apple_token(token)


@pytest.mark.asyncio
async def test_verify_apple_token_wrong_issuer_raises(
    monkeypatch: pytest.MonkeyPatch,
    fake_jwks_keys: list[dict[str, str]],
) -> None:
    async def fake_fetch() -> list[dict[str, str]]:
        return fake_jwks_keys

    def fake_construct(*args: Any, **kwargs: Any) -> Any:
        return object()

    def fake_decode(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise JWTError("invalid issuer")

    monkeypatch.setattr(apple_jwks, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(apple_jwks.jose_jwk, "construct", fake_construct)
    monkeypatch.setattr(apple_jwks.jose_jwt, "decode", fake_decode)

    token = _make_jwt(
        {"alg": "RS256", "kid": "apple-key-1"},
        {"sub": "someone", "aud": "app.id", "iss": "https://evil.com"},
    )

    with pytest.raises(InvalidTokenError, match="issuer"):
        await apple_jwks.verify_apple_token(token)


@pytest.mark.asyncio
async def test_verify_apple_token_valid_returns_claims(
    monkeypatch: pytest.MonkeyPatch,
    fake_jwks_keys: list[dict[str, str]],
) -> None:
    async def fake_fetch() -> list[dict[str, str]]:
        return fake_jwks_keys

    def fake_construct(*args: Any, **kwargs: Any) -> Any:
        return object()

    def fake_decode(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "sub": "apple-user-123",
            "email": "user@icloud.com",
            "aud": "app.id",
            "iss": apple_jwks.APPLE_ISSUER,
        }

    monkeypatch.setattr(apple_jwks, "_fetch_jwks", fake_fetch)
    monkeypatch.setattr(apple_jwks.jose_jwk, "construct", fake_construct)
    monkeypatch.setattr(apple_jwks.jose_jwt, "decode", fake_decode)

    token = _make_jwt(
        {"alg": "RS256", "kid": "apple-key-1"},
        {"sub": "apple-user-123"},
    )

    info = await apple_jwks.verify_apple_token(token)

    assert info["provider_id"] == "apple-user-123"
    assert info["email"] == "user@icloud.com"
    assert info["avatar_url"] is None


# ── Cache behaviour ──────────────────────


@pytest.mark.asyncio
async def test_jwks_cache_reused_within_ttl(
    monkeypatch: pytest.MonkeyPatch,
    fake_jwks_keys: list[dict[str, str]],
) -> None:
    call_count = {"n": 0}

    async def fake_fetch() -> list[dict[str, str]]:
        call_count["n"] += 1
        return fake_jwks_keys

    monkeypatch.setattr(apple_jwks, "_fetch_jwks", fake_fetch)

    token = _make_jwt({"alg": "RS256", "kid": "not-in-jwks"}, {"sub": "y"})

    for _ in range(3):
        with pytest.raises(InvalidTokenError):
            await apple_jwks.verify_apple_token(token)

    assert call_count["n"] == 1, "JWKS should be fetched only once (cached)"

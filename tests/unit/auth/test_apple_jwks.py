"""Tests for Apple JWKS verification — RS256 signature, audience, issuer checks."""

import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwk, jwt as jose_jwt

from app.auth.domain import InvalidTokenError
from app.auth.infrastructure import verify_apple_token, _apple_jwks_cache

# ---------------------------------------------------------------------------
# Helpers — generate RSA keys and fake JWKS
# ---------------------------------------------------------------------------

APPLE_ISSUER = "https://appleid.apple.com"
TEST_CLIENT_ID = "com.test.nutricia"
TEST_KID = "test-kid-001"


def _generate_rsa_keypair():
    """Return (private_key, public_key) as cryptography objects."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _public_key_to_jwk(public_key, kid: str) -> dict:
    """Convert an RSA public key to JWK dict (as Apple would serve)."""
    pub_numbers = public_key.public_numbers()

    def _b64url(num: int, length: int) -> str:
        import base64

        raw = num.to_bytes(length, byteorder="big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url(pub_numbers.n, 256),
        "e": _b64url(pub_numbers.e, 3),
    }


def _sign_jwt(private_key, claims: dict, kid: str) -> str:
    """Sign a JWT with RS256 using the given private key."""
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jose_jwt.encode(
        claims,
        pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _make_claims(
    sub: str = "apple-user-001",
    email: str = "user@icloud.com",
    aud: str = TEST_CLIENT_ID,
    iss: str = APPLE_ISSUER,
    exp: int | None = None,
) -> dict:
    """Build a standard Apple-like JWT payload."""
    return {
        "sub": sub,
        "email": email,
        "aud": aud,
        "iss": iss,
        "exp": exp or int(time.time()) + 3600,
        "iat": int(time.time()),
    }


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def apple_keys():
    """Generate a fresh RSA keypair and return (private_key, jwks_response)."""
    priv, pub = _generate_rsa_keypair()
    jwks_response = {"keys": [_public_key_to_jwk(pub, TEST_KID)]}
    return priv, jwks_response


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear Apple JWKS cache before each test."""
    _apple_jwks_cache.clear()
    yield
    _apple_jwks_cache.clear()


# ---------------------------------------------------------------------------
# 3.1 — Happy-path test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_apple_token_happy_path(apple_keys):
    """A properly signed JWT with valid kid/aud/iss is decoded correctly."""
    priv, jwks_response = apple_keys
    token = _sign_jwt(priv, _make_claims(), TEST_KID)

    mock_settings = MagicMock()
    mock_settings.apple_client_id = TEST_CLIENT_ID

    with (
        patch(
            "app.auth.infrastructure._fetch_apple_jwks",
            new_callable=AsyncMock,
            return_value=jwks_response["keys"],
        ),
        patch("app.auth.infrastructure.settings", mock_settings),
    ):
        result = await verify_apple_token(token)

    assert result["provider_id"] == "apple-user-001"
    assert result["email"] == "user@icloud.com"


# ---------------------------------------------------------------------------
# 3.2 — Rejection cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_wrong_audience(apple_keys):
    """JWT with wrong audience is rejected."""
    priv, jwks_response = apple_keys
    token = _sign_jwt(priv, _make_claims(aud="com.wrong.app"), TEST_KID)

    with (
        patch(
            "app.auth.infrastructure._fetch_apple_jwks",
            new_callable=AsyncMock,
            return_value=jwks_response["keys"],
        ),
        patch("app.auth.infrastructure.settings") as mock_settings,
    ):
        mock_settings.apple_client_id = TEST_CLIENT_ID
        with pytest.raises(InvalidTokenError):
            await verify_apple_token(token)


@pytest.mark.asyncio
async def test_reject_wrong_issuer(apple_keys):
    """JWT with wrong issuer is rejected."""
    priv, jwks_response = apple_keys
    token = _sign_jwt(priv, _make_claims(iss="https://evil.example.com"), TEST_KID)

    with (
        patch(
            "app.auth.infrastructure._fetch_apple_jwks",
            new_callable=AsyncMock,
            return_value=jwks_response["keys"],
        ),
        patch("app.auth.infrastructure.settings") as mock_settings,
    ):
        mock_settings.apple_client_id = TEST_CLIENT_ID
        with pytest.raises(InvalidTokenError):
            await verify_apple_token(token)


@pytest.mark.asyncio
async def test_reject_unknown_kid(apple_keys):
    """JWT with a kid not in Apple's JWKS is rejected."""
    priv, jwks_response = apple_keys
    token = _sign_jwt(priv, _make_claims(), "unknown-kid-999")

    with (
        patch(
            "app.auth.infrastructure._fetch_apple_jwks",
            new_callable=AsyncMock,
            return_value=jwks_response["keys"],
        ),
        patch("app.auth.infrastructure.settings") as mock_settings,
    ):
        mock_settings.apple_client_id = TEST_CLIENT_ID
        with pytest.raises(InvalidTokenError):
            await verify_apple_token(token)


@pytest.mark.asyncio
async def test_reject_expired_token(apple_keys):
    """Expired JWT is rejected."""
    priv, jwks_response = apple_keys
    token = _sign_jwt(priv, _make_claims(exp=int(time.time()) - 3600), TEST_KID)

    with (
        patch(
            "app.auth.infrastructure._fetch_apple_jwks",
            new_callable=AsyncMock,
            return_value=jwks_response["keys"],
        ),
        patch("app.auth.infrastructure.settings") as mock_settings,
    ):
        mock_settings.apple_client_id = TEST_CLIENT_ID
        with pytest.raises(InvalidTokenError):
            await verify_apple_token(token)


@pytest.mark.asyncio
async def test_reject_invalid_signature(apple_keys):
    """JWT signed with a different key is rejected."""
    _priv, jwks_response = apple_keys
    # Sign with a DIFFERENT key pair
    other_priv, _ = _generate_rsa_keypair()
    token = _sign_jwt(other_priv, _make_claims(), TEST_KID)

    with (
        patch(
            "app.auth.infrastructure._fetch_apple_jwks",
            new_callable=AsyncMock,
            return_value=jwks_response["keys"],
        ),
        patch("app.auth.infrastructure.settings") as mock_settings,
    ):
        mock_settings.apple_client_id = TEST_CLIENT_ID
        with pytest.raises(InvalidTokenError):
            await verify_apple_token(token)


# ---------------------------------------------------------------------------
# 3.3 — Caching tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jwks_cache_hit_no_refetch(apple_keys):
    """Second call within TTL uses cached keys — no HTTP request."""
    priv, jwks_response = apple_keys
    token = _sign_jwt(priv, _make_claims(), TEST_KID)

    mock_fetch = AsyncMock(return_value=jwks_response["keys"])

    with (
        patch("app.auth.infrastructure._fetch_apple_jwks", mock_fetch),
        patch("app.auth.infrastructure.settings") as mock_settings,
    ):
        mock_settings.apple_client_id = TEST_CLIENT_ID

        await verify_apple_token(token)
        await verify_apple_token(token)

        # Should only have fetched once — second call used cache
        assert mock_fetch.call_count == 1


@pytest.mark.asyncio
async def test_jwks_cache_can_be_invalidated(apple_keys):
    """After clearing cache, next call fetches fresh keys."""
    priv, jwks_response = apple_keys
    token = _sign_jwt(priv, _make_claims(), TEST_KID)

    mock_fetch = AsyncMock(return_value=jwks_response["keys"])

    with (
        patch("app.auth.infrastructure._fetch_apple_jwks", mock_fetch),
        patch("app.auth.infrastructure.settings") as mock_settings,
    ):
        mock_settings.apple_client_id = TEST_CLIENT_ID

        await verify_apple_token(token)
        assert mock_fetch.call_count == 1

        # Invalidate cache
        _apple_jwks_cache.clear()

        await verify_apple_token(token)
        assert mock_fetch.call_count == 2

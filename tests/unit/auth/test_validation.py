"""Tests for auth schema validation (OAuthRequest.provider Literal)."""

import pytest
from pydantic import ValidationError

from app.auth.presentation import OAuthRequest


class TestOAuthRequestProvider:
    """OAuthRequest.provider must be Literal["google", "apple"]."""

    def test_google_is_valid(self) -> None:
        req = OAuthRequest(token="tok", provider="google")
        assert req.provider == "google"

    def test_apple_is_valid(self) -> None:
        req = OAuthRequest(token="tok", provider="apple")
        assert req.provider == "apple"

    def test_facebook_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OAuthRequest(token="tok", provider="facebook")

    def test_empty_string_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OAuthRequest(token="tok", provider="")

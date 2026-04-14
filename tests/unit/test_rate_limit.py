"""Unit tests for the rate limiting module."""

from unittest.mock import MagicMock

from slowapi import Limiter
from slowapi.util import get_remote_address


class TestLimiterInstance:
    """Tests for the rate limiter configuration."""

    def test_limiter_is_slowapi_instance(self):
        from app.shared.infrastructure.rate_limit import limiter

        assert isinstance(limiter, Limiter)

    def test_limiter_uses_get_remote_address_as_key_func(self):
        from app.shared.infrastructure.rate_limit import get_key_func

        assert get_key_func is get_remote_address

    def test_default_limits_are_configured(self):
        from app.shared.infrastructure.rate_limit import limiter

        assert limiter._default_limits is not None
        assert len(limiter._default_limits) > 0


class TestKeyFunction:
    """Tests for IP extraction from requests."""

    def test_key_func_extracts_client_ip(self):
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}

        result = get_remote_address(mock_request)
        assert result == "192.168.1.100"

    def test_key_func_with_different_ip(self):
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = {}

        result = get_remote_address(mock_request)
        assert result == "10.0.0.1"

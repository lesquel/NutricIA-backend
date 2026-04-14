"""Unit tests for JWT secret startup validation."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def test_startup_fails_with_default_secret_in_production():
    """App should refuse to start if jwt_secret is the default in non-debug mode."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.jwt_secret = "change-me-in-production"
        mock_settings.debug = False
        mock_settings.app_name = "NutricIA"
        mock_settings.cors_origins = "http://localhost:3000"

        from app.main import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)
        with pytest.raises(RuntimeError, match="JWT_SECRET must be changed"):
            with client:
                pass


def test_startup_warns_with_default_secret_in_debug(caplog):
    """App should log a warning if jwt_secret is the default in debug mode."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.jwt_secret = "change-me-in-production"
        mock_settings.debug = True
        mock_settings.app_name = "NutricIA"
        mock_settings.cors_origins = "http://localhost:3000"

        from app.main import create_app

        app = create_app()
        client = TestClient(app)
        with client:
            pass  # Should not raise
    assert "JWT_SECRET is set to the default value" in caplog.text


def test_startup_ok_with_custom_secret():
    """App should start normally when jwt_secret is not the default."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.jwt_secret = "super-secure-random-secret"
        mock_settings.debug = False
        mock_settings.app_name = "NutricIA"
        mock_settings.cors_origins = "http://localhost:3000"

        from app.main import create_app

        app = create_app()
        client = TestClient(app)
        with client:
            resp = client.get("/health")
            assert resp.status_code == 200

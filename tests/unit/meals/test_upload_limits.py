"""Tests for meal upload file size limits."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_scan_rejects_file_over_5mb(
    api_client: AsyncClient, auth_headers: dict
):
    """POST /meals/scan should return 413 for files over 5MB."""
    large_content = b"x" * (5 * 1024 * 1024 + 1)  # 5MB + 1 byte
    files = {"file": ("big.jpg", io.BytesIO(large_content), "image/jpeg")}

    response = await api_client.post(
        "/api/v1/meals/scan", headers=auth_headers, files=files
    )

    assert response.status_code == 413
    assert "5MB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_scan_accepts_file_under_5mb(
    api_client: AsyncClient, auth_headers: dict
):
    """POST /meals/scan should accept files <= 5MB (may fail for other reasons, but NOT 413)."""
    small_content = b"x" * (5 * 1024 * 1024)  # exactly 5MB
    files = {"file": ("ok.jpg", io.BytesIO(small_content), "image/jpeg")}

    response = await api_client.post(
        "/api/v1/meals/scan", headers=auth_headers, files=files
    )

    # Should NOT be 413 — may fail with 422/500 due to AI analysis, but size is accepted
    assert response.status_code != 413


@pytest.mark.asyncio
async def test_upload_image_rejects_file_over_5mb(
    api_client: AsyncClient, auth_headers: dict
):
    """POST /meals/upload-image should return 413 for files over 5MB."""
    large_content = b"x" * (5 * 1024 * 1024 + 1)
    files = {"file": ("big.jpg", io.BytesIO(large_content), "image/jpeg")}

    response = await api_client.post(
        "/api/v1/meals/upload-image", headers=auth_headers, files=files
    )

    assert response.status_code == 413
    assert "5MB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_image_accepts_file_under_5mb(
    api_client: AsyncClient, auth_headers: dict
):
    """POST /meals/upload-image should accept files <= 5MB."""
    small_content = b"\x89PNG" + b"\x00" * (1024)  # small valid-ish file
    files = {"file": ("ok.png", io.BytesIO(small_content), "image/png")}

    response = await api_client.post(
        "/api/v1/meals/upload-image", headers=auth_headers, files=files
    )

    assert response.status_code != 413

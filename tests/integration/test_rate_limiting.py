"""Integration tests for rate limiting middleware."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.shared.infrastructure import Base
from app.dependencies import get_db
from app.main import create_app


@pytest_asyncio.fixture
async def rate_limit_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Isolated DB session for rate limit tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def rate_limit_app(
    rate_limit_db_session: AsyncSession,
) -> AsyncGenerator[FastAPI, None]:
    """App instance with DB overridden for rate limit tests."""
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield rate_limit_db_session
            await rate_limit_db_session.commit()
        except Exception:
            await rate_limit_db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def rate_limit_client(
    rate_limit_app: FastAPI,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for rate limit tests."""
    transport = ASGITransport(app=rate_limit_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestSlowAPIMiddlewareIntegration:
    """Tests that SlowAPI middleware is wired into the app."""

    @pytest.mark.asyncio
    async def test_app_has_limiter_in_state(self, rate_limit_app: FastAPI):
        """Verify that app.state.limiter is configured."""
        from slowapi import Limiter

        assert hasattr(rate_limit_app.state, "limiter")
        assert isinstance(rate_limit_app.state.limiter, Limiter)

    @pytest.mark.asyncio
    async def test_rate_limited_login_returns_429_after_exceeding_limit(
        self, rate_limit_client: AsyncClient
    ):
        """The login endpoint should return 429 after 5 requests/min."""
        payload = {"email": "test@test.com", "password": "testpassword123"}

        # Make 5 requests (within limit)
        for _ in range(5):
            await rate_limit_client.post("/api/v1/auth/login", json=payload)

        # 6th request should be rate limited
        response = await rate_limit_client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_429_includes_retry_after_header(
        self, rate_limit_client: AsyncClient
    ):
        """429 responses must include a Retry-After header."""
        payload = {"email": "test@test.com", "password": "testpassword123"}

        # Exhaust rate limit
        for _ in range(5):
            await rate_limit_client.post("/api/v1/auth/login", json=payload)

        response = await rate_limit_client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 429
        assert "Retry-After" in response.headers

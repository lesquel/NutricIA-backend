import pytest
import asyncio
import uuid
from typing import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.shared.infrastructure import Base
from app.auth.infrastructure.models import User, PasswordResetTokenModel  # noqa: F401
from app.catalog.infrastructure.models import FoodCatalogModel  # noqa: F401
from app.meal_plans.infrastructure.models import MealPlanModel, PlannedMealModel  # noqa: F401  # meal_plans models (iter 3B)
from app.chat.infrastructure.models import ConversationModel, MessageModel  # noqa: F401

# learning_loop models (iter 4A)
from app.learning_loop.infrastructure.models import (
    UserFoodProfileModel,
    ScanCorrectionModel,
)  # noqa: F401
from app.shared.infrastructure.security import create_access_token, decode_access_token
from app.dependencies import get_db
from app.main import create_app


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a clean database session for tests using in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Creates and returns a test user."""
    from app.auth.infrastructure.repository import hash_password

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        password_hash=hash_password("password123"),
        provider=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user: User) -> str:
    """Generates a valid JWT token for test_user."""
    return create_access_token(str(test_user.id))


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Returns authorization headers for requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def expired_token() -> str:
    """Generates an expired JWT token."""
    from jose import jwt
    from app.config import settings

    expire = datetime.now(timezone.utc) - timedelta(minutes=1)
    payload = {
        "sub": str(uuid.uuid4()),
        "exp": expire,
        "iat": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest_asyncio.fixture
async def test_app(db_session: AsyncSession) -> AsyncGenerator[FastAPI, None]:
    """Create a FastAPI app with DB dependency overridden for tests."""
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client bound to the app instance."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

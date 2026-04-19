import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings

logger = logging.getLogger("nutricia")


_AI_PROVIDER_KEY_ATTR: dict[str, str] = {
    "groq": "groq_api_key",
    "gemini": "google_api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "deepseek": "deepseek_api_key",
    "mistral": "mistral_api_key",
}


def _validate_ai_credentials() -> None:
    """Warn at startup if the AI stack is misconfigured.

    Catches the common footgun where keys live in `backend/.env` while
    docker-compose injects empty strings for the same vars from the root
    `.env`, which wins in pydantic-settings precedence.
    """
    provider = settings.ai_provider

    if provider == "mock":
        if not settings.debug:
            raise RuntimeError(
                "AI_PROVIDER=mock is not allowed when DEBUG=false. "
                "Set a real provider (groq/gemini/openai/anthropic/...) and its API key."
            )
        logger.warning(
            "NutricIA running with MOCK AI provider — all scans return the same sample data."
        )
        return

    primary_attr = _AI_PROVIDER_KEY_ATTR.get(provider)
    primary_key = getattr(settings, primary_attr, "") if primary_attr else ""
    if primary_key:
        return

    configured_fallbacks = [
        name
        for name, attr in _AI_PROVIDER_KEY_ATTR.items()
        if name != provider and getattr(settings, attr, "")
    ]

    if configured_fallbacks:
        logger.warning(
            "AI_PROVIDER=%s has no credentials — will attempt fallback providers: %s. "
            "Set the primary key in your ROOT .env (not backend/.env) so docker-compose picks it up.",
            provider,
            ", ".join(configured_fallbacks),
        )
        return

    logger.error(
        "AI provider '%s' has no API key AND no fallback providers are configured. "
        "Scans and chat will fail. Set %s in your ROOT .env (consumed by docker-compose). "
        "Do NOT put it only in backend/.env — docker-compose env vars override that file.",
        provider,
        (primary_attr or provider).upper(),
    )


async def _ensure_pgvector_extension() -> None:
    """Create the pgvector extension on startup when using Postgres.

    Idempotent — `CREATE EXTENSION IF NOT EXISTS` is a no-op once installed.
    Requires the DB user to have privileges (Render's default role does).
    Silently skipped for SQLite.
    """
    if settings.vector_store_backend != "pgvector":
        return
    if not settings.database_url.startswith(
        ("postgresql+asyncpg://", "postgresql://", "postgres://")
    ):
        return

    from sqlalchemy import text

    from app.shared.infrastructure import engine

    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension verified")
    except Exception as exc:  # noqa: BLE001 — startup diagnostic
        logger.warning("Could not ensure pgvector extension: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    logger.info("NutricIA backend starting up...")
    # Schema is managed exclusively by Alembic migrations.
    # Run `make db-upgrade` (alembic upgrade head) before starting the server.
    from app.shared.infrastructure import engine  # noqa: F401

    _validate_ai_credentials()
    await _ensure_pgvector_extension()

    yield
    logger.info("NutricIA backend shutting down...")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Open source AI-powered calorie tracker",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — origins from settings (.env CORS_ORIGINS)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers (Clean Architecture — presentation layer)
    from app.auth.presentation.router import router as auth_router
    from app.meals.presentation.router import router as meals_router
    from app.analytics.presentation.router import router as analytics_router
    from app.habits.presentation.router import router as habits_router
    from app.users.presentation.router import router as users_router
    from app.meal_plans.presentation.router import (
        router as meal_plans_router,
    )  # meal_plans (iter 3B)
    from app.chat.presentation.router import router as chat_router
    from app.learning_loop.presentation.router import (
        router as learning_loop_router,
    )  # learning_loop router (iter 4A)

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(meals_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(habits_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(meal_plans_router, prefix="/api/v1")  # meal_plans (iter 3B)
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(
        learning_loop_router, prefix="/api/v1"
    )  # learning_loop (iter 4A)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "app": settings.app_name}

    # Serve uploaded files (avatars, etc.)
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    return app


app = create_app()

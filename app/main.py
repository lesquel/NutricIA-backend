import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings

logger = logging.getLogger("nutricia")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    logger.info("NutricIA backend starting up...")
    # Schema is managed exclusively by Alembic migrations.
    # Run `make db-upgrade` (alembic upgrade head) before starting the server.
    from app.shared.infrastructure import engine  # noqa: F401

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

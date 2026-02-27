import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logger = logging.getLogger("nutricia")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    logger.info("🌱 NutricIA backend starting up...")
    yield
    logger.info("🍃 NutricIA backend shutting down...")
    from app.database import engine

    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Open source AI-powered calorie tracker",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow Expo dev server and common origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8081",  # Expo dev
            "http://localhost:19006",  # Expo web
            "http://localhost:3000",
            "exp://localhost:8081",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from app.auth.router import router as auth_router
    from app.meals.router import router as meals_router
    from app.analytics.router import router as analytics_router
    from app.habits.router import router as habits_router
    from app.users.router import router as users_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(meals_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(habits_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()

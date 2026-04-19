from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "NutricIA"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./nutricia.db"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Server
    base_url: str = "http://localhost:8000"

    # CORS
    cors_origins: str = (
        "http://localhost:8081,http://localhost:19006,http://localhost:3000"
    )

    # OAuth
    google_client_id: str = ""
    apple_client_id: str = ""

    # AI Provider — Groq is the primary provider for LLM tasks (chat, meal
    # scanning, meal-plan generation). Groq does NOT provide embeddings, so
    # RAG still requires GOOGLE_API_KEY or OPENAI_API_KEY for the embeddings
    # pipeline (see app.shared.infrastructure.embeddings).
    ai_provider: Literal[
        "groq", "gemini", "openai", "anthropic", "deepseek", "mistral", "mock"
    ] = "groq"
    ai_model: str = ""  # Leave empty to use provider default
    groq_api_key: str = ""  # Groq (primary LLM provider)
    google_api_key: str = ""  # Gemini + embeddings
    openai_api_key: str = ""  # OpenAI / DeepSeek (via base_url) + embeddings
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    mistral_api_key: str = ""

    # External data source API keys
    usda_api_key: str = ""  # USDA FoodData Central (https://api.nal.usda.gov)

    # SMTP (used by SmtpEmailAdapter; unset = use ConsoleEmailAdapter)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@nutricia.app"

    # App URLs (for reset email deep links)
    app_base_url: str = "http://localhost:8000"
    frontend_deep_link_base: str = "nutricia://"

    # Vector store backend
    vector_store_backend: Literal["pgvector", "in_memory"] = "in_memory"

    # Feature flags
    chat_enabled: bool = True
    meal_plans_enabled: bool = True
    learning_loop_enabled: bool = True

    # Admin
    admin_emails: str = ""  # Comma-separated admin email list

    # Image processing
    max_image_size_px: int = 1024
    max_image_bytes: int = 1_048_576  # 1MB

    @field_validator(
        "ai_provider",
        "ai_model",
        "google_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "deepseek_api_key",
        "groq_api_key",
        "mistral_api_key",
        "usda_api_key",
        mode="before",
    )
    @classmethod
    def strip_string_values(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_driver(cls, value: str | None) -> str | None:
        """Normalize Postgres URLs to the asyncpg driver.

        Managed Postgres providers (Render, Heroku, Railway) expose
        `postgres://` or `postgresql://` which SQLAlchemy routes to the
        sync `psycopg2` driver. This app uses async SQLAlchemy, so we
        rewrite the scheme to `postgresql+asyncpg://`.
        """
        if not isinstance(value, str):
            return value
        url = value.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        return url


settings = Settings()

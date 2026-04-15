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

    # AI Provider
    ai_provider: Literal[
        "gemini", "openai", "anthropic", "deepseek", "groq", "mistral", "mock"
    ] = "gemini"
    ai_model: str = ""  # Leave empty to use provider default
    google_api_key: str = ""  # Gemini
    openai_api_key: str = ""  # OpenAI / DeepSeek (via base_url)
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    groq_api_key: str = ""
    mistral_api_key: str = ""

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
        mode="before",
    )
    @classmethod
    def strip_string_values(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value


settings = Settings()

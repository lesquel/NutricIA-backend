"""Auth infrastructure — SQLAlchemy models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Password auth (nullable — OAuth-only users won't have a password)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # OAuth provider info (nullable — email/password-only users won't have provider)
    provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "google" | "apple" | None
    provider_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )

    # Goals & preferences
    calorie_goal: Mapped[int] = mapped_column(default=2100)
    water_goal_ml: Mapped[int] = mapped_column(default=2500)
    dietary_preferences: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default="[]"
    )  # JSON array as string

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

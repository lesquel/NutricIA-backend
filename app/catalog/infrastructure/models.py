"""Catalog infrastructure — SQLAlchemy model for food_catalog table."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure import Base


class FoodCatalogModel(Base):
    """SQLAlchemy model for the food_catalog table.

    The `aliases` and `macros_per_100g` columns are stored as JSON strings
    (TEXT) in SQLite and JSONB in PostgreSQL.  The `embedding` column is TEXT
    in both environments because SQLAlchemy has no built-in VECTOR type; the
    migration handles the actual VECTOR(1536) column on postgres.

    The application layer serialises/deserialises these columns explicitly.
    """

    __tablename__ = "food_catalog"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )  # JSON array as text
    macros_per_100g: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON object as text
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

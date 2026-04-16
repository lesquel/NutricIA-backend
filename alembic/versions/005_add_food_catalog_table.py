"""Add food_catalog table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-15 00:00:00.000000

Changes:
- food_catalog: canonical food entries with macros, aliases, source, and optional embedding.
- Embedding column is VECTOR(1536) on PostgreSQL; TEXT on SQLite (tests).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        id_col = sa.Column(
            "id", PG_UUID(as_uuid=True), primary_key=True, nullable=False
        )
        aliases_col = sa.Column("aliases", JSONB(), nullable=False, server_default="[]")
        macros_col = sa.Column("macros_per_100g", JSONB(), nullable=False)
        created_at_col = sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )
        # VECTOR type via raw DDL after table creation
        embedding_col = sa.Column("embedding", sa.Text(), nullable=True)  # placeholder
    else:
        id_col = sa.Column(
            "id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False
        )
        aliases_col = sa.Column(
            "aliases", sa.Text(), nullable=False, server_default="[]"
        )
        macros_col = sa.Column("macros_per_100g", sa.Text(), nullable=False)
        created_at_col = sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        embedding_col = sa.Column("embedding", sa.Text(), nullable=True)

    op.create_table(
        "food_catalog",
        id_col,
        sa.Column("canonical_name", sa.String(255), nullable=False),
        aliases_col,
        macros_col,
        sa.Column("source", sa.String(50), nullable=False),
        embedding_col,
        created_at_col,
        sa.UniqueConstraint(
            "canonical_name", "source", name="uq_food_catalog_name_source"
        ),
    )

    if is_postgres:
        # Replace the TEXT placeholder with the actual VECTOR(1536) column type.
        # We do this via ALTER TABLE because SQLAlchemy doesn't have a native
        # VECTOR type (pgvector provides it, but we avoid importing pgvector
        # in migrations to keep them self-contained).
        op.drop_column("food_catalog", "embedding")
        op.execute("ALTER TABLE food_catalog ADD COLUMN embedding vector(1536)")


def downgrade() -> None:
    op.drop_table("food_catalog")

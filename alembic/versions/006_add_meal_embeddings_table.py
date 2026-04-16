"""Add meal_embeddings table.

Revision ID: 006
Revises: 005
Create Date: 2026-04-15 00:00:00.000000

Changes:
- meal_embeddings: stores per-meal vector embeddings for RAG retrieval.
- Embedding column is VECTOR(1536) on PostgreSQL; TEXT on SQLite (tests).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        meal_id_col = sa.Column(
            "meal_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
        created_at_col = sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )
        embedding_col = sa.Column("embedding", sa.Text(), nullable=False)  # placeholder
    else:
        meal_id_col = sa.Column(
            "meal_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
        created_at_col = sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        embedding_col = sa.Column("embedding", sa.Text(), nullable=False)

    op.create_table(
        "meal_embeddings",
        meal_id_col,
        embedding_col,
        sa.Column("content_text", sa.Text(), nullable=False),
        created_at_col,
    )

    if is_postgres:
        op.drop_column("meal_embeddings", "embedding")
        op.execute(
            "ALTER TABLE meal_embeddings ADD COLUMN embedding vector(1536) NOT NULL"
        )


def downgrade() -> None:
    op.drop_table("meal_embeddings")

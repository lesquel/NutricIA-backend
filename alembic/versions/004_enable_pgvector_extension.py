"""Enable pgvector extension.

Revision ID: 004
Revises: 003
Create Date: 2026-04-15 00:00:00.000000

Changes:
- Enables the vector extension in PostgreSQL for vector similarity search.
- No-op on SQLite (pgvector is postgres-only; tests use mocked adapters).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP EXTENSION IF EXISTS vector")

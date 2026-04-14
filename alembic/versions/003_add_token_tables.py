"""Add refresh_tokens and token_blocklist tables.

Revision ID: 003
Revises: 002
Create Date: 2026-04-14 00:00:00.000000

Changes:
- Create refresh_tokens table (user_id FK, token_hash UNIQUE, expires_at)
- Create token_blocklist table (jti UNIQUE, expires_at)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        )
        op.create_index(
            "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"]
        )
        op.create_index(
            "ix_refresh_tokens_token_hash",
            "refresh_tokens",
            ["token_hash"],
            unique=True,
        )

    if not inspector.has_table("token_blocklist"):
        op.create_table(
            "token_blocklist",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("jti", sa.String(36), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("jti", name="uq_token_blocklist_jti"),
        )
        op.create_index(
            "ix_token_blocklist_jti", "token_blocklist", ["jti"], unique=True
        )


def downgrade() -> None:
    op.drop_table("token_blocklist")
    op.drop_table("refresh_tokens")

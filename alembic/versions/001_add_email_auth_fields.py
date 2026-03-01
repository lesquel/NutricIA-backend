"""Add email auth fields to users table.

Revision ID: 001
Revises: None
Create Date: 2025-01-01 00:00:00.000000

Changes:
- Add password_hash column (nullable) to users table
- Make provider column nullable (was required for OAuth-only)
- Make provider_id column nullable (was required for OAuth-only)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("avatar_url", sa.String(512), nullable=True),
            sa.Column("password_hash", sa.String(255), nullable=True),
            sa.Column("provider", sa.String(50), nullable=True),
            sa.Column("provider_id", sa.String(255), nullable=True),
            sa.Column(
                "calorie_goal", sa.Integer(), nullable=False, server_default="2100"
            ),
            sa.Column(
                "water_goal_ml", sa.Integer(), nullable=False, server_default="2500"
            ),
            sa.Column(
                "dietary_preferences",
                sa.String(1024),
                nullable=True,
                server_default="[]",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("email", name="uq_users_email"),
            sa.UniqueConstraint("provider_id", name="uq_users_provider_id"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_provider_id", "users", ["provider_id"], unique=True)
        return

    columns = {column["name"] for column in inspector.get_columns("users")}

    if "password_hash" not in columns:
        op.add_column(
            "users",
            sa.Column("password_hash", sa.String(255), nullable=True),
        )

    if "provider" in columns:
        op.alter_column(
            "users",
            "provider",
            existing_type=sa.String(50),
            nullable=True,
        )

    if "provider_id" in columns:
        op.alter_column(
            "users",
            "provider_id",
            existing_type=sa.String(255),
            nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("users"):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}

    # Revert provider_id to non-nullable
    if "provider_id" in columns:
        op.alter_column(
            "users",
            "provider_id",
            existing_type=sa.String(255),
            nullable=False,
        )

    # Revert provider to non-nullable
    if "provider" in columns:
        op.alter_column(
            "users",
            "provider",
            existing_type=sa.String(50),
            nullable=False,
        )

    # Drop password_hash column
    if "password_hash" in columns:
        op.drop_column("users", "password_hash")

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

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password_hash column for email/password authentication
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(255), nullable=True),
    )

    # Make provider nullable to support email-only users
    op.alter_column(
        "users",
        "provider",
        existing_type=sa.String(50),
        nullable=True,
    )

    # Make provider_id nullable to support email-only users
    op.alter_column(
        "users",
        "provider_id",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    # Revert provider_id to non-nullable
    op.alter_column(
        "users",
        "provider_id",
        existing_type=sa.String(255),
        nullable=False,
    )

    # Revert provider to non-nullable
    op.alter_column(
        "users",
        "provider",
        existing_type=sa.String(50),
        nullable=False,
    )

    # Drop password_hash column
    op.drop_column("users", "password_hash")

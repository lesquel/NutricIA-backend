"""Add scan_corrections table.

Revision ID: 010
Revises: 009
Create Date: 2026-04-15 00:00:00.000000

Changes:
- Add scan_corrections table for learning loop feedback
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scan_corrections",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "meal_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_scan", sa.JSON(), nullable=False),
        sa.Column("corrected_values", sa.JSON(), nullable=False),
        sa.Column("original_confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_scan_corrections_user_id_created_at",
        "scan_corrections",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scan_corrections_user_id_created_at", table_name="scan_corrections"
    )
    op.drop_table("scan_corrections")

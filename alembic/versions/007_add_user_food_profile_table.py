"""Add user_food_profile table.

Revision ID: 007
Revises: 006
Create Date: 2026-04-15 00:00:00.000000

Changes:
- user_food_profile: rolling nutritional summary and food preferences per user.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        user_id_col = sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
        frequent_foods_col = sa.Column(
            "frequent_foods", JSONB(), nullable=False, server_default="[]"
        )
        avoided_tags_col = sa.Column(
            "avoided_tags", JSONB(), nullable=False, server_default="[]"
        )
        avg_daily_macros_col = sa.Column("avg_daily_macros", JSONB(), nullable=True)
        updated_at_col = sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )
    else:
        user_id_col = sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
        frequent_foods_col = sa.Column(
            "frequent_foods", sa.Text(), nullable=False, server_default="[]"
        )
        avoided_tags_col = sa.Column(
            "avoided_tags", sa.Text(), nullable=False, server_default="[]"
        )
        avg_daily_macros_col = sa.Column("avg_daily_macros", sa.Text(), nullable=True)
        updated_at_col = sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )

    op.create_table(
        "user_food_profile",
        user_id_col,
        frequent_foods_col,
        avoided_tags_col,
        avg_daily_macros_col,
        updated_at_col,
    )


def downgrade() -> None:
    op.drop_table("user_food_profile")

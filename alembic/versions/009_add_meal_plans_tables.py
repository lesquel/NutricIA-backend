"""Add meal_plans and planned_meals tables.

Revision ID: 009
Revises: 008
Create Date: 2026-04-15 00:00:00.000000

Changes:
- Add meal_plans table for weekly nutrition plans
- Add planned_meals table for individual scheduled meals
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_plans",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("target_calories", sa.Integer(), nullable=False),
        sa.Column("target_macros", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.VARCHAR(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "approximation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "week_start", name="uq_meal_plans_user_week"),
    )

    op.create_table(
        "planned_meals",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "plan_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("meal_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("meal_type", sa.VARCHAR(20), nullable=False),
        sa.Column("recipe_name", sa.VARCHAR(255), nullable=False),
        sa.Column("recipe_ingredients", sa.JSON(), nullable=False),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("macros", sa.JSON(), nullable=False),
        sa.Column("cook_time_minutes", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.VARCHAR(20), nullable=True),
        sa.Column(
            "servings",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "is_logged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "logged_meal_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("meals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_planned_meals_plan_id_day_of_week",
        "planned_meals",
        ["plan_id", "day_of_week"],
    )


def downgrade() -> None:
    op.drop_index("ix_planned_meals_plan_id_day_of_week", table_name="planned_meals")
    op.drop_table("planned_meals")
    op.drop_table("meal_plans")

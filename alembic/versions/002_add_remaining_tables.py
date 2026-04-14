"""Add remaining tables.

Revision ID: 002
Revises: 001
Create Date: 2026-04-13 00:00:00.000000

Changes:
- Create habits table
- Create habit_check_ins table
- Create water_intake table
- Create meals table
- Create meal_tags table
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not insp.has_table("habits"):
        op.create_table(
            "habits",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("icon", sa.String(50), nullable=False),
            sa.Column("plant_type", sa.String(50), nullable=False),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column("streak_days", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_habits_user_id", "habits", ["user_id"])

    if not insp.has_table("habit_check_ins"):
        op.create_table(
            "habit_check_ins",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("habit_id", UUID(as_uuid=True), nullable=False),
            sa.Column("checked_at", sa.Date(), nullable=False),
            sa.ForeignKeyConstraint(["habit_id"], ["habits.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_habit_check_ins_habit_id", "habit_check_ins", ["habit_id"])

    if not insp.has_table("water_intake"):
        op.create_table(
            "water_intake",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("cups", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_water_intake_user_id", "water_intake", ["user_id"])

    if not insp.has_table("meals"):
        op.create_table(
            "meals",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("image_url", sa.String(512), nullable=True),
            sa.Column("calories", sa.Float(), nullable=False),
            sa.Column("protein_g", sa.Float(), nullable=False),
            sa.Column("carbs_g", sa.Float(), nullable=False),
            sa.Column("fat_g", sa.Float(), nullable=False),
            sa.Column("meal_type", sa.String(50), nullable=False),
            sa.Column("confidence_score", sa.Float(), nullable=False),
            sa.Column("ai_raw_response", sa.Text(), nullable=True),
            sa.Column(
                "logged_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_meals_user_id", "meals", ["user_id"])

    if not insp.has_table("meal_tags"):
        op.create_table(
            "meal_tags",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("meal_id", UUID(as_uuid=True), nullable=False),
            sa.Column("label", sa.String(100), nullable=False),
            sa.ForeignKeyConstraint(["meal_id"], ["meals.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_meal_tags_meal_id", "meal_tags", ["meal_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    for table in ("meal_tags", "meals", "water_intake", "habit_check_ins", "habits"):
        if insp.has_table(table):
            op.drop_table(table)

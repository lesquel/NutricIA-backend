"""Create baseline remaining tables (idempotent).

Revision ID: 003
Revises: 002
Create Date: 2026-04-15 00:00:00.000000

Changes:
- Idempotently creates tables that existed before Alembic was introduced:
  users (pre-001 schema), meals, meal_tags, habits, habit_check_ins, water_intake
- Uses has_table() checks so existing databases are not disturbed.
- downgrade() is a no-op to preserve existing data.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_col(name: str, **kwargs) -> sa.Column:
    """Return a UUID column that works on both postgres and sqlite."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.Column(name, PG_UUID(as_uuid=True), **kwargs)
    return sa.Column(name, sa.Uuid(as_uuid=True), **kwargs)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── users ────────────────────────────────────────────────────────────────
    # 001 already handles create-if-missing for users (including all columns).
    # We only need to ensure it exists here if somehow 001 was bypassed.
    if not inspector.has_table("users"):
        op.create_table(
            "users",
            _uuid_col("id", primary_key=True, nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("avatar_url", sa.String(512), nullable=True),
            sa.Column("password_hash", sa.String(255), nullable=True),
            sa.Column("provider", sa.String(50), nullable=True),
            sa.Column("provider_id", sa.String(255), nullable=True),
            sa.Column(
                "calorie_goal",
                sa.Integer(),
                nullable=False,
                server_default="2100",
            ),
            sa.Column(
                "water_goal_ml",
                sa.Integer(),
                nullable=False,
                server_default="2500",
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
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("email", name="uq_users_email"),
            sa.UniqueConstraint("provider_id", name="uq_users_provider_id"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_provider_id", "users", ["provider_id"], unique=True)

    # ── meals ────────────────────────────────────────────────────────────────
    if not inspector.has_table("meals"):
        op.create_table(
            "meals",
            _uuid_col("id", primary_key=True, nullable=False),
            _uuid_col(
                "user_id",
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("image_url", sa.String(512), nullable=True),
            sa.Column("calories", sa.Float(), nullable=False, server_default="0"),
            sa.Column("protein_g", sa.Float(), nullable=False, server_default="0"),
            sa.Column("carbs_g", sa.Float(), nullable=False, server_default="0"),
            sa.Column("fat_g", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "meal_type",
                sa.String(50),
                nullable=False,
                server_default="snack",
            ),
            sa.Column(
                "confidence_score",
                sa.Float(),
                nullable=False,
                server_default="0.0",
            ),
            sa.Column("ai_raw_response", sa.Text(), nullable=True),
            sa.Column(
                "logged_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("ix_meals_user_id", "meals", ["user_id"])

    # ── meal_tags ────────────────────────────────────────────────────────────
    if not inspector.has_table("meal_tags"):
        op.create_table(
            "meal_tags",
            _uuid_col("id", primary_key=True, nullable=False),
            _uuid_col(
                "meal_id",
                sa.ForeignKey("meals.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("label", sa.String(100), nullable=False),
        )
        op.create_index("ix_meal_tags_meal_id", "meal_tags", ["meal_id"])

    # ── habits ───────────────────────────────────────────────────────────────
    if not inspector.has_table("habits"):
        op.create_table(
            "habits",
            _uuid_col("id", primary_key=True, nullable=False),
            _uuid_col(
                "user_id",
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("icon", sa.String(50), nullable=False, server_default="eco"),
            sa.Column(
                "plant_type",
                sa.String(50),
                nullable=False,
                server_default="fern",
            ),
            sa.Column("level", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("streak_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("ix_habits_user_id", "habits", ["user_id"])

    # ── habit_check_ins ──────────────────────────────────────────────────────
    if not inspector.has_table("habit_check_ins"):
        op.create_table(
            "habit_check_ins",
            _uuid_col("id", primary_key=True, nullable=False),
            _uuid_col(
                "habit_id",
                sa.ForeignKey("habits.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("checked_at", sa.Date(), nullable=False),
        )
        op.create_index("ix_habit_check_ins_habit_id", "habit_check_ins", ["habit_id"])

    # ── water_intake ─────────────────────────────────────────────────────────
    if not inspector.has_table("water_intake"):
        op.create_table(
            "water_intake",
            _uuid_col("id", primary_key=True, nullable=False),
            _uuid_col(
                "user_id",
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("cups", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("date", sa.Date(), nullable=False),
        )
        op.create_index("ix_water_intake_user_id", "water_intake", ["user_id"])


def downgrade() -> None:
    # No-op: we never drop tables that may have pre-existing data.
    pass

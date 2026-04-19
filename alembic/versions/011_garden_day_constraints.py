"""Add day-level uniqueness to garden tables.

Revision ID: 011
Revises: 010
Create Date: 2026-04-19 00:00:00.000000

Prevents duplicate check-ins or water-log rows for the same (habit, day) or
(user, day) at the database level. The application layer already has a
fast-path idempotency check, but the constraint is the safety net.

Idempotent: skips creation if the constraint already exists. Downgrade drops
the constraints if present.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_HABIT_UQ = "uq_habit_check_ins_habit_id_checked_at"
_WATER_UQ = "uq_water_intake_user_id_date"


def _has_constraint(table: str, name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {uq["name"] for uq in inspector.get_unique_constraints(table)}
    return name in existing


def _deduplicate(table: str, partition_cols: list[str], keep_col: str) -> None:
    """Delete duplicate rows, keeping the latest per ``partition_cols``.

    Uses a portable CTE so it runs on both Postgres and SQLite dev DBs. The
    row selected to keep is the one with the highest ``keep_col`` value
    (normally ``id``), which preserves the most recent insert.
    """
    bind = op.get_bind()
    partition = ", ".join(partition_cols)
    # DELETE with ROW_NUMBER() CTE — supported by Postgres and SQLite 3.35+.
    sql = sa.text(
        f"""
        DELETE FROM {table}
        WHERE {keep_col} IN (
            SELECT {keep_col} FROM (
                SELECT {keep_col},
                       ROW_NUMBER() OVER (
                           PARTITION BY {partition}
                           ORDER BY {keep_col} DESC
                       ) AS rn
                FROM {table}
            ) ranked
            WHERE ranked.rn > 1
        )
        """
    )
    bind.execute(sql)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "habit_check_ins" in tables and not _has_constraint(
        "habit_check_ins", _HABIT_UQ
    ):
        _deduplicate("habit_check_ins", ["habit_id", "checked_at"], "id")
        op.create_unique_constraint(
            _HABIT_UQ,
            "habit_check_ins",
            ["habit_id", "checked_at"],
        )

    if "water_intake" in tables and not _has_constraint("water_intake", _WATER_UQ):
        _deduplicate("water_intake", ["user_id", "date"], "id")
        op.create_unique_constraint(
            _WATER_UQ,
            "water_intake",
            ["user_id", "date"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "water_intake" in tables and _has_constraint("water_intake", _WATER_UQ):
        op.drop_constraint(_WATER_UQ, "water_intake", type_="unique")

    if "habit_check_ins" in tables and _has_constraint(
        "habit_check_ins", _HABIT_UQ
    ):
        op.drop_constraint(_HABIT_UQ, "habit_check_ins", type_="unique")

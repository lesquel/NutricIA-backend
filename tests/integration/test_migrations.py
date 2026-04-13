"""Tests for schema management: lifespan and Alembic migrations.

Task 1.1: Verify lifespan does NOT call create_all.
Task 1.3: Verify alembic upgrade head creates all expected tables.
"""

import inspect as python_inspect
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect


EXPECTED_TABLES = {
    "users",
    "habits",
    "habit_check_ins",
    "water_intake",
    "meals",
    "meal_tags",
}


def _run_alembic_migrations(db_url: str) -> None:
    """Run all Alembic migrations against *db_url* using a **sync** engine.

    This bypasses env.py (which is async + reads settings) so that tests
    can point at a disposable SQLite file without touching the app config.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.runtime.environment import EnvironmentContext

    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    script = ScriptDirectory.from_config(alembic_cfg)
    engine = create_engine(db_url)

    with engine.begin() as connection:
        with EnvironmentContext(
            alembic_cfg,
            script,
            fn=lambda rev, context: script._upgrade_revs("head", rev),
            as_sql=False,
            destination_rev="head",
        ) as env:
            env.configure(connection=connection, target_metadata=None)
            with env.begin_transaction():
                env.run_migrations()

    engine.dispose()


class TestLifespanNoCreateAll:
    """Task 1.1: Lifespan MUST NOT call Base.metadata.create_all."""

    def test_lifespan_source_has_no_create_all(self) -> None:
        """The lifespan function source code must not contain create_all."""
        from app.main import lifespan

        source = python_inspect.getsource(lifespan)
        assert "create_all" not in source, (
            "lifespan still contains create_all — "
            "all schema changes must go through Alembic"
        )


class TestAlembicMigrations:
    """Task 1.3: Alembic upgrade head must create all expected tables."""

    def test_alembic_upgrade_head_creates_all_tables(self, tmp_path: Path) -> None:
        """Running alembic upgrade head on an empty SQLite DB creates all tables."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        _run_alembic_migrations(db_url)

        engine = create_engine(db_url)
        tables = set(sa_inspect(engine).get_table_names())
        engine.dispose()

        missing = EXPECTED_TABLES - tables
        assert not missing, f"Tables missing after migration: {missing}"

    def test_alembic_migrations_are_idempotent(self, tmp_path: Path) -> None:
        """Running upgrade head twice does not error (idempotent)."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        _run_alembic_migrations(db_url)
        # Second run should not raise
        _run_alembic_migrations(db_url)

        engine = create_engine(db_url)
        tables = set(sa_inspect(engine).get_table_names())
        engine.dispose()

        missing = EXPECTED_TABLES - tables
        assert not missing, f"Tables missing after second migration: {missing}"

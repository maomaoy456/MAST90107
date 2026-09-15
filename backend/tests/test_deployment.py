from pathlib import Path
import importlib.util

import yaml
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from app.db import Base


ROOT = Path(__file__).resolve().parents[2]


def test_compose_static_safety():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    api = compose["services"]["api"]
    assert "./datasets:/raw-data:ro" in api["volumes"]
    assert api["environment"]["RAW_DATA_ROOT"] == "/raw-data"
    for service in compose["services"].values():
        assert all(port.startswith("127.0.0.1:") for port in service.get("ports", []))
    assert "datasets" in (ROOT / ".dockerignore").read_text().splitlines()
    assert "datasets/" in (ROOT / ".gitignore").read_text().splitlines()


def test_migration_offline_without_credentials(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    command.upgrade(Config(str(ROOT / "backend" / "alembic.ini")), "head", sql=True)
    sql = capsys.readouterr().out
    assert "CREATE TABLE students" in sql
    assert "CREATE TABLE assessment_rules" in sql
    assert "CREATE TABLE model_runs" in sql
    assert "INSERT INTO assessment_rules" not in sql


def test_frozen_migration_schema_and_downgrade():
    path = ROOT / "backend" / "alembic" / "versions" / "0001_initial.py"
    spec = importlib.util.spec_from_file_location("initial_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            migration.op = Operations(context)
            migration.upgrade()
            assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables) - {"survey_responses", "support_cases", "offering_calendars"}
            # Initial migration is frozen; current-schema drift is checked on live MySQL.
            migration.downgrade()
            assert inspect(connection).get_table_names() == []
    finally:
        engine.dispose()

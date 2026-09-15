"""Opt-in live checks. Only an explicitly configured empty test database is used."""
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from dotenv import dotenv_values
from sqlalchemy import inspect, text, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.config import Settings, PROJECT_ROOT
from app.db import Base, build_engine, session_factory
from app.main import create_app
from app.seed import seed_rules


@pytest.mark.mysql
def test_mysql_migration_roundtrip_and_seed(monkeypatch, tmp_path):
    raw_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(PROJECT_ROOT / ".env").get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("Configure TEST_DATABASE_URL using the local MySQL setup command")
    url = make_url(raw_url)
    assert url.drivername == "mysql+pymysql"
    assert url.database and url.database.startswith("mpe_") and url.database.endswith("_test")
    engine = build_engine(Settings(database_url=raw_url, _env_file=None))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    monkeypatch.setenv("DATABASE_URL", raw_url)
    # Refuse any pre-existing tables. Cleanup below is authorized only after this gate.
    with engine.connect() as connection:
        assert inspect(connection).get_table_names() == [], "Test database must be empty"
    try:
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        with Session(engine) as session:
            with session.begin():
                seed_rules(session)
                seed_rules(session)
        with TestClient(create_app(Settings(database_url=raw_url, _env_file=None))) as client:
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.json() == {"application": "ok", "database": "ok"}
        command.downgrade(config, "base")
        with engine.connect() as connection:
            assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
        command.upgrade(config, "head")
        command.check(config)
        # Re-seed after the roundtrip, then exercise real import transactions.
        with Session(engine) as session:
            with session.begin():
                seed_rules(session)
        from test_ingestion import exercise_mysql_import
        exercise_mysql_import(session_factory(engine), tmp_path)
        # Validate rule writes on MySQL too, only inside this isolated test database.
        from app.models import Assignment, CourseOffering
        from app.db import get_session
        with Session(engine) as session:
            offering = session.scalar(select(CourseOffering))
            offering_code = offering.offering_code
            session.add(Assignment(offering_id=offering.id, source_key="RULE_TEST", name="Assessment", max_score=100))
            session.add(Assignment(offering_id=offering.id, source_key="RULE_TEST_2", name="Assessment 2", max_score=100))
            session.commit()
        api = create_app(Settings(database_url=raw_url, dashboard_api_key="mysql-test-api-key", _env_file=None))
        def test_session():
            with Session(engine) as session:
                yield session
        api.dependency_overrides[get_session] = test_session
        with TestClient(api) as client:
            body = {"version": "v1", "expected_version": "confirmed-v2", "pass_threshold": 70, "confirmed": True,
                    "components": [{"key": "AT1", "assignment_ref": "RULE_TEST", "weight": .4},
                                   {"key": "AT2", "assignment_ref": "RULE_TEST_2", "weight": .6}]}
            endpoint = "/api/v1/rules/" + offering_code
            headers = {"X-API-Key": "mysql-test-api-key"}
            assert client.put(endpoint, json=body, headers=headers).status_code == 200
            assert client.put(endpoint, json=body, headers=headers).status_code == 409
            assert client.put(endpoint, json=body | {"version": "v2", "expected_version": "v1"}, headers=headers).status_code == 200
    finally:
        # All objects are ours because the database was empty on entry.
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()

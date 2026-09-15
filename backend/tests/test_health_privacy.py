import json
import logging
import io

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.db import get_session
from app.logging import PrivacyFormatter, PrivacyHandler
from app.main import create_app

SECRET = "student-secret-987654"


@pytest.fixture
def app(session):
    app = create_app(Settings(database_url="mysql+pymysql://local:private@localhost/test", _env_file=None))
    app.dependency_overrides[get_session] = lambda: session
    return app


def test_health_ok(app):
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"application": "ok", "database": "ok"}


def test_database_unavailable_is_private(app, capsys):
    class BrokenSession:
        def execute(self, statement):
            raise OperationalError(SECRET, {"student_id": SECRET}, RuntimeError("password=" + SECRET))

    app.dependency_overrides[get_session] = BrokenSession
    with TestClient(app) as client:
        response = client.get("/api/v1/health?student_id=" + SECRET)
    assert response.status_code == 503
    assert response.json() == {"application": "ok", "database": "unavailable"}
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err + response.text


def test_errors_do_not_echo_inputs(app, capsys):
    @app.get("/test/{number}")
    def temporary_route(number: int):
        if number == 1:
            raise HTTPException(400, SECRET)
        raise RuntimeError(SECRET)

    with TestClient(app) as client:
        for path, status in [("/test/" + SECRET, 422), ("/test/1", 400), ("/test/2", 500), ("/" + SECRET, 404)]:
            response = client.get(path)
            assert response.status_code == status
            assert SECRET not in response.text
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err


def test_log_formatter_discards_arbitrary_details():
    record = logging.LogRecord(SECRET, logging.ERROR, SECRET, 5, SECRET, (), (RuntimeError, RuntimeError(SECRET), None))
    record.student_id = SECRET
    record.safe_event = SECRET
    record.safe_status = SECRET
    rendered = PrivacyFormatter().format(record)
    assert SECRET not in rendered
    assert json.loads(rendered)["event"] == "system_event"


def test_logging_output_failure_cannot_dump_original_message(capsys):
    stream = io.StringIO()
    handler = PrivacyHandler(stream)
    handler.setFormatter(PrivacyFormatter())
    stream.close()
    handler.handle(logging.LogRecord(SECRET, logging.ERROR, SECRET, 5, SECRET, (), None))
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err


def test_settings_hide_credentials_and_reject_other_databases():
    settings = Settings(database_url="mysql+pymysql://user:" + SECRET + "@localhost/mpe", _env_file=None)
    assert SECRET not in repr(settings)
    with pytest.raises(ValidationError) as exc:
        Settings(database_url="sqlite:///" + SECRET, _env_file=None)
    assert SECRET not in str(exc.value)


def test_no_student_routes(app):
    paths = app.openapi()["paths"]
    assert "/api/v1/health" in paths
    assert all("student" not in path for path in paths)

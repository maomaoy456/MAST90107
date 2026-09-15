"""Frontend-style HTTP tests using synthetic cohorts; never change real course rules."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import get_session
from app.main import create_app
from app.models import (Assignment, AssignmentSubmission, Course, CourseOffering,
                        EngagementEvent, ImportBatch, Student)
from app.seed import seed_rules
from sqlalchemy import select

KEY = "test-api-key-that-is-not-a-real-credential"
HEADERS = {"X-API-Key": KEY}
PAGES = ("overview", "engagement", "assignments", "outcomes", "insights", "data-rules")


def test_aggregate_counts_are_released_without_identity_fields():
    from app.dashboard.privacy import metric
    assert metric(20, set()).value == 20
    assert metric(20, set()).suppressed is False
    assert metric(0, set()).value == 0


@pytest.fixture
def dashboard(session):
    seed_rules(session)
    course = session.scalar(select(Course).where(Course.code == "0AUTI0001"))
    offering = CourseOffering(course_id=course.id, source_key="test", offering_code="0AUTI0001_2025_MAR_PAR_1")
    ab = ImportBatch(source="assignment", file_sha256="a" * 64, importer_version="test", status="completed", finished_at=datetime(2025, 1, 1))
    eb = ImportBatch(source="engagement", file_sha256="b" * 64, importer_version="test", status="completed", finished_at=datetime(2025, 1, 1))
    session.add_all([offering, ab, eb]); session.flush()
    items = [Assignment(offering_id=offering.id, source_key=key, name=key, max_score=maximum)
             for key, maximum in (("AT1", 100), ("AT2", 100), ("SELF", 0))]
    session.add_all(items); session.flush()
    for i in range(20):
        person = Student(identity_digest=f"private-test-identity-{i}")
        session.add(person); session.flush()
        for j, item in enumerate(items):
            session.add(AssignmentSubmission(batch_id=ab.id, student_id=person.id, assignment_id=item.id,
                source_row=2 + i * 3 + j, attempt=1, score=(55 if j == 0 else 80) if i < 10 else 40,
                status="graded", missing=False, source_fields={"points_possible": float(item.max_score)}))
        session.add(EngagementEvent(batch_id=eb.id, student_id=person.id, offering_id=offering.id,
            source_row=i + 2, event_type="page", times_viewed=60, participated_count=1))
    session.commit()
    app = create_app(Settings(database_url="mysql+pymysql://user:unused@localhost/test", dashboard_api_key=KEY, _env_file=None))
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield client, session, offering


def test_six_pages_and_catalog_contract(dashboard):
    client, _, _ = dashboard
    assert client.get("/api/v1/catalog", headers=HEADERS).json()["pages"] == list(PAGES)
    for name in PAGES:
        response = client.get("/api/v1/" + name, headers=HEADERS)
        assert response.status_code == 200
        result = response.json()
        assert result["page"] == name and isinstance(result["tables"], dict)
        assert "private-test-identity" not in response.text
        assert "student_id" not in response.text and "identity_digest" not in response.text
    assert client.get("/api/v1/overview", headers=HEADERS).json()["metrics"]["assignment_students"]["value"] == 20


def test_academic_tables_only_appear_on_relevant_pages(dashboard):
    client, _, _ = dashboard
    for page_name in ("overview", "assignments", "outcomes"):
        tables = client.get("/api/v1/" + page_name, headers=HEADERS).json()["tables"]
        assert {"academic_results", "weighted_grade_distribution"} <= tables.keys()
    engagement = client.get("/api/v1/engagement", headers=HEADERS).json()["tables"]
    assert "academic_results" not in engagement
    assert "weighted_grade_distribution" not in engagement


@pytest.mark.parametrize("query", ["student_id=private-test-identity", "course=X&course=Y", "mode=bad", "date_from=2025-01-01", "course='OR1=1"])
def test_invalid_filters_are_private(dashboard, query):
    client, _, _ = dashboard
    response = client.get("/api/v1/assignments?" + query, headers=HEADERS)
    assert response.status_code == 422
    assert response.json() == {"detail": "request_error"}


def test_auth_unknown_scope_and_cors(dashboard):
    client, _, _ = dashboard
    assert client.get("/api/v1/overview").status_code == 401
    assert client.get("/api/v1/overview", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/overview?course=UNKNOWN", headers=HEADERS).status_code == 404
    response = client.options("/api/v1/overview", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "X-API-Key"})
    assert response.status_code == 200 and response.headers["access-control-allow-origin"] == "http://localhost:5173"
    response = client.options("/api/v1/overview", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in response.headers


def test_modes_and_explicit_weight_confirmation(dashboard):
    client, _, offering = dashboard
    params = {"offering": offering.offering_code}
    response = client.get("/api/v1/assignments", params=params, headers=HEADERS).json()
    assert "weighted_outcomes" not in response["tables"]
    body = {"version": "v1", "expected_version": "confirmed-v2", "pass_threshold": 70,
        "confirmed": True, "components": [{"assignment_ref": "AT1", "key": "AT1", "weight": .4},
                                          {"assignment_ref": "AT2", "key": "AT2", "weight": .6}]}
    endpoint = "/api/v1/rules/" + offering.offering_code
    assert client.put(endpoint, json=body, headers=HEADERS).status_code == 200
    result = client.get("/api/v1/assignments", params=params, headers=HEADERS).json()
    assert result["tables"]["academic_results"][0]["metrics"]["passed"]["value"] == 10
    assert client.put(endpoint, json=body, headers=HEADERS).status_code == 409
    wrong = body | {"version": "v2", "expected_version": "v1", "components": [{"assignment_ref": "SELF", "key": "AT1", "weight": 1}]}
    assert client.put(endpoint, json=wrong, headers=HEADERS).status_code == 422
    for mode in ("scored", "self_assessment", "combined"):
        result = client.get("/api/v1/assignments", params=params | {"mode": mode}, headers=HEADERS)
        assert result.status_code == 200
        if mode == "self_assessment":
            assert all(r["metrics"]["mean_score_pct"]["value"] is None for r in result.json()["tables"]["assessments"])


def test_small_source_complement_remains_aggregate_and_visible(dashboard):
    client, session, offering = dashboard
    from sqlalchemy import delete
    person = session.scalar(select(EngagementEvent.student_id))
    session.execute(delete(EngagementEvent).where(EngagementEvent.student_id == person)); session.commit()
    for page in ("overview", "engagement", "assignments", "insights"):
        response = client.get("/api/v1/" + page, headers=HEADERS)
        assert "student_id" not in response.text and "identity_digest" not in response.text
        assert all(not metric["suppressed"] for metric in response.json()["metrics"].values())
    overview = client.get("/api/v1/overview", headers=HEADERS).json()
    assert overview["metrics"]["assignment_students"]["value"] == 20
    assert overview["metrics"]["engagement_students"]["value"] == 19


@pytest.mark.parametrize("patch", [
    {"components": [{"assignment_ref": "AT1", "key": "AT1", "weight": .9}]},
    {"components": [{"assignment_ref": "AT1", "key": "AT1", "weight": .5}, {"assignment_ref": "AT1", "key": "AT2", "weight": .5}]},
    {"pass_threshold": 101}, {"confirmed": False}, {"student_id": "must-not-echo"},
])
def test_invalid_rule_body_does_not_mutate(dashboard, patch):
    client, _, offering = dashboard
    body = {"version": "v1", "expected_version": "confirmed-v2", "pass_threshold": 70,
        "confirmed": True, "components": [{"assignment_ref": "AT1", "key": "AT1", "weight": 1}]}
    before = client.get("/api/v1/rules", headers=HEADERS).json()
    response = client.put("/api/v1/rules/" + offering.offering_code, json=body | patch, headers=HEADERS)
    assert response.status_code == 422 and "must-not-echo" not in response.text
    assert client.get("/api/v1/rules", headers=HEADERS).json() == before


def test_missing_sources_are_unknown_not_zero(session):
    app = create_app(Settings(database_url="mysql+pymysql://user:unused@localhost/test", dashboard_api_key=KEY, _env_file=None))
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        for page in ("engagement", "assignments", "outcomes", "insights"):
            response = client.get("/api/v1/" + page, headers=HEADERS)
            assert response.status_code == 200
            assert all(m["value"] is None for m in response.json()["metrics"].values())


def test_database_failure_has_frontend_retry_status(dashboard):
    client, _, _ = dashboard
    from sqlalchemy.exc import OperationalError
    class BrokenSession:
        def scalars(self, *args):
            raise OperationalError("private-student-detail", {}, RuntimeError("private-password"))
    client.app.dependency_overrides[get_session] = BrokenSession
    response = client.get("/api/v1/overview", headers=HEADERS)
    assert response.status_code == 503
    assert response.json() == {"detail": "database_unavailable"}


def test_badges_resolve_from_engagement_without_course_dates(dashboard):
    client, session, offering = dashboard
    from app.models import BadgeAward, BadgeClass, BadgeClassCourseMapping
    batch = ImportBatch(source="badge", file_sha256="c" * 64, importer_version="test", status="completed", finished_at=datetime(2025, 1, 1))
    badge_class = BadgeClass(name="PBS: Autism Affirming Practice")
    session.add_all([batch, badge_class]); session.flush()
    session.add(BadgeClassCourseMapping(badge_class_id=badge_class.id, course_id=offering.course_id, status="confirmed", mapping_version="test"))
    for i, student in enumerate(session.scalars(select(Student))):
        session.add(BadgeAward(batch_id=batch.id, source_row=i + 2, badge_class_id=badge_class.id,
            student_id=student.id, revoked=False, match_status="manual_review", outcome="unknown"))
    session.commit()
    response = client.get("/api/v1/outcomes", params={"offering": offering.offering_code}, headers=HEADERS)
    assert response.json()["metrics"]["valid_award_holders"]["value"] == 20
    assert response.json()["metrics"]["badge_completion_rate_pct"]["value"] == 100

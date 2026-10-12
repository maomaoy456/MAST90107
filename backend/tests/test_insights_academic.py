"""Reviewed grading, independent awards and the Summary page contract."""
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from test_dashboard import dashboard, HEADERS
from app.models import Assignment, AssignmentSubmission, AssessmentRule, Course, CourseOffering
from app.models import ImportBatch, BadgeClass, BadgeClassCourseMapping, BadgeAward
from app.seed import seed_rules, CONFIG_PATH
from app.dashboard.data import Snapshot
from app.dashboard.academic import academic_records, score_band


def confirmed(session, offering):
    items = list(session.scalars(select(Assignment).where(Assignment.offering_id == offering.id)))
    for item in items:
        if item.source_key in {"AT1", "AT2"}:
            item.assessment_key, item.mapping_status = item.source_key, "confirmed"
    session.commit()
    return items


def test_seed_upgrade_preserves_history_and_reviewed_aliases(session):
    seed_rules(session, Path(CONFIG_PATH).with_name("assessment_rules.v1.json"))
    course = session.scalar(select(Course).where(Course.code == "0UNDE0001"))
    offering = CourseOffering(course_id=course.id, source_key="legacy", offering_code="0UNDE0001_TEST")
    session.add(offering); session.flush()
    assignment = Assignment(offering_id=offering.id, source_key="a", name="Assessment 1: Why treaty?  (40%)", max_score=100)
    self_activity = Assignment(offering_id=offering.id, source_key="self", name=assignment.name, max_score=0)
    session.add_all([assignment, self_activity]); session.flush()
    seed_rules(session); seed_rules(session)
    rules = list(session.scalars(select(AssessmentRule)))
    assert len(rules) == 4
    assert all(rule.enabled == (rule.version == "confirmed-v2") for rule in rules)
    assert assignment.assessment_key == "AT1" and assignment.mapping_status == "confirmed"
    assert self_activity.assessment_key is None


def test_exact_weighted_boundary_missing_scores_and_relevant_pages(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    rows = list(session.scalars(select(AssignmentSubmission).order_by(AssignmentSubmission.student_id)))
    people = sorted({row.student_id for row in rows})
    for row in rows:
        index = people.index(row.student_id)
        row.score = Decimal("70") if index < 5 else Decimal("69.9999") if index < 10 else Decimal("80") if index < 15 else None
    session.commit()
    records = academic_records(Snapshot(session), {offering.id})
    assert sum(record["state"] == "pass" for record in records.values()) == 10
    assert sum(record["state"] == "below_threshold" for record in records.values()) == 5
    assert sum(record["state"] == "unknown" for record in records.values()) == 5
    for page in ("overview", "assignments"):
        result = client.get("/api/v1/" + page, headers=HEADERS).json()
        metrics = result["tables"]["academic_results"][0]["metrics"]
        assert metrics["passed"]["value"] == 10
        assert metrics["unknown"]["value"] == 5
        assert metrics["pass_rate_among_complete_pct"]["value"] == pytest.approx(100 * 10 / 15, abs=.0001)
    assert [score_band(Decimal(value)) for value in ("69.9999", "70", "79.9999", "80")] == [
        "below_70", "70_to_below_80", "70_to_below_80", "80_and_above"]


def test_incomplete_component_not_renormalized_and_selection_does_not_change_final(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    first = session.scalar(select(AssignmentSubmission).join(Assignment).where(Assignment.source_key == "AT2"))
    first.score = None
    session.commit()
    records = academic_records(Snapshot(session), {offering.id})
    assert records[(first.student_id, offering.id)]["final"] is None
    whole = client.get("/api/v1/assignments", headers=HEADERS).json()
    one = client.get("/api/v1/assignments", params={"assignments": "AT1"}, headers=HEADERS).json()
    assert whole["tables"]["academic_results"] == one["tables"]["academic_results"]
    metrics = one["tables"]["academic_results"][0]["metrics"]
    assert metrics["complete_grades"]["value"] == 19 and metrics["unknown"]["value"] == 1


def test_displayed_weighted_rule_uses_effective_configuration(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    rule = Snapshot(session).rule(offering)
    for first, second, threshold in ((.4, .6, 70), (.2, .8, 75), (.5, .5, 60)):
        rule.components = [{"key": "AT1", "weight": first}, {"key": "AT2", "weight": second}]
        rule.pass_threshold = threshold
        session.commit()
        row = client.get("/api/v1/assignments", headers=HEADERS).json()["tables"]["academic_results"][0]
        assert row["dimensions"]["calculation_rule"] == f"AT1 {first * 100:g}% + AT2 {second * 100:g}%"
        assert float(row["dimensions"]["pass_threshold_pct"]) == threshold


def test_ambiguous_component_is_not_silently_chosen(dashboard):
    _, session, offering = dashboard
    confirmed(session, offering)
    item = Assignment(offering_id=offering.id, source_key="DUP", name="Assessment 1", max_score=100,
        assessment_key="AT1", mapping_status="confirmed")
    session.add(item); session.flush()
    source = session.scalar(select(AssignmentSubmission))
    session.add(AssignmentSubmission(batch_id=source.batch_id, student_id=source.student_id, assignment_id=item.id,
        source_row=1000, score=100, status="graded", source_fields={"points_possible": 100}))
    session.commit()
    assert all(record["final"] is None for record in academic_records(Snapshot(session), {offering.id}).values())


def test_summary_contract_has_only_pass_and_badge_targets(dashboard):
    client, _, _ = dashboard
    response = client.get("/api/v1/insights", headers=HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert {row["key"] for row in payload["tables"]["analysis_options"]} == {"pass", "badge"}
    assert "associations" not in payload["tables"] and "analysis_questions" not in payload["tables"]
    assert all("AT1/AT2 submission" in row["dimensions"]["excluded_predictors"]
               for row in payload["tables"]["analysis_options"])


def test_badge_revocation_does_not_change_academic_pass(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    batch = ImportBatch(source="badge", file_sha256="c" * 64, importer_version="test", status="completed", finished_at=datetime(2025, 1, 1))
    badge = BadgeClass(name="Test badge")
    session.add_all([batch, badge]); session.flush()
    session.add(BadgeClassCourseMapping(badge_class_id=badge.id, course_id=offering.course_id, status="confirmed", mapping_version="test"))
    students = sorted({row.student_id for row in session.scalars(select(AssignmentSubmission))})
    for index, student in enumerate(students):
        session.add(BadgeAward(batch_id=batch.id, source_row=index + 2, badge_class_id=badge.id, student_id=student,
            revoked=index < 5, match_status="manual_review", outcome="unknown"))
    session.commit()
    result = client.get("/api/v1/assignments", headers=HEADERS).json()
    assert result["tables"]["academic_results"][0]["metrics"]["passed"]["value"] == 10
    assert result["metrics"]["active_badge_students"]["value"] == 15
    assert result["metrics"]["revoked_badge_only_students"]["value"] == 5


@pytest.mark.parametrize("page,query", [
    ("insights", {"target": "weighted_final"}), ("overview", {"target": "pass"}),
    ("insights", {"assignments": "AT1"}), ("rules", {"target": "badge"}),
    ("assignment-options", {"target": "pass"}),
])
def test_target_filters_reject_unsupported_requests(dashboard, page, query):
    client, _, _ = dashboard
    assert client.get("/api/v1/" + page, params=query, headers=HEADERS).status_code == 422

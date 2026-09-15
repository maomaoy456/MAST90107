import json
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import Base
from app.models import AssessmentRule, BadgeAward, BadgeClass, Course, CourseOffering, ImportBatch, ImportErrorRecord, Student
from app.seed import CONFIG_PATH, Rule, seed_rules


def test_required_tables_present():
    assert set(Base.metadata.tables) == {
        "import_batches", "import_errors", "students", "courses", "course_offerings",
        "assignments", "engagement_events", "assignment_submissions", "badge_classes",
        "badge_awards", "badge_class_course_mapping", "assessment_rules", "model_runs",
        "offering_calendars", "survey_responses", "support_cases",
    }


def test_seed_idempotent_and_rules_exact(session):
    seed_rules(session)
    seed_rules(session)
    assert session.scalar(select(func.count()).select_from(Course)) == 2
    assert session.scalar(select(func.count()).select_from(AssessmentRule)) == 2
    rules = {code: rule for code, rule in session.execute(select(Course.code, AssessmentRule).join(AssessmentRule))}
    pbs = rules["0AUTI0001"]
    assert pbs.enabled and pbs.status == "confirmed"
    assert pbs.pass_threshold == Decimal("70")
    assert pbs.components == [{"key": "AT1", "weight": "0.40"}, {"key": "AT2", "weight": "0.60"}]
    treaty = rules["0UNDE0001"]
    assert treaty.enabled and treaty.status == "confirmed"
    assert treaty.components == pbs.components
    assert len(pbs.config_sha256) == 64


def test_seed_rejects_same_version_edits(session, tmp_path):
    seed_rules(session)
    session.commit()
    config = json.loads(CONFIG_PATH.read_text())
    config["courses"][0]["rule"]["pass_threshold"] = 71
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="Immutable seed conflict"):
        seed_rules(session, changed)
    session.rollback()
    assert session.scalar(select(AssessmentRule.pass_threshold).where(AssessmentRule.enabled.is_(True))) == Decimal("70")


def test_seed_detects_database_drift(session):
    seed_rules(session)
    rule = session.scalar(select(AssessmentRule).where(AssessmentRule.enabled.is_(True)))
    rule.pass_threshold = Decimal("71")
    session.flush()
    with pytest.raises(ValueError, match="Immutable seed conflict"):
        seed_rules(session)


@pytest.mark.parametrize("change", [
    {"status": "candidate", "enabled": True},
    {"components": [{"key": "AT1", "weight": "0.4"}]},
    {"components": [{"key": "AT1", "weight": "0.4"}, {"key": "AT1", "weight": "0.6"}]},
    {"components": []}, {"pass_threshold": 101},
])
def test_invalid_rule_configuration(change):
    data = json.loads(CONFIG_PATH.read_text())["courses"][0]["rule"]
    with pytest.raises(ValidationError):
        Rule.model_validate(data | change)


def test_database_rejects_enabled_candidate(session):
    seed_rules(session)
    rule = session.scalar(select(AssessmentRule))
    rule.status = "candidate"
    rule.enabled = True
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("missing_student,revoked", [(True, False), (False, True)])
def test_badge_invalid_success_rejected(session, missing_student, revoked):
    batch = ImportBatch(source="badge", file_sha256="a" * 64, importer_version="test")
    badge = BadgeClass(name="Test badge")
    student = Student(identity_digest="b" * 64)
    course = Course(code="TEST", name="Test")
    session.add_all([batch, badge, student, course])
    session.flush()
    offering = CourseOffering(course_id=course.id, source_key="test", status="completed")
    session.add(offering)
    session.flush()
    session.add(BadgeAward(batch_id=batch.id, source_row=1, badge_class_id=badge.id,
                           student_id=None if missing_student else student.id, offering_id=offering.id,
                           revoked=revoked, match_status="matched", outcome="achieved"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_multiple_disabled_versions_but_only_one_enabled(session):
    seed_rules(session)
    original = session.scalar(select(AssessmentRule).where(AssessmentRule.enabled.is_(True)))
    for version in ("history-1", "history-2"):
        session.add(AssessmentRule(course_id=original.course_id, version=version,
            status="confirmed", enabled=False, pass_threshold=70,
            components=original.components, evidence="test", config_sha256="a" * 64))
    session.flush()
    another = session.scalar(select(AssessmentRule).where(AssessmentRule.version == "history-1"))
    another.enabled = True
    with pytest.raises(IntegrityError):
        session.flush()


def test_import_errors_reject_free_text(session):
    batch = ImportBatch(source="assignment", file_sha256="a" * 64, importer_version="test")
    session.add(batch)
    session.flush()
    session.add(ImportErrorRecord(batch_id=batch.id, row_number=1, code="student-id-should-not-be-here"))
    with pytest.raises(IntegrityError):
        session.flush()

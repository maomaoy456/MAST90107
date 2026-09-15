from datetime import date, datetime

import pandas as pd
import pytest
from sqlalchemy import func, select

from app.ingestion.adapters import assignment, engagement
from app.ingestion.normalize import InvalidValue, boolean, identity, timestamp
from app.ingestion.readers import source_fields
from app.ingestion.report import build_report
from app.ingestion.service import import_file, badge_import_status
from app.models import Assignment, AssignmentSubmission, EngagementEvent, ImportErrorRecord


def test_melbourne_dates_and_explicit_utc():
    assert timestamp(45759) == datetime(2025, 4, 11, 14)
    assert timestamp("2025-01-15 12:00") == datetime(2025, 1, 15, 1)
    assert timestamp("2025-07-15 12:00") == datetime(2025, 7, 15, 2)
    assert timestamp("2025-01-15T12:00:00Z") == datetime(2025, 1, 15, 12)
    assert timestamp(None) is None


def test_verification_tolerates_only_tiny_json_float_roundoff():
    from app.ingestion.verify import equivalent
    assert equivalent({"time": 45759.5}, {"time": 45759.50000000001})
    assert not equivalent({"time": 45759.5}, {"time": 45759.50001})


@pytest.mark.parametrize("value", ["2025-10-05 02:30", "2025-04-06 02:30", "not-a-date"])
def test_ambiguous_or_invalid_dates_are_quarantined(value):
    with pytest.raises(InvalidValue, match="invalid_date"):
        timestamp(value)


def test_null_attempt_and_separate_flags():
    row = {"submission_status": "unsubmitted", "attempt": None, "score": None, "missing": False}
    result = assignment(row)
    assert result["attempt"] is None and result["status"] == "unsubmitted"
    assert result["missing"] is False and result["score"] is None


def test_identity_and_free_text_are_not_copied():
    raw = {"Student_ID_anonymised": "private-value", "Narrative": "private-value", "Badge Class Name": "Test"}
    assert "private-value" not in str(source_fields(raw, "badge"))
    assert identity(" private-value ", "key-one") == identity("private-value", "key-one")
    assert identity("private-value", "key-one") != identity("private-value", "key-two")
    assert boolean(None) is None


def test_reversed_view_dates_preserve_counts_and_raw_values():
    row = {"resource_type": "page", "start_date": 45759, "times_viewed": 3,
           "participated_count": 1, "first_viewed": 45760, "last_viewed": 45759}
    result = engagement(row)
    assert result["first_viewed_at"] is None and result["last_viewed_at"] is None
    assert result["times_viewed"] == 3
    assert result["source_fields"]["first_viewed"] == 45760
    assert result["source_fields"]["_quality_issues"] == ["view_interval:reversed"]
    assert result["first_viewed_on"] == date(2025, 4, 12)
    assert result["occurred_at"] is None


def test_source_name_intake_does_not_invent_start_day():
    from app.ingestion.offering import parse_offering
    fields = parse_offering("0UNDE0001_2025_MAR_PAR_4", "0UNDE0001_2025_MAR_PAR_4_Canvas.csv")
    assert fields["intake_year"] == 2025 and fields["intake_month"] == 3
    assert fields["cohort_label"] == "PAR_4" and "starts_on" not in fields
    with pytest.raises(InvalidValue):
        parse_offering("0UNDE0001_2025_MAR_PAR_4", "different_Canvas.csv")


def test_badge_import_does_not_infer_offering_from_dates():
    values = {"revoked": False, "awarded_at": datetime(2025, 6, 1)}
    assert badge_import_status(values, 1)["outcome"] == "unknown"
    assert badge_import_status(values, 1)["offering_id"] is None
    assert badge_import_status(values, None)["outcome"] == "ineligible"
    assert badge_import_status(dict(values, revoked=True), 1)["match_status"] == "revoked"


def exercise_mysql_import(factory, tmp_path):
    """Called inside the existing isolated MySQL integration test's cleanup boundary."""
    key = "test-only-key-that-is-at-least-32-characters"
    row = {"Student_ID_anonymised": "test-person", "course_canvas_id": "test-offering",
        "course_sis_id": "0AUTI0001_TEST", "course_name": "PBS: Autism Affirming Practice",
        "assignment_id": "test-self", "assignment_name": "Self-assessment",
        "points_possible": 0, "submission_status": "unsubmitted", "attempt": None,
        "score": None, "missing": False, "created_at": "2025-01-15T12:00:00Z"}
    path = tmp_path / "assignment.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    assert import_file(factory, path, "assignment", key) == "completed"
    assert import_file(factory, path, "assignment", key) == "already_imported"
    from app.ingestion.verify import verify_file
    assert verify_file(factory, path, "assignment", key)
    with factory() as session:
        sub = session.scalar(select(AssignmentSubmission))
        assert sub.attempt is None and sub.missing is False and sub.status == "unsubmitted"
        assert session.scalar(select(Assignment.max_score)) == 0
        assert "Student_ID_anonymised" not in sub.source_fields
        assert session.scalar(select(func.count()).select_from(AssignmentSubmission)) == 1
        assert build_report(session)["students"]["assignment"] == {"value": 1, "suppressed": False}
    # Bad rows are counted, and valid rows in the same file remain importable.
    e = {"Student_ID_anonymised": "test-person", "canvas_subject_id": "test-offering",
         "subject_code": "0AUTI0001_TEST", "subject_name": "PBS: Autism Affirming Practice",
         "resource_type": "page", "start_date": 45759, "times_viewed": 2, "participated_count": 0}
    path2 = tmp_path / "engagement.xlsx"
    pd.DataFrame([e, e | {"times_viewed": -1}]).to_excel(path2, index=False)
    assert import_file(factory, path2, "engagement", key) == "completed"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(EngagementEvent)) == 1
        assert session.scalar(select(ImportErrorRecord.code)) == "invalid_number"
    with pytest.raises(InvalidValue):
        import_file(factory, path2, "engagement", "different-key")
    # A fatal mid-file failure must roll back all observations, then allow a clean retry.
    from unittest.mock import patch
    path3 = tmp_path / "assignment-new.csv"
    pd.DataFrame([row, row | {"Student_ID_anonymised": "test-person-two"}]).to_csv(path3, index=False)
    with patch("app.ingestion.adapters.assignment", side_effect=[assignment(row), RuntimeError("private-detail")]):
        with pytest.raises(InvalidValue, match="^invalid_row$"):
            import_file(factory, path3, "assignment", key)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AssignmentSubmission)) == 1
    assert import_file(factory, path3, "assignment", key) == "completed"
    assert verify_file(factory, path3, "assignment", key)

"""Model cutoffs, eligibility, grouped evaluation, persistence and API control."""
from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy import select

from app.config import Settings
from app.dashboard.data import Snapshot
from app.modeling.features import behavior, build_training_data
from app.modeling.training import artifact_valid, load_model, train
from app.models import Assignment, AssignmentSubmission, EngagementEvent, ImportBatch
from test_dashboard import dashboard, HEADERS


def prepare_grade_model(session, offering):
    offering.starts_on, offering.ends_on = date(2025, 1, 1), date(2025, 3, 31)
    assignments = {a.source_key: a for a in session.scalars(select(Assignment).where(Assignment.offering_id == offering.id))}
    for key in ("AT1", "AT2"):
        assignments[key].assessment_key, assignments[key].mapping_status = key, "confirmed"
    people = sorted({r.student_id for r in session.scalars(select(AssignmentSubmission))})
    for row in session.scalars(select(AssignmentSubmission)):
        index = people.index(row.student_id)
        if row.assignment_id in {assignments['AT1'].id, assignments['AT2'].id}:
            row.score = 60 if index < 6 else 75 if index < 13 else 85
            row.source_fields = {**(row.source_fields or {}), "due_at": "2025-02-15T12:00:00Z"}
            row.graded_at = datetime(2025, 2, 20)
        else:
            row.source_fields = {**(row.source_fields or {}), "due_at": "2025-02-01T12:00:00Z"}
            row.submitted_at = datetime(2025, 1, 20)
    for row in session.scalars(select(EngagementEvent)):
        row.first_viewed_on = date(2025, 1, 5)
        row.first_viewed_at = datetime(2025, 1, 5)
        row.last_viewed_at = datetime(2025, 1, 6)
        row.times_viewed = 10 + people.index(row.student_id)
    session.commit()


def test_spanning_activity_never_uses_future_totals():
    cutoff = datetime(2025, 2, 1)
    event = SimpleNamespace(first_viewed_at=datetime(2025, 1, 1), first_viewed_on=date(2025, 1, 1),
        last_viewed_at=datetime(2025, 3, 1), times_viewed=999, participated_count=99, event_type="page")
    offering = SimpleNamespace(starts_on=date(2025, 1, 1))
    result = behavior([event], offering, cutoff)
    assert result["resources_touched"] == 1 and result["spanning_resource_count"] == 1
    assert result["safe_views"] == 0 and result["safe_participations"] == 0


def test_training_persists_one_pipeline_and_is_idempotent(dashboard, tmp_path):
    _, session, offering = dashboard
    prepare_grade_model(session, offering)
    settings = Settings(database_url="mysql+pymysql://user:unused@localhost/test",
        dashboard_api_key="test", model_artifact_root=tmp_path, _env_file=None)
    run, current = train(session, settings, "0AUTI0001", "AT1")
    assert run.status == "completed" and not current
    assert set(run.metrics) == {"logistic_regression", "random_forest"}
    assert run.model_name in run.metrics and artifact_valid(run, settings)
    bundle, loaded = load_model(session, settings, "0AUTI0001", "AT1")
    assert loaded.id == run.id and set(bundle) == {"pipeline", "feature_names", "classes", "course", "target", "model_version", "data_sha256", "config_sha256"}
    assert bundle["classes"] == ["below_70", "70_to_below_80", "80_and_above"]
    again, current = train(session, settings, "0AUTI0001", "AT1")
    assert current and again.id == run.id
    assert len(list(tmp_path.glob("*.joblib"))) == 1


def test_new_snapshot_creates_new_version_without_replacing_old_on_shortage(dashboard, tmp_path):
    _, session, offering = dashboard
    prepare_grade_model(session, offering)
    settings = Settings(database_url="mysql+pymysql://user:unused@localhost/test", dashboard_api_key="test",
        model_artifact_root=tmp_path, _env_file=None)
    good, _ = train(session, settings, "0AUTI0001", "AT1")
    batch = session.scalar(select(ImportBatch).where(ImportBatch.source == "engagement"))
    batch.file_sha256 = "d" * 64
    for row in session.scalars(select(AssignmentSubmission).join(Assignment).where(Assignment.source_key == "AT1")):
        row.score = 85
    session.commit()
    short, _ = train(session, settings, "0AUTI0001", "AT1")
    assert short.status == "insufficient" and short.summary["reason"] == "missing_target_class"
    _, active = load_model(session, settings, "0AUTI0001", "AT1")
    assert active.id == good.id


def test_feature_cutoffs_and_badge_excludes_grade_values(dashboard):
    _, session, offering = dashboard
    prepare_grade_model(session, offering)
    data = Snapshot(session)
    grade = build_training_data(data, offering.course_id, "AT2", date(2026, 9, 2))
    assert "AT1_score_pct" in grade.feature_names
    badge = build_training_data(data, offering.course_id, "badge", date(2026, 9, 2))
    assert all("score" not in name.lower() for name in badge.feature_names)
    assert set(["AT1_submitted", "AT2_submitted"]) <= set(badge.feature_names)


def test_model_api_training_history_and_private_small_counts(dashboard, tmp_path):
    client, session, offering = dashboard
    client.app.state.settings.model_artifact_root = tmp_path
    prepare_grade_model(session, offering)
    response = client.post("/api/v1/models/train", headers=HEADERS,
        json={"course": "0AUTI0001", "target": "AT1"})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed" and result["artifact_available"]
    assert set(result["candidates"]) == {"logistic_regression", "random_forest"}
    assert "confusion_matrix" not in response.text and "student_id" not in response.text
    again = client.post("/api/v1/models/train", headers=HEADERS,
        json={"course": "0AUTI0001", "target": "AT1"}).json()
    assert again["already_current"] and again["id"] == result["id"]
    history = client.get("/api/v1/models", headers=HEADERS,
        params={"course": "0AUTI0001", "target": "AT1"}).json()["runs"]
    assert len(history) == 1 and history[0]["data_current"]
    insight = client.get("/api/v1/insights", headers=HEADERS,
        params={"course": "0AUTI0001", "target": "AT1"})
    assert insight.status_code == 200
    assert insight.json()["tables"]["model_status"][0]["dimensions"]["status"] == "completed"
    assert client.get("/api/v1/models", headers=HEADERS, params={"unexpected": "x"}).status_code == 422
    assert client.post("/api/v1/models/train", headers=HEADERS,
        json={"course": "UNKNOWN", "target": "AT1"}).status_code == 404
    assert client.post("/api/v1/models/train", headers=HEADERS,
        json={"course": "0AUTI0001", "target": "unknown"}).status_code == 422

"""Internal aggregate inspection only; no student identifiers or row-level output."""
from sqlalchemy import func, select

from app.models import (AssignmentSubmission, BadgeAward, EngagementEvent,
                        ImportBatch)


def count(value):
    value = int(value)
    return {"value": value, "suppressed": False}


def build_report(session):
    batches = list(session.scalars(select(ImportBatch).order_by(ImportBatch.finished_at, ImportBatch.id)))
    latest = {b.source: b for b in batches if b.status == "completed" and b.scope == "global"}
    output = {"snapshot_policy": "latest_completed_per_source", "sources": {}}
    supplemental = {b.scope: b for b in batches if b.status == "completed" and b.scope != "global"}
    output["supplemental"] = {scope: {"accepted_rows": count((b.summary or {}).get("accepted_rows", 0)),
        "finished_at": b.finished_at.isoformat() + "Z" if b.finished_at else None} for scope, b in supplemental.items()}
    for source, batch in latest.items():
        info = batch.summary or {}
        output["sources"][source] = {"status": batch.status, "input_rows": count(batch.row_count),
            "accepted_rows": count(info.get("accepted_rows", 0)), "rejected_rows": count(info.get("rejected_rows", 0)),
            "warning_rows": count(info.get("warning_rows", 0))}
    def students(model, source):
        if source not in latest:
            return set()
        return set(session.scalars(select(model.student_id).where(model.batch_id == latest[source].id).distinct()))
    assignment, engagement = students(AssignmentSubmission, "assignment"), students(EngagementEvent, "engagement")
    output["students"] = {name: count(n) for name, n in {
        "assignment": len(assignment), "engagement": len(engagement), "intersection": len(assignment & engagement),
        "assignment_only": len(assignment - engagement), "engagement_only": len(engagement - assignment)}.items()}
    if "assignment" in latest:
        base = select(func.count()).select_from(AssignmentSubmission).where(AssignmentSubmission.batch_id == latest["assignment"].id)
        output["assignment_checks"] = {
            "null_attempts": count(session.scalar(base.where(AssignmentSubmission.attempt.is_(None)))),
            "unsubmitted": count(session.scalar(base.where(AssignmentSubmission.status == "unsubmitted"))),
            "missing_flag_true": count(session.scalar(base.where(AssignmentSubmission.missing.is_(True)))),
            "non_scored_rows": count(session.scalar(base.where(
                AssignmentSubmission.source_fields["points_possible"].as_float() == 0))),
        }
    if "badge" in latest:
        rows = session.execute(select(BadgeAward.match_status, func.count()).where(
            BadgeAward.batch_id == latest["badge"].id).group_by(BadgeAward.match_status))
        output["badge_import_eligibility"] = {status: count(n) for status, n in rows}
    output["failed_batches"] = count(sum(b.status == "failed" for b in batches))
    return output

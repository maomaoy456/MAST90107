"""One short adapter per source. Returns values ready for SQL persistence."""
from app.ingestion.normalize import InvalidValue, boolean, number, string, timestamp, calendar_date
from app.ingestion.readers import source_fields


def engagement(row):
    # Keep useful activity counts even when a timestamp is inconsistent.
    # Raw date values remain in source_fields; uncertain normalized dates become NULL.
    fields, issues, dates = source_fields(row, "engagement"), [], {}
    for name in ("start_date", "first_viewed", "last_viewed"):
        try:
            dates[name] = calendar_date(row.get(name)) if name == "start_date" else timestamp(row.get(name))
        except InvalidValue:
            dates[name] = None
            issues.append(name + ":invalid_date")
    first, last = dates["first_viewed"], dates["last_viewed"]
    if first and last and first > last:
        issues.append("view_interval:reversed")
        first = last = None
    if issues:
        fields["_quality_issues"] = issues
    return dict(event_type=string(row["resource_type"], required=True),
        first_viewed_on=dates["start_date"], occurred_at=None, first_viewed_at=first, last_viewed_at=last,
        times_viewed=number(row["times_viewed"], integer=True, minimum=0),
        participated_count=number(row["participated_count"], integer=True, minimum=0),
        source_fields=fields)


def assignment(row):
    status = string(row["submission_status"]) or "unknown"
    if status not in {"unknown", "unsubmitted", "missing", "submitted", "graded", "excused"}:
        raise InvalidValue("invalid_row")
    return dict(attempt=number(row["attempt"], integer=True, minimum=1),
        score=number(row["score"]), status=status,
        submitted_at=timestamp(row.get("submitted_at")), graded_at=timestamp(row.get("graded_at")),
        missing=boolean(row.get("missing")), late=boolean(row.get("late")), excused=boolean(row.get("excused")),
        source_fields=source_fields(row, "assignment"))


def badge(row):
    revoked = boolean(row["Revoked"])
    if revoked is None:
        raise InvalidValue("missing_required")
    return dict(awarded_at=timestamp(row["Issue Date"]), expires_at=timestamp(row.get("Expiration Date")),
        revoked=revoked, source_fields=source_fields(row, "badge"))

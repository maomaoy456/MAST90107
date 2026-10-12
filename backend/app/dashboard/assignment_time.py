"""Assignment deadline and cumulative submitted-student aggregates."""
from collections import defaultdict
from datetime import datetime, timezone

from app.dashboard.activity import bucket, group_guard, local_date
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric, partition
from app.ingestion.normalize import timestamp


def source_time(row, field):
    try:
        return timestamp((row.source_fields or {}).get(field))
    except (TypeError, ValueError):
        return None


def deadline(row):
    return source_time(row, "due_at")


def _representative_time(rows, getter):
    values = {getter(row) for row in rows if getter(row) is not None}
    return next(iter(values)) if len(values) == 1 else None


def _selected_groups(page, data, scope):
    from app.dashboard.assignments import selected_submissions
    rows = selected_submissions(data, scope, page.filters.mode)
    refs = set(page.filters.assignments.split(",")) if page.filters.assignments else None
    rows = [row for row in rows
            if refs is None or data.assignments[row.assignment_id].source_key in refs]
    groups = defaultdict(list)
    for row in rows:
        groups[row.assignment_id].append(row)
    return groups


def add_assignment_deadlines(page, data, scope):
    """Add AT1/AT2 deadline markers to Engagement timelines."""
    from app.dashboard.assignments import assignment_name, selected_submissions
    groups = defaultdict(list)
    for row in selected_submissions(data, scope, "scored"):
        groups[row.assignment_id].append(row)
    for assignment_id, rows in groups.items():
        assignment = data.assignments[assignment_id]
        if assignment.mapping_status != "confirmed" or not assignment.assessment_key:
            continue
        due_at = _representative_time(rows, deadline)
        if due_at is None:
            continue
        due_day = local_date(due_at)
        offering = data.offerings[assignment.offering_id]
        code = offering.offering_code or "unlabelled"
        page.tables.setdefault("assignment_deadlines", []).append(TableRow(
            key=f"{code}:{assignment.source_key}",
            label=assignment_name(assignment),
            dimensions={
                "offering": code,
                "assessment_key": assignment.assessment_key,
                "assignment_name": assignment_name(assignment),
                "deadline_date": due_day.isoformat(),
                "period": bucket(due_day, page.filters.interval),
                "unit": "Melbourne_calendar_date",
            },
            metrics={},
        ))


def add_assignment_time(page, data, scope):
    """Build cumulative submission curves from observed submissions around each deadline."""
    from app.dashboard.assignments import assignment_name
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
    indexed = _selected_groups(page, data, scope)
    for assignment_id, group in indexed.items():
        assignment = data.assignments[assignment_id]
        offering = data.offerings[assignment.offering_id]
        code = offering.offering_code or "unlabelled"
        due_at = _representative_time(group, deadline)
        due_day = local_date(due_at)
        days_after_course_end = ((due_day - offering.ends_on).days
                                 if due_day and offering.ends_on and due_day > offering.ends_on else 0)
        deadline_status = "source_date_after_course_end" if days_after_course_end else (
            "source_date_available" if due_day else "source_date_unavailable")
        dims = {
            "offering": code,
            "assignment_ref": assignment.source_key,
            "assignment_name": assignment_name(assignment),
            "assessment_key": assignment.assessment_key if assignment.mapping_status == "confirmed" else "unconfirmed",
            "deadline_date": due_day.isoformat() if due_day else "unknown",
            "deadline_status": deadline_status,
            "deadline_days_after_course_end": str(days_after_course_end),
            "unit": "elapsed_calendar_days",
        }
        key = f"{code}:{assignment.source_key}"
        members = {row.student_id for row in group}
        submitted = {
            row.student_id: local_date(row.submitted_at)
            for row in group
            if row.submitted_at is not None and row.submitted_at <= cutoff
            and row.status in {"submitted", "graded"} and not row.excused
        }
        if due_day is not None and submitted:
            elapsed = {student: (day - due_day).days for student, day in submitted.items()}
            checkpoints = set(elapsed.values())
            # When submissions begin before the deadline, retain Day 0 so the
            # chart shows how many students had submitted by the deadline.
            if min(checkpoints) <= 0:
                checkpoints.add(0)
            gate = group_guard([set(submitted)], members, data.privacy_reason({assignment.offering_id}))
            for days in sorted(checkpoints):
                people = {student for student, value in elapsed.items() if value <= days}
                point_day = due_day.fromordinal(due_day.toordinal() + days)
                page.tables.setdefault("assignment_cumulative_submission", []).append(TableRow(
                    key=f"{key}:{days}",
                    label=str(days),
                    dimensions=dims | {
                        "days_from_deadline": str(days),
                        "calendar_date": point_day.isoformat(),
                    },
                    metrics={
                        "submitted_students": metric(len(people), people, gate),
                        "total_students": metric(len(members), members, gate),
                        "submitted_pct": metric(100 * len(people) / len(members) if members else None, members, gate),
                    },
                ))
        page.tables.setdefault("assignment_schedule", []).append(TableRow(
            key=key,
            label=assignment_name(assignment),
            dimensions=dims,
            metrics={
                "total_students": metric(len(members), members),
                "submitted_students": metric(len(submitted), set(submitted)),
            },
        ))

    refs = set(page.filters.assignments.split(",")) if page.filters.assignments else None
    if len(scope) == 1:
        if refs and len(refs) == 2:
            selected_ids = [assignment_id for assignment_id in indexed
                            if data.assignments[assignment_id].source_key in refs]
        elif refs is None:
            by_component = {
                data.assignments[assignment_id].assessment_key: assignment_id
                for assignment_id in indexed
                if data.assignments[assignment_id].mapping_status == "confirmed"
                and data.assignments[assignment_id].assessment_key in {"AT1", "AT2"}
            }
            selected_ids = [by_component[key] for key in ("AT1", "AT2") if key in by_component]
        else:
            selected_ids = []
        if len(selected_ids) == 2:
            left, right = [{row.student_id: row for row in indexed[assignment_id]}
                           for assignment_id in selected_ids]
            eligible = left.keys() & right.keys()
            bins = {key: set() for key in
                    ("both_submitted", "first_only", "second_only", "neither_submitted")}
            for student in eligible:
                flags = [
                    row.status in {"submitted", "graded"}
                    and row.submitted_at is not None and row.submitted_at <= cutoff
                    for row in (left[student], right[student])
                ]
                bins["both_submitted" if all(flags) else "first_only" if flags[0]
                     else "second_only" if flags[1] else "neither_submitted"].add(student)
            gate = group_guard([set(eligible)], set(left) | set(right), data.privacy_reason(scope))
            for row in partition([(key, key, people) for key, people in bins.items()], reason=gate):
                row.dimensions = {
                    "first_assignment": data.assignments[selected_ids[0]].source_key,
                    "second_assignment": data.assignments[selected_ids[1]].source_key,
                    "unit": "students",
                }
                page.tables.setdefault("assignment_pair_submission", []).append(row)
    page.notes += [
        "Cumulative submission curves start on the first observed submission date. Day 0 is each assignment's source deadline; elapsed calendar days do not measure time spent working.",
        "A source deadline after the teaching period end is retained for audit, marked as requiring review and hidden by default in the interactive comparison.",
        "Pair comparison automatically uses confirmed AT1 and AT2 records when both are present in one teaching period.",
    ]

"""Recorded submission timing, not time spent working or historical reconstruction."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from app.dashboard.activity import group_guard
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric, partition
from app.ingestion.normalize import timestamp

OFFSETS = (-30, -14, -7, -3, -1, 0, 1, 3, 7, 14, 30)


def deadline(row):
    try:
        return timestamp((row.source_fields or {}).get("due_at"))
    except ValueError:
        return None


def add_assignment_time(page, data, scope):
    from app.dashboard.assignments import selected_submissions
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = selected_submissions(data, scope, page.filters.mode)
    refs = set(page.filters.assignments.split(",")) if page.filters.assignments else None
    rows = [r for r in rows if refs is None or data.assignments[r.assignment_id].source_key in refs]
    indexed = defaultdict(list)
    for row in rows:
        indexed[row.assignment_id].append(row)
    for assignment_id, group in indexed.items():
        assignment = data.assignments[assignment_id]
        code = data.offerings[assignment.offering_id].offering_code
        dims = {"offering": code, "assignment_ref": assignment.source_key, "as_of_utc": cutoff.isoformat() + "Z"}
        key = code + ":" + assignment.source_key
        members = {r.student_id for r in group}
        eligible = [r for r in group if deadline(r) is not None and deadline(r) <= cutoff]
        due = {r.student_id for r in eligible}
        pending = {r.student_id for r in group if deadline(r) is not None and deadline(r) > cutoff}
        unknown = members - due - pending
        base = data.privacy_reason({assignment.offering_id})
        gate = group_guard([due, pending, unknown], members, base)
        for row in partition([("due", "Deadline passed", due), ("not_yet_due", "Not yet due", pending),
                              ("unknown_deadline", "Unknown deadline", unknown)], reason=gate):
            row.dimensions = dims | {"status": row.key}
            row.key = key + ":" + row.key
            page.tables.setdefault("assignment_deadline_coverage", []).append(row)
        delays, waits = {}, {}
        bins = defaultdict(set)
        for row in eligible:
            if row.submitted_at is None or row.submitted_at > cutoff:
                band = "no_observed_submission"
            else:
                days = (row.submitted_at - deadline(row)).total_seconds() / 86400
                delays[row.student_id] = days
                band = "early_over_7d" if days < -7 else "early_1_7d" if days < -1 else "final_24h" if days <= 0 else "late_0_1d" if days <= 1 else "late_1_7d" if days <= 7 else "late_over_7d"
                if row.graded_at and row.submitted_at <= row.graded_at <= cutoff:
                    waits[row.student_id] = (row.graded_at - row.submitted_at).total_seconds() / 86400
            bins[band].add(row.student_id)
        timing_gate = group_guard(list(bins.values()), due, gate)
        final = {s for s, value in delays.items() if -1 <= value <= 0}
        page.tables.setdefault("assignment_time_summary", []).append(TableRow(key=key, label=assignment.source_key, dimensions=dims, metrics={
            "eligible_students": metric(len(due), due, gate),
            "final_24h_pct_among_submitted": metric(100 * len(final) / len(delays) if delays else None, set(delays), timing_gate),
            "median_days_relative_to_deadline": metric(median(delays.values()) if delays else None, set(delays), timing_gate),
            "grading_interval_n": metric(len(waits), set(waits), group_guard([set(waits)], due, gate)),
            "median_grading_days": metric(median(waits.values()) if waits else None, set(waits), group_guard([set(waits)], due, gate))}))
        for row in partition([(k, k, v) for k, v in bins.items()], reason=timing_gate):
            row.dimensions = dims | {"band": row.key}
            row.key = key + ":" + row.key
            page.tables.setdefault("assignment_submission_timing", []).append(row)
        curve = [{s for s, value in delays.items() if value <= offset} for offset in OFFSETS]
        curve_gate = group_guard(curve, due, timing_gate)
        for offset, submitted in zip(OFFSETS, curve):
            fully_observed = bool(eligible) and all(deadline(r) + timedelta(days=offset) <= cutoff for r in eligible)
            page.tables.setdefault("assignment_cumulative_submission", []).append(TableRow(key=key + ":" + str(offset), label=str(offset),
                dimensions=dims | {"days_relative_to_deadline": str(offset), "fully_observed": str(fully_observed).lower()}, metrics={
                    "submitted_pct": metric(100 * len(submitted) / len(due), due, curve_gate) if fully_observed else metric(None, set())}))
    # Pairing is opt-in, exactly two selected references in one offering. Students
    # without both exported records remain outside the paired denominator.
    if refs and len(refs) == 2 and len(scope) == 1:
        selected_ids = [i for i in indexed if data.assignments[i].source_key in refs]
        if len(selected_ids) == 2:
            left, right = [{r.student_id: r for r in indexed[i]} for i in selected_ids]
            eligible = {s for s in left.keys() & right.keys() if all(deadline(r) is not None and deadline(r) <= cutoff for r in (left[s], right[s]))}
            bins = {k: set() for k in ("both_submitted", "first_only", "second_only", "neither_submitted")}
            for s in eligible:
                a, b = [r.submitted_at is not None and r.submitted_at <= cutoff for r in (left[s], right[s])]
                bins["both_submitted" if a and b else "first_only" if a else "second_only" if b else "neither_submitted"].add(s)
            union = set(left) | set(right)
            gate = group_guard([eligible], union, data.privacy_reason(scope))
            for row in partition([(k, k, v) for k, v in bins.items()], reason=gate):
                row.dimensions = {"first_assignment": data.assignments[selected_ids[0]].source_key,
                                  "second_assignment": data.assignments[selected_ids[1]].source_key}
                page.tables.setdefault("assignment_pair_submission", []).append(row)
    page.notes += ["Timing uses recorded timestamps and source deadlines as of the current query time. Source late flags remain separate; missing deadlines do not become overdue.",
        "Cumulative curves keep all deadline-eligible records in the denominator. Points without complete follow-up are unknown. Overwritten historical exports cannot be reconstructed.",
        "Grading interval is submission-to-grading, not verified feedback release. Pair comparison requires two explicitly selected assignments in one offering, both deadlines passed and both records present."]

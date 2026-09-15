"""Per-assignment statistics; weighted components require reviewed mappings."""
from collections import defaultdict
from statistics import mean
from decimal import Decimal
from fastapi import HTTPException
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric, partition
from app.dashboard.activity import group_guard
import math
import re


def exact_percentage(submission):
    fields = submission.source_fields or {}
    maximum = fields.get("points_possible")
    if submission.status != "graded" or submission.excused or submission.missing or submission.score is None or not maximum:
        return None
    score = Decimal(str(submission.score)) / Decimal(str(maximum)) * 100
    return score if 0 <= score <= 100 else None


def percentage(submission):
    score = exact_percentage(submission)
    return float(score) if score is not None else None


def selected_submissions(data, scope, mode="combined"):
    latest = {}
    for row in data.submissions:
        if data.assignments[row.assignment_id].offering_id not in scope:
            continue
        maximum = (row.source_fields or {}).get("points_possible")
        if mode == "scored" and not (maximum is not None and maximum > 0):
            continue
        if mode == "self_assessment" and maximum != 0:
            continue
        key = (row.student_id, row.assignment_id)
        if key not in latest or (row.attempt or -1, row.source_row) > (latest[key].attempt or -1, latest[key].source_row):
            latest[key] = row
    return list(latest.values())


def assignment_name(assignment):
    # Course-authored assessment headings only. Arbitrary future free text stays private.
    name = assignment.name.strip()
    if re.match(r"^(?:Assessment(?: Task)?\s+\d+\b|Self-assessment\s+\d+\b|AT\d+$|Assignments?\s*\d+$)", name, re.I) and not re.search(r"@|https?://|\b\d{7,}\b", name):
        return name
    return "Assignment " + assignment.source_key


def available_assignments(data, scope, mode):
    ids = {r.assignment_id for r in selected_submissions(data, scope, mode)}
    return sorted((data.assignments[i] for i in ids), key=lambda a: (a.offering_id, a.source_key))


def assignment_options(data, filters):
    scope = data.scope(filters)
    return [{"ref": a.source_key, "name": assignment_name(a),
             "assessment_key": a.assessment_key if a.mapping_status == "confirmed" else None,
             "offering": data.offerings[a.offering_id].offering_code,
             "kind": "self_assessment" if a.max_score == 0 else "scored" if a.max_score else "unknown"}
            for a in available_assignments(data, scope, filters.mode)]


def late_seconds(row):
    value = (row.source_fields or {}).get("seconds_late")
    # A zero in a non-late row is not a measured late duration.
    if row.late is not True or not isinstance(value, (float, int)) or isinstance(value, bool):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def distributions(rows):
    groups = {name: defaultdict(set) for name in ("submission_status", "missing_flag", "late_flag", "attempt_distribution", "late_duration", "score_distribution", "self_assessment_completion")}
    for row in rows:
        student = row.student_id
        groups["submission_status"][row.status].add(student)
        for field in ("missing", "late"):
            flag = getattr(row, field)
            groups[field + "_flag"]["unknown" if flag is None else "yes" if flag else "no"].add(student)
        attempt = "unknown" if row.attempt is None else str(row.attempt) if row.attempt <= 2 else "3_plus"
        groups["attempt_distribution"][attempt].add(student)
        seconds = late_seconds(row)
        duration = "not_late" if row.late is False else "unknown" if seconds is None else "0_24h" if seconds <= 86400 else "1_7d" if seconds <= 604800 else "over_7d"
        groups["late_duration"][duration].add(student)
        score = percentage(row)
        band = "unknown" if score is None else "below_70" if score < 70 else "70_to_below_80" if score < 80 else "80_and_above"
        groups["score_distribution"][band].add(student)
        if (row.source_fields or {}).get("points_possible") == 0:
            state = "excused" if row.excused else "submitted" if row.status in {"submitted", "graded"} else "unsubmitted" if row.status == "unsubmitted" else "unknown"
            groups["self_assessment_completion"][state].add(student)
    return groups


def build_assignments(page, data, scope, reason):
    page.cohort = "all_assignment"
    options = available_assignments(data, scope, page.filters.mode)
    refs = set(page.filters.assignments.split(",")) if page.filters.assignments else {a.source_key for a in options}
    if refs - {a.source_key for a in options}:
        raise HTTPException(404)
    all_rows = selected_submissions(data, scope)
    population = {r.student_id for r in all_rows}
    all_groups = {a.id: [r for r in all_rows if r.assignment_id == a.id]
                  for a in available_assignments(data, scope, "combined")}
    # Selection changes only which complete assignment summaries are returned.
    blocked = group_guard([{r.student_id for r in group} for group in all_groups.values()], population, reason)
    rows = [r for r in selected_submissions(data, scope, page.filters.mode) if data.assignments[r.assignment_id].source_key in refs]
    students = {r.student_id for r in rows}
    page.metrics = {"students": metric(len(students), students, blocked)}
    page.tables["assessments"] = []
    for a in options:
        if a.source_key not in refs:
            continue
        group = [r for r in rows if r.assignment_id == a.id]
        members = {r.student_id for r in group}
        graded = {r.student_id for r in group if percentage(r) is not None}
        submitted = {r.student_id for r in group if r.status in {"graded", "submitted"}}
        late = {r.student_id for r in group if r.late is True}
        measured_late = {r.student_id for r in group if late_seconds(r) is not None}
        base_gate = data.privacy_reason({a.offering_id})
        score_gate = base_gate
        late_gate = group_guard([late, measured_late], members, base_gate)
        values = [percentage(r) for r in group if percentage(r) is not None]
        durations = [late_seconds(r) / 3600 for r in group if late_seconds(r) is not None]
        dims = {"offering": data.offerings[a.offering_id].offering_code or "unlabelled", "assignment_ref": a.source_key,
                "assessment_key": a.assessment_key if a.mapping_status == "confirmed" else "unconfirmed",
                "kind": "self_assessment" if a.max_score == 0 else "scored"}
        key = dims["offering"] + ":" + a.source_key
        page.tables["assessments"].append(TableRow(key=key, label=assignment_name(a), dimensions=dims, metrics={
            "students": metric(len(members), members, base_gate), "submitted_students": metric(len(submitted), submitted, score_gate),
            "submission_rate_pct": metric(100 * len(submitted) / len(members) if members else None, members, score_gate),
            "graded_students": metric(len(graded), graded, score_gate),
            "mean_score_pct": metric(mean(values) if values else None, graded, score_gate),
            "late_students": metric(len(late), late, late_gate),
            "mean_late_hours": metric(mean(durations) if durations else None, measured_late, late_gate)}))
        for name, bins in distributions(group).items():
            for row in partition([(k, k, v) for k, v in sorted(bins.items())], reason=base_gate):
                row.dimensions = dims | {"band": row.key}
                row.key = key + ":" + row.key
                page.tables.setdefault(name, []).append(row)
    page.notes += ["Source names and references are retained; only reviewed course-specific aliases map to AT1/AT2. Zero-point activities remain self-assessments.",
        "Each comparison row represents one offering and one assignment; scores use only available valid graded submissions.",
        "Weighted course summaries use both complete valid components and the effective confirmed rule; assignment selection does not change their course-wide scope.",
        "Latest exported attempt per student/assignment; null attempts remain unknown, not one. Distributions do not reconstruct attempt history.",
        "Missing, late and submission status are independent. Late duration uses supplied seconds_late only for rows flagged late.",
        "Self-assessment completion means a submitted/graded record, not a passing score. Denominators are observed assignment students, not an enrolment roster."]



"""Per-assignment statistics; weighted components require reviewed mappings."""
from collections import defaultdict
from decimal import Decimal
from fastapi import HTTPException
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric, partition
from app.dashboard.activity import group_guard
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


def distributions(rows, pass_threshold=70):
    groups = {name: defaultdict(set) for name in (
        "submission_status", "attempt_distribution", "assessment_pass_status",
        "self_assessment_completion")}
    for row in rows:
        student = row.student_id
        groups["submission_status"][row.status].add(student)
        attempt = "unknown" if row.attempt is None else str(row.attempt) if row.attempt <= 2 else "3_plus"
        groups["attempt_distribution"][attempt].add(student)
        score = percentage(row)
        result = "result_unavailable" if score is None else "passed" if score >= pass_threshold else "below_pass_mark"
        groups["assessment_pass_status"][result].add(student)
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
    page.metrics = {"students": metric(len(population), population, blocked)}
    page.tables["assessments"] = []
    for a in options:
        if a.source_key not in refs:
            continue
        group = [r for r in rows if r.assignment_id == a.id]
        members = {r.student_id for r in group}
        graded = {r.student_id for r in group if percentage(r) is not None}
        submitted = {r.student_id for r in group if r.status in {"graded", "submitted"}}
        base_gate = data.privacy_reason({a.offering_id})
        score_gate = base_gate
        rule = data.rule(data.offerings[a.offering_id])
        threshold = float(rule.pass_threshold) if rule else 70.0
        passed = {r.student_id for r in group if percentage(r) is not None and percentage(r) >= threshold}
        below = graded - passed
        unavailable = members - graded
        dims = {"offering": data.offerings[a.offering_id].offering_code or "unlabelled", "assignment_ref": a.source_key,
                "assessment_key": a.assessment_key if a.mapping_status == "confirmed" else "unconfirmed",
                "kind": "self_assessment" if a.max_score == 0 else "scored"}
        key = dims["offering"] + ":" + a.source_key
        page.tables["assessments"].append(TableRow(key=key, label=assignment_name(a), dimensions=dims, metrics={
            "students": metric(len(members), members, base_gate), "submitted_students": metric(len(submitted), submitted, score_gate),
            "submission_rate_pct": metric(100 * len(submitted) / len(members) if members else None, members, score_gate),
            "graded_students": metric(len(graded), graded, score_gate),
            "passed_students": metric(len(passed), passed, score_gate),
            "below_pass_mark_students": metric(len(below), below, score_gate),
            "result_unavailable_students": metric(len(unavailable), unavailable, score_gate)}))
        for name, bins in distributions(group, threshold).items():
            for row in partition([(k, k, v) for k, v in sorted(bins.items())], reason=base_gate):
                row.dimensions = dims | {"band": row.key}
                row.key = key + ":" + row.key
                page.tables.setdefault(name, []).append(row)
    page.notes += ["Source names and references are retained; only reviewed course-specific aliases map to AT1/AT2. Zero-point activities remain self-assessments.",
        "Each comparison row represents one offering and one assignment; scores use only available valid graded submissions.",
        "Weighted course summaries use both complete valid components and the effective confirmed rule; assignment selection does not change their course-wide scope.",
        "Latest exported attempt per student/assignment; null attempts remain unknown, not one. Distributions do not reconstruct attempt history.",
        "Submission status and result availability are independent. Missing attempt values remain unknown.",
        "Self-assessment completion means a submitted/graded record, not a passing score. Denominators are observed assignment students, not an enrolment roster."]



"""Match Badge records to the Assignment population for each teaching period."""
from collections import defaultdict

from app.dashboard.academic import academic_records
from app.dashboard.activity import group_guard
from app.dashboard.assignments import selected_submissions
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric


def resolve_awards(data):
    """Resolve a Badge only when Assignment data places the student in one offering.

    Award dates are deliberately ignored. A student appearing in more than one
    teaching period for the same course remains a review case.
    """
    membership = defaultdict(set)
    for row in selected_submissions(data, set(data.offerings)):
        offering = data.assignments[row.assignment_id].offering_id
        membership[(data.offerings[offering].course_id, row.student_id)].add(offering)
    resolved = []
    for award in data.badges:
        course = data.badge_courses.get(award.badge_class_id)
        candidates = membership.get((course, award.student_id), set())
        status = "unmapped_course" if course is None else "missing_identity" if award.student_id is None else (
            "no_assignment_match" if not candidates else "multiple_offerings" if len(candidates) > 1 else "matched")
        offering = next(iter(candidates)) if status == "matched" else None
        resolved.append((award, course, offering, status))
    return resolved


def add_badges(page, data, scope, reason):
    """Append course-pass and Badge comparisons to the Assignments page."""
    courses = {data.offerings[o].course_id for o in scope}
    population = {
        (row.student_id, data.assignments[row.assignment_id].offering_id)
        for row in selected_submissions(data, scope)
    }
    valid, revoked, ambiguous = set(), set(), set()
    for award, course, offering, status in resolve_awards(data):
        if offering in scope:
            member = (award.student_id, offering)
            (revoked if award.revoked else valid).add(member)
        elif status == "multiple_offerings" and course in courses:
            ambiguous.update(pair for pair in population
                             if pair[0] == award.student_id and data.offerings[pair[1]].course_id == course)

    states = {
        "valid": valid,
        "revoked_only": revoked - valid,
        "needs_review": ambiguous - valid - revoked,
        "no_matched_award": population - valid - revoked - ambiguous,
    }
    academic = academic_records(data, scope)
    passed = {pair for pair in population if pair in academic and academic[pair]["state"] == "pass"}
    reconciliation = {
        "passed_and_badge": passed & valid,
        "passed_no_badge_record": passed - valid,
        "badge_recorded_pass_not_confirmed": valid - passed,
        "neither_confirmed": population - passed - valid,
    }
    blocked = group_guard(list(states.values()), population, reason)
    page.metrics.update({
        "badge_population_students": metric(len(population), population, blocked),
        "active_badge_students": metric(len(valid), valid, blocked),
        "revoked_badge_only_students": metric(len(states["revoked_only"]), states["revoked_only"], blocked),
    })
    page.tables["badge_status"] = [
        TableRow(key=key, label=key,
                 dimensions={"unit": "students_with_assignment_records"},
                 metrics={"students": metric(len(people), people, blocked)})
        for key, people in states.items()
    ]
    page.tables["badge_course_reconciliation"] = [
        TableRow(key=key, label=key,
                 dimensions={"unit": "students_with_assignment_records"},
                 metrics={"students": metric(len(people), people, blocked)})
        for key, people in reconciliation.items()
    ]
    page.tables["badge_offering_comparison"] = []
    for offering in sorted(scope):
        members = {pair for pair in population if pair[1] == offering}
        gate = group_guard([people & members for people in states.values()], members, reason)
        code = data.offerings[offering].offering_code or "unlabelled"
        page.tables["badge_offering_comparison"].append(TableRow(
            key=code, label=code,
            dimensions={"offering": code, "unit": "students"},
            metrics={
                "total_students": metric(len(members), members, gate),
                "confirmed_passes": metric(len(passed & members), passed & members, gate),
                "active_badges": metric(len(valid & members), valid & members, gate),
            }))
    page.notes += [
        "Badge records are matched through student identity to exactly one Assignment teaching period in the same course; award dates do not assign teaching periods.",
        "Active Badge, revoked-only evidence and no Badge record are separate states. A separate active award takes precedence over revoked history.",
        "Course pass and Badge evidence use the same Assignment population. Differences can reflect claiming, export or matching gaps and are not manually balanced.",
    ]

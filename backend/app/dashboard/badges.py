"""Resolve awards from course identity and current Engagement memberships, not dates."""
from collections import defaultdict
from app.dashboard.activity import bucket, local_date, group_guard
from app.dashboard.contracts import Metric, TableRow
from app.dashboard.privacy import metric


def resolve_awards(data):
    membership = defaultdict(set)
    for row in data.engagement:
        membership[(data.offerings[row.offering_id].course_id, row.student_id)].add(row.offering_id)
    resolved = []
    for award in data.badges:
        course = data.badge_courses.get(award.badge_class_id)
        candidates = membership.get((course, award.student_id), set())
        status = "unmapped_course" if course is None else "missing_identity" if award.student_id is None else (
            "no_engagement_match" if not candidates else "multiple_offerings" if len(candidates) > 1 else "matched")
        offering = next(iter(candidates)) if status == "matched" else None
        resolved.append((award, course, offering, status))
    return resolved


def build_outcomes(page, data, scope, reason):
    page.cohort = "engagement_student_offering_memberships"
    courses = {data.offerings[o].course_id for o in scope}
    resolved = resolve_awards(data)
    population = {(r.student_id, r.offering_id) for r in data.engagement if r.offering_id in scope}
    valid, revoked, ambiguous = set(), set(), set()
    timelines = defaultdict(list)
    for award, course, offering, status in resolved:
        if offering in scope:
            member = (award.student_id, offering)
            (revoked if award.revoked else valid).add(member)
            timelines[(bucket(local_date(award.awarded_at), page.filters.interval), "revoked" if award.revoked else "valid")].append((award, member))
        elif status == "multiple_offerings" and course in courses:
            ambiguous.update(pair for pair in population if pair[0] == award.student_id and data.offerings[pair[1]].course_id == course)
    # A revoked historical award does not cancel a separate, currently valid award.
    states = {"valid": valid, "revoked_only": revoked - valid,
              "needs_review": ambiguous - valid - revoked,
              "no_matched_award": population - valid - revoked - ambiguous}
    blocked = group_guard(list(states.values()), population, reason)
    page.metrics = {"cohort_memberships": metric(len(population), population, blocked),
        "valid_award_holders": metric(len(valid), valid, blocked),
        "badge_completion_rate_pct": metric(100 * len(valid) / len(population) if population else None, population, blocked),
        "revoked_only_holders": metric(len(states["revoked_only"]), states["revoked_only"], blocked)}
    page.tables["badge_status"] = [TableRow(key=k, label=k, metrics={"memberships": metric(len(v), v, blocked)}) for k, v in states.items()]
    page.tables["offering_comparison"] = []
    for offering in sorted(scope):
        members = {p for p in population if p[1] == offering}
        holders = valid & members
        code = data.offerings[offering].offering_code or "unlabelled"
        gate = group_guard([v & members for v in states.values()], members, reason)
        page.tables["offering_comparison"].append(TableRow(key=code, label=code, dimensions={"offering": code}, metrics={
            "cohort_students": metric(len(members), members, gate),
            "valid_award_holders": metric(len(holders), holders, gate),
            "badge_completion_rate_pct": metric(100 * len(holders) / len(members) if members else None, members, gate)}))
    # Diagnostics count records, not deduplicated people. Without identity a record
    # cannot be placed into an offering, so this table is explicitly course-wide.
    diagnostics = {status + suffix: 0 for status in ("matched", "missing_identity", "no_engagement_match", "multiple_offerings", "unmapped_course")
                   for suffix in (":revoked", ":not_revoked")}
    for award, course, offering, status in resolved:
        if course in courses or (not page.filters.course and not page.filters.offering and not page.filters.offerings and course is None):
            diagnostics[status + (":revoked" if award.revoked else ":not_revoked")] += 1
    page.tables["award_diagnostics"] = [TableRow(key=k, label=k, dimensions={"scope": "selected_courses_all_offerings", "unit": "award_records"},
        metrics={"records": Metric(value=n)}) for k, n in sorted(diagnostics.items())]
    page.tables["award_timeline"] = []
    for (period, state), group in sorted(timelines.items()):
        members = {member for _, member in group}
        page.tables["award_timeline"].append(TableRow(key=f"{period}:{state}", label=f"{period} / {state}",
            dimensions={"period": period, "status": state}, metrics={
                "memberships": metric(len(members), members),
                "award_records": metric(len(group), members)}))
    page.notes += ["Match badge class to course, then identity to exactly one Engagement offering within that course, considering all offerings before filtering.",
        "Badge completion rate = distinct matched non-revoked holders / Engagement students in the same offering. Across offerings the unit is student-offering memberships.",
        "Revoked-only means unsuccessful badge evidence, not an academic fail. No matched award is distinct from revoked, and is not an academic fail.",
        "A separate valid award takes precedence over revoked historical awards. Repeated awards are deduplicated for rates, but retained in record counts.",
        "Missing identities, unmatched identities and multiple offerings remain review diagnostics; the observed rate is not proof of final academic completion.",
        "Diagnostics cover selected courses across all offerings; unresolved records cannot be attributed to a selected offering.",
        "Award timeline uses supplied issue dates in Melbourne time, with an unknown-date bucket; dates are never used to infer intake.",
        "Resolution is calculated from latest snapshots; stored legacy import match_status/outcome fields are not used as dashboard conclusions."]

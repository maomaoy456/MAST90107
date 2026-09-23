"""Resource counts attributed to their recorded first-view date."""
from collections import defaultdict
from app.dashboard.activity import bucket
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric


def category(row):
    kind = row.event_type.lower()
    return "assessment" if kind in {"assignment", "quiz"} else "content" if kind in {
        "page", "home_page", "modules", "subject_overview"} else "other"


def resource_type(row):
    """Stable business labels for the expandable Other category."""
    kind = row.event_type.strip().lower()
    return {"discussion": "discussions", "user": "user_profiles", "announcement": "announcements",
            "calendar_event": "calendar_events", "external_tool": "external_tools",
            "subject_grades": "grades"}.get(kind, kind or "uncategorised")


def build_engagement(page, data, scope, reason):
    page.cohort = "all_engagement"
    rows = [r for r in data.engagement if r.offering_id in scope]
    students = {r.student_id for r in rows}
    tables = {name: defaultdict(list) for name in ("resource_categories", "activity_by_start_date")}
    other_types = defaultdict(list)
    for row in rows:
        kind = category(row)
        start = row.first_viewed_on
        tables["resource_categories"][("all", kind)].append(row)
        tables["activity_by_start_date"][(bucket(start, page.filters.interval), kind)].append(row)
        if kind == "other":
            other_types[resource_type(row)].append(row)
    views = sum(r.times_viewed or 0 for r in rows)
    page.metrics = {"students": metric(len(students), students),
        "views": metric(views, students),
        "participations": metric(sum(r.participated_count or 0 for r in rows), students),
        "views_per_student": metric(views / len(students) if students else None, students)}
    for name, groups in tables.items():
        page.tables[name] = []
        for (period, kind), group in sorted(groups.items()):
            members = {r.student_id for r in group}
            page.tables[name].append(TableRow(key=f"{period}:{kind}", label=f"{period} / {kind}",
                dimensions={"period": period, "category": kind}, metrics={
                    "students": metric(len(members), members),
                    "views": metric(sum(r.times_viewed or 0 for r in group), members),
                    "participations": metric(sum(r.participated_count or 0 for r in group), members)}))
    page.tables["other_resource_types"] = []
    for kind, group in sorted(other_types.items()):
        members = {r.student_id for r in group}
        page.tables["other_resource_types"].append(TableRow(key=kind, label=kind,
            dimensions={"resource_type": kind, "category": "other"}, metrics={
                "students": metric(len(members), members),
                "views": metric(sum(r.times_viewed or 0 for r in group), members),
                "participations": metric(sum(r.participated_count or 0 for r in group), members)}))
    page.notes += ["Start-date activity assigns each resource summary's full count to start_date.",
        "First-view attribution is not a daily click log: each resource summary's total count is placed on its recorded first-view date.",
        "Unknown dates remain an unknown bucket. Weeks start Monday; missing calendar buckets are not asserted to be zero.",
        "Teaching stages are available only where a supplied calendar exists."]

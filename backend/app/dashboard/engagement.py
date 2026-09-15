"""Activity summaries with explicit start-date and estimated midpoint attribution."""
from collections import defaultdict
from app.dashboard.activity import bucket, local_date
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric


def category(row):
    kind = row.event_type.lower()
    return "assessment" if kind in {"assignment", "quiz"} else "content" if kind in {
        "page", "home_page", "modules", "subject_overview"} else "other"


def build_engagement(page, data, scope, reason):
    page.cohort = "all_engagement"
    rows = [r for r in data.engagement if r.offering_id in scope]
    students = {r.student_id for r in rows}
    tables = {name: defaultdict(list) for name in ("resource_categories", "activity_by_start_date", "activity_by_midpoint")}
    for row in rows:
        kind = category(row)
        start = row.first_viewed_on
        midpoint = None
        if row.first_viewed_at and row.last_viewed_at and row.last_viewed_at >= row.first_viewed_at:
            midpoint = local_date(row.first_viewed_at + (row.last_viewed_at - row.first_viewed_at) / 2)
        tables["resource_categories"][("all", kind)].append(row)
        tables["activity_by_start_date"][(bucket(start, page.filters.interval), kind)].append(row)
        tables["activity_by_midpoint"][(bucket(midpoint, page.filters.interval), kind)].append(row)
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
    page.notes += ["Start-date activity assigns each resource summary's full count to start_date.",
        "Midpoint activity is an estimate: the full count is assigned to the midpoint of first/last view, in Melbourne time; no click times are reconstructed.",
        "Unknown dates remain an unknown bucket. Weeks start Monday; missing calendar buckets are not asserted to be zero.",
        "Teaching stages are available only where a supplied calendar exists."]

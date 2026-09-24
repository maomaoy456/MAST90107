"""Additional teaching-stage and Badge-delay aggregate views."""
from collections import defaultdict
from app.dashboard.calendar import phase
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric


def add_engagement_stages(page, data, scope, reason):
    from app.dashboard.engagement import category
    for offering_id in sorted(scope):
        offering = data.offerings[offering_id]
        rows = [r for r in data.engagement if r.offering_id == offering_id]
        members = {r.student_id for r in rows}
        tables = {"activity_by_course_phase": defaultdict(list), "activity_by_course_week": defaultdict(list)}
        for row in rows:
            day = row.first_viewed_on
            stage = phase(offering, day)
            week = str((day - offering.starts_on).days // 7 + 1) if day and offering.starts_on else "unknown"
            tables["activity_by_course_phase"][(stage, category(row))].append(row)
            tables["activity_by_course_week"][(week, category(row))].append(row)
        for name, bins in tables.items():
            for (period, kind), group in sorted(bins.items()):
                people = {r.student_id for r in group}
                code = offering.offering_code or "unlabelled"
                page.tables.setdefault(name, []).append(TableRow(key=f"{code}:{period}:{kind}", label=period,
                    dimensions={"offering": code, "period": period, "category": kind, "attribution": "start_date"}, metrics={
                        "students": metric(len(people), people),
                        "views": metric(sum(r.times_viewed or 0 for r in group), people)}))
    page.notes.append("Course week 1 starts on the supplied start date; week 0 and negative weeks precede it. Stage/week counts use start-date attribution.")

"""Additional teaching-stage and Badge-delay aggregate views."""
from collections import defaultdict
from app.dashboard.activity import local_date
from app.dashboard.calendar import phase, today
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric, partition


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
                        "views": metric(sum(r.times_viewed or 0 for r in group), people),
                        "participations": metric(sum(r.participated_count or 0 for r in group), people)}))
    page.notes.append("Course week 1 starts on the supplied start date; week 0 and negative weeks precede it. Stage/week counts use start-date attribution.")


def add_badge_delays(page, data, scope, reason):
    from app.dashboard.badges import resolve_awards
    earliest = {}
    for award, _, offering, status in resolve_awards(data):
        if offering not in scope or award.revoked:
            continue
        pair = (award.student_id, offering)
        if pair not in earliest or (award.awarded_at is not None and (earliest[pair] is None or award.awarded_at < earliest[pair])):
            earliest[pair] = award.awarded_at
    for offering_id in sorted(scope):
        offering = data.offerings[offering_id]
        pairs = {p for p in earliest if p[1] == offering_id}
        bins = {k: set() for k in ("before_end", "0_7_days_after", "8_30_days_after", "over_30_days_after", "unknown")}
        for pair in pairs:
            day = local_date(earliest[pair])
            delta = (day - offering.ends_on).days if day and offering.ends_on else None
            band = "unknown" if delta is None else "before_end" if delta < 0 else "0_7_days_after" if delta <= 7 else "8_30_days_after" if delta <= 30 else "over_30_days_after"
            bins[band].add(pair)
        inherited = page.metrics.get("valid_award_holders")
        gate = reason or (inherited.reason if inherited and inherited.suppressed else None)
        for row in partition([(k, k, v) for k, v in bins.items()], reason=gate):
            row.dimensions = {"offering": offering.offering_code or "unlabelled", "band": row.key,
                              "calendar_phase": phase(offering, today())}
            row.key = (offering.offering_code or "unlabelled") + ":" + row.key
            row.metrics = {"holders": row.metrics["students"]}
            page.tables.setdefault("badge_delay_from_course_end", []).append(row)
    for row in page.tables.get("offering_comparison", []):
        offering = next((o for o in data.offerings.values() if o.offering_code == row.key), None)
        if offering:
            row.dimensions["calendar_phase"] = phase(offering, today())
    page.notes.append("Badge delay uses each holder's earliest non-revoked issue date in the matched offering. Awards after course end remain valid; calendar phase is reported per offering for comparison.")

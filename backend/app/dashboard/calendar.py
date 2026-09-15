"""Calendar phases describe planned teaching dates, never academic completion."""
from datetime import datetime, timezone
from app.dashboard.activity import MELBOURNE
from app.dashboard.contracts import TableRow, Metric


def today():
    return datetime.now(timezone.utc).astimezone(MELBOURNE).date()


def phase(offering, day):
    if day is None or offering.starts_on is None or offering.ends_on is None:
        return "unknown"
    return "before_start" if day < offering.starts_on else "after_end" if day > offering.ends_on else "during_course"


def add_calendar(page, data, scope):
    page.tables["course_calendar"] = []
    for key in sorted(scope):
        offering = data.offerings[key]
        code = offering.offering_code or "unlabelled"
        calendar = data.calendars.get(key)
        dims = {"offering": code, "starts_on": str(offering.starts_on or "unknown"),
                "ends_on": str(offering.ends_on or "unknown"), "phase": phase(offering, today()), "as_of": str(today())}
        page.tables["course_calendar"].append(TableRow(key=code, label=code, dimensions=dims, metrics={}))
        page.coverage[code] = {"calendar": calendar is not None,
            "survey": "survey:" + code in data.extra_batches,
            "support": "support:" + data.courses[offering.course_id].code in data.extra_batches,
            "engagement": any(r.offering_id == key for r in data.engagement),
            "assignment": any(data.assignments[r.assignment_id].offering_id == key for r in data.submissions)}
        if page.page == "overview" and calendar:
            n = calendar.enrolment_records
            page.tables.setdefault("enrolment_coverage", []).append(TableRow(key=code, label=code,
                dimensions={"unit": "enrolment_records", "offering": code}, metrics={
                    "enrolment_records": Metric(value=n)}))
    page.notes.append("Calendar phases use Melbourne dates as of today; after_end is not an academic pass or confirmed graduation.")

"""Extract month-level intake labels, never invent an exact start/end date."""
import re

from app.ingestion.normalize import InvalidValue, string

MONTHS = {name: i for i, name in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), start=1)}
PATTERN = re.compile(r"^(?P<course>[A-Z0-9]+)_(?P<year>20\d{2})_(?P<month>[A-Z]{3})_(?P<cohort>[A-Z]+_\d+)$")


def parse_offering(code, source_name=None):
    code = string(code, required=True)
    filename = string(source_name)
    if filename and filename != code + "_Canvas.csv":
        raise InvalidValue("unmapped_course")
    match = PATTERN.fullmatch(code)
    if not match:
        # Other code conventions still retain their label, without guessing dates.
        return {"offering_code": code}
    month = MONTHS.get(match["month"])
    if month is None:
        raise InvalidValue("invalid_date")
    return {"offering_code": code, "intake_year": int(match["year"]),
            "intake_month": month, "cohort_label": match["cohort"]}

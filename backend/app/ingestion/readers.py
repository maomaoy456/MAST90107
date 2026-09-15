"""Explicit column contracts: keep known analytical fields, quarantine schema drift."""
from io import BytesIO
from pathlib import Path
import hashlib

import pandas as pd

from app.ingestion.normalize import InvalidValue, json_value

ID = "Student_ID_anonymised"
REQUIRED = {
    "engagement": {ID, "canvas_subject_id", "subject_code", "subject_name", "resource_type", "start_date", "times_viewed", "participated_count"},
    "assignment": {ID, "course_canvas_id", "course_sis_id", "course_name", "assignment_id", "assignment_name", "points_possible", "submission_status", "attempt", "score"},
    "badge": {ID, "Badge Class Name", "Issue Date", "Revoked"},
}
KEEP = {
    "engagement": "Source.Name section_ids section_names canvas_subject_id subject_code subject_name resource_type resource_title times_viewed participated_count start_date first_viewed last_viewed account_id".split(),
    "assignment": "enrolment_status type created_at updated_at assignment_id assignment_name due_at unlock_at lock_at points_possible grading_type assignment_group_id submission_types published submission_status submitted_at graded_at submission_type attempt score grade late missing excused seconds_late course_canvas_id course_sis_id course_code course_name".split(),
    "badge": ["Issue Date", "Badge Class Name", "Expiration Date", "Claim Code Used", "Revoked", "Recipient Type"],
}
EXCLUDED = {ID, "resource_title", "Narrative", "Revocation Reason", "Image Url"}


def read_file(path: Path, source: str):
    # Hash and parse the very same bytes; never open the source for writing.
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if path.suffix.lower() == ".xlsx":
        frame = pd.read_excel(BytesIO(raw), dtype={ID: "string"})
    elif path.suffix.lower() == ".csv":
        frame = pd.read_csv(BytesIO(raw), dtype={ID: "string"}, encoding="utf-8-sig")
    else:
        raise InvalidValue("unsupported_source")
    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.columns.duplicated().any() or not REQUIRED[source].issubset(frame.columns):
        raise InvalidValue("missing_required")
    unknown = set(frame.columns) - set(KEEP[source]) - EXCLUDED
    if unknown:
        # Do not silently discard newly supplied fields. Extend KEEP after review.
        raise InvalidValue("unsupported_source")
    return frame, digest


def source_fields(row, source):
    """Internal snapshots retain original typed values, excluding identity/free text.

    These JSON columns are never an API response. Normalized query fields live beside them.
    """
    fields = {name: json_value(row[name]) for name in KEEP[source] if name in row}
    if source == "engagement":
        token = str(row.get(ID, "")).strip()
        if str(row.get("resource_type", "")).lower() == "user" or (token and token in str(fields.get("resource_title", ""))):
            fields["resource_title"] = None
    return fields

"""Atomic, scoped snapshots. Original files and out-of-window cases stay untouched."""
import hashlib
from datetime import datetime, timezone
from collections import Counter
import pandas as pd
from sqlalchemy import insert, select
from app.models import Course, CourseOffering, ImportBatch, OfferingCalendar, SurveyResponse, SupportCase
from app.ingestion.normalize import identity, boolean, number, string, timestamp, json_value
from app.supplemental import readers
from app.supplemental.schema import LIKERT, THEMES, TEXT


def save(session, source, scope, raw_hash, rows, model, summary, key, dependency=""):
    version = "supp-v1-" + hashlib.sha256((scope + dependency).encode()).hexdigest()[:16]
    old = session.scalar(select(ImportBatch).where(ImportBatch.source == source,
        ImportBatch.file_sha256 == raw_hash, ImportBatch.importer_version == version))
    if old:
        return "already_imported"
    summary = dict(summary, identity_key_fingerprint=hashlib.sha256(key.encode()).hexdigest(), accepted_rows=len(rows))
    batch = ImportBatch(source=source, scope=scope, file_sha256=raw_hash, importer_version=version,
        status="running", row_count=summary.get("input_rows", len(rows)), summary=summary)
    session.add(batch)
    session.flush()
    for offset in range(0, len(rows), 1000):
        session.execute(insert(model), [dict(row, batch_id=batch.id) for row in rows[offset:offset + 1000]])
    batch.status, batch.finished_at = "completed", datetime.now(timezone.utc)
    return "completed"


def date_value(value):
    return pd.to_datetime(value, dayfirst=True, format="mixed", errors="raise").date()


def import_calendars(session, paths, key):
    offerings = {o.offering_code: o for o in session.scalars(select(CourseOffering))}
    prepared, fingerprints = {}, []
    code, start, end = "Subject Offering ID: Subject Offering ID", "Subject Offering ID: Start Date", "Subject Offering ID: End Date"
    for path in paths:
        raw = path.read_bytes()
        fingerprints.append(hashlib.sha256(raw).hexdigest())
        frame = readers.salesforce(raw)
        if not {code, start, end, "Enrolment Status"} <= set(frame):
            raise ValueError("calendar_columns")
        for label, group in frame[frame[code].isin(offerings)].groupby(code):
            dates = {(date_value(a), date_value(b)) for a, b in zip(group[start], group[end])}
            if len(dates) != 1:
                raise ValueError("conflicting_calendar_dates")
            first, last = dates.pop()
            if last < first:
                raise ValueError("reversed_calendar_dates")
            if "Subject Enrolment ID" in group and group["Subject Enrolment ID"].notna().all():
                group = group.drop_duplicates("Subject Enrolment ID")
            values = dict(offering_id=offerings[label].id, starts_on=first, ends_on=last,
                enrolment_records=len(group), withdrawn_records=int(group["Enrolment Status"].eq("Withdrawn").sum()))
            if label in prepared and prepared[label] != values:
                raise ValueError("conflicting_calendar_exports")
            prepared[label] = values  # Overlapping exports must agree; never sum them.
    if not prepared:
        raise ValueError("no_known_offerings")
    digest = hashlib.sha256("".join(sorted(fingerprints)).encode()).hexdigest()
    result = save(session, "salesforce", "calendar", digest, list(prepared.values()), OfferingCalendar, {}, key,
                  dependency="|".join(sorted(prepared)))
    for label, row in prepared.items():
        offerings[label].starts_on, offerings[label].ends_on = row["starts_on"], row["ends_on"]
    return result


def import_survey(session, path, code, key):
    offering = session.scalar(select(CourseOffering).where(CourseOffering.offering_code == code))
    if offering is None:
        raise ValueError("unknown_offering")
    raw = path.read_bytes()
    frame = readers.survey(raw)
    if not {"ResponseId", "Finished", "Q2"} <= set(frame):
        raise ValueError("survey_columns")
    rows, seen, quality = [], set(), Counter()
    questions = {q for values in THEMES.values() for q in values}
    for record in frame.to_dict("records"):
        digest = identity(record.get("ResponseId"), key)
        if not digest or digest in seen:
            raise ValueError("missing_or_duplicate_response")
        seen.add(digest)
        answers = {}
        for q in questions:
            original = string(record.get(q))
            answers[q] = LIKERT.get(original)
            quality["invalid_likert"] += int(original is not None and answers[q] is None)
        try:
            nps = number(record.get("Q2"), integer=True, minimum=0)
            if nps is not None and nps > 10:
                raise ValueError()
        except ValueError:
            nps = None
            quality["invalid_nps"] += 1
        try:
            recorded = timestamp(record.get("RecordedDate"))
        except ValueError:
            recorded = None
            quality["invalid_date"] += 1
        fields = {q: json_value(record.get(q)) for q in ("Progress", "Duration (in seconds)", "Q16", "Q2_NPS_GROUP", "DistributionChannel", "UserLanguage")}
        # Raw analytical answers remain private evidence; no IP, name or ResponseId.
        fields["raw_answers"] = {q: json_value(record.get(q)) for q in questions | {"Q2"}}
        rows.append(dict(offering_id=offering.id, response_digest=digest,
            finished=boolean(record.get("Finished")) is True, recorded_at=recorded, nps=nps,
            answers=answers, feedback={q: string(record.get(q)) for q in TEXT}, source_fields=fields))
    return save(session, "survey", "survey:" + code, hashlib.sha256(raw).hexdigest(), rows,
                SurveyResponse, {"quality": dict(quality)}, key)


def import_support(session, path, course_code, key):
    course = session.scalar(select(Course).where(Course.code == course_code))
    if course is None:
        raise ValueError("unknown_course")
    offerings = list(session.scalars(select(CourseOffering).where(CourseOffering.course_id == course.id)))
    if not offerings or any(o.starts_on is None or o.ends_on is None for o in offerings):
        raise ValueError("course_dates_required")
    raw = path.read_bytes()
    frame = readers.salesforce(raw)
    if not {"Subject", "Date/Time Opened", "Age (Hours)", "Open", "Closed", "Case Origin"} <= set(frame):
        raise ValueError("support_columns")
    if "Course Name" in frame and not frame["Course Name"].dropna().eq(course.name).all():
        raise ValueError("course_name_mismatch")
    times = pd.to_datetime(frame["Date/Time Opened"], format="mixed", dayfirst=True, errors="coerce")
    # The current export supplies naive Melbourne times. Ambiguous local times
    # remain excluded diagnostics rather than being assigned an invented instant.
    local = times.dt.tz_localize("Australia/Melbourne", ambiguous="NaT", nonexistent="NaT")
    mask = pd.Series(False, index=frame.index)
    for o in offerings:
        mask |= local.dt.date.between(o.starts_on, o.ends_on)
    rows, quality = [], Counter()
    quality["invalid_opened_at"] = int(local.isna().sum())
    for index, record in frame.loc[mask].iterrows():
        try:
            hours = number(str(record["Age (Hours)"]).replace(",", "") if record["Age (Hours)"] is not None else None, minimum=0)
        except ValueError:
            hours = None
            quality["invalid_response_hours"] += 1
        subject = string(record["Subject"])
        if subject and len(subject) > 2000:
            raise ValueError("subject_too_long")
        rows.append(dict(course_id=course.id, source_row=int(index) + 2,
            opened_at=local.loc[index].tz_convert("UTC").tz_localize(None).to_pydatetime(),
            response_hours=hours, is_open=boolean(record["Open"]), is_closed=boolean(record["Closed"]),
            channel=string(record["Case Origin"]) or "Unknown", subject=subject,
            source_fields={"priority": string(record.get("Priority")), "response_time_definition": "user_confirmed_Age_Hours"}))
    windows = sorted((o.offering_code, o.starts_on.isoformat(), o.ends_on.isoformat()) for o in offerings)
    return save(session, "salesforce", "support:" + course_code, hashlib.sha256(raw).hexdigest(), rows,
        SupportCase, {"input_rows": len(frame), "outside_window_rows": int((~mask & local.notna()).sum()),
                      "quality": dict(quality), "windows": windows}, key, dependency=str(windows))

"""Transactional file imports. Identical files are idempotent; changed files are snapshots."""
from datetime import datetime, timezone
import hashlib

from sqlalchemy import delete, insert, select, text

from app.ingestion import adapters
from app.ingestion.offering import parse_offering
from app.ingestion.normalize import InvalidValue, identity, number, string
from app.ingestion.readers import ID, read_file
from app.seed import load_config
from app.models import (Assignment, AssignmentSubmission, BadgeAward, BadgeClass,
    BadgeClassCourseMapping, Course, CourseOffering, EngagementEvent, ImportBatch,
    ImportErrorRecord, Student)

VERSIONS = {"assignment": "files-v3", "engagement": "files-v4", "badge": "files-v4"}
OBSERVATIONS = {"engagement": EngagementEvent, "assignment": AssignmentSubmission, "badge": BadgeAward}


class Dimensions:
    """Resolve shared dimensions once per file, without retaining plaintext identities."""
    def __init__(self, session, key):
        self.session, self.key = session, key
        self.students = {x.identity_digest: x.id for x in session.scalars(select(Student))}
        self.courses = {x.code: x for x in session.scalars(select(Course))}
        self.offerings = {x.source_key: x for x in session.scalars(select(CourseOffering))}
        self.assignments = {(x.offering_id, x.source_key): x for x in session.scalars(select(Assignment))}
        self.classes = {x.name: x for x in session.scalars(select(BadgeClass))}
        self.aliases = {c.code: c.assignment_aliases for c in load_config()[0].courses}

    def add(self, obj):
        self.session.add(obj)
        self.session.flush()
        return obj

    def student(self, raw, *, required=True):
        digest = identity(raw, self.key)
        if digest is None:
            if required:
                raise InvalidValue("missing_required")
            return None
        if digest not in self.students:
            self.students[digest] = self.add(Student(identity_digest=digest)).id
        return self.students[digest]

    def offering(self, row, source):
        sis = string(row["course_sis_id" if source == "assignment" else "subject_code"], required=True)
        canvas = string(row["course_canvas_id" if source == "assignment" else "canvas_subject_id"], required=True)
        metadata = parse_offering(sis, row.get("Source.Name"))
        course = self.courses.get(sis.split("_")[0])
        if course is None:
            raise InvalidValue("unmapped_course")
        offering = self.offerings.get(canvas)
        if offering is None:
            # Activity dates and code month are not confirmed course boundaries.
            offering = self.add(CourseOffering(course_id=course.id, source_key=canvas, status="unknown"))
            self.offerings[canvas] = offering
        if offering.course_id != course.id:
            raise InvalidValue("unmapped_course")
        for name, value in metadata.items():
            setattr(offering, name, value)
        return offering

    def assignment(self, row, offering):
        key = (offering.id, string(row["assignment_id"], required=True))
        maximum = number(row["points_possible"], minimum=0)
        name = string(row["assignment_name"], required=True)
        assignment = self.assignments.get(key)
        if assignment is None:
            course = next(c for c in self.courses.values() if c.id == offering.course_id)
            component = self.aliases.get(course.code, {}).get(name) if maximum and maximum > 0 else None
            assignment = self.add(Assignment(offering_id=offering.id, source_key=key[1],
                name=name, max_score=maximum, assessment_key=component,
                mapping_status="confirmed" if component else "unverified"))
            self.assignments[key] = assignment
        # Preserve each export's metadata in submission.source_fields; do not overwrite history.
        return assignment

    def badge_class(self, row):
        name = string(row["Badge Class Name"], required=True)
        if name not in self.classes:
            self.classes[name] = self.add(BadgeClass(name=name))
        badge_class = self.classes[name]
        course = next((c for c in self.courses.values() if c.name == name), None)
        if course and self.session.scalar(select(BadgeClassCourseMapping).where(
                BadgeClassCourseMapping.badge_class_id == badge_class.id)) is None:
            self.add(BadgeClassCourseMapping(badge_class_id=badge_class.id, course_id=course.id,
                status="confirmed", mapping_version="exact-course-name-v1"))
        return badge_class, course


def badge_import_status(values, student_id):
    """Retain eligibility only; dashboard resolves current Engagement membership.

    No date-based guess is persisted. Recomputing from latest snapshots avoids
    stale links when a new Engagement export adds another offering.
    """
    status = "revoked" if values["revoked"] else "missing_student" if student_id is None else "manual_review"
    return dict(offering_id=None, match_status=status,
                outcome="ineligible" if status != "manual_review" else "unknown")


def import_file(factory, path, source, key):
    version = VERSIONS[source]
    frame, digest = read_file(path, source)
    fingerprint = hashlib.sha256(key.encode()).hexdigest()
    # One cooperative importer per database prevents concurrent dimension/key races.
    # Bind to one connection: GET_LOCK must survive commits on that connection.
    with factory.kw["bind"].connect() as connection, factory(bind=connection) as session:
        locked = session.scalar(text("SELECT GET_LOCK('mpe_file_import', 0)"))
        if locked != 1:
            raise InvalidValue("duplicate_record")
        try:
            previous = list(session.scalars(select(ImportBatch)))
            if any(b.summary and b.summary.get("identity_key_fingerprint") not in (None, fingerprint) for b in previous):
                raise InvalidValue("invalid_row")
            batch = next((b for b in previous if b.source == source and b.file_sha256 == digest and b.importer_version == version), None)
            if batch and batch.status == "completed":
                return "already_imported"
            if batch is None:
                batch = ImportBatch(source=source, file_sha256=digest, importer_version=version)
                session.add(batch)
            batch.status = "running"
            batch.row_count = len(frame)
            batch.summary = {"identity_key_fingerprint": fingerprint}
            session.commit()
            batch_id = batch.id
            try:
                session.execute(delete(ImportErrorRecord).where(ImportErrorRecord.batch_id == batch_id))
                dimensions = Dimensions(session, key)
                pending, rejected, accepted, warnings, seen = [], 0, 0, 0, set()
                for row_number, row in enumerate(frame.to_dict("records"), start=2):
                    try:
                        values = getattr(adapters, source)(row)
                        if source == "badge":
                            badge_class, course = dimensions.badge_class(row)
                            student_id = dimensions.student(row[ID], required=False)
                            values.update(badge_class_id=badge_class.id, student_id=student_id)
                            values.update(badge_import_status(values, student_id))
                        else:
                            # Validate before creating dimensions where possible.
                            if source == "assignment":
                                number(row["points_possible"], minimum=0)
                            offering = dimensions.offering(row, source)
                            student_id = dimensions.student(row[ID])
                            values["student_id"] = student_id
                            if source == "engagement":
                                values["offering_id"] = offering.id
                            else:
                                assignment = dimensions.assignment(row, offering)
                                identity_key = (student_id, assignment.id, values["attempt"])
                                if identity_key in seen:
                                    raise InvalidValue("duplicate_record")
                                seen.add(identity_key)
                                values["assignment_id"] = assignment.id
                        pending.append(dict(batch_id=batch_id, source_row=row_number, **values))
                        accepted += 1
                        if values.get("source_fields", {}).get("_quality_issues"):
                            warnings += 1
                            session.add(ImportErrorRecord(batch_id=batch_id, row_number=row_number, code="invalid_date"))
                    except InvalidValue as error:
                        rejected += 1
                        session.add(ImportErrorRecord(batch_id=batch_id, row_number=row_number, code=str(error)))
                    if len(pending) >= 1000:
                        session.execute(insert(OBSERVATIONS[source]), pending)
                        pending.clear()
                if pending:
                    session.execute(insert(OBSERVATIONS[source]), pending)
                batch.status = "completed"
                batch.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                batch.summary = {"accepted_rows": accepted, "rejected_rows": rejected, "warning_rows": warnings,
                    "identity_key_fingerprint": fingerprint, "naive_timezone": "Australia/Melbourne", "naive_timezone_status": "assumed_supported_by_distribution",
                    "storage_timezone": "UTC", "snapshot_policy": "latest_completed_per_source"}
                session.commit()
                return "completed"
            except Exception:
                session.rollback()
                batch = session.get(ImportBatch, batch_id)
                batch.status = "failed"
                batch.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                session.add(ImportErrorRecord(batch_id=batch_id, code="invalid_row"))
                session.commit()
                raise InvalidValue("invalid_row") from None
        finally:
            session.execute(text("SELECT RELEASE_LOCK('mpe_file_import')"))
            session.commit()

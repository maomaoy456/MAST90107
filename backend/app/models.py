"""Internal storage only. Never serialize these models into analytics responses.

Foreign keys restrict deletion by default to preserve provenance. Source identifiers
are opaque internal keys; ingestion and identity hashing belong to Phase 2.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Computed, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import DATETIME

from app.db import Base

JSON_TYPE = JSON()
UTC_DATETIME = DateTime().with_variant(DATETIME(fsp=3), "mysql")


class IdMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class CreatedMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportBatch(IdMixin, CreatedMixin, Base):
    __tablename__ = "import_batches"
    source: Mapped[str] = mapped_column(String(24))
    scope: Mapped[str] = mapped_column(String(160), default="global", server_default="global")
    file_sha256: Mapped[str] = mapped_column(String(64))
    importer_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    row_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict | None] = mapped_column(JSON_TYPE)
    __table_args__ = (
        UniqueConstraint("source", "file_sha256", "importer_version"),
        CheckConstraint("source IN ('engagement','assignment','badge','survey','salesforce')", name="source"),
        CheckConstraint("status IN ('pending','running','completed','failed')", name="status"),
        CheckConstraint("row_count >= 0", name="row_count"),
    )


class ImportErrorRecord(IdMixin, CreatedMixin, Base):
    __tablename__ = "import_errors"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer)
    # No raw cell values, exception strings, student IDs or free-text details.
    code: Mapped[str] = mapped_column(String(32))
    __table_args__ = (
        CheckConstraint("`row_number` IS NULL OR `row_number` > 0", name="row_number"),
        CheckConstraint("code IN ('invalid_row','missing_required','invalid_date','invalid_number','unmapped_course','ambiguous_offering','duplicate_record','unsupported_source')", name="code"),
    )


class Student(IdMixin, CreatedMixin, Base):
    __tablename__ = "students"
    identity_digest: Mapped[str] = mapped_column(String(64), unique=True)


class Course(IdMixin, Base):
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))


class CourseOffering(IdMixin, Base):
    __tablename__ = "course_offerings"
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(120), unique=True)
    offering_code: Mapped[str | None] = mapped_column(String(120))
    intake_year: Mapped[int | None] = mapped_column(Integer)
    intake_month: Mapped[int | None] = mapped_column(Integer)
    cohort_label: Mapped[str | None] = mapped_column(String(32))
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="unknown", server_default="unknown")
    __table_args__ = (
        CheckConstraint("ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on", name="dates"),
        CheckConstraint("status IN ('unknown','planned','in_progress','completed')", name="status"),
    )


class Assignment(IdMixin, Base):
    __tablename__ = "assignments"
    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(300))
    assessment_key: Mapped[str | None] = mapped_column(String(32))
    mapping_status: Mapped[str] = mapped_column(String(16), default="unverified", server_default="unverified")
    max_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    __table_args__ = (
        UniqueConstraint("offering_id", "source_key"),
        UniqueConstraint("id", "offering_id"),
        CheckConstraint("max_score IS NULL OR max_score >= 0", name="max_score"),
        CheckConstraint("mapping_status IN ('unverified','confirmed','manual_review')", name="mapping_status"),
        CheckConstraint("mapping_status != 'confirmed' OR assessment_key IS NOT NULL", name="confirmed_key"),
    )


class EngagementEvent(IdMixin, Base):
    __tablename__ = "engagement_events"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"), index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(48))
    first_viewed_on: Mapped[date | None] = mapped_column(Date)
    occurred_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    times_viewed: Mapped[int | None] = mapped_column(Integer)
    participated_count: Mapped[int | None] = mapped_column(Integer)
    first_viewed_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    last_viewed_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    source_fields: Mapped[dict | None] = mapped_column(JSON_TYPE)
    __table_args__ = (UniqueConstraint("batch_id", "source_row"), CheckConstraint("source_row > 0", name="source_row"))


class AssignmentSubmission(IdMixin, Base):
    __tablename__ = "assignment_submissions"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    attempt: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    missing: Mapped[bool | None] = mapped_column(Boolean)
    late: Mapped[bool | None] = mapped_column(Boolean)
    excused: Mapped[bool | None] = mapped_column(Boolean)
    graded_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    source_fields: Mapped[dict | None] = mapped_column(JSON_TYPE)
    status: Mapped[str] = mapped_column(String(16), default="unknown", server_default="unknown")
    __table_args__ = (
        UniqueConstraint("batch_id", "source_row"),
        UniqueConstraint("batch_id", "student_id", "assignment_id", "attempt", name="uq_submissions_batch_student_assignment_attempt"),
        CheckConstraint("source_row > 0 AND (attempt IS NULL OR attempt > 0)", name="positive_numbers"),
        CheckConstraint("status IN ('unknown','unsubmitted','missing','submitted','graded','excused')", name="status"),
    )


class BadgeClass(IdMixin, Base):
    __tablename__ = "badge_classes"
    name: Mapped[str] = mapped_column(String(300), unique=True)


class BadgeClassCourseMapping(IdMixin, CreatedMixin, Base):
    __tablename__ = "badge_class_course_mapping"
    badge_class_id: Mapped[int] = mapped_column(ForeignKey("badge_classes.id"), unique=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="manual_review", server_default="manual_review")
    mapping_version: Mapped[str] = mapped_column(String(40))
    __table_args__ = (CheckConstraint("status IN ('confirmed','manual_review')", name="status"),)


class BadgeAward(IdMixin, Base):
    __tablename__ = "badge_awards"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    badge_class_id: Mapped[int] = mapped_column(ForeignKey("badge_classes.id"), index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), index=True)
    offering_id: Mapped[int | None] = mapped_column(ForeignKey("course_offerings.id"), index=True)
    awarded_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    source_fields: Mapped[dict | None] = mapped_column(JSON_TYPE)
    expires_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    match_status: Mapped[str] = mapped_column(String(20), default="manual_review", server_default="manual_review")
    outcome: Mapped[str] = mapped_column(String(16), default="unknown", server_default="unknown")
    __table_args__ = (
        UniqueConstraint("batch_id", "source_row"),
        CheckConstraint("source_row > 0", name="source_row"),
        CheckConstraint("match_status IN ('matched','missing_student','revoked','manual_review')", name="match_status"),
        CheckConstraint("outcome IN ('unknown','achieved','not_achieved','ineligible')", name="outcome"),
        CheckConstraint("outcome != 'achieved' OR (student_id IS NOT NULL AND revoked = false AND offering_id IS NOT NULL AND match_status = 'matched')", name="eligible_success"),
    )


class AssessmentRule(IdMixin, CreatedMixin, Base):
    __tablename__ = "assessment_rules"
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    pass_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    offering_id: Mapped[int | None] = mapped_column(ForeignKey("course_offerings.id"))
    scope_key: Mapped[int | None] = mapped_column(Integer, Computed("COALESCE(offering_id, 0)", persisted=True))
    active_slot: Mapped[int | None] = mapped_column(Integer, Computed("CASE WHEN enabled THEN 1 ELSE NULL END", persisted=True))
    components: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE)
    evidence: Mapped[str] = mapped_column(String(200))
    config_sha256: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint("course_id", "scope_key", "version", name="uq_rules_course_scope_version"),
        CheckConstraint("status IN ('confirmed','candidate')", name="status"),
        CheckConstraint("enabled = false OR status = 'confirmed'", name="enabled_confirmed"),
        CheckConstraint("pass_threshold >= 0 AND pass_threshold <= 100", name="threshold"),
        Index("uq_assessment_rules_enabled_course", "course_id", "scope_key", "active_slot", unique=True),
    )


class ModelRun(IdMixin, CreatedMixin, Base):
    __tablename__ = "model_runs"
    model_name: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str] = mapped_column(String(40))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    target: Mapped[str] = mapped_column(String(24), index=True)
    cohort_policy: Mapped[str] = mapped_column(String(32), default="student_grouped", server_default="student_grouped")
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    config_sha256: Mapped[str] = mapped_column(String(64))
    data_sha256: Mapped[str] = mapped_column(String(64))
    artifact_path: Mapped[str | None] = mapped_column(String(255))
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    metrics: Mapped[dict | None] = mapped_column(JSON_TYPE)
    summary: Mapped[dict | None] = mapped_column(JSON_TYPE)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("cohort_policy = 'student_grouped'", name="cohort_policy"),
        CheckConstraint("target IN ('AT1','AT2','weighted_final','badge')", name="target"),
        CheckConstraint("status IN ('pending','running','completed','insufficient','failed')", name="status"),
    )


class OfferingCalendar(IdMixin, Base):
    __tablename__ = "offering_calendars"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    enrolment_records: Mapped[int] = mapped_column(Integer)
    withdrawn_records: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("batch_id", "offering_id"),
        CheckConstraint("ends_on >= starts_on", name="dates"),
        CheckConstraint("enrolment_records >= withdrawn_records AND withdrawn_records >= 0", name="counts"))


class SurveyResponse(IdMixin, Base):
    __tablename__ = "survey_responses"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    offering_id: Mapped[int] = mapped_column(ForeignKey("course_offerings.id"), index=True)
    response_digest: Mapped[str] = mapped_column(String(64))
    finished: Mapped[bool] = mapped_column(Boolean)
    recorded_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    nps: Mapped[int | None] = mapped_column(Integer)
    answers: Mapped[dict] = mapped_column(JSON_TYPE)
    feedback: Mapped[dict] = mapped_column(JSON_TYPE)
    source_fields: Mapped[dict] = mapped_column(JSON_TYPE)
    __table_args__ = (UniqueConstraint("batch_id", "response_digest"),
        CheckConstraint("nps IS NULL OR (nps >= 0 AND nps <= 10)", name="nps"))


class SupportCase(IdMixin, Base):
    __tablename__ = "support_cases"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    source_row: Mapped[int] = mapped_column(Integer)
    opened_at: Mapped[datetime] = mapped_column(UTC_DATETIME)
    response_hours: Mapped[Decimal | None] = mapped_column(Numeric(16, 4))
    is_open: Mapped[bool | None] = mapped_column(Boolean)
    is_closed: Mapped[bool | None] = mapped_column(Boolean)
    channel: Mapped[str] = mapped_column(String(64))
    # Free text is restricted internal evidence, never serialized into API output.
    subject: Mapped[str | None] = mapped_column(String(2000))
    source_fields: Mapped[dict] = mapped_column(JSON_TYPE)
    __table_args__ = (UniqueConstraint("batch_id", "source_row"),
        CheckConstraint("response_hours IS NULL OR response_hours >= 0", name="response_hours"))

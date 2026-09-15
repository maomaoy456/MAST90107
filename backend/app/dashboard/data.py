"""Read only the latest complete snapshots. Internal IDs never leave this layer."""
from fastapi import HTTPException
from sqlalchemy import select

from app.models import (Assignment, AssignmentSubmission, AssessmentRule, BadgeAward,
    BadgeClassCourseMapping, Course, CourseOffering, EngagementEvent, ImportBatch,
    OfferingCalendar, SurveyResponse, SupportCase, ModelRun)


class Snapshot:
    def __init__(self, session):
        self.courses = {c.id: c for c in session.scalars(select(Course))}
        self.offerings = {o.id: o for o in session.scalars(select(CourseOffering))}
        self.assignments = {a.id: a for a in session.scalars(select(Assignment))}
        self.rules = list(session.scalars(select(AssessmentRule)))
        self.model_runs = list(session.scalars(select(ModelRun).order_by(ModelRun.created_at, ModelRun.id)))
        self.batches, self.extra_batches = {}, {}
        for batch in session.scalars(select(ImportBatch).where(ImportBatch.status == "completed").order_by(ImportBatch.finished_at, ImportBatch.id)):
            if batch.scope == "global":
                self.batches[batch.source] = batch
            else:
                self.extra_batches[batch.scope] = batch
        self.surveys, self.support, self.calendars = [], [], {}
        survey_ids = [b.id for k, b in self.extra_batches.items() if k.startswith("survey:")]
        support_ids = [b.id for k, b in self.extra_batches.items() if k.startswith("support:")]
        if survey_ids:
            self.surveys = list(session.scalars(select(SurveyResponse).where(SurveyResponse.batch_id.in_(survey_ids))))
        if support_ids:
            self.support = list(session.scalars(select(SupportCase).where(SupportCase.batch_id.in_(support_ids))))
        if "calendar" in self.extra_batches:
            self.calendars = {c.offering_id: c for c in session.scalars(select(OfferingCalendar).where(
                OfferingCalendar.batch_id == self.extra_batches["calendar"].id))}
        self.engagement, self.submissions, self.badges = [], [], []
        if "engagement" in self.batches:
            self.engagement = list(session.execute(select(EngagementEvent.student_id,
                EngagementEvent.offering_id, EngagementEvent.event_type, EngagementEvent.times_viewed,
                EngagementEvent.participated_count, EngagementEvent.first_viewed_on,
                EngagementEvent.first_viewed_at, EngagementEvent.last_viewed_at
                ).where(EngagementEvent.batch_id == self.batches["engagement"].id)))
        if "assignment" in self.batches:
            self.submissions = list(session.scalars(select(AssignmentSubmission).where(
                AssignmentSubmission.batch_id == self.batches["assignment"].id)))
        if "badge" in self.batches:
            self.badges = list(session.scalars(select(BadgeAward).where(BadgeAward.batch_id == self.batches["badge"].id)))
        self.badge_courses = {m.badge_class_id: m.course_id for m in session.scalars(
            select(BadgeClassCourseMapping).where(BadgeClassCourseMapping.status == "confirmed"))}

    def scope(self, filters):
        selected = set(self.offerings)
        if filters.course:
            course = next((c for c in self.courses.values() if c.code == filters.course), None)
            if course is None:
                raise HTTPException(404)
            selected = {o for o in selected if self.offerings[o].course_id == course.id}
        if filters.offering:
            offering = next((o for o in self.offerings.values() if o.offering_code == filters.offering), None)
            if offering is None or offering.id not in selected:
                raise HTTPException(404)
            selected = {offering.id}
        if filters.offerings:
            codes = set(filters.offerings.split(","))
            matches = {o for o in selected if self.offerings[o].offering_code in codes}
            if len(matches) != len(codes):
                raise HTTPException(404)
            selected = matches
        return selected

    def populations(self, scope):
        a = {s.student_id for s in self.submissions if self.assignments[s.assignment_id].offering_id in scope}
        e = {s.student_id for s in self.engagement if s.offering_id in scope}
        return a, e

    def rule(self, offering):
        specific = [r for r in self.rules if r.offering_id == offering.id and r.enabled]
        default = [r for r in self.rules if r.offering_id is None and r.course_id == offering.course_id and r.enabled]
        return (specific or default or [None])[0]

    def privacy_reason(self, scope):
        """Aggregate results are visible; raw identities remain inside Snapshot."""
        return None

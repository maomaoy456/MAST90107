"""Known aggregate answers and filter boundaries for the revised page contracts."""
from datetime import date, datetime
from sqlalchemy import select
from test_dashboard import dashboard, HEADERS
from app.models import (Assignment, AssignmentSubmission, BadgeAward, BadgeClass,
    BadgeClassCourseMapping, Course, CourseOffering, EngagementEvent, ImportBatch, Student)


def test_first_view_activity_totals_and_local_date(dashboard):
    client, session, _ = dashboard
    for row in session.scalars(select(EngagementEvent)):
        row.first_viewed_on = date(2025, 3, 1)
        # A resource spanning two dates is still attributed to its first view.
        row.first_viewed_at = datetime(2025, 3, 1, 12)
        row.last_viewed_at = datetime(2025, 3, 1, 16)
    session.commit()
    page = client.get('/api/v1/engagement', headers=HEADERS).json()
    start = page['tables']['activity_by_start_date'][0]
    assert 'activity_by_midpoint' not in page['tables']
    assert start['dimensions']['period'] == '2025-03-01'
    assert start['metrics']['views']['value'] == 1200
    assert start['metrics']['participations']['value'] == 20
    month = client.get('/api/v1/engagement?interval=month', headers=HEADERS).json()
    assert month['tables']['activity_by_start_date'][0]['dimensions']['period'] == '2025-03'


def test_unknown_view_dates_and_small_temporal_groups_are_visible(dashboard):
    client, session, _ = dashboard
    rows = list(session.scalars(select(EngagementEvent)))
    rows[0].first_viewed_on = date(2025, 3, 1)
    session.commit()
    for interval in ('day', 'week', 'month'):
        page = client.get('/api/v1/engagement', params={'interval': interval}, headers=HEADERS).json()
        assert page['metrics']['views']['value'] == 1200
        assert all(not r['metrics']['views']['suppressed'] for r in page['tables']['activity_by_start_date'])
        assert any(r['dimensions']['period'] == 'unknown' for r in page['tables']['activity_by_start_date'])


def test_assignment_selection_preserves_names_null_attempts_and_lateness(dashboard):
    client, session, offering = dashboard
    item = session.scalar(select(Assignment).where(Assignment.source_key == 'AT1'))
    item.name = 'Assignment 1'
    rows = list(session.scalars(select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == item.id)))
    for i, row in enumerate(rows):
        row.attempt = None if i < 10 else 2
        row.late = i < 10
        row.missing = False
        row.source_fields = dict(row.source_fields, seconds_late=7200 if i < 10 else 0)
    session.commit()
    options = client.get('/api/v1/assignment-options', headers=HEADERS).json()
    assert next(a for a in options if a['ref'] == 'AT1')['name'] == 'Assignment 1'
    page = client.get('/api/v1/assignments?assignments=AT1', headers=HEADERS).json()
    assert len(page['tables']['assessments']) == 1
    item = page['tables']['assessments'][0]
    assert item['label'] == 'Assignment 1'
    assert item['dimensions']['offering'] == offering.offering_code
    assert item['metrics']['mean_late_hours']['value'] == 2
    assert item['metrics']['mean_score_pct']['value'] == 47.5
    assert {r['dimensions']['band']: r['metrics']['students']['value'] for r in page['tables']['attempt_distribution']} == {'2': 10, 'unknown': 10}
    self_page = client.get('/api/v1/assignments?mode=self_assessment', headers=HEADERS).json()
    assert self_page['tables']['self_assessment_completion'][0]['metrics']['students']['value'] == 20
    assert 'weighted_outcomes' not in page['tables']


def test_new_course_catalog_and_all_page_scope_switches(dashboard):
    client, session, offering = dashboard
    course = Course(code='NEW100', name='New course')
    session.add(course); session.flush()
    other = CourseOffering(course_id=course.id, source_key='other', offering_code='NEW100_2026_JUL_PAR_1')
    session.add(other); session.commit()
    catalog = client.get('/api/v1/catalog', headers=HEADERS).json()
    assert any(c['code'] == 'NEW100' for c in catalog['courses'])
    for page in catalog['pages']:
        assert client.get('/api/v1/' + page, params={'course': 'NEW100', 'offering': offering.offering_code}, headers=HEADERS).status_code == 404
        response = client.get('/api/v1/' + page, params={'course': 'NEW100', 'offering': other.offering_code}, headers=HEADERS)
        assert response.status_code == 200
        assert response.json()['filters']['course'] == 'NEW100'
        assert client.get('/api/v1/' + page, params={'offerings': offering.offering_code + ',' + other.offering_code}, headers=HEADERS).status_code == 200


def test_invalid_multi_select_and_inapplicable_filters(dashboard):
    client, _, offering = dashboard
    for query in ('assignments=AT1,AT1', 'assignments=bad!', 'offering=X&offerings=Y', 'offerings=X,X', 'interval=hour'):
        assert client.get('/api/v1/assignments?' + query, headers=HEADERS).status_code == 422
    assert client.get('/api/v1/assignments?assignments=UNKNOWN', headers=HEADERS).status_code == 404
    assert client.get('/api/v1/assignments?mode=self_assessment&assignments=AT1', headers=HEADERS).status_code == 404
    assert client.get('/api/v1/engagement?assignments=AT1', headers=HEADERS).status_code == 422
    assert client.get('/api/v1/assignments', params={'offerings': offering.offering_code + ',UNKNOWN'}, headers=HEADERS).status_code == 404


def add_badges(session, offering):
    batch = ImportBatch(source='badge', file_sha256='d' * 64, importer_version='test', status='completed', finished_at=datetime(2025, 1, 1))
    badge = BadgeClass(name='Test class')
    session.add_all([batch, badge]); session.flush()
    session.add(BadgeClassCourseMapping(badge_class_id=badge.id, course_id=offering.course_id, status='confirmed', mapping_version='test'))
    students = list(session.scalars(select(Student)))
    for i, student in enumerate(students):
        session.add(BadgeAward(batch_id=batch.id, badge_class_id=badge.id, student_id=student.id,
            source_row=i + 2, revoked=i >= 10, awarded_at=datetime(2025, 3, 1, 14)))
    session.commit()
    return batch, badge, students


def test_badge_revoked_deduplication_rate_and_issue_dates(dashboard):
    client, session, offering = dashboard
    batch, badge, students = add_badges(session, offering)
    # Duplicate valid award and revoked history must not change unique holder count.
    for i, student in enumerate(students[:10]):
        session.add(BadgeAward(batch_id=batch.id, badge_class_id=badge.id, student_id=student.id,
            source_row=30 + i, revoked=True, awarded_at=datetime(2025, 3, 1, 14)))
        session.add(BadgeAward(batch_id=batch.id, badge_class_id=badge.id, student_id=student.id,
            source_row=50 + i, revoked=False, awarded_at=datetime(2025, 3, 1, 14)))
    session.commit()
    page = client.get('/api/v1/outcomes', headers=HEADERS).json()
    assert page['metrics']['valid_award_holders']['value'] == 10
    assert page['metrics']['revoked_only_holders']['value'] == 10
    assert page['metrics']['badge_completion_rate_pct']['value'] == 50
    assert {r['dimensions']['period'] for r in page['tables']['award_timeline']} == {'2025-03-02'}


def test_badge_ambiguity_cannot_be_resolved_by_filtering(dashboard):
    client, session, offering = dashboard
    add_badges(session, offering)
    other = CourseOffering(course_id=offering.course_id, source_key='second', offering_code='0AUTI0001_2026_MAR_PAR_1')
    session.add(other); session.flush()
    events = list(session.scalars(select(EngagementEvent)))
    for i, event in enumerate(events):
        session.add(EngagementEvent(batch_id=event.batch_id, student_id=event.student_id, offering_id=other.id,
            source_row=100 + i, event_type='page', times_viewed=10))
    session.commit()
    page = client.get('/api/v1/outcomes', params={'offering': offering.offering_code}, headers=HEADERS).json()
    assert page['metrics']['valid_award_holders']['value'] == 0
    states = {r['key']: r['metrics']['memberships']['value'] for r in page['tables']['badge_status']}
    assert states['needs_review'] == 20
    assert all(r['key'].startswith('multiple_offerings') for r in page['tables']['award_diagnostics'] if r['metrics']['records']['value'])


def test_register_new_course_is_idempotent_and_rejects_name_conflict(session):
    import pytest
    from app.courses import register
    assert register(session, 'NEW100', 'New course') == 'registered'
    assert register(session, 'NEW100', 'New course') == 'already_registered'
    with pytest.raises(ValueError):
        register(session, 'NEW100', 'Different name')
    with pytest.raises(ValueError):
        register(session, 'bad code', 'New course')


def test_small_late_group_and_assignment_scores_are_visible(dashboard):
    client, session, _ = dashboard
    rows = list(session.scalars(select(AssignmentSubmission).where(AssignmentSubmission.assignment_id ==
        session.scalar(select(Assignment.id).where(Assignment.source_key == 'AT1')))))
    for i, row in enumerate(rows):
        row.late = i == 0
        row.source_fields = dict(row.source_fields, seconds_late=3600 if i == 0 else 0)
    session.commit()
    page = client.get('/api/v1/assignments?assignments=AT1', headers=HEADERS).json()
    metrics = page['tables']['assessments'][0]['metrics']
    assert metrics['mean_score_pct']['value'] == 47.5
    assert metrics['late_students']['value'] == 1 and metrics['mean_late_hours']['value'] == 1
    assert all(not r['metrics']['students']['suppressed'] for r in page['tables']['late_flag'])


def test_badge_missing_identity_is_course_diagnostic_not_cohort_member(dashboard):
    client, session, offering = dashboard
    batch, badge, _ = add_badges(session, offering)
    for i in range(5):
        session.add(BadgeAward(batch_id=batch.id, badge_class_id=badge.id, student_id=None, source_row=100+i, revoked=False))
    session.commit()
    page = client.get('/api/v1/outcomes', params={'offering': offering.offering_code}, headers=HEADERS).json()
    assert page['metrics']['cohort_memberships']['value'] == 20
    diagnostic = next(r for r in page['tables']['award_diagnostics'] if r['key'].startswith('missing_identity'))
    assert diagnostic['metrics']['records']['value'] == 5
    assert diagnostic['dimensions']['scope'] == 'selected_courses_all_offerings'

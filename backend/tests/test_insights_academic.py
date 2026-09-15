"""Reviewed grading, independent awards and retrospective aggregate analysis."""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import numpy as np
import pytest
from sqlalchemy import select
from test_dashboard import dashboard, HEADERS
from app.models import Assignment, AssignmentSubmission, AssessmentRule, Course, CourseOffering, EngagementEvent
from app.models import ImportBatch, BadgeClass, BadgeClassCourseMapping, BadgeAward
from app.seed import seed_rules, CONFIG_PATH
from app.dashboard.data import Snapshot
from app.dashboard.academic import academic_records, score_band
from app.dashboard.insight_stats import association, correlation


def confirmed(session, offering):
    items = list(session.scalars(select(Assignment).where(Assignment.offering_id == offering.id)))
    for item in items:
        if item.source_key in {'AT1', 'AT2'}:
            item.assessment_key, item.mapping_status = item.source_key, 'confirmed'
    session.commit()
    return items


def test_seed_upgrade_preserves_history_and_reviewed_aliases(session):
    seed_rules(session, Path(CONFIG_PATH).with_name('assessment_rules.v1.json'))
    course = session.scalar(select(Course).where(Course.code == '0UNDE0001'))
    offering = CourseOffering(course_id=course.id, source_key='legacy', offering_code='0UNDE0001_TEST')
    session.add(offering); session.flush()
    assignment = Assignment(offering_id=offering.id, source_key='a', name='Assessment 1: Why treaty?  (40%)', max_score=100)
    self_activity = Assignment(offering_id=offering.id, source_key='self', name=assignment.name, max_score=0)
    session.add_all([assignment, self_activity]); session.flush()
    seed_rules(session); seed_rules(session)
    rules = list(session.scalars(select(AssessmentRule)))
    assert len(rules) == 4
    assert all(r.enabled == (r.version == 'confirmed-v2') for r in rules)
    assert assignment.assessment_key == 'AT1' and assignment.mapping_status == 'confirmed'
    assert self_activity.assessment_key is None


def test_exact_weighted_boundary_missing_scores_and_relevant_pages(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    rows = list(session.scalars(select(AssignmentSubmission).order_by(AssignmentSubmission.student_id)))
    people = sorted({r.student_id for r in rows})
    for row in rows:
        idx = people.index(row.student_id)
        row.score = Decimal('70') if idx < 5 else Decimal('69.9999') if idx < 10 else Decimal('80') if idx < 15 else None
    session.commit()
    records = academic_records(Snapshot(session), {offering.id})
    assert sum(r['state'] == 'pass' for r in records.values()) == 10
    assert sum(r['state'] == 'below_threshold' for r in records.values()) == 5
    assert sum(r['state'] == 'unknown' for r in records.values()) == 5
    for page in ('overview', 'assignments', 'outcomes'):
        result = client.get('/api/v1/' + page, headers=HEADERS).json()
        metrics = result['tables']['academic_results'][0]['metrics']
        assert metrics['passed']['value'] == 10
        assert metrics['unknown']['value'] == 5
        assert metrics['pass_rate_among_complete_pct']['value'] == pytest.approx(100*10/15, abs=.0001)
    result = client.get('/api/v1/outcomes', headers=HEADERS).json()
    assert result['metrics']['valid_award_holders']['value'] is None  # No badge export; grades cannot create awards.
    assert [score_band(Decimal(x)) for x in ('69.9999','70','79.9999','80')] == ['below_70','70_to_below_80','70_to_below_80','80_and_above']


def test_incomplete_component_not_renormalized_and_selection_does_not_change_final(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    first = session.scalar(select(AssignmentSubmission).join(Assignment).where(Assignment.source_key == 'AT2'))
    first.score = None
    session.commit()
    records = academic_records(Snapshot(session), {offering.id})
    assert records[(first.student_id, offering.id)]['final'] is None
    whole = client.get('/api/v1/assignments', headers=HEADERS).json()
    one = client.get('/api/v1/assignments', params={'assignments':'AT1'}, headers=HEADERS).json()
    assert whole['tables']['academic_results'] == one['tables']['academic_results']
    metrics = one['tables']['academic_results'][0]['metrics']
    assert metrics['complete_grades']['value'] == 19 and metrics['unknown']['value'] == 1
    assert all(not value['suppressed'] for value in metrics.values())


def test_ambiguous_component_is_not_silently_chosen(dashboard):
    _, session, offering = dashboard
    confirmed(session, offering)
    item = Assignment(offering_id=offering.id, source_key='DUP', name='Assessment 1', max_score=100,
        assessment_key='AT1', mapping_status='confirmed')
    session.add(item); session.flush()
    source = session.scalar(select(AssignmentSubmission))
    session.add(AssignmentSubmission(batch_id=source.batch_id, student_id=source.student_id, assignment_id=item.id,
        source_row=1000, score=100, status='graded', source_fields={'points_possible':100}))
    session.commit()
    assert all(r['final'] is None and r['missing_reason']=='unconfirmed_mapping_or_rule' for r in academic_records(Snapshot(session), {offering.id}).values())


def test_insights_targets_course_separation_and_known_association(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    rows = list(session.scalars(select(AssignmentSubmission)))
    people = sorted({r.student_id for r in rows})
    for row in rows:
        idx = people.index(row.student_id)
        row.score = 60 if idx < 5 else 75 if idx < 10 else 85
    for event in session.scalars(select(EngagementEvent)):
        idx = people.index(event.student_id)
        event.times_viewed = 60 if idx < 5 else 75 if idx < 10 else 85
        event.first_viewed_on = date(2025,1,1)
    session.commit()
    result = client.get('/api/v1/insights', params={'target':'AT1'}, headers=HEADERS)
    assert result.status_code == 200
    payload = result.json()
    assert all(r['dimensions']['target']=='AT1' for r in payload['tables']['associations'])
    row = next(r for r in payload['tables']['associations'] if r['dimensions']['feature']=='views' and r['dimensions']['outcome']=='score')
    assert row['metrics']['spearman_rho']['value'] == 1
    assert row['metrics']['rho_ci_low']['value'] == 1
    assert 'student_id' not in result.text and 'private-test-identity' not in result.text
    assert all(r['dimensions']['course']=='0AUTI0001' for r in payload['tables']['associations'])
    assert {r['key'] for r in payload['tables']['analysis_options']} == {'AT1','AT2','weighted_final','badge'}
    assert {r['key'] for r in payload['tables']['analysis_questions']} == {
        'engagement_grade', 'page_category', 'timing_submission', 'self_assessment', 'badge_relationship'}
    assert all(r['dimensions']['model_status']=='see_model_status' for r in payload['tables']['analysis_options'])


def test_constants_and_within_offering_confounding_are_not_fabricated():
    assert correlation(np.ones(20), np.arange(20)) is None
    rows = [dict(student=i%20, offering=i//20, x=i//20, y=50+30*(i//20)) for i in range(40)]
    result = association(rows, 'x', 'y')
    assert result['spearman_rho'] == 1
    assert result['within_offering_rank_r'] is None
    assert result['rho_ci_low'] == 1
    assert association(rows[:10], 'student', 'x')['rho_ci_low'] is None


def test_badge_revocation_does_not_change_academic_pass(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    batch = ImportBatch(source='badge', file_sha256='c'*64, importer_version='test', status='completed', finished_at=datetime(2025,1,1))
    badge = BadgeClass(name='Test badge')
    session.add_all([batch, badge]); session.flush()
    session.add(BadgeClassCourseMapping(badge_class_id=badge.id, course_id=offering.course_id, status='confirmed', mapping_version='test'))
    for index, student in enumerate(session.scalars(select(EngagementEvent.student_id))):
        session.add(BadgeAward(batch_id=batch.id, source_row=index+2, badge_class_id=badge.id, student_id=student,
            revoked=index < 5, match_status='manual_review', outcome='unknown'))
    session.commit()
    result = client.get('/api/v1/outcomes', headers=HEADERS).json()
    assert result['tables']['academic_results'][0]['metrics']['passed']['value'] == 10
    assert result['metrics']['valid_award_holders']['value'] == 15
    assert result['metrics']['revoked_only_holders']['value'] == 5


def test_partial_batch_correlation_is_aggregate_and_badge_has_no_grade_inputs(dashboard):
    client, session, offering = dashboard
    confirmed(session, offering)
    session.add(CourseOffering(course_id=offering.course_id, source_key='another', offering_code='0AUTI0001_OTHER'))
    session.commit()
    result = client.get('/api/v1/insights', headers=HEADERS, params={'offering':offering.offering_code,'target':'AT1'}).json()
    assert all(not r['metrics']['spearman_rho']['suppressed'] for r in result['tables']['associations'])
    result = client.get('/api/v1/insights', headers=HEADERS, params={'target':'badge'}).json()
    assert all(r['dimensions']['feature'] not in {'score','AT1','AT2','weighted_final'} for r in result['tables']['associations'])
    assert {'AT1_submitted', 'AT2_submitted'} <= {r['dimensions']['feature'] for r in result['tables']['associations']}
    assert all(r['dimensions']['analysis_area'] == 'badge_relationship' for r in result['tables']['associations'])


def test_self_assessment_and_unknown_engagement_are_features_not_grades(dashboard):
    _, session, offering = dashboard
    confirmed(session, offering)
    from app.dashboard.insight_features import learning_records, target_rows
    records = learning_records(Snapshot(session), {offering.id})
    assert all(r['self_assessment_completion_pct']==100 for r in records.values())
    assert all(r['first_contact_date_count'] is None for r in records.values())
    assert all(r['score'] is None for r in target_rows(records, 'badge'))


@pytest.mark.parametrize('page,query', [('insights',{'target':'final_exam'}), ('overview',{'target':'AT1'}),
    ('insights',{'assignments':'AT1'}), ('rules',{'target':'badge'}), ('assignment-options',{'target':'AT2'})])
def test_target_filters_reject_unsupported_requests(dashboard, page, query):
    client, _, _ = dashboard
    assert client.get('/api/v1/'+page, params=query, headers=HEADERS).status_code == 422

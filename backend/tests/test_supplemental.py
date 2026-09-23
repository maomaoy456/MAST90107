"""Source contracts, transactional imports and frontend-facing aggregate answers."""
from datetime import date, datetime
import html
import json
import pytest
from sqlalchemy import select, func
from test_dashboard import dashboard, HEADERS
from app.models import ImportBatch, SurveyResponse, SupportCase, OfferingCalendar, AssignmentSubmission, Assignment
from app.supplemental.readers import salesforce, survey
from app.supplemental.importer import import_support, import_survey, import_calendars
from app.supplemental.schema import THEMES

KEY = "test-only-identity-secret-at-least-32-characters"


def html_file(path, records):
    columns = list(records[0])
    rows = [columns] + [[str(r.get(c, "")) for c in columns] for r in records]
    contents = '<meta charset="ISO-8859-1"><table>' + ''.join('<tr>' + ''.join('<td>' + html.escape(v) + '</td>' for v in row) + '</tr>' for row in rows) + '</table>'
    path.write_bytes(contents.encode('iso-8859-1'))
    return path


def add_survey(session, offering):
    batch = ImportBatch(source='survey', scope='survey:' + offering.offering_code,
        file_sha256='e' * 64, importer_version='synthetic', status='completed', finished_at=datetime(2026, 1, 1))
    session.add(batch); session.flush()
    for i in range(20):
        answers = {q: 5 if i < 10 else 3 for theme in THEMES.values() for q in theme}
        session.add(SurveyResponse(batch_id=batch.id, offering_id=offering.id, response_digest=f'private-response-{i}',
            finished=True, nps=9 if i < 10 else 7, answers=answers,
            feedback={'Q2.3': 'private-person@example.org useful resources'}, source_fields={}))
    session.commit()


def test_survey_frontend_themes_nps_and_redacted_comments(dashboard):
    client, session, offering = dashboard
    add_survey(session, offering)
    for endpoint in ('overview', 'assignments', 'outcomes'):
        response = client.get('/api/v1/' + endpoint, headers=HEADERS)
        assert response.status_code == 200
        assert 'private-person' not in response.text and 'private-response' not in response.text
        page = response.json()
        assert page['metrics']['survey_completed_responses']['value'] == 20
        assert all(r['metrics']['mean_agreement']['value'] == 4 for r in page['tables']['survey_themes'])
        if endpoint == 'assignments':
            assert {r['dimensions']['theme'] for r in page['tables']['survey_themes']} == {'assessment'}
        else:
            assert page['tables']['survey_nps'][0]['metrics']['nps']['value'] == 50
        if endpoint == 'outcomes':
            comments = page['tables']['survey_feedback_comments']
            assert comments and '[email removed] useful resources' in comments[0]['label']
            assert any('Anonymous feedback comments' in note for note in page['notes'])
        else:
            assert 'survey_feedback_comments' not in page['tables']
            assert not any('Anonymous feedback comments' in note for note in page['notes'])
    assert 'survey_feedback_comments' not in client.get('/api/v1/engagement', headers=HEADERS).json()['tables']
    # Aggregate NPS remains visible; response identities and text remain private.
    row = session.scalar(select(SurveyResponse))
    row.nps = 0
    session.commit()
    page = client.get('/api/v1/outcomes', headers=HEADERS).json()
    assert page['tables']['survey_nps'][0]['metrics']['nps']['value'] is not None
    assert not page['tables']['survey_nps'][0]['metrics']['nps']['suppressed']


def test_theme_scores_weight_respondents_equally(dashboard):
    client, session, offering = dashboard
    add_survey(session, offering)
    rows = list(session.scalars(select(SurveyResponse)))
    for row in rows[:10]:
        row.answers = dict(row.answers, Q5_ignored=1)
        row.answers = {k: v for k, v in row.answers.items() if k not in ('Q5.0_4', 'Q5.0_5')}
    session.commit()
    page = client.get('/api/v1/assignments', headers=HEADERS).json()
    assert page['tables']['survey_themes'][0]['metrics']['mean_agreement']['value'] == 4


def test_salesforce_reader_honours_declared_encoding():
    raw = '<meta charset="ISO-8859-1"><table><tr><th>Subject</th></tr><tr><td>caf\xe9 &amp; support</td></tr></table>'.encode('latin1')
    assert salesforce(raw).iloc[0]['Subject'] == 'caf\xe9 & support'
    with pytest.raises(ValueError):
        survey(b'ResponseId,Finished,Q2\nactual,true,9\nactual2,true,8\n')


def test_calendar_exports_overlap_without_double_counting(dashboard, tmp_path):
    _, session, offering = dashboard
    record = {'Subject Offering ID: Subject Offering ID': offering.offering_code,
        'Subject Offering ID: Start Date': '1/03/2025', 'Subject Offering ID: End Date': '31/03/2025', 'Enrolment Status': 'Enrolled'}
    p = html_file(tmp_path/'calendar.xls', [record] * 20)
    assert import_calendars(session, [p, p], KEY) == 'completed'
    session.commit()
    assert session.scalar(select(OfferingCalendar)).enrolment_records == 20
    assert offering.starts_on == date(2025, 3, 1)
    assert import_calendars(session, [p, p], KEY) == 'already_imported'
    bad = html_file(tmp_path/'bad.xls', [record | {'Subject Offering ID: End Date': '28/02/2025'}])
    with pytest.raises(ValueError):
        import_calendars(session, [bad], KEY)
    assert offering.ends_on == date(2025, 3, 31)


def test_support_window_timezone_missing_subject_and_response_time(dashboard, tmp_path):
    client, session, offering = dashboard
    offering.starts_on, offering.ends_on = date(2025, 3, 1), date(2025, 3, 2)
    session.commit()
    base = {'Subject': '', 'Date/Time Opened': '2/03/2025 23:59', 'Age (Hours)': '0',
            'Open': '0', 'Closed': '1', 'Case Origin': 'Email', 'Account Name': 'private person'}
    records = [base] * 10 + [base | {'Date/Time Opened': '3/03/2025 00:00'}] * 5
    p = html_file(tmp_path/'cases.xls', records)
    assert import_support(session, p, '0AUTI0001', KEY) == 'completed'
    session.commit()
    assert session.scalar(select(func.count()).select_from(SupportCase)) == 10
    row = session.scalar(select(SupportCase))
    assert row.opened_at == datetime(2025, 3, 2, 12, 59)
    assert row.response_hours == 0 and row.subject is None
    assert 'Account Name' not in row.source_fields
    assert import_support(session, p, '0AUTI0001', KEY) == 'already_imported'
    session.commit()
    response = client.get('/api/v1/engagement', headers=HEADERS)
    assert 'private person' not in response.text
    page = response.json()
    assert page['metrics']['support_records']['value'] is None
    assert page['tables']['support_data_status'][0]['dimensions']['status'] == 'excluded_unverified_scope'
    assert 'support_summary' not in page['tables']


def test_support_representative_titles_remove_direct_identifiers(dashboard):
    client, session, offering = dashboard
    offering.starts_on, offering.ends_on = date(2025, 3, 1), date(2025, 3, 31)
    batch = ImportBatch(source='salesforce', scope='support:0AUTI0001', file_sha256='f'*64,
        importer_version='synthetic', status='completed', finished_at=datetime(2026, 1, 1),
        summary={'course_scope_verified': True})
    session.add(batch); session.flush()
    for i in range(10):
        session.add(SupportCase(batch_id=batch.id, course_id=offering.course_id, source_row=i+2,
            opened_at=datetime(2025, 3, 5), response_hours=2, is_open=False, is_closed=True,
            channel='Email', subject='Student ID 123456 needs Canvas help; private@example.org', source_fields={}))
    session.commit()
    response = client.get('/api/v1/engagement', headers=HEADERS)
    assert '123456' not in response.text and 'private@example.org' not in response.text
    rows = response.json()['tables']['support_issue_summaries']
    assert rows and '[student ID removed]' in rows[0]['label'] and '[email removed]' in rows[0]['label']
    assert any('representative issue titles' in note for note in response.json()['notes'])
    overview = client.get('/api/v1/overview', headers=HEADERS).json()
    assert 'support_issue_summaries' not in overview['tables']
    assert not any('representative issue titles' in note for note in overview['notes'])
    assert 'support_issue_summaries' not in client.get('/api/v1/outcomes', headers=HEADERS).json()['tables']


def test_anonymous_text_removes_common_direct_identifiers():
    from app.dashboard.text import anonymous_text
    value = anonymous_text('My name is Jane Doe; ID: abc1234; phone +61 412 345 678; https://example.org @janed')
    assert 'Jane Doe' not in value and 'abc1234' not in value and '412 345 678' not in value
    assert 'example.org' not in value and '@janed' not in value


def test_scoped_survey_import_rejects_duplicates_and_preserves_partial(dashboard, tmp_path):
    _, session, offering = dashboard
    import csv
    path = tmp_path/'survey.csv'
    fields = ['ResponseId', 'Finished', 'Q2', 'RecordedDate', 'Q1_1']
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerow(['Question'] * len(fields))
        writer.writerow([json.dumps({'ImportId': name}) for name in fields])
        writer.writerow(['private-response', 'False', '11', '2025-03-01T00:00:00Z', 'Strongly agree'])
    assert import_survey(session, path, offering.offering_code, KEY) == 'completed'
    session.commit()
    row = session.scalar(select(SurveyResponse))
    assert row.nps is None and row.finished is False and row.answers['Q1_1'] == 5
    assert row.response_digest != 'private-response'
    with path.open('a', newline='', encoding='utf-8') as stream:
        csv.writer(stream).writerow(['private-response', 'True', '9', '', 'Strongly agree'])
    with pytest.raises(ValueError):
        import_survey(session, path, offering.offering_code, KEY)
    assert session.scalar(select(func.count()).select_from(SurveyResponse)) == 1


def test_assignment_cumulative_curve_keeps_non_submitters(dashboard):
    client, session, offering = dashboard
    ids = list(session.scalars(select(Assignment.id).where(Assignment.source_key.in_(['AT1', 'AT2']))))
    for aid in ids:
        for i, row in enumerate(session.scalars(select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == aid))):
            row.source_fields = dict(row.source_fields, due_at='2025-03-10T00:00:00Z')
            row.submitted_at = datetime(2025, 3, 9, 12) if i < 10 else None
            row.graded_at = datetime(2025, 3, 11, 12) if i < 10 else None
    session.commit()
    page = client.get('/api/v1/assignments', headers=HEADERS,
        params={'offering': offering.offering_code, 'assignments': 'AT1,AT2'}).json()
    curve = [r for r in page['tables']['assignment_cumulative_submission'] if r['dimensions']['days_relative_to_deadline'] == '0']
    assert all(r['metrics']['submitted_pct']['value'] == 50 for r in curve)
    assert page['tables']['assignment_time_summary'][0]['metrics']['median_grading_days']['value'] == 2
    for name in ('assignment_deadline_coverage', 'assignment_submission_timing', 'assignment_time_summary'):
        assert {r['dimensions']['assignment_name'] for r in page['tables'][name]} == {'AT1', 'AT2'}
    pairs = {r['key']: r['metrics']['students']['value'] for r in page['tables']['assignment_pair_submission']}
    assert pairs == {'both_submitted': 10, 'first_only': 0, 'second_only': 0, 'neither_submitted': 10}


def test_calendar_phase_does_not_set_academic_completion(dashboard):
    client, session, offering = dashboard
    offering.starts_on, offering.ends_on = date(2025, 3, 1), date(2025, 4, 1)
    session.commit()
    options = client.get('/api/v1/catalog', headers=HEADERS).json()['offerings']
    assert options[0]['calendar_phase'] == 'after_end'
    assert options[0]['status'] == 'unknown'

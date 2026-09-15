"""One internal student/offering record. Summary clicks are retrospective only."""
from collections import defaultdict
from app.dashboard.academic import academic_records
from app.dashboard.assignments import selected_submissions
from app.dashboard.assignment_time import deadline
from app.dashboard.activity import local_date
from app.dashboard.badges import resolve_awards
from app.dashboard.engagement import category

FEATURES = ("views", "participations", "content_view_share", "assessment_view_share",
            "first_contact_days_from_start", "first_contact_date_count", "self_assessment_completion_pct",
            "first_contact_days_from_deadline", "first_content_days_from_deadline", "first_assessment_days_from_deadline")
BADGE_FEATURES = FEATURES + ("AT1_submitted", "AT2_submitted")


def submission_state(row):
    if row is None or row.excused:
        return None
    return 1 if row.status in {"submitted", "graded"} else 0 if row.status in {"unsubmitted", "missing"} else None


def badge_states(data, scope):
    population = {(r.student_id, r.offering_id) for r in data.engagement if r.offering_id in scope}
    valid, revoked, review = set(), set(), set()
    for award, course, offering, status in resolve_awards(data):
        if offering in scope:
            (revoked if award.revoked else valid).add((award.student_id, offering))
        elif status == "multiple_offerings":
            review.update(p for p in population if p[0] == award.student_id and data.offerings[p[1]].course_id == course)
    return {p: "valid" if p in valid else "revoked_only" if p in revoked else "needs_review" if p in review else "no_matched_award" for p in population}


def learning_records(data, scope):
    activity, self_rows = defaultdict(list), defaultdict(list)
    academic = academic_records(data, scope)
    for row in data.engagement:
        if row.offering_id in scope:
            activity[(row.student_id, row.offering_id)].append(row)
    for row in selected_submissions(data, scope, "self_assessment"):
        self_rows[(row.student_id, data.assignments[row.assignment_id].offering_id)].append(row)
    badges = badge_states(data, scope) if "badge" in data.batches else {}
    result = {}
    for pair in academic.keys() | activity.keys():
        student, offering_id = pair
        offering = data.offerings[offering_id]
        academic_result = academic.get(pair)
        events = activity.get(pair, [])
        dates = [r.first_viewed_on for r in events if r.first_viewed_on is not None]
        first = min(dates) if dates else None
        views = sum(r.times_viewed for r in events) if events and all(r.times_viewed is not None for r in events) else None
        participates = sum(r.participated_count for r in events) if events and all(r.participated_count is not None for r in events) else None
        own = self_rows.get(pair, [])
        known_self = bool(own) and all(not r.excused and r.status in {"submitted", "graded", "unsubmitted"} for r in own)
        rate = 100 * sum(r.status in {"submitted", "graded"} for r in own) / len(own) if known_self else None
        category_first = {kind: min((r.first_viewed_on for r in events if category(r) == kind and r.first_viewed_on), default=None) for kind in ('content', 'assessment')}
        result[pair] = dict(student=student, offering=offering_id, course=offering.course_id, category_first=category_first,
            engagement_available=bool(events), academic=academic_result, first=first, badge=badges.get(pair, "unknown"),
            views=views, participations=participates,
            content_view_share=100 * sum(r.times_viewed for r in events if category(r) == "content") / views if views else None,
            assessment_view_share=100 * sum(r.times_viewed for r in events if category(r) == "assessment") / views if views else None,
            first_contact_days_from_start=(first - offering.starts_on).days if first and offering.starts_on else None,
            first_contact_date_count=len(set(dates)) if dates else None, self_assessment_completion_pct=rate,
            **{key + "_submitted": submission_state(academic_result['rows'].get(key) if academic_result else None)
               for key in ("AT1", "AT2")})
    return result


def target_rows(records, target):
    rows = []
    for pair, record in records.items():
        row = dict(record, first_contact_days_from_deadline=None, first_content_days_from_deadline=None,
                   first_assessment_days_from_deadline=None, score=None, submitted=None)
        academic = record['academic']
        if target == "badge":
            row['outcome_group'] = record['badge']
            row['badge_observed'] = 1 if record['badge'] == "valid" else 0 if record['badge'] in {"revoked_only", "no_matched_award"} else None
        elif target == "weighted_final":
            row['score'] = float(academic['final']) if academic and academic['final'] is not None else None
        else:
            source = academic['rows'].get(target) if academic else None
            score = academic['scores'].get(target) if academic else None
            row['score'] = float(score) if score is not None else None
            if source:
                row['missing_flag'] = int(source.missing) if source.missing is not None else None
                row['late_flag'] = int(source.late) if source.late is not None else None
                row['submitted'] = 1 if source.status in {"submitted", "graded"} else 0 if source.status in {"unsubmitted", "missing"} else None
                if source.excused:
                    row['submitted'] = None
                due = local_date(deadline(source))
                row['first_contact_days_from_deadline'] = (record['first'] - due).days if record['first'] and due else None
                for kind, first in record['category_first'].items():
                    row['first_' + kind + '_days_from_deadline'] = (first - due).days if first and due else None
                row['submission_days_from_deadline'] = (source.submitted_at - deadline(source)).total_seconds() / 86400 if source.submitted_at and due else None
        row['pair'] = pair
        rows.append(row)
    return rows

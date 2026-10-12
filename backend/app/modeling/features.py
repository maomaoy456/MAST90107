"""Leakage-aware feature snapshots for course pass and recorded Badge targets."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

import pandas as pd

from app.dashboard.academic import academic_records
from app.dashboard.assignment_time import deadline
from app.dashboard.assignments import selected_submissions
from app.dashboard.badges import resolve_awards
from app.dashboard.engagement import category

MELBOURNE = ZoneInfo("Australia/Melbourne")
PASS_LABELS = ("not_passed", "passed")
BADGE_LABELS = ("no_valid_badge", "valid_badge")
BASE_FEATURES = (
    "safe_views", "safe_participations", "resources_touched", "content_resources_touched",
    "assessment_resources_touched", "other_resources_touched", "content_safe_view_share",
    "assessment_safe_view_share", "first_contact_days_from_start", "first_content_days_from_start",
    "first_assessment_days_from_start", "distinct_first_contact_dates",
    "closed_resource_count", "spanning_resource_count", "self_assessment_completion_pct",
)


@dataclass
class TrainingData:
    frame: pd.DataFrame
    labels: list[str]
    groups: list[int]
    feature_names: list[str]
    summary: dict


def end_of_day(day: date) -> datetime:
    return datetime.combine(day, time.max, MELBOURNE).astimezone(timezone.utc).replace(tzinfo=None)


def seen_by(row, cutoff):
    if row.first_viewed_at is not None:
        return row.first_viewed_at <= cutoff
    return row.first_viewed_on is not None and row.first_viewed_on <= cutoff.replace(tzinfo=timezone.utc).astimezone(MELBOURNE).date()


def behavior(events, offering, cutoff):
    touched = [row for row in events if seen_by(row, cutoff)]
    closed = [row for row in touched if row.last_viewed_at is not None and row.last_viewed_at <= cutoff]
    views_known = all(row.times_viewed is not None for row in closed)
    parts_known = all(row.participated_count is not None for row in closed)
    safe_views = sum(row.times_viewed for row in closed) if views_known else None
    safe_parts = sum(row.participated_count for row in closed) if parts_known else None
    dates = [row.first_viewed_on for row in touched if row.first_viewed_on is not None]
    first = min(dates) if dates else None
    first_by_kind = {kind: min((row.first_viewed_on for row in touched if category(row) == kind and row.first_viewed_on), default=None)
                     for kind in ("content", "assessment")}
    category_views = {kind: sum(row.times_viewed for row in closed if category(row) == kind) for kind in ("content", "assessment")}
    result = {
        "safe_views": safe_views, "safe_participations": safe_parts,
        "resources_touched": len(touched), "closed_resource_count": len(closed),
        "spanning_resource_count": len(touched) - len(closed),
        "distinct_first_contact_dates": len(set(dates)),
        "first_contact_days_from_start": (first - offering.starts_on).days if first and offering.starts_on else None,
        "content_safe_view_share": 100 * category_views["content"] / safe_views if safe_views else None,
        "assessment_safe_view_share": 100 * category_views["assessment"] / safe_views if safe_views else None,
    }
    for kind in ("content", "assessment", "other"):
        result[kind + "_resources_touched"] = sum(category(row) == kind for row in touched)
    for kind in ("content", "assessment"):
        first_kind = first_by_kind[kind]
        result["first_" + kind + "_days_from_start"] = (first_kind - offering.starts_on).days if first_kind and offering.starts_on else None
    return result


def submitted_by(row, cutoff):
    if row is None or row.excused:
        return None
    if row.submitted_at is not None:
        return int(row.submitted_at <= cutoff)
    due = deadline(row)
    return 0 if due is not None and due <= cutoff and row.status in {"unsubmitted", "missing"} else None


def self_assessment(rows, cutoff):
    states = []
    for row in rows:
        due = deadline(row)
        if row.excused or due is None or due > cutoff:
            continue
        states.append(submitted_by(row, cutoff))
    known = [state for state in states if state is not None]
    return 100 * sum(known) / len(known) if known else None


def badge_labels(data, scope, as_of, wait_days=60):
    population = {(row.student_id, row.offering_id) for row in data.engagement if row.offering_id in scope}
    valid, revoked, ambiguous = {}, set(), set()
    for award, course, offering, status in resolve_awards(data):
        if offering in scope and award.revoked:
            revoked.add((award.student_id, offering))
        elif offering in scope and award.awarded_at is not None:
            pair = (award.student_id, offering)
            day = award.awarded_at.replace(tzinfo=timezone.utc).astimezone(MELBOURNE).date()
            valid[pair] = min(valid.get(pair, day), day)
        elif status == "multiple_offerings":
            ambiguous.update(pair for pair in population if pair[0] == award.student_id and data.offerings[pair[1]].course_id == course)
    labels, excluded = {}, Counter()
    for pair in population:
        offering = data.offerings[pair[1]]
        if offering.ends_on is None or (as_of - offering.ends_on).days < wait_days:
            excluded["immature_badge_window"] += 1
        elif pair in ambiguous:
            excluded["ambiguous_badge_offering"] += 1
        elif pair in valid:
            delay = (valid[pair] - offering.ends_on).days
            if delay > wait_days:
                excluded["late_award_over_60_days"] += 1
            else:
                labels[pair] = "valid_badge"
        elif pair in revoked:
            labels[pair] = "no_valid_badge"
        else:
            labels[pair] = "no_valid_badge"
    return labels, dict(excluded)


def build_training_data(data, course_id, target, badge_as_of):
    scope = {oid for oid, offering in data.offerings.items() if offering.course_id == course_id}
    academic = academic_records(data, scope)
    events = defaultdict(list)
    for row in data.engagement:
        if row.offering_id in scope:
            events[(row.student_id, row.offering_id)].append(row)
    self_rows = defaultdict(list)
    for row in selected_submissions(data, scope, "self_assessment"):
        self_rows[(row.student_id, data.assignments[row.assignment_id].offering_id)].append(row)
    badge, badge_excluded = badge_labels(data, scope, badge_as_of) if target == "badge" and badge_as_of else ({}, {})
    features, labels, groups, included_offerings = [], [], [], set()
    excluded = Counter()
    if target not in {"pass", "badge"}:
        raise ValueError("unknown_target")
    pairs = set(events) if target == "badge" else set(academic) & set(events)
    for pair in pairs:
        person, offering_id = pair
        offering = data.offerings[offering_id]
        record = academic.get(pair)
        if target == "badge":
            if pair not in badge:
                excluded["badge_outcome_unavailable"] += 1
                continue
            cutoff, label = end_of_day(offering.ends_on), badge[pair]
        else:
            final = record["final"] if record else None
            due_dates = [deadline(row) for row in (record["rows"].values() if record else ()) if row is not None]
            due_dates = [due for due in due_dates if due is not None]
            cutoff = max(due_dates) if due_dates else end_of_day(offering.ends_on) if offering.ends_on else None
            if cutoff is None or final is None:
                excluded["missing_cutoff_or_complete_course_result"] += 1
                continue
            label = "passed" if record["state"] == "pass" else "not_passed"
        row = behavior(events[pair], offering, cutoff)
        row["self_assessment_completion_pct"] = self_assessment(self_rows.get(pair, []), cutoff)
        features.append(row); labels.append(label); groups.append(person); included_offerings.add(offering_id)
    feature_names = list(BASE_FEATURES)
    frame = pd.DataFrame(features, columns=feature_names, dtype=float)
    summary = {"included_records": len(labels), "distinct_students": len(set(groups)),
               "contributing_offerings": len(included_offerings),
               "excluded": dict(excluded), "badge_excluded": badge_excluded,
               "feature_policy": "canvas_and_non_scored_self_assessment_only_v2",
               "feature_cutoff": "latest_assessment_deadline_for_pass;course_end_for_badge",
               "excluded_predictors": ["AT1_submission", "AT2_submission", "AT1_score", "AT2_score", "weighted_grade"]}
    return TrainingData(frame, labels, groups, feature_names, summary)


def data_signature(data, course_id, target, badge_as_of, config):
    offerings = sorted((o.offering_code, str(o.starts_on), str(o.ends_on)) for o in data.offerings.values() if o.course_id == course_id)
    batches = sorted((name, batch.file_sha256, batch.importer_version) for name, batch in data.batches.items())
    rules = sorted((r.version, r.config_sha256, str(r.offering_id)) for r in data.rules if r.course_id == course_id and r.enabled)
    payload = {"target": target, "badge_as_of": str(badge_as_of), "offerings": offerings,
               "batches": batches, "rules": rules, "config": config}
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

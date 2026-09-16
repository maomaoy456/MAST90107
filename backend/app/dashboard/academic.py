"""Confirmed weighted grades, independent of any award or revocation evidence."""
from collections import defaultdict
from decimal import Decimal
from statistics import mean
from app.dashboard.assignments import selected_submissions, exact_percentage
from app.dashboard.activity import group_guard
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric


def components(data, offering_id, rows):
    """Require one active reference per component; never choose between duplicates."""
    active = {r.assignment_id for r in rows}
    rule = data.rule(data.offerings[offering_id])
    if not rule or rule.status != "confirmed" or {c['key'] for c in rule.components} != {"AT1", "AT2"}:
        return {}, None
    mapped = {}
    for c in rule.components:
        candidates = [data.assignments[i] for i in active if (
            data.assignments[i].source_key == c['assignment_ref'] if c.get('assignment_ref') else
            data.assignments[i].mapping_status == "confirmed" and data.assignments[i].assessment_key == c['key'])]
        if len(candidates) != 1 or candidates[0].max_score is None or candidates[0].max_score <= 0:
            return {}, rule
        mapped[c['key']] = candidates[0].id
    if len(set(mapped.values())) != 2:
        return {}, rule
    return mapped, rule


def academic_records(data, scope):
    grouped = defaultdict(list)
    for row in selected_submissions(data, scope):
        grouped[data.assignments[row.assignment_id].offering_id].append(row)
    result = {}
    for offering_id, rows in grouped.items():
        mapped, rule = components(data, offering_id, rows)
        people = defaultdict(dict)
        for row in rows:
            people[row.student_id][row.assignment_id] = row
        for student, submissions in people.items():
            source = {key: submissions.get(i) for key, i in mapped.items()}
            scores = {key: exact_percentage(row) if row is not None else None for key, row in source.items()}
            complete = bool(mapped) and all(v is not None for v in scores.values())
            final = sum(scores[c['key']] * Decimal(str(c['weight'])) for c in rule.components) if complete else None
            result[(student, offering_id)] = dict(rows=source, scores=scores, final=final, rule=rule,
                state="pass" if final is not None and final >= rule.pass_threshold else "below_threshold" if final is not None else "unknown",
                missing_reason="unconfirmed_mapping_or_rule" if not mapped else "incomplete_valid_scores" if not complete else "none")
    return result


def score_band(value):
    return "unknown" if value is None else "below_70" if value < 70 else "70_to_below_80" if value < 80 else "80_and_above"


def add_academic(page, data, scope):
    records = academic_records(data, scope)
    for offering_id in sorted(scope):
        selected = {p: r for p, r in records.items() if p[1] == offering_id}
        members = set(selected)
        states = {k: {p for p, r in selected.items() if r['state'] == k} for k in ("pass", "below_threshold", "unknown")}
        valid = states['pass'] | states['below_threshold']
        gate = group_guard(list(states.values()), members, data.privacy_reason({offering_id}))
        offering = data.offerings[offering_id]
        rule = data.rule(offering)
        dims = {"offering": offering.offering_code or "unlabelled", "unit": "student_offering_memberships",
            "scope": "whole_offering_ignores_assignment_selection", "rule_version": rule.version if rule else "unavailable"}
        if rule:
            dims["calculation_rule"] = " + ".join(f"{c['key']} {float(c['weight']) * 100:g}%" for c in rule.components)
            dims["pass_threshold_pct"] = str(rule.pass_threshold)
        values = [float(r['final']) for r in selected.values() if r['final'] is not None]
        page.tables.setdefault("academic_results", []).append(TableRow(key=dims['offering'], label="Weighted course grade", dimensions=dims, metrics={
            "observed_memberships": metric(len(members), members, gate),
            "complete_grades": metric(len(valid), valid, gate),
            "passed": metric(len(states['pass']), states['pass'], gate),
            "below_threshold": metric(len(states['below_threshold']), states['below_threshold'], gate),
            "unknown": metric(len(states['unknown']), states['unknown'], gate),
            "mean_weighted_pct": metric(mean(values) if values else None, valid, gate),
            "pass_rate_among_complete_pct": metric(100 * len(states['pass']) / len(valid) if valid else None, valid, gate)}))
        bands = {k: {p for p, r in selected.items() if score_band(r['final']) == k} for k in ("below_70", "70_to_below_80", "80_and_above", "unknown")}
        band_gate = group_guard(list(bands.values()), members, gate)
        for band, people in bands.items():
            page.tables.setdefault("weighted_grade_distribution", []).append(TableRow(key=dims['offering'] + ':' + band,
                label=band, dimensions=dims | {"band": band}, metrics={"memberships": metric(len(people), people, band_gate)}))
    page.notes += ["Academic pass is separate from Badge: the reviewed default is AT1 40% + AT2 60%, pass at >=70 without rounding; there is no final exam.",
        "Weighted results require both valid graded components; missing grades are unknown, not zero. Pass rate uses complete grades, not all enrolled students. Offering overrides remain versioned."]

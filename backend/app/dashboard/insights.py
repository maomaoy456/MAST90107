"""Course-separated exploration plus privacy-safe model status."""
from statistics import mean, median
from app.dashboard.activity import group_guard
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric
from app.dashboard.insight_features import FEATURES, BADGE_FEATURES, learning_records, target_rows
from app.dashboard.insight_stats import association

TARGETS = ("AT1", "AT2", "weighted_final", "badge")


def privacy(rows, groups, reason=None):
    people = {r['student'] for r in rows}
    return group_guard([{r['student'] for r in group} for group in groups], people, reason)


def add_groups(page, rows, course, target, group_name, labels, reason, features=FEATURES):
    groups = {label: [r for r in rows if r.get(group_name) == label] for label in labels}
    gate = privacy(rows, list(groups.values()), reason)
    for label, group in groups.items():
        people = {r['student'] for r in group}
        dims = {"course": course, "target": target, "grouping": group_name, "group": str(label)}
        values = {"memberships": metric(len(group), people, gate), "students": metric(len(people), people, gate)}
        for feature in features:
            measured = [r for r in group if r.get(feature) is not None]
            members = {r['student'] for r in measured}
            blocked = privacy(group, [measured], gate)
            values[feature + '_n'] = metric(len(measured), members, blocked)
            values['mean_' + feature] = metric(mean(r[feature] for r in measured) if measured else None, members, blocked)
            ordered = sorted(r[feature] for r in measured)
            def quantile(fraction):
                if not ordered:
                    return None
                position = (len(ordered) - 1) * fraction
                low, high = int(position), min(int(position) + 1, len(ordered) - 1)
                return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
            values['median_' + feature] = metric(median(ordered) if ordered else None, members, blocked)
            values['q1_' + feature] = metric(quantile(.25), members, blocked)
            values['q3_' + feature] = metric(quantile(.75), members, blocked)
        page.tables.setdefault("behavior_by_outcome", []).append(TableRow(
            key=f"{course}:{target}:{group_name}:{label}", label=str(label), dimensions=dims, metrics=values))


def build_insights(page, data, scope, reason):
    page.cohort = "course_separated_student_offering_records"
    records = learning_records(data, scope)
    targets = TARGETS if page.filters.target == "all" else (page.filters.target,)
    people = {p[0] for p in records}
    page.metrics['students'] = metric(len(people) if {'assignment', 'engagement'} & data.batches.keys() else None, people, reason)
    page.tables['analysis_options'] = [TableRow(key=t, label=t, dimensions={"target": t,
        "analysis": "exploratory_and_modeling", "model_status": "see_model_status", "final_definition": "AT1*0.4+AT2*0.6; effective offering rule applies",
        "badge_prediction_policy": "exclude_AT1_AT2_scores_and_weighted_grade"}, metrics={}) for t in TARGETS]
    questions = (
        ("engagement_grade", "Engagement and passing", "Canvas views and interactive actions versus confirmed pass outcomes."),
        ("page_category", "Learning activity mix", "Content and assessment-page activity among students who passed or did not pass."),
        ("timing_submission", "When students started and submitted", "Elapsed calendar time from course start or first activity to submission."),
        ("self_assessment", "Self-assessment and passing", "Self-assessment completion groups versus confirmed pass outcomes."),
        ("badge_relationship", "Behaviours linked to recorded Badges", "Engagement and AT1/AT2 submission indicators versus valid non-revoked Badge evidence."),
    )
    page.tables['analysis_questions'] = [TableRow(key=key, label=label,
        dimensions={"analysis_area": key, "result": description}, metrics={}) for key, label, description in questions]
    for course_id in sorted({data.offerings[o].course_id for o in scope}):
        course = data.courses[course_id].code
        course_scope = {o for o in scope if data.offerings[o].course_id == course_id}
        base = data.privacy_reason(course_scope)
        selected = {p: r for p, r in records.items() if r['course'] == course_id}
        for target in targets:
            features = BADGE_FEATURES if target == "badge" else FEATURES
            history = [r for r in data.model_runs if r.course_id == course_id and r.target == target]
            latest = history[-1] if history else None
            scores = (latest.metrics or {}).get(latest.model_name, {}) if latest else {}
            small_model_class = latest and any(0 < int(value) < 5 for value in (latest.summary or {}).get("class_counts", {}).values())
            limitations = [] if not latest or latest.status != "completed" else list((latest.summary or {}).get("warnings", []))
            if small_model_class and "low_class_support" not in limitations:
                limitations.append("low_class_support")
            if latest and latest.status == "completed" and (latest.summary or {}).get("contributing_offerings", 0) < 2 and "single_offering_training" not in limitations:
                limitations.append("single_offering_training")
            model_people = {row['student'] for row in selected.values()}
            page.tables.setdefault("model_status", []).append(TableRow(key=f"{course}:{target}", label=target,
                dimensions={"course": course, "target": target, "status": latest.status if latest else "never_trained",
                            "selected_model": latest.model_name if latest and latest.status == "completed" else "none",
                            "limitations": ",".join(limitations) if limitations else "none",
                            "run_id": str(latest.id) if latest else "none"}, metrics={
                    "macro_f1": metric(scores.get("macro_f1"), model_people) if scores else metric(None, set()),
                    "balanced_accuracy": metric(scores.get("balanced_accuracy"), model_people) if scores else metric(None, set())}))
            rows = target_rows(selected, target)
            outcomes = ('badge_observed',) if target == 'badge' else ('score', 'passed') if target == 'weighted_final' else (
                'score', 'passed', 'submitted', 'submission_days_from_course_start', 'first_activity_to_submission_days')
            # Protect pass/submission/badge complements before releasing
            # related association statistics or alternative views of those groups.
            for row in rows:
                row['self_group'] = 'unknown' if row['self_assessment_completion_pct'] is None else 'none' if row['self_assessment_completion_pct'] == 0 else 'all' if row['self_assessment_completion_pct'] == 100 else 'partial'
            partitions = []
            if target == 'badge':
                labels = ('valid', 'revoked_only', 'no_matched_award', 'needs_review', 'unknown')
                partitions += [[r for r in rows if r['outcome_group'] == label] for label in labels]
            else:
                partitions += [[r for r in rows if r['passed'] == value] for value in (0, 1, None)]
                if target != 'weighted_final':
                    partitions += [[r for r in rows if r['submitted'] == state] for state in (0, 1, None)]
            gate = privacy(rows, partitions, base)
            if target == 'badge':
                add_groups(page, rows, course, target, 'outcome_group', labels, gate, features)
            else:
                add_groups(page, rows, course, target, 'passed', (0, 1, None), gate)
                if target != 'weighted_final':
                    add_groups(page, rows, course, target, 'submitted', (0, 1, None), gate)
            for outcome in outcomes:
                valid = [r for r in rows if r.get(outcome) is not None]
                linked = [r for r in valid if r['engagement_available']]
                covered = {r['student'] for r in rows}
                valid_people = {r['student'] for r in valid}
                linked_people = {r['student'] for r in linked}
                coverage_gate = privacy(rows, [valid, linked], gate)
                dims = {"course": course, "target": target, "outcome": outcome, "unit": "student_offering_records"}
                page.tables.setdefault('analysis_coverage', []).append(TableRow(key=f'{course}:{target}:{outcome}', label=outcome,
                    dimensions=dims, metrics={
                        'observed_records': metric(len(rows), covered, coverage_gate),
                        'valid_outcomes': metric(len(valid), valid_people, coverage_gate),
                        'unknown_outcomes': metric(len(rows)-len(valid), covered-valid_people, coverage_gate),
                        'linked_engagement_records': metric(len(linked), linked_people, coverage_gate)}))
                for feature in features:
                    sample = [r for r in linked if r.get(feature) is not None]
                    members = {r['student'] for r in sample}
                    count_gate = privacy(rows, [valid, linked, sample], gate)
                    blocked = privacy(rows, [valid, linked, sample])
                    blocked = privacy(sample, [[r for r in sample if r['offering'] == o] for o in course_scope], blocked)
                    if outcome in {'submitted', 'passed', 'badge_observed'}:
                        blocked = privacy(sample, [[r for r in sample if r[outcome] == value] for value in (0, 1)], blocked)
                    stats = association(sample, feature, outcome) if len(members) >= 5 and not blocked else {
                        k: None for k in ('spearman_rho', 'within_offering_rank_r', 'rho_ci_low', 'rho_ci_high')}
                    area = "badge_relationship" if target == "badge" else "self_assessment" if feature == "self_assessment_completion_pct" else \
                        "engagement_grade" if feature in {"views", "participations"} else "page_category" if feature in {
                            "content_view_share", "assessment_view_share"} else "timing_submission"
                    page.tables.setdefault('associations', []).append(TableRow(key=f'{course}:{target}:{outcome}:{feature}',
                        label=feature, dimensions=dims | {'feature': feature, 'analysis_area': area,
                                                          'ci_method': 'student_cluster_percentile_bootstrap_200'},
                        metrics={'records': metric(len(sample), members, count_gate or blocked), 'students': metric(len(members), members, count_gate or blocked),
                                 **{k: metric(v, members, blocked) for k, v in stats.items()}}))
                # Self-assessment is a behavior, never a scored target. Compare
                # available outcome means within its observed completion groups.
                self_groups = [[r for r in valid if r['self_group'] == label] for label in ('none', 'partial', 'all', 'unknown')]
                self_gate = privacy(rows, [valid] + self_groups, gate)
                for label, sample in zip(('none', 'partial', 'all', 'unknown'), self_groups):
                    members = {r['student'] for r in sample}
                    page.tables.setdefault('self_assessment_association', []).append(TableRow(key=f'{course}:{target}:{outcome}:{label}',
                        label=label, dimensions=dims | {'self_completion': label}, metrics={
                            'records': metric(len(sample), members, self_gate),
                            'mean_outcome': metric(mean(r[outcome] for r in sample) if sample else None, members, self_gate)}))
    page.notes += [
        "Each course is analysed separately; compatible confirmed AT1/AT2 references pool offerings. One record is a student-offering experience; repeated students are clustered for uncertainty.",
        "All outputs are aggregate. Student identifiers and row-level student records are never returned; selected-batch correlations remain descriptive rather than causal.",
        "Retrospective association, not causation or a fitted prediction. Within-offering rank association removes mean offering ranks, not all confounding. No significance claims or personal scatter points.",
        "Raw Spearman intervals use 200 student-cluster bootstrap resamples, require >=20 distinct students and >=180 valid replicates. Constant variables and insufficient samples return unknown.",
        "Views/interactive actions span the source export. First-contact dates are not active days; time to submission is elapsed calendar time, not time spent working.",
        "Grade bands: <70, 70<=score<80, >=80; unavailable scores never become low grades. Weighted final is a derived grade, not a separate assessment.",
        "Badge observed=1 means valid matched non-revoked evidence; 0 combines revoked-only/no matched award for descriptive comparison, not proven academic failure. Detailed states remain separate.",
        "Binary outcome means are proportions. Submission timing is measured in days from course start or first recorded activity. Self completion uses only observed, non-excused activities with known submission states.",
        "Survey is anonymous and Salesforce has no student join; neither is a personal feature. Badge models exclude AT1/AT2 scores and derived weighted grades."]

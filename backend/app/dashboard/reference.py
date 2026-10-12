"""Course-level data guide, glossary and calculation rules."""
from app.dashboard.contracts import Metric, TableRow


GLOSSARY = (
    ("course", "Course", "Scope", "One Melbourne MicroCert, such as Understanding Treaty or PBS: Autism Affirming Practice.", "All pages"),
    ("teaching_period", "Teaching period", "Scope", "One scheduled delivery of a course, identified by year, month and PAR number.", "Overview, Engagement, Assignments, Feedback"),
    ("par_label", "PAR number", "Scope", "A source label used to distinguish parallel teaching-period records. The dashboard preserves it as an identifier and does not infer another meaning from it.", "Teaching period selector"),
    ("assignment_cohort", "Assignment cohort", "Cohorts", "Distinct students with at least one Canvas Assignment record in the selected scope.", "Overview, Assignments"),
    ("engagement_cohort", "Engagement cohort", "Cohorts", "Distinct students with at least one Canvas Engagement record in the selected scope.", "Overview, Engagement"),
    ("survey_response_cohort", "Survey response cohort", "Cohorts", "Completed anonymous Qualtrics responses in the selected scope. Responses cannot be linked to students.", "Overview, Feedback"),
    ("model_cohort", "Model cohort", "Cohorts", "Linked student-teaching-period records that contain the outcome and predictors required by a model.", "Summary & Recommendations"),
    ("student_period_record", "Student-teaching-period record", "Cohorts", "One student's linked record within one teaching period. The same student can contribute another record in a different period.", "Summary & Recommendations"),
    ("support_case", "Support case record", "Records", "One Salesforce case row. A case is not a student and one student may create several cases.", "Overview, Engagement"),
    ("import_snapshot", "Import snapshot", "Records", "The latest completed import selected by the backend for a source. Quality counts describe that whole imported file.", "Data & Rules"),
    ("source_available", "Available source", "Records", "The selected course has usable, verified records for this dataset.", "Overview, Data & Rules"),
    ("source_excluded", "Excluded source", "Records", "A file exists but cannot support published analysis because its course scope is not verified.", "Overview, Data & Rules"),
    ("page_view", "Page view", "Engagement", "Canvas times_viewed for a resource. Timeline charts place this summary at its first access date; it is not a daily click log.", "Engagement"),
    ("first_access", "First access date", "Engagement", "The first recorded Canvas view date for a resource within a student record.", "Engagement"),
    ("canvas_area", "Canvas area", "Engagement", "A grouped resource type: Content, Assessment or Other Canvas areas. Other can be expanded into its source types.", "Engagement"),
    ("interactive_action", "Interactive action", "Engagement", "Canvas participated count, retained internally for modeling and not presented as a page-view measure.", "Summary & Recommendations models"),
    ("release_proxy", "Assignment release proxy", "Assignments", "The earliest reliable source created_at timestamp. It is used because verified publication timestamps are unavailable.", "Assignments"),
    ("deadline", "Assignment deadline", "Assignments", "The source due_at timestamp recorded for an assignment.", "Assignments"),
    ("submission", "Recorded submission", "Assignments", "An assignment record with submitted or graded status. Missing attempts remain unknown rather than being changed to attempt 1.", "Assignments"),
    ("result_unavailable", "Result unavailable", "Assignments", "The source does not contain enough confirmed score information for a pass decision. It is not counted as a failure.", "Assignments"),
    ("self_assessment", "Self-assessment activity", "Assignments", "A zero-point, non-scored activity retained for participation analysis.", "Assignments, Summary & Recommendations"),
    ("course_pass", "Course pass", "Outcomes", "A complete valid weighted result of at least 70%, using AT1 at 40% and AT2 at 60%.", "Overview, Assignments, Summary & Recommendations"),
    ("complete_result", "Complete valid result", "Outcomes", "Both scored components have usable results, so the weighted course result and pass status can be calculated.", "Overview, Assignments"),
    ("active_badge", "Active Badge", "Outcomes", "A matched Badge record that is valid and has not been revoked. Badge evidence is reported separately from course pass.", "Assignments, Summary & Recommendations"),
    ("course_default", "Course default rule", "Outcomes", "The assessment rule used for every teaching period in a course unless an active teaching-period override exists.", "Data & Rules"),
    ("response_time", "Response time", "Support", "Salesforce Age (Hours), confirmed as the time taken to respond to a support case.", "Overview, Engagement"),
    ("support_topic", "Support topic", "Support", "A keyword-based grouping of cleaned Salesforce case subjects. One case can match more than one topic.", "Engagement"),
    ("nps", "Net Promoter Score (NPS)", "Feedback", "Recommendation score calculated from 0–10 responses: promoter percentage minus detractor percentage, ranging from −100 to +100.", "Overview, Feedback"),
    ("valid_survey_response", "Valid survey response", "Feedback", "For one question, a completed response with an answer; for a theme, a completed response answering at least half of that theme's items.", "Feedback"),
    ("nps_groups", "Detractor, Passive and Promoter", "Feedback", "NPS response groups for ratings 0–6, 7–8 and 9–10 respectively.", "Overview, Feedback"),
    ("feedback_type", "Feedback type", "Feedback", "A transparent keyword-based classification of cleaned written feedback. It describes the leading request or theme, not sentiment.", "Feedback"),
    ("macro_f1", "Macro F1", "Models", "The average F1 score across outcome classes, giving each class equal weight.", "Summary & Recommendations models"),
    ("balanced_accuracy", "Balanced Accuracy", "Models", "The average recall across outcome classes, reducing the influence of an imbalanced majority class.", "Summary & Recommendations models"),
    ("key_insight", "Key insight", "Interpretation", "A course-team note saved beside a chart to explain the most useful finding. It is interpretation, not source data.", "All analytical pages"),
    ("not_available", "Not available", "Interpretation", "The required source or value is absent or cannot be verified. It does not mean zero.", "All pages"),
)


CALCULATIONS = (
    ("course_pass", "Course pass", "AT1 × 40% + AT2 × 60%; pass when the complete weighted result is at least 70%.", "Students with both valid scored components"),
    ("assignment_completion", "Assignment completion", "Count records with submitted or graded status.", "Assignment records for the selected assessment"),
    ("badge_status", "Badge status", "Keep Active Badge, revoked-only evidence and no matched record as separate states.", "Assignment cohort"),
    ("nps", "Net Promoter Score", "Promoter percentage minus detractor percentage on the −100 to +100 scale.", "Valid 0–10 Qualtrics responses"),
    ("theme_score", "Qualtrics theme score", "Mean of answered 1–5 items after a response answers at least half of the theme.", "Valid responses for that theme"),
    ("engagement_timeline", "Engagement timeline", "Place each resource's summary views on its first access date.", "Canvas Engagement resource records"),
    ("support_response", "Support response time", "Use the source Age (Hours); retain valid extremes and leave invalid or missing values unknown.", "Cases with a valid response time"),
    ("privacy", "Privacy rule", "Publish aggregates and cleaned text only; never return student identifiers or row-level student records.", "All outputs"),
)


def _quality(batch):
    summary = batch.summary or {}
    quality = summary.get("quality") or {}
    warnings = sum(int(value or 0) for value in quality.values() if isinstance(value, (int, float)))
    return {
        "accepted_rows": Metric(value=summary.get("accepted_rows")),
        "input_rows": Metric(value=summary.get("input_rows", batch.row_count)),
        "warning_rows": Metric(value=warnings),
    }


def _source_row(key, label, course, platform, dataset, contains, unit, status, coverage, batch=None):
    return TableRow(key=f"{course.code}:{key}", label=label, dimensions={
        "course": course.name, "platform": platform, "dataset": dataset,
        "contains": contains, "unit": unit, "availability": status,
        "coverage": coverage,
    }, metrics=_quality(batch) if batch else {})


def build_reference(page, data, scope):
    """Populate a course-level manual without exposing source identifiers."""
    course_ids = sorted({data.offerings[item].course_id for item in scope})
    page.snapshots.update({key: batch.finished_at.isoformat() + "Z"
                           for key, batch in data.extra_batches.items() if batch.finished_at})
    for course_id in course_ids:
        course = data.courses[course_id]
        course_scope = {key for key in scope if data.offerings[key].course_id == course_id}
        engagement = any(row.offering_id in course_scope for row in data.engagement)
        assignments = any(data.assignments[row.assignment_id].offering_id in course_scope for row in data.submissions)
        badges = any(data.badge_courses.get(row.badge_class_id) == course_id or row.offering_id in course_scope
                     for row in data.badges)
        survey_batches = [data.extra_batches.get("survey:" + (data.offerings[key].offering_code or ""))
                          for key in course_scope]
        survey_batches = [batch for batch in survey_batches if batch]
        support_batch = data.extra_batches.get("support:" + course.code)
        support_verified = bool(support_batch and (support_batch.summary or {}).get("course_scope_verified") is True)
        calendar_batch = data.extra_batches.get("calendar")
        calendars = sum(key in data.calendars for key in course_scope)
        rows = [
            _source_row("engagement", "Canvas Engagement", course, "Canvas", "Engagement export",
                        "Resource area, first access time, view totals and interactive-action totals", "resource records",
                        "Available" if engagement else "Not available", "All imported teaching periods" if engagement else "No records for this course", data.batches.get("engagement")),
            _source_row("assignments", "Canvas Assignments", course, "Canvas", "Assignment export",
                        "Assignment status, attempts, submission times and results", "student-assignment records",
                        "Available" if assignments else "Not available", "All imported teaching periods" if assignments else "No records for this course", data.batches.get("assignment")),
            _source_row("badge", "Badge records", course, "Badge platform", "Badge export",
                        "Award, revocation and matching evidence", "Badge records",
                        "Available" if badges else "Not available", "Matched to this course" if badges else "No mapped records for this course", data.batches.get("badge")),
            _source_row("survey", "Qualtrics feedback", course, "Qualtrics", "End-of-course survey",
                        "Ratings, NPS and cleaned written feedback", "completed responses",
                        "Available" if survey_batches else "Not available", f"{len(survey_batches)} teaching period(s)", survey_batches[-1] if survey_batches else None),
            _source_row("calendar", "Teaching-period records", course, "Salesforce", "Course schedule and enrolment export",
                        "Course start and end dates plus enrolment record counts", "teaching-period records",
                        "Available" if calendars else "Not available", f"{calendars} teaching period(s)", calendar_batch if calendars else None),
            _source_row("support", "Salesforce support cases", course, "Salesforce", "Support case export",
                        "Case topics, channels, opened times and response time", "case records",
                        "Available" if support_verified else "Excluded: course scope unverified" if support_batch else "Not available",
                        "Selected teaching windows" if support_verified else "Date overlap alone is not accepted as course membership" if support_batch else "No export for this course", support_batch),
        ]
        page.tables.setdefault("data_sources", []).extend(rows)

    page.tables["glossary"] = [TableRow(key=key, label=label,
        dimensions={"category": category, "definition": definition, "used_on": used_on}, metrics={})
        for key, label, category, definition, used_on in GLOSSARY]
    page.tables["calculation_rules"] = [TableRow(key=key, label=label,
        dimensions={"calculation": calculation, "denominator": denominator}, metrics={})
        for key, label, calculation, denominator in CALCULATIONS]

    page.tables["assessment_rules"] = []
    for rule in data.rules:
        if rule.course_id not in course_ids:
            continue
        components = ", ".join(f"{item['key']} {float(item['weight']) * 100:g}%" for item in rule.components)
        offering = data.offerings[rule.offering_id].offering_code if rule.offering_id else "Course default"
        page.tables["assessment_rules"].append(TableRow(key=f"{rule.course_id}:{rule.id}", label=rule.version,
            dimensions={"course": data.courses[rule.course_id].name, "scope": offering,
                        "components": components, "pass_mark": f"{float(rule.pass_threshold):g}%",
                        "status": "Active" if rule.enabled else rule.status.title()}, metrics={}))

    limitations = [
        ("cohort_difference", "Source cohorts differ", "Assignment cohort, Engagement cohort and Survey response cohort are defined by different source records and should not be treated as the same population."),
        ("survey_link", "Survey responses are anonymous", "Qualtrics responses cannot be linked to individual Canvas activity, assignment results or Badge records."),
        ("view_summary", "Canvas views are summaries", "times_viewed is a resource-level total placed at first access for timeline reporting; it is not a daily event log."),
        ("release_proxy", "Publication time is unavailable", "Assignment created_at is labelled Assignment release proxy and must not be read as a verified publication time."),
        ("unknown", "Unknown is not zero", "Missing or unverified values stay Not available and are not converted to zero, failure or non-participation."),
        ("badge_pass", "Course pass and Badge are separate", "A course pass does not guarantee a recorded Badge, and a Badge record does not replace the academic result."),
    ]
    if any((data.extra_batches.get("support:" + data.courses[course_id].code) and
            (data.extra_batches["support:" + data.courses[course_id].code].summary or {}).get("course_scope_verified") is not True)
           for course_id in course_ids):
        limitations.append(("support_scope", "Unverified support data is excluded", "A support export without a verified course field is not published merely because its dates overlap teaching periods."))
    page.tables["data_limitations"] = [TableRow(key=key, label=label,
        dimensions={"explanation": explanation}, metrics={}) for key, label, explanation in limitations]
    page.notes = ["This reference page is course-wide and does not change with the Teaching period selector."]

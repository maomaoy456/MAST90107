"""Summary-page metadata and privacy-safe model availability."""
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric

TARGETS = ("pass", "badge")

RECOMMENDATIONS = (
    ("before_start", "Before the course starts", "Reducing the effort needed to get in and get going.",
     "Provide an onboarding guide before the course opens, and simplify the access steps.",
     "35 of the 60 verified Salesforce support cases for Understanding Treaty are classified as access and technology, and the common case subjects concern Canvas access. Enrolment cases have a median response time of 24 hours.",
     "Engagement → Salesforce support topics", "Supported by current data"),
    ("communication", "Communication during the course", "Answering the same question once, in public, instead of many times in private.",
     "Turn recurring course questions into a published FAQ, starting with assessment questions.",
     "Support demand is concentrated in repeating case subjects. 45 of 60 verified cases arrive by email, with a median response time of 21 hours compared with 0 hours for phone.",
     "Engagement → support channels and case subjects", "Supported by current data"),
    ("communication", "Communication during the course", "Answering the same question once, in public, instead of many times in private.",
     "Add a shared discussion space so an answer is visible to everyone instead of being repeated one learner at a time.",
     "19 of the 60 verified cases took longer than 24 hours to answer and 3 took more than 7 days. Meaningful peer interaction is also one of the weakest Treaty survey statements, at 4.14 out of 5.",
     "Engagement → support response time · Feedback → Q3", "Supported by current data"),
    ("assessment", "Assessment scheduling and reminders", "Keeping the second assessment in view once the first one is done.",
     "Reconsider when the two assessments are made available.",
     "In all 7 Treaty teaching periods, AT1 and AT2 share the same recorded Assignment release proxy. For 2026 FEB PAR 2, both source records were created on 3 February; AT1 was due 33 days later and AT2 54 days later. This proxy is not a verified publication timestamp.",
     "Assignments → assignment schedule", "Supported by current data"),
    ("assessment", "Assessment scheduling and reminders", "Keeping the second assessment in view once the first one is done.",
     "Send assessment requirements and deadline reminders by email while each assessment is open.",
     "Within the Treaty Assignment cohort, 278 records have a graded AT1 and 259 have a graded AT2. Unsubmitted records rise from 59 to 78 between the two assessments.",
     "Assignments → submission status", "Supported by current data"),
    ("data", "Data groundwork", "What has to be in place before the analysis can go further.",
     "Continue running the end-of-course survey for every teaching period, and encourage learners to complete it.",
     "Survey data is mapped to only 2 of the 9 teaching periods. Feedback findings currently rest on 28 Treaty responses and 11 PBS responses.",
     "Feedback", "Data groundwork"),
    ("data", "Data groundwork", "What has to be in place before the analysis can go further.",
     "Collect a wider set of course data to support the analysis.",
     "78 of 337 Treaty assignment records have no complete weighted result, and Salesforce support data is excluded for PBS, so several comparisons cannot be made for both courses.",
     "Assignments → course completion · Engagement → support data status", "Data groundwork"),
    ("data", "Data groundwork", "What has to be in place before the analysis can go further.",
     "Agree one format for future data collection.",
     "The PBS Salesforce support export has no verified course field and can only be associated by date window. Treaty also has 337 assignment records and 306 students in the Engagement cohort. One teaching period records an AT2 deadline 210 days after its release proxy and after the teaching period ended.",
     "Data & Rules", "Data groundwork"),
)


def build_insights(page, data, scope, reason):
    """Expose recommendations and the two reviewed prediction targets."""
    page.cohort = "course_separated_student_offering_records"
    assignment_people, engagement_people = data.populations(scope)
    people = assignment_people | engagement_people
    available = bool({"assignment", "engagement"} & data.batches.keys())
    page.metrics["students"] = metric(len(people) if available else None, people, reason)
    targets = TARGETS if page.filters.target == "all" else (page.filters.target,)
    page.tables["analysis_options"] = [TableRow(
        key=target,
        label="Course pass" if target == "pass" else "Active Badge",
        dimensions={
            "target": target,
            "outcome": "AT1 40% + AT2 60%; pass at 70%" if target == "pass" else "Valid matched non-revoked Badge",
            "predictors": "Canvas behaviour and non-scored self-assessment completion",
            "excluded_predictors": "AT1/AT2 submission, AT1/AT2 score, weighted grade",
        },
        metrics={},
    ) for target in targets]
    page.tables["recommendations"] = [TableRow(key=f"recommendation_{index}", label=title,
        dimensions={"group": group, "group_description": description, "evidence": evidence,
                    "where_to_look": where, "status": status}, metrics={})
        for index, (key, group, description, title, evidence, where, status) in enumerate(RECOMMENDATIONS, 1)]
    for course_id in sorted({data.offerings[offering].course_id for offering in scope}):
        course = data.courses[course_id].code
        for target in targets:
            history = [run for run in data.model_runs if run.course_id == course_id and run.target == target]
            latest = history[-1] if history else None
            page.tables.setdefault("model_status", []).append(TableRow(
                key=f"{course}:{target}", label="Course pass" if target == "pass" else "Active Badge",
                dimensions={
                    "course": course,
                    "target": target,
                    "status": latest.status if latest else "never_trained",
                    "selected_model": latest.model_name if latest and latest.status == "completed" else "none",
                    "run_id": str(latest.id) if latest else "none",
                }, metrics={}))
    page.notes += [
        "Models pool compatible teaching periods within each course and use student-grouped three-fold validation.",
        "Course pass is binary and requires both valid components: AT1 40% + AT2 60%, with a pass mark of 70%.",
        "Badge means valid matched non-revoked evidence after a 60-day observation window; it is not identical to academic pass.",
        "Predictors use Canvas behaviour and non-scored self-assessment completion only. AT1/AT2 submission indicators, assignment scores and weighted grades are excluded.",
        "Logistic regression and random forest are compared using Macro F1 and Balanced Accuracy. Insufficient or imbalanced samples are reported rather than forced into a model.",
    ]

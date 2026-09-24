"""Six page builders returning aggregates without student identifiers."""
from app.dashboard.assignments import build_assignments
from app.dashboard.engagement import build_engagement
from app.dashboard.academic import add_academic
from app.dashboard.insights import build_insights
from app.dashboard.badges import add_badges
from app.dashboard.calendar import add_calendar
from app.dashboard.survey import add_survey
from app.dashboard.support import add_support
from app.dashboard.assignment_time import add_assignment_time, add_assignment_deadlines
from app.dashboard.course_timing import add_engagement_stages

from app.dashboard.contracts import Page, TableRow, Metric
from app.dashboard.privacy import metric


def make_page(name, data, filters):
    scope = data.scope(filters)
    a, e = data.populations(scope)
    reason = data.privacy_reason(scope)
    page = Page(page=name, filters=filters, cohort="source_specific",
        snapshots={source: b.finished_at.isoformat() + "Z" for source, b in data.batches.items() if b.finished_at},
        metrics={}, notes=["Counts use distinct students and latest completed source snapshots.",
                           "Naive engagement times provisionally use Australia/Melbourne."])
    if name == "overview":
        # Catalog counts describe courses, not student groups.
        page.metrics["courses"] = Metric(value=len({data.offerings[o].course_id for o in scope}))
        page.metrics["offerings"] = Metric(value=len(scope))
        for key, students in (("assignment_students", a), ("engagement_students", e)):
            required = {"assignment" if key.startswith("assignment") else "engagement"}
            page.metrics[key] = metric(len(students) if required <= data.batches.keys() else None, students, reason)
        page.tables["offering_comparison"] = []
        for offering in sorted(scope):
            aa, ee = data.populations({offering})
            blocked = data.privacy_reason({offering})
            obj = data.offerings[offering]
            page.tables["offering_comparison"].append(TableRow(key=obj.offering_code or "unlabelled", label=obj.offering_code or "Unlabelled offering",
                metrics={"assignment_students": metric(len(aa) if "assignment" in data.batches else None, aa, blocked),
                         "engagement_students": metric(len(ee) if "engagement" in data.batches else None, ee, blocked)}))
        page.notes += ["Source cohorts differ; missing engagement is not zero engagement."]
    elif name == "engagement":
        build_engagement(page, data, scope, reason)
    elif name == "assignments":
        build_assignments(page, data, scope, reason)
    elif name == "outcomes":
        page.cohort = "completed_qualtrics_responses"
    elif name == "insights":
        build_insights(page, data, scope, reason)
    elif name == "data-rules":
        page.cohort = "metadata_only"
        page.tables["source_quality"] = []
        for source, batch in data.batches.items():
            summary = batch.summary or {}
            members = a if source == "assignment" else e if source == "engagement" else {
                r.student_id for r in data.badges if r.student_id is not None}
            fields = {key: summary.get(key) for key in ("accepted_rows", "rejected_rows", "warning_rows")}
            # These are whole-file diagnostics, never pretend they are filtered row totals.
            page.tables["source_quality"].append(TableRow(key=source, label=source + " (whole snapshot)",
                metrics={k: metric(v, members) for k, v in fields.items()}))
        page.notes += ["Import diagnostics are available via the local ingestion report command; raw errors/rows are not exposed.",
            "Rule history is available from /api/v1/rules; extended source logs are deferred.",
            "First-view date is distinct from intake month; exact offering boundaries remain unconfirmed where absent."]
    required = {"engagement": {"engagement"}, "assignments": {"assignment"}}.get(name, set())
    if required - data.batches.keys():
        page.metrics = {key: metric(None, set()) for key in page.metrics}
        page.tables = {}
        page.notes.append("Required source is unavailable; values are unknown, not zero.")
    if name in {"overview", "engagement", "assignments", "outcomes"}:
        if name == "overview":
            add_calendar(page, data, scope)
        if name in {"overview", "assignments"} and "assignment" in data.batches:
            add_academic(page, data, scope)
        page.snapshots.update({k: b.finished_at.isoformat() + "Z" for k, b in data.extra_batches.items() if b.finished_at})
        if name in {"overview", "outcomes"}:
            add_survey(page, data, scope)
        if name in {"overview", "engagement"}:
            add_support(page, data, scope)
        if name == "engagement" and "engagement" in data.batches:
            add_engagement_stages(page, data, scope, reason)
            add_assignment_deadlines(page, data, scope)
        if name == "assignments" and "assignment" in data.batches:
            add_assignment_time(page, data, scope)
            if "badge" in data.batches:
                add_badges(page, data, scope, reason)
    return page

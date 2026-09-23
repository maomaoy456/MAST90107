"""Course-attributed cases plus redacted representative issue titles."""
from collections import Counter, defaultdict
from statistics import median
from app.dashboard.activity import bucket, local_date
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric
from app.supplemental.schema import topics
from app.dashboard.text import anonymous_text


def selected_cases(data, scope):
    return [r for r in data.support if any(o.course_id == r.course_id and o.starts_on and o.ends_on
        and o.starts_on <= local_date(r.opened_at) <= o.ends_on for o in (data.offerings[i] for i in scope))]


def add_support(page, data, scope):
    courses = {data.offerings[o].course_id for o in scope}
    available, unverified = set(), set()
    for course in courses:
        code = data.courses[course].code
        batch = data.extra_batches.get("support:" + code)
        if batch is None:
            continue
        (available if (batch.summary or {}).get("course_scope_verified") is True else unverified).add(course)
    for course in sorted(unverified):
        code = data.courses[course].code
        page.tables.setdefault("support_data_status", []).append(TableRow(
            key=code, label=code, dimensions={"course": code, "status": "excluded_unverified_scope",
                "reason": "date_window_only_no_course_field"}, metrics={}))
    if not available:
        page.metrics["support_records"] = metric(None, set())
        if unverified:
            page.notes.append("Support results are excluded because the supplied case export has no verified course field or enrolment link; date overlap alone does not establish course membership.")
        return
    selected = selected_cases(data, scope)
    population = {r.id for r in selected}
    page.metrics["support_records"] = metric(len(selected), population) if available == courses else metric(None, set())
    for course in sorted(available):
        code = data.courses[course].code
        rows = [r for r in selected if r.course_id == course]
        members = {r.id for r in rows}
        valid = {r.id for r in rows if r.response_hours is not None}
        values = [float(r.response_hours) for r in rows if r.response_hours is not None]
        page.tables.setdefault("support_summary", []).append(TableRow(key=code, label=code,
            dimensions={"course": code, "scope": "selected_teaching_windows", "unit": "case_records"}, metrics={
                "records": metric(len(members), members),
                "response_n": metric(len(valid), valid),
                "median_response_hours": metric(median(values) if values else None, valid)}))
        tables = {k: defaultdict(list) for k in ("support_channels", "support_status", "support_weekdays", "support_timeline", "support_response_distribution", "support_topics", "support_topics_timeline")}
        for row in rows:
            day = local_date(row.opened_at)
            # Channel labels from a controlled vocabulary, never a raw owner/name.
            channel = row.channel if row.channel in {"Email", "Phone", "Web", "Chat", "Webform", "Internal", "Appointment", "Events"} else "Other"
            status = "closed" if row.is_closed is True and row.is_open is False else "open" if row.is_open is True and row.is_closed is False else "unknown"
            hours = float(row.response_hours) if row.response_hours is not None else None
            band = "unknown" if hours is None else "0_24h" if hours <= 24 else "1_7d" if hours <= 168 else "over_7d"
            for table, key in (("support_channels", channel), ("support_status", status), ("support_weekdays", str(day.weekday())),
                               ("support_timeline", bucket(day, page.filters.interval)), ("support_response_distribution", band)):
                tables[table][key].append(row)
            for topic in topics(row.subject):
                tables["support_topics"][topic].append(row)
                tables["support_topics_timeline"][bucket(day, page.filters.interval) + ":" + topic].append(row)
        for name, bins in tables.items():
            if page.page == "overview" and name != "support_channels":
                continue
            for key, group in sorted(bins.items()):
                people = {r.id for r in group}
                measured = {r.id for r in group if r.response_hours is not None}
                values = [float(r.response_hours) for r in group if r.id in measured]
                page.tables.setdefault(name, []).append(TableRow(key=code + ":" + key, label=key,
                    dimensions={"course": code, "group": key, "unit": "case_records"}, metrics={
                        "records": metric(len(people), people),
                        "median_response_hours": metric(median(values) if values else None, measured)}))
        if page.page == "engagement":
            examples = defaultdict(Counter)
            for row in rows:
                cleaned = anonymous_text(row.subject)
                if cleaned:
                    for topic in topics(row.subject):
                        examples[topic][cleaned] += 1
            for topic, values in sorted(examples.items()):
                ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))[:5]
                for index, (subject, count) in enumerate(ranked, 1):
                    page.tables.setdefault("support_issue_summaries", []).append(TableRow(
                        key=f"{code}:{topic}:{index}", label=subject,
                        dimensions={"course": code, "topic": topic,
                                    "redaction": "direct_identifiers_v1", "selection": "top_5_by_frequency"},
                        metrics={"records": metric(count, set(range(count)))}))
    page.notes += ["Salesforce file-to-course attribution is user-confirmed. Opened timestamps provisionally use Melbourne; only selected inclusive teaching windows are counted, once per source row.",
        "Overlapping windows do not identify a case's offering. Counts are case records, not unique students or verified unique cases; no title/time-based deletion is performed.",
        "Age (Hours) is response time, confirmed by the user. Valid extremes are retained; invalid/missing values remain unknown.",
        "Support topics use keyword_rules_v1, can overlap and are not validated sentiment. Owners and account names are not stored."]
    if unverified:
        page.notes.append("Some selected courses have Support exports that are excluded because their course scope is not verifiable.")
    if page.page == "engagement":
        page.notes.append("Up to five frequent representative issue titles per topic are included after automated direct-identifier redaction; these are source subjects, not generated summaries or complete case descriptions.")

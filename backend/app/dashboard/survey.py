"""Anonymous survey aggregates and redacted completed-response comments."""
from collections import Counter, defaultdict
from math import ceil
from statistics import mean
from app.dashboard.contracts import TableRow
from app.dashboard.privacy import metric, partition
from app.dashboard.activity import group_guard
from app.supplemental.schema import THEMES, QUESTION_GROUPS, TEXT, topics
from app.dashboard.text import anonymous_text


def add_survey(page, data, scope):
    available = [o for o in scope if "survey:" + (data.offerings[o].offering_code or "") in data.extra_batches]
    if not available:
        page.metrics["survey_completed_responses"] = metric(None, set())
        return
    selected = [r for r in data.surveys if r.offering_id in scope and r.finished]
    members = {r.id for r in selected}
    page.metrics["survey_completed_responses"] = metric(len(members), members)
    for offering in sorted(available):
        code = data.offerings[offering].offering_code
        rows = [r for r in selected if r.offering_id == offering]
        population = {r.id for r in rows}
        for theme, questions in THEMES.items():
            group_code, group_label = QUESTION_GROUPS[theme]
            values = {}
            for row in rows:
                answers = [row.answers[q] for q in questions if row.answers.get(q) is not None]
                if len(answers) >= ceil(len(questions) / 2):
                    values[row.id] = mean(answers)
            gate = group_guard([set(values)], population)
            page.tables.setdefault("survey_themes", []).append(TableRow(key=code + ":" + theme, label=theme,
                dimensions={"offering": code, "theme": theme, "unit": "completed_responses"}, metrics={
                    "valid_responses": metric(len(values), set(values), gate),
                    "mean_agreement": metric(mean(values.values()) if values else None, set(values), gate)}))
            for q, label in questions.items():
                if page.page == "overview" and q != "Q1_5":
                    continue
                valid = {r.id for r in rows if r.answers.get(q) is not None}
                bins = {str(i): {r.id for r in rows if r.answers.get(q) == i} for i in range(1, 6)}
                gate = group_guard([valid], population)
                page.tables.setdefault("survey_questions", []).append(TableRow(key=code + ":" + q, label=label,
                    dimensions={"offering": code, "question": q, "theme": theme,
                                "question_group": group_code, "question_group_label": group_label}, metrics={
                        "valid_responses": metric(len(valid), valid, gate),
                        "mean_agreement": metric(mean([r.answers[q] for r in rows if r.id in valid]) if valid else None, valid, gate)}))
                if page.page == "overview":
                    continue
                for row in partition([(k, k, v) for k, v in bins.items()], reason=gate):
                    row.dimensions = {"offering": code, "question": q, "agreement": row.key}
                    row.key = code + ":" + q + ":" + row.key
                    row.metrics = {"responses": row.metrics["students"]}
                    page.tables.setdefault("survey_distribution", []).append(row)
        nps = [r for r in rows if r.nps is not None]
        valid = {r.id for r in nps}
        bins = {"detractor": {r.id for r in nps if r.nps <= 6},
                "passive": {r.id for r in nps if 7 <= r.nps <= 8}, "promoter": {r.id for r in nps if r.nps >= 9}}
        gate = group_guard([valid] + list(bins.values()), population)
        page.tables.setdefault("survey_nps", []).append(TableRow(key=code, label="MicroCert recommendation",
            dimensions={"offering": code}, metrics={
                "valid_responses": metric(len(valid), valid, gate),
                "nps": metric(100 * (len(bins["promoter"]) - len(bins["detractor"])) / len(valid) if valid else None, valid, gate),
                **{k + "_pct": metric(100 * len(v) / len(valid) if valid else None, valid, gate) for k, v in bins.items()}}))
        if page.page == "overview":
            continue
        # Three recommendation branches belong to one question; count each response
        # at most once per topic, even when the same keyword repeats.
        for category in sorted(set(TEXT.values())):
            groups = defaultdict(set)
            answered = set()
            comments = Counter()
            for row in rows:
                value = " ".join(row.feedback.get(q) or "" for q, name in TEXT.items() if name == category).strip()
                if value:
                    answered.add(row.id)
                    for topic in topics(value):
                        groups[topic].add(row.id)
                    cleaned = anonymous_text(value)
                    if cleaned:
                        comments[cleaned] += 1
            gate = group_guard([answered] + list(groups.values()), population)
            page.tables.setdefault("survey_feedback_response_counts", []).append(TableRow(
                key=f"{code}:{category}", label=category,
                dimensions={"offering": code, "question_group": category,
                            "unit": "completed_responses_with_text"},
                metrics={"responses": metric(len(answered), answered, gate)}))
            ranked = sorted(
                ((topic, people) for topic, people in groups.items()
                 if topic not in {"other_unclassified", "no_text"}),
                key=lambda item: (-len(item[1]), item[0]),
            )[:5]
            for rank, (topic, people) in enumerate(ranked, 1):
                item = TableRow(key=f"{code}:{category}:{topic}", label=topic,
                    dimensions={"offering": code, "question_group": category, "classification": "keyword_rules_v1"},
                    metrics={"responses": metric(len(people), people, gate)})
                page.tables.setdefault("survey_feedback_topics", []).append(item)
                if rank == 1:
                    page.tables.setdefault("survey_feedback_topic_highlights", []).append(item.model_copy(deep=True))
            if page.page == "outcomes":
                for index, (comment, count) in enumerate(sorted(comments.items()), 1):
                    page.tables.setdefault("survey_feedback_comments", []).append(TableRow(
                        key=f"{code}:{category}:{index}", label=comment,
                        dimensions={"offering": code, "question_group": category,
                                    "redaction": "direct_identifiers_v1"},
                        metrics={"responses": metric(count, population)}))
    page.notes += ["Survey scope is the explicitly mapped offering. Completed responses only; anonymous responses cannot be linked to Canvas students.",
        "Theme scores first average each response with at least half the theme's items answered (rounded up), then average responses equally. Item denominators may differ.",
        "Recommendation concerns Melbourne MicroCerts, grouped by offering; NPS uses valid 0-10 integer responses.",
        "Feedback themes are auditable keyword classifications, not validated sentiment; multiple themes may apply."]
    if page.page == "outcomes":
        page.notes.append("Anonymous feedback comments are included after automated removal of emails, links, phone-like numbers, student IDs, handles, markup and explicitly labelled names; no response identity is returned.")

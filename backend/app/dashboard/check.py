"""Read-only HTTP contract smoke tests against the configured application database."""
import json
import logging

from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from sqlalchemy import select, func
from app.db import build_engine, session_factory
from app.models import ImportBatch, AssignmentSubmission, Assignment, EngagementEvent, CourseOffering


def main():
    settings = Settings()
    if settings.dashboard_api_key is None:
        print("DASHBOARD_API_KEY is not configured.")
        return 1
    headers = {"X-API-Key": settings.dashboard_api_key.get_secret_value()}
    checks = []
    # Independent SQL count reference, not the page builder implementation.
    engine = build_engine(settings)
    reference = {}
    with session_factory(engine)() as session:
        batches = {b.source: b.id for b in session.scalars(select(ImportBatch).where(
            ImportBatch.status == "completed", ImportBatch.scope == "global").order_by(ImportBatch.finished_at, ImportBatch.id))}
        scopes = [(None, None)] + [(o.offering_code, o.id) for o in session.scalars(select(CourseOffering)) if o.offering_code]
        for code, scope in scopes:
            counts = {}
            for source, model in (("assignment", AssignmentSubmission), ("engagement", EngagementEvent)):
                query = select(func.count(func.distinct(model.student_id))).where(model.batch_id == batches.get(source, -1))
                if scope is not None:
                    query = query.join(Assignment).where(Assignment.offering_id == scope) if source == "assignment" else query.where(EngagementEvent.offering_id == scope)
                counts[source + "_students"] = session.scalar(query)
            reference[code] = counts
    engine.dispose()
    with TestClient(create_app(settings)) as client:
        logging.disable(logging.INFO)
        def check(url, expected=200, params=None, authorized=True):
            response = client.get(url, params=params, headers=headers if authorized else {})
            assert response.status_code == expected, "Unexpected HTTP status"
            payload = response.json()
            encoded = json.dumps(payload)
            assert all(key not in encoded for key in ("student_id", "identity_digest", "response_digest", "source_fields", "Account Name", "Case Owner"))
            assert settings.dashboard_api_key.get_secret_value() not in encoded
            def metrics(value):
                if isinstance(value, dict):
                    if "suppressed" in value and "value" in value:
                        yield value
                    for child in value.values():
                        yield from metrics(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from metrics(child)
            assert all(not item["suppressed"] for item in metrics(payload))
            if url == "/api/v1/overview" and expected == 200 and not any(k in (params or {}) for k in ("course", "offerings")):
                for key, expected_count in reference[(params or {}).get("offering")].items():
                    reported = payload["metrics"][key]
                    assert reported["value"] is None or reported["value"] == expected_count
            checks.append({"path": url, "status": response.status_code})
            return payload
        catalog = check("/api/v1/catalog")
        initial_rules = check("/api/v1/rules")
        model_history = check("/api/v1/models")
        assert all(run["course"] in {c["code"] for c in catalog["courses"]} and
                   run["target"] in {"AT1", "AT2", "weighted_final", "badge"} for run in model_history["runs"])
        for course in catalog["courses"]:
            for page in catalog["pages"]:
                check("/api/v1/" + page, params={"course": course["code"]})
            for target in ("AT1", "AT2", "weighted_final", "badge"):
                result = check("/api/v1/insights", params={"course": course["code"], "target": target})
                assert all(row["dimensions"]["course"] == course["code"] and row["dimensions"]["target"] == target
                           for row in result["tables"]["associations"])
                assert all(row["dimensions"]["model_status"] == "see_model_status" for row in result["tables"]["analysis_options"])
                check("/api/v1/models", params={"course": course["code"], "target": target})
        for offering in catalog["offerings"]:
            params = {"course": offering["course"], "offering": offering["code"]}
            options = check("/api/v1/assignment-options", params=params)
            if options:
                selected = check("/api/v1/assignments", params=params | {"assignments": options[0]["ref"]})
                assert all(row["dimensions"]["assignment_ref"] == options[0]["ref"] for row in selected["tables"]["assessments"])
            for interval in ("week", "month"):
                check("/api/v1/engagement", params=params | {"interval": interval})
        if len(catalog["offerings"]) > 1:
            codes = ",".join(o["code"] for o in catalog["offerings"][:2])
            for page in catalog["pages"]:
                check("/api/v1/" + page, params={"offerings": codes})
        for page in catalog["pages"]:
            check("/api/v1/" + page)
            for offering in catalog["offerings"]:
                result = check("/api/v1/" + page, params={"offering": offering["code"]})
                assert result["page"] == page
                if page == "overview":
                    assert offering["code"] in result["coverage"]
                    calendar = result["tables"]["course_calendar"][0]["dimensions"]
                    assert calendar["starts_on"] == (offering["starts_on"] or "unknown")
                    assert calendar["ends_on"] == (offering["ends_on"] or "unknown")
                    if result["coverage"][offering["code"]]["survey"]:
                        assert len(result["tables"]["survey_themes"]) == 4
                        assert result["tables"]["survey_questions"][0]["dimensions"]["question"] == "Q1_5"
                if page == "engagement" and result["metrics"]["support_records"]["value"] is not None:
                    assert "support_summary" in result["tables"]
                if page == "assignments":
                    for mode in ("scored", "self_assessment"):
                        check("/api/v1/assignments", params={"offering": offering["code"], "mode": mode})
        assert check("/api/v1/rules") == initial_rules
        check("/api/v1/overview", 401, authorized=False)
        check("/api/v1/overview", 404, params={"course": "DOES_NOT_EXIST"})
        check("/api/v1/assignments", 422, params={"mode": "invalid"})
        check("/api/v1/overview", 422, params={"unexpected_filter": "rejected"})
        check("/api/v1/assignments", 404, params={"assignments": "DOES_NOT_EXIST"})
        check("/api/v1/engagement", 422, params={"interval": "hour"})
        check("/api/v1/outcomes", 422, params={"offering": "X", "offerings": "Y"})
        check("/api/v1/insights", 422, params={"target": "final_exam"})
        check("/api/v1/overview", 422, params={"target": "AT1"})
        check("/api/v1/models", 422, params={"unexpected": "rejected"})
    output = {"passed": True, "http_checks": len(checks), "pages": catalog["pages"],
              "offerings_checked": len(catalog["offerings"]), "mutated_rules": False}
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("API acceptance failed. Details were withheld to protect credentials and data.")
        raise SystemExit(1) from None

"""Authenticated aggregate APIs. Query options are intentionally bounded."""
import hashlib
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.dashboard.contracts import (Filters, Page, RuleUpdate, Catalog, RuleList, RuleSaved,
    AssignmentOption, ModelTrainRequest, ModelRunView, ModelRunList)
from app.dashboard.assignments import assignment_options
from app.dashboard.data import Snapshot
from app.dashboard.pages import make_page
from app.dashboard.calendar import phase, today
from app.dashboard.privacy import metric
from app.models import AssessmentRule, Assignment, CourseOffering
from app.modeling.features import data_signature
from app.modeling.training import MODEL_CONFIG, artifact_valid, train

key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def authenticated(request: Request, key: str | None = Security(key_header)):
    expected = request.app.state.settings.dashboard_api_key
    if expected is None:
        raise HTTPException(503)
    if key is None or len(key) > 512 or not secrets.compare_digest(key.encode(), expected.get_secret_value().encode()):
        raise HTTPException(401)


router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticated)])


def filters(request: Request):
    if len(request.query_params.multi_items()) != len(request.query_params):
        raise HTTPException(422)
    try:
        return Filters.model_validate(dict(request.query_params))
    except ValidationError:
        raise HTTPException(422) from None


@router.get("/catalog", response_model=Catalog)
def catalog(request: Request, session=Depends(get_session)):
    if request.query_params:
        raise HTTPException(422)
    data = Snapshot(session)
    return {"courses": [{"code": c.code, "name": c.name} for c in data.courses.values()],
        "offerings": [{"code": o.offering_code, "course": data.courses[o.course_id].code,
                       "intake_year": o.intake_year, "intake_month": o.intake_month,
                       "cohort_label": o.cohort_label, "status": o.status,
                       "starts_on": str(o.starts_on) if o.starts_on else None,
                       "ends_on": str(o.ends_on) if o.ends_on else None,
                       "calendar_phase": phase(o, today())} for o in data.offerings.values() if o.offering_code],
        "pages": ["overview", "engagement", "assignments", "outcomes", "insights", "data-rules"],
        "assignment_modes": ["combined", "scored", "self_assessment"],
        "sources": {source: source in data.batches or any(b.source == source for b in data.extra_batches.values())
                    for source in ("engagement", "assignment", "badge", "survey", "salesforce")}}


@router.get("/assignment-options", response_model=list[AssignmentOption], openapi_extra={"parameters": [
    {"name": name, "in": "query", "required": False, "schema": {"type": "string"}}
    for name in ("course", "offering", "offerings", "mode")]})
def options(query: Filters = Depends(filters), session=Depends(get_session)):
    if query.assignments or query.interval != "day" or query.target != "all":
        raise HTTPException(422)
    return assignment_options(Snapshot(session), query)


def page_endpoint(name):
    def endpoint(query: Filters = Depends(filters), session=Depends(get_session)):
        if name != "insights" and query.target != "all":
            raise HTTPException(422)
        if name != "assignments" and query.mode != "combined":
            raise HTTPException(422)
        if name != "assignments" and query.assignments:
            raise HTTPException(422)
        if name not in {"engagement", "outcomes"} and query.interval != "day":
            raise HTTPException(422)
        data = Snapshot(session)
        return make_page(name, data, query)
    endpoint.__name__ = name.replace("-", "_")
    return endpoint


for name in ("overview", "engagement", "assignments", "outcomes", "insights", "data-rules"):
    parameters = [{"name": key, "in": "query", "required": False,
                   "schema": {"type": "string", "pattern": "^[A-Z0-9_]{1,120}$"}}
                  for key in ("course", "offering")]
    parameters.append({"name": "offerings", "in": "query", "schema": {"type": "string"},
                       "description": "Comma-separated offering codes, at most 20; cannot combine with offering."})
    if name in {"engagement", "outcomes"}:
        parameters.append({"name": "interval", "in": "query", "schema": {"type": "string", "enum": ["day", "week", "month"], "default": "day"}})
    if name == "assignments":
        parameters.append({"name": "assignments", "in": "query", "schema": {"type": "string"},
                           "description": "Comma-separated assignment references from assignment-options, at most 20."})
        parameters.append({"name": "mode", "in": "query", "required": False,
            "schema": {"type": "string", "enum": ["combined", "scored", "self_assessment"], "default": "combined"}})
    if name == "insights":
        parameters.append({"name": "target", "in": "query", "schema": {"type": "string",
            "enum": ["all", "AT1", "AT2", "weighted_final", "badge"], "default": "all"}})
    router.add_api_route("/" + name, page_endpoint(name), methods=["GET"], response_model=Page,
                        openapi_extra={"parameters": parameters})


@router.get("/rules", response_model=RuleList)
def rules(query: Filters = Depends(filters), session=Depends(get_session)):
    if query.mode != "combined" or query.assignments or query.interval != "day" or query.target != "all":
        raise HTTPException(422)
    data = Snapshot(session)
    scope = data.scope(query)
    courses = {c.id for c in data.courses.values() if not query.course or c.code == query.course}
    if query.offering or query.offerings:
        courses &= {data.offerings[o].course_id for o in scope}
    return {"rules": [{"course": data.courses[r.course_id].code,
        "offering": data.offerings[r.offering_id].offering_code if r.offering_id else None,
        "version": r.version, "status": r.status, "enabled": r.enabled,
        "pass_threshold": float(r.pass_threshold), "components": r.components}
        for r in data.rules if r.course_id in courses and (r.offering_id is None or r.offering_id in scope)]}


def public_run(run, course, data, settings, already_current=False):
    summary, results = run.summary or {}, run.metrics or {}
    current = data_signature(data, course.id, run.target, settings.badge_data_as_of, MODEL_CONFIG)
    def protected(value):
        members = set(range(int(value or 0)))
        return metric(int(value), members) if value is not None else metric(None, set())
    small_class = any(0 < int(value) < 5 for value in summary.get("class_counts", {}).values())
    warnings = list(summary.get("warnings", []))
    if run.status == "completed" and small_class and "low_class_support" not in warnings:
        warnings.append("low_class_support")
    if run.status == "completed" and summary.get("contributing_offerings", 0) < 2 and "single_offering_training" not in warnings:
        warnings.append("single_offering_training")
    return {"id": run.id, "course": course.code, "target": run.target, "status": run.status,
        "selected_model": run.model_name if run.status == "completed" else None,
        "model_version": run.model_version, "created_at": run.created_at.isoformat() + "Z",
        "finished_at": run.finished_at.isoformat() + "Z" if run.finished_at else None,
        "reason": summary.get("reason"), "warnings": warnings,
        "data_current": run.data_sha256 == current,
        "artifact_available": run.status == "completed" and artifact_valid(run, settings),
        "already_current": already_current, "included_records": protected(summary.get("included_records")),
        "distinct_students": protected(summary.get("distinct_students")),
        "class_counts": {key: protected(value) for key, value in summary.get("class_counts", {}).items()},
        "candidates": {name: {"macro_f1": values.get("macro_f1"),
                              "balanced_accuracy": values.get("balanced_accuracy")}
                       for name, values in results.items()}}


@router.get("/models", response_model=ModelRunList)
def models(request: Request, session=Depends(get_session)):
    if len(request.query_params.multi_items()) != len(request.query_params) or set(request.query_params) - {"course", "target"}:
        raise HTTPException(422)
    course_code, target = request.query_params.get("course"), request.query_params.get("target")
    if target and target not in {"AT1", "AT2", "weighted_final", "badge"}:
        raise HTTPException(422)
    data = Snapshot(session)
    courses = {c.id: c for c in data.courses.values() if not course_code or c.code == course_code}
    if course_code and not courses:
        raise HTTPException(404)
    rows = [r for r in data.model_runs if r.course_id in courses and (not target or r.target == target)]
    return {"runs": [public_run(r, courses[r.course_id], data, request.app.state.settings) for r in reversed(rows[-100:])]}


@router.post("/models/train", response_model=ModelRunView)
def train_model(body: ModelTrainRequest, request: Request, session=Depends(get_session)):
    if request.query_params:
        raise HTTPException(422)
    dialect, locked = session.bind.dialect.name, False
    try:
        if dialect == "mysql":
            locked = session.scalar(text("SELECT GET_LOCK('mpe_model_training', 0)")) == 1
            if not locked:
                raise HTTPException(409)
        try:
            run, current = train(session, request.app.state.settings, body.course, body.target)
        except ValueError:
            raise HTTPException(404) from None
        data = Snapshot(session)
        course = next(c for c in data.courses.values() if c.code == body.course)
        return public_run(run, course, data, request.app.state.settings, current)
    finally:
        if dialect == "mysql" and locked:
            session.execute(text("SELECT RELEASE_LOCK('mpe_model_training')"))
            session.commit()


@router.put("/rules/{offering_code}", response_model=RuleSaved)
def update_rule(offering_code: str, body: RuleUpdate, request: Request, session=Depends(get_session)):
    if request.query_params:
        raise HTTPException(422)
    # Lock the scope to serialize edits, including the first override of a course default.
    offering = session.scalar(select(CourseOffering).where(CourseOffering.offering_code == offering_code).with_for_update())
    if offering is None:
        raise HTTPException(404)
    existing = list(session.scalars(select(AssessmentRule).where(AssessmentRule.course_id == offering.course_id)))
    active = next((r for r in existing if r.offering_id == offering.id and r.enabled), None)
    effective = active or next((r for r in existing if r.offering_id is None and r.enabled), None)
    if body.expected_version != (effective.version if effective else None):
        raise HTTPException(409)
    if any(r.offering_id == offering.id and r.version == body.version for r in existing):
        raise HTTPException(409)
    assignments = {a.source_key: a for a in session.scalars(select(Assignment).where(Assignment.offering_id == offering.id))}
    if {c.key for c in body.components} != {"AT1", "AT2"}:
        raise HTTPException(422)
    for component in body.components:
        a = assignments.get(component.assignment_ref)
        if a is None or a.max_score is None or a.max_score <= 0:
            raise HTTPException(422)
    values = body.model_dump()
    if active:
        active.enabled = False
        session.flush()
    session.add(AssessmentRule(course_id=offering.course_id, offering_id=offering.id,
        version=body.version, status="confirmed", enabled=True, pass_threshold=body.pass_threshold,
        components=[c.model_dump() for c in body.components], evidence="Authenticated explicit offering-rule confirmation",
        config_sha256=hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409) from None
    return {"offering": offering.offering_code, "version": body.version, "status": "confirmed", "enabled": True}

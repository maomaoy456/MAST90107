"""Shared chart commentary, separated by course, teaching period and chart."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.models import Course, CourseOffering, InsightNote
from app.dashboard.contracts import InsightNoteInput, InsightNoteView

router = APIRouter()


def resolve_scope(session, params):
    course = session.scalar(select(Course).where(Course.code == params.course))
    if course is None:
        raise HTTPException(404)
    offering = None
    if params.offering:
        offering = session.scalar(select(CourseOffering).where(
            CourseOffering.course_id == course.id, CourseOffering.offering_code == params.offering))
        if offering is None:
            raise HTTPException(404)
    return course, offering


def view(note, course, scope, chart_key):
    return InsightNoteView(course=course.code, offering=scope, chart_key=chart_key,
        note=note.note if note else "",
        updated_at=note.updated_at.isoformat() if note and note.updated_at else None)


@router.get("/insight-notes", response_model=InsightNoteView | dict[str, list[InsightNoteView]])
def get_notes(request: Request, session=Depends(get_session)):
    query = dict(request.query_params)
    if (len(request.query_params.multi_items()) != len(query)
            or set(query) - {"course", "offering", "chart_key"}):
        raise HTTPException(422)
    try:
        params = InsightNoteInput.model_validate({"chart_key": "all", **query, "note": ""})
    except ValidationError:
        raise HTTPException(422) from None
    course, _ = resolve_scope(session, params)
    selection = select(InsightNote).where(InsightNote.course_id == course.id,
                                         InsightNote.scope_key == params.offering)
    if "chart_key" in query:
        saved = session.scalar(selection.where(InsightNote.chart_key == params.chart_key))
        return view(saved, course, params.offering, params.chart_key)
    return {"notes": [view(note, course, params.offering, note.chart_key)
                      for note in session.scalars(selection.order_by(InsightNote.chart_key))]}


@router.put("/insight-notes", response_model=InsightNoteView)
def save_note(body: InsightNoteInput, session=Depends(get_session)):
    course, offering = resolve_scope(session, body)
    saved = session.scalar(select(InsightNote).where(InsightNote.course_id == course.id,
        InsightNote.scope_key == body.offering, InsightNote.chart_key == body.chart_key).with_for_update())
    if saved is None:
        saved = InsightNote(course_id=course.id, offering_id=offering.id if offering else None,
                            scope_key=body.offering, chart_key=body.chart_key, note=body.note)
        session.add(saved)
    else:
        saved.note = body.note
        saved.updated_at = datetime.now(timezone.utc)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409) from None
    session.refresh(saved)
    return view(saved, course, body.offering, body.chart_key)

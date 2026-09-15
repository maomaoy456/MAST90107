"""Versioned, immutable rule seed. Never infer confirmation from assignment names."""
import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.config import Settings
from app.db import build_engine, session_factory
from app.logging import configure_logging, safe_log
from app.models import AssessmentRule, Assignment, Course, CourseOffering

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "assessment_rules.v2.json"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Component(StrictModel):
    key: str = Field(pattern=r"^AT[1-9][0-9]*$")
    weight: Decimal = Field(gt=0, le=1)


class Rule(StrictModel):
    status: Literal["confirmed", "candidate"]
    enabled: bool
    pass_threshold: Decimal = Field(ge=0, le=100)
    components: list[Component]
    evidence: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def consistent(self):
        if self.enabled and self.status != "confirmed":
            raise ValueError("Only confirmed rules may be enabled")
        if self.status == "confirmed" and not self.components:
            raise ValueError("Confirmed weighted rules require components")
        if self.components:
            if sum(c.weight for c in self.components) != Decimal("1"):
                raise ValueError("Weights must sum to one")
            if len({c.key for c in self.components}) != len(self.components):
                raise ValueError("Duplicate assessment keys")
        return self


class CourseConfig(StrictModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    rule: Rule
    assignment_aliases: dict[str, Literal["AT1", "AT2"]] = Field(default_factory=dict)


class SeedConfig(StrictModel):
    version: str = Field(min_length=1, max_length=40)
    courses: list[CourseConfig]

    @model_validator(mode="after")
    def unique_courses(self):
        if len({c.code for c in self.courses}) != len(self.courses):
            raise ValueError("Duplicate course codes")
        return self


def load_config(path: Path = CONFIG_PATH) -> tuple[SeedConfig, str]:
    raw = path.read_bytes()
    return SeedConfig.model_validate_json(raw), hashlib.sha256(raw).hexdigest()


def seed_rules(session, path: Path = CONFIG_PATH) -> None:
    config, digest = load_config(path)
    for item in config.courses:
        course = session.scalar(select(Course).where(Course.code == item.code))
        if course is None:
            course = Course(code=item.code, name=item.name)
            session.add(course)
            session.flush()
        elif course.name != item.name:
            raise ValueError("Course seed conflicts with existing course")
        values = item.rule.model_dump(mode="json")
        # Explicit, course-specific aliases were reviewed by the user. Unknown
        # titles and zero-point self-assessments never acquire a scoring key.
        for assignment in session.scalars(select(Assignment).join(CourseOffering).where(CourseOffering.course_id == course.id)):
            key = item.assignment_aliases.get(assignment.name)
            if key and assignment.max_score and assignment.max_score > 0 and assignment.mapping_status != "confirmed":
                assignment.assessment_key, assignment.mapping_status = key, "confirmed"
        # Decimal threshold has a numeric database column, components retain exact decimal strings.
        values["pass_threshold"] = item.rule.pass_threshold
        existing = session.scalar(select(AssessmentRule).where(
            AssessmentRule.course_id == course.id, AssessmentRule.version == config.version,
            AssessmentRule.offering_id.is_(None)
        ))
        if existing:
            if existing.config_sha256 != digest or any(getattr(existing, key) != value for key, value in values.items()):
                raise ValueError("Immutable seed conflict; create a reviewed new version")
            continue
        if item.rule.enabled:
            for previous in session.scalars(select(AssessmentRule).where(AssessmentRule.course_id == course.id,
                    AssessmentRule.offering_id.is_(None), AssessmentRule.enabled.is_(True))):
                previous.enabled = False
            session.flush()
        session.add(AssessmentRule(course_id=course.id, version=config.version, config_sha256=digest, **values))
    session.flush()


def main() -> int:
    configure_logging()
    engine = None
    try:
        engine = build_engine(Settings())
        with session_factory(engine).begin() as session:
            seed_rules(session)
        safe_log("seed_complete")
        return 0
    except Exception:
        # Do not print DB exceptions, credentials or input data.
        print("Seed failed. Check database readiness, migrations and immutable config version.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Filters(StrictModel):
    target: Literal["all", "AT1", "AT2", "weighted_final", "badge"] = "all"
    course: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,120}$")
    offering: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,120}$")
    mode: Literal["combined", "scored", "self_assessment"] = "combined"
    offerings: str | None = Field(default=None, max_length=2400, pattern=r"^[A-Z0-9_]+(?:,[A-Z0-9_]+)*$")
    assignments: str | None = Field(default=None, max_length=2400, pattern=r"^[A-Za-z0-9_-]+(?:,[A-Za-z0-9_-]+)*$")
    interval: Literal["day", "week", "month"] = "day"

    @model_validator(mode="after")
    def selections(self):
        if self.offering and self.offerings:
            raise ValueError("Use one offering selector")
        for value in (self.offerings, self.assignments):
            if value and (len(value.split(",")) > 20 or len(set(value.split(","))) != len(value.split(","))):
                raise ValueError("Invalid selection")
        return self


class Metric(StrictModel):
    value: float | int | None = None
    suppressed: bool = False
    reason: Literal["not_available"] | None = None


class TableRow(StrictModel):
    key: str
    label: str
    metrics: dict[str, Metric]
    dimensions: dict[str, str] = Field(default_factory=dict)


class Page(StrictModel):
    page: str
    filters: Filters
    cohort: str
    snapshots: dict[str, str]
    metrics: dict[str, Metric]
    tables: dict[str, list[TableRow]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    coverage: dict[str, dict[str, bool]] = Field(default_factory=dict)


class Component(StrictModel):
    assignment_ref: str = Field(pattern=r"^[A-Za-z0-9_-]{1,120}$")
    key: str = Field(pattern=r"^AT[1-9][0-9]*$")
    weight: float = Field(gt=0, le=1)


class RuleUpdate(StrictModel):
    version: str = Field(pattern=r"^v[0-9]{1,6}$")
    expected_version: str | None = Field(default=None, max_length=40)
    pass_threshold: float = Field(ge=0, le=100)
    components: list[Component] = Field(min_length=1, max_length=20)
    confirmed: Literal[True]

    @model_validator(mode="after")
    def consistent(self):
        from decimal import Decimal
        if sum(Decimal(str(c.weight)) for c in self.components) != Decimal(1):
            raise ValueError("Weights must sum to one")
        if len({c.key for c in self.components}) != len(self.components) or len({c.assignment_ref for c in self.components}) != len(self.components):
            raise ValueError("Duplicate components")
        return self


class CourseOption(StrictModel):
    code: str
    name: str


class OfferingOption(StrictModel):
    code: str
    course: str
    intake_year: int | None
    intake_month: int | None
    cohort_label: str | None
    status: str
    starts_on: str | None = None
    ends_on: str | None = None
    calendar_phase: str = "unknown"


class Catalog(StrictModel):
    courses: list[CourseOption]
    offerings: list[OfferingOption]
    pages: list[str]
    assignment_modes: list[str]
    sources: dict[str, bool]


class AssignmentOption(StrictModel):
    assessment_key: str | None = None
    ref: str
    name: str
    offering: str | None
    kind: Literal["scored", "self_assessment", "unknown"]


class RuleComponent(StrictModel):
    key: str
    assignment_ref: str | None = None
    weight: float


class RuleRecord(StrictModel):
    course: str
    offering: str | None
    version: str
    status: str
    enabled: bool
    pass_threshold: float
    components: list[RuleComponent]


class RuleList(StrictModel):
    rules: list[RuleRecord]


class RuleSaved(StrictModel):
    offering: str
    version: str
    status: Literal["confirmed"]
    enabled: Literal[True]


class ModelTrainRequest(StrictModel):
    course: str = Field(pattern=r"^[A-Z0-9_]{1,32}$")
    target: Literal["AT1", "AT2", "weighted_final", "badge"]


class ModelCandidate(StrictModel):
    macro_f1: float | None = None
    balanced_accuracy: float | None = None


class ModelRunView(StrictModel):
    id: int
    course: str
    target: str
    status: str
    selected_model: str | None = None
    model_version: str
    created_at: str
    finished_at: str | None = None
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    data_current: bool
    artifact_available: bool
    already_current: bool = False
    included_records: Metric
    distinct_students: Metric
    class_counts: dict[str, Metric]
    candidates: dict[str, ModelCandidate]


class ModelRunList(StrictModel):
    runs: list[ModelRunView]

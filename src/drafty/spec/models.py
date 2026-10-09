"""Pydantic models for the DesignSpec and its sections.

The spec is the single JSON document shared by the engine, the checker, the CAD writer, the agent
and the API. Units live in field names. Only code writes ``results``; the model fills and edits the
input and design sections.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Shape = Literal["rectangular", "trapezoidal", "v"]
Side = Literal["left", "right"]
Lining = Literal["concrete", "masonry", "grass", "earth"]
OutletType = Literal["existing_channel", "culvert", "drain", "soakaway"]
Camber = Literal["crown", "crossfall"]
Surface = Literal["gravel", "tarmac", "earth", "concrete"]
RainfallSource = Literal["user", "brief", "placeholder"]
CheckStatus = Literal["pass", "fail", "warn"]


class Meta(BaseModel):
    """Spec metadata written by code, never by the model."""

    spec_version: str = "0.1"
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    model_setup: str | None = None


class Project(BaseModel):
    name: str | None = None
    location_description: str | None = None
    purpose: str | None = None


class Alignment(BaseModel):
    type: Literal["straight", "curved"] = "straight"
    bearing_deg: float | None = None
    radius_m: float | None = Field(default=None, gt=0)


class ProfilePoint(BaseModel):
    chainage_m: float = Field(ge=0)
    level_m: float


class ShoulderWidths(BaseModel):
    left: float = Field(ge=0)
    right: float = Field(ge=0)


class Road(BaseModel):
    length_m: float = Field(gt=0)
    alignment: Alignment = Field(default_factory=Alignment)
    carriageway_width_m: float = Field(gt=0)
    shoulder_width_m: ShoulderWidths
    camber: Camber = "crown"
    crossfall_pct: float | None = Field(default=None, ge=0)
    surface: Surface = "gravel"
    profile: list[ProfilePoint] = Field(min_length=2)

    @model_validator(mode="after")
    def _check_profile(self) -> Road:
        chainages = [point.chainage_m for point in self.profile]
        if chainages != sorted(chainages):
            raise ValueError("road.profile chainages must be in ascending order")
        if len(set(chainages)) != len(chainages):
            raise ValueError("road.profile chainages must be unique")
        if chainages[0] < 0 or chainages[-1] > self.length_m:
            raise ValueError("road.profile chainages must lie within the road length")
        return self


class Rainfall(BaseModel):
    method: Literal["rational"] = "rational"
    intensity_mm_per_hr: float | None = Field(default=None, gt=0)
    return_period_yr: float | None = Field(default=None, gt=0)
    source: RainfallSource = "placeholder"


class Catchment(BaseModel):
    id: str
    area_ha: float = Field(gt=0)
    runoff_coefficient: float | None = Field(default=None, ge=0, le=1)
    feeds: str
    description: str | None = None


class Section(BaseModel):
    shape: Shape
    bottom_width_m: float = Field(ge=0)
    depth_m: float = Field(gt=0)
    side_slope_h_per_v: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _check_shape(self) -> Section:
        if self.shape in ("rectangular", "trapezoidal") and self.bottom_width_m <= 0:
            raise ValueError(f"{self.shape} sections need a positive bottom_width_m")
        return self


class Outlet(BaseModel):
    type: OutletType
    ref: str | None = None


class Drain(BaseModel):
    id: str
    side: Side
    from_chainage_m: float = Field(ge=0)
    to_chainage_m: float = Field(gt=0)
    section: Section
    lining: Lining
    manning_n: float | None = Field(default=None, gt=0)
    gradient: float | None = None
    outlet: Outlet

    @model_validator(mode="after")
    def _check_chainages(self) -> Drain:
        if self.from_chainage_m >= self.to_chainage_m:
            raise ValueError(f"drain {self.id}: from_chainage_m must be less than to_chainage_m")
        return self


class Culvert(BaseModel):
    id: str
    chainage_m: float = Field(ge=0)
    type: Literal["pipe"] = "pipe"
    diameter_m: float = Field(gt=0)
    count: int = Field(default=1, ge=1)
    length_m: float | None = Field(default=None, gt=0)
    invert_in_m: float | None = None
    invert_out_m: float | None = None
    discharges_to: str | None = None


class Constraint(BaseModel):
    id: str | None = None
    type: str
    side: Side | None = None
    from_chainage_m: float | None = None
    to_chainage_m: float | None = None
    description: str | None = None


class Assumption(BaseModel):
    field: str
    value: str | float | None = None
    reason: str


class CheckResult(BaseModel):
    """One rule outcome. The message must say what to change, not just that it failed."""

    rule_id: str
    element_id: str
    status: CheckStatus
    measured: float | str | None = None
    limit: float | str | None = None
    message: str


class DrainResult(BaseModel):
    id: str
    design_flow_m3_s: float | None = None
    capacity_m3_s: float | None = None
    velocity_m_s: float | None = None
    gradient: float | None = None
    design_depth_m: float | None = None
    freeboard_m: float | None = None
    flow_area_m2: float | None = None
    invert_up_m: float | None = None
    invert_down_m: float | None = None


class CulvertResult(BaseModel):
    id: str
    design_flow_m3_s: float | None = None
    capacity_m3_s: float | None = None
    velocity_m_s: float | None = None
    cover_m: float | None = None
    invert_in_m: float | None = None
    invert_out_m: float | None = None


class Quantities(BaseModel):
    excavation_m3: float = 0.0
    lining_area_m2: float = 0.0
    pipe_length_m: float = 0.0
    headwall_count: int = 0


class Results(BaseModel):
    """Computed outputs. Written by code only."""

    drains: list[DrainResult] = Field(default_factory=list)
    culverts: list[CulvertResult] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    quantities: Quantities = Field(default_factory=Quantities)
    warnings: list[str] = Field(default_factory=list)


def _validate_references(
    road: Road,
    catchments: list[Catchment],
    drains: list[Drain],
    culverts: list[Culvert],
    constraints: list[Constraint],
) -> None:
    """Shared cross-section validation for DesignSpec and ParsedBrief."""
    drain_ids = {drain.id for drain in drains}
    culvert_ids = {culvert.id for culvert in culverts}
    all_ids = [c.id for c in catchments] + [d.id for d in drains] + [c.id for c in culverts]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("catchment, drain and culvert ids must be unique")

    for drain in drains:
        if drain.to_chainage_m > road.length_m or drain.from_chainage_m > road.length_m:
            raise ValueError(f"drain {drain.id}: chainages must lie within the road length")
        outlet = drain.outlet
        if outlet.type == "drain" and outlet.ref not in drain_ids:
            raise ValueError(f"drain {drain.id}: outlet.ref {outlet.ref!r} is not a drain id")
        if outlet.type == "culvert" and outlet.ref not in culvert_ids:
            raise ValueError(f"drain {drain.id}: outlet.ref {outlet.ref!r} is not a culvert id")

    for catchment in catchments:
        if catchment.feeds not in drain_ids:
            raise ValueError(
                f"catchment {catchment.id}: feeds {catchment.feeds!r} is not a drain id"
            )

    for culvert in culverts:
        if culvert.chainage_m > road.length_m:
            raise ValueError(f"culvert {culvert.id}: chainage lies outside the road length")
        if culvert.discharges_to is not None and culvert.discharges_to in culvert_ids:
            raise ValueError(f"culvert {culvert.id}: discharges_to must not be another culvert")

    for constraint in constraints:
        for value in (constraint.from_chainage_m, constraint.to_chainage_m):
            if value is not None and value > road.length_m:
                raise ValueError(
                    f"constraint {constraint.id}: chainages lie outside the road length"
                )


class ParsedBrief(BaseModel):
    """The subset the model fills: a spec without ``meta`` and ``results``."""

    project: Project = Field(default_factory=Project)
    road: Road
    rainfall: Rainfall
    catchments: list[Catchment]
    drains: list[Drain]
    culverts: list[Culvert] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> ParsedBrief:
        _validate_references(
            self.road, self.catchments, self.drains, self.culverts, self.constraints
        )
        return self


class DesignSpec(BaseModel):
    meta: Meta
    project: Project = Field(default_factory=Project)
    road: Road
    rainfall: Rainfall
    catchments: list[Catchment]
    drains: list[Drain]
    culverts: list[Culvert] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    results: Results | None = None

    @model_validator(mode="after")
    def _check_references(self) -> DesignSpec:
        _validate_references(
            self.road, self.catchments, self.drains, self.culverts, self.constraints
        )
        return self

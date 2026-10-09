"""Model-callable tools.

Each tool has a Pydantic argument model, a description with units, field locking and a dispatcher
that returns a :class:`ToolResult` (never raises to the model). OpenAI-format definitions are
generated from the argument models.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from drafty.checks.runner import run_checks
from drafty.engine import calculate
from drafty.engine.standards import Standards
from drafty.spec.models import (
    CheckResult,
    Culvert,
    DesignSpec,
    Drain,
    Outlet,
    Results,
    Section,
)

Shape = Literal["rectangular", "trapezoidal", "v"]
Side = Literal["left", "right"]
Lining = Literal["concrete", "masonry", "grass", "earth"]
OutletType = Literal["existing_channel", "culvert", "drain", "soakaway"]


@dataclass
class ToolResult:
    ok: bool
    message: str
    element_id: str | None = None


@dataclass
class SpecWorkspace:
    """A working copy of the spec plus the set of locked field groups."""

    spec: DesignSpec
    locked: set[str] = field(default_factory=set)

    def is_locked(self, group: str) -> bool:
        return group in self.locked


@dataclass
class ToolContext:
    workspace: SpecWorkspace
    standards: Standards
    results: Results | None = None
    checks: list[CheckResult] = field(default_factory=list)


class SetRoadSectionArgs(BaseModel):
    carriageway_width_m: float = Field(gt=0, description="Carriageway width in metres.")
    shoulder_left_m: float = Field(ge=0, description="Left shoulder width in metres.")
    shoulder_right_m: float = Field(ge=0, description="Right shoulder width in metres.")
    camber: Literal["crown", "crossfall"] = "crown"
    crossfall_pct: float | None = Field(default=None, ge=0, description="Crossfall in percent.")


class AddSideDrainArgs(BaseModel):
    side: Side
    from_chainage_m: float = Field(ge=0)
    to_chainage_m: float = Field(gt=0)
    shape: Shape = "trapezoidal"
    bottom_width_m: float = Field(ge=0, description="Bottom width in metres.")
    depth_m: float = Field(gt=0, description="Section depth in metres.")
    side_slope_h_per_v: float = Field(
        default=0.0, ge=0, description="Side slope, horizontal per 1 vertical."
    )
    lining: Lining = "concrete"
    outlet_type: OutletType = "existing_channel"
    outlet_ref: str | None = None


class ResizeDrainArgs(BaseModel):
    drain_id: str
    bottom_width_m: float = Field(ge=0, description="Bottom width in metres.")
    depth_m: float = Field(gt=0, description="Section depth in metres.")
    side_slope_h_per_v: float = Field(default=0.0, ge=0)


class SetDrainLiningArgs(BaseModel):
    drain_id: str
    lining: Lining


class SetDrainGradientArgs(BaseModel):
    drain_id: str
    gradient: float = Field(description="Longitudinal fall in m/m toward the outlet.")


class SplitDrainArgs(BaseModel):
    drain_id: str
    chainage_m: float = Field(gt=0, description="Chainage to split the reach at.")
    new_outlet_type: OutletType = "existing_channel"
    new_outlet_ref: str | None = None


class AddCulvertArgs(BaseModel):
    chainage_m: float = Field(ge=0)
    diameter_m: float = Field(gt=0, description="Barrel diameter in metres.")
    count: int = Field(default=1, ge=1, description="Number of barrels.")
    discharges_to: str | None = Field(
        default=None, description="Receiving drain id, or an outlet name."
    )


class ResizeCulvertArgs(BaseModel):
    culvert_id: str
    diameter_m: float = Field(gt=0, description="Barrel diameter in metres.")
    count: int = Field(default=1, ge=1)


class EmptyArgs(BaseModel):
    pass


class FinishArgs(BaseModel):
    summary: str = ""


TOOL_DESCRIPTIONS = {
    "set_road_section": "Set carriageway width (m), shoulder widths (m), camber and crossfall (%).",
    "add_side_drain": "Add a side drain with a section (m), lining and outlet.",
    "resize_drain": "Change a drain section: bottom width (m), depth (m) and side slope.",
    "set_drain_lining": "Change a drain lining (concrete, masonry, grass, earth).",
    "set_drain_gradient": "Set a drain longitudinal gradient (m/m) toward its outlet.",
    "split_drain": "Split a drain reach at a chainage (m) and give the upper part a new outlet.",
    "add_culvert": "Add a pipe culvert at a chainage (m) with diameter (m) and barrel count.",
    "resize_culvert": "Change a culvert diameter (m) and barrel count.",
    "run_calculations": "Compute flows, capacities, velocities and levels for the current design.",
    "run_checks": "Run all engineering checks on the current design.",
    "finish": "Finish this turn with a one-line summary.",
}


def _find_drain(spec: DesignSpec, drain_id: str) -> Drain | None:
    return next((drain for drain in spec.drains if drain.id == drain_id), None)


def _find_culvert(spec: DesignSpec, culvert_id: str) -> Culvert | None:
    return next((culvert for culvert in spec.culverts if culvert.id == culvert_id), None)


def set_road_section(ctx: ToolContext, args: SetRoadSectionArgs) -> ToolResult:
    if ctx.workspace.is_locked("road"):
        return ToolResult(False, "the road section is locked and cannot be changed")
    road = ctx.workspace.spec.road
    road.carriageway_width_m = args.carriageway_width_m
    road.shoulder_width_m.left = args.shoulder_left_m
    road.shoulder_width_m.right = args.shoulder_right_m
    road.camber = args.camber
    road.crossfall_pct = args.crossfall_pct
    return ToolResult(
        True,
        f"road section set: {args.carriageway_width_m} m carriageway, camber {args.camber}",
        "road",
    )


def add_side_drain(ctx: ToolContext, args: AddSideDrainArgs) -> ToolResult:
    spec = ctx.workspace.spec
    if args.from_chainage_m >= args.to_chainage_m:
        return ToolResult(False, "from_chainage_m must be less than to_chainage_m")
    if args.to_chainage_m > spec.road.length_m:
        return ToolResult(
            False,
            f"to_chainage_m {args.to_chainage_m} exceeds the road length {spec.road.length_m}",
        )
    try:
        section = Section(
            shape=args.shape,
            bottom_width_m=args.bottom_width_m,
            depth_m=args.depth_m,
            side_slope_h_per_v=args.side_slope_h_per_v,
        )
    except ValidationError as exc:
        return ToolResult(False, f"invalid section: {exc}")
    prefix = "D-L" if args.side == "left" else "D-R"
    new_id = f"{prefix}{sum(1 for drain in spec.drains if drain.id.startswith(prefix)) + 1}"
    spec.drains.append(
        Drain(
            id=new_id,
            side=args.side,
            from_chainage_m=args.from_chainage_m,
            to_chainage_m=args.to_chainage_m,
            section=section,
            lining=args.lining,
            outlet=Outlet(type=args.outlet_type, ref=args.outlet_ref),
        )
    )
    return ToolResult(True, f"added drain {new_id} on the {args.side}", new_id)


def resize_drain(ctx: ToolContext, args: ResizeDrainArgs) -> ToolResult:
    drain = _find_drain(ctx.workspace.spec, args.drain_id)
    if drain is None:
        return ToolResult(False, f"no drain with id {args.drain_id!r}")
    try:
        drain.section = Section(
            shape=drain.section.shape,
            bottom_width_m=args.bottom_width_m,
            depth_m=args.depth_m,
            side_slope_h_per_v=args.side_slope_h_per_v,
        )
    except ValidationError as exc:
        return ToolResult(False, f"invalid section: {exc}")
    return ToolResult(
        True,
        f"{args.drain_id} resized to {args.bottom_width_m} x {args.depth_m} m",
        args.drain_id,
    )


def set_drain_lining(ctx: ToolContext, args: SetDrainLiningArgs) -> ToolResult:
    drain = _find_drain(ctx.workspace.spec, args.drain_id)
    if drain is None:
        return ToolResult(False, f"no drain with id {args.drain_id!r}")
    drain.lining = args.lining
    return ToolResult(True, f"{args.drain_id} lining set to {args.lining}", args.drain_id)


def set_drain_gradient(ctx: ToolContext, args: SetDrainGradientArgs) -> ToolResult:
    drain = _find_drain(ctx.workspace.spec, args.drain_id)
    if drain is None:
        return ToolResult(False, f"no drain with id {args.drain_id!r}")
    drain.gradient = args.gradient
    return ToolResult(True, f"{args.drain_id} gradient set to {args.gradient} m/m", args.drain_id)


def split_drain(ctx: ToolContext, args: SplitDrainArgs) -> ToolResult:
    spec = ctx.workspace.spec
    drain = _find_drain(spec, args.drain_id)
    if drain is None:
        return ToolResult(False, f"no drain with id {args.drain_id!r}")
    if not (drain.from_chainage_m < args.chainage_m < drain.to_chainage_m):
        return ToolResult(False, "chainage_m must lie strictly inside the reach")
    prefix = "D-L" if drain.side == "left" else "D-R"
    new_id = f"{prefix}{sum(1 for d in spec.drains if d.id.startswith(prefix)) + 1}"
    original_to = drain.to_chainage_m
    original_outlet = drain.outlet
    drain.to_chainage_m = args.chainage_m
    drain.outlet = Outlet(type=args.new_outlet_type, ref=args.new_outlet_ref)
    spec.drains.append(
        Drain(
            id=new_id,
            side=drain.side,
            from_chainage_m=args.chainage_m,
            to_chainage_m=original_to,
            section=drain.section.model_copy(),
            lining=drain.lining,
            manning_n=drain.manning_n,
            gradient=drain.gradient,
            outlet=original_outlet,
        )
    )
    return ToolResult(True, f"split {args.drain_id} at {args.chainage_m} into {new_id}", new_id)


def add_culvert(ctx: ToolContext, args: AddCulvertArgs) -> ToolResult:
    spec = ctx.workspace.spec
    if args.chainage_m > spec.road.length_m:
        return ToolResult(False, "chainage_m exceeds the road length")
    new_id = f"C-{len(spec.culverts) + 1:02d}"
    spec.culverts.append(
        Culvert(
            id=new_id,
            chainage_m=args.chainage_m,
            type="pipe",
            diameter_m=args.diameter_m,
            count=args.count,
            discharges_to=args.discharges_to,
        )
    )
    return ToolResult(True, f"added culvert {new_id} at ch {args.chainage_m}", new_id)


def resize_culvert(ctx: ToolContext, args: ResizeCulvertArgs) -> ToolResult:
    culvert = _find_culvert(ctx.workspace.spec, args.culvert_id)
    if culvert is None:
        return ToolResult(False, f"no culvert with id {args.culvert_id!r}")
    culvert.diameter_m = args.diameter_m
    culvert.count = args.count
    return ToolResult(
        True,
        f"{args.culvert_id} set to {args.diameter_m} m x{args.count}",
        args.culvert_id,
    )


def run_calculations(ctx: ToolContext, args: EmptyArgs) -> ToolResult:
    results = calculate(ctx.workspace.spec, ctx.standards)
    ctx.results = results
    ctx.workspace.spec.results = results
    return ToolResult(
        True, f"calculated {len(results.drains)} drains and {len(results.culverts)} culverts"
    )


def run_checks_tool(ctx: ToolContext, args: EmptyArgs) -> ToolResult:
    if ctx.results is None:
        ctx.results = calculate(ctx.workspace.spec, ctx.standards)
    checks = run_checks(ctx.workspace.spec, ctx.results, ctx.standards)
    ctx.checks = checks
    ctx.results.checks = checks
    ctx.workspace.spec.results = ctx.results
    failing = [check for check in checks if check.status == "fail"]
    if not failing:
        return ToolResult(True, "all checks pass")
    summary = "; ".join(
        f"{check.rule_id} {check.element_id}: {check.message}" for check in failing[:5]
    )
    return ToolResult(True, f"{len(failing)} failing check(s): {summary}")


def finish(ctx: ToolContext, args: FinishArgs) -> ToolResult:
    return ToolResult(True, args.summary or "finished")


TOOLS: dict[str, tuple[type[BaseModel], Callable[[ToolContext, Any], ToolResult]]] = {
    "set_road_section": (SetRoadSectionArgs, set_road_section),
    "add_side_drain": (AddSideDrainArgs, add_side_drain),
    "resize_drain": (ResizeDrainArgs, resize_drain),
    "set_drain_lining": (SetDrainLiningArgs, set_drain_lining),
    "set_drain_gradient": (SetDrainGradientArgs, set_drain_gradient),
    "split_drain": (SplitDrainArgs, split_drain),
    "add_culvert": (AddCulvertArgs, add_culvert),
    "resize_culvert": (ResizeCulvertArgs, resize_culvert),
    "run_calculations": (EmptyArgs, run_calculations),
    "run_checks": (EmptyArgs, run_checks_tool),
    "finish": (FinishArgs, finish),
}


def tool_definitions() -> list[dict[str, Any]]:
    """OpenAI-format tool definitions generated from the argument models."""
    definitions: list[dict[str, Any]] = []
    for name, (args_model, _) in TOOLS.items():
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": TOOL_DESCRIPTIONS.get(name, ""),
                    "parameters": args_model.model_json_schema(),
                },
            }
        )
    return definitions


def dispatch(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> ToolResult:
    """Validate arguments and run a tool, returning a clear error string on any failure."""
    entry = TOOLS.get(name)
    if entry is None:
        return ToolResult(False, f"unknown tool {name!r}")
    args_model, function = entry
    try:
        args = args_model.model_validate(arguments)
    except ValidationError as exc:
        return ToolResult(False, f"invalid arguments for {name}: {exc}")
    try:
        return function(ctx, args)
    except Exception as exc:  # noqa: BLE001 - the model must see a clear error, never a crash
        return ToolResult(False, f"{name} failed: {exc}")

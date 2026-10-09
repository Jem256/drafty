"""Tool dispatcher: argument validation, mutations, locking and generated definitions."""

from __future__ import annotations

import specs
from drafty.agent.tools import SpecWorkspace, ToolContext, dispatch, tool_definitions
from drafty.spec.models import DesignSpec, Meta

ALL_TOOLS = {
    "set_road_section",
    "add_side_drain",
    "resize_drain",
    "set_drain_lining",
    "set_drain_gradient",
    "split_drain",
    "add_culvert",
    "resize_culvert",
    "run_calculations",
    "run_checks",
    "finish",
}


def _empty_spec() -> DesignSpec:
    return DesignSpec(meta=Meta(run_id="t"), **specs.parsed_no_drains().model_dump())


def _ctx(standards, spec: DesignSpec | None = None, locked: set[str] | None = None) -> ToolContext:
    return ToolContext(SpecWorkspace(spec or specs.happy_spec(), locked=locked or set()), standards)


def test_tool_definitions_cover_all_tools() -> None:
    names = {definition["function"]["name"] for definition in tool_definitions()}
    assert names == ALL_TOOLS
    assert all(definition["function"]["parameters"] for definition in tool_definitions())


def test_add_side_drain_creates_drain(standards) -> None:
    ctx = _ctx(standards, spec=_empty_spec())
    result = dispatch(
        ctx,
        "add_side_drain",
        {
            "side": "left",
            "from_chainage_m": 0,
            "to_chainage_m": 200,
            "shape": "rectangular",
            "bottom_width_m": 0.5,
            "depth_m": 0.8,
        },
    )
    assert result.ok and result.element_id == "D-L1"
    assert ctx.workspace.spec.drains[0].side == "left"


def test_add_side_drain_rejects_chainage_beyond_road(standards) -> None:
    ctx = _ctx(standards, spec=_empty_spec())
    result = dispatch(
        ctx,
        "add_side_drain",
        {
            "side": "left",
            "from_chainage_m": 0,
            "to_chainage_m": 500,
            "shape": "rectangular",
            "bottom_width_m": 0.5,
            "depth_m": 0.8,
        },
    )
    assert not result.ok and "road length" in result.message


def test_resize_drain(standards) -> None:
    ctx = _ctx(standards)
    result = dispatch(
        ctx, "resize_drain", {"drain_id": "D-L1", "bottom_width_m": 0.6, "depth_m": 1.0}
    )
    assert result.ok
    assert ctx.workspace.spec.drains[0].section.depth_m == 1.0


def test_resize_drain_unknown_id(standards) -> None:
    result = dispatch(
        _ctx(standards), "resize_drain", {"drain_id": "X", "bottom_width_m": 0.6, "depth_m": 1.0}
    )
    assert not result.ok and "no drain" in result.message


def test_set_lining_and_gradient(standards) -> None:
    ctx = _ctx(standards)
    assert dispatch(ctx, "set_drain_lining", {"drain_id": "D-L1", "lining": "grass"}).ok
    assert dispatch(ctx, "set_drain_gradient", {"drain_id": "D-L1", "gradient": 0.01}).ok
    drain = ctx.workspace.spec.drains[0]
    assert drain.lining == "grass" and drain.gradient == 0.01


def test_split_drain(standards) -> None:
    ctx = _ctx(standards)
    result = dispatch(ctx, "split_drain", {"drain_id": "D-L1", "chainage_m": 100})
    assert result.ok
    ids = {drain.id for drain in ctx.workspace.spec.drains}
    assert "D-L2" in ids
    assert ctx.workspace.spec.drains[0].to_chainage_m == 100


def test_add_and_resize_culvert(standards) -> None:
    ctx = _ctx(standards, spec=_empty_spec())
    added = dispatch(ctx, "add_culvert", {"chainage_m": 50, "diameter_m": 0.6})
    assert added.ok and added.element_id == "C-01"
    resized = dispatch(ctx, "resize_culvert", {"culvert_id": "C-01", "diameter_m": 0.9, "count": 2})
    assert resized.ok
    assert ctx.workspace.spec.culverts[0].diameter_m == 0.9


def test_run_calculations_and_checks(standards) -> None:
    ctx = _ctx(standards)
    assert dispatch(ctx, "run_calculations", {}).ok
    assert ctx.results is not None
    result = dispatch(ctx, "run_checks", {})
    assert result.ok
    assert ctx.checks


def test_finish(standards) -> None:
    result = dispatch(_ctx(standards), "finish", {"summary": "done"})
    assert result.ok and result.message == "done"


def test_unknown_tool(standards) -> None:
    result = dispatch(_ctx(standards), "explode", {})
    assert not result.ok and "unknown tool" in result.message


def test_invalid_arguments(standards) -> None:
    result = dispatch(_ctx(standards), "resize_drain", {"drain_id": "D-L1", "depth_m": -1})
    assert not result.ok and "invalid arguments" in result.message


def test_locked_road_cannot_change(standards) -> None:
    ctx = _ctx(standards, locked={"road"})
    result = dispatch(
        ctx,
        "set_road_section",
        {"carriageway_width_m": 7.0, "shoulder_left_m": 1.0, "shoulder_right_m": 1.0},
    )
    assert not result.ok and "locked" in result.message


def test_v_section_rejects_bottom_width(standards) -> None:
    result = dispatch(
        _ctx(standards, spec=_empty_spec()),
        "add_side_drain",
        {
            "side": "left",
            "from_chainage_m": 0,
            "to_chainage_m": 100,
            "shape": "v",
            "bottom_width_m": 0.5,
            "depth_m": 0.6,
        },
    )
    assert not result.ok

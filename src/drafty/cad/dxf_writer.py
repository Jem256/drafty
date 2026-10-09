"""Write the plan, typical cross-section and long-section views to a DXF.

The drawing is produced from the spec and the computed results, so the drawing and the numbers
always agree. R2018 format, metres. Every entity is placed on one of the standard layers.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf

from drafty.spec.models import DesignSpec, Results, Section

STANDARD_LAYERS: tuple[str, ...] = (
    "ROAD-CL",
    "ROAD-EDGE",
    "ROAD-SHOULDER",
    "DRAIN-L",
    "DRAIN-R",
    "CULVERT",
    "TEXT-CHAINAGE",
    "TEXT-LABEL",
    "XSECT",
    "LSECT",
)

TICK_INTERVAL_M = 20.0
TEXT_HEIGHT_M = 2.0
VIEW_GAP_M = 10.0
NOTE = "First draft for engineer review - not for construction"
DEFAULT_CROSSFALL_PCT = 2.5


def _crossfall(spec: DesignSpec) -> float:
    if spec.road.crossfall_pct is not None:
        return spec.road.crossfall_pct
    return DEFAULT_CROSSFALL_PCT


def section_top_width_m(section: Section) -> float:
    if section.shape == "rectangular":
        return section.bottom_width_m
    return section.bottom_width_m + 2.0 * section.side_slope_h_per_v * section.depth_m


def _text(msp, content: str, x: float, y: float, layer: str, height: float = TEXT_HEIGHT_M) -> None:
    entity = msp.add_text(content, height=height, dxfattribs={"layer": layer})
    entity.set_placement((x, y))


def _plan_metrics(spec: DesignSpec) -> tuple[float, float, float]:
    """Return ``(carriageway_half, outer_edge, plan_half)``."""
    carriageway_half = spec.road.carriageway_width_m / 2.0
    outer_edge = carriageway_half + max(
        spec.road.shoulder_width_m.left, spec.road.shoulder_width_m.right
    )
    max_drain_top = max((section_top_width_m(d.section) for d in spec.drains), default=0.0)
    return carriageway_half, outer_edge, outer_edge + max_drain_top


def _write_plan(
    msp, spec: DesignSpec, results: Results, outer_edge: float, plan_half: float
) -> None:
    length = spec.road.length_m
    msp.add_line((0, 0), (length, 0), dxfattribs={"layer": "ROAD-CL"})

    chainage = 0.0
    while chainage <= length + 1e-6:
        msp.add_line((chainage, -1.0), (chainage, 1.0), dxfattribs={"layer": "ROAD-CL"})
        _text(msp, f"ch {chainage:.0f}", chainage, -1.5, "TEXT-CHAINAGE", height=1.5)
        chainage += TICK_INTERVAL_M

    carriageway_half = spec.road.carriageway_width_m / 2.0
    for y in (carriageway_half, -carriageway_half):
        msp.add_line((0, y), (length, y), dxfattribs={"layer": "ROAD-EDGE"})
    for y in (outer_edge, -outer_edge):
        msp.add_line((0, y), (length, y), dxfattribs={"layer": "ROAD-SHOULDER"})

    for drain in spec.drains:
        layer = "DRAIN-L" if drain.side == "left" else "DRAIN-R"
        top_width = section_top_width_m(drain.section)
        sign = -1.0 if drain.side == "left" else 1.0
        inner_y = sign * outer_edge
        outer_y = sign * (outer_edge + top_width)
        msp.add_line(
            (drain.from_chainage_m, inner_y),
            (drain.to_chainage_m, inner_y),
            dxfattribs={"layer": layer},
        )
        msp.add_line(
            (drain.from_chainage_m, outer_y),
            (drain.to_chainage_m, outer_y),
            dxfattribs={"layer": layer},
        )
        _text(
            msp,
            drain.id,
            drain.from_chainage_m,
            sign * (outer_edge + top_width + 1.0),
            "TEXT-LABEL",
            height=1.5,
        )

    for culvert in spec.culverts:
        msp.add_line(
            (culvert.chainage_m, -outer_edge),
            (culvert.chainage_m, outer_edge),
            dxfattribs={"layer": "CULVERT"},
        )
        _text(msp, culvert.id, culvert.chainage_m, outer_edge + 1.0, "TEXT-LABEL", height=1.5)

    _text(msp, "PLAN", 0, plan_half + 3.0, "TEXT-LABEL", height=3.0)
    _text(msp, NOTE, 0, plan_half + 7.0, "TEXT-LABEL", height=1.5)


def _surface_level(road, offset: float, crossfall_pct: float) -> float:
    slope = crossfall_pct / 100.0
    if road.camber == "crown":
        return -slope * abs(offset)
    return -slope * offset


def _drain_polygon(
    section: Section, offset_inner: float, shoulder_level: float, side: str
) -> list[tuple[float, float]]:
    top_width = section_top_width_m(section)
    bottom_width = section.bottom_width_m if section.shape != "v" else 0.0
    inset = (top_width - bottom_width) / 2.0
    sign = -1.0 if side == "left" else 1.0
    offset_outer = offset_inner + sign * top_width
    return [
        (offset_inner, shoulder_level),
        (offset_outer, shoulder_level),
        (offset_outer - sign * inset, shoulder_level - section.depth_m),
        (offset_inner + sign * inset, shoulder_level - section.depth_m),
        (offset_inner, shoulder_level),
    ]


def _write_cross_section(msp, spec: DesignSpec, origin_x: float, outer_edge: float) -> None:
    crossfall = _crossfall(spec)
    road = spec.road
    offsets = [
        -outer_edge,
        -road.carriageway_width_m / 2,
        0.0,
        road.carriageway_width_m / 2,
        outer_edge,
    ]
    surface = [(origin_x + off, _surface_level(road, off, crossfall)) for off in offsets]
    msp.add_lwpolyline(surface, dxfattribs={"layer": "XSECT"})

    for drain in spec.drains:
        sign = -1.0 if drain.side == "left" else 1.0
        offset_inner = sign * outer_edge
        shoulder_level = _surface_level(road, offset_inner, crossfall)
        points = _drain_polygon(drain.section, offset_inner, shoulder_level, drain.side)
        msp.add_lwpolyline([(origin_x + x, y) for x, y in points], dxfattribs={"layer": "XSECT"})

    _text(msp, "TYPICAL CROSS-SECTION", origin_x - outer_edge, 4.0, "TEXT-LABEL", height=3.0)


def _write_long_section(
    msp, spec: DesignSpec, results: Results, base_y: float, min_level: float
) -> None:
    road = spec.road
    road_points = [(point.chainage_m, base_y + point.level_m - min_level) for point in road.profile]
    msp.add_lwpolyline(road_points, dxfattribs={"layer": "LSECT"})

    reach_by_id = {reach.id: reach for reach in results.drains}
    for drain in spec.drains:
        reach = reach_by_id.get(drain.id)
        if reach is None or reach.invert_up_m is None or reach.invert_down_m is None:
            continue
        points = [
            (drain.from_chainage_m, base_y + reach.invert_up_m - min_level),
            (drain.to_chainage_m, base_y + reach.invert_down_m - min_level),
        ]
        msp.add_lwpolyline(points, dxfattribs={"layer": "LSECT"})

    for culvert in spec.culverts:
        msp.add_line(
            (culvert.chainage_m, base_y - 2.0),
            (culvert.chainage_m, base_y + 4.0),
            dxfattribs={"layer": "CULVERT"},
        )
        _text(msp, culvert.id, culvert.chainage_m, base_y + 4.5, "TEXT-LABEL", height=1.5)

    chainage = 0.0
    while chainage <= road.length_m + 1e-6:
        _text(msp, f"ch {chainage:.0f}", chainage, base_y - 4.0, "TEXT-CHAINAGE", height=1.5)
        chainage += TICK_INTERVAL_M

    _text(msp, "LONG-SECTION", 0.0, base_y + 8.0, "TEXT-LABEL", height=3.0)


def write_dxf(spec: DesignSpec, results: Results, path: str | Path) -> Path:
    """Write the drawing and return its path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.M
    for name in STANDARD_LAYERS:
        if name not in doc.layers:
            doc.layers.add(name)
    msp = doc.modelspace()

    _, outer_edge, plan_half = _plan_metrics(spec)
    _write_plan(msp, spec, results, outer_edge, plan_half)

    cross_section_x = spec.road.length_m + VIEW_GAP_M + plan_half
    _write_cross_section(msp, spec, cross_section_x, outer_edge)

    min_level = min(point.level_m for point in spec.road.profile)
    span = max(point.level_m for point in spec.road.profile) - min_level
    long_section_base_y = -plan_half - VIEW_GAP_M - span
    _write_long_section(msp, spec, results, long_section_base_y, min_level)

    doc.saveas(path)
    return path


def nonstandard_layers(path: str | Path) -> list[tuple[str, str]]:
    """Return ``(layer, dxftype)`` for every entity not on a standard layer."""
    doc = ezdxf.readfile(path)
    offending: list[tuple[str, str]] = []
    for entity in doc.modelspace():
        layer = entity.dxf.layer
        if layer not in STANDARD_LAYERS:
            offending.append((layer, entity.dxftype()))
    return offending


def audit_error_count(path: str | Path) -> int:
    """Number of errors ezdxf's auditor reports for the file."""
    doc = ezdxf.readfile(path)
    return len(doc.audit().errors)

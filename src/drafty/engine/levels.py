"""Road, drain and culvert level computation.

Road levels come from linear interpolation of the road profile. Drain inverts follow the road edge
minus the section depth unless a gradient overrides the invert line. Culvert inverts come from the
upstream drain; cover is measured from the road surface.
"""

from __future__ import annotations

import bisect

from drafty.spec.models import Culvert, Drain, Road, Side


def road_level_at(road: Road, chainage_m: float) -> float:
    """Interpolate the centreline road level at a chainage."""
    points = road.profile
    chainages = [point.chainage_m for point in points]
    if chainage_m <= chainages[0]:
        return points[0].level_m
    if chainage_m >= chainages[-1]:
        return points[-1].level_m
    index = bisect.bisect_right(chainages, chainage_m) - 1
    x0, y0 = points[index].chainage_m, points[index].level_m
    x1, y1 = points[index + 1].chainage_m, points[index + 1].level_m
    if x1 == x0:
        return y0
    fraction = (chainage_m - x0) / (x1 - x0)
    return y0 + fraction * (y1 - y0)


def road_edge_offset_m(road: Road, side: Side) -> float:
    """Distance from the centreline to the road edge on a side."""
    shoulder = road.shoulder_width_m.left if side == "left" else road.shoulder_width_m.right
    return road.carriageway_width_m / 2.0 + shoulder


def road_edge_level(road: Road, chainage_m: float, side: Side, crossfall_pct: float) -> float:
    """Road edge level, allowing for camber or one-way crossfall.

    A crown sheds both ways from the centreline. A crossfall sheds to the right (the right edge is
    the low side).
    """
    centre = road_level_at(road, chainage_m)
    offset = road_edge_offset_m(road, side)
    slope = crossfall_pct / 100.0
    if road.camber == "crown":
        drop = slope * offset
    else:
        signed_offset = offset if side == "right" else -offset
        drop = slope * signed_offset
    return centre - drop


def drain_gradient(road: Road, drain: Drain, crossfall_pct: float) -> float:
    """Longitudinal fall per metre toward the outlet.

    Uses the explicit gradient when given, otherwise the fall of the road edge over the reach.
    """
    if drain.gradient is not None:
        return drain.gradient
    length = drain.to_chainage_m - drain.from_chainage_m
    if length <= 0:
        return 0.0
    up = road_edge_level(road, drain.from_chainage_m, drain.side, crossfall_pct)
    down = road_edge_level(road, drain.to_chainage_m, drain.side, crossfall_pct)
    return (up - down) / length


def drain_invert_at(road: Road, drain: Drain, chainage_m: float, crossfall_pct: float) -> float:
    """Drain invert level at a chainage."""
    if drain.gradient is None:
        edge = road_edge_level(road, chainage_m, drain.side, crossfall_pct)
        return edge - drain.section.depth_m
    start_edge = road_edge_level(road, drain.from_chainage_m, drain.side, crossfall_pct)
    start_invert = start_edge - drain.section.depth_m
    return start_invert - drain.gradient * (chainage_m - drain.from_chainage_m)


def culvert_inverts(
    road: Road, culvert: Culvert, upstream_invert: float | None, crossfall_pct: float
) -> tuple[float | None, float | None]:
    """Culvert inlet and outlet invert levels.

    The inlet comes from the upstream drain unless the spec sets it; the outlet falls by the culvert
    length times the road gradient unless the spec sets it.
    """
    invert_in = culvert.invert_in_m if culvert.invert_in_m is not None else upstream_invert
    if invert_in is None:
        return (None, culvert.invert_out_m)
    if culvert.invert_out_m is not None:
        return (invert_in, culvert.invert_out_m)
    length = culvert.length_m
    if length is None:
        length = road.carriageway_width_m + road.shoulder_width_m.left + road.shoulder_width_m.right
    slope = 0.0
    up = road_level_at(road, max(culvert.chainage_m - length / 2, 0.0))
    down = road_level_at(road, min(culvert.chainage_m + length / 2, road.length_m))
    if length > 0:
        slope = max(up - down, 0.0) / length
    return (invert_in, invert_in - slope * length)


def culvert_cover_m(
    road: Road, culvert: Culvert, invert_in_m: float | None, wall_allowance_m: float
) -> float | None:
    """Depth of cover over a culvert crown at its chainage."""
    if invert_in_m is None:
        return None
    road_level = road_level_at(road, culvert.chainage_m)
    return road_level - (invert_in_m + culvert.diameter_m + wall_allowance_m)

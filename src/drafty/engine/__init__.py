"""Deterministic engine entry point.

``calculate(spec, standards)`` fills flows, capacities, velocities, levels, quantities and warnings.
It never mutates its inputs and never calls a model. Checks are produced separately by the checker.
"""

from __future__ import annotations

from pathlib import Path

from drafty.engine import hydraulics, levels, network, quantities
from drafty.engine.hydrology import rational_flow_m3_s
from drafty.engine.standards import Standards
from drafty.spec.models import (
    CulvertResult,
    DesignSpec,
    DrainResult,
    Quantities,
    Results,
)

SpecLike = DesignSpec


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _resolve_crossfall(spec: SpecLike, standards: Standards, warnings: list[str]) -> float:
    if spec.road.crossfall_pct is not None:
        return spec.road.crossfall_pct
    key = "paved" if spec.road.surface in ("tarmac", "concrete") else "gravel"
    value, _, _ = standards.get("crossfall_pct", key)
    if value is None:
        warnings.append("road crossfall is not set and no standard value is available; using 0%")
        return 0.0
    return value


def _manning_n(drain_lining: str, override: float | None, standards: Standards) -> float | None:
    if override is not None:
        return override
    value, _, _ = standards.get("manning_n", drain_lining)
    return value


def calculate(
    spec: SpecLike,
    standards: Standards | None = None,
    standards_path: str | Path | None = None,
) -> Results:
    """Compute all engineering results for a spec."""
    if standards is None:
        if standards_path is None:
            raise ValueError("calculate needs a Standards instance or a standards_path")
        standards = Standards.load(standards_path)

    warnings: list[str] = []
    intensity = spec.rainfall.intensity_mm_per_hr
    if intensity is None:
        warnings.append("rainfall intensity is not set; design flows are not computed")
    if spec.rainfall.source == "placeholder":
        warnings.append("rainfall is a placeholder; replace it with a design value")

    crossfall = _resolve_crossfall(spec, standards, warnings)

    injections: dict[str, float] = {}
    for catchment in spec.catchments:
        coefficient = catchment.runoff_coefficient
        if coefficient is None:
            warnings.append(
                f"catchment {catchment.id} has no runoff coefficient; its flow is not computed"
            )
            continue
        if intensity is None:
            continue
        flow = rational_flow_m3_s(coefficient, intensity, catchment.area_ha)
        injections[catchment.feeds] = injections.get(catchment.feeds, 0.0) + flow

    flow_per_node, network_warnings = network.accumulate_flows(spec, injections)
    warnings.extend(network_warnings)

    drain_results: list[DrainResult] = []
    excavation_m3 = 0.0
    lining_area = 0.0

    for drain in spec.drains:
        gradient = levels.drain_gradient(spec.road, drain, crossfall)
        n = _manning_n(drain.lining, drain.manning_n, standards)
        design_flow = None if intensity is None else flow_per_node.get(drain.id, 0.0)

        capacity = velocity = design_depth = freeboard = flow_area = None
        if n is not None:
            capacity, _, _ = hydraulics.capacity_at_depth(
                drain.section, drain.section.depth_m, gradient, n
            )
            if design_flow is not None:
                design_depth = hydraulics.normal_depth(drain.section, design_flow, gradient, n)
                _, velocity, geometry = hydraulics.capacity_at_depth(
                    drain.section, design_depth, gradient, n
                )
                flow_area = geometry.area_m2
                freeboard = drain.section.depth_m - design_depth

        drain_results.append(
            DrainResult(
                id=drain.id,
                design_flow_m3_s=design_flow,
                capacity_m3_s=capacity,
                velocity_m_s=velocity,
                gradient=gradient,
                design_depth_m=design_depth,
                freeboard_m=freeboard,
                flow_area_m2=flow_area,
                invert_up_m=levels.drain_invert_at(
                    spec.road, drain, drain.from_chainage_m, crossfall
                ),
                invert_down_m=levels.drain_invert_at(
                    spec.road, drain, drain.to_chainage_m, crossfall
                ),
            )
        )

        geometry_full = hydraulics.section_geometry(drain.section, drain.section.depth_m)
        length = drain.to_chainage_m - drain.from_chainage_m
        excavation_m3 += quantities.excavation_volume_m3(geometry_full.area_m2, length)
        lining_area += quantities.lining_area_m2(geometry_full.wetted_perimeter_m, length)

    wall_allowance, _, _ = standards.get("culvert_wall_allowance_m")
    wall_allowance = wall_allowance if wall_allowance is not None else 0.0
    pipe_n = _manning_n("concrete", None, standards)

    culvert_results: list[CulvertResult] = []
    pipe_length_total = 0.0
    for culvert in spec.culverts:
        upstream_invert = None
        for drain in spec.drains:
            if drain.outlet.type == "culvert" and drain.outlet.ref == culvert.id:
                upstream_invert = levels.drain_invert_at(
                    spec.road, drain, culvert.chainage_m, crossfall
                )
                break

        invert_in, invert_out = levels.culvert_inverts(
            spec.road, culvert, upstream_invert, crossfall
        )
        length = quantities.pipe_length_m(spec.road, culvert.length_m)
        if invert_in is not None and invert_out is not None and length > 0:
            slope = max((invert_in - invert_out) / length, 0.0)
        else:
            slope = 0.0

        capacity = velocity = None
        if pipe_n is not None:
            capacity = (
                hydraulics.pipe_full_capacity(culvert.diameter_m, slope, pipe_n) * culvert.count
            )
            velocity = hydraulics.pipe_full_velocity(culvert.diameter_m, slope, pipe_n)

        culvert_results.append(
            CulvertResult(
                id=culvert.id,
                design_flow_m3_s=None if intensity is None else flow_per_node.get(culvert.id, 0.0),
                capacity_m3_s=capacity,
                velocity_m_s=velocity,
                cover_m=levels.culvert_cover_m(spec.road, culvert, invert_in, wall_allowance),
                invert_in_m=invert_in,
                invert_out_m=invert_out,
            )
        )
        pipe_length_total += length

    results = Results(
        drains=drain_results,
        culverts=culvert_results,
        quantities=Quantities(
            excavation_m3=excavation_m3,
            lining_area_m2=lining_area,
            pipe_length_m=pipe_length_total,
            headwall_count=quantities.headwall_count(len(spec.culverts)),
        ),
        warnings=_dedupe(warnings + standards.warnings),
    )
    return results

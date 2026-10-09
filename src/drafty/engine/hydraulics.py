"""Section geometry and Manning capacity/velocity.

Flow area and wetted perimeter for rectangular, trapezoidal and V sections at a given depth; Manning
capacity and velocity; and full-bore circular pipe capacity. All SI units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from drafty.spec.models import Section

_EPS = 1e-9


@dataclass(frozen=True)
class SectionGeometry:
    area_m2: float
    wetted_perimeter_m: float

    @property
    def hydraulic_radius_m(self) -> float:
        if self.wetted_perimeter_m <= _EPS:
            return 0.0
        return self.area_m2 / self.wetted_perimeter_m


def section_geometry(section: Section, depth_m: float) -> SectionGeometry:
    """Flow area and wetted perimeter at a water depth."""
    if depth_m <= 0:
        return SectionGeometry(0.0, 0.0)
    bottom = section.bottom_width_m
    side = section.side_slope_h_per_v
    depth = depth_m
    if section.shape == "rectangular":
        area = bottom * depth
        perimeter = bottom + 2 * depth
    elif section.shape == "trapezoidal":
        area = depth * (bottom + side * depth)
        perimeter = bottom + 2 * depth * math.sqrt(1 + side * side)
    elif section.shape == "v":
        area = side * depth * depth
        perimeter = 2 * depth * math.sqrt(1 + side * side)
    else:  # pragma: no cover - guarded by the Section literal type
        raise ValueError(f"unknown section shape {section.shape!r}")
    return SectionGeometry(area, perimeter)


def manning_capacity(area_m2: float, wetted_perimeter_m: float, slope: float, n: float) -> float:
    """Manning discharge capacity Q = (1/n) A R^(2/3) S^(1/2)."""
    if area_m2 <= _EPS or wetted_perimeter_m <= _EPS or slope <= _EPS or n <= _EPS:
        return 0.0
    radius = area_m2 / wetted_perimeter_m
    return (1.0 / n) * area_m2 * radius ** (2.0 / 3.0) * math.sqrt(slope)


def manning_velocity(area_m2: float, wetted_perimeter_m: float, slope: float, n: float) -> float:
    """Manning velocity V = (1/n) R^(2/3) S^(1/2)."""
    if area_m2 <= _EPS or wetted_perimeter_m <= _EPS or slope <= _EPS or n <= _EPS:
        return 0.0
    radius = area_m2 / wetted_perimeter_m
    return (1.0 / n) * radius ** (2.0 / 3.0) * math.sqrt(slope)


def capacity_at_depth(
    section: Section, depth_m: float, slope: float, n: float
) -> tuple[float, float, SectionGeometry]:
    """Return ``(capacity, velocity, geometry)`` for a section at a water depth."""
    geometry = section_geometry(section, depth_m)
    capacity = manning_capacity(geometry.area_m2, geometry.wetted_perimeter_m, slope, n)
    velocity = manning_velocity(geometry.area_m2, geometry.wetted_perimeter_m, slope, n)
    return capacity, velocity, geometry


def full_pipe_geometry(diameter_m: float) -> SectionGeometry:
    """Full-bore circular pipe geometry."""
    area = math.pi * diameter_m * diameter_m / 4.0
    perimeter = math.pi * diameter_m
    return SectionGeometry(area, perimeter)


def pipe_full_capacity(diameter_m: float, slope: float, n: float) -> float:
    """Full-bore pipe capacity (per barrel)."""
    geometry = full_pipe_geometry(diameter_m)
    return manning_capacity(geometry.area_m2, geometry.wetted_perimeter_m, slope, n)


def pipe_full_velocity(diameter_m: float, slope: float, n: float) -> float:
    """Full-bore pipe velocity (per barrel)."""
    geometry = full_pipe_geometry(diameter_m)
    return manning_velocity(geometry.area_m2, geometry.wetted_perimeter_m, slope, n)


def normal_depth(section: Section, flow_m3_s: float, slope: float, n: float) -> float:
    """Water depth that carries ``flow_m3_s`` (bisection), capped at the section depth.

    Returns the full depth when the flow exceeds the capacity or the slope is zero.
    """
    if flow_m3_s <= 0 or slope <= _EPS or n <= _EPS:
        return 0.0
    full = section.depth_m
    full_capacity, _, _ = capacity_at_depth(section, full, slope, n)
    if full_capacity <= flow_m3_s:
        return full
    low, high = 0.0, full
    for _ in range(60):
        mid = (low + high) / 2.0
        capacity, _, _ = capacity_at_depth(section, mid, slope, n)
        if capacity < flow_m3_s:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0

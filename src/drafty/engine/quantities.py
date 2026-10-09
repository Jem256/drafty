"""Rough quantity take-off: excavation, lining area, pipe length and headwalls."""

from __future__ import annotations

from drafty.spec.models import Road

PIPE_LENGTH_ALLOWANCE_M = 1.0


def excavation_volume_m3(section_area_m2: float, length_m: float) -> float:
    return section_area_m2 * length_m


def lining_area_m2(wetted_perimeter_m: float, length_m: float) -> float:
    return wetted_perimeter_m * length_m


def pipe_length_m(road: Road, culvert_length_m: float | None = None) -> float:
    """Pipe length across the road: carriageway plus shoulders plus an allowance."""
    if culvert_length_m is not None:
        return culvert_length_m
    return (
        road.carriageway_width_m
        + road.shoulder_width_m.left
        + road.shoulder_width_m.right
        + PIPE_LENGTH_ALLOWANCE_M
    )


def headwall_count(culvert_count: int) -> int:
    """Two headwalls per culvert."""
    return 2 * culvert_count

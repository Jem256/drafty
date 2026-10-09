"""Road, edge and drain level computation."""

from __future__ import annotations

import pytest

import specs
from drafty.engine import levels


def test_interpolation_midpoint() -> None:
    road = specs.road(300, 1185.0, 1179.0)
    assert levels.road_level_at(road, 150) == pytest.approx(1182.0)


def test_edge_levels_crown_are_symmetric_and_lower() -> None:
    road = specs.road(300, 100.0, 98.0, camber="crown", crossfall_pct=2.5)
    left = levels.road_edge_level(road, 0, "left", 2.5)
    right = levels.road_edge_level(road, 0, "right", 2.5)
    assert left == pytest.approx(right)
    assert left < 100.0


def test_edge_levels_crossfall_right_is_lower() -> None:
    road = specs.road(300, 100.0, 98.0, camber="crossfall", crossfall_pct=2.5)
    left = levels.road_edge_level(road, 0, "left", 2.5)
    right = levels.road_edge_level(road, 0, "right", 2.5)
    assert right < left


def test_drain_invert_follows_road_edge() -> None:
    spec = specs.happy_spec()
    drain = spec.drains[0]
    edge = levels.road_edge_level(spec.road, 0, drain.side, 2.5)
    invert = levels.drain_invert_at(spec.road, drain, 0, 2.5)
    assert invert == pytest.approx(edge - drain.section.depth_m)


def test_drain_gradient_from_road_fall() -> None:
    spec = specs.happy_spec()
    drain = spec.drains[0]
    assert levels.drain_gradient(spec.road, drain, 2.5) == pytest.approx(0.02)

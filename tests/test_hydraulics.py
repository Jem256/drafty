"""Hydraulics checked against stated textbook-style worked numbers."""

from __future__ import annotations

import pytest

from drafty.engine import hydraulics
from drafty.spec.models import Section


def test_rectangular_capacity_and_velocity() -> None:
    # b=0.6 m, d=0.6 m, S=0.01, n=0.015 -> A=0.36 m2, P=1.8 m, Q=0.821 m3/s, V=2.28 m/s
    section = Section(shape="rectangular", bottom_width_m=0.6, depth_m=0.6)
    capacity, velocity, geometry = hydraulics.capacity_at_depth(section, 0.6, 0.01, 0.015)
    assert geometry.area_m2 == pytest.approx(0.36)
    assert geometry.wetted_perimeter_m == pytest.approx(1.8)
    assert capacity == pytest.approx(0.8208, rel=1e-3)
    assert velocity == pytest.approx(2.280, rel=1e-3)


def test_trapezoidal_capacity() -> None:
    # b=0.45 m, d=0.6 m, z=0.5, S=0.01, n=0.015 -> A=0.45 m2, Q=1.194 m3/s
    section = Section(shape="trapezoidal", bottom_width_m=0.45, depth_m=0.6, side_slope_h_per_v=0.5)
    capacity, _, geometry = hydraulics.capacity_at_depth(section, 0.6, 0.01, 0.015)
    assert geometry.area_m2 == pytest.approx(0.45)
    assert geometry.wetted_perimeter_m == pytest.approx(1.7916, rel=1e-3)
    assert capacity == pytest.approx(1.194, rel=1e-2)


def test_v_section_capacity() -> None:
    # z=2, d=0.5 m, S=0.02, n=0.015 -> A=0.5 m2, Q=1.736 m3/s
    section = Section(shape="v", bottom_width_m=0.0, depth_m=0.5, side_slope_h_per_v=2.0)
    capacity, _, geometry = hydraulics.capacity_at_depth(section, 0.5, 0.02, 0.015)
    assert geometry.area_m2 == pytest.approx(0.5)
    assert capacity == pytest.approx(1.736, rel=1e-2)


def test_pipe_full_capacity() -> None:
    # D=0.6 m, S=0.01, n=0.015 -> Q=0.532 m3/s
    assert hydraulics.pipe_full_capacity(0.6, 0.01, 0.015) == pytest.approx(0.5321, rel=1e-2)


def test_zero_slope_gives_zero_capacity() -> None:
    section = Section(shape="rectangular", bottom_width_m=0.6, depth_m=0.6)
    capacity, velocity, _ = hydraulics.capacity_at_depth(section, 0.6, 0.0, 0.015)
    assert capacity == 0.0
    assert velocity == 0.0


def test_normal_depth_recovers_flow() -> None:
    section = Section(shape="rectangular", bottom_width_m=0.6, depth_m=0.6)
    depth = hydraulics.normal_depth(section, 0.5, 0.01, 0.015)
    capacity, _, _ = hydraulics.capacity_at_depth(section, depth, 0.01, 0.015)
    assert capacity == pytest.approx(0.5, rel=1e-2)

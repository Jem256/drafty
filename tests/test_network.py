"""Flow network accumulation and cycle detection."""

from __future__ import annotations

import pytest

import specs
from drafty.engine import network
from drafty.spec.models import Outlet


def test_accumulation_with_culvert_crossing() -> None:
    spec = specs.example_spec(with_data=True)
    flows, warnings = network.accumulate_flows(spec, {"D-L1": 0.3, "D-R1": 0.3})
    assert warnings == []
    assert flows["D-R1"] == pytest.approx(0.3)
    assert flows["C-01"] == pytest.approx(0.3)
    assert flows["D-L1"] == pytest.approx(0.6)


def test_cycle_detected() -> None:
    spec = specs.happy_spec()
    spec.drains[0].outlet = Outlet(type="drain", ref="D-R1")
    spec.drains[1].outlet = Outlet(type="drain", ref="D-L1")
    flows, warnings = network.accumulate_flows(spec, {})
    assert flows == {}
    assert warnings and "cycle" in warnings[0]


def test_reaches_outlet() -> None:
    spec = specs.happy_spec()
    assert network.reaches_outlet(spec, "D-L1") is True


def test_cycle_does_not_reach_outlet() -> None:
    spec = specs.happy_spec()
    spec.drains[0].outlet = Outlet(type="drain", ref="D-R1")
    spec.drains[1].outlet = Outlet(type="drain", ref="D-L1")
    assert network.reaches_outlet(spec, "D-L1") is False

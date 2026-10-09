"""Rational-method flow."""

from __future__ import annotations

import pytest

from drafty.engine.hydrology import rational_flow_m3_s


def test_rational_flow() -> None:
    # C=0.9, i=100 mm/h, A=1.2 ha -> Q=0.3 m3/s
    assert rational_flow_m3_s(0.9, 100.0, 1.2) == pytest.approx(0.3)

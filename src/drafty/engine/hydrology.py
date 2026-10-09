"""Rational-method peak flows.

``Q = C * i * A / 360`` with Q in m^3/s, C the runoff coefficient, i the intensity in mm/h and A the
catchment area in ha. Intensity and return period come from the user or config, never the model.
"""

from __future__ import annotations


def rational_flow_m3_s(
    runoff_coefficient: float, intensity_mm_per_hr: float, area_ha: float
) -> float:
    """Peak flow by the rational method."""
    return runoff_coefficient * intensity_mm_per_hr * area_ha / 360.0

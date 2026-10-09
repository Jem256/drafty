"""Acceptance tests against the owner's three hand calculations.

The Phase 2 exit criterion is that the engine matches three hand-calculated briefs supplied by the
owner. This test is skipped until those numbers exist. Do not invent them.
"""

from __future__ import annotations

import pytest


def test_hand_calculated_briefs_pending() -> None:
    pytest.skip("owner must supply 3 hand-calculated briefs (Phase 2 exit criterion)")

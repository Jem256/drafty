"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from drafty.engine.standards import Standards

FIXTURE_STANDARDS = Path(__file__).parent / "fixtures" / "test_standards.yaml"


@pytest.fixture
def standards() -> Standards:
    return Standards.load(FIXTURE_STANDARDS)

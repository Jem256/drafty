"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from drafty.agent.llm import ModelsConfig
from drafty.engine.standards import Standards

FIXTURE_STANDARDS = Path(__file__).parent / "fixtures" / "test_standards.yaml"
FIXTURE_MODELS = Path(__file__).parent / "fixtures" / "test_models.yaml"


@pytest.fixture
def standards() -> Standards:
    return Standards.load(FIXTURE_STANDARDS)


@pytest.fixture
def models_config() -> ModelsConfig:
    return ModelsConfig.load(FIXTURE_MODELS)

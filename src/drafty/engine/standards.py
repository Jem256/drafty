"""Standards loader.

Reads thresholds from a standards YAML (production: ``config/standards.yaml``; tests: the fixture).
Every value carries ``{value, source, verified}``. A missing or null value returns ``None`` and
records a warning; an unverified value returns the value but records a warning. The engine never
guesses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class Standards:
    """A loaded standards file with warning tracking."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self._warnings: list[str] = []

    @classmethod
    def load(cls, path: str | Path) -> Standards:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return cls(data)

    def _node(self, key: str, sub: str | None) -> Any:
        node = self._data.get(key)
        if sub is not None:
            if not isinstance(node, dict):
                return None
            node = node.get(sub)
        return node

    def get(self, key: str, sub: str | None = None) -> tuple[float | None, bool, str]:
        """Return ``(value, verified, source)``, warning on missing or unverified values."""
        label = f"{key}.{sub}" if sub else key
        node = self._node(key, sub)
        if node is None:
            self._warnings.append(f"standards value '{label}' is missing")
            return (None, False, "")
        if isinstance(node, dict):
            value = node.get("value")
            verified = bool(node.get("verified", False))
            source = str(node.get("source") or "")
        else:
            value = node
            verified = False
            source = ""
        if value is None:
            self._warnings.append(f"standards value '{label}' is not set")
            return (None, False, source)
        if not verified:
            self._warnings.append(
                f"standards value '{label}' is unverified (source: {source or 'none'})"
            )
        return (float(value), verified, source)

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

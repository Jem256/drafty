"""Tests for the Conventional Commits validator in scripts/commit_msg.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "commit_msg.py"


def run_validator(message: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text(message, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(message_file)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "message",
    [
        "feat: add rational method flow calculation",
        "fix(engine): correct trapezoidal wetted perimeter",
        "chore(deps): bump pydantic to 2.8",
        "feat(api)!: change run response shape",
        "docs: explain standards verification",
        "revert: undo drainage split",
        "feat: add drain\n\nA longer body that explains the change in more detail.",
    ],
)
def test_valid_messages(message: str, tmp_path: Path) -> None:
    result = run_validator(message, tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "message",
    [
        "Phase 0: scaffold repo",
        "feat add drain without colon",
        "added a new feature",
        "feat(Engine): scope must be lower case",
        "FEAT: type must be lower case",
        "feat: subject ends with a full stop.",
        "wip: not an allowed type",
        "feat: ",
    ],
)
def test_invalid_messages(message: str, tmp_path: Path) -> None:
    result = run_validator(message, tmp_path)
    assert result.returncode == 1, result.stdout


def test_merge_commit_is_ignored(tmp_path: Path) -> None:
    assert run_validator("Merge branch 'main' into feature", tmp_path).returncode == 0


def test_body_requires_blank_line(tmp_path: Path) -> None:
    assert run_validator("feat: add thing\nbody without a blank line", tmp_path).returncode == 1


def test_header_length_limit(tmp_path: Path) -> None:
    assert run_validator("feat: " + "x" * 100, tmp_path).returncode == 1


def test_comments_are_ignored(tmp_path: Path) -> None:
    message = "feat: add thing\n# Please enter the commit message\n#\n# On branch main"
    assert run_validator(message, tmp_path).returncode == 0

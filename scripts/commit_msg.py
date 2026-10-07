"""Validate a commit message against the Conventional Commits structure used by the polar project.

Rules mirror ``@commitlint/config-conventional`` (polar's ``.commitlintrc``):

- header format ``type(scope)!: subject`` (scope and ``!`` optional)
- ``type`` is one of the allowed types, lower case
- ``scope``, when present, is lower case
- ``subject`` is non-empty and does not end with a full stop
- header is at most 100 characters; body lines are at most 100 characters
- the body, if any, is preceded by a blank line

Merge, revert, ``fixup!``/``squash!`` and ``chore(release)`` commits are ignored.

Usage::

    python scripts/commit_msg.py <path-to-COMMIT_EDITMSG>   # git commit-msg hook
    python scripts/commit_msg.py --range <rev-range>        # CI: validate every commit in range
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TYPES = (
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
)
HEADER_MAX = 100
BODY_MAX = 100

HEADER_RE = re.compile(
    r"^(?P<type>[A-Za-z]+)"
    r"(?:\((?P<scope>[^()]+)\))?"
    r"(?P<breaking>!)?"
    r": (?P<subject>.+)$"
)
IGNORE_RE = re.compile(r"^(Merge |Revert |fixup! |squash! |chore\(release\))")


def check_message(message: str) -> list[str]:
    """Return a list of human-readable problems, empty when the message is valid."""
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return ["empty commit message"]

    header = lines[0]
    if IGNORE_RE.match(header):
        return []

    match = HEADER_RE.match(header)
    if not match:
        return [f"header must be 'type(scope): subject', got {header!r}"]

    commit_type = match.group("type")
    scope = match.group("scope")
    subject = match.group("subject")
    errors: list[str] = []

    if commit_type != commit_type.lower() or commit_type not in TYPES:
        errors.append(f"type {commit_type!r} must be lower case and one of: {', '.join(TYPES)}")
    if scope is not None and scope != scope.lower():
        errors.append(f"scope {scope!r} must be lower case")
    if not subject.strip():
        errors.append("subject must not be empty")
    elif subject.rstrip().endswith("."):
        errors.append("subject must not end with a full stop")
    if len(header) > HEADER_MAX:
        errors.append(f"header is {len(header)} characters; the maximum is {HEADER_MAX}")
    if len(lines) > 1 and lines[1] != "":
        errors.append("body must be preceded by a blank line")
    for number, line in enumerate(lines[1:], start=2):
        if len(line) > BODY_MAX:
            errors.append(f"line {number} is {len(line)} characters; the maximum is {BODY_MAX}")
    return errors


def _report(label: str, errors: list[str]) -> None:
    print(f"commit message rejected: {label}", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    print("expected: type(scope): subject", file=sys.stderr)
    print(f"types: {', '.join(TYPES)}", file=sys.stderr)


def _check_file(path: Path) -> int:
    errors = check_message(path.read_text(encoding="utf-8"))
    if errors:
        _report(str(path), errors)
        return 1
    return 0


def _check_range(rev_range: str) -> int:
    output = subprocess.run(
        ["git", "log", "--format=%H%x00%B%x01", rev_range],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    failures = 0
    for record in output.split("\x01"):
        record = record.strip("\n")
        if not record:
            continue
        sha, _, body = record.partition("\x00")
        errors = check_message(body)
        if errors:
            failures += 1
            first_line = body.splitlines()[0] if body.splitlines() else ""
            _report(f"{sha[:12]} {first_line!r}", errors)

    if failures:
        print(f"{failures} commit message(s) failed.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--range":
        return _check_range(argv[2])
    if len(argv) == 2:
        return _check_file(Path(argv[1]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

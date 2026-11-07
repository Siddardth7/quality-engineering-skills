"""
conftest.py
Shared FMEA test fixtures for the quality_core.schema suites, so the canonical
"valid row" and its factories are defined once instead of copied across
test_schema and test_relational.

Also carries the end-of-session citation-verification summary (see the bottom of this
file) — reporting only, it never changes an outcome.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Callable
from fnmatch import fnmatch
from pathlib import PurePath
from typing import Any

import pytest
from quality_core.schema import FMEADataset, FMEARow

# Make this directory importable so the citation-audit test modules can share the
# non-collected `_citation_audit` helper regardless of pytest's import mode / rootdir.
sys.path.insert(0, os.path.dirname(__file__))

VALID_ROW: dict[str, object] = {
    "ID": 1,
    "Process_Step": "Mix",
    "Component": "Resin",
    "Function": "Bond layers",
    "Failure_Mode": "Incomplete cure",
    "Effect": "Delamination",
    "Severity": 8,
    "Cause": "Low temperature",
    "Occurrence": 4,
    "Current_Control": "Oven thermocouple",
    "Detection": 5,
}


@pytest.fixture
def make_row() -> Callable[..., FMEARow]:
    """Factory: build a valid FMEARow, applying any field overrides."""

    def _make(**overrides: object) -> FMEARow:
        return FMEARow(**{**VALID_ROW, **overrides})  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_dataset() -> Callable[..., FMEADataset]:
    """Factory: build an FMEADataset from per-row override dicts."""

    def _make(*rows: dict[str, object]) -> FMEADataset:
        return FMEADataset(rows=[FMEARow(**{**VALID_ROW, **r}) for r in rows])  # type: ignore[arg-type]

    return _make


# --- Citation-verification session summary (#241) -------------------------------------
#
# The citation gate used to be silent about how much of itself never ran: a machine with no
# licensed manuals skipped hundreds of row checks and still printed a green suite. This hook
# reports the split every session, and splits the *unverified* rows into two buckets that
# must never look alike:
#
#   - "structurally unverifiable (PDF-only)" — the domain's declared manuals are present but
#     are PDFs, which cannot be line-matched (COPQ). Nothing an operator can configure fixes
#     this; only extracting a `.md` text layer does.
#   - "missing config" — a `*_MANUAL_PATH` is unset or wrong. An operator CAN fix this, and
#     under strict mode these fail rather than skip.
#
# Reporting only: this hook never changes an outcome.

_CITATION_MODULE_GLOB = "test_*citation*.py"


def _is_citation_report(report: object) -> bool:
    """True for a report belonging to a `test_*citation*.py` module."""
    nodeid = str(getattr(report, "nodeid", ""))
    return fnmatch(PurePath(nodeid.split("::")[0]).name, _CITATION_MODULE_GLOB)


def _skip_reason(report: object) -> str:
    """The human-readable reason of a skipped report (`(path, lineno, reason)` triple)."""
    longrepr = getattr(report, "longrepr", "")
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2])
    return str(longrepr)


def pytest_terminal_summary(terminalreporter: Any) -> None:
    """Print the citation verified/unverified split, and mirror it into the CI job summary."""
    import _citation_audit as ca  # local import: sys.path is extended above, not at import time

    stats = terminalreporter.stats
    passed = [
        r
        for r in stats.get("passed", [])
        if _is_citation_report(r) and getattr(r, "when", "call") == "call"
    ]
    skipped = [r for r in stats.get("skipped", []) if _is_citation_report(r)]
    # A strict-mode failure raised inside a module-scoped fixture lands in "error", not
    # "failed" — both mean "this row was never verified", so count them together.
    failed = [
        r for r in stats.get("failed", []) + stats.get("error", []) if _is_citation_report(r)
    ]
    total = len(passed) + len(skipped) + len(failed)
    if not total:
        return

    pdf_only = 0
    missing_config = 0
    for report in skipped:
        reason = _skip_reason(report)
        if ca.PDF_ONLY_SKIP_MARKER in reason:
            pdf_only += 1
        elif ca.MISSING_MANUAL_SKIP_MARKER in reason:
            missing_config += 1
    other = len(skipped) - pdf_only - missing_config

    lines = [
        f"CITATION VERIFICATION: {len(passed)} verified, {len(skipped)} unverified (of {total})",
        f"  structurally unverifiable (PDF-only): {pdf_only}",
        f"  missing config (*_MANUAL_PATH unset or wrong): {missing_config}",
    ]
    if other:
        lines.append(f"  unclassified skips: {other}")
    if failed:
        lines.append(f"  FAILED/ERRORED (unverified under strict mode): {len(failed)}")
    for line in lines:
        terminalreporter.write_line(line)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        body = "\n".join(f"- {line.strip()}" for line in lines[1:])
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(
                "### Citation verification\n\n"
                f"**{len(passed)} verified, {len(skipped)} unverified** (of {total})\n\n"
                f"{body}\n\n"
            )

"""Behavioural proof that the /8d skill's closure precondition guards a real hazard.

The `/8d` skill (``skills/8d-problem-solving/SKILL.md``) forbids attempting the D8 -> CLOSED
transition while ``validate_8d`` reports ``closeable: false``. That prohibition is only worth
writing if the engine actually permits the transition -- prose guarding nothing is the failure
mode tracked in #220. This module pins the hazard so the guard cannot go stale silently: if a
future engine change makes ``advance_8d`` refuse this transition on its own, this test fails and
whoever made that change is told to revisit the skill's Step 3.

Raised as a blocking [P1] on PR #236 (E12/#215) and reproduced end-to-end before the fix.
"""

from __future__ import annotations

import copy
from typing import Any

from quality_core.canvas.eight_d import SAMPLE_EIGHT_D_REPORT
from quality_mcp.tools.eight_d import advance_8d, validate_8d


def _report_closeable_false_at_d8() -> dict[str, Any]:
    """A D8 report the whole-report gate rejects for a reason that belongs to an earlier step."""
    report = copy.deepcopy(SAMPLE_EIGHT_D_REPORT)
    report["d3"]["linked_ncr_validation"] = {
        "is_valid": False,
        "record_count": 2,
        "findings": ["NCR linkage recorded invalid."],
    }
    return report


def test_engine_permits_closing_a_report_the_whole_report_gate_rejects() -> None:
    """advance_8d(CLOSED) returns ADVANCED while validate_8d says closeable is False.

    This is correct engine behaviour, not a defect: ``advance_8d`` evaluates only the gates of the
    transition attempted, and ``LINKED_NCR_INVALID`` (``PDD-8D-008``) gates D3 -> D4, not
    D8 -> CLOSED. It is precisely why the skill needs a precondition rather than a disclaimer.
    """
    report = _report_closeable_false_at_d8()

    before = validate_8d(report=report)
    assert before["state"] == "D8"
    assert before["closeable"] is False
    assert before["d8"]["closeable"] is True, "the two closeable flags must disagree here"
    assert [(r["code"], r["rule_id"]) for r in before["gate_reasons"]] == [
        ("LINKED_NCR_INVALID", "PDD-8D-008")
    ]

    advanced = advance_8d(report=report, target="CLOSED")
    assert advanced["verdict"] == "ADVANCED", (
        "the engine still permits this transition; if this now BLOCKS, revisit the closure "
        "precondition in skills/8d-problem-solving/SKILL.md Step 3 -- the guard may be redundant"
    )
    assert advanced["state"] == "CLOSED"
    assert advanced["reasons"] == []

    after = validate_8d(report=advanced["report"])
    assert after["state"] == "CLOSED"
    assert after["closeable"] is False, (
        "the closed report is still not closeable -- this is the hazard the skill's precondition "
        "exists to prevent an agent from creating"
    )

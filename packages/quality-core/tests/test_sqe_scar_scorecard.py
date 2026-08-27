"""
test_sqe_scar_scorecard.py
Worked-benchmark SCAR scenarios for quality_core.sqe.scar.

Mirrors test_sqe_otif_scorecard.py's "hand-computed benchmark" role (NOT the vendor scorecard
engine from #118). Each benchmark drives a full generate_scar call with real sub-engine evidence,
then flips exactly one input and asserts the OPPOSITE verdict — the negative-control discipline.

Standards references for the benchmark chains (per the citation trail the module carries):
- Systemic root-cause requirement: AIAG CQI-20 Effective Problem Solving (2nd Ed, 2018) D4 /
  Ford Global 8D D4 ("root of the root cause") — RULE-SQE-007.
- Corrective action on the system, not the part: Ford Global 8D D5 — RULE-SQE-008.
- Blame-terminal / operator-error rejection: ASQ Quality Toolbox & Ford Global 8D, enforced by
  quality_core.rca.five_why (BLAME_TERMINAL_OPERATOR_ERROR).
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from quality_core.sqe.scar import generate_scar
from quality_core.sqe.schema import SCARRequest

ISSUED = datetime.date(2026, 1, 1)
DUE = datetime.date(2026, 2, 1)

# A fully valid, systemic 5-Why chain.
SYSTEMIC_CHAIN: list[dict[str, Any]] = [
    {"step_number": 1, "why": "Why did the motor overheat?", "because": "The cooling fan stopped turning."},
    {"step_number": 2, "why": "Why did the cooling fan stop?", "because": "The electrical fuse blew from an incorrect rating."},
    {"step_number": 3, "why": "Why was an incorrect rating installed?", "because": "The maintenance work instruction lacked a fuse specification table."},
]
SYSTEMIC_ROOT_CAUSE = "The maintenance work instruction lacked a fuse specification table."

# Same scenario, terminal blame instead of a systemic cause.
BLAME_CHAIN: list[dict[str, Any]] = [
    {"step_number": 1, "why": "Why did the motor overheat?", "because": "The cooling fan stopped turning."},
    {"step_number": 2, "why": "Why did the cooling fan stop?", "because": "The operator forgot to switch it on."},
]

VALID_NCR: list[dict[str, Any]] = [
    {
        "part_lot_id": "LOT-77",
        "defect_description": "overheated winding",
        "requirement_violated": "max temp 90C",
        "quantity_affected": 12,
        "detection_point": "final test",
    }
]

# Hand-computed COPQ: 40 scrap * $30 + $300 direct sort = $1500.00.
COST_ITEMS: list[dict[str, Any]] = [
    {"category": "InternalFailure", "description": "scrap", "scrap_qty": 40, "unit_cost": 30.0},
    {"category": "InternalFailure", "description": "sort", "direct_cost": 300.0},
]
COST_TOTAL = 1500.0


def _request(**overrides: Any) -> SCARRequest:
    base: dict[str, Any] = {
        "supplier_id": "SUP-BENCH",
        "issue_description": "motor overheat",
        "scar_id": "SCAR-BENCH-1",
        "date_issued": ISSUED,
        "due_date": DUE,
    }
    base.update(overrides)
    return SCARRequest(**base)


# ===========================================================================
# Benchmark 1 — everything valid -> CLOSABLE
# ===========================================================================


def test_full_valid_scenario_is_closable() -> None:
    r = generate_scar(
        _request(),
        linked_ncr_evidence=VALID_NCR,
        supplier_root_cause_evidence=SYSTEMIC_CHAIN,
        cost_impact_evidence=COST_ITEMS,
        verification_of_effectiveness="Effectiveness audit of 3 subsequent lots passed.",
    )
    assert r.status == "CLOSABLE"
    assert r.reason is None
    assert r.linkage["linked_ncr"].verdict == "EVIDENCE_VALID"
    assert r.linkage["supplier_root_cause"].verdict == "EVIDENCE_VALID"
    assert r.linkage["cost_impact"].verdict == "EVIDENCE_VALID"
    assert r.root_cause == SYSTEMIC_ROOT_CAUSE
    assert len(r.sections) == 3
    assert r.linkage["cost_impact"].raw_result is not None
    assert r.linkage["cost_impact"].raw_result["total_copq"] == COST_TOTAL


# ===========================================================================
# Benchmark 2 — flip ONE input (systemic -> blame) -> RESPONSE_REJECTED
# ===========================================================================


def test_flip_root_cause_to_blame_flips_verdict() -> None:
    r = generate_scar(
        _request(),
        linked_ncr_evidence=VALID_NCR,
        supplier_root_cause_evidence=BLAME_CHAIN,  # the single flipped input
        cost_impact_evidence=COST_ITEMS,
        verification_of_effectiveness="Effectiveness audit of 3 subsequent lots passed.",
    )
    assert r.status == "RESPONSE_REJECTED"
    assert r.status != "CLOSABLE"
    assert r.linkage["supplier_root_cause"].verdict == "EVIDENCE_INVALID"
    assert any(
        f.startswith("BLAME_TERMINAL_OPERATOR_ERROR: ")
        for f in r.linkage["supplier_root_cause"].findings
    )


# ===========================================================================
# Benchmark 3 — linked_ncr_id referenced but no evidence -> still CLOSABLE
# ===========================================================================


def test_unsupplied_but_referenced_ncr_is_not_verdict_affecting() -> None:
    r = generate_scar(
        _request(linked_ncr_id="NCR-REF-1"),
        linked_ncr_evidence=None,  # id present, evidence absent
        supplier_root_cause_evidence=SYSTEMIC_CHAIN,
        cost_impact_evidence=COST_ITEMS,
        verification_of_effectiveness="Verified across the next production run.",
    )
    assert r.status == "CLOSABLE"
    assert r.linkage["linked_ncr"].verdict == "EVIDENCE_NOT_SUPPLIED"
    # The unbacked id still surfaces as a warning, but never changes the verdict.
    assert any("NCR-REF-1" in w for w in r.warnings)


def test_flip_referenced_ncr_to_invalid_breaks_closable() -> None:
    # Opposite direction of benchmark 3: an *invalid* linked NCR does move the verdict.
    invalid_ncr = [
        {
            "part_lot_id": "LOT-77",
            "defect_description": "overheated winding",
            "requirement_violated": "max temp 90C",
            "quantity_affected": -1,  # out of range -> EVIDENCE_INVALID
            "detection_point": "final test",
        }
    ]
    r = generate_scar(
        _request(linked_ncr_id="NCR-REF-1"),
        linked_ncr_evidence=invalid_ncr,
        supplier_root_cause_evidence=SYSTEMIC_CHAIN,
        cost_impact_evidence=COST_ITEMS,
        verification_of_effectiveness="Verified across the next production run.",
    )
    assert r.linkage["linked_ncr"].verdict == "EVIDENCE_INVALID"
    assert r.status != "CLOSABLE"
    assert r.status == "AWAITING_SUPPLIER_RESPONSE"


# ===========================================================================
# Deferred vendor_scorecard slot — LINKAGE_NOT_AVAILABLE regardless of inputs
# ===========================================================================


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"linked_ncr_evidence": VALID_NCR},
        {"supplier_root_cause_evidence": SYSTEMIC_CHAIN},
        {
            "linked_ncr_evidence": VALID_NCR,
            "supplier_root_cause_evidence": SYSTEMIC_CHAIN,
            "cost_impact_evidence": COST_ITEMS,
            "verification_of_effectiveness": "ok",
        },
    ],
)
def test_vendor_scorecard_slot_always_deferred(kwargs: dict[str, Any]) -> None:
    r = generate_scar(_request(), **kwargs)
    slot = r.linkage["vendor_scorecard"]
    assert slot.verdict == "LINKAGE_NOT_AVAILABLE"
    assert slot.engine is None

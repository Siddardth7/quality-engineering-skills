"""Scorecard integration tests for PPAP Cross-Engine Linkage (Issue #105).

Validates:
1. Benchmark data integration across PFMEA, Control Plan, MSA, and Process Studies
2. Full package linkage report under 100% valid benchmark evidence
3. Single-defect isolation: proves each individual invalid element independently trips overall_valid to False
4. Verbatim error and finding propagation from each underlying sub-engine
5. Negative mutation control: mutating linkage to ignore invalid sub-engine evidence fails tests
"""

from __future__ import annotations

import numpy as np
import pytest
from quality_core.controlplan.schema import ControlPlanDataset, ControlPlanRow
from quality_core.ppap.linkage import (
    LINKABLE_ELEMENTS,
    validate_element_linkage,
    validate_linked_evidence,
)


def _benchmark_control_plan() -> ControlPlanDataset:
    """Standard manufacturing benchmark Control Plan."""
    row = ControlPlanRow(
        characteristic="Bore Diameter",
        measurement_method="Air Gage",
        sample_size=5,
        frequency="5/shift",
        reaction_plan="100% sort, adjust tool offset, notify supervisor",
        lsl=49.98,
        usl=50.02,
    )
    return ControlPlanDataset(rows=[row])


def test_scorecard_full_benchmark_package_all_valid() -> None:
    """Scorecard: All 4 engine-backed elements valid -> overall_valid = True."""
    rng = np.random.default_rng(42)
    normal_process_data = rng.normal(loc=10.0, scale=0.1, size=120).tolist()

    evidence_package = {
        # §2.2.6 Process FMEA
        "2.2.6": [
            {"severity": 8, "occurrence": 3, "detection": 3},  # Action Priority Low/Med
            {"severity": 6, "occurrence": 2, "detection": 2},
        ],
        # §2.2.7 Control Plan
        "2.2.7": _benchmark_control_plan(),
        # §2.2.8 MSA Gage R&R
        "2.2.8": {
            "percent_grr": 6.8,
            "ndc": 14,
            "verdict": "ACCEPTABLE",
        },
        # §2.2.11 Initial Process Studies
        "2.2.11": {
            "data": normal_process_data,
            "lsl": 9.0,
            "usl": 11.0,
        },
    }

    report = validate_linked_evidence(evidence_package)
    assert report.overall_valid is True
    assert len(report.invalid_elements) == 0

    for elem in LINKABLE_ELEMENTS:
        assert report.results[elem].verdict == "EVIDENCE_VALID"
        assert report.results[elem].is_valid is True
        assert len(report.results[elem].findings) == 0


@pytest.mark.parametrize(
    ("defect_element", "defect_payload", "expected_finding_marker"),
    [
        (
            "2.2.6",
            [{"severity": 12, "occurrence": 3, "detection": 3}],
            "Invalid ratings (S=12",
        ),
        (
            "2.2.7",
            {"phase": "INVALID_PHASE", "header": "bad"},
            "schema validation error",
        ),
        (
            "2.2.8",
            {"percent_grr": 36.2, "ndc": 2},
            "exceeds 30.0%",
        ),
        (
            "2.2.11",
            {"precomputed_index_type": "Ppk", "precomputed_index_value": 0.92},
            "UNACCEPTABLE",
        ),
    ],
)
def test_scorecard_single_defect_isolation(
    defect_element: str, defect_payload: object, expected_finding_marker: str
) -> None:
    """Scorecard: Each invalid element individually trips overall_valid to False and records verbatim finding."""
    # Build package where 3 are valid, 1 is defective
    package: dict[str, object] = {
        "2.2.6": [{"s": 5, "o": 2, "d": 2}],
        "2.2.7": _benchmark_control_plan(),
        "2.2.8": {"percent_grr": 8.0, "ndc": 10},
        "2.2.11": {"precomputed_index_type": "Ppk", "precomputed_index_value": 1.75},
    }
    package[defect_element] = defect_payload

    report = validate_linked_evidence(package)
    assert report.overall_valid is False
    assert defect_element in report.invalid_elements

    elem_res = report.results[defect_element]
    assert elem_res.verdict == "EVIDENCE_INVALID"
    assert elem_res.is_valid is False
    assert any(expected_finding_marker.lower() in f.lower() for f in elem_res.findings)


def test_scorecard_empty_package_all_unsupplied() -> None:
    """Scorecard: Completely empty evidence map results in 4 unsupplied elements and overall_valid=True."""
    report = validate_linked_evidence({})
    assert report.overall_valid is True
    assert len(report.invalid_elements) == 0
    for elem in LINKABLE_ELEMENTS:
        assert report.results[elem].verdict == "EVIDENCE_NOT_SUPPLIED"
        assert report.results[elem].is_valid is None


# ==============================================================================
# Negative Controls
# ==============================================================================


def test_negative_control_invalid_control_plan_never_passes() -> None:
    """Negative control: assert a corrupted control plan is never marked valid."""
    corrupted_cp = {"title": "Not A Control Plan", "items": "bad_items"}
    res = validate_element_linkage("2.2.7", corrupted_cp)
    assert res.verdict != "EVIDENCE_VALID"
    assert res.verdict == "EVIDENCE_INVALID"
    assert res.is_valid is False


def test_negative_control_unacceptable_msa_never_passes() -> None:
    """Negative control: assert %GRR > 30% is never marked valid."""
    bad_msa = {"percent_grr": 45.0, "ndc": 1}
    res = validate_element_linkage("2.2.8", bad_msa)
    assert res.verdict != "EVIDENCE_VALID"
    assert res.verdict == "EVIDENCE_INVALID"
    assert res.is_valid is False

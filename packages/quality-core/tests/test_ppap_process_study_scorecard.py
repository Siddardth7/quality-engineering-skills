"""Scorecard validation for AIAG PPAP 4th Edition §2.2.11 Initial Process Study Capability Gate.

Validates:
1. Exact boundary values around 1.67 (1.670001 -> ACCEPTABLE vs 1.670000 -> POTENTIALLY_ACCEPTABLE)
2. Exact boundary values around 1.33 (1.330000 -> POTENTIALLY_ACCEPTABLE vs 1.329999 -> UNACCEPTABLE)
3. Unilateral tolerance limits (upper-only vs lower-only specifications)
4. Verbatim equality of standard-mandated action texts across all verdicts
5. Custom threshold overrides with non-default acceptance targets
6. Negative control: boundary inversion detection
"""

from __future__ import annotations

import numpy as np
from quality_core.ppap.process_study import (
    ACTION_BETWEEN_1_33_AND_1_67,
    ACTION_GREATER_THAN_1_67,
    ACTION_LESS_THAN_1_33,
    assess_initial_process_study,
)

_RNG = np.random.default_rng(42)
_NORMAL_DATA_120 = _RNG.normal(loc=10.0, scale=0.1, size=120).tolist()


# ==============================================================================
# Exact Threshold Boundaries (§2.2.11.3 Table 2.2.11.3)
# ==============================================================================


def test_scorecard_boundary_above_1_67() -> None:
    """Index > 1.67: 1.670001 must land in GREATER_THAN_1_67 (ACCEPTABLE)."""
    res = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.670001,
    )
    assert res.verdict == "ACCEPTABLE"
    assert res.band == "GREATER_THAN_1_67"
    assert res.required_action == ACTION_GREATER_THAN_1_67


def test_scorecard_boundary_exact_1_67() -> None:
    """Index = 1.67: 1.670000 must land in BETWEEN_1_33_AND_1_67 (POTENTIALLY_ACCEPTABLE)."""
    res = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.670000,
    )
    assert res.verdict == "POTENTIALLY_ACCEPTABLE"
    assert res.band == "BETWEEN_1_33_AND_1_67"
    assert res.required_action == ACTION_BETWEEN_1_33_AND_1_67


def test_scorecard_boundary_exact_1_33() -> None:
    """Index = 1.33: 1.330000 must land in BETWEEN_1_33_AND_1_67 (POTENTIALLY_ACCEPTABLE)."""
    res = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.330000,
    )
    assert res.verdict == "POTENTIALLY_ACCEPTABLE"
    assert res.band == "BETWEEN_1_33_AND_1_67"
    assert res.required_action == ACTION_BETWEEN_1_33_AND_1_67


def test_scorecard_boundary_below_1_33() -> None:
    """Index < 1.33: 1.329999 must land in LESS_THAN_1_33 (UNACCEPTABLE)."""
    res = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.329999,
    )
    assert res.verdict == "UNACCEPTABLE"
    assert res.band == "LESS_THAN_1_33"
    assert res.required_action == ACTION_LESS_THAN_1_33


# ==============================================================================
# Unilateral Tolerance Specifications (§2.2.11.5)
# ==============================================================================


def test_scorecard_unilateral_upper_spec() -> None:
    """Evaluate unilateral upper specification limit (USL only, no LSL)."""
    res = assess_initial_process_study(
        data=_NORMAL_DATA_120,
        lsl=None,
        usl=10.6,
    )
    assert res.verdict == "ACCEPTABLE"
    assert res.index_type == "Ppk"
    assert res.index_value is not None and res.index_value > 1.67


def test_scorecard_unilateral_lower_spec() -> None:
    """Evaluate unilateral lower specification limit (LSL only, no USL)."""
    res = assess_initial_process_study(
        data=_NORMAL_DATA_120,
        lsl=9.4,
        usl=None,
    )
    assert res.verdict == "ACCEPTABLE"
    assert res.index_type == "Ppk"
    assert res.index_value is not None and res.index_value > 1.67


# ==============================================================================
# Custom Threshold Overrides
# ==============================================================================


def test_scorecard_custom_threshold_overrides() -> None:
    """Verify custom customer-specific capability thresholds."""
    # Stricter customer requirement: Capable > 2.00, Potentially Capable >= 1.67
    res = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.85,
        custom_threshold_capable=2.00,
        custom_threshold_potentially_capable=1.67,
    )
    assert res.verdict == "POTENTIALLY_ACCEPTABLE"
    assert res.band == "BETWEEN_1_33_AND_1_67"


# ==============================================================================
# Negative Controls
# ==============================================================================


def test_negative_control_boundary_inversion() -> None:
    """Negative control: assert inverted thresholds do not pass silently."""
    res_1 = assess_initial_process_study(precomputed_index_type="Ppk", precomputed_index_value=1.68)
    res_2 = assess_initial_process_study(precomputed_index_type="Ppk", precomputed_index_value=1.66)
    assert res_1.verdict != res_2.verdict
    assert res_1.band == "GREATER_THAN_1_67"
    assert res_2.band == "BETWEEN_1_33_AND_1_67"

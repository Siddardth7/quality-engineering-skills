"""Unit tests for AIAG PPAP 4th Edition §2.2.11 Initial Process Study Capability Gate.

Validates:
1. assess_initial_process_study on 1D individuals and 2D subgroups
2. ProcessStudyResult attributes, rationales, citations, and .to_dict()
3. Index selection: Ppk (default initial study) vs Cpk (ongoing stable process)
4. Attribute data guard: reject attribute data, return NOT_APPLICABLE_ATTRIBUTE_DATA with standard action
5. Insufficient sample guard: n < 100 or subgroups < 25 return INDETERMINATE unless customer concurrence
6. Stability gate: out-of-control control-chart signals return INDETERMINATE with named signals
7. Acceptance bands: GREATER_THAN_1_67 (ACCEPTABLE), BETWEEN_1_33_AND_1_67 (POTENTIALLY_ACCEPTABLE), LESS_THAN_1_33 (UNACCEPTABLE)
8. Precomputed metric evaluation path (when data is None)
9. Downward import invariant: ppap imports spc; spc does NOT import ppap
10. Input validation: invalid data dimensions, invalid limits (LSL >= USL, no specs), missing data
11. Negative controls: attribute data mutation, stability bypass mutation, sample threshold mutation
"""

from __future__ import annotations

import sys

import numpy as np
import pytest
from quality_core.ppap.process_study import (
    ACTION_ATTRIBUTE_DATA,
    ACTION_BETWEEN_1_33_AND_1_67,
    ACTION_GREATER_THAN_1_67,
    ACTION_INSUFFICIENT_SAMPLE,
    ACTION_LESS_THAN_1_33,
    ACTION_UNSTABLE,
    assess_initial_process_study,
)

# Deterministic test dataset generation
# 25 subgroups of size 5 = 125 observations (exceeds 100 sample / 25 subgroup minimum)
_RNG = np.random.default_rng(42)
_CAPABLE_DATA_2D = _RNG.normal(loc=10.0, scale=0.1, size=(25, 5)).tolist()
_CAPABLE_DATA_1D = _RNG.normal(loc=10.0, scale=0.1, size=120).tolist()


# ==============================================================================
# Downward Import Invariant
# ==============================================================================


def test_spc_does_not_import_ppap() -> None:
    """Verify downward-only import invariant: spc must never import ppap."""

    for mod_name, mod in sys.modules.items():
        if mod_name.startswith("quality_core.spc.") and mod is not None:
            mod_code = getattr(mod, "__file__", "")
            if mod_code and mod_code.endswith(".py"):
                with open(mod_code, encoding="utf-8") as f:
                    content = f.read()
                assert "quality_core.ppap" not in content, (
                    f"Import violation in {mod_name}: imports quality_core.ppap"
                )


# ==============================================================================
# Attribute Data Guard (§2.2.11.1 Note 2)
# ==============================================================================


def test_attribute_data_guard_rejects_capability() -> None:
    """Verify attribute data returns NOT_APPLICABLE_ATTRIBUTE_DATA with no numeric index."""
    res = assess_initial_process_study(
        data=[0, 1, 0, 0, 2, 0, 1],
        lsl=0.0,
        usl=5.0,
        is_attribute=True,
    )
    assert res.verdict == "NOT_APPLICABLE_ATTRIBUTE_DATA"
    assert res.index_type is None
    assert res.index_value is None
    assert res.band is None
    assert res.is_attribute is True
    assert res.required_action == ACTION_ATTRIBUTE_DATA
    assert "AIAG PPAP 4th Edition §2.2.11.1 Note 2" in res.citations[0]
    assert res.to_dict()["verdict"] == "NOT_APPLICABLE_ATTRIBUTE_DATA"


def test_attribute_data_guard_with_none_data() -> None:
    """Verify attribute data with no data provided still returns NOT_APPLICABLE_ATTRIBUTE_DATA."""
    res = assess_initial_process_study(
        data=None,
        is_attribute=True,
        customer_concurrence=True,
    )
    assert res.verdict == "NOT_APPLICABLE_ATTRIBUTE_DATA"
    assert res.sample_size == 0
    assert res.subgroup_count is None
    assert res.customer_concurrence is True


# ==============================================================================
# Sample Size Adequacy (§2.2.11.1 Note 5, §2.2.11.2)
# ==============================================================================


def test_insufficient_samples_1d_returns_indeterminate() -> None:
    """Verify 1D sample size < 100 returns INDETERMINATE without customer concurrence."""
    small_data = [10.0 + 0.1 * i for i in range(50)]
    res = assess_initial_process_study(data=small_data, lsl=8.0, usl=12.0)
    assert res.verdict == "INDETERMINATE"
    assert res.index_type is None
    assert res.index_value is None
    assert res.band is None
    assert res.sample_size == 50
    assert res.required_action == ACTION_INSUFFICIENT_SAMPLE
    assert "AIAG PPAP 4th Edition §2.2.11.1 Note 5" in res.citations


def test_insufficient_subgroups_2d_returns_indeterminate() -> None:
    """Verify 2D dataset with < 25 subgroups returns INDETERMINATE without customer concurrence."""
    small_subgroups = [
        [10.0, 10.1, 9.9, 10.0, 10.0]
    ] * 20  # 20 subgroups = 100 obs, but < 25 subgroups
    res = assess_initial_process_study(data=small_subgroups, lsl=8.0, usl=12.0)
    assert res.verdict == "INDETERMINATE"
    assert res.subgroup_count == 20
    assert res.required_action == ACTION_INSUFFICIENT_SAMPLE


def test_insufficient_sample_with_customer_concurrence_evaluated() -> None:
    """Verify small sample size IS evaluated when customer_concurrence is True (§2.2.11.1 Note 5)."""
    rng = np.random.default_rng(99)
    small_data = rng.normal(loc=10.0, scale=0.1, size=50).tolist()
    res = assess_initial_process_study(
        data=small_data,
        lsl=9.0,
        usl=11.0,
        customer_concurrence=True,
    )
    assert res.verdict == "ACCEPTABLE"
    assert res.index_type == "Ppk"
    assert res.index_value is not None
    assert res.index_value > 1.67
    assert res.customer_concurrence is True


# ==============================================================================
# Stability Gate (§2.2.11.4)
# ==============================================================================


def test_stability_gate_with_out_of_control_violations() -> None:
    """Verify out-of-control signals trigger INDETERMINATE verdict and ACTION_UNSTABLE."""
    violations = [{"rule": 1, "point": 10, "value": 15.0, "subgroup": 10}]
    res = assess_initial_process_study(
        data=_CAPABLE_DATA_1D,
        lsl=9.0,
        usl=11.0,
        violations=violations,
    )
    assert res.verdict == "INDETERMINATE"
    assert res.stable is False
    assert res.band is None
    assert res.required_action == ACTION_UNSTABLE
    assert res.violations is not None
    assert len(res.violations) == 1
    assert "AIAG PPAP 4th Edition §2.2.11.4" in res.citations[0]


# ==============================================================================
# Acceptance Bands (§2.2.11.3 & §2.2.11.6)
# ==============================================================================


def test_capable_initial_study_ppk_acceptable() -> None:
    """Verify Ppk > 1.67 yields ACCEPTABLE verdict and ACTION_GREATER_THAN_1_67."""
    res = assess_initial_process_study(
        data=_CAPABLE_DATA_1D,
        lsl=9.0,
        usl=11.0,
    )
    assert res.verdict == "ACCEPTABLE"
    assert res.index_type == "Ppk"
    assert res.band == "GREATER_THAN_1_67"
    assert res.index_value is not None and res.index_value > 1.67
    assert res.required_action == ACTION_GREATER_THAN_1_67
    assert "Index > 1.67" in res.citations[0]


def test_ongoing_stable_process_cpk_selected() -> None:
    """Verify is_ongoing_stable_process=True uses Cpk instead of Ppk (§2.2.11.2)."""
    res = assess_initial_process_study(
        data=_CAPABLE_DATA_2D,
        lsl=9.0,
        usl=11.0,
        is_ongoing_stable_process=True,
    )
    assert res.verdict == "ACCEPTABLE"
    assert res.index_type == "Cpk"
    assert res.band == "GREATER_THAN_1_67"
    assert "demonstrated stable historical process" in res.rationales[1]


def test_marginally_capable_potentially_acceptable() -> None:
    """Verify 1.33 <= Ppk <= 1.67 yields POTENTIALLY_ACCEPTABLE."""
    # Scale data so that Ppk lands around 1.45 (USL - Mean) / (3 * 0.23) = 1.0 / 0.69 ≈ 1.45
    rng = np.random.default_rng(123)
    mod_data = rng.normal(loc=10.0, scale=0.23, size=120).tolist()
    res = assess_initial_process_study(
        data=mod_data,
        lsl=9.0,
        usl=11.0,
    )
    assert res.verdict == "POTENTIALLY_ACCEPTABLE"
    assert res.band == "BETWEEN_1_33_AND_1_67"
    assert res.index_value is not None and 1.33 <= res.index_value <= 1.67
    assert res.required_action == ACTION_BETWEEN_1_33_AND_1_67
    assert "1.33 <= Index <= 1.67" in res.citations[0]


def test_incapable_process_unacceptable() -> None:
    """Verify Ppk < 1.33 yields UNACCEPTABLE with 100% inspection / corrective action mandate."""
    # Scale data so that Ppk lands around 0.83 (1.0 / (3 * 0.4) ≈ 0.83)
    rng = np.random.default_rng(456)
    poor_data = rng.normal(loc=10.0, scale=0.4, size=120).tolist()
    res = assess_initial_process_study(
        data=poor_data,
        lsl=9.0,
        usl=11.0,
    )
    assert res.verdict == "UNACCEPTABLE"
    assert res.band == "LESS_THAN_1_33"
    assert res.index_value is not None and res.index_value < 1.33
    assert res.required_action == ACTION_LESS_THAN_1_33
    assert "Index < 1.33" in res.citations[0]
    assert "§2.2.11.6" in res.citations[1]


# ==============================================================================
# Precomputed Metric Path
# ==============================================================================


def test_precomputed_metrics_evaluation() -> None:
    """Verify evaluation from precomputed index values without raw data array."""
    res_acc = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.85,
        precomputed_sample_size=150,
        precomputed_subgroup_count=30,
    )
    assert res_acc.verdict == "ACCEPTABLE"
    assert res_acc.index_type == "Ppk"
    assert res_acc.index_value == 1.85
    assert res_acc.sample_size == 150
    assert res_acc.subgroup_count == 30

    res_pot = assess_initial_process_study(
        precomputed_index_type="Cpk",
        precomputed_index_value=1.50,
    )
    assert res_pot.verdict == "POTENTIALLY_ACCEPTABLE"
    assert res_pot.index_type == "Cpk"
    assert res_pot.index_value == 1.50

    res_unacc = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.10,
    )
    assert res_unacc.verdict == "UNACCEPTABLE"
    assert res_unacc.index_value == 1.10

    res_unstable = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.85,
        violations=[{"rule": 1, "point": 5}],
    )
    assert res_unstable.verdict == "INDETERMINATE"
    assert res_unstable.stable is False


# ==============================================================================
# Input Validation & Errors
# ==============================================================================


def test_missing_data_and_precomputed_raises() -> None:
    """Verify ValueError when neither data nor precomputed values are supplied."""
    with pytest.raises(ValueError, match="Must provide either 'data'"):
        assess_initial_process_study(data=None)


def test_missing_spec_limits_raises() -> None:
    """Verify ValueError when both LSL and USL are None."""
    with pytest.raises(ValueError, match="At least one specification limit"):
        assess_initial_process_study(data=_CAPABLE_DATA_1D, lsl=None, usl=None)


def test_invalid_spec_limits_raises() -> None:
    """Verify ValueError when LSL >= USL."""
    with pytest.raises(ValueError, match="LSL .* must be strictly less than USL"):
        assess_initial_process_study(data=_CAPABLE_DATA_1D, lsl=12.0, usl=10.0)


def test_invalid_data_dimension_raises() -> None:
    """Verify ValueError when data has ndim > 2."""
    data_3d = np.zeros((5, 5, 5)).tolist()
    with pytest.raises(ValueError, match="data must be 1D individual readings or 2D subgroups"):
        assess_initial_process_study(data=data_3d, lsl=8.0, usl=12.0)


# ==============================================================================
# Negative Controls
# ==============================================================================


def test_negative_control_attribute_data_never_computes_ppk() -> None:
    """Negative control: assert attribute data is never assigned a numeric capability index."""
    res = assess_initial_process_study(
        data=[0, 0, 1, 0, 1, 0] * 20,
        lsl=0.0,
        usl=5.0,
        is_attribute=True,
    )
    assert res.verdict != "ACCEPTABLE"
    assert res.verdict != "UNACCEPTABLE"
    assert res.verdict == "NOT_APPLICABLE_ATTRIBUTE_DATA"
    assert res.index_value is None


def test_negative_control_out_of_control_never_acceptable() -> None:
    """Negative control: assert out-of-control process never resolves ACCEPTABLE even with high index."""
    res = assess_initial_process_study(
        data=_CAPABLE_DATA_1D,
        lsl=5.0,
        usl=15.0,
        violations=[{"rule": 1, "point": 2}],
    )
    assert res.verdict != "ACCEPTABLE"
    assert res.verdict == "INDETERMINATE"
    assert res.stable is False


def test_to_dict_structure_and_types() -> None:
    """Verify to_dict produces clean serializable dictionary."""
    res = assess_initial_process_study(
        data=_CAPABLE_DATA_1D,
        lsl=9.0,
        usl=11.0,
    )
    d = res.to_dict()
    assert isinstance(d, dict)
    assert d["verdict"] == "ACCEPTABLE"
    assert isinstance(d["rationales"], list)
    assert isinstance(d["citations"], list)
    assert d["violations"] is None


def test_to_dict_with_violations() -> None:
    """Verify to_dict correctly converts violations tuple to list."""
    res = assess_initial_process_study(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.85,
        violations=[{"rule": 1, "point": 5}],
    )
    d = res.to_dict()
    assert isinstance(d["violations"], list)
    assert len(d["violations"]) == 1
    assert d["violations"][0]["point"] == 5


def test_precomputed_none_index_value_raises() -> None:
    """Verify ValueError when precomputed_index_type is provided but index_value is None."""
    with pytest.raises(ValueError, match="Failed to compute capability index value"):
        assess_initial_process_study(
            precomputed_index_type="Ppk",
            precomputed_index_value=None,
        )

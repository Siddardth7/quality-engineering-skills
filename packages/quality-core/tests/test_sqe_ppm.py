"""
Tests for quality_core.sqe.ppm — the supplier PPM / DPMO defect-rate engine (E2, #116).

Covers, to 100% line + branch on quality_core.sqe.ppm:
- PPMConfig validation (bool / non-int -> TypeError, negative -> ValueError, default = 1000)
- PPMResult.to_dict() JSON-compatibility (dates -> ISO-8601 strings, list/dict copies)
- _resolve_lots: plain sequence vs ReceiptLotDataset unwrap
- _select_in_scope_lots: other-supplier drop, undated held in scope, in-window, out-of-window
- calculate_supplier_ppm verdict logic:
  * empty / other-supplier / zero-denominator -> INDETERMINATE, ppm is None (never 0.0)
  * undecided defect_count sentinel -> INDETERMINATE, numerator/ppm None
  * undated receipt_date on matched lot -> INDETERMINATE (held in scope, not dropped)
  * both blockers at once -> reason joins with "; "
  * MEASURED: numerator/denominator summed across lots, exact ppm, decided-zero -> 0.0
  * DPMO all-or-nothing: partial -> None + warning; complete -> computed, separate from ppm
  * sample_adequacy heuristic labelling + boundary at/below/above the minimum
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from quality_core.sqe import PPMConfig, PPMResult, calculate_supplier_ppm
from quality_core.sqe.ppm import (
    _SAMPLE_ADEQUACY_BASIS,
    _build_sample_adequacy,
    _format_lot_ids,
    _resolve_lots,
    _select_in_scope_lots,
)
from quality_core.sqe.schema import ReceiptLot, ReceiptLotDataset, SupplierPeriod

# ==============================================================================
# Helper functions
# ==============================================================================

_WINDOW_START = datetime.date(2026, 1, 1)
_WINDOW_END = datetime.date(2026, 3, 31)


def _period(supplier_id: str = "SUP-1", **overrides: Any) -> SupplierPeriod:
    base: dict[str, Any] = {
        "supplier_id": supplier_id,
        "period_start": _WINDOW_START,
        "period_end": _WINDOW_END,
        "period_label": "Q1 2026",
    }
    base.update(overrides)
    return SupplierPeriod(**base)


def _lot(**overrides: Any) -> ReceiptLot:
    base: dict[str, Any] = {
        "supplier_id": "SUP-1",
        "lot_id": "LOT-1",
        "quantity_received": 100,
        "receipt_date": datetime.date(2026, 1, 15),
        "defect_count": 2,
        "opportunities_per_unit": 3,
    }
    base.update(overrides)
    return ReceiptLot(**base)


# ==============================================================================
# 1. PPMConfig validation
# ==============================================================================


def test_ppm_config_default_minimum_is_1000() -> None:
    assert PPMConfig().sample_adequacy_minimum == 1000


def test_ppm_config_accepts_override() -> None:
    assert PPMConfig(sample_adequacy_minimum=500).sample_adequacy_minimum == 500
    assert PPMConfig(sample_adequacy_minimum=0).sample_adequacy_minimum == 0


def test_ppm_config_is_frozen() -> None:
    cfg = PPMConfig()
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError / dataclasses
        cfg.sample_adequacy_minimum = 5  # type: ignore[misc]


def test_ppm_config_rejects_bool() -> None:
    # bool is a subclass of int, but must be rejected explicitly.
    with pytest.raises(TypeError, match="must be an integer"):
        PPMConfig(sample_adequacy_minimum=True)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["1000", 1000.0, None])
def test_ppm_config_rejects_non_int(bad: Any) -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        PPMConfig(sample_adequacy_minimum=bad)


@pytest.mark.parametrize("neg", [-1, -1000])
def test_ppm_config_rejects_negative(neg: int) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        PPMConfig(sample_adequacy_minimum=neg)


# ==============================================================================
# 2. Private helpers
# ==============================================================================


def test_resolve_lots_plain_sequence() -> None:
    lots = [_lot(lot_id="A"), _lot(lot_id="B")]
    assert _resolve_lots(lots) == lots
    assert _resolve_lots(()) == []


def test_resolve_lots_unwraps_dataset() -> None:
    ds = ReceiptLotDataset(records=[_lot(lot_id="A"), _lot(lot_id="B")])
    out = _resolve_lots(ds)
    assert [lot.lot_id for lot in out] == ["A", "B"]


def test_select_in_scope_lots_all_arms() -> None:
    period = _period()
    other_supplier = _lot(lot_id="OTHER", supplier_id="SUP-2")
    undated = _lot(lot_id="UNDATED", receipt_date=None)
    out_of_window = _lot(lot_id="OUT", receipt_date=datetime.date(2026, 6, 1))
    in_window = _lot(lot_id="IN", receipt_date=datetime.date(2026, 2, 1))

    in_scope, undated_ids = _select_in_scope_lots(
        period, [other_supplier, undated, out_of_window, in_window]
    )
    ids = [lot.lot_id for lot in in_scope]
    assert ids == ["UNDATED", "IN"]  # other-supplier and out-of-window dropped
    assert undated_ids == ["UNDATED"]


def test_format_lot_ids() -> None:
    assert _format_lot_ids(["A", "B"]) == "'A', 'B'"


def test_build_sample_adequacy_shape() -> None:
    adequacy = _build_sample_adequacy(1000, PPMConfig())
    assert adequacy == {
        "minimum": 1000,
        "meets_minimum": True,
        "is_heuristic": True,
        "basis": _SAMPLE_ADEQUACY_BASIS,
    }


# ==============================================================================
# 3. Empty / zero-denominator -> INDETERMINATE (headline control)
# ==============================================================================


def test_empty_lots_indeterminate_ppm_is_none_not_zero() -> None:
    result = calculate_supplier_ppm(_period(), ())
    assert result.verdict == "INDETERMINATE"
    assert result.ppm is None  # NOT 0.0 — a supplier that shipped nothing is not perfect
    assert result.numerator is None
    assert result.denominator == 0
    assert result.lot_count == 0
    assert result.dpmo is None
    assert result.dpmo_opportunity_count is None
    assert result.reason is not None
    assert "no in-scope received quantity" in result.reason


def test_default_lots_argument_is_empty() -> None:
    # lots defaults to () — must not raise, must resolve INDETERMINATE.
    result = calculate_supplier_ppm(_period())
    assert result.verdict == "INDETERMINATE"
    assert result.ppm is None


def test_only_other_supplier_lots_indeterminate() -> None:
    result = calculate_supplier_ppm(_period(), [_lot(supplier_id="SUP-2")])
    assert result.verdict == "INDETERMINATE"
    assert result.ppm is None
    assert result.lot_count == 0
    assert result.denominator == 0


def test_zero_denominator_matched_lot_indeterminate() -> None:
    # A matched, dated, decided lot whose quantity_received bypasses ge=1 validation
    # (model_construct) -> lot_count == 1 but denominator == 0. The defensive
    # denominator-zero arm of the first guard must still resolve INDETERMINATE, not 0.0.
    zero_lot = ReceiptLot.model_construct(
        supplier_id="SUP-1",
        lot_id="LOT-ZERO",
        quantity_received=0,
        receipt_date=datetime.date(2026, 1, 15),
        defect_count=0,
        opportunities_per_unit=None,
    )
    result = calculate_supplier_ppm(_period(), [zero_lot])
    assert result.verdict == "INDETERMINATE"
    assert result.ppm is None  # no ZeroDivisionError, no 0.0
    assert result.numerator is None
    assert result.lot_count == 1
    assert result.denominator == 0


# ==============================================================================
# 4. Undecided sentinel -> INDETERMINATE (E1 sentinel control)
# ==============================================================================


def test_undecided_defect_count_indeterminate() -> None:
    # One decided lot + one uncounted (defect_count=None) lot -> whole period INDETERMINATE.
    # No PPM computed over the decided remainder.
    decided = _lot(lot_id="DECIDED", defect_count=5)
    undecided = _lot(lot_id="UNDECIDED", defect_count=None)
    result = calculate_supplier_ppm(_period(), [decided, undecided])
    assert result.verdict == "INDETERMINATE"
    assert result.ppm is None
    assert result.numerator is None
    # denominator IS knowable even when the numerator is not.
    assert result.denominator == 200
    assert result.lot_count == 2
    assert result.reason is not None
    assert "'UNDECIDED'" in result.reason
    assert "defect_count is undecided" in result.reason
    assert any("Complete the inspection count" in r for r in result.recommendations)


def test_single_undecided_lot_not_coerced_to_zero() -> None:
    # A lone uncounted lot must not read as ppm == 0.0.
    result = calculate_supplier_ppm(_period(), [_lot(defect_count=None)])
    assert result.verdict == "INDETERMINATE"
    assert result.ppm is None


# ==============================================================================
# 5. Undated receipt_date -> INDETERMINATE (held in scope, not dropped)
# ==============================================================================


def test_undated_matched_lot_indeterminate() -> None:
    # A supplier-matched lot with receipt_date=None is held in scope and drives
    # INDETERMINATE — never silently dropped (which would be a verdict on absent data).
    result = calculate_supplier_ppm(_period(), [_lot(lot_id="UNDATED", receipt_date=None)])
    assert result.verdict == "INDETERMINATE"
    assert result.ppm is None
    assert result.lot_count == 1  # held in scope
    assert result.denominator == 100  # counts toward denominator
    assert result.reason is not None
    assert "'UNDATED'" in result.reason
    assert "receipt_date is undecided" in result.reason
    assert any("Record a receipt_date" in r for r in result.recommendations)


def test_undated_and_undecided_both_named_in_reason() -> None:
    undated = _lot(lot_id="UNDATED", receipt_date=None, defect_count=1)
    undecided = _lot(lot_id="UNCOUNTED", receipt_date=datetime.date(2026, 2, 1), defect_count=None)
    result = calculate_supplier_ppm(_period(), [undated, undecided])
    assert result.verdict == "INDETERMINATE"
    assert result.reason is not None
    assert "; " in result.reason  # two blockers joined
    assert "'UNDATED'" in result.reason
    assert "'UNCOUNTED'" in result.reason


# ==============================================================================
# 6. MEASURED path — arithmetic, summation, decided-zero
# ==============================================================================


def test_measured_single_lot_exact_ppm() -> None:
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=1000, defect_count=2)])
    assert result.verdict == "MEASURED"
    assert result.numerator == 2
    assert result.denominator == 1000
    assert result.ppm == 2000.0  # (2 / 1000) * 1_000_000
    assert result.reason is None


def test_measured_sums_across_multiple_lots() -> None:
    lots = [
        _lot(lot_id="L1", quantity_received=500, defect_count=1, opportunities_per_unit=None),
        _lot(lot_id="L2", quantity_received=1500, defect_count=3, opportunities_per_unit=None),
    ]
    result = calculate_supplier_ppm(_period(), lots)
    assert result.verdict == "MEASURED"
    assert result.numerator == 4  # summed, not first-lot-only
    assert result.denominator == 2000
    assert result.ppm == 2000.0  # (4 / 2000) * 1_000_000


def test_decided_zero_is_measured_zero_ppm() -> None:
    # The one legitimate 0.0: every lot decided and decided clean.
    lots = [
        _lot(lot_id="Z1", quantity_received=1000, defect_count=0, opportunities_per_unit=None),
        _lot(lot_id="Z2", quantity_received=2000, defect_count=0, opportunities_per_unit=None),
    ]
    result = calculate_supplier_ppm(_period(), lots)
    assert result.verdict == "MEASURED"
    assert result.ppm == 0.0  # a real, decided zero — distinct from None
    assert result.numerator == 0


def test_measured_from_dataset_input() -> None:
    ds = ReceiptLotDataset(
        records=[_lot(lot_id="D1", quantity_received=1000, defect_count=1)]
    )
    result = calculate_supplier_ppm(_period(), ds)
    assert result.verdict == "MEASURED"
    assert result.ppm == 1000.0


def test_out_of_window_lot_excluded_from_measured() -> None:
    lots = [
        _lot(lot_id="IN", receipt_date=datetime.date(2026, 2, 1), quantity_received=1000, defect_count=1),
        _lot(lot_id="OUT", receipt_date=datetime.date(2026, 12, 1), quantity_received=9999, defect_count=999),
    ]
    result = calculate_supplier_ppm(_period(), lots)
    assert result.verdict == "MEASURED"
    assert result.lot_count == 1
    assert result.denominator == 1000  # OUT excluded


# ==============================================================================
# 7. DPMO all-or-nothing, separate from PPM
# ==============================================================================


def test_dpmo_computed_when_all_lots_have_opportunities() -> None:
    lots = [
        _lot(lot_id="D1", quantity_received=1000, defect_count=3, opportunities_per_unit=5),
        _lot(lot_id="D2", quantity_received=1000, defect_count=1, opportunities_per_unit=5),
    ]
    result = calculate_supplier_ppm(_period(), lots)
    assert result.verdict == "MEASURED"
    assert result.numerator == 4
    assert result.denominator == 2000
    # opportunities = 1000*5 + 1000*5 = 10000
    assert result.dpmo_opportunity_count == 10000
    assert result.dpmo == (4 / 10000) * 1_000_000  # 400.0
    # DPMO is a SEPARATE field from PPM and not interchangeable.
    assert result.ppm == 2000.0
    assert result.dpmo != result.ppm


def test_dpmo_none_when_partial_opportunities() -> None:
    lots = [
        _lot(lot_id="HAS", quantity_received=1000, defect_count=2, opportunities_per_unit=5),
        _lot(lot_id="MISSING", quantity_received=1000, defect_count=2, opportunities_per_unit=None),
    ]
    result = calculate_supplier_ppm(_period(), lots)
    assert result.verdict == "MEASURED"
    assert result.ppm == 2000.0  # PPM still computed
    assert result.dpmo is None  # all-or-nothing
    assert result.dpmo_opportunity_count is None
    warning = next(w for w in result.warnings if "DPMO not computed" in w)
    assert "'MISSING'" in warning  # names the gap lot
    assert "'HAS'" not in warning
    assert "not interchangeable with PPM" in warning


# ==============================================================================
# 8. sample_adequacy — heuristic labelling + boundary
# ==============================================================================


def test_sample_adequacy_is_always_heuristic() -> None:
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=1000, defect_count=1)])
    assert result.sample_adequacy["is_heuristic"] is True
    assert result.sample_adequacy["basis"] == _SAMPLE_ADEQUACY_BASIS
    assert "ASSUMPTIONS_LOG.md" in result.sample_adequacy["basis"]


def test_sample_adequacy_at_minimum_meets() -> None:
    # denominator exactly at the default 1000 minimum -> meets, no low-volume warning.
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=1000, defect_count=1)])
    assert result.sample_adequacy["meets_minimum"] is True
    assert not any("below the sample-adequacy minimum" in w for w in result.warnings)


def test_sample_adequacy_one_below_minimum_flags_low_volume() -> None:
    # denominator one below the minimum -> does not meet, warning + recommendation appended.
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=999, defect_count=1)])
    assert result.sample_adequacy["meets_minimum"] is False
    assert result.verdict == "MEASURED"  # adequacy never changes the verdict
    assert result.ppm is not None  # never suppresses the rate
    assert any("below the sample-adequacy minimum" in w for w in result.warnings)
    assert any("indicative only" in r for r in result.recommendations)


def test_sample_adequacy_one_above_minimum_meets() -> None:
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=1001, defect_count=1)])
    assert result.sample_adequacy["meets_minimum"] is True
    assert not any("below the sample-adequacy minimum" in w for w in result.warnings)


def test_sample_adequacy_minimum_is_caller_overridable() -> None:
    # A denominator that fails the default 1000 passes a caller-lowered minimum of 100.
    cfg = PPMConfig(sample_adequacy_minimum=100)
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=200, defect_count=1)], config=cfg)
    assert result.sample_adequacy["minimum"] == 100
    assert result.sample_adequacy["meets_minimum"] is True
    assert not any("below the sample-adequacy minimum" in w for w in result.warnings)


def test_sample_adequacy_minimum_zero_meets_even_on_empty_period() -> None:
    # sample_adequacy_minimum == 0 makes meets_minimum true even at denominator == 0.
    cfg = PPMConfig(sample_adequacy_minimum=0)
    result = calculate_supplier_ppm(_period(), (), config=cfg)
    assert result.verdict == "INDETERMINATE"
    assert result.denominator == 0
    assert result.sample_adequacy["meets_minimum"] is True


def test_low_volume_warning_appears_on_indeterminate_period() -> None:
    # Adequacy is evaluated for every verdict, including INDETERMINATE ones.
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=10, defect_count=None)])
    assert result.verdict == "INDETERMINATE"
    assert result.sample_adequacy["meets_minimum"] is False
    assert any("below the sample-adequacy minimum" in w for w in result.warnings)


# ==============================================================================
# 9. PPMResult.to_dict()
# ==============================================================================


def test_to_dict_measured_is_json_shaped() -> None:
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=1000, defect_count=2)])
    payload = result.to_dict()
    assert payload["period_start"] == "2026-01-01"  # ISO-8601 string, not date object
    assert payload["period_end"] == "2026-03-31"
    assert isinstance(payload["period_start"], str)
    assert payload["verdict"] == "MEASURED"
    assert payload["ppm"] == 2000.0
    assert payload["supplier_id"] == "SUP-1"
    assert payload["standards_basis"] == result.standards_basis


def test_to_dict_copies_mutable_fields() -> None:
    result = calculate_supplier_ppm(_period(), [_lot(quantity_received=10, defect_count=None)])
    payload = result.to_dict()
    payload["warnings"].append("MUTATED")
    payload["sample_adequacy"]["is_heuristic"] = "MUTATED"
    # Mutating the payload must not corrupt the result object.
    assert "MUTATED" not in result.warnings
    assert result.sample_adequacy["is_heuristic"] is True


def test_result_default_standards_basis() -> None:
    result = calculate_supplier_ppm(_period(), ())
    assert "No published AIAG/ISO/IATF standard" in result.standards_basis
    assert isinstance(result, PPMResult)

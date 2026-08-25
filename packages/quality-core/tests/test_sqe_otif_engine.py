"""
test_sqe_otif_engine.py
Exhaustive branch-coverage tests for quality_core.sqe.otif.

Covers, per the #117 spec Algorithm + Edge cases sections:
- OTIFConfig validation (every raise in __post_init__, both range ends)
- _resolve_deliveries: plain Sequence vs DeliveryRecordDataset unwrap
- calculate_otif window matching: wrong supplier, promised in/out of window, promised None held-in-scope
- empty-period INDETERMINATE, each blocker type (promised/actual/quantity), grouped reason
- MEASURED per-delivery on-time/in-full/OTIF conjunction, boundary dates (early + late), in-full boundary
- early_counts_as_on_time True/False, over_delivery_counts_as_in_full via model_construct (both flags)
- config=None default path, delivery_breakdown/shortfall_qty, to_dict() ISO strings + copy isolation
- heuristic_configuration labelling on both verdicts, perfect-set (warning False sides)
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from quality_core.sqe import (
    DeliveryRecord,
    DeliveryRecordDataset,
    OTIFConfig,
    OTIFResult,
    SupplierPeriod,
    calculate_otif,
)

SUP = "SUP-1"
P_START = datetime.date(2026, 1, 1)
P_END = datetime.date(2026, 1, 31)
PROMISED = datetime.date(2026, 1, 15)


def _period(**overrides: Any) -> SupplierPeriod:
    base: dict[str, Any] = {
        "supplier_id": SUP,
        "period_start": P_START,
        "period_end": P_END,
        "period_label": "2026-01",
    }
    base.update(overrides)
    return SupplierPeriod(**base)


def _delivery(**overrides: Any) -> DeliveryRecord:
    base: dict[str, Any] = {
        "supplier_id": SUP,
        "order_id": "O-1",
        "quantity_ordered": 10,
        "quantity_delivered": 10,
        "promised_date": PROMISED,
        "actual_delivery_date": PROMISED,
    }
    base.update(overrides)
    return DeliveryRecord(**base)


# ==============================================================================
# OTIFConfig validation
# ==============================================================================


def test_config_defaults_are_declared_heuristics() -> None:
    cfg = OTIFConfig()
    assert cfg.early_tolerance_days == 0
    assert cfg.late_tolerance_days == 2
    assert cfg.early_counts_as_on_time is False
    assert cfg.in_full_tolerance_pct == 0.0
    assert cfg.over_delivery_counts_as_in_full is True


@pytest.mark.parametrize("field_name", ["early_tolerance_days", "late_tolerance_days"])
def test_config_day_field_rejects_bool(field_name: str) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be an int"):
        OTIFConfig(**{field_name: True})


@pytest.mark.parametrize("field_name", ["early_tolerance_days", "late_tolerance_days"])
def test_config_day_field_rejects_non_int(field_name: str) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be an int"):
        OTIFConfig(**{field_name: 1.5})


@pytest.mark.parametrize("field_name", ["early_tolerance_days", "late_tolerance_days"])
def test_config_day_field_rejects_negative(field_name: str) -> None:
    with pytest.raises(ValueError, match=f"{field_name} must be >= 0"):
        OTIFConfig(**{field_name: -1})


@pytest.mark.parametrize(
    "field_name", ["early_counts_as_on_time", "over_delivery_counts_as_in_full"]
)
def test_config_flag_rejects_non_bool(field_name: str) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be a bool"):
        OTIFConfig(**{field_name: 1})


def test_config_in_full_tolerance_rejects_bool() -> None:
    with pytest.raises(TypeError, match="in_full_tolerance_pct must be a number"):
        OTIFConfig(in_full_tolerance_pct=True)


def test_config_in_full_tolerance_rejects_non_number() -> None:
    with pytest.raises(TypeError, match="in_full_tolerance_pct must be a number"):
        OTIFConfig(in_full_tolerance_pct="5")  # type: ignore[arg-type]


def test_config_in_full_tolerance_rejects_below_zero() -> None:
    with pytest.raises(ValueError, match=r"within \[0, 100\]"):
        OTIFConfig(in_full_tolerance_pct=-0.1)


def test_config_in_full_tolerance_rejects_above_hundred() -> None:
    with pytest.raises(ValueError, match=r"within \[0, 100\]"):
        OTIFConfig(in_full_tolerance_pct=100.1)


def test_config_in_full_tolerance_accepts_both_range_ends() -> None:
    assert OTIFConfig(in_full_tolerance_pct=0.0).in_full_tolerance_pct == 0.0
    assert OTIFConfig(in_full_tolerance_pct=100.0).in_full_tolerance_pct == 100.0


def test_config_in_full_tolerance_accepts_int() -> None:
    # int is a valid number for in_full_tolerance_pct (isinstance int/float True branch).
    assert OTIFConfig(in_full_tolerance_pct=5).in_full_tolerance_pct == 5


# ==============================================================================
# Empty / no-match INDETERMINATE
# ==============================================================================


def test_empty_deliveries_is_indeterminate() -> None:
    res = calculate_otif(_period())
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 0
    assert res.on_time_pct is None
    assert res.in_full_pct is None
    assert res.otif_pct is None
    assert res.on_time_count is None
    assert res.in_full_count is None
    assert res.otif_count is None
    assert res.delivery_breakdown == []
    assert res.reason == "no delivery records matched supplier_id and period window"


def test_only_other_supplier_records_is_indeterminate() -> None:
    res = calculate_otif(_period(), [_delivery(supplier_id="OTHER", order_id="X")])
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 0


def test_promised_date_outside_window_is_dropped() -> None:
    # Matched supplier but promised_date outside the window -> excluded (range False).
    res = calculate_otif(
        _period(),
        [_delivery(order_id="X", promised_date=datetime.date(2026, 2, 15))],
    )
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 0


def test_promised_date_on_period_start_is_in_scope() -> None:
    # Inclusive LOWER window bound: promised_date == period_start is IN scope,
    # so it counts toward the denominator. Pins `period_start <= promised_date`.
    res = calculate_otif(
        _period(),
        [_delivery(order_id="LO", promised_date=P_START, actual_delivery_date=P_START)],
    )
    assert res.delivery_count == 1
    assert res.verdict == "MEASURED"


def test_promised_date_on_period_end_is_in_scope() -> None:
    # Inclusive UPPER window bound: promised_date == period_end is IN scope.
    # Pins `promised_date <= period_end`.
    res = calculate_otif(
        _period(),
        [_delivery(order_id="HI", promised_date=P_END, actual_delivery_date=P_END)],
    )
    assert res.delivery_count == 1
    assert res.verdict == "MEASURED"


# ==============================================================================
# Blocker (undecided-data) INDETERMINATE
# ==============================================================================


def test_promised_none_is_held_in_scope_and_blocks() -> None:
    res = calculate_otif(_period(), [_delivery(order_id="E", promised_date=None)])
    assert res.verdict == "INDETERMINATE"
    # Held in scope: counted, not silently dropped.
    assert res.delivery_count == 1
    assert "missing or unparseable promised_date: E" in (res.reason or "")


def test_missing_actual_delivery_date_blocks() -> None:
    res = calculate_otif(_period(), [_delivery(order_id="E", actual_delivery_date=None)])
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 1
    assert "missing or unparseable actual_delivery_date: E" in (res.reason or "")


def test_undecided_quantity_blocks() -> None:
    res = calculate_otif(_period(), [_delivery(order_id="E", quantity_delivered=None)])
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 1
    assert "undecided quantity_delivered: E" in (res.reason or "")


def test_all_three_blocker_types_grouped_in_reason() -> None:
    res = calculate_otif(
        _period(),
        [
            _delivery(order_id="A", promised_date=None),
            _delivery(order_id="B", actual_delivery_date=None),
            _delivery(order_id="C", quantity_delivered=None),
        ],
    )
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 3
    reason = res.reason or ""
    assert "missing or unparseable promised_date: A" in reason
    assert "missing or unparseable actual_delivery_date: B" in reason
    assert "undecided quantity_delivered: C" in reason
    assert "; " in reason


def test_one_blocker_among_complete_still_whole_period_indeterminate() -> None:
    # A single undecided delivery blocks the whole period: no partial pct over the remainder.
    res = calculate_otif(
        _period(),
        [
            _delivery(order_id="GOOD-1"),
            _delivery(order_id="GOOD-2"),
            _delivery(order_id="BAD", quantity_delivered=None),
        ],
    )
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 3
    assert res.on_time_pct is None
    assert res.delivery_breakdown == []


# ==============================================================================
# MEASURED path
# ==============================================================================


def test_single_perfect_delivery_measured() -> None:
    res = calculate_otif(_period(), [_delivery()])
    assert res.verdict == "MEASURED"
    assert res.delivery_count == 1
    assert res.on_time_count == 1
    assert res.in_full_count == 1
    assert res.otif_count == 1
    assert res.on_time_pct == 100.0
    assert res.in_full_pct == 100.0
    assert res.otif_pct == 100.0
    assert res.reason is None
    # Perfect set: all three warning/recommendation `if X < delivery_count` False sides.
    assert res.warnings == []


def test_multiple_deliveries_aggregate() -> None:
    res = calculate_otif(
        _period(),
        [_delivery(order_id="O-1"), _delivery(order_id="O-2"), _delivery(order_id="O-3")],
    )
    assert res.verdict == "MEASURED"
    assert res.delivery_count == 3
    assert res.otif_count == 3
    assert res.otif_pct == 100.0


def test_on_time_but_short_is_not_otif() -> None:
    # Partial shipment: on-time True, in-full False, so is_otif False, shortfall exact.
    res = calculate_otif(_period(), [_delivery(order_id="S", quantity_delivered=8)])
    assert res.verdict == "MEASURED"
    assert res.on_time_count == 1
    assert res.in_full_count == 0
    assert res.otif_count == 0
    row = res.delivery_breakdown[0]
    assert row["is_on_time"] is True
    assert row["is_in_full"] is False
    assert row["is_otif"] is False
    assert row["shortfall_qty"] == 2


def test_in_full_but_late_is_not_otif() -> None:
    res = calculate_otif(
        _period(),
        [_delivery(order_id="L", actual_delivery_date=datetime.date(2026, 1, 20))],
    )
    row = res.delivery_breakdown[0]
    assert row["is_on_time"] is False
    assert row["is_in_full"] is True
    assert row["is_otif"] is False
    assert row["shortfall_qty"] == 0


# ==============================================================================
# Late-side on-time boundary (default late_tolerance_days=2)
# ==============================================================================


def test_late_boundary_exactly_at_bound_is_on_time() -> None:
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", actual_delivery_date=datetime.date(2026, 1, 17))],
    )
    assert res.delivery_breakdown[0]["is_on_time"] is True


def test_late_boundary_one_day_beyond_is_not_on_time() -> None:
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", actual_delivery_date=datetime.date(2026, 1, 18))],
    )
    assert res.delivery_breakdown[0]["is_on_time"] is False


def test_late_boundary_one_day_inside_is_on_time() -> None:
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", actual_delivery_date=datetime.date(2026, 1, 16))],
    )
    assert res.delivery_breakdown[0]["is_on_time"] is True


def test_late_boundary_inclusive_when_early_counts_as_on_time() -> None:
    # Under early_counts_as_on_time=True the late side is still bounded INCLUSIVELY:
    # actual == late_bound (promised + late_tolerance_days) is on-time; one day beyond
    # is not. Pins the `actual_delivery_date <= late_bound` edge on that branch.
    cfg = OTIFConfig(early_counts_as_on_time=True)
    late_bound = PROMISED + datetime.timedelta(days=cfg.late_tolerance_days)
    at_bound = calculate_otif(
        _period(),
        [_delivery(order_id="AT", actual_delivery_date=late_bound)],
        config=cfg,
    )
    assert at_bound.delivery_breakdown[0]["is_on_time"] is True
    beyond = calculate_otif(
        _period(),
        [_delivery(order_id="OB", actual_delivery_date=late_bound + datetime.timedelta(days=1))],
        config=cfg,
    )
    assert beyond.delivery_breakdown[0]["is_on_time"] is False


# ==============================================================================
# Early-side on-time boundary (needs non-zero early_tolerance_days)
# ==============================================================================


def test_early_boundary_exactly_at_bound_is_on_time() -> None:
    cfg = OTIFConfig(early_tolerance_days=3)
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", actual_delivery_date=datetime.date(2026, 1, 12))],
        config=cfg,
    )
    assert res.delivery_breakdown[0]["is_on_time"] is True


def test_early_boundary_one_day_beyond_is_not_on_time() -> None:
    cfg = OTIFConfig(early_tolerance_days=3)
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", actual_delivery_date=datetime.date(2026, 1, 11))],
        config=cfg,
    )
    assert res.delivery_breakdown[0]["is_on_time"] is False


def test_early_boundary_one_day_inside_is_on_time() -> None:
    cfg = OTIFConfig(early_tolerance_days=3)
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", actual_delivery_date=datetime.date(2026, 1, 13))],
        config=cfg,
    )
    assert res.delivery_breakdown[0]["is_on_time"] is True


def test_early_counts_as_on_time_flips_verdict() -> None:
    # Arrives far earlier than early_tolerance_days=0 allows.
    early = _delivery(
        order_id="E", promised_date=datetime.date(2026, 1, 20), actual_delivery_date=datetime.date(2026, 1, 5)
    )
    strict = calculate_otif(_period(), [early])
    assert strict.on_time_pct == 0.0
    lenient = calculate_otif(_period(), [early], config=OTIFConfig(early_counts_as_on_time=True))
    assert lenient.on_time_pct == 100.0


def test_early_counts_as_on_time_still_bounds_late_side() -> None:
    late = _delivery(order_id="L", actual_delivery_date=datetime.date(2026, 1, 20))
    res = calculate_otif(_period(), [late], config=OTIFConfig(early_counts_as_on_time=True))
    assert res.delivery_breakdown[0]["is_on_time"] is False


# ==============================================================================
# In-full boundary (in_full_tolerance_pct)
# ==============================================================================


def test_in_full_boundary_exactly_at_lower_bound() -> None:
    # quantity_ordered=100, tolerance 5% -> lower bound 95.0
    cfg = OTIFConfig(in_full_tolerance_pct=5.0)
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", quantity_ordered=100, quantity_delivered=95)],
        config=cfg,
    )
    assert res.delivery_breakdown[0]["is_in_full"] is True


def test_in_full_boundary_one_below_lower_bound() -> None:
    cfg = OTIFConfig(in_full_tolerance_pct=5.0)
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", quantity_ordered=100, quantity_delivered=94)],
        config=cfg,
    )
    assert res.delivery_breakdown[0]["is_in_full"] is False
    assert res.delivery_breakdown[0]["shortfall_qty"] == 6


def test_in_full_boundary_one_above_lower_bound() -> None:
    cfg = OTIFConfig(in_full_tolerance_pct=5.0)
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", quantity_ordered=100, quantity_delivered=96)],
        config=cfg,
    )
    assert res.delivery_breakdown[0]["is_in_full"] is True
    assert res.delivery_breakdown[0]["shortfall_qty"] == 4


# ==============================================================================
# over_delivery_counts_as_in_full (only reachable via model_construct)
# ==============================================================================


def _over_delivery() -> DeliveryRecord:
    # model_construct bypasses reject_delivered_exceeding_ordered AND the lenient date parser,
    # so pass real date objects and requested_date=None explicitly.
    return DeliveryRecord.model_construct(
        supplier_id=SUP,
        order_id="OVER",
        quantity_ordered=5,
        quantity_delivered=7,
        requested_date=None,
        promised_date=PROMISED,
        actual_delivery_date=PROMISED,
    )


def test_over_delivery_counts_in_full_when_flag_true() -> None:
    res = calculate_otif(_period(), [_over_delivery()])  # default flag True
    assert res.in_full_count == 1
    assert res.in_full_pct == 100.0
    assert res.delivery_breakdown[0]["is_in_full"] is True
    # over-delivery never produces a negative shortfall.
    assert res.delivery_breakdown[0]["shortfall_qty"] == 0


def test_over_delivery_not_in_full_when_flag_false() -> None:
    res = calculate_otif(
        _period(), [_over_delivery()], config=OTIFConfig(over_delivery_counts_as_in_full=False)
    )
    assert res.in_full_count == 0
    assert res.in_full_pct == 0.0
    assert res.delivery_breakdown[0]["is_in_full"] is False


# ==============================================================================
# Input plumbing: config=None, DeliveryRecordDataset overload, window matching
# ==============================================================================


def test_config_none_uses_defaults() -> None:
    # actual +2 days from promised is on-time only under the default late_tolerance_days=2.
    res = calculate_otif(
        _period(),
        [_delivery(order_id="B", actual_delivery_date=datetime.date(2026, 1, 17))],
        config=None,
    )
    assert res.delivery_breakdown[0]["is_on_time"] is True


def test_dataset_overload_matches_plain_list() -> None:
    records = [_delivery(order_id="O-1"), _delivery(order_id="O-2", quantity_delivered=8)]
    from_list = calculate_otif(_period(), records)
    from_dataset = calculate_otif(_period(), DeliveryRecordDataset(records=records))
    assert from_list.to_dict() == from_dataset.to_dict()


def test_promised_date_none_and_in_window_both_matched() -> None:
    # Wrong-supplier (excluded), promised None (in scope), promised in window (matched).
    res = calculate_otif(
        _period(),
        [
            _delivery(order_id="WRONG", supplier_id="OTHER"),
            _delivery(order_id="NONE", promised_date=None),
            _delivery(order_id="IN"),
        ],
    )
    # promised None makes it INDETERMINATE, but count reflects the two matched SUP records.
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 2


# ==============================================================================
# Serialization + heuristic labelling
# ==============================================================================


def test_to_dict_emits_iso_dates_and_isolates_copies() -> None:
    res = calculate_otif(_period(), [_delivery()])
    d = res.to_dict()
    assert d["period_start"] == "2026-01-01"
    assert d["period_end"] == "2026-01-31"
    assert isinstance(d["period_start"], str)
    # Mutating returned containers must not mutate the result.
    d["delivery_breakdown"].append({"tampered": True})
    d["heuristic_configuration"]["is_heuristic"] = False
    d["warnings"].append("x")
    d["recommendations"].append("x")
    assert len(res.delivery_breakdown) == 1
    assert res.heuristic_configuration["is_heuristic"] is True
    assert "x" not in res.warnings
    assert "x" not in res.recommendations


def test_heuristic_configuration_labelled_on_measured() -> None:
    res = calculate_otif(_period(), [_delivery()])
    hc = res.heuristic_configuration
    assert hc["is_heuristic"] is True
    assert "no standards citation" in hc["basis"]
    assert "ASSUMPTIONS_LOG" in hc["basis"]
    assert hc["late_tolerance_days"] == 2


def test_heuristic_configuration_labelled_on_indeterminate() -> None:
    res = calculate_otif(_period())
    hc = res.heuristic_configuration
    assert hc["is_heuristic"] is True
    assert "no standards citation" in hc["basis"]


def test_standards_basis_disclaims_standard() -> None:
    res = calculate_otif(_period(), [_delivery()])
    assert "No published AIAG/ISO/IATF standard" in res.standards_basis


def test_result_is_otifresult() -> None:
    assert isinstance(calculate_otif(_period()), OTIFResult)

"""Benchmark supplier scorecards and mandatory negative controls for issue #118."""

from __future__ import annotations

import datetime

from quality_core.sqe import (
    DeliveryRecord,
    LinearScoringCurve,
    ReceiptLot,
    ScorecardConfig,
    SupplierPeriod,
    calculate_vendor_scorecard,
)

PERIOD = SupplierPeriod(
    supplier_id="SUP-BENCH",
    period_start=datetime.date(2026, 4, 1),
    period_end=datetime.date(2026, 6, 30),
    period_label="2026 Q2",
)
DATE = datetime.date(2026, 5, 15)


def _lot(defects: int | None, *, quantity: int = 1_000, lot_id: str = "LOT-1") -> ReceiptLot:
    return ReceiptLot(
        supplier_id="SUP-BENCH",
        lot_id=lot_id,
        quantity_received=quantity,
        receipt_date=DATE,
        defect_count=defects,
    )


def _delivery(
    order_id: str,
    *,
    delivered: int | None = 100,
    actual: datetime.date | None = DATE,
) -> DeliveryRecord:
    return DeliveryRecord(
        supplier_id="SUP-BENCH",
        order_id=order_id,
        quantity_ordered=100,
        quantity_delivered=delivered,
        promised_date=DATE,
        actual_delivery_date=actual,
    )


def test_default_perfect_supplier_benchmark_is_a() -> None:
    """0 PPM -> 100; 100% OTIF -> 100; 0.60(100)+0.40(100)=100 -> A."""
    result = calculate_vendor_scorecard(PERIOD, [_lot(0)], [_delivery("D1")])
    assert result.verdict == "RATED"
    assert [dimension.raw_metric for dimension in result.dimensions] == [0.0, 100.0]
    assert [dimension.sub_score for dimension in result.dimensions] == [100.0, 100.0]
    assert result.composite_score == 100.0
    assert result.band == "A"


def test_default_benchmark_with_one_injected_defect_condition_flips_to_c() -> None:
    """10/1000 -> 10,000 PPM -> quality 0; OTIF 100; 0.60(0)+0.40(100)=40 -> C."""
    result = calculate_vendor_scorecard(PERIOD, [_lot(10)], [_delivery("D1")])
    assert result.verdict == "RATED"
    assert result.dimensions[0].raw_metric == 10_000.0
    assert result.dimensions[0].sub_score == 0.0
    assert result.composite_score == 40.0
    assert result.band == "C"


def test_custom_configuration_benchmark_is_b() -> None:
    """2,500 PPM -> 75; 50% OTIF -> 50; 0.8(75)+0.2(50)=70 -> custom B at 68."""
    config = ScorecardConfig(
        quality_weight=0.8,
        delivery_weight=0.2,
        cost_weight=0.0,
        quality_curve=LinearScoringCurve(0, 10_000),
        delivery_curve=LinearScoringCurve(100, 0),
        a_band_minimum=80,
        b_band_minimum=68,
    )
    deliveries = [
        _delivery("D1"),
        _delivery("D2", actual=datetime.date(2026, 5, 20)),
    ]
    result = calculate_vendor_scorecard(
        PERIOD, [_lot(25, quantity=10_000)], deliveries, config=config
    )
    assert [dimension.raw_metric for dimension in result.dimensions] == [2_500.0, 50.0]
    assert [dimension.sub_score for dimension in result.dimensions] == [75.0, 50.0]
    assert result.composite_score == 70.0
    assert result.band == "B"


def test_custom_benchmark_with_one_injected_delivery_defect_flips_to_c() -> None:
    """Same config plus one late delivery: OTIF 1/3; 0.8(75)+0.2(33.333)=66.667 -> C."""
    config = ScorecardConfig(
        quality_weight=0.8,
        delivery_weight=0.2,
        cost_weight=0.0,
        a_band_minimum=80,
        b_band_minimum=68,
    )
    deliveries = [
        _delivery("D1"),
        _delivery("D2", actual=datetime.date(2026, 5, 20)),
        _delivery("D3", actual=datetime.date(2026, 5, 20)),
    ]
    result = calculate_vendor_scorecard(
        PERIOD, [_lot(25, quantity=10_000)], deliveries, config=config
    )
    assert result.composite_score is not None
    assert 66.66 < result.composite_score < 66.67
    assert result.band == "C"


def test_band_suppression_negative_control_zero_denominator_ppm() -> None:
    """No receipt evidence must suppress both composite and band, never imply perfect quality."""
    result = calculate_vendor_scorecard(PERIOD, [], [_delivery("D1")])
    assert result.verdict == "INDETERMINATE"
    assert result.composite_score is None
    assert result.band is None


def test_band_suppression_negative_control_undecided_ppm() -> None:
    """An undecided defect count must suppress both composite and band."""
    result = calculate_vendor_scorecard(PERIOD, [_lot(None)], [_delivery("D1")])
    assert result.verdict == "INDETERMINATE"
    assert result.composite_score is None
    assert result.band is None
    assert result.dimensions[0].source_verdict == "INDETERMINATE"


def test_omitted_dimension_negative_control_does_not_redistribute_cost() -> None:
    """Default cost omission retains exact 0.60/0.40 contributions; neither becomes 1.0."""
    result = calculate_vendor_scorecard(PERIOD, [_lot(5)], [_delivery("D1")])
    quality, delivery = result.dimensions
    assert quality.weight == 0.60
    assert delivery.weight == 0.40
    assert quality.weighted_contribution == 30.0
    assert delivery.weighted_contribution == 40.0
    assert result.composite_score == 70.0
    assert result.band == "C"
    assert result.omitted_dimensions[0]["name"] == "cost"


def test_weight_integrity_negative_control_non_summing_weights_raise() -> None:
    """A 0.60/0.30/0.0 configuration is invalid; silent normalization is forbidden."""
    try:
        ScorecardConfig(quality_weight=0.60, delivery_weight=0.30, cost_weight=0.0)
    except ValueError as exc:
        assert "must equal 1.0" in str(exc)
    else:  # pragma: no cover - this is the mutation-killing assertion
        raise AssertionError("non-summing weights were silently accepted or normalized")


def test_no_standard_implied_negative_control_for_band_basis() -> None:
    """A scorecard boundary basis may name no ISO/IATF clause as its numeric authority."""
    payload = calculate_vendor_scorecard(PERIOD, [_lot(0)], [_delivery("D1")]).to_dict()
    for name in ("a_band_minimum", "b_band_minimum"):
        criterion = payload["heuristic_configuration"]["rating_bands"][name]
        assert criterion["is_heuristic"] is True
        assert "no standards citation" in criterion["basis"]
        assert "ISO 9001" not in criterion["basis"]
        assert "IATF 16949" not in criterion["basis"]

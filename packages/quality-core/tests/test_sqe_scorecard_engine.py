"""Exhaustive unit and branch tests for ``quality_core.sqe.scorecard`` (#118)."""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any

import pytest
from quality_core.copq import COPQDataset, CostItem
from quality_core.sqe import (
    DeliveryRecord,
    DeliveryRecordDataset,
    LinearScoringCurve,
    OTIFConfig,
    PPMConfig,
    ReceiptLot,
    ReceiptLotDataset,
    ScorecardConfig,
    ScorecardDimensionResult,
    ScorecardResult,
    SupplierPeriod,
    calculate_vendor_scorecard,
)
from quality_core.sqe import scorecard as scorecard_module


def _period() -> SupplierPeriod:
    return SupplierPeriod(
        supplier_id="SUP-118",
        period_start=datetime.date(2026, 1, 1),
        period_end=datetime.date(2026, 3, 31),
        period_label="2026 Q1",
    )


def _lot(*, defects: int | None = 0, quantity: int = 1_000, lot_id: str = "L1") -> ReceiptLot:
    return ReceiptLot(
        supplier_id="SUP-118",
        lot_id=lot_id,
        quantity_received=quantity,
        defect_count=defects,
        receipt_date=datetime.date(2026, 2, 1),
    )


def _delivery(
    *,
    delivered: int | None = 10,
    actual: datetime.date | None = datetime.date(2026, 2, 10),
    order_id: str = "D1",
) -> DeliveryRecord:
    return DeliveryRecord(
        supplier_id="SUP-118",
        order_id=order_id,
        quantity_ordered=10,
        quantity_delivered=delivered,
        promised_date=datetime.date(2026, 2, 10),
        actual_delivery_date=actual,
    )


def _source_stub(
    metric_name: str, metric: float | None, verdict: str = "MEASURED"
) -> SimpleNamespace:
    payload = {
        "verdict": verdict,
        metric_name: metric,
        "reason": None if verdict == "MEASURED" else "source evidence undecided",
        "warnings": [],
        "recommendations": [],
    }
    return SimpleNamespace(
        verdict=verdict,
        ppm=metric if metric_name == "ppm" else None,
        otif_pct=metric if metric_name == "otif_pct" else None,
        reason=payload["reason"],
        warnings=[],
        recommendations=[],
        to_dict=lambda: dict(payload),
    )


# ---------------------------------------------------------------------------
# LinearScoringCurve and ScorecardConfig validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["best_value", "worst_value"])
@pytest.mark.parametrize("bad", [True, "0", None, object()])
def test_curve_rejects_non_numeric_endpoint(field: str, bad: object) -> None:
    values: dict[str, object] = {"best_value": 100.0, "worst_value": 0.0}
    values[field] = bad
    with pytest.raises(TypeError, match=f"{field} must be a number"):
        LinearScoringCurve(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["best_value", "worst_value"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_curve_rejects_non_finite_endpoint(field: str, bad: float) -> None:
    values = {"best_value": 100.0, "worst_value": 0.0, field: bad}
    with pytest.raises(ValueError, match=f"{field} must be finite"):
        LinearScoringCurve(**values)


def test_curve_rejects_equal_endpoints_and_is_frozen() -> None:
    with pytest.raises(ValueError, match="must be different"):
        LinearScoringCurve(5, 5.0)
    curve = LinearScoringCurve(100, 0)
    assert curve.best_value == 100.0
    with pytest.raises(FrozenInstanceError):
        curve.best_value = 10  # type: ignore[misc]


def test_curve_direction_interpolation_clamping_and_endpoints() -> None:
    higher = LinearScoringCurve(best_value=100, worst_value=0)
    assert higher.score(100) == 100.0
    assert higher.score(0) == 0.0
    assert higher.score(25) == 25.0
    assert higher.score(150) == 100.0
    assert higher.score(-1) == 0.0

    lower = LinearScoringCurve(best_value=0, worst_value=10_000)
    assert lower.score(0) == 100.0
    assert lower.score(10_000) == 0.0
    assert lower.score(2_500) == 75.0
    assert lower.score(-10) == 100.0
    assert lower.score(20_000) == 0.0


@pytest.mark.parametrize("bad", [False, "10", None])
def test_curve_rejects_non_numeric_raw_metric(bad: object) -> None:
    with pytest.raises(TypeError, match="raw_metric must be a number"):
        LinearScoringCurve(100, 0).score(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_curve_rejects_non_finite_raw_metric(bad: float) -> None:
    with pytest.raises(ValueError, match="raw_metric must be finite"):
        LinearScoringCurve(100, 0).score(bad)


def test_config_defaults_factories_and_frozen_contract() -> None:
    first = ScorecardConfig()
    second = ScorecardConfig()
    assert (first.quality_weight, first.delivery_weight, first.cost_weight) == (0.6, 0.4, 0.0)
    assert first.quality_curve == LinearScoringCurve(0, 10_000)
    assert first.delivery_curve == LinearScoringCurve(100, 0)
    assert first.cost_curve is None
    assert first.ppm_config is not second.ppm_config
    assert first.otif_config is not second.otif_config
    with pytest.raises(FrozenInstanceError):
        first.cost_weight = 0.1  # type: ignore[misc]


@pytest.mark.parametrize("name", ["quality_weight", "delivery_weight", "cost_weight"])
@pytest.mark.parametrize("bad", [True, "0.5", None])
def test_config_rejects_non_numeric_weights(name: str, bad: object) -> None:
    kwargs: dict[str, object] = {
        "quality_weight": 0.6,
        "delivery_weight": 0.4,
        "cost_weight": 0.0,
    }
    kwargs[name] = bad
    with pytest.raises(TypeError, match=f"{name} must be a number"):
        ScorecardConfig(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["quality_weight", "delivery_weight", "cost_weight"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_config_rejects_non_finite_weights(name: str, bad: float) -> None:
    kwargs = {"quality_weight": 0.6, "delivery_weight": 0.4, "cost_weight": 0.0, name: bad}
    with pytest.raises(ValueError, match=f"{name} must be finite"):
        ScorecardConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quality_weight": -0.1, "delivery_weight": 1.0, "cost_weight": 0.1},
        {"quality_weight": 0.0, "delivery_weight": 1.1, "cost_weight": -0.1},
        {"quality_weight": 0.0, "delivery_weight": 0.0, "cost_weight": 1.1},
    ],
)
def test_config_rejects_weights_outside_unit_interval(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match=r"within \[0, 1\]"):
        ScorecardConfig(**kwargs)


def test_weight_integrity_negative_control_rejects_instead_of_normalizing() -> None:
    with pytest.raises(ValueError, match="must equal 1.0"):
        ScorecardConfig(quality_weight=0.6, delivery_weight=0.3, cost_weight=0.0)


@pytest.mark.parametrize("name", ["quality_curve", "delivery_curve"])
def test_config_rejects_wrong_required_curve_type(name: str) -> None:
    with pytest.raises(TypeError, match=f"{name} must be a LinearScoringCurve"):
        ScorecardConfig(**{name: object()})  # type: ignore[arg-type]


def test_config_rejects_wrong_cost_curve_and_requires_it_when_weighted() -> None:
    with pytest.raises(TypeError, match="cost_curve must be"):
        ScorecardConfig(cost_curve=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="required when cost_weight is positive"):
        ScorecardConfig(quality_weight=0.5, delivery_weight=0.4, cost_weight=0.1)


@pytest.mark.parametrize("name", ["a_band_minimum", "b_band_minimum"])
@pytest.mark.parametrize("bad", [True, "90", None])
def test_config_rejects_non_numeric_bands(name: str, bad: object) -> None:
    with pytest.raises(TypeError, match=f"{name} must be a number"):
        ScorecardConfig(**{name: bad})  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["a_band_minimum", "b_band_minimum"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_config_rejects_non_finite_bands(name: str, bad: float) -> None:
    with pytest.raises(ValueError, match=f"{name} must be finite"):
        ScorecardConfig(**{name: bad})


@pytest.mark.parametrize(
    ("a_min", "b_min"),
    [(90, -1), (90, 90), (75, 90), (101, 75), (0, 0)],
)
def test_config_rejects_invalid_band_order(a_min: float, b_min: float) -> None:
    with pytest.raises(ValueError, match="band boundaries must satisfy"):
        ScorecardConfig(a_band_minimum=a_min, b_band_minimum=b_min)


def test_config_rejects_wrong_nested_source_configs() -> None:
    with pytest.raises(TypeError, match="ppm_config must be"):
        ScorecardConfig(ppm_config=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="otif_config must be"):
        ScorecardConfig(otif_config=object())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Composition, omissions, evidence, and serialization
# ---------------------------------------------------------------------------


def test_default_composition_and_dataset_inputs_are_equivalent() -> None:
    lots = [_lot()]
    deliveries = [_delivery()]
    from_sequences = calculate_vendor_scorecard(_period(), lots, deliveries)
    from_datasets = calculate_vendor_scorecard(
        _period(), ReceiptLotDataset(records=lots), DeliveryRecordDataset(records=deliveries)
    )
    assert from_sequences.to_dict() == from_datasets.to_dict()
    assert from_sequences.verdict == "RATED"
    assert from_sequences.composite_score == 100.0
    assert from_sequences.band == "A"
    assert [dimension.name for dimension in from_sequences.dimensions] == ["quality", "delivery"]
    assert from_sequences.omitted_dimensions[0]["name"] == "cost"


def test_source_engines_are_called_exactly_once_with_nested_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_ppm = scorecard_module.calculate_supplier_ppm
    real_otif = scorecard_module.calculate_otif
    calls: list[tuple[str, object]] = []

    def ppm_spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(("ppm", kwargs["config"]))
        return real_ppm(*args, **kwargs)

    def otif_spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(("otif", kwargs["config"]))
        return real_otif(*args, **kwargs)

    monkeypatch.setattr(scorecard_module, "calculate_supplier_ppm", ppm_spy)
    monkeypatch.setattr(scorecard_module, "calculate_otif", otif_spy)
    config = ScorecardConfig(
        ppm_config=PPMConfig(sample_adequacy_minimum=10),
        otif_config=OTIFConfig(late_tolerance_days=5),
    )
    calculate_vendor_scorecard(_period(), [_lot()], [_delivery()], config=config)
    assert calls == [("ppm", config.ppm_config), ("otif", config.otif_config)]


def test_config_none_and_wrong_config_type() -> None:
    assert calculate_vendor_scorecard(_period(), [_lot()], [_delivery()], config=None).band == "A"
    with pytest.raises(TypeError, match="config must be"):
        calculate_vendor_scorecard(_period(), [_lot()], [_delivery()], config=object())  # type: ignore[arg-type]


def test_custom_weighted_copq_composition_delegates_estimator_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_estimate = scorecard_module.estimate_copq
    calls: list[tuple[object, object]] = []

    def estimate_spy(*, items: object, revenue_base: object) -> Any:
        calls.append((items, revenue_base))
        return real_estimate(items=items, revenue_base=revenue_base)  # type: ignore[arg-type]

    monkeypatch.setattr(scorecard_module, "estimate_copq", estimate_spy)
    items = [CostItem(category="InternalFailure", description="scrap", direct_cost=5_000)]
    config = ScorecardConfig(
        quality_weight=0.50,
        delivery_weight=0.25,
        cost_weight=0.25,
        cost_curve=LinearScoringCurve(best_value=0, worst_value=10),
    )
    result = calculate_vendor_scorecard(
        _period(), [_lot()], [_delivery()], copq_items=items, revenue_base=100_000, config=config
    )
    assert calls == [(items, 100_000)]
    cost = next(dimension for dimension in result.dimensions if dimension.name == "cost")
    assert cost.raw_metric == 5.0
    assert cost.sub_score == 50.0
    assert cost.weighted_contribution == 12.5
    assert result.composite_score == 87.5
    assert result.band == "B"


def test_weighted_copq_dataset_uses_dataset_revenue_base() -> None:
    dataset = COPQDataset(
        items=[CostItem(category="ExternalFailure", description="returns", direct_cost=2_000)],
        revenue_base=100_000,
    )
    config = ScorecardConfig(
        quality_weight=0.4,
        delivery_weight=0.4,
        cost_weight=0.2,
        cost_curve=LinearScoringCurve(0, 10),
    )
    result = calculate_vendor_scorecard(
        _period(), [_lot()], [_delivery()], copq_items=dataset, config=config
    )
    assert result.verdict == "RATED"
    assert result.dimensions[-1].raw_metric == 2.0


def test_absent_and_empty_weighted_cost_are_indeterminate_without_redistribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_estimator(**_: object) -> Any:
        raise AssertionError("empty cost evidence must not call estimate_copq")

    monkeypatch.setattr(scorecard_module, "estimate_copq", forbidden_estimator)
    config = ScorecardConfig(
        quality_weight=0.5,
        delivery_weight=0.4,
        cost_weight=0.1,
        cost_curve=LinearScoringCurve(0, 10),
    )
    for evidence in (None, []):
        result = calculate_vendor_scorecard(
            _period(), [_lot()], [_delivery()], copq_items=evidence, config=config
        )
        assert result.verdict == "INDETERMINATE"
        assert result.composite_score is None
        assert result.band is None
        assert result.dimensions[-1].name == "cost"
        assert result.dimensions[-1].weighted_contribution is None
        assert "cannot be redistributed" in (result.reason or "")


def test_unusable_weighted_cost_and_missing_revenue_are_indeterminate() -> None:
    config = ScorecardConfig(
        quality_weight=0.5,
        delivery_weight=0.4,
        cost_weight=0.1,
        cost_curve=LinearScoringCurve(0, 10),
    )
    invalid = calculate_vendor_scorecard(
        _period(),
        [_lot()],
        [_delivery()],
        copq_items=[{"category": "wrong", "description": "bad"}],
        revenue_base=100,
        config=config,
    )
    assert invalid.verdict == "INDETERMINATE"
    assert "unusable" in (invalid.reason or "")

    no_revenue = calculate_vendor_scorecard(
        _period(),
        [_lot()],
        [_delivery()],
        copq_items=[CostItem(category="InternalFailure", description="scrap", direct_cost=10)],
        config=config,
    )
    assert no_revenue.verdict == "INDETERMINATE"
    assert "positive revenue base" in (no_revenue.reason or "")
    assert no_revenue.dimensions[-1].source_evidence["copq_percentage_of_revenue"] is None


def test_zero_cost_weight_never_calls_copq_and_reports_supplied_evidence_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scorecard_module,
        "estimate_copq",
        lambda **_: (_ for _ in ()).throw(AssertionError("zero-weight cost must not be called")),
    )
    result = calculate_vendor_scorecard(
        _period(),
        [_lot()],
        [_delivery()],
        copq_items=[CostItem(category="InternalFailure", description="scrap", direct_cost=10)],
        revenue_base=1_000,
    )
    assert result.verdict == "RATED"
    assert result.composite_score == 100.0
    assert "supplied COPQ evidence was not scored" in result.omitted_dimensions[0]["reason"]


def test_zero_weight_source_dimensions_are_omitted_and_do_not_block() -> None:
    delivery_only = ScorecardConfig(quality_weight=0, delivery_weight=1, cost_weight=0)
    result = calculate_vendor_scorecard(_period(), [], [_delivery()], config=delivery_only)
    assert result.verdict == "RATED"
    assert result.band == "A"
    assert [dimension.name for dimension in result.dimensions] == ["delivery"]
    assert [item["name"] for item in result.omitted_dimensions] == ["quality", "cost"]

    quality_only = ScorecardConfig(quality_weight=1, delivery_weight=0, cost_weight=0)
    result = calculate_vendor_scorecard(_period(), [_lot()], [], config=quality_only)
    assert result.verdict == "RATED"
    assert [dimension.name for dimension in result.dimensions] == ["quality"]
    assert [item["name"] for item in result.omitted_dimensions] == ["delivery", "cost"]


def test_ppm_and_otif_indeterminate_propagate_separately() -> None:
    ppm_blocked = calculate_vendor_scorecard(_period(), [], [_delivery()])
    assert ppm_blocked.verdict == "INDETERMINATE"
    assert ppm_blocked.composite_score is None
    assert ppm_blocked.band is None
    assert ppm_blocked.dimensions[0].source_evidence["ppm"] is None
    assert "quality/ppm" in (ppm_blocked.reason or "")

    otif_blocked = calculate_vendor_scorecard(_period(), [_lot()], [])
    assert otif_blocked.verdict == "INDETERMINATE"
    assert otif_blocked.composite_score is None
    assert otif_blocked.band is None
    assert otif_blocked.dimensions[1].source_evidence["otif_pct"] is None
    assert "delivery/otif_pct" in (otif_blocked.reason or "")


def test_source_warnings_recommendations_and_blocker_evidence_are_preserved() -> None:
    result = calculate_vendor_scorecard(
        _period(), [_lot(defects=None)], [_delivery(delivered=None, actual=None)]
    )
    assert result.verdict == "INDETERMINATE"
    assert len(result.dimensions) == 2
    assert all(dimension.source_reason for dimension in result.dimensions)
    assert any(item.startswith("delivery: ") for item in result.warnings)
    assert any(item.startswith("quality: ") for item in result.recommendations)
    assert any(item.startswith("delivery: ") for item in result.recommendations)
    assert "quality/ppm" in (result.reason or "")
    assert "delivery/otif_pct" in (result.reason or "")


def test_band_boundaries_use_unrounded_value() -> None:
    config = ScorecardConfig()
    assert scorecard_module._band_for(100, config) == "A"
    assert scorecard_module._band_for(90, config) == "A"
    assert scorecard_module._band_for(math.nextafter(90.0, -math.inf), config) == "B"
    assert scorecard_module._band_for(math.nextafter(90.0, math.inf), config) == "A"
    assert scorecard_module._band_for(75, config) == "B"
    assert scorecard_module._band_for(math.nextafter(75.0, -math.inf), config) == "C"
    assert scorecard_module._band_for(math.nextafter(75.0, math.inf), config) == "B"
    assert scorecard_module._band_for(0, config) == "C"


def test_public_band_boundaries_with_custom_source_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scorecard_module, "calculate_otif", lambda *a, **k: _source_stub("otif_pct", 0))
    config = ScorecardConfig(quality_weight=1, delivery_weight=0, cost_weight=0)
    for score, expected in [(90.0, "A"), (89.999, "B"), (75.0, "B"), (74.999, "C")]:
        ppm = (100.0 - score) * 100.0
        monkeypatch.setattr(
            scorecard_module, "calculate_supplier_ppm", lambda *a, value=ppm, **k: _source_stub("ppm", value)
        )
        result = calculate_vendor_scorecard(_period(), [], [], config=config)
        assert result.composite_score == pytest.approx(score)
        assert result.band == expected


def test_serialization_is_json_compatible_copy_isolated_and_sums_contributions() -> None:
    result = calculate_vendor_scorecard(_period(), [_lot(defects=5)], [_delivery()])
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["period_start"] == "2026-01-01"
    assert payload["period_end"] == "2026-03-31"
    contributions = [
        dimension["weighted_contribution"]
        for dimension in payload["dimensions"]
        if dimension["weighted_contribution"] is not None
    ]
    assert sum(contributions) == payload["composite_score"]
    payload["dimensions"][0]["source_evidence"]["warnings"].append("changed")
    payload["heuristic_configuration"]["weights"]["quality"]["value"] = -1
    payload["omitted_dimensions"][0]["reason"] = "changed"
    assert "changed" not in result.dimensions[0].source_evidence["warnings"]
    assert result.heuristic_configuration["weights"]["quality"]["value"] == 0.6
    assert result.omitted_dimensions[0]["reason"] != "changed"


def test_manual_dimension_and_indeterminate_result_serialization_none_paths() -> None:
    dimension = ScorecardDimensionResult(
        name="quality",
        source_metric_name="ppm",
        raw_metric=None,
        sub_score=None,
        weight=1.0,
        weighted_contribution=None,
        source_verdict="INDETERMINATE",
        source_reason="none",
        source_evidence={"nested": [{"value": 1}]},
    )
    result = ScorecardResult(
        supplier_id="S",
        period_start=datetime.date(2026, 1, 1),
        period_end=datetime.date(2026, 1, 2),
        period_label=None,
        verdict="INDETERMINATE",
        composite_score=None,
        band=None,
        dimensions=[dimension],
        heuristic_configuration={"x": [1]},
        omitted_dimensions=[],
        reason="blocked",
    )
    payload = result.to_dict()
    assert payload["composite_score"] is None
    assert payload["dimensions"][0]["raw_metric"] is None
    assert payload["dimensions"][0]["weighted_contribution"] is None


def test_inputs_and_caller_configs_are_not_mutated() -> None:
    lots = [_lot()]
    deliveries = [_delivery()]
    items = [{"category": "InternalFailure", "description": "scrap", "direct_cost": 10}]
    config = ScorecardConfig(
        quality_weight=0.4,
        delivery_weight=0.4,
        cost_weight=0.2,
        cost_curve=LinearScoringCurve(0, 10),
    )
    lot_before = lots[0].model_dump()
    delivery_before = deliveries[0].model_dump()
    item_before = dict(items[0])
    config_before = config
    calculate_vendor_scorecard(
        _period(), lots, deliveries, copq_items=items, revenue_base=1_000, config=config
    )
    assert lots[0].model_dump() == lot_before
    assert deliveries[0].model_dump() == delivery_before
    assert items[0] == item_before
    assert config == config_before


def test_no_standard_implied_numeric_criteria_negative_control() -> None:
    payload = calculate_vendor_scorecard(_period(), [_lot()], [_delivery()]).to_dict()
    heuristic = payload["heuristic_configuration"]
    assert heuristic["is_heuristic"] is True
    assert "no standards citation" in heuristic["basis"]

    criteria = [
        *heuristic["weights"].values(),
        *heuristic["rating_bands"].values(),
    ]
    for curve in heuristic["curves"].values():
        if isinstance(curve, dict):
            criteria.extend(curve.values())
    numeric_criteria = [item for item in criteria if isinstance(item, dict) and "value" in item]
    assert len(numeric_criteria) == 9
    for criterion in numeric_criteria:
        assert criterion["is_heuristic"] is True
        assert "no standards citation" in criterion["basis"]
        assert "ISO 9001" not in criterion["basis"]
        assert "IATF 16949" not in criterion["basis"]
    assert "do not define any scorecard weight" in payload["standards_basis"]


def test_cost_curve_defensive_absence_still_suppresses_band() -> None:
    # Public construction rejects this state. The defensive runtime branch still must fail closed.
    config = object.__new__(ScorecardConfig)
    for name, value in ScorecardConfig().__dict__.items():
        object.__setattr__(config, name, value)
    object.__setattr__(config, "quality_weight", 0.5)
    object.__setattr__(config, "delivery_weight", 0.4)
    object.__setattr__(config, "cost_weight", 0.1)
    object.__setattr__(config, "cost_curve", None)
    result = calculate_vendor_scorecard(
        _period(),
        [_lot()],
        [_delivery()],
        copq_items=[CostItem(category="InternalFailure", description="scrap", direct_cost=1)],
        revenue_base=100,
        config=config,
    )
    assert result.verdict == "INDETERMINATE"
    assert result.band is None
    assert "curve is absent" in (result.reason or "")


def test_scorecard_module_does_not_duplicate_source_formulas() -> None:
    source = scorecard_module.__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()  # noqa: PTH123 - inspect installed source
    assert "1_000_000" not in text
    assert "quantity_received *" not in text
    assert "quantity_delivered /" not in text
    assert "total_copq / revenue_base" not in text

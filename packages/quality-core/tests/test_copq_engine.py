"""
test_copq_engine.py
Unit tests and negative control test suite for the COPQ financial estimator engine.
"""

from __future__ import annotations

import pandas as pd
import pytest
from quality_core.copq.estimator import (
    estimate_copq,
)
from quality_core.copq.schema import COPQDataset, CostItem


def test_copq_direct_internal_failure_drivers() -> None:
    """Test individual internal failure cost drivers and their consolidation."""
    res = estimate_copq(
        scrap_qty=50,
        unit_cost=120.0,
        rework_hours=10.0,
        labor_rate=75.0,
        added_material_cost=250.0,
        sort_hours=20.0,
        retest_hours=5.0,
        downtime_hours=4.0,
        downtime_hourly_rate=500.0,
    )

    # Scrap: 50 * 120 = 6000
    # Rework: 10 * 75 + 250 = 1000
    # Containment: 20 * 75 = 1500
    # Retest: 5 * 75 = 375
    # Downtime: 4 * 500 = 2000
    # Total Internal Failure = 6000 + 1000 + 1500 + 375 + 2000 = 10875
    assert res.internal_failure_total == 10875.0
    assert res.external_failure_total == 0.0
    assert res.total_copq == 10875.0
    assert res.cogq_total == 0.0
    assert res.total_coq == 10875.0

    breakdown = res.cost_breakdown["internal_failure"]
    assert breakdown["scrap"] == 6000.0
    assert breakdown["rework"] == 1000.0
    assert breakdown["containment"] == 1500.0
    assert breakdown["retest"] == 375.0
    assert breakdown["downtime"] == 2000.0
    assert breakdown["total"] == 10875.0


def test_copq_containment_hours_alias() -> None:
    """Test that containment_hours works as an alias for sort_hours."""
    res = estimate_copq(
        containment_hours=15.0,
        labor_rate=50.0,
    )
    assert res.internal_failure_total == 750.0
    assert res.cost_breakdown["internal_failure"]["containment"] == 750.0


def test_copq_direct_external_failure_drivers() -> None:
    """Test individual external failure cost drivers and their consolidation."""
    res = estimate_copq(
        warranty_units=15,
        warranty_cost_per_unit=800.0,
        returned_qty=25,
        unit_cost=150.0,
        recall_cost=50000.0,
        concession_qty=200,
        price_reduction_per_unit=15.0,
    )

    # Warranty: 15 * 800 = 12000
    # Returns: 25 * 150 = 3750
    # Recall: 50000
    # Concession: 200 * 15 = 3000
    # Total External Failure = 12000 + 3750 + 50000 + 3000 = 68750
    assert res.external_failure_total == 68750.0
    assert res.internal_failure_total == 0.0
    assert res.total_copq == 68750.0

    breakdown = res.cost_breakdown["external_failure"]
    assert breakdown["warranty"] == 12000.0
    assert breakdown["returns"] == 3750.0
    assert breakdown["recall"] == 50000.0
    assert breakdown["concessions"] == 3000.0
    assert breakdown["total"] == 68750.0


def test_copq_warranty_unit_cost_alias() -> None:
    """Test that warranty_unit_cost works as an alias for warranty_cost_per_unit."""
    res = estimate_copq(
        warranty_units=8,
        warranty_unit_cost=450.0,
    )
    assert res.external_failure_total == 3600.0
    assert res.cost_breakdown["external_failure"]["warranty"] == 3600.0


def test_copq_prevention_and_appraisal_direct() -> None:
    """Test direct prevention and appraisal input rollups."""
    res = estimate_copq(
        prevention_cost=8500.0,
        appraisal_cost=12500.0,
        scrap_qty=10,
        unit_cost=100.0,
    )
    assert res.prevention_total == 8500.0
    assert res.appraisal_total == 12500.0
    assert res.cogq_total == 21000.0
    assert res.internal_failure_total == 1000.0
    assert res.total_copq == 1000.0
    assert res.total_coq == 22000.0


def test_copq_itemized_dataset_ingest() -> None:
    """Test full PAF rollup from itemized CostItem dictionaries."""
    items = [
        {"category": "Prevention", "description": "FMEA training", "direct_cost": 3000.0},
        {"category": "Appraisal", "description": "CMM inspection", "direct_cost": 4000.0},
        {"category": "InternalFailure", "description": "Casting scrap", "scrap_qty": 20, "unit_cost": 100.0},
        {"category": "ExternalFailure", "description": "Field replacement", "warranty_units": 5, "warranty_unit_cost": 500.0},
    ]
    res = estimate_copq(items=items, revenue_base=500000.0)

    assert res.item_count == 4
    assert res.prevention_total == 3000.0
    assert res.appraisal_total == 4000.0
    assert res.internal_failure_total == 2000.0
    assert res.external_failure_total == 2500.0
    assert res.cogq_total == 7000.0
    assert res.total_copq == 4500.0
    assert res.total_coq == 11500.0
    assert res.copq_percentage_of_revenue == 0.9
    assert res.failure_cost_ratio["internal_failure_pct"] == round(2000.0 / 4500.0 * 100.0, 2)
    assert res.failure_cost_ratio["external_failure_pct"] == round(2500.0 / 4500.0 * 100.0, 2)


def test_copq_itemized_costitem_objects_and_copqdataset() -> None:
    """Test passing CostItem instances and COPQDataset objects."""
    cost_items = [
        CostItem(category="Prevention", description="DOE Study", direct_cost=5000.0),
        CostItem(category="InternalFailure", description="Rework", rework_hours=20.0, labor_rate=60.0),
    ]
    res = estimate_copq(items=cost_items)
    assert res.item_count == 2
    assert res.prevention_total == 5000.0
    assert res.internal_failure_total == 1200.0
    assert res.total_copq == 1200.0

    dataset = COPQDataset(items=cost_items, revenue_base=200000.0)
    res_ds = estimate_copq(items=dataset)
    assert res_ds.item_count == 2
    assert res_ds.total_copq == 1200.0
    assert res_ds.revenue_base == 200000.0
    assert res_ds.copq_percentage_of_revenue == round((1200.0 / 200000.0) * 100.0, 4)

    # Explicit override precedence over dataset revenue_base
    res_override = estimate_copq(items=dataset, revenue_base=500000.0)
    assert res_override.revenue_base == 500000.0
    assert res_override.copq_percentage_of_revenue == round((1200.0 / 500000.0) * 100.0, 4)


def test_copq_validated_dataset_dict_revenue_base_fallback() -> None:
    """Test that dictionary data validated to COPQDataset falls back to dataset revenue_base."""
    raw_data = {
        "items": [
            {"category": "InternalFailure", "description": "Casting scrap", "scrap_qty": 20, "unit_cost": 100.0},
        ],
        "revenue_base": 400000.0,
    }
    res = estimate_copq(items=raw_data)
    assert res.revenue_base == 400000.0
    assert res.total_copq == 2000.0
    assert res.copq_percentage_of_revenue == round((2000.0 / 400000.0) * 100.0, 4)

    # Explicit override precedence on validated dict ingest
    res_override = estimate_copq(items=raw_data, revenue_base=800000.0)
    assert res_override.revenue_base == 800000.0
    assert res_override.copq_percentage_of_revenue == round((2000.0 / 800000.0) * 100.0, 4)


def test_copq_dataframe_input() -> None:
    """Test passing a pandas DataFrame as items."""
    df = pd.DataFrame([
        {"category": "Prevention", "description": "Training", "direct_cost": 1500.0},
        {"category": "ExternalFailure", "description": "Warranty", "warranty_units": 4, "warranty_unit_cost": 250.0},
    ])
    res = estimate_copq(items=df)
    assert res.item_count == 2
    assert res.prevention_total == 1500.0
    assert res.external_failure_total == 1000.0
    assert res.total_copq == 1000.0


def test_copq_combined_items_and_direct_drivers() -> None:
    """Test combining itemized dataset with additional direct incident drivers."""
    items = [
        {"category": "Prevention", "description": "SOP authoring", "direct_cost": 2000.0},
    ]
    res = estimate_copq(
        items=items,
        scrap_qty=10,
        unit_cost=50.0,
        prevention_cost=1000.0,
    )
    assert res.prevention_total == 3000.0
    assert res.internal_failure_total == 500.0
    assert res.total_copq == 500.0
    assert res.total_coq == 3500.0


def test_copq_percentage_of_revenue_calculation() -> None:
    """Test COPQ percentage of revenue calculations with valid, zero, and missing revenue base."""
    res_with_rev = estimate_copq(scrap_qty=100, unit_cost=50.0, revenue_base=1000000.0)
    assert res_with_rev.revenue_base == 1000000.0
    assert res_with_rev.copq_percentage_of_revenue == 0.5

    res_no_rev = estimate_copq(scrap_qty=100, unit_cost=50.0, revenue_base=None)
    assert res_no_rev.revenue_base is None
    assert res_no_rev.copq_percentage_of_revenue is None
    assert any("Provide revenue_base ($) to calculate COPQ as a percentage of product/organization sales." in r for r in res_no_rev.recommendations)
    assert not any("revenue_base must be greater than 0.0" in w for w in res_no_rev.warnings)

    res_zero = estimate_copq(scrap_qty=100, unit_cost=50.0, revenue_base=0.0)
    assert res_zero.revenue_base == 0.0
    assert res_zero.copq_percentage_of_revenue is None
    assert any(
        "revenue_base must be greater than 0.0 to calculate COPQ as a percentage of revenue; received 0.0." in w
        for w in res_zero.warnings
    )
    assert any(
        "Provide a positive revenue_base ($ > 0.0) to calculate COPQ as a percentage of product/organization sales." in r
        for r in res_zero.recommendations
    )
    assert not any(
        r == "Provide revenue_base ($) to calculate COPQ as a percentage of product/organization sales."
        for r in res_zero.recommendations
    )


def test_copq_external_failure_exceeds_internal_warning() -> None:
    """Test warning triggered when external failure exceeds internal failure."""
    res = estimate_copq(
        scrap_qty=10,
        unit_cost=100.0,  # $1,000 internal
        warranty_units=10,
        warranty_cost_per_unit=500.0,  # $5,000 external
    )
    assert any("exceed internal failure costs" in w for w in res.warnings)
    assert any("Prioritize immediate containment" in r for r in res.recommendations)


def test_copq_failure_dominance_over_cogq_recommendation() -> None:
    """Test recommendation triggered when COPQ exceeds 3x CoGQ."""
    res = estimate_copq(
        prevention_cost=1000.0,
        appraisal_cost=1000.0,  # CoGQ = $2,000
        scrap_qty=100,
        unit_cost=100.0,  # COPQ = $10,000 (> 3 * 2000)
    )
    assert any("Shift budget into Prevention" in r for r in res.recommendations)


def test_copq_empty_inputs_handling() -> None:
    """Test that empty inputs evaluate to $0.00 with appropriate warning."""
    res = estimate_copq()
    assert res.total_copq == 0.0
    assert res.total_coq == 0.0
    assert res.failure_cost_ratio["internal_failure_pct"] == 0.0
    assert res.failure_cost_ratio["external_failure_pct"] == 0.0
    assert any("No cost drivers or items provided" in w for w in res.warnings)


def test_copq_missing_paired_cost_drivers_warnings() -> None:
    """Test that supplying one driver parameter without its multiplier generates warnings and $0.00 cost."""
    res = estimate_copq(
        scrap_qty=50,  # unit_cost missing
        rework_hours=10.0,  # labor_rate missing
        sort_hours=5.0,  # labor_rate missing
        retest_hours=3.0,  # labor_rate missing
        downtime_hours=2.0,  # downtime_hourly_rate missing
        warranty_units=5,  # warranty_cost_per_unit missing
        returned_qty=8,  # unit_cost missing
        concession_qty=100,  # price_reduction_per_unit missing
    )
    assert res.total_copq == 0.0
    assert any("scrap_qty was provided without unit_cost" in w for w in res.warnings)
    assert any("rework_hours was provided without labor_rate" in w for w in res.warnings)
    assert any("sort_hours / containment_hours provided without labor_rate" in w for w in res.warnings)
    assert any("retest_hours was provided without labor_rate" in w for w in res.warnings)
    assert any("downtime_hours was provided without downtime_hourly_rate" in w for w in res.warnings)
    assert any("warranty_units provided without warranty_cost_per_unit" in w for w in res.warnings)
    assert any("returned_qty was provided without unit_cost" in w for w in res.warnings)
    assert any("concession_qty was provided without price_reduction_per_unit" in w for w in res.warnings)


def test_copq_to_dict_serialization() -> None:
    """Test to_dict serialization of COPQEstimationResult."""
    res = estimate_copq(scrap_qty=10, unit_cost=50.0, title="Test COPQ")
    d = res.to_dict()
    assert isinstance(d, dict)
    assert d["title"] == "Test COPQ"
    assert d["total_copq"] == 500.0
    assert "standards_basis" in d


def test_copq_alias_parameter_conflicts_and_matches() -> None:
    """Test alias conflict warnings when differing values are provided, and clean execution when values match."""
    # sort_hours vs containment_hours conflict
    res_sort_conflict = estimate_copq(
        sort_hours=10.0,
        containment_hours=20.0,
        labor_rate=50.0,
    )
    assert res_sort_conflict.internal_failure_total == 500.0
    assert res_sort_conflict.cost_breakdown["internal_failure"]["containment"] == 500.0
    assert any(
        "Conflicting values provided for sort_hours (10.0) and containment_hours (20.0); using sort_hours=10.0." in w
        for w in res_sort_conflict.warnings
    )

    # warranty_cost_per_unit vs warranty_unit_cost conflict
    res_w_conflict = estimate_copq(
        warranty_units=5,
        warranty_cost_per_unit=300.0,
        warranty_unit_cost=400.0,
    )
    assert res_w_conflict.external_failure_total == 1500.0
    assert res_w_conflict.cost_breakdown["external_failure"]["warranty"] == 1500.0
    assert any(
        "Conflicting values provided for warranty_cost_per_unit (300.0) and warranty_unit_cost (400.0); using warranty_cost_per_unit=300.0." in w
        for w in res_w_conflict.warnings
    )

    # Matching alias values (no conflict warnings)
    res_sort_match = estimate_copq(
        sort_hours=15.0,
        containment_hours=15.0,
        labor_rate=50.0,
    )
    assert res_sort_match.internal_failure_total == 750.0
    assert not any("Conflicting values provided for sort_hours" in w for w in res_sort_match.warnings)

    res_w_match = estimate_copq(
        warranty_units=4,
        warranty_cost_per_unit=250.0,
        warranty_unit_cost=250.0,
    )
    assert res_w_match.external_failure_total == 1000.0
    assert not any("Conflicting values provided for warranty_cost_per_unit" in w for w in res_w_match.warnings)


# ---------------------------------------------------------------------------
# Negative Controls and Exception Handling Tests
# ---------------------------------------------------------------------------

def test_negative_control_invalid_title() -> None:
    """Non-string title must raise TypeError; empty or whitespace string title must raise ValueError."""
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        estimate_copq(title="")
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        estimate_copq(title="   ")
    with pytest.raises(TypeError, match="title must be a string"):
        estimate_copq(title=123)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="title must be a string"):
        estimate_copq(title=None)  # type: ignore[arg-type]


def test_negative_control_negative_quantities() -> None:
    """Negative integer quantities must raise ValueError."""
    with pytest.raises(ValueError, match="scrap_qty must be >= 0"):
        estimate_copq(scrap_qty=-5)
    with pytest.raises(ValueError, match="warranty_units must be >= 0"):
        estimate_copq(warranty_units=-1)
    with pytest.raises(ValueError, match="returned_qty must be >= 0"):
        estimate_copq(returned_qty=-10)
    with pytest.raises(ValueError, match="concession_qty must be >= 0"):
        estimate_copq(concession_qty=-20)


def test_negative_control_boolean_as_numeric() -> None:
    """Booleans passed for numeric parameters must raise TypeError."""
    with pytest.raises(TypeError, match="scrap_qty cannot be a boolean"):
        estimate_copq(scrap_qty=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unit_cost cannot be a boolean"):
        estimate_copq(unit_cost=False)  # type: ignore[arg-type]


def test_negative_control_negative_floats() -> None:
    """Negative float values must raise ValueError."""
    with pytest.raises(ValueError, match="unit_cost must be >= 0.0"):
        estimate_copq(unit_cost=-10.0)
    with pytest.raises(ValueError, match="rework_hours must be >= 0.0"):
        estimate_copq(rework_hours=-2.5)
    with pytest.raises(ValueError, match="labor_rate must be >= 0.0"):
        estimate_copq(labor_rate=-50.0)
    with pytest.raises(ValueError, match="revenue_base must be >= 0.0"):
        estimate_copq(revenue_base=-100000.0)


def test_negative_control_nan_and_inf_floats() -> None:
    """NaN and Infinite floats must raise ValueError."""
    with pytest.raises(ValueError, match="must be a finite number"):
        estimate_copq(unit_cost=float("nan"))
    with pytest.raises(ValueError, match="must be a finite number"):
        estimate_copq(labor_rate=float("inf"))


def test_negative_control_invalid_types() -> None:
    """Passing invalid string or object types for numeric drivers must raise TypeError."""
    with pytest.raises(TypeError, match="scrap_qty must be an integer or None"):
        estimate_copq(scrap_qty="50")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unit_cost must be a number or None"):
        estimate_copq(unit_cost="120.0")  # type: ignore[arg-type]


def test_negative_control_invalid_items_element() -> None:
    """Passing non-CostItem/non-dict element in items list must raise TypeError."""
    with pytest.raises(TypeError, match="items element at index 0 must be CostItem or dict"):
        estimate_copq(items=["invalid_string"])  # type: ignore[list-item]

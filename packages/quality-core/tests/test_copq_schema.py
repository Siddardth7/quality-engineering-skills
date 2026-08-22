"""
Tests for quality_core.copq.schema and quality_core.copq module exports.

Covers:
- PAFCategory literal, values, aliases, case-insensitivity, and normalization
- CostItem row model, string stripping, blank rejection, cost-driver numeric bounds, total_cost computation
- COPQDataset dataset model, empty checks, revenue_base validation, rollup properties (total_cost, prevention_cost, appraisal_cost, internal_failure_cost, external_failure_cost, copq, cogq, copq_pct_revenue)
- COPQ_SCHEMA TableSchema descriptor
- load_copq_csv ingestion helper (str path and BinaryIO buffer, error formatting)
- validate_copq trust-boundary validator (COPQDataset, DataFrame, list of dicts/items, dict, revenue_base forwarding, invalid types)
- Negative controls and error handling
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd
import pydantic
import pytest
import quality_core.copq as copq
from quality_core.copq import (
    COPQ_SCHEMA,
    PAF_CATEGORY_ALIASES,
    PAF_CATEGORY_VALUES,
    COPQDataset,
    CostItem,
    IngestError,
    PAFCategory,
    load_copq_csv,
    validate_copq,
)

# ==============================================================================
# Helper functions
# ==============================================================================


def _csv_buf(rows: list[dict[str, Any]], name: str = "copq_upload.csv") -> io.BytesIO:
    buf = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode("utf-8"))
    buf.name = name
    return buf


def _valid_cost_item_dict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "category": "InternalFailure",
        "description": "CNC Machining scrap on housing bore",
        "scrap_qty": 20,
        "unit_cost": 45.5,
        "rework_hours": None,
        "labor_rate": None,
        "containment_hours": None,
        "warranty_units": None,
        "warranty_unit_cost": None,
        "direct_cost": None,
    }
    base.update(overrides)
    return base


# ==============================================================================
# 0. Module exports & IngestError tests
# ==============================================================================


def test_copq_module_all_exports() -> None:
    expected_exports = {
        "PAFCategory",
        "PAF_CATEGORY_VALUES",
        "PAF_CATEGORY_ALIASES",
        "CostItem",
        "COPQDataset",
        "COPQEstimationResult",
        "COPQ_SCHEMA",
        "estimate_copq",
        "load_copq_csv",
        "validate_copq",
        "IngestError",
    }
    assert set(copq.__all__) == expected_exports
    for symbol in expected_exports:
        assert hasattr(copq, symbol)


def test_ingest_error_is_subclass_of_value_error() -> None:
    assert issubclass(IngestError, ValueError)
    err = IngestError("COPQ Ingest failed")
    assert isinstance(err, ValueError)
    assert str(err) == "COPQ Ingest failed"


# ==============================================================================
# 1. PAFCategory literal, values, and alias normalization
# ==============================================================================


def test_paf_category_values_tuple() -> None:
    assert PAF_CATEGORY_VALUES == (
        "Prevention",
        "Appraisal",
        "InternalFailure",
        "ExternalFailure",
    )


@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        ("Prevention", "Prevention"),
        ("prevention", "Prevention"),
        ("p", "Prevention"),
        ("prev", "Prevention"),
        ("preventive", "Prevention"),
        ("preventative", "Prevention"),
        ("  PREVENTION  ", "Prevention"),
        ("Appraisal", "Appraisal"),
        ("appraisal", "Appraisal"),
        ("a", "Appraisal"),
        ("appr", "Appraisal"),
        ("inspection", "Appraisal"),
        ("testing", "Appraisal"),
        ("audit", "Appraisal"),
        ("  INSPECTION  ", "Appraisal"),
        ("InternalFailure", "InternalFailure"),
        ("internal failure", "InternalFailure"),
        ("internal_failure", "InternalFailure"),
        ("internalfailure", "InternalFailure"),
        ("internal", "InternalFailure"),
        ("if", "InternalFailure"),
        ("internal failures", "InternalFailure"),
        ("internal_failures", "InternalFailure"),
        ("  INTERNAL FAILURE  ", "InternalFailure"),
        ("ExternalFailure", "ExternalFailure"),
        ("external failure", "ExternalFailure"),
        ("external_failure", "ExternalFailure"),
        ("externalfailure", "ExternalFailure"),
        ("external", "ExternalFailure"),
        ("ef", "ExternalFailure"),
        ("external failures", "ExternalFailure"),
        ("external_failures", "ExternalFailure"),
        ("  EXTERNAL FAILURE  ", "ExternalFailure"),
    ],
)
def test_paf_category_normalization_all_cases(input_val: str, expected: PAFCategory) -> None:
    item = CostItem(category=input_val, description="Test cost item")  # type: ignore[arg-type]
    assert item.category == expected


@pytest.mark.parametrize("blank_val", ["", "   ", "\t\n"])
def test_paf_category_blank_rejected(blank_val: str) -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be blank or whitespace-only"):
        CostItem(category=blank_val, description="Test cost item")  # type: ignore[arg-type]


def test_paf_category_invalid_string_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="Invalid PAF category"):
        CostItem(category="UnknownCategory", description="Test cost item")  # type: ignore[arg-type]


def test_paf_category_non_string_passthrough() -> None:
    # Non-string object passes through validator and is caught by Pydantic literal validation
    with pytest.raises(pydantic.ValidationError):
        CostItem(category=999, description="Test cost item")  # type: ignore[arg-type]


# ==============================================================================
# 2. CostItem row model tests
# ==============================================================================


def test_cost_item_minimal_defaults() -> None:
    item = CostItem(category="Prevention", description="FMEA Facilitation Workshop")
    assert item.category == "Prevention"
    assert item.description == "FMEA Facilitation Workshop"
    assert item.scrap_qty is None
    assert item.unit_cost is None
    assert item.rework_hours is None
    assert item.labor_rate is None
    assert item.containment_hours is None
    assert item.warranty_units is None
    assert item.warranty_unit_cost is None
    assert item.direct_cost is None
    assert item.total_cost == 0.0


def test_cost_item_full_instantiation() -> None:
    data = _valid_cost_item_dict(
        category="ExternalFailure",
        description="Field recall warranty replacement",
        warranty_units=50,
        warranty_unit_cost=120.0,
        direct_cost=5000.0,
    )
    item = CostItem(**data)
    assert item.category == "ExternalFailure"
    assert item.description == "Field recall warranty replacement"
    assert item.warranty_units == 50
    assert item.warranty_unit_cost == 120.0
    assert item.direct_cost == 5000.0


@pytest.mark.parametrize("blank_val", ["", "   ", "\t\n\r"])
def test_cost_item_rejects_blank_description(blank_val: str) -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be blank or whitespace-only"):
        CostItem(category="Appraisal", description=blank_val)


def test_cost_item_strips_description() -> None:
    item = CostItem(category="Appraisal", description="   Gage Calibration Audit   ")
    assert item.description == "Gage Calibration Audit"


def test_cost_item_non_string_description_passthrough() -> None:
    with pytest.raises(pydantic.ValidationError):
        CostItem(category="Appraisal", description=12345)  # type: ignore[arg-type]


def test_cost_item_description_max_length() -> None:
    huge_desc = "A" * 2001
    with pytest.raises(pydantic.ValidationError):
        CostItem(category="Appraisal", description=huge_desc)


@pytest.mark.parametrize(
    ("field_name", "invalid_val"),
    [
        ("scrap_qty", -1),
        ("unit_cost", -0.01),
        ("unit_cost", float("inf")),
        ("unit_cost", float("nan")),
        ("rework_hours", -1.0),
        ("labor_rate", -25.0),
        ("containment_hours", -0.5),
        ("warranty_units", -5),
        ("warranty_unit_cost", -10.0),
        ("direct_cost", -100.0),
    ],
)
def test_cost_item_rejects_negative_and_nan_inf_drivers(field_name: str, invalid_val: Any) -> None:
    data = _valid_cost_item_dict(**{field_name: invalid_val})
    with pytest.raises(pydantic.ValidationError):
        CostItem(**data)


# ==============================================================================
# 3. CostItem total_cost driver computation tests
# ==============================================================================


def test_cost_item_total_cost_scrap_only() -> None:
    item = CostItem(
        category="InternalFailure",
        description="Scrap",
        scrap_qty=10,
        unit_cost=25.0,
    )
    assert item.total_cost == 250.0


def test_cost_item_total_cost_rework_only() -> None:
    item = CostItem(
        category="InternalFailure",
        description="Rework",
        rework_hours=5.5,
        labor_rate=40.0,
    )
    assert item.total_cost == 220.0


def test_cost_item_total_cost_containment_only() -> None:
    item = CostItem(
        category="InternalFailure",
        description="Containment sorting",
        containment_hours=8.0,
        labor_rate=50.0,
    )
    assert item.total_cost == 400.0


def test_cost_item_total_cost_warranty_only() -> None:
    item = CostItem(
        category="ExternalFailure",
        description="Warranty replacements",
        warranty_units=12,
        warranty_unit_cost=150.0,
    )
    assert item.total_cost == 1800.0


def test_cost_item_total_cost_direct_cost_only() -> None:
    item = CostItem(
        category="Prevention",
        description="Supplier Quality Training Consultant",
        direct_cost=3500.0,
    )
    assert item.total_cost == 3500.0


def test_cost_item_total_cost_combined_drivers() -> None:
    item = CostItem(
        category="InternalFailure",
        description="Comprehensive failure event",
        scrap_qty=5,
        unit_cost=100.0,  # 500
        rework_hours=10.0,
        labor_rate=50.0,  # 500
        containment_hours=4.0,  # 4 * 50 = 200
        direct_cost=300.0,  # 300
    )
    assert item.total_cost == (500.0 + 500.0 + 200.0 + 300.0)


def test_cost_item_total_cost_partial_driver_pairs_zero() -> None:
    # scrap_qty set but unit_cost is None
    i1 = CostItem(category="InternalFailure", description="Partial 1", scrap_qty=10)
    assert i1.total_cost == 0.0

    # unit_cost set but scrap_qty is None
    i2 = CostItem(category="InternalFailure", description="Partial 2", unit_cost=50.0)
    assert i2.total_cost == 0.0

    # rework_hours set but labor_rate is None
    i3 = CostItem(category="InternalFailure", description="Partial 3", rework_hours=10.0)
    assert i3.total_cost == 0.0

    # containment_hours set but labor_rate is None
    i4 = CostItem(category="InternalFailure", description="Partial 4", containment_hours=5.0)
    assert i4.total_cost == 0.0

    # warranty_units set but warranty_unit_cost is None
    i5 = CostItem(category="ExternalFailure", description="Partial 5", warranty_units=3)
    assert i5.total_cost == 0.0

    # warranty_unit_cost set but warranty_units is None
    i6 = CostItem(category="ExternalFailure", description="Partial 6", warranty_unit_cost=100.0)
    assert i6.total_cost == 0.0


# ==============================================================================
# 4. COPQDataset model & Rollup properties tests
# ==============================================================================


def test_copq_dataset_instantiation() -> None:
    i1 = CostItem(category="Prevention", description="Design Review", direct_cost=1000.0)
    i2 = CostItem(category="Appraisal", description="CMM Inspection", direct_cost=500.0)
    ds = COPQDataset(items=[i1, i2], revenue_base=500000.0)
    assert len(ds.items) == 2
    assert ds.rows == [i1, i2]
    assert ds.revenue_base == 500000.0


def test_copq_dataset_empty_items_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="COPQDataset must contain at least one item"):
        COPQDataset(items=[])


@pytest.mark.parametrize("bad_rev", [0.0, -100.0, -0.01, float("inf"), float("nan")])
def test_copq_dataset_invalid_revenue_base_rejected(bad_rev: float) -> None:
    i1 = CostItem(category="Prevention", description="Training", direct_cost=100.0)
    with pytest.raises(pydantic.ValidationError):
        COPQDataset(items=[i1], revenue_base=bad_rev)


def test_copq_dataset_rows_alias_in_dict_coercion() -> None:
    raw_dict = {
        "rows": [
            _valid_cost_item_dict(description="Item 1"),
            _valid_cost_item_dict(description="Item 2"),
        ]
    }
    ds = COPQDataset.model_validate(raw_dict)
    assert len(ds.items) == 2
    assert ds.items[0].description == "Item 1"
    assert ds.items[1].description == "Item 2"


def test_copq_dataset_coercion_non_dict_passthrough() -> None:
    res = COPQDataset._coerce_rows_to_items("not a dict")
    assert res == "not a dict"


def test_copq_dataset_coercion_both_rows_and_items_keeps_items() -> None:
    raw_dict = {
        "items": [_valid_cost_item_dict(description="Item Keep")],
        "rows": [_valid_cost_item_dict(description="Item Ignore")],
    }
    ds = COPQDataset.model_validate(raw_dict)
    assert len(ds.items) == 1
    assert ds.items[0].description == "Item Keep"


def test_copq_dataset_arithmetic_rollups() -> None:
    p1 = CostItem(category="Prevention", description="Training", direct_cost=2000.0)
    p2 = CostItem(category="Prevention", description="Control Plan Review", direct_cost=1000.0)
    a1 = CostItem(category="Appraisal", description="Final Inspection", direct_cost=1500.0)
    i1 = CostItem(category="InternalFailure", description="Scrap", scrap_qty=100, unit_cost=50.0)  # 5000
    e1 = CostItem(category="ExternalFailure", description="Warranty", warranty_units=10, warranty_unit_cost=300.0)  # 3000

    ds = COPQDataset(
        items=[p1, p2, a1, i1, e1],
        revenue_base=100000.0,
    )

    assert ds.prevention_cost == 3000.0
    assert ds.appraisal_cost == 1500.0
    assert ds.internal_failure_cost == 5000.0
    assert ds.external_failure_cost == 3000.0
    assert ds.copq == 8000.0  # 5000 + 3000
    assert ds.cogq == 4500.0  # 3000 + 1500
    assert ds.total_cost == 12500.0  # 3000 + 1500 + 5000 + 3000
    assert ds.copq_pct_revenue == 8.0  # (8000 / 100000) * 100


def test_copq_dataset_copq_pct_revenue_none_when_revenue_base_is_none() -> None:
    i1 = CostItem(category="InternalFailure", description="Scrap", direct_cost=500.0)
    ds = COPQDataset(items=[i1], revenue_base=None)
    assert ds.copq_pct_revenue is None


# ==============================================================================
# 5. COPQ_SCHEMA TableSchema tests
# ==============================================================================


def test_copq_schema_descriptor() -> None:
    assert COPQ_SCHEMA.name == "Cost of Poor Quality"
    assert COPQ_SCHEMA.row_model == CostItem
    assert COPQ_SCHEMA.required_columns == ("category", "description")
    assert COPQ_SCHEMA.optional_columns == (
        "scrap_qty",
        "unit_cost",
        "rework_hours",
        "labor_rate",
        "containment_hours",
        "warranty_units",
        "warranty_unit_cost",
        "direct_cost",
    )
    assert COPQ_SCHEMA.dataset_model == COPQDataset
    assert COPQ_SCHEMA.template_hint == "data/copq_template.csv"


# ==============================================================================
# 6. load_copq_csv tests
# ==============================================================================


def test_load_copq_csv_from_buffer() -> None:
    rows = [
        _valid_cost_item_dict(description="Scrap part A", scrap_qty=10, unit_cost=5.0),
        _valid_cost_item_dict(description="Scrap part B", scrap_qty=20, unit_cost=15.0),
    ]
    buf = _csv_buf(rows)
    df = load_copq_csv(buf)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "category" in df.columns
    assert "description" in df.columns
    assert "scrap_qty" in df.columns


def test_load_copq_csv_from_file_path(tmp_path: Path) -> None:
    rows = [_valid_cost_item_dict(description="File cost item")]
    csv_file = tmp_path / "copq_test.csv"
    pd.DataFrame(rows).to_csv(csv_file, index=False)

    df = load_copq_csv(str(csv_file))
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]["description"] == "File cost item"


def test_load_copq_csv_missing_required_column_raises_ingest_error() -> None:
    rows = [
        {"category": "Prevention"}  # missing description
    ]
    buf = _csv_buf(rows)
    with pytest.raises(IngestError, match="Missing required column"):
        load_copq_csv(buf)


def test_load_copq_csv_malformed_row_raises_ingest_error() -> None:
    rows = [
        _valid_cost_item_dict(scrap_qty=-5),  # negative scrap_qty
    ]
    buf = _csv_buf(rows)
    with pytest.raises(IngestError, match="Row 2, column 'scrap_qty'"):
        load_copq_csv(buf)


def test_load_copq_csv_narrows_extra_columns() -> None:
    rows = [
        _valid_cost_item_dict(department="Machining Shop", cost_center=4412),
    ]
    buf = _csv_buf(rows)
    df = load_copq_csv(buf)
    assert "department" not in df.columns
    assert "cost_center" not in df.columns
    assert "category" in df.columns


# ==============================================================================
# 7. validate_copq trust-boundary validator tests
# ==============================================================================


def test_validate_copq_from_copq_dataset_without_revenue_base() -> None:
    ds = COPQDataset(items=[CostItem(**_valid_cost_item_dict())], revenue_base=250000.0)
    validated = validate_copq(ds)
    assert validated is ds


def test_validate_copq_from_copq_dataset_with_revenue_base_override() -> None:
    ds = COPQDataset(items=[CostItem(**_valid_cost_item_dict())], revenue_base=250000.0)
    validated = validate_copq(ds, revenue_base=750000.0)
    assert validated is not ds
    assert validated.revenue_base == 750000.0
    assert len(validated.items) == 1


def test_validate_copq_from_dataframe() -> None:
    df = pd.DataFrame([_valid_cost_item_dict(description="DF cost item")])
    validated = validate_copq(df, revenue_base=500000.0)
    assert isinstance(validated, COPQDataset)
    assert len(validated.items) == 1
    assert validated.items[0].description == "DF cost item"
    assert validated.revenue_base == 500000.0


def test_validate_copq_from_dataframe_with_nan() -> None:
    df = pd.DataFrame(
        [
            {
                "category": "Prevention",
                "description": "DF with NaN",
                "scrap_qty": float("nan"),
                "unit_cost": float("nan"),
                "rework_hours": float("nan"),
                "labor_rate": float("nan"),
                "containment_hours": float("nan"),
                "warranty_units": float("nan"),
                "warranty_unit_cost": float("nan"),
                "direct_cost": float("nan"),
            }
        ]
    )
    validated = validate_copq(df)
    assert len(validated.items) == 1
    assert validated.items[0].scrap_qty is None
    assert validated.items[0].direct_cost is None


def test_validate_copq_from_list_of_dicts() -> None:
    data = [
        _valid_cost_item_dict(description="Item 1"),
        _valid_cost_item_dict(description="Item 2"),
    ]
    validated = validate_copq(data, revenue_base=100000.0)
    assert isinstance(validated, COPQDataset)
    assert len(validated.items) == 2
    assert validated.revenue_base == 100000.0


def test_validate_copq_from_list_of_items() -> None:
    i1 = CostItem(**_valid_cost_item_dict(description="Item A"))
    i2 = CostItem(**_valid_cost_item_dict(description="Item B"))
    validated = validate_copq([i1, i2], revenue_base=200000.0)
    assert isinstance(validated, COPQDataset)
    assert len(validated.items) == 2
    assert validated.items[0] is i1
    assert validated.items[1] is i2
    assert validated.revenue_base == 200000.0


def test_validate_copq_from_mixed_list() -> None:
    i1 = CostItem(**_valid_cost_item_dict(description="Item A"))
    d2 = _valid_cost_item_dict(description="Item B")
    validated = validate_copq([i1, d2])
    assert isinstance(validated, COPQDataset)
    assert len(validated.items) == 2
    assert validated.items[0].description == "Item A"
    assert validated.items[1].description == "Item B"


def test_validate_copq_from_dict_with_revenue_base() -> None:
    data = {
        "items": [
            _valid_cost_item_dict(description="Dict Item"),
        ],
        "revenue_base": 300000.0,
    }
    validated = validate_copq(data)
    assert isinstance(validated, COPQDataset)
    assert len(validated.items) == 1
    assert validated.revenue_base == 300000.0


def test_validate_copq_from_dict_with_revenue_base_parameter_injection() -> None:
    data = {
        "items": [
            _valid_cost_item_dict(description="Dict Item"),
        ]
    }
    validated = validate_copq(data, revenue_base=450000.0)
    assert validated.revenue_base == 450000.0


def test_validate_copq_from_dict_with_none_fields() -> None:
    data = {
        "items": [
            {
                "category": "Appraisal",
                "description": "Dict with None",
                "direct_cost": None,
            }
        ]
    }
    validated = validate_copq(data)
    assert len(validated.items) == 1
    assert validated.items[0].direct_cost is None


def test_validate_copq_invalid_list_item_type_raises_type_error() -> None:
    with pytest.raises(TypeError, match="Expected CostItem or dict in list, got int"):
        validate_copq([123])  # type: ignore[list-item]


@pytest.mark.parametrize("invalid_input", [12345, "invalid string", True, 3.14])
def test_validate_copq_unsupported_root_type_raises_type_error(invalid_input: Any) -> None:
    with pytest.raises(TypeError, match="Expected COPQDataset, DataFrame, list of dicts/items, or dict"):
        validate_copq(invalid_input)


def test_validate_copq_invalid_item_content_raises_validation_error() -> None:
    invalid_data = [{"category": "InvalidCategory"}]
    with pytest.raises(pydantic.ValidationError):
        validate_copq(invalid_data)


def test_copq_field_validators_non_string_passthrough() -> None:
    assert CostItem.normalize_category(123) == 123
    assert CostItem.reject_blank_description(123) == 123


def test_copq_normalize_category_direct_value_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quality_core.copq.schema.PAF_CATEGORY_ALIASES",
        {k: v for k, v in PAF_CATEGORY_ALIASES.items() if k != "prevention"},
    )
    assert CostItem.normalize_category("Prevention") == "Prevention"


"""
Tests for quality_core.ncr.schema and quality_core.ncr module exports.

Covers:
- Disposition enum, aliases, case-insensitivity, and normalization
- NonconformanceRecord row model, string stripping, blank rejection, quantity bounds, optional fields
- NCRDataset dataset model, empty checks, duplicate record_id detection, rows property, rows-to-records coercion
- NCR_SCHEMA TableSchema descriptor
- load_ncr_csv ingestion helper (str path and BinaryIO buffer, error formatting)
- validate_ncr trust-boundary validator (NCRDataset, DataFrame, list of dicts/records, dict, invalid types)
- Negative controls and error handling
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd
import pydantic
import pytest
import quality_core.ncr as ncr
from quality_core.ncr import (
    DISPOSITION_ALIASES,
    DISPOSITION_VALUES,
    NCR_SCHEMA,
    IngestError,
    NCRDataset,
    NonconformanceRecord,
    load_ncr_csv,
    validate_ncr,
)

# ==============================================================================
# Helper functions
# ==============================================================================


def _csv_buf(rows: list[dict[str, Any]], name: str = "ncr_upload.csv") -> io.BytesIO:
    buf = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode("utf-8"))
    buf.name = name
    return buf


def _valid_ncr_record_dict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "part_lot_id": "LOT-2026-001",
        "defect_description": "Surface porosity exceeds specification",
        "requirement_violated": "Spec-402 Rev C max pore diameter 0.2mm",
        "quantity_affected": 25,
        "detection_point": "Final Inspection Station 4",
        "record_id": "NCR-2026-001",
        "disposition": "Scrap",
        "severity": "Major",
        "rationale": "Porosity compromises structural integrity",
        "approval_authority": "Quality Engineering Manager",
    }
    base.update(overrides)
    return base


# ==============================================================================
# 0. Module exports & IngestError tests
# ==============================================================================


def test_ncr_module_all_exports() -> None:
    expected_exports = {
        "Disposition",
        "DISPOSITION_VALUES",
        "DISPOSITION_ALIASES",
        "NonconformanceRecord",
        "NCRDataset",
        "NCR_SCHEMA",
        "load_ncr_csv",
        "validate_ncr",
        "IngestError",
        "write_nonconformance",
        "recommend_disposition",
        "NonconformanceWriteResult",
        "DispositionRecommendation",
    }
    assert set(ncr.__all__) == expected_exports
    for symbol in expected_exports:
        assert hasattr(ncr, symbol)


def test_ingest_error_is_subclass_of_value_error() -> None:
    assert issubclass(IngestError, ValueError)
    err = IngestError("Ingest failed")
    assert isinstance(err, ValueError)
    assert str(err) == "Ingest failed"


# ==============================================================================
# 1. Disposition literal, values, and alias normalization
# ==============================================================================


def test_disposition_values_tuple() -> None:
    assert DISPOSITION_VALUES == (
        "Scrap",
        "Rework",
        "UseAsIs",
        "ReturnToVendor",
        "Regrade",
    )


@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        ("Scrap", "Scrap"),
        ("scrap", "Scrap"),
        ("scrapped", "Scrap"),
        ("  SCRAP  ", "Scrap"),
        ("Rework", "Rework"),
        ("rework", "Rework"),
        ("re-work", "Rework"),
        ("reworked", "Rework"),
        ("repair", "Rework"),
        ("  REPAIR  ", "Rework"),
        ("UseAsIs", "UseAsIs"),
        ("useasis", "UseAsIs"),
        ("use as is", "UseAsIs"),
        ("use_as_is", "UseAsIs"),
        ("use-as-is", "UseAsIs"),
        ("concession", "UseAsIs"),
        ("deviation", "UseAsIs"),
        ("accept", "UseAsIs"),
        ("  USE AS IS  ", "UseAsIs"),
        ("ReturnToVendor", "ReturnToVendor"),
        ("returntovendor", "ReturnToVendor"),
        ("return to vendor", "ReturnToVendor"),
        ("return_to_vendor", "ReturnToVendor"),
        ("return-to-vendor", "ReturnToVendor"),
        ("rtv", "ReturnToVendor"),
        ("vendor return", "ReturnToVendor"),
        ("vendor_return", "ReturnToVendor"),
        ("supplier return", "ReturnToVendor"),
        ("  RTV  ", "ReturnToVendor"),
        ("Regrade", "Regrade"),
        ("regrade", "Regrade"),
        ("re-grade", "Regrade"),
        ("downgrade", "Regrade"),
        ("down-grade", "Regrade"),
        ("secondary", "Regrade"),
        ("  DOWNGRADE  ", "Regrade"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_disposition_normalization_all_cases(input_val: Any, expected: Any) -> None:
    rec = NonconformanceRecord(
        part_lot_id="LOT-01",
        defect_description="Crack",
        requirement_violated="Spec-01",
        quantity_affected=1,
        detection_point="Op 10",
        disposition=input_val,
    )
    assert rec.disposition == expected


def test_disposition_invalid_string_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="Invalid disposition"):
        NonconformanceRecord(
            part_lot_id="LOT-01",
            defect_description="Crack",
            requirement_violated="Spec-01",
            quantity_affected=1,
            detection_point="Op 10",
            disposition="IgnoreDefect",
        )


def test_disposition_non_string_validator_passthrough() -> None:
    # Non-string object passes through validator and is caught by Pydantic literal type checking
    with pytest.raises(pydantic.ValidationError):
        NonconformanceRecord(
            part_lot_id="LOT-01",
            defect_description="Crack",
            requirement_violated="Spec-01",
            quantity_affected=1,
            detection_point="Op 10",
            disposition=12345,  # type: ignore[arg-type]
        )


# ==============================================================================
# 2. NonconformanceRecord row model tests
# ==============================================================================


def test_nonconformance_record_minimal_defaults() -> None:
    rec = NonconformanceRecord(
        part_lot_id="LOT-999",
        defect_description="Weld bead undersize",
        requirement_violated="AWS D1.1 fillet size 6mm min",
        quantity_affected=10,
        detection_point="Visual Inspection",
    )
    assert rec.part_lot_id == "LOT-999"
    assert rec.defect_description == "Weld bead undersize"
    assert rec.requirement_violated == "AWS D1.1 fillet size 6mm min"
    assert rec.quantity_affected == 10
    assert rec.detection_point == "Visual Inspection"
    assert rec.record_id is None
    assert rec.disposition is None
    assert rec.severity is None
    assert rec.rationale is None
    assert rec.approval_authority is None


def test_nonconformance_record_full_instantiation() -> None:
    data = _valid_ncr_record_dict()
    rec = NonconformanceRecord(**data)
    assert rec.part_lot_id == "LOT-2026-001"
    assert rec.defect_description == "Surface porosity exceeds specification"
    assert rec.requirement_violated == "Spec-402 Rev C max pore diameter 0.2mm"
    assert rec.quantity_affected == 25
    assert rec.detection_point == "Final Inspection Station 4"
    assert rec.record_id == "NCR-2026-001"
    assert rec.disposition == "Scrap"
    assert rec.severity == "Major"
    assert rec.rationale == "Porosity compromises structural integrity"
    assert rec.approval_authority == "Quality Engineering Manager"


@pytest.mark.parametrize(
    "field_name",
    [
        "part_lot_id",
        "defect_description",
        "requirement_violated",
        "detection_point",
    ],
)
@pytest.mark.parametrize("blank_val", ["", "   ", "\t\n\r"])
def test_required_string_fields_reject_blank(field_name: str, blank_val: str) -> None:
    data = _valid_ncr_record_dict(**{field_name: blank_val})
    with pytest.raises(pydantic.ValidationError, match="must not be blank or whitespace-only"):
        NonconformanceRecord(**data)


@pytest.mark.parametrize(
    "field_name",
    [
        "part_lot_id",
        "defect_description",
        "requirement_violated",
        "detection_point",
    ],
)
def test_required_string_fields_stripped(field_name: str) -> None:
    data = _valid_ncr_record_dict(**{field_name: "  Clean Value  "})
    rec = NonconformanceRecord(**data)
    assert getattr(rec, field_name) == "Clean Value"


@pytest.mark.parametrize(
    "field_name",
    [
        "record_id",
        "severity",
        "rationale",
        "approval_authority",
    ],
)
@pytest.mark.parametrize("blank_val", [None, "", "   ", "\t\n"])
def test_optional_string_fields_normalized_to_none(field_name: str, blank_val: Any) -> None:
    data = _valid_ncr_record_dict(**{field_name: blank_val})
    rec = NonconformanceRecord(**data)
    assert getattr(rec, field_name) is None


@pytest.mark.parametrize(
    "field_name",
    [
        "record_id",
        "severity",
        "rationale",
        "approval_authority",
    ],
)
def test_optional_string_fields_stripped(field_name: str) -> None:
    data = _valid_ncr_record_dict(**{field_name: "  Stripped Text  "})
    rec = NonconformanceRecord(**data)
    assert getattr(rec, field_name) == "Stripped Text"


@pytest.mark.parametrize("qty", [0, -1, -50])
def test_quantity_affected_rejects_non_positive(qty: int) -> None:
    data = _valid_ncr_record_dict(quantity_affected=qty)
    with pytest.raises(pydantic.ValidationError):
        NonconformanceRecord(**data)


def test_quantity_affected_accepts_positive() -> None:
    data = _valid_ncr_record_dict(quantity_affected=1)
    rec = NonconformanceRecord(**data)
    assert rec.quantity_affected == 1

    data = _valid_ncr_record_dict(quantity_affected=10000)
    rec = NonconformanceRecord(**data)
    assert rec.quantity_affected == 10000


def test_field_length_exceeded_rejected() -> None:
    huge_str = "A" * 2001
    data = _valid_ncr_record_dict(part_lot_id=huge_str)
    with pytest.raises(pydantic.ValidationError):
        NonconformanceRecord(**data)


# ==============================================================================
# 3. NCRDataset model tests
# ==============================================================================


def test_ncr_dataset_instantiation() -> None:
    r1 = NonconformanceRecord(**_valid_ncr_record_dict(record_id="NCR-001"))
    r2 = NonconformanceRecord(**_valid_ncr_record_dict(record_id="NCR-002", part_lot_id="LOT-002"))
    ds = NCRDataset(records=[r1, r2])
    assert len(ds.records) == 2
    assert ds.rows == [r1, r2]


def test_ncr_dataset_empty_records_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="NCRDataset must contain at least one record"):
        NCRDataset(records=[])


def test_ncr_dataset_duplicate_record_id_rejected() -> None:
    r1 = NonconformanceRecord(**_valid_ncr_record_dict(record_id="NCR-DUPE-01"))
    r2 = NonconformanceRecord(**_valid_ncr_record_dict(record_id="NCR-DUPE-01", part_lot_id="LOT-002"))
    with pytest.raises(pydantic.ValidationError, match="duplicate record_id values found"):
        NCRDataset(records=[r1, r2])


def test_ncr_dataset_multiple_none_record_ids_allowed() -> None:
    r1 = NonconformanceRecord(**_valid_ncr_record_dict(record_id=None))
    r2 = NonconformanceRecord(**_valid_ncr_record_dict(record_id=None, part_lot_id="LOT-002"))
    ds = NCRDataset(records=[r1, r2])
    assert len(ds.records) == 2


def test_ncr_dataset_rows_alias_in_dict_coercion() -> None:
    raw_dict = {
        "rows": [
            _valid_ncr_record_dict(record_id="NCR-001"),
            _valid_ncr_record_dict(record_id="NCR-002"),
        ]
    }
    ds = NCRDataset.model_validate(raw_dict)
    assert len(ds.records) == 2
    assert ds.records[0].record_id == "NCR-001"
    assert ds.records[1].record_id == "NCR-002"


def test_ncr_dataset_coercion_non_dict_passthrough() -> None:
    # If already a list or other object, validator returns as-is
    res = NCRDataset._coerce_rows_to_records("not a dict")
    assert res == "not a dict"


def test_ncr_dataset_coercion_both_rows_and_records_keeps_records() -> None:
    raw_dict = {
        "records": [_valid_ncr_record_dict(record_id="NCR-KEEP")],
        "rows": [_valid_ncr_record_dict(record_id="NCR-IGNORE")],
    }
    ds = NCRDataset.model_validate(raw_dict)
    assert len(ds.records) == 1
    assert ds.records[0].record_id == "NCR-KEEP"


# ==============================================================================
# 4. NCR_SCHEMA TableSchema tests
# ==============================================================================


def test_ncr_schema_descriptor() -> None:
    assert NCR_SCHEMA.name == "Nonconformance Record"
    assert NCR_SCHEMA.row_model == NonconformanceRecord
    assert NCR_SCHEMA.required_columns == (
        "part_lot_id",
        "defect_description",
        "requirement_violated",
        "quantity_affected",
        "detection_point",
    )
    assert NCR_SCHEMA.optional_columns == (
        "record_id",
        "disposition",
        "severity",
        "rationale",
        "approval_authority",
    )
    assert NCR_SCHEMA.dataset_model == NCRDataset
    assert NCR_SCHEMA.template_hint == "data/ncr_template.csv"


# ==============================================================================
# 5. load_ncr_csv tests
# ==============================================================================


def test_load_ncr_csv_from_buffer() -> None:
    rows = [
        _valid_ncr_record_dict(record_id="NCR-1"),
        _valid_ncr_record_dict(record_id="NCR-2", part_lot_id="LOT-02"),
    ]
    buf = _csv_buf(rows)
    df = load_ncr_csv(buf)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "part_lot_id" in df.columns
    assert "quantity_affected" in df.columns
    assert list(df["record_id"]) == ["NCR-1", "NCR-2"]


def test_load_ncr_csv_from_file_path(tmp_path: Path) -> None:
    rows = [_valid_ncr_record_dict(record_id="NCR-FILE-1")]
    csv_file = tmp_path / "ncr_test.csv"
    pd.DataFrame(rows).to_csv(csv_file, index=False)

    df = load_ncr_csv(str(csv_file))
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.iloc[0]["record_id"] == "NCR-FILE-1"


def test_load_ncr_csv_missing_required_column_raises_ingest_error() -> None:
    rows = [
        {
            "part_lot_id": "LOT-01",
            "defect_description": "Crack",
            # missing requirement_violated, quantity_affected, detection_point
        }
    ]
    buf = _csv_buf(rows)
    with pytest.raises(IngestError, match="Missing required column"):
        load_ncr_csv(buf)


def test_load_ncr_csv_malformed_row_raises_ingest_error() -> None:
    rows = [
        _valid_ncr_record_dict(quantity_affected=0),  # invalid quantity < 1
    ]
    buf = _csv_buf(rows)
    with pytest.raises(IngestError, match="Row 2, column 'quantity_affected'"):
        load_ncr_csv(buf)


def test_load_ncr_csv_narrows_extra_columns() -> None:
    rows = [
        _valid_ncr_record_dict(extra_metadata="Unrecognized Column Value"),
    ]
    buf = _csv_buf(rows)
    df = load_ncr_csv(buf)
    assert "extra_metadata" not in df.columns
    assert "part_lot_id" in df.columns


# ==============================================================================
# 6. validate_ncr trust-boundary validator tests
# ==============================================================================


def test_validate_ncr_from_ncr_dataset() -> None:
    ds = NCRDataset(records=[NonconformanceRecord(**_valid_ncr_record_dict())])
    validated = validate_ncr(ds)
    assert validated is ds


def test_validate_ncr_from_dataframe() -> None:
    df = pd.DataFrame([_valid_ncr_record_dict(record_id="NCR-DF-1")])
    validated = validate_ncr(df)
    assert isinstance(validated, NCRDataset)
    assert len(validated.records) == 1
    assert validated.records[0].record_id == "NCR-DF-1"


def test_validate_ncr_from_dataframe_with_nan() -> None:
    df = pd.DataFrame(
        [
            {
                "part_lot_id": "LOT-01",
                "defect_description": "Burr",
                "requirement_violated": "Spec-1",
                "quantity_affected": 5,
                "detection_point": "Line 1",
                "record_id": float("nan"),
                "disposition": float("nan"),
                "severity": float("nan"),
                "rationale": float("nan"),
                "approval_authority": float("nan"),
            }
        ]
    )
    validated = validate_ncr(df)
    assert len(validated.records) == 1
    assert validated.records[0].record_id is None
    assert validated.records[0].disposition is None


def test_validate_ncr_from_list_of_dicts() -> None:
    data = [
        _valid_ncr_record_dict(record_id="NCR-L1"),
        _valid_ncr_record_dict(record_id="NCR-L2", part_lot_id="LOT-02"),
    ]
    validated = validate_ncr(data)
    assert isinstance(validated, NCRDataset)
    assert len(validated.records) == 2
    assert validated.records[0].record_id == "NCR-L1"


def test_validate_ncr_from_list_of_records() -> None:
    r1 = NonconformanceRecord(**_valid_ncr_record_dict(record_id="NCR-R1"))
    r2 = NonconformanceRecord(**_valid_ncr_record_dict(record_id="NCR-R2", part_lot_id="LOT-02"))
    validated = validate_ncr([r1, r2])
    assert isinstance(validated, NCRDataset)
    assert len(validated.records) == 2
    assert validated.records[0] is r1
    assert validated.records[1] is r2


def test_validate_ncr_from_mixed_list() -> None:
    r1 = NonconformanceRecord(**_valid_ncr_record_dict(record_id="NCR-M1"))
    d2 = _valid_ncr_record_dict(record_id="NCR-M2", part_lot_id="LOT-02")
    validated = validate_ncr([r1, d2])
    assert isinstance(validated, NCRDataset)
    assert len(validated.records) == 2
    assert validated.records[0].record_id == "NCR-M1"
    assert validated.records[1].record_id == "NCR-M2"


def test_validate_ncr_from_dict() -> None:
    data = {
        "records": [
            _valid_ncr_record_dict(record_id="NCR-D1"),
        ]
    }
    validated = validate_ncr(data)
    assert isinstance(validated, NCRDataset)
    assert len(validated.records) == 1
    assert validated.records[0].record_id == "NCR-D1"


def test_validate_ncr_from_dict_with_none_fields() -> None:
    data = {
        "records": [
            {
                "part_lot_id": "LOT-01",
                "defect_description": "Scratch",
                "requirement_violated": "Spec-02",
                "quantity_affected": 3,
                "detection_point": "Inspection",
                "record_id": None,
                "disposition": None,
            }
        ]
    }
    validated = validate_ncr(data)
    assert len(validated.records) == 1
    assert validated.records[0].record_id is None
    assert validated.records[0].disposition is None


def test_validate_ncr_invalid_list_item_type_raises_type_error() -> None:
    with pytest.raises(TypeError, match="Expected NonconformanceRecord or dict in list, got int"):
        validate_ncr([123])  # type: ignore[list-item]


@pytest.mark.parametrize("invalid_input", [12345, "invalid string", True, 3.14])
def test_validate_ncr_unsupported_root_type_raises_type_error(invalid_input: Any) -> None:
    with pytest.raises(TypeError, match="Expected NCRDataset, DataFrame, list of dicts/records, or dict"):
        validate_ncr(invalid_input)


def test_validate_ncr_invalid_record_content_raises_validation_error() -> None:
    invalid_data = [{"part_lot_id": "LOT-1"}]  # missing required fields
    with pytest.raises(pydantic.ValidationError):
        validate_ncr(invalid_data)


def test_ncr_field_validators_non_string_passthrough() -> None:
    assert NonconformanceRecord.reject_blank_required_fields(123) == 123
    assert NonconformanceRecord.normalize_optional_strings(123) == 123
    assert NonconformanceRecord.normalize_disposition(123) == 123


def test_ncr_normalize_disposition_direct_value_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quality_core.ncr.schema.DISPOSITION_ALIASES",
        {k: v for k, v in DISPOSITION_ALIASES.items() if k != "scrap"},
    )
    assert NonconformanceRecord.normalize_disposition("Scrap") == "Scrap"


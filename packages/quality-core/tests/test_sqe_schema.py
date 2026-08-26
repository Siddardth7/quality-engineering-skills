"""
Tests for quality_core.sqe.schema and quality_core.sqe module exports.

Covers:
- Module exports and IngestError subclass
- Supplier / SupplierPeriod caller-constructed identity/window models
- ReceiptLot / DeliveryRecord / SCARRequest row models: blank rejection, stripping,
  optional-string normalization, numeric bounds, lenient date parsing
- The undecided sentinel (defect_count / quantity_delivered): None never conflated with 0
- ReceiptLotDataset / DeliveryRecordDataset / SCARRequestDataset: empty/duplicate rules,
  rows->records coercion, rows property alias
- SQE_*_SCHEMA TableSchema descriptors
- load_sqe_*_csv ingestion helpers (path, buffer, missing column, malformed row, narrowing,
  column-alias rename, already-canonical headers, alias collision)
- _normalize_sqe_columns alias hit/miss/no-op branches
- validate_sqe_* trust-boundary validators (Dataset, DataFrame w/ NaN, list, dict, TypeError)
- mode="before" validator non-string passthrough branches
"""

from __future__ import annotations

import datetime
import io
from pathlib import Path
from typing import Any

import pandas as pd
import pydantic
import pytest
import quality_core.sqe as sqe
from quality_core.sqe import (
    SQE_DELIVERY_SCHEMA,
    SQE_RECEIPT_SCHEMA,
    SQE_SCAR_SCHEMA,
    DeliveryRecord,
    DeliveryRecordDataset,
    IngestError,
    ReceiptLot,
    ReceiptLotDataset,
    SCARRequest,
    SCARRequestDataset,
    Supplier,
    SupplierPeriod,
    load_sqe_delivery_csv,
    load_sqe_receipt_csv,
    load_sqe_scar_csv,
    validate_sqe_delivery,
    validate_sqe_receipt,
    validate_sqe_scar,
)
from quality_core.sqe.schema import (
    DELIVERY_COLUMN_ALIASES,
    RECEIPT_COLUMN_ALIASES,
    SCAR_COLUMN_ALIASES,
    _normalize_sqe_columns,
)

# ==============================================================================
# Helper functions
# ==============================================================================


def _csv_buf(rows: list[dict[str, Any]], name: str = "sqe_upload.csv") -> io.BytesIO:
    buf = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode("utf-8"))
    buf.name = name
    return buf


def _valid_receipt(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "supplier_id": "SUP-01",
        "lot_id": "LOT-01",
        "quantity_received": 100,
        "receipt_date": "2026-01-15",
        "defect_count": 2,
        "opportunities_per_unit": 3,
    }
    base.update(overrides)
    return base


def _valid_delivery(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "supplier_id": "SUP-01",
        "order_id": "ORD-01",
        "quantity_ordered": 100,
        "quantity_delivered": 100,
        "requested_date": "2026-01-01",
        "promised_date": "2026-01-05",
        "actual_delivery_date": "2026-01-05",
    }
    base.update(overrides)
    return base


def _valid_scar(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "supplier_id": "SUP-01",
        "issue_description": "Recurring late shipments and short quantities",
        "scar_id": "SCAR-01",
        "linked_ncr_id": "NCR-01",
        "date_issued": "2026-01-01",
        "due_date": "2026-02-01",
        "requested_by": "J. Doe",
    }
    base.update(overrides)
    return base


# ==============================================================================
# 0. Module exports & IngestError
# ==============================================================================


def test_sqe_module_all_exports() -> None:
    expected_exports = {
        "DeliveryRecord",
        "DeliveryRecordDataset",
        "IngestError",
        "LinearScoringCurve",
        "OTIFConfig",
        "OTIFResult",
        "PPMConfig",
        "PPMResult",
        "ReceiptLot",
        "ReceiptLotDataset",
        "SCARRequest",
        "SCARRequestDataset",
        "SQE_DELIVERY_SCHEMA",
        "SQE_RECEIPT_SCHEMA",
        "SQE_SCAR_SCHEMA",
        "Supplier",
        "SupplierPeriod",
        "ScorecardConfig",
        "ScorecardDimensionResult",
        "ScorecardResult",
        "calculate_otif",
        "calculate_supplier_ppm",
        "calculate_vendor_scorecard",
        "load_sqe_delivery_csv",
        "load_sqe_receipt_csv",
        "load_sqe_scar_csv",
        "validate_sqe_delivery",
        "validate_sqe_receipt",
        "validate_sqe_scar",
    }
    assert set(sqe.__all__) == expected_exports
    for symbol in expected_exports:
        assert hasattr(sqe, symbol)


def test_ingest_error_is_subclass_of_value_error() -> None:
    assert issubclass(IngestError, ValueError)
    err = IngestError("Ingest failed")
    assert isinstance(err, ValueError)
    assert str(err) == "Ingest failed"


# ==============================================================================
# 1. Supplier model
# ==============================================================================


def test_supplier_minimal_and_full() -> None:
    s = Supplier(supplier_id="SUP-1", supplier_name="Acme Forgings")
    assert s.supplier_id == "SUP-1"
    assert s.supplier_name == "Acme Forgings"
    assert s.commodity is None

    s2 = Supplier(supplier_id="SUP-2", supplier_name="Beta", commodity="Castings")
    assert s2.commodity == "Castings"


@pytest.mark.parametrize("field_name", ["supplier_id", "supplier_name"])
@pytest.mark.parametrize("blank_val", ["", "   ", "\t\n\r"])
def test_supplier_required_fields_reject_blank(field_name: str, blank_val: str) -> None:
    data = {"supplier_id": "SUP-1", "supplier_name": "Acme", field_name: blank_val}
    with pytest.raises(pydantic.ValidationError, match="must not be blank or whitespace-only"):
        Supplier(**data)


@pytest.mark.parametrize("field_name", ["supplier_id", "supplier_name"])
def test_supplier_required_fields_stripped(field_name: str) -> None:
    data = {"supplier_id": "SUP-1", "supplier_name": "Acme", field_name: "  Clean  "}
    s = Supplier(**data)
    assert getattr(s, field_name) == "Clean"


@pytest.mark.parametrize("blank_val", [None, "", "   ", "\t\n"])
def test_supplier_commodity_blank_to_none(blank_val: Any) -> None:
    s = Supplier(supplier_id="SUP-1", supplier_name="Acme", commodity=blank_val)
    assert s.commodity is None


def test_supplier_commodity_stripped() -> None:
    s = Supplier(supplier_id="SUP-1", supplier_name="Acme", commodity="  Castings  ")
    assert s.commodity == "Castings"


# ==============================================================================
# 2. SupplierPeriod model
# ==============================================================================


def test_supplier_period_valid() -> None:
    p = SupplierPeriod(
        supplier_id="SUP-1",
        period_start=datetime.date(2026, 1, 1),
        period_end=datetime.date(2026, 3, 31),
        period_label="Q1 2026",
    )
    assert p.period_start == datetime.date(2026, 1, 1)
    assert p.period_end == datetime.date(2026, 3, 31)
    assert p.period_label == "Q1 2026"


def test_supplier_period_equal_bounds_allowed() -> None:
    # A single-day window (end == start) is a valid, decided window, not a broken one.
    p = SupplierPeriod(
        supplier_id="SUP-1",
        period_start=datetime.date(2026, 1, 1),
        period_end=datetime.date(2026, 1, 1),
    )
    assert p.period_end == p.period_start


def test_supplier_period_end_before_start_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="period_end must not be before period_start"):
        SupplierPeriod(
            supplier_id="SUP-1",
            period_start=datetime.date(2026, 3, 31),
            period_end=datetime.date(2026, 1, 1),
        )


def test_supplier_period_blank_supplier_id_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be blank or whitespace-only"):
        SupplierPeriod(
            supplier_id="   ",
            period_start=datetime.date(2026, 1, 1),
            period_end=datetime.date(2026, 3, 31),
        )


def test_supplier_period_label_blank_to_none() -> None:
    p = SupplierPeriod(
        supplier_id="SUP-1",
        period_start=datetime.date(2026, 1, 1),
        period_end=datetime.date(2026, 3, 31),
        period_label="   ",
    )
    assert p.period_label is None


def test_supplier_period_required_dates_strict() -> None:
    # Required window dates are parsed strictly: an unparseable date raises, never resolves None.
    with pytest.raises(pydantic.ValidationError):
        SupplierPeriod(
            supplier_id="SUP-1",
            period_start="not-a-date",  # type: ignore[arg-type]
            period_end=datetime.date(2026, 3, 31),
        )


# ==============================================================================
# 3. ReceiptLot row model
# ==============================================================================


def test_receipt_lot_minimal_defaults() -> None:
    r = ReceiptLot(supplier_id="SUP-1", lot_id="LOT-1", quantity_received=50)
    assert r.supplier_id == "SUP-1"
    assert r.lot_id == "LOT-1"
    assert r.quantity_received == 50
    assert r.receipt_date is None
    assert r.defect_count is None
    assert r.opportunities_per_unit is None


def test_receipt_lot_full_instantiation() -> None:
    r = ReceiptLot(**_valid_receipt())
    assert r.supplier_id == "SUP-01"
    assert r.lot_id == "LOT-01"
    assert r.quantity_received == 100
    assert r.receipt_date == datetime.date(2026, 1, 15)
    assert r.defect_count == 2
    assert r.opportunities_per_unit == 3


@pytest.mark.parametrize("field_name", ["supplier_id", "lot_id"])
@pytest.mark.parametrize("blank_val", ["", "   ", "\t\n\r"])
def test_receipt_lot_required_fields_reject_blank(field_name: str, blank_val: str) -> None:
    data = _valid_receipt(**{field_name: blank_val})
    with pytest.raises(pydantic.ValidationError, match="must not be blank or whitespace-only"):
        ReceiptLot(**data)


@pytest.mark.parametrize("field_name", ["supplier_id", "lot_id"])
def test_receipt_lot_required_fields_stripped(field_name: str) -> None:
    data = _valid_receipt(**{field_name: "  Clean  "})
    r = ReceiptLot(**data)
    assert getattr(r, field_name) == "Clean"


@pytest.mark.parametrize("qty", [0, -1, -50])
def test_receipt_lot_quantity_received_rejects_non_positive(qty: int) -> None:
    with pytest.raises(pydantic.ValidationError):
        ReceiptLot(**_valid_receipt(quantity_received=qty))


def test_receipt_lot_defect_count_zero_allowed_negative_rejected() -> None:
    r = ReceiptLot(**_valid_receipt(defect_count=0))
    assert r.defect_count == 0
    with pytest.raises(pydantic.ValidationError):
        ReceiptLot(**_valid_receipt(defect_count=-1))


def test_receipt_lot_opportunities_per_unit_rejects_below_one() -> None:
    with pytest.raises(pydantic.ValidationError):
        ReceiptLot(**_valid_receipt(opportunities_per_unit=0))


def test_receipt_lot_defect_count_exceeding_received_rejected() -> None:
    # Quantity-sanity control (#115): a counted lot cannot have more defectives
    # than it received, and the error must name the field.
    with pytest.raises(
        pydantic.ValidationError,
        match=r"defect_count \(11\) cannot exceed quantity_received \(10\)",
    ):
        ReceiptLot(**_valid_receipt(quantity_received=10, defect_count=11))


def test_receipt_lot_defect_count_equal_received_allowed() -> None:
    # Boundary: all received units defective is a legitimate (if grim) lot.
    r = ReceiptLot(**_valid_receipt(quantity_received=10, defect_count=10))
    assert r.defect_count == r.quantity_received == 10


def test_receipt_lot_undecided_defect_count_exempt_from_sanity_check() -> None:
    # The undecided sentinel is "not yet counted", not a quantity — it must survive
    # the cross-field check rather than be rejected.
    r = ReceiptLot(**_valid_receipt(quantity_received=10, defect_count=None))
    assert r.defect_count is None


# ==============================================================================
# 3a. Undecided sentinel — MANDATORY negative control (ReceiptLot.defect_count)
# ==============================================================================


def test_receipt_lot_blank_defect_count_is_none_not_zero() -> None:
    undecided = ReceiptLot(supplier_id="SUP-1", lot_id="LOT-1", quantity_received=10)
    decided = ReceiptLot(
        supplier_id="SUP-1", lot_id="LOT-2", quantity_received=10, defect_count=0
    )
    # The whole point of the sentinel: undecided (None) is NOT the decided-zero value.
    assert undecided.defect_count is None
    assert decided.defect_count == 0
    assert undecided.defect_count != decided.defect_count
    assert undecided.defect_count is not decided.defect_count


def test_receipt_lot_sentinel_survives_csv_roundtrip() -> None:
    rows = [
        {"supplier_id": "SUP-1", "lot_id": "LOT-BLANK", "quantity_received": 10},
        {
            "supplier_id": "SUP-1",
            "lot_id": "LOT-ZERO",
            "quantity_received": 10,
            "defect_count": 0,
        },
    ]
    df = load_sqe_receipt_csv(_csv_buf(rows))
    ds = validate_sqe_receipt(df)
    by_lot = {r.lot_id: r.defect_count for r in ds.records}
    assert by_lot["LOT-BLANK"] is None
    assert by_lot["LOT-ZERO"] == 0


# ==============================================================================
# 4. DeliveryRecord row model
# ==============================================================================


def test_delivery_record_minimal_defaults() -> None:
    d = DeliveryRecord(supplier_id="SUP-1", order_id="ORD-1", quantity_ordered=20)
    assert d.quantity_delivered is None
    assert d.requested_date is None
    assert d.promised_date is None
    assert d.actual_delivery_date is None


def test_delivery_record_full_instantiation() -> None:
    d = DeliveryRecord(**_valid_delivery())
    assert d.quantity_ordered == 100
    assert d.quantity_delivered == 100
    assert d.requested_date == datetime.date(2026, 1, 1)
    assert d.promised_date == datetime.date(2026, 1, 5)
    assert d.actual_delivery_date == datetime.date(2026, 1, 5)


@pytest.mark.parametrize("field_name", ["supplier_id", "order_id"])
@pytest.mark.parametrize("blank_val", ["", "   ", "\t\n\r"])
def test_delivery_record_required_fields_reject_blank(field_name: str, blank_val: str) -> None:
    data = _valid_delivery(**{field_name: blank_val})
    with pytest.raises(pydantic.ValidationError, match="must not be blank or whitespace-only"):
        DeliveryRecord(**data)


@pytest.mark.parametrize("field_name", ["supplier_id", "order_id"])
def test_delivery_record_required_fields_stripped(field_name: str) -> None:
    data = _valid_delivery(**{field_name: "  Clean  "})
    d = DeliveryRecord(**data)
    assert getattr(d, field_name) == "Clean"


@pytest.mark.parametrize("qty", [0, -1])
def test_delivery_record_quantity_ordered_rejects_non_positive(qty: int) -> None:
    with pytest.raises(pydantic.ValidationError):
        DeliveryRecord(**_valid_delivery(quantity_ordered=qty))


def test_delivery_quantity_delivered_exceeding_ordered_rejected() -> None:
    # Quantity-sanity control (#115): a shipment cannot deliver more than ordered,
    # and the error must name the field.
    with pytest.raises(
        pydantic.ValidationError,
        match=r"quantity_delivered \(11\) cannot exceed quantity_ordered \(10\)",
    ):
        DeliveryRecord(**_valid_delivery(quantity_ordered=10, quantity_delivered=11))


def test_delivery_quantity_delivered_equal_ordered_allowed() -> None:
    d = DeliveryRecord(**_valid_delivery(quantity_ordered=10, quantity_delivered=10))
    assert d.quantity_delivered == d.quantity_ordered == 10


def test_delivery_undecided_quantity_delivered_exempt_from_sanity_check() -> None:
    d = DeliveryRecord(**_valid_delivery(quantity_ordered=10, quantity_delivered=None))
    assert d.quantity_delivered is None


def test_delivery_record_quantity_delivered_zero_allowed_negative_rejected() -> None:
    d = DeliveryRecord(**_valid_delivery(quantity_delivered=0))
    assert d.quantity_delivered == 0
    with pytest.raises(pydantic.ValidationError):
        DeliveryRecord(**_valid_delivery(quantity_delivered=-1))


# ==============================================================================
# 4a. Undecided sentinel — MANDATORY negative control (quantity_delivered)
# ==============================================================================


def test_delivery_blank_quantity_delivered_is_none_not_zero() -> None:
    undecided = DeliveryRecord(supplier_id="SUP-1", order_id="ORD-1", quantity_ordered=10)
    decided = DeliveryRecord(
        supplier_id="SUP-1", order_id="ORD-2", quantity_ordered=10, quantity_delivered=0
    )
    assert undecided.quantity_delivered is None
    assert decided.quantity_delivered == 0
    assert undecided.quantity_delivered != decided.quantity_delivered
    assert undecided.quantity_delivered is not decided.quantity_delivered


def test_delivery_sentinel_survives_csv_roundtrip() -> None:
    rows = [
        {"supplier_id": "SUP-1", "order_id": "ORD-BLANK", "quantity_ordered": 10},
        {
            "supplier_id": "SUP-1",
            "order_id": "ORD-ZERO",
            "quantity_ordered": 10,
            "quantity_delivered": 0,
        },
    ]
    df = load_sqe_delivery_csv(_csv_buf(rows))
    ds = validate_sqe_delivery(df)
    by_order = {r.order_id: r.quantity_delivered for r in ds.records}
    assert by_order["ORD-BLANK"] is None
    assert by_order["ORD-ZERO"] == 0


# ==============================================================================
# 5. SCARRequest row model
# ==============================================================================


def test_scar_request_minimal_defaults() -> None:
    s = SCARRequest(supplier_id="SUP-1", issue_description="Late delivery")
    assert s.scar_id is None
    assert s.linked_ncr_id is None
    assert s.date_issued is None
    assert s.due_date is None
    assert s.requested_by is None


def test_scar_request_full_instantiation() -> None:
    s = SCARRequest(**_valid_scar())
    assert s.scar_id == "SCAR-01"
    assert s.linked_ncr_id == "NCR-01"
    assert s.date_issued == datetime.date(2026, 1, 1)
    assert s.due_date == datetime.date(2026, 2, 1)
    assert s.requested_by == "J. Doe"


@pytest.mark.parametrize("field_name", ["supplier_id", "issue_description"])
@pytest.mark.parametrize("blank_val", ["", "   ", "\t\n\r"])
def test_scar_request_required_fields_reject_blank(field_name: str, blank_val: str) -> None:
    data = _valid_scar(**{field_name: blank_val})
    with pytest.raises(pydantic.ValidationError, match="must not be blank or whitespace-only"):
        SCARRequest(**data)


@pytest.mark.parametrize("field_name", ["scar_id", "linked_ncr_id", "requested_by"])
@pytest.mark.parametrize("blank_val", [None, "", "   ", "\t\n"])
def test_scar_request_optional_fields_normalized_to_none(field_name: str, blank_val: Any) -> None:
    data = _valid_scar(**{field_name: blank_val})
    s = SCARRequest(**data)
    assert getattr(s, field_name) is None


@pytest.mark.parametrize("field_name", ["scar_id", "linked_ncr_id", "requested_by"])
def test_scar_request_optional_fields_stripped(field_name: str) -> None:
    data = _valid_scar(**{field_name: "  Stripped  "})
    s = SCARRequest(**data)
    assert getattr(s, field_name) == "Stripped"


def test_scar_request_issue_description_length_limit() -> None:
    with pytest.raises(pydantic.ValidationError):
        SCARRequest(supplier_id="SUP-1", issue_description="A" * 4001)


# ==============================================================================
# 6. Lenient date parsing
# ==============================================================================


def test_date_lenient_valid_iso_string() -> None:
    r = ReceiptLot(**_valid_receipt(receipt_date="2026-06-15"))
    assert r.receipt_date == datetime.date(2026, 6, 15)


def test_date_lenient_non_iso_string() -> None:
    r = ReceiptLot(**_valid_receipt(receipt_date="01/15/2026"))
    assert r.receipt_date == datetime.date(2026, 1, 15)


@pytest.mark.parametrize("blank_val", [None, "", "   "])
def test_date_lenient_blank_to_none(blank_val: Any) -> None:
    r = ReceiptLot(**_valid_receipt(receipt_date=blank_val))
    assert r.receipt_date is None


@pytest.mark.parametrize("garbage", ["not-a-date", "13/45/2026"])
def test_date_lenient_garbage_to_none(garbage: str) -> None:
    r = ReceiptLot(**_valid_receipt(receipt_date=garbage))
    assert r.receipt_date is None


def test_date_lenient_date_object_passthrough() -> None:
    # An already-`date` object bypasses pd.to_datetime and is returned unchanged.
    d = datetime.date(2026, 2, 2)
    r = ReceiptLot(**_valid_receipt(receipt_date=d))
    assert r.receipt_date == d


def test_date_lenient_numeric_cell_is_epoch_not_none() -> None:
    # DELIBERATE, DOCUMENTED behaviour: a numeric cell is read by pd.to_datetime as an
    # epoch-nanosecond timestamp, so 123456789 -> 1970-01-01, NOT None. Pinned so any
    # future change to this quirk is caught.
    assert ReceiptLot.parse_dates_lenient(123456789) == datetime.date(1970, 1, 1)


# ==============================================================================
# 7. Dataset models
# ==============================================================================


def test_receipt_dataset_instantiation_and_rows_property() -> None:
    r1 = ReceiptLot(**_valid_receipt(lot_id="LOT-1"))
    r2 = ReceiptLot(**_valid_receipt(lot_id="LOT-2"))
    ds = ReceiptLotDataset(records=[r1, r2])
    assert len(ds.records) == 2
    assert ds.rows == [r1, r2]


def test_receipt_dataset_empty_rejected() -> None:
    with pytest.raises(
        pydantic.ValidationError, match="ReceiptLotDataset must contain at least one record"
    ):
        ReceiptLotDataset(records=[])


def test_receipt_dataset_duplicate_lot_id_rejected() -> None:
    r1 = ReceiptLot(**_valid_receipt(lot_id="DUPE"))
    r2 = ReceiptLot(**_valid_receipt(lot_id="DUPE"))
    with pytest.raises(pydantic.ValidationError, match="duplicate lot_id values found"):
        ReceiptLotDataset(records=[r1, r2])


def test_receipt_dataset_rows_alias_coercion() -> None:
    raw = {"rows": [_valid_receipt(lot_id="LOT-1"), _valid_receipt(lot_id="LOT-2")]}
    ds = ReceiptLotDataset.model_validate(raw)
    assert len(ds.records) == 2


def test_receipt_dataset_coercion_non_dict_passthrough() -> None:
    assert ReceiptLotDataset._coerce_rows_to_records("not a dict") == "not a dict"


def test_receipt_dataset_coercion_both_rows_and_records_keeps_records() -> None:
    raw = {
        "records": [_valid_receipt(lot_id="KEEP")],
        "rows": [_valid_receipt(lot_id="IGNORE")],
    }
    ds = ReceiptLotDataset.model_validate(raw)
    assert len(ds.records) == 1
    assert ds.records[0].lot_id == "KEEP"


def test_delivery_dataset_empty_and_duplicate() -> None:
    with pytest.raises(
        pydantic.ValidationError, match="DeliveryRecordDataset must contain at least one record"
    ):
        DeliveryRecordDataset(records=[])
    d1 = DeliveryRecord(**_valid_delivery(order_id="DUPE"))
    d2 = DeliveryRecord(**_valid_delivery(order_id="DUPE"))
    with pytest.raises(pydantic.ValidationError, match="duplicate order_id values found"):
        DeliveryRecordDataset(records=[d1, d2])


def test_delivery_dataset_rows_alias_and_passthrough() -> None:
    raw = {"rows": [_valid_delivery(order_id="ORD-1")]}
    ds = DeliveryRecordDataset.model_validate(raw)
    assert len(ds.records) == 1
    assert ds.rows[0].order_id == "ORD-1"
    assert DeliveryRecordDataset._coerce_rows_to_records(42) == 42


def test_scar_dataset_empty_rejected() -> None:
    with pytest.raises(
        pydantic.ValidationError, match="SCARRequestDataset must contain at least one record"
    ):
        SCARRequestDataset(records=[])


def test_scar_dataset_duplicate_scar_id_rejected() -> None:
    s1 = SCARRequest(**_valid_scar(scar_id="DUPE"))
    s2 = SCARRequest(**_valid_scar(scar_id="DUPE"))
    with pytest.raises(pydantic.ValidationError, match="duplicate scar_id values found"):
        SCARRequestDataset(records=[s1, s2])


def test_scar_dataset_multiple_none_scar_ids_allowed() -> None:
    s1 = SCARRequest(**_valid_scar(scar_id=None))
    s2 = SCARRequest(**_valid_scar(scar_id=None))
    ds = SCARRequestDataset(records=[s1, s2])
    assert len(ds.records) == 2


def test_scar_dataset_rows_alias_and_passthrough() -> None:
    raw = {"rows": [_valid_scar(scar_id="SCAR-1")]}
    ds = SCARRequestDataset.model_validate(raw)
    assert len(ds.records) == 1
    assert ds.rows[0].scar_id == "SCAR-1"
    assert SCARRequestDataset._coerce_rows_to_records(["x"]) == ["x"]


# ==============================================================================
# 8. TableSchema descriptors
# ==============================================================================


def test_receipt_schema_descriptor() -> None:
    assert SQE_RECEIPT_SCHEMA.name == "Supplier Receipt Lot"
    assert SQE_RECEIPT_SCHEMA.row_model == ReceiptLot
    assert SQE_RECEIPT_SCHEMA.required_columns == ("supplier_id", "lot_id", "quantity_received")
    assert SQE_RECEIPT_SCHEMA.optional_columns == (
        "receipt_date",
        "defect_count",
        "opportunities_per_unit",
    )
    assert SQE_RECEIPT_SCHEMA.dataset_model == ReceiptLotDataset
    assert SQE_RECEIPT_SCHEMA.template_hint == "data/sqe_receipt_template.csv"


def test_delivery_schema_descriptor() -> None:
    assert SQE_DELIVERY_SCHEMA.name == "Supplier Delivery Record"
    assert SQE_DELIVERY_SCHEMA.row_model == DeliveryRecord
    assert SQE_DELIVERY_SCHEMA.required_columns == ("supplier_id", "order_id", "quantity_ordered")
    assert SQE_DELIVERY_SCHEMA.optional_columns == (
        "quantity_delivered",
        "requested_date",
        "promised_date",
        "actual_delivery_date",
    )
    assert SQE_DELIVERY_SCHEMA.dataset_model == DeliveryRecordDataset
    assert SQE_DELIVERY_SCHEMA.template_hint == "data/sqe_delivery_template.csv"


def test_scar_schema_descriptor() -> None:
    assert SQE_SCAR_SCHEMA.name == "SCAR Request"
    assert SQE_SCAR_SCHEMA.row_model == SCARRequest
    assert SQE_SCAR_SCHEMA.required_columns == ("supplier_id", "issue_description")
    assert SQE_SCAR_SCHEMA.optional_columns == (
        "scar_id",
        "linked_ncr_id",
        "date_issued",
        "due_date",
        "requested_by",
    )
    assert SQE_SCAR_SCHEMA.dataset_model == SCARRequestDataset
    assert SQE_SCAR_SCHEMA.template_hint == "data/sqe_scar_template.csv"


# ==============================================================================
# 9. load_sqe_*_csv ingestion helpers
# ==============================================================================


def test_load_receipt_csv_from_buffer() -> None:
    rows = [_valid_receipt(lot_id="LOT-1"), _valid_receipt(lot_id="LOT-2")]
    df = load_sqe_receipt_csv(_csv_buf(rows))
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df["lot_id"]) == ["LOT-1", "LOT-2"]


def test_load_receipt_csv_from_file_path(tmp_path: Path) -> None:
    csv_file = tmp_path / "receipt.csv"
    pd.DataFrame([_valid_receipt(lot_id="LOT-FILE")]).to_csv(csv_file, index=False)
    df = load_sqe_receipt_csv(str(csv_file))
    assert df.iloc[0]["lot_id"] == "LOT-FILE"


def test_load_receipt_csv_missing_required_column() -> None:
    rows = [{"supplier_id": "SUP-1", "lot_id": "LOT-1"}]  # missing quantity_received
    with pytest.raises(IngestError, match="Missing required column"):
        load_sqe_receipt_csv(_csv_buf(rows))


def test_load_receipt_csv_malformed_row() -> None:
    rows = [_valid_receipt(quantity_received=0)]  # ge=1 violation
    with pytest.raises(IngestError, match="Row 2, column 'quantity_received'"):
        load_sqe_receipt_csv(_csv_buf(rows))


def test_load_receipt_csv_defect_exceeds_received_raises() -> None:
    # Quantity-sanity control at the load boundary: the cross-field error surfaces
    # as an IngestError naming the field, not a raw traceback.
    rows = [_valid_receipt(quantity_received=10, defect_count=11)]
    with pytest.raises(
        IngestError, match=r"defect_count \(11\) cannot exceed quantity_received \(10\)"
    ):
        load_sqe_receipt_csv(_csv_buf(rows))


def test_load_delivery_csv_delivered_exceeds_ordered_raises() -> None:
    rows = [_valid_delivery(quantity_ordered=10, quantity_delivered=11)]
    with pytest.raises(
        IngestError,
        match=r"quantity_delivered \(11\) cannot exceed quantity_ordered \(10\)",
    ):
        load_sqe_delivery_csv(_csv_buf(rows))


def test_load_receipt_csv_narrows_extra_columns() -> None:
    rows = [_valid_receipt(unknown_extra="junk")]
    df = load_sqe_receipt_csv(_csv_buf(rows))
    assert "unknown_extra" not in df.columns
    assert "lot_id" in df.columns


def test_load_receipt_csv_alias_headers() -> None:
    # Aliased, mixed-case, whitespace-y headers must resolve to canonical fields.
    csv = "Vendor,Lot Number,QTY Received,Defects\nSUP-9,LOT-9,42,1\n"
    buf = io.BytesIO(csv.encode("utf-8"))
    buf.name = "aliased.csv"
    df = load_sqe_receipt_csv(buf)
    assert df.iloc[0]["supplier_id"] == "SUP-9"
    assert df.iloc[0]["lot_id"] == "LOT-9"
    assert df.iloc[0]["quantity_received"] == 42
    assert df.iloc[0]["defect_count"] == 1


def test_load_receipt_csv_already_canonical_headers() -> None:
    rows = [_valid_receipt(lot_id="CANON")]
    df = load_sqe_receipt_csv(_csv_buf(rows))
    assert df.iloc[0]["lot_id"] == "CANON"


def test_load_receipt_csv_alias_collision_silently_drops_data() -> None:
    # KNOWN GAP / FINDING (pinned): two headers aliasing to the same canonical name produce
    # DUPLICATE columns. This does NOT raise (contrary to the coder's "fails inside
    # validate_table" note) — it silently keeps both columns, and validate_table's
    # `df[columns].to_dict()` emits only a UserWarning and last-column-wins, dropping the
    # first column's data. No collision guard exists; this pins the real, lossy behaviour.
    csv = "supplier,supplier_id,lot_id,quantity_received\nAAA,BBB,LOT-1,10\n"
    buf = io.BytesIO(csv.encode("utf-8"))
    buf.name = "collision.csv"
    df = load_sqe_receipt_csv(buf)  # does not raise
    # Both aliases resolved to the same canonical name -> duplicate column.
    assert list(df.columns).count("supplier_id") == 2
    with pytest.warns(UserWarning, match="columns are not unique"):
        ds = validate_sqe_receipt(df)
    # The first column's value ("AAA") is silently lost; the last one ("BBB") survives.
    assert ds.records[0].supplier_id == "BBB"


def test_load_delivery_csv_from_buffer_and_alias() -> None:
    csv = "Supplier ID,PO Number,Qty Ordered,Delivered\nSUP-1,PO-1,50,50\n"
    buf = io.BytesIO(csv.encode("utf-8"))
    buf.name = "delivery.csv"
    df = load_sqe_delivery_csv(buf)
    assert df.iloc[0]["supplier_id"] == "SUP-1"
    assert df.iloc[0]["order_id"] == "PO-1"
    assert df.iloc[0]["quantity_ordered"] == 50
    assert df.iloc[0]["quantity_delivered"] == 50


def test_load_delivery_csv_from_file_path(tmp_path: Path) -> None:
    csv_file = tmp_path / "delivery.csv"
    pd.DataFrame([_valid_delivery(order_id="ORD-FILE")]).to_csv(csv_file, index=False)
    df = load_sqe_delivery_csv(str(csv_file))
    assert df.iloc[0]["order_id"] == "ORD-FILE"


def test_load_delivery_csv_missing_required_column() -> None:
    rows = [{"supplier_id": "SUP-1", "order_id": "ORD-1"}]  # missing quantity_ordered
    with pytest.raises(IngestError, match="Missing required column"):
        load_sqe_delivery_csv(_csv_buf(rows))


def test_load_scar_csv_from_buffer_and_alias() -> None:
    csv = "Vendor,Problem,SCAR#,Requestor\nSUP-1,Bad parts,SCAR-7,Alice\n"
    buf = io.BytesIO(csv.encode("utf-8"))
    buf.name = "scar.csv"
    df = load_sqe_scar_csv(buf)
    assert df.iloc[0]["supplier_id"] == "SUP-1"
    assert df.iloc[0]["issue_description"] == "Bad parts"
    assert df.iloc[0]["scar_id"] == "SCAR-7"
    assert df.iloc[0]["requested_by"] == "Alice"


def test_load_scar_csv_from_file_path(tmp_path: Path) -> None:
    csv_file = tmp_path / "scar.csv"
    pd.DataFrame([_valid_scar(scar_id="SCAR-FILE")]).to_csv(csv_file, index=False)
    df = load_sqe_scar_csv(str(csv_file))
    assert df.iloc[0]["scar_id"] == "SCAR-FILE"


def test_load_scar_csv_missing_required_column() -> None:
    rows = [{"supplier_id": "SUP-1"}]  # missing issue_description
    with pytest.raises(IngestError, match="Missing required column"):
        load_sqe_scar_csv(_csv_buf(rows))


def test_load_csv_empty_file_raises() -> None:
    buf = io.BytesIO(b"supplier_id,lot_id,quantity_received\n")
    buf.name = "empty.csv"
    with pytest.raises(IngestError, match="No data rows found"):
        load_sqe_receipt_csv(buf)


# ==============================================================================
# 10. _normalize_sqe_columns branch coverage
# ==============================================================================


def test_normalize_columns_alias_hit_and_miss() -> None:
    # One recognized header (renamed) and one unrecognized (passed through unchanged).
    df = pd.DataFrame({"  Supplier ID ": ["SUP-1"], "unknown_col": ["x"]})
    out = _normalize_sqe_columns(df, RECEIPT_COLUMN_ALIASES)
    assert "supplier_id" in out.columns
    assert "unknown_col" in out.columns


def test_normalize_columns_no_matches_returns_same_object() -> None:
    df = pd.DataFrame({"totally_unknown": [1], "another_unknown": [2]})
    out = _normalize_sqe_columns(df, DELIVERY_COLUMN_ALIASES)
    assert out is df


def test_normalize_columns_scar_alias_map() -> None:
    df = pd.DataFrame({"CONCERN": ["late"], "raised by": ["Bob"]})
    out = _normalize_sqe_columns(df, SCAR_COLUMN_ALIASES)
    assert "issue_description" in out.columns
    assert "requested_by" in out.columns


# ==============================================================================
# 11. validate_sqe_* trust-boundary validators
# ==============================================================================


def test_validate_receipt_from_dataset_identity() -> None:
    ds = ReceiptLotDataset(records=[ReceiptLot(**_valid_receipt())])
    assert validate_sqe_receipt(ds) is ds


def test_validate_receipt_from_dataframe_with_nan() -> None:
    df = pd.DataFrame(
        [
            {
                "supplier_id": "SUP-1",
                "lot_id": "LOT-1",
                "quantity_received": 10,
                "receipt_date": float("nan"),
                "defect_count": float("nan"),
                "opportunities_per_unit": float("nan"),
            }
        ]
    )
    ds = validate_sqe_receipt(df)
    assert len(ds.records) == 1
    assert ds.records[0].receipt_date is None
    assert ds.records[0].defect_count is None
    assert ds.records[0].opportunities_per_unit is None


def test_validate_receipt_from_list_dicts_records_and_mixed() -> None:
    r1 = ReceiptLot(**_valid_receipt(lot_id="R1"))
    ds = validate_sqe_receipt([r1, _valid_receipt(lot_id="R2")])
    assert len(ds.records) == 2
    assert ds.records[0] is r1
    assert ds.records[1].lot_id == "R2"


def test_validate_receipt_from_dict() -> None:
    ds = validate_sqe_receipt({"records": [_valid_receipt(lot_id="D1")]})
    assert ds.records[0].lot_id == "D1"


def test_validate_receipt_invalid_list_item_type() -> None:
    with pytest.raises(TypeError, match="Expected ReceiptLot or dict in list, got int"):
        validate_sqe_receipt([123])


@pytest.mark.parametrize("bad", [12345, "str", True, 3.14])
def test_validate_receipt_unsupported_root_type(bad: Any) -> None:
    with pytest.raises(
        TypeError, match="Expected ReceiptLotDataset, DataFrame, list of dicts/records, or dict"
    ):
        validate_sqe_receipt(bad)


def test_validate_receipt_invalid_content() -> None:
    with pytest.raises(pydantic.ValidationError):
        validate_sqe_receipt([{"supplier_id": "SUP-1"}])  # missing required fields


def test_validate_delivery_from_dataset_identity() -> None:
    ds = DeliveryRecordDataset(records=[DeliveryRecord(**_valid_delivery())])
    assert validate_sqe_delivery(ds) is ds


def test_validate_delivery_from_dataframe_with_nan() -> None:
    df = pd.DataFrame(
        [
            {
                "supplier_id": "SUP-1",
                "order_id": "ORD-1",
                "quantity_ordered": 10,
                "quantity_delivered": float("nan"),
                "requested_date": float("nan"),
                "promised_date": float("nan"),
                "actual_delivery_date": float("nan"),
            }
        ]
    )
    ds = validate_sqe_delivery(df)
    assert ds.records[0].quantity_delivered is None
    assert ds.records[0].requested_date is None


def test_validate_delivery_from_list_and_dict() -> None:
    d1 = DeliveryRecord(**_valid_delivery(order_id="D1"))
    ds = validate_sqe_delivery([d1, _valid_delivery(order_id="D2")])
    assert len(ds.records) == 2
    ds2 = validate_sqe_delivery({"records": [_valid_delivery(order_id="D3")]})
    assert ds2.records[0].order_id == "D3"


def test_validate_delivery_invalid_list_item_type() -> None:
    with pytest.raises(TypeError, match="Expected DeliveryRecord or dict in list, got int"):
        validate_sqe_delivery([123])


@pytest.mark.parametrize("bad", [12345, "str", True, 3.14])
def test_validate_delivery_unsupported_root_type(bad: Any) -> None:
    with pytest.raises(
        TypeError,
        match="Expected DeliveryRecordDataset, DataFrame, list of dicts/records, or dict",
    ):
        validate_sqe_delivery(bad)


def test_validate_scar_from_dataset_identity() -> None:
    ds = SCARRequestDataset(records=[SCARRequest(**_valid_scar())])
    assert validate_sqe_scar(ds) is ds


def test_validate_scar_from_dataframe_with_nan() -> None:
    df = pd.DataFrame(
        [
            {
                "supplier_id": "SUP-1",
                "issue_description": "Bad parts",
                "scar_id": float("nan"),
                "linked_ncr_id": float("nan"),
                "date_issued": float("nan"),
                "due_date": float("nan"),
                "requested_by": float("nan"),
            }
        ]
    )
    ds = validate_sqe_scar(df)
    assert ds.records[0].scar_id is None
    assert ds.records[0].date_issued is None


def test_validate_scar_from_list_and_dict() -> None:
    s1 = SCARRequest(**_valid_scar(scar_id="S1"))
    ds = validate_sqe_scar([s1, _valid_scar(scar_id="S2")])
    assert len(ds.records) == 2
    ds2 = validate_sqe_scar({"records": [_valid_scar(scar_id="S3")]})
    assert ds2.records[0].scar_id == "S3"


def test_validate_scar_invalid_list_item_type() -> None:
    with pytest.raises(TypeError, match="Expected SCARRequest or dict in list, got int"):
        validate_sqe_scar([123])


@pytest.mark.parametrize("bad", [12345, "str", True, 3.14])
def test_validate_scar_unsupported_root_type(bad: Any) -> None:
    with pytest.raises(
        TypeError, match="Expected SCARRequestDataset, DataFrame, list of dicts/records, or dict"
    ):
        validate_sqe_scar(bad)


# ==============================================================================
# 12. mode="before" validator non-string passthrough (coverage-shaped)
# ==============================================================================


def test_receipt_field_validators_non_string_passthrough() -> None:
    assert ReceiptLot.reject_blank_required_fields(123) == 123
    assert ReceiptLot.parse_dates_lenient(None) is None


def test_delivery_field_validators_non_string_passthrough() -> None:
    assert DeliveryRecord.reject_blank_required_fields(123) == 123


def test_scar_field_validators_non_string_passthrough() -> None:
    assert SCARRequest.reject_blank_required_fields(123) == 123
    assert SCARRequest.normalize_optional_strings(123) == 123


def test_supplier_and_period_validators_non_string_passthrough() -> None:
    assert Supplier.reject_blank_required_fields(123) == 123
    assert Supplier.normalize_optional_strings(123) == 123
    assert SupplierPeriod.reject_blank_required_fields(123) == 123
    assert SupplierPeriod.normalize_optional_strings(123) == 123

"""
schema.py
Supplier Quality Engineering (SQE) — shared domain models, schemas, and ingest validators.

Defines Pydantic row and dataset models along with TableSchema descriptors for:
- Supplier receipt lots (ReceiptLot, ReceiptLotDataset, SQE_RECEIPT_SCHEMA)
- Supplier delivery records (DeliveryRecord, DeliveryRecordDataset, SQE_DELIVERY_SCHEMA)
- Supplier corrective action requests (SCARRequest, SCARRequestDataset, SQE_SCAR_SCHEMA)
- Caller-constructed identity/window models (Supplier, SupplierPeriod) — no CSV path

Provides CSV loading helpers and trust-boundary validation functions ensuring type coercion,
blank rejection, lenient date parsing, column-alias normalization, and unique key enforcement.

Scope note (E1 is scaffolding only)
-----------------------------------
No AIAG/ISO/IATF/CQI-20/8D constant, threshold, or table is encoded here, so nothing in this
module is cited: it asserts no standard. PPM/OTIF/scorecard thresholds are declared,
caller-configurable heuristics that belong to the downstream engines (E2-E5), never to a field
default in this file.

The undecided sentinel
----------------------
``ReceiptLot.defect_count`` and ``DeliveryRecord.quantity_delivered`` are ``int | None`` with a
``None`` default. ``None`` means *undecided* — the lot was never inspected/counted, the shipment
was never received/counted — and is deliberately distinct from an explicit ``0`` (decided:
inspected and clean / delivered nothing). Downstream engines must resolve ``None`` to
INDETERMINATE; they must never coerce it to ``0`` (or to ``quantity_ordered``). The mechanism is
already in the ingest substrate: :func:`quality_core.io.validate_table` normalises a blank cell to
``None`` before the row model sees it, so a blank column resolves to the sentinel and an explicit
``0`` resolves to ``0``. The same rule governs every optional date field — an absent or
unparseable date is ``None``, never an imputed or defaulted date.

CSV column aliasing
-------------------
Each CSV shape carries an alias map (``RECEIPT_COLUMN_ALIASES``, ``DELIVERY_COLUMN_ALIASES``,
``SCAR_COLUMN_ALIASES``) applied by :func:`_normalize_sqe_columns` *between* the read and the
validate step. Lookup is by the source header's stripped, lower-cased spelling; every map
includes the lower-cased canonical field name itself, so an already-canonical file takes the same
code path with no rename. A header with no entry in the map passes through unchanged and is then
dropped by ``validate_table``'s narrowing, exactly like every other engine's ingest. The maps are
deterministic house vocabulary, not standards-derived — there is no authority to check them
against. The accepted spellings are:

Receipt (``SQE_RECEIPT_SCHEMA``)
    - ``supplier_id`` <- supplier id, supplier, vendor_id, vendor id, vendor
    - ``lot_id`` <- lot id, lot number, lot_number, lot no, lot_no, lot#, lot
    - ``receipt_date`` <- receipt date, date received, received_date, received date
    - ``quantity_received`` <- qty received, qty_received, quantity, qty, lot size, lot_size,
      lot_qty
    - ``defect_count`` <- defects, defect qty, defect_qty, qty defective, rejected_qty,
      rejected qty, rejects
    - ``opportunities_per_unit`` <- opportunities per unit, opportunities, opportunity_count,
      opportunity count

Delivery (``SQE_DELIVERY_SCHEMA``)
    - ``supplier_id`` <- supplier id, supplier, vendor_id, vendor id, vendor
    - ``order_id`` <- order id, order number, order_number, po, po_number, po number,
      purchase order
    - ``quantity_ordered`` <- qty ordered, qty_ordered, quantity, ordered_qty, order qty,
      order_qty
    - ``quantity_delivered`` <- qty delivered, qty_delivered, delivered, delivered_qty,
      received qty, received_qty
    - ``requested_date`` <- requested date, request date, need by, need_by_date, requested
    - ``promised_date`` <- promised date, promise date, commit date, commit_date, due date,
      due_date
    - ``actual_delivery_date`` <- actual delivery date, actual date, actual_date, delivery date,
      delivery_date, delivered date, delivered_date

SCAR (``SQE_SCAR_SCHEMA``)
    - ``supplier_id`` <- supplier id, supplier, vendor_id, vendor id, vendor
    - ``issue_description`` <- issue description, issue, description, problem, problem statement,
      problem_statement, concern
    - ``scar_id`` <- scar id, scar number, scar_number, scar#, scar
    - ``linked_ncr_id`` <- linked ncr id, ncr_id, ncr id, ncr, linked_ncr
    - ``date_issued`` <- date issued, issued_date, issued date, issue date, opened_date
    - ``due_date`` <- due date, response_due, response due, response_due_date
    - ``requested_by`` <- requested by, requestor, requester, raised_by, raised by, owner

``SCARRequest`` is a *request* record only: it carries linkage IDs as plain optional strings and
never authors a root cause or validates against ``quality_core.ncr``/``rca``/``copq`` — that
dispatch belongs to E6.
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Annotated, Any, BinaryIO, cast

import pandas as pd
import pydantic

from quality_core.io import (
    IngestError,
    TableSchema,
    read_table,
    read_table_from_path,
    validate_table,
)
from quality_core.schema._base import find_duplicates

__all__ = [
    "DeliveryRecord",
    "DeliveryRecordDataset",
    "IngestError",
    "ReceiptLot",
    "ReceiptLotDataset",
    "SCARRequest",
    "SCARRequestDataset",
    "SQE_DELIVERY_SCHEMA",
    "SQE_RECEIPT_SCHEMA",
    "SQE_SCAR_SCHEMA",
    "Supplier",
    "SupplierPeriod",
    "load_sqe_delivery_csv",
    "load_sqe_receipt_csv",
    "load_sqe_scar_csv",
    "validate_sqe_delivery",
    "validate_sqe_receipt",
    "validate_sqe_scar",
]


# ===========================================================================
# Shared field-normalisation helpers
# ===========================================================================


def _reject_blank_string(v: object) -> object:
    """Strip a required string cell, rejecting a blank/whitespace-only one; pass non-strings."""
    if isinstance(v, str) and not v.strip():
        raise ValueError("must not be blank or whitespace-only")
    return v.strip() if isinstance(v, str) else v


def _blank_string_to_none(v: object) -> object:
    """Normalise a blank/``None`` optional string cell to ``None``; strip an otherwise-present one."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return v.strip() if isinstance(v, str) else v


def _parse_date_lenient(v: object) -> object:
    """Parse an optional date cell leniently: unparseable or absent resolves to ``None``.

    A missing date is *undecided*, not an error and not a value to impute — downstream engines
    resolve it to INDETERMINATE. So this never raises and never substitutes today's date or a
    neighbouring row's date.
    """
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, datetime.date):
        return v
    try:
        return pd.to_datetime(cast("Any", v)).date()
    except (ValueError, TypeError):
        return None


# ===========================================================================
# Caller-constructed models (no CSV path, no TableSchema)
# ===========================================================================


class Supplier(pydantic.BaseModel):
    """Caller-constructed supplier identity. Not CSV-ingested: there is no supplier roster schema."""

    supplier_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    supplier_name: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    commodity: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None

    @pydantic.field_validator("supplier_id", "supplier_name", mode="before")
    @classmethod
    def reject_blank_required_fields(cls, v: object) -> object:
        return _reject_blank_string(v)

    @pydantic.field_validator("commodity", mode="before")
    @classmethod
    def normalize_optional_strings(cls, v: object) -> object:
        return _blank_string_to_none(v)


class SupplierPeriod(pydantic.BaseModel):
    """Caller-supplied evaluation window.

    Not CSV-ingested. Consumed downstream to filter ReceiptLot/DeliveryRecord datasets by
    ``supplier_id`` and the inclusive window ``[period_start, period_end]``. Both bounds are
    required and parsed strictly: a broken window is a caller bug, not an undecided state.
    """

    supplier_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    period_start: datetime.date
    period_end: datetime.date
    period_label: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None

    @pydantic.field_validator("supplier_id", mode="before")
    @classmethod
    def reject_blank_required_fields(cls, v: object) -> object:
        return _reject_blank_string(v)

    @pydantic.field_validator("period_label", mode="before")
    @classmethod
    def normalize_optional_strings(cls, v: object) -> object:
        return _blank_string_to_none(v)

    @pydantic.model_validator(mode="after")
    def validate_window(self) -> "SupplierPeriod":
        if self.period_end < self.period_start:
            raise ValueError("period_end must not be before period_start")
        return self


# ===========================================================================
# Receipt lots
# ===========================================================================


class ReceiptLot(pydantic.BaseModel):
    """One supplier receipt-lot row.

    ``defect_count=None`` is the undecided sentinel: the lot has not (yet) been
    inspected/counted. It MUST NOT be treated as zero defects by any downstream engine —
    a PPM numerator and a scorecard band suppression both key off that distinction.
    """

    supplier_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    lot_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    quantity_received: Annotated[int, pydantic.Field(ge=1)]
    receipt_date: datetime.date | None = None
    defect_count: Annotated[int | None, pydantic.Field(default=None, ge=0)] = None
    opportunities_per_unit: Annotated[int | None, pydantic.Field(default=None, ge=1)] = None

    @pydantic.field_validator("supplier_id", "lot_id", mode="before")
    @classmethod
    def reject_blank_required_fields(cls, v: object) -> object:
        return _reject_blank_string(v)

    @pydantic.field_validator("receipt_date", mode="before")
    @classmethod
    def parse_dates_lenient(cls, v: object) -> object:
        return _parse_date_lenient(v)

    @pydantic.model_validator(mode="after")
    def reject_defects_exceeding_received(self) -> "ReceiptLot":
        # A counted lot cannot have more defectives than it received. The undecided
        # sentinel (defect_count is None) is exempt: it is "not yet counted", not a
        # quantity, and must survive ingestion rather than be rejected here.
        if self.defect_count is not None and self.defect_count > self.quantity_received:
            raise ValueError(
                f"defect_count ({self.defect_count}) cannot exceed quantity_received "
                f"({self.quantity_received})"
            )
        return self


class ReceiptLotDataset(pydantic.BaseModel):
    """Collection of supplier receipt lots representing one ingested receipt dataset."""

    records: list[ReceiptLot] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="before")
    @classmethod
    def _coerce_rows_to_records(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rows" in data and "records" not in data:
                data = dict(data)
                data["records"] = data.pop("rows")
        return data

    @property
    def rows(self) -> list[ReceiptLot]:
        return self.records

    @pydantic.model_validator(mode="after")
    def validate_dataset_rules(self) -> "ReceiptLotDataset":
        if not self.records:
            raise ValueError("ReceiptLotDataset must contain at least one record")
        dupes = find_duplicates([r.lot_id for r in self.records])
        if dupes:
            raise ValueError(f"duplicate lot_id values found: {dupes}")
        return self


# ===========================================================================
# Delivery records
# ===========================================================================


class DeliveryRecord(pydantic.BaseModel):
    """One supplier delivery/order row.

    ``quantity_delivered=None`` is the undecided sentinel for a shipment not yet
    received/counted — never coerce it to ``0`` (which would falsely fail "in-full") nor to
    ``quantity_ordered`` (which would falsely pass it). Missing or unparseable dates are likewise
    ``None``; downstream OTIF resolves both cases to INDETERMINATE rather than imputing a date.
    """

    supplier_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    order_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    quantity_ordered: Annotated[int, pydantic.Field(ge=1)]
    quantity_delivered: Annotated[int | None, pydantic.Field(default=None, ge=0)] = None
    requested_date: datetime.date | None = None
    promised_date: datetime.date | None = None
    actual_delivery_date: datetime.date | None = None

    @pydantic.field_validator("supplier_id", "order_id", mode="before")
    @classmethod
    def reject_blank_required_fields(cls, v: object) -> object:
        return _reject_blank_string(v)

    @pydantic.field_validator(
        "requested_date",
        "promised_date",
        "actual_delivery_date",
        mode="before",
    )
    @classmethod
    def parse_dates_lenient(cls, v: object) -> object:
        return _parse_date_lenient(v)

    @pydantic.model_validator(mode="after")
    def reject_delivered_exceeding_ordered(self) -> "DeliveryRecord":
        # A shipment cannot deliver more than was ordered. The undecided sentinel
        # (quantity_delivered is None) is exempt: it is "not yet counted", not a
        # quantity, and must survive ingestion for OTIF to resolve INDETERMINATE.
        if (
            self.quantity_delivered is not None
            and self.quantity_delivered > self.quantity_ordered
        ):
            raise ValueError(
                f"quantity_delivered ({self.quantity_delivered}) cannot exceed "
                f"quantity_ordered ({self.quantity_ordered})"
            )
        return self


class DeliveryRecordDataset(pydantic.BaseModel):
    """Collection of supplier delivery records representing one ingested delivery dataset."""

    records: list[DeliveryRecord] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="before")
    @classmethod
    def _coerce_rows_to_records(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rows" in data and "records" not in data:
                data = dict(data)
                data["records"] = data.pop("rows")
        return data

    @property
    def rows(self) -> list[DeliveryRecord]:
        return self.records

    @pydantic.model_validator(mode="after")
    def validate_dataset_rules(self) -> "DeliveryRecordDataset":
        if not self.records:
            raise ValueError("DeliveryRecordDataset must contain at least one record")
        dupes = find_duplicates([r.order_id for r in self.records])
        if dupes:
            raise ValueError(f"duplicate order_id values found: {dupes}")
        return self


# ===========================================================================
# SCAR requests
# ===========================================================================


class SCARRequest(pydantic.BaseModel):
    """A request to open a Supplier Corrective Action Request — structural input only.

    Does NOT author a root cause (that invariant belongs to the SCAR generator), and the linkage
    fields are plain optional IDs, structurally inert at this layer: they are not validated
    against ``quality_core.ncr``/``rca``/``copq`` here.
    """

    supplier_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    issue_description: Annotated[str, pydantic.Field(min_length=1, max_length=4000)]
    scar_id: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None
    linked_ncr_id: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None
    date_issued: datetime.date | None = None
    due_date: datetime.date | None = None
    requested_by: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None

    @pydantic.field_validator("supplier_id", "issue_description", mode="before")
    @classmethod
    def reject_blank_required_fields(cls, v: object) -> object:
        return _reject_blank_string(v)

    @pydantic.field_validator("scar_id", "linked_ncr_id", "requested_by", mode="before")
    @classmethod
    def normalize_optional_strings(cls, v: object) -> object:
        return _blank_string_to_none(v)

    @pydantic.field_validator("date_issued", "due_date", mode="before")
    @classmethod
    def parse_dates_lenient(cls, v: object) -> object:
        return _parse_date_lenient(v)


class SCARRequestDataset(pydantic.BaseModel):
    """Collection of SCAR requests representing one ingested SCAR dataset."""

    records: list[SCARRequest] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="before")
    @classmethod
    def _coerce_rows_to_records(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rows" in data and "records" not in data:
                data = dict(data)
                data["records"] = data.pop("rows")
        return data

    @property
    def rows(self) -> list[SCARRequest]:
        return self.records

    @pydantic.model_validator(mode="after")
    def validate_dataset_rules(self) -> "SCARRequestDataset":
        if not self.records:
            raise ValueError("SCARRequestDataset must contain at least one record")
        # scar_id may not be assigned yet, so only assigned ids participate in the dedup check.
        scar_ids = [r.scar_id for r in self.records if r.scar_id is not None]
        dupes = find_duplicates(scar_ids)
        if dupes:
            raise ValueError(f"duplicate scar_id values found: {dupes}")
        return self


# ===========================================================================
# TableSchema descriptors
# ===========================================================================


SQE_RECEIPT_SCHEMA = TableSchema(
    name="Supplier Receipt Lot",
    row_model=ReceiptLot,
    required_columns=(
        "supplier_id",
        "lot_id",
        "quantity_received",
    ),
    optional_columns=(
        "receipt_date",
        "defect_count",
        "opportunities_per_unit",
    ),
    dataset_model=ReceiptLotDataset,
    template_hint="data/sqe_receipt_template.csv",
)

SQE_DELIVERY_SCHEMA = TableSchema(
    name="Supplier Delivery Record",
    row_model=DeliveryRecord,
    required_columns=(
        "supplier_id",
        "order_id",
        "quantity_ordered",
    ),
    optional_columns=(
        "quantity_delivered",
        "requested_date",
        "promised_date",
        "actual_delivery_date",
    ),
    dataset_model=DeliveryRecordDataset,
    template_hint="data/sqe_delivery_template.csv",
)

SQE_SCAR_SCHEMA = TableSchema(
    name="SCAR Request",
    row_model=SCARRequest,
    required_columns=(
        "supplier_id",
        "issue_description",
    ),
    optional_columns=(
        "scar_id",
        "linked_ncr_id",
        "date_issued",
        "due_date",
        "requested_by",
    ),
    dataset_model=SCARRequestDataset,
    template_hint="data/sqe_scar_template.csv",
)


# ===========================================================================
# CSV column-alias normalisation
# ===========================================================================


RECEIPT_COLUMN_ALIASES: dict[str, str] = {
    "supplier_id": "supplier_id",
    "supplier id": "supplier_id",
    "supplier": "supplier_id",
    "vendor_id": "supplier_id",
    "vendor id": "supplier_id",
    "vendor": "supplier_id",
    "lot_id": "lot_id",
    "lot id": "lot_id",
    "lot number": "lot_id",
    "lot_number": "lot_id",
    "lot no": "lot_id",
    "lot_no": "lot_id",
    "lot#": "lot_id",
    "lot": "lot_id",
    "receipt_date": "receipt_date",
    "receipt date": "receipt_date",
    "date received": "receipt_date",
    "received_date": "receipt_date",
    "received date": "receipt_date",
    "quantity_received": "quantity_received",
    "qty received": "quantity_received",
    "qty_received": "quantity_received",
    "quantity": "quantity_received",
    "qty": "quantity_received",
    "lot size": "quantity_received",
    "lot_size": "quantity_received",
    "lot_qty": "quantity_received",
    "defect_count": "defect_count",
    "defects": "defect_count",
    "defect qty": "defect_count",
    "defect_qty": "defect_count",
    "qty defective": "defect_count",
    "rejected_qty": "defect_count",
    "rejected qty": "defect_count",
    "rejects": "defect_count",
    "opportunities_per_unit": "opportunities_per_unit",
    "opportunities per unit": "opportunities_per_unit",
    "opportunities": "opportunities_per_unit",
    "opportunity_count": "opportunities_per_unit",
    "opportunity count": "opportunities_per_unit",
}

DELIVERY_COLUMN_ALIASES: dict[str, str] = {
    "supplier_id": "supplier_id",
    "supplier id": "supplier_id",
    "supplier": "supplier_id",
    "vendor_id": "supplier_id",
    "vendor id": "supplier_id",
    "vendor": "supplier_id",
    "order_id": "order_id",
    "order id": "order_id",
    "order number": "order_id",
    "order_number": "order_id",
    "po": "order_id",
    "po_number": "order_id",
    "po number": "order_id",
    "purchase order": "order_id",
    "quantity_ordered": "quantity_ordered",
    "quantity ordered": "quantity_ordered",
    "qty ordered": "quantity_ordered",
    "qty_ordered": "quantity_ordered",
    "quantity": "quantity_ordered",
    "ordered_qty": "quantity_ordered",
    "order qty": "quantity_ordered",
    "order_qty": "quantity_ordered",
    "quantity_delivered": "quantity_delivered",
    "quantity delivered": "quantity_delivered",
    "qty delivered": "quantity_delivered",
    "qty_delivered": "quantity_delivered",
    "delivered": "quantity_delivered",
    "delivered_qty": "quantity_delivered",
    "received qty": "quantity_delivered",
    "received_qty": "quantity_delivered",
    "requested_date": "requested_date",
    "requested date": "requested_date",
    "request date": "requested_date",
    "need by": "requested_date",
    "need_by_date": "requested_date",
    "requested": "requested_date",
    "promised_date": "promised_date",
    "promised date": "promised_date",
    "promise date": "promised_date",
    "commit date": "promised_date",
    "commit_date": "promised_date",
    "due date": "promised_date",
    "due_date": "promised_date",
    "actual_delivery_date": "actual_delivery_date",
    "actual delivery date": "actual_delivery_date",
    "actual date": "actual_delivery_date",
    "actual_date": "actual_delivery_date",
    "delivery date": "actual_delivery_date",
    "delivery_date": "actual_delivery_date",
    "delivered date": "actual_delivery_date",
    "delivered_date": "actual_delivery_date",
}

SCAR_COLUMN_ALIASES: dict[str, str] = {
    "supplier_id": "supplier_id",
    "supplier id": "supplier_id",
    "supplier": "supplier_id",
    "vendor_id": "supplier_id",
    "vendor id": "supplier_id",
    "vendor": "supplier_id",
    "issue_description": "issue_description",
    "issue description": "issue_description",
    "issue": "issue_description",
    "description": "issue_description",
    "problem": "issue_description",
    "problem statement": "issue_description",
    "problem_statement": "issue_description",
    "concern": "issue_description",
    "scar_id": "scar_id",
    "scar id": "scar_id",
    "scar number": "scar_id",
    "scar_number": "scar_id",
    "scar#": "scar_id",
    "scar": "scar_id",
    "linked_ncr_id": "linked_ncr_id",
    "linked ncr id": "linked_ncr_id",
    "ncr_id": "linked_ncr_id",
    "ncr id": "linked_ncr_id",
    "ncr": "linked_ncr_id",
    "linked_ncr": "linked_ncr_id",
    "date_issued": "date_issued",
    "date issued": "date_issued",
    "issued_date": "date_issued",
    "issued date": "date_issued",
    "issue date": "date_issued",
    "opened_date": "date_issued",
    "due_date": "due_date",
    "due date": "due_date",
    "response_due": "due_date",
    "response due": "due_date",
    "response_due_date": "due_date",
    "requested_by": "requested_by",
    "requested by": "requested_by",
    "requestor": "requested_by",
    "requester": "requested_by",
    "raised_by": "requested_by",
    "raised by": "requested_by",
    "owner": "requested_by",
}


def _normalize_sqe_columns(df: pd.DataFrame, aliases: Mapping[str, str]) -> pd.DataFrame:
    """Rename ``df`` columns via a case/whitespace-insensitive alias map.

    Lookup key is the source column's stripped, lower-cased name. ``aliases`` maps every
    accepted spelling (including the canonical name itself, lower-cased) to the exact
    canonical field name ``row_model`` expects. A column whose normalized name has no
    entry in ``aliases`` passes through unchanged (so an unrecognized/extra column still
    reaches ``validate_table``'s "narrow to known columns" step and is silently dropped
    there, matching every other engine's ingest behaviour).
    """
    renames = {
        column: aliases[str(column).strip().lower()]
        for column in df.columns
        if str(column).strip().lower() in aliases
    }
    if not renames:
        return df
    return df.rename(columns=renames)


# ===========================================================================
# CSV loaders — read, alias-normalise, then validate
# ===========================================================================


def _read_source(source: str | BinaryIO) -> pd.DataFrame:
    """Read a trusted path or an uploaded binary stream into a raw DataFrame."""
    if isinstance(source, str):
        return read_table_from_path(source)
    return read_table(source)


def load_sqe_receipt_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded receipt-lot ``.csv`` against :data:`SQE_RECEIPT_SCHEMA`.

    Column headers are alias-normalised before validation. Returns a DataFrame narrowed to the
    validated columns. Raises :class:`IngestError` (a ``ValueError`` subclass) with a user-safe
    message on a malformed upload.
    """
    df = _normalize_sqe_columns(_read_source(source), RECEIPT_COLUMN_ALIASES)
    return validate_table(df, SQE_RECEIPT_SCHEMA)


def load_sqe_delivery_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded delivery ``.csv`` against :data:`SQE_DELIVERY_SCHEMA`.

    Column headers are alias-normalised before validation. Returns a DataFrame narrowed to the
    validated columns. Raises :class:`IngestError` (a ``ValueError`` subclass) with a user-safe
    message on a malformed upload.
    """
    df = _normalize_sqe_columns(_read_source(source), DELIVERY_COLUMN_ALIASES)
    return validate_table(df, SQE_DELIVERY_SCHEMA)


def load_sqe_scar_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded SCAR-request ``.csv`` against :data:`SQE_SCAR_SCHEMA`.

    Column headers are alias-normalised before validation. Returns a DataFrame narrowed to the
    validated columns. Raises :class:`IngestError` (a ``ValueError`` subclass) with a user-safe
    message on a malformed upload.
    """
    df = _normalize_sqe_columns(_read_source(source), SCAR_COLUMN_ALIASES)
    return validate_table(df, SQE_SCAR_SCHEMA)


# ===========================================================================
# Trust-boundary validators
# ===========================================================================


def _clean_nan(mapping: Mapping[Any, Any]) -> dict[str, Any]:
    """Map pandas missing values to ``None`` so a NaN cell reads as undecided, not as ``nan``."""
    return cast(
        "dict[str, Any]",
        {key: (None if pd.isna(value) else value) for key, value in mapping.items()},
    )


def validate_sqe_receipt(data: Any) -> ReceiptLotDataset:
    """Validate untrusted receipt-lot input (ReceiptLotDataset, DataFrame, list of dicts/records, or dict) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, ReceiptLotDataset):
        return data
    if isinstance(data, pd.DataFrame):
        records = [_clean_nan(row) for row in data.to_dict("records")]
        return ReceiptLotDataset(records=[ReceiptLot(**rec) for rec in records])
    if isinstance(data, list):
        records_list: list[ReceiptLot] = []
        for item in data:
            if isinstance(item, ReceiptLot):
                records_list.append(item)
            elif isinstance(item, dict):
                records_list.append(ReceiptLot(**_clean_nan(item)))
            else:
                raise TypeError(f"Expected ReceiptLot or dict in list, got {type(item).__name__}")
        return ReceiptLotDataset(records=records_list)
    if isinstance(data, dict):
        return ReceiptLotDataset(**_clean_nan(data))
    raise TypeError(
        f"Expected ReceiptLotDataset, DataFrame, list of dicts/records, or dict, got {type(data).__name__}"
    )


def validate_sqe_delivery(data: Any) -> DeliveryRecordDataset:
    """Validate untrusted delivery input (DeliveryRecordDataset, DataFrame, list of dicts/records, or dict) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, DeliveryRecordDataset):
        return data
    if isinstance(data, pd.DataFrame):
        records = [_clean_nan(row) for row in data.to_dict("records")]
        return DeliveryRecordDataset(records=[DeliveryRecord(**rec) for rec in records])
    if isinstance(data, list):
        records_list: list[DeliveryRecord] = []
        for item in data:
            if isinstance(item, DeliveryRecord):
                records_list.append(item)
            elif isinstance(item, dict):
                records_list.append(DeliveryRecord(**_clean_nan(item)))
            else:
                raise TypeError(
                    f"Expected DeliveryRecord or dict in list, got {type(item).__name__}"
                )
        return DeliveryRecordDataset(records=records_list)
    if isinstance(data, dict):
        return DeliveryRecordDataset(**_clean_nan(data))
    raise TypeError(
        f"Expected DeliveryRecordDataset, DataFrame, list of dicts/records, or dict, got {type(data).__name__}"
    )


def validate_sqe_scar(data: Any) -> SCARRequestDataset:
    """Validate untrusted SCAR-request input (SCARRequestDataset, DataFrame, list of dicts/records, or dict) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, SCARRequestDataset):
        return data
    if isinstance(data, pd.DataFrame):
        records = [_clean_nan(row) for row in data.to_dict("records")]
        return SCARRequestDataset(records=[SCARRequest(**rec) for rec in records])
    if isinstance(data, list):
        records_list: list[SCARRequest] = []
        for item in data:
            if isinstance(item, SCARRequest):
                records_list.append(item)
            elif isinstance(item, dict):
                records_list.append(SCARRequest(**_clean_nan(item)))
            else:
                raise TypeError(f"Expected SCARRequest or dict in list, got {type(item).__name__}")
        return SCARRequestDataset(records=records_list)
    if isinstance(data, dict):
        return SCARRequestDataset(**_clean_nan(data))
    raise TypeError(
        f"Expected SCARRequestDataset, DataFrame, list of dicts/records, or dict, got {type(data).__name__}"
    )

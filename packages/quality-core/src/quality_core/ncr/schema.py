"""
schema.py
Nonconformance Reporting (NCR) — shared domain models, schemas, and ingest validators.

Defines Pydantic row and dataset models along with TableSchema descriptors for:
- Nonconformance Records (NonconformanceRecord, NCRDataset, NCR_SCHEMA)
- Standard disposition vocabulary (Scrap, Rework, UseAsIs, ReturnToVendor, Regrade)

Provides CSV loading helpers and trust-boundary validation functions ensuring type coercion,
blank rejection, disposition alias normalization, and unique record ID enforcement.
"""

from __future__ import annotations

from typing import Annotated, Any, BinaryIO, Literal, cast

import pandas as pd
import pydantic

from quality_core.io.validate import IngestError, TableSchema, load_table, load_table_from_path
from quality_core.schema._base import find_duplicates

__all__ = [
    "DISPOSITION_ALIASES",
    "DISPOSITION_VALUES",
    "Disposition",
    "IngestError",
    "NCR_SCHEMA",
    "NCRDataset",
    "NonconformanceRecord",
    "load_ncr_csv",
    "validate_ncr",
]

Disposition = Literal["Scrap", "Rework", "UseAsIs", "ReturnToVendor", "Regrade"]
DISPOSITION_VALUES: tuple[Disposition, ...] = (
    "Scrap",
    "Rework",
    "UseAsIs",
    "ReturnToVendor",
    "Regrade",
)

DISPOSITION_ALIASES: dict[str, Disposition] = {
    # Scrap
    "scrap": "Scrap",
    "scrapped": "Scrap",
    # Rework
    "rework": "Rework",
    "re-work": "Rework",
    "reworked": "Rework",
    "repair": "Rework",
    # UseAsIs
    "useasis": "UseAsIs",
    "use as is": "UseAsIs",
    "use_as_is": "UseAsIs",
    "use-as-is": "UseAsIs",
    "concession": "UseAsIs",
    "deviation": "UseAsIs",
    "accept": "UseAsIs",
    # ReturnToVendor
    "returntovendor": "ReturnToVendor",
    "return to vendor": "ReturnToVendor",
    "return_to_vendor": "ReturnToVendor",
    "return-to-vendor": "ReturnToVendor",
    "rtv": "ReturnToVendor",
    "vendor return": "ReturnToVendor",
    "vendor_return": "ReturnToVendor",
    "supplier return": "ReturnToVendor",
    # Regrade
    "regrade": "Regrade",
    "re-grade": "Regrade",
    "downgrade": "Regrade",
    "down-grade": "Regrade",
    "secondary": "Regrade",
}


class NonconformanceRecord(pydantic.BaseModel):
    """One Nonconformance Record (NCR) capturing an identified nonconformity."""

    part_lot_id: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    defect_description: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    requirement_violated: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    quantity_affected: Annotated[int, pydantic.Field(ge=1)]
    detection_point: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    record_id: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    disposition: Disposition | None = None
    severity: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    rationale: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    approval_authority: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None

    @pydantic.field_validator(
        "part_lot_id",
        "defect_description",
        "requirement_violated",
        "detection_point",
        mode="before",
    )
    @classmethod
    def reject_blank_required_fields(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @pydantic.field_validator(
        "record_id",
        "severity",
        "rationale",
        "approval_authority",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip() if isinstance(v, str) else v

    @pydantic.field_validator("disposition", mode="before")
    @classmethod
    def normalize_disposition(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if not isinstance(v, str):
            return v
        clean = v.strip()
        lowered = clean.lower()
        if lowered in DISPOSITION_ALIASES:
            return DISPOSITION_ALIASES[lowered]
        if clean in DISPOSITION_VALUES:
            return clean  # type: ignore[return-value]
        raise ValueError(
            f"Invalid disposition: '{clean}'. Must be one of {list(DISPOSITION_VALUES)} or recognized alias."
        )


class NCRDataset(pydantic.BaseModel):
    """Collection of Nonconformance Records representing an operational dataset."""

    records: list[NonconformanceRecord] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="before")
    @classmethod
    def _coerce_rows_to_records(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rows" in data and "records" not in data:
                data = dict(data)
                data["records"] = data.pop("rows")
        return data

    @property
    def rows(self) -> list[NonconformanceRecord]:
        return self.records

    @pydantic.model_validator(mode="after")
    def validate_dataset_rules(self) -> "NCRDataset":
        if not self.records:
            raise ValueError("NCRDataset must contain at least one record")
        record_ids = [r.record_id for r in self.records if r.record_id is not None]
        dupes = find_duplicates(record_ids)
        if dupes:
            raise ValueError(f"duplicate record_id values found: {dupes}")
        return self


NCR_SCHEMA = TableSchema(
    name="Nonconformance Record",
    row_model=NonconformanceRecord,
    required_columns=(
        "part_lot_id",
        "defect_description",
        "requirement_violated",
        "quantity_affected",
        "detection_point",
    ),
    optional_columns=(
        "record_id",
        "disposition",
        "severity",
        "rationale",
        "approval_authority",
    ),
    dataset_model=NCRDataset,
    template_hint="data/ncr_template.csv",
)


def load_ncr_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded Nonconformance Record ``.csv`` against :data:`NCR_SCHEMA`.

    Returns a DataFrame narrowed to the validated columns.
    Raises :class:`IngestError` (a ``ValueError`` subclass) with a user-safe message on a malformed upload.
    """
    if isinstance(source, str):
        return load_table_from_path(source, NCR_SCHEMA)
    return load_table(source, NCR_SCHEMA)


def validate_ncr(data: Any) -> NCRDataset:
    """Validate untrusted Nonconformance Record input (NCRDataset, DataFrame, list of dicts/records, or dict) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, NCRDataset):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in row.items()})
            for row in data.to_dict("records")
        ]
        return NCRDataset(records=[NonconformanceRecord(**rec) for rec in records])
    if isinstance(data, list):
        records_list: list[NonconformanceRecord] = []
        for item in data:
            if isinstance(item, NonconformanceRecord):
                records_list.append(item)
            elif isinstance(item, dict):
                clean_rec = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in item.items()})
                records_list.append(NonconformanceRecord(**clean_rec))
            else:
                raise TypeError(f"Expected NonconformanceRecord or dict in list, got {type(item).__name__}")
        return NCRDataset(records=records_list)
    if isinstance(data, dict):
        clean_dict = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in data.items()})
        return NCRDataset(**clean_dict)
    raise TypeError(f"Expected NCRDataset, DataFrame, list of dicts/records, or dict, got {type(data).__name__}")

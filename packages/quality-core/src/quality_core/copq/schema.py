"""
schema.py
Cost of Poor Quality (COPQ) — shared domain models, schemas, and ingest validators.

Defines Pydantic row and dataset models along with TableSchema descriptors for:
- Cost Items (CostItem, COPQDataset, COPQ_SCHEMA)
- Prevention-Appraisal-Failure (PAF) cost taxonomy (PAFCategory, PAF_CATEGORY_VALUES, PAF_CATEGORY_ALIASES)

Provides CSV loading helpers and trust-boundary validation functions ensuring type coercion,
blank rejection, PAF taxonomy alias normalization, cost driver aggregation, and dataset constraints.
"""

from __future__ import annotations

from typing import Annotated, Any, BinaryIO, Literal, cast

import pandas as pd
import pydantic

from quality_core.io.validate import IngestError, TableSchema, load_table, load_table_from_path

__all__ = [
    "COPQ_SCHEMA",
    "COPQDataset",
    "CostItem",
    "IngestError",
    "PAF_CATEGORY_ALIASES",
    "PAF_CATEGORY_VALUES",
    "PAFCategory",
    "load_copq_csv",
    "validate_copq",
]

PAFCategory = Literal["Prevention", "Appraisal", "InternalFailure", "ExternalFailure"]
PAF_CATEGORY_VALUES: tuple[PAFCategory, ...] = (
    "Prevention",
    "Appraisal",
    "InternalFailure",
    "ExternalFailure",
)

PAF_CATEGORY_ALIASES: dict[str, PAFCategory] = {
    # Prevention
    "prevention": "Prevention",
    "p": "Prevention",
    "prev": "Prevention",
    "preventive": "Prevention",
    "preventative": "Prevention",
    # Appraisal
    "appraisal": "Appraisal",
    "a": "Appraisal",
    "appr": "Appraisal",
    "inspection": "Appraisal",
    "testing": "Appraisal",
    "audit": "Appraisal",
    # Internal Failure
    "internal failure": "InternalFailure",
    "internal_failure": "InternalFailure",
    "internalfailure": "InternalFailure",
    "internal": "InternalFailure",
    "if": "InternalFailure",
    "internal failures": "InternalFailure",
    "internal_failures": "InternalFailure",
    # External Failure
    "external failure": "ExternalFailure",
    "external_failure": "ExternalFailure",
    "externalfailure": "ExternalFailure",
    "external": "ExternalFailure",
    "ef": "ExternalFailure",
    "external failures": "ExternalFailure",
    "external_failures": "ExternalFailure",
}


class CostItem(pydantic.BaseModel):
    """One cost entry categorized under the PAF (Prevention-Appraisal-Failure) taxonomy."""

    category: PAFCategory
    description: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    scrap_qty: Annotated[int | None, pydantic.Field(default=None, ge=0)] = None
    unit_cost: Annotated[float | None, pydantic.Field(default=None, ge=0.0, allow_inf_nan=False)] = None
    rework_hours: Annotated[float | None, pydantic.Field(default=None, ge=0.0, allow_inf_nan=False)] = None
    labor_rate: Annotated[float | None, pydantic.Field(default=None, ge=0.0, allow_inf_nan=False)] = None
    containment_hours: Annotated[float | None, pydantic.Field(default=None, ge=0.0, allow_inf_nan=False)] = None
    warranty_units: Annotated[int | None, pydantic.Field(default=None, ge=0)] = None
    warranty_unit_cost: Annotated[float | None, pydantic.Field(default=None, ge=0.0, allow_inf_nan=False)] = None
    direct_cost: Annotated[float | None, pydantic.Field(default=None, ge=0.0, allow_inf_nan=False)] = None

    @pydantic.field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        clean = v.strip()
        if not clean:
            raise ValueError("must not be blank or whitespace-only")
        lowered = clean.lower()
        if lowered in PAF_CATEGORY_ALIASES:
            return PAF_CATEGORY_ALIASES[lowered]
        if clean in PAF_CATEGORY_VALUES:
            return clean  # type: ignore[return-value]
        raise ValueError(
            f"Invalid PAF category: '{clean}'. Must be one of {list(PAF_CATEGORY_VALUES)} or recognized alias."
        )

    @pydantic.field_validator("description", mode="before")
    @classmethod
    def reject_blank_description(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @property
    def total_cost(self) -> float:
        """Calculate the computed total cost for this cost item based on its cost drivers."""
        cost = 0.0
        if self.scrap_qty is not None and self.unit_cost is not None:
            cost += float(self.scrap_qty) * float(self.unit_cost)
        if self.rework_hours is not None and self.labor_rate is not None:
            cost += float(self.rework_hours) * float(self.labor_rate)
        if self.containment_hours is not None and self.labor_rate is not None:
            cost += float(self.containment_hours) * float(self.labor_rate)
        if self.warranty_units is not None and self.warranty_unit_cost is not None:
            cost += float(self.warranty_units) * float(self.warranty_unit_cost)
        if self.direct_cost is not None:
            cost += float(self.direct_cost)
        return cost


class COPQDataset(pydantic.BaseModel):
    """Collection of PAF Cost Items representing a Cost of Poor Quality dataset."""

    items: list[CostItem] = pydantic.Field(default_factory=list)
    revenue_base: Annotated[float | None, pydantic.Field(default=None, gt=0.0, allow_inf_nan=False)] = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def _coerce_rows_to_items(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rows" in data and "items" not in data:
                data = dict(data)
                data["items"] = data.pop("rows")
        return data

    @property
    def rows(self) -> list[CostItem]:
        return self.items

    @pydantic.model_validator(mode="after")
    def validate_dataset_rules(self) -> "COPQDataset":
        if not self.items:
            raise ValueError("COPQDataset must contain at least one item")
        return self

    @property
    def total_cost(self) -> float:
        """Total Cost of Quality (CoQ = Prevention + Appraisal + Internal Failure + External Failure)."""
        return sum(item.total_cost for item in self.items)

    @property
    def prevention_cost(self) -> float:
        """Total Prevention cost."""
        return sum(item.total_cost for item in self.items if item.category == "Prevention")

    @property
    def appraisal_cost(self) -> float:
        """Total Appraisal cost."""
        return sum(item.total_cost for item in self.items if item.category == "Appraisal")

    @property
    def internal_failure_cost(self) -> float:
        """Total Internal Failure cost."""
        return sum(item.total_cost for item in self.items if item.category == "InternalFailure")

    @property
    def external_failure_cost(self) -> float:
        """Total External Failure cost."""
        return sum(item.total_cost for item in self.items if item.category == "ExternalFailure")

    @property
    def copq(self) -> float:
        """Cost of Poor Quality (COPQ = Internal Failure + External Failure)."""
        return self.internal_failure_cost + self.external_failure_cost

    @property
    def cogq(self) -> float:
        """Cost of Good Quality (CoGQ = Prevention + Appraisal)."""
        return self.prevention_cost + self.appraisal_cost

    @property
    def copq_pct_revenue(self) -> float | None:
        """COPQ as a percentage of total revenue base, if revenue_base is provided."""
        if self.revenue_base is None or self.revenue_base <= 0.0:
            return None
        return (self.copq / self.revenue_base) * 100.0


COPQ_SCHEMA = TableSchema(
    name="Cost of Poor Quality",
    row_model=CostItem,
    required_columns=("category", "description"),
    optional_columns=(
        "scrap_qty",
        "unit_cost",
        "rework_hours",
        "labor_rate",
        "containment_hours",
        "warranty_units",
        "warranty_unit_cost",
        "direct_cost",
    ),
    dataset_model=COPQDataset,
    template_hint="data/copq_template.csv",
)


def load_copq_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded Cost of Poor Quality (COPQ) ``.csv`` against :data:`COPQ_SCHEMA`.

    Returns a DataFrame narrowed to the validated columns.
    Raises :class:`IngestError` (a ``ValueError`` subclass) with a user-safe message on a malformed upload.
    """
    if isinstance(source, str):
        return load_table_from_path(source, COPQ_SCHEMA)
    return load_table(source, COPQ_SCHEMA)


def validate_copq(data: Any, revenue_base: float | None = None) -> COPQDataset:
    """Validate untrusted COPQ input (COPQDataset, DataFrame, list of dicts/items, or dict) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, COPQDataset):
        if revenue_base is not None:
            return COPQDataset(items=data.items, revenue_base=revenue_base)
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in row.items()})
            for row in data.to_dict("records")
        ]
        return COPQDataset(
            items=[CostItem(**rec) for rec in records],
            revenue_base=revenue_base,
        )
    if isinstance(data, list):
        items_list: list[CostItem] = []
        for item in data:
            if isinstance(item, CostItem):
                items_list.append(item)
            elif isinstance(item, dict):
                clean_rec = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in item.items()})
                items_list.append(CostItem(**clean_rec))
            else:
                raise TypeError(f"Expected CostItem or dict in list, got {type(item).__name__}")
        return COPQDataset(items=items_list, revenue_base=revenue_base)
    if isinstance(data, dict):
        clean_dict = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in data.items()})
        if revenue_base is not None and "revenue_base" not in clean_dict:
            clean_dict["revenue_base"] = revenue_base
        return COPQDataset(**clean_dict)
    raise TypeError(f"Expected COPQDataset, DataFrame, list of dicts/items, or dict, got {type(data).__name__}")

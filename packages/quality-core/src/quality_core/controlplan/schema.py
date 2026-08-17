"""
schema.py
Control Plan — upload and validation schema.

Defines the Pydantic row/dataset models and the shared :class:`TableSchema` that
the uploader routes through, so a malformed input gives a friendly, row-addressed
error instead of crashing a downstream call. Mirrors MSA and FMEA discipline
(row and dataset model, uniqueness via ``find_duplicates``), plugged into the
cross-app ``quality_core.io`` validated-ingest boundary.

The field set — characteristic, spec/tolerance (LSL/target/USL), measurement
method, sample size/frequency, control method (recommended SPC chart), reaction
plan — is the AIAG Control Plan column structure (see ROADMAP.md §4).
``lsl``/``usl``/``target``/``recommended_chart`` are nullable — not every
characteristic has a tolerance or is SPC-monitored (e.g. attribute go/no-go, visual)
— so they are declared as ``optional_columns`` rather than ``required_columns``.

``source_cause_id`` is a further nullable field: the durable SPC->FMEA join key a row
carries back to the FMEA cause it was derived from
(``quality_core.controlplan.connector.build_control_plan``).

``sample_plan_is_placeholder`` is an optional boolean provenance marker: ``True``
on the rows ``quality_core.controlplan.connector.build_control_plan`` emits, whose
``sample_size``/``frequency``/``reaction_plan`` are the connector's declared
placeholders rather than engineered values. It defaults to ``False``.
"""

from __future__ import annotations

from typing import Annotated, Any, BinaryIO, cast

import pandas as pd
import pydantic

from quality_core.io import IngestError, TableSchema, load_table, load_table_from_path
from quality_core.schema._base import find_duplicates
from quality_core.spc.constants import SPCChart

__all__ = [
    "CONTROL_PLAN_SCHEMA",
    "ControlPlanDataset",
    "ControlPlanRow",
    "IngestError",
    "SPCChart",
    "load_control_plan_csv",
    "validate_control_plan",
]


class ControlPlanRow(pydantic.BaseModel):
    """One characteristic row of a Control Plan.

    Non-strict on purpose: a CSV read by pandas yields numpy scalars, so values
    are coerced (e.g. ``"5"``/``5.0`` → ``5``) rather than rejected for not being
    a native Python type. Blank cells arrive as ``None`` (the ingest boundary
    normalises NaN→None) and are rejected with a clear message.
    """

    characteristic: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    lsl: Annotated[float | None, pydantic.Field(default=None, allow_inf_nan=False)]
    usl: Annotated[float | None, pydantic.Field(default=None, allow_inf_nan=False)]
    target: Annotated[float | None, pydantic.Field(default=None, allow_inf_nan=False)]
    measurement_method: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    sample_size: Annotated[int, pydantic.Field(ge=1)]
    # Free text: "per shift" / "hourly" / "each lot" — not an enum, control plans
    # phrase frequency too many ways to constrain usefully.
    frequency: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    recommended_chart: SPCChart | None = None
    reaction_plan: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    #: Nullable join key back to the FMEA cause this row's control derives from.
    #: None for a manually-added/edited row with no FMEA source.
    source_cause_id: Annotated[str | None, pydantic.Field(default=None, max_length=300)] = None
    #: True when sample_size / frequency / reaction_plan on this row are the
    #: connector's placeholders rather than engineered values.
    sample_plan_is_placeholder: bool = False

    @pydantic.field_validator(
        "characteristic", "measurement_method", "frequency", "reaction_plan", mode="before"
    )
    @classmethod
    def reject_blank(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @pydantic.field_validator("source_cause_id", mode="before")
    @classmethod
    def blank_source_cause_id_to_none(cls, v: object) -> object:
        # A blank cell is the normal "no FMEA source" shape — coerce to None.
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v

    @pydantic.field_validator("sample_plan_is_placeholder", mode="before")
    @classmethod
    def missing_placeholder_flag_to_false(cls, v: object) -> object:
        # An absent/blank cell means "not marked as a placeholder", not an error.
        if v is None or (isinstance(v, str) and not v.strip()):
            return False
        return v

    @pydantic.model_validator(mode="after")
    def check_tolerance(self) -> "ControlPlanRow":
        if self.usl is not None and self.lsl is not None and self.usl <= self.lsl:
            raise ValueError("usl must be greater than lsl")
        if (
            self.target is not None
            and self.lsl is not None
            and self.usl is not None
            and (self.target < self.lsl or self.target > self.usl)
        ):
            raise ValueError("target must be within [lsl, usl]")
        return self


class ControlPlanDataset(pydantic.BaseModel):
    """Cross-row rules for a Control Plan.

    ``characteristic`` is the row identity — a repeated characteristic is a
    duplicate control, so it must be unique across the dataset.
    """

    rows: list[ControlPlanRow]

    @pydantic.model_validator(mode="after")
    def check_unique_characteristics(self) -> "ControlPlanDataset":
        dupes = find_duplicates(row.characteristic for row in self.rows)
        if dupes:
            raise ValueError(f"duplicate characteristic rows found: {dupes}")
        return self


CONTROL_PLAN_SCHEMA = TableSchema(
    name="Control Plan",
    row_model=ControlPlanRow,
    required_columns=(
        "characteristic",
        "measurement_method",
        "sample_size",
        "frequency",
        "reaction_plan",
    ),
    optional_columns=(
        "lsl",
        "usl",
        "target",
        "recommended_chart",
        "source_cause_id",
        "sample_plan_is_placeholder",
    ),
    dataset_model=ControlPlanDataset,
    template_hint="data/control_plan_template.csv",
)


def load_control_plan_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded Control Plan ``.csv`` against :data:`CONTROL_PLAN_SCHEMA`.

    Returns a DataFrame narrowed to the validated columns: the five required ones
    plus whichever of ``lsl``/``usl``/``target``/``recommended_chart``/
    ``source_cause_id``/``sample_plan_is_placeholder`` the upload carried. Raises :class:`IngestError` (a
    ``ValueError`` subclass) with a user-safe message on a malformed upload.
    """
    if isinstance(source, str):
        return load_table_from_path(source, CONTROL_PLAN_SCHEMA)
    return load_table(source, CONTROL_PLAN_SCHEMA)


def validate_control_plan(data: Any) -> ControlPlanDataset:
    """Validate untrusted Control Plan input (DataFrame, dict list, or dataset) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation.
    """
    if isinstance(data, ControlPlanDataset):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in row.items()})
            for row in data.to_dict("records")
        ]
        return ControlPlanDataset(rows=[ControlPlanRow(**rec) for rec in records])
    if isinstance(data, list):
        rows: list[ControlPlanRow] = []
        for item in data:
            if isinstance(item, ControlPlanRow):
                rows.append(item)
            elif isinstance(item, dict):
                clean_rec = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in item.items()})
                rows.append(ControlPlanRow(**clean_rec))
            else:
                raise TypeError(f"Expected ControlPlanRow or dict in list, got {type(item).__name__}")
        return ControlPlanDataset(rows=rows)
    raise TypeError(f"Expected ControlPlanDataset, DataFrame, or list of dicts/rows, got {type(data).__name__}")

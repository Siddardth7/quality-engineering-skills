"""
schema.py
Root Cause Analysis (RCA) — shared domain models, schemas, and ingest validators.

Defines Pydantic row and dataset models along with TableSchema descriptors for:
- 5-Why problem solving (FiveWhyStep, FiveWhyChain, FIVE_WHY_SCHEMA)
- 6M Fishbone cause-and-effect analysis (Category6M, FishboneCause, FishboneDataset, FISHBONE_SCHEMA)
- Kepner-Tregoe Is/Is-Not problem scoping (KTDimension, IsIsNotRow, IsIsNotMatrix, IS_IS_NOT_SCHEMA)

Provides CSV loading helpers and trust-boundary validation functions ensuring type coercion,
blank rejection, taxonomy alias normalization, and cross-row constraint enforcement.
"""

from __future__ import annotations

from typing import Annotated, Any, BinaryIO, Literal, cast, get_args

import pandas as pd
import pydantic

from quality_core.io import IngestError, TableSchema, load_table, load_table_from_path
from quality_core.schema._base import find_duplicates

__all__ = [
    "CATEGORY_6M_VALUES",
    "FISHBONE_SCHEMA",
    "FIVE_WHY_SCHEMA",
    "IS_IS_NOT_SCHEMA",
    "KT_DIMENSIONS",
    "Category6M",
    "FishboneCause",
    "FishboneDataset",
    "FiveWhyChain",
    "FiveWhyStep",
    "IngestError",
    "IsIsNotMatrix",
    "IsIsNotRow",
    "KTDimension",
    "load_fishbone_csv",
    "load_five_why_csv",
    "load_is_is_not_csv",
    "validate_fishbone",
    "validate_five_why",
    "validate_is_is_not",
]

# ==============================================================================
# 1. 5-Why Problem Solving
# ==============================================================================


class FiveWhyStep(pydantic.BaseModel):
    """One step in a 5-Why causal chain.

    Represents an inquiry step linking a specific 'why' question to its
    immediate causal explanation ('because'). Non-strict to support
    coercion from CSV/DataFrame scalar values.
    """

    step_number: Annotated[int, pydantic.Field(ge=1)]
    why: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    because: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]

    @pydantic.field_validator("why", "because", mode="before")
    @classmethod
    def reject_blank_step_fields(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v


class FiveWhyChain(pydantic.BaseModel):
    """Sequential causal chain of 5-Why steps with root cause isolation."""

    problem_statement: Annotated[
        str, pydantic.Field(default="Problem Statement", min_length=1, max_length=2000)
    ]
    steps: list[FiveWhyStep] = pydantic.Field(default_factory=list)
    root_cause: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None

    @pydantic.field_validator("problem_statement", mode="before")
    @classmethod
    def reject_blank_problem_statement(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @pydantic.field_validator("root_cause", mode="before")
    @classmethod
    def reject_blank_root_cause(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @pydantic.model_validator(mode="before")
    @classmethod
    def _coerce_rows_to_steps(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rows" in data and "steps" not in data:
                data = dict(data)
                data["steps"] = data.pop("rows")
        return data

    @property
    def rows(self) -> list[FiveWhyStep]:
        return self.steps

    @pydantic.model_validator(mode="after")
    def check_sequential_steps(self) -> "FiveWhyChain":
        if not self.steps:
            raise ValueError("FiveWhyChain must contain at least one step")
        step_numbers = [s.step_number for s in self.steps]
        dupes = find_duplicates(step_numbers)
        if dupes:
            raise ValueError(f"duplicate step numbers found: {dupes}")
        expected = list(range(1, len(self.steps) + 1))
        if step_numbers != expected:
            raise ValueError(
                f"step numbers must be consecutive integers starting from 1 (expected {expected}, got {step_numbers})"
            )
        return self


FIVE_WHY_SCHEMA = TableSchema(
    name="5-Why",
    row_model=FiveWhyStep,
    required_columns=("step_number", "why", "because"),
    optional_columns=(),
    dataset_model=FiveWhyChain,
    template_hint="data/five_why_template.csv",
)


def load_five_why_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded 5-Why ``.csv`` against :data:`FIVE_WHY_SCHEMA`.

    Returns a DataFrame narrowed to the validated columns (``step_number``, ``why``, ``because``).
    Raises :class:`IngestError` (a ``ValueError`` subclass) with a user-safe message on a malformed upload.
    """
    if isinstance(source, str):
        return load_table_from_path(source, FIVE_WHY_SCHEMA)
    return load_table(source, FIVE_WHY_SCHEMA)


def validate_five_why(
    data: Any,
    problem_statement: str = "Problem Statement",
    root_cause: str | None = None,
) -> FiveWhyChain:
    """Validate untrusted 5-Why input (FiveWhyChain, DataFrame, list of dicts/steps, or dict) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, FiveWhyChain):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in row.items()})
            for row in data.to_dict("records")
        ]
        return FiveWhyChain(
            problem_statement=problem_statement,
            steps=[FiveWhyStep(**rec) for rec in records],
            root_cause=root_cause,
        )
    if isinstance(data, list):
        steps: list[FiveWhyStep] = []
        for item in data:
            if isinstance(item, FiveWhyStep):
                steps.append(item)
            elif isinstance(item, dict):
                clean_rec = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in item.items()})
                steps.append(FiveWhyStep(**clean_rec))
            else:
                raise TypeError(f"Expected FiveWhyStep or dict in list, got {type(item).__name__}")
        return FiveWhyChain(problem_statement=problem_statement, steps=steps, root_cause=root_cause)
    if isinstance(data, dict):
        clean_dict = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in data.items()})
        return FiveWhyChain(**clean_dict)
    raise TypeError(f"Expected FiveWhyChain, DataFrame, list of dicts/steps, or dict, got {type(data).__name__}")


# ==============================================================================
# 2. 6M Fishbone (Cause-and-Effect) Analysis
# ==============================================================================

Category6M = Literal["Man", "Machine", "Method", "Material", "Measurement", "Environment"]
CATEGORY_6M_VALUES: tuple[Category6M, ...] = (
    "Man",
    "Machine",
    "Method",
    "Material",
    "Measurement",
    "Environment",
)

CATEGORY_6M_ALIASES: dict[str, Category6M] = {
    # Man
    "man": "Man",
    "manpower": "Man",
    "man power": "Man",
    "man_power": "Man",
    "people": "Man",
    "personnel": "Man",
    "worker": "Man",
    "workers": "Man",
    "operator": "Man",
    "operators": "Man",
    # Machine
    "machine": "Machine",
    "machines": "Machine",
    "equipment": "Machine",
    "tools": "Machine",
    "tooling": "Machine",
    "machinery": "Machine",
    "technology": "Machine",
    "hardware": "Machine",
    # Method
    "method": "Method",
    "methods": "Method",
    "process": "Method",
    "processes": "Method",
    "procedure": "Method",
    "procedures": "Method",
    "work method": "Method",
    "method of work": "Method",
    # Material
    "material": "Material",
    "materials": "Material",
    "raw material": "Material",
    "raw materials": "Material",
    "parts": "Material",
    "supply": "Material",
    "supplies": "Material",
    # Measurement
    "measurement": "Measurement",
    "measurements": "Measurement",
    "measure": "Measurement",
    "inspection": "Measurement",
    "testing": "Measurement",
    "gage": "Measurement",
    "gauge": "Measurement",
    "metrology": "Measurement",
    "measuring method": "Measurement",
    # Environment
    "environment": "Environment",
    "milieu": "Environment",
    "mother nature": "Environment",
    "mother_nature": "Environment",
    "nature": "Environment",
    "surroundings": "Environment",
    "environmental": "Environment",
}


class FishboneCause(pydantic.BaseModel):
    """One cause entry in a 6M Fishbone (Ishikawa) diagram."""

    category: Category6M
    cause: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    sub_category: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None

    @pydantic.field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        clean = v.strip()
        if not clean:
            raise ValueError("must not be blank or whitespace-only")
        lowered = clean.lower()
        if lowered in CATEGORY_6M_ALIASES:
            return CATEGORY_6M_ALIASES[lowered]
        if clean in CATEGORY_6M_VALUES:
            return clean
        raise ValueError(
            f"Invalid 6M category: '{clean}'. Must be one of {list(CATEGORY_6M_VALUES)} or recognized alias."
        )

    @pydantic.field_validator("cause", mode="before")
    @classmethod
    def reject_blank_cause(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @pydantic.field_validator("sub_category", mode="before")
    @classmethod
    def normalize_sub_category(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip() if isinstance(v, str) else v


class FishboneDataset(pydantic.BaseModel):
    """Collection of causes grouped under an effect statement for 6M Fishbone analysis."""

    effect: Annotated[
        str, pydantic.Field(default="Problem Effect", min_length=1, max_length=2000)
    ]
    causes: list[FishboneCause] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("effect", mode="before")
    @classmethod
    def reject_blank_effect(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @pydantic.model_validator(mode="before")
    @classmethod
    def _coerce_rows_to_causes(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "rows" in data and "causes" not in data:
                data = dict(data)
                data["causes"] = data.pop("rows")
        return data

    @property
    def rows(self) -> list[FishboneCause]:
        return self.causes

    @pydantic.model_validator(mode="after")
    def check_causes_non_empty(self) -> "FishboneDataset":
        if not self.causes:
            raise ValueError("FishboneDataset must contain at least one cause")
        return self


FISHBONE_SCHEMA = TableSchema(
    name="Fishbone",
    row_model=FishboneCause,
    required_columns=("category", "cause"),
    optional_columns=("sub_category",),
    dataset_model=FishboneDataset,
    template_hint="data/fishbone_template.csv",
)


def load_fishbone_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded Fishbone ``.csv`` against :data:`FISHBONE_SCHEMA`.

    Returns a DataFrame narrowed to the validated columns (``category``, ``cause``, and optional ``sub_category``).
    Raises :class:`IngestError` (a ``ValueError`` subclass) with a user-safe message on a malformed upload.
    """
    if isinstance(source, str):
        return load_table_from_path(source, FISHBONE_SCHEMA)
    return load_table(source, FISHBONE_SCHEMA)


def validate_fishbone(
    data: Any,
    effect: str = "Problem Effect",
) -> FishboneDataset:
    """Validate untrusted Fishbone input (FishboneDataset, DataFrame, list of dicts/causes, or dict) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, FishboneDataset):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in row.items()})
            for row in data.to_dict("records")
        ]
        return FishboneDataset(
            effect=effect,
            causes=[FishboneCause(**rec) for rec in records],
        )
    if isinstance(data, list):
        causes: list[FishboneCause] = []
        for item in data:
            if isinstance(item, FishboneCause):
                causes.append(item)
            elif isinstance(item, dict):
                clean_rec = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in item.items()})
                causes.append(FishboneCause(**clean_rec))
            else:
                raise TypeError(f"Expected FishboneCause or dict in list, got {type(item).__name__}")
        return FishboneDataset(effect=effect, causes=causes)
    if isinstance(data, dict):
        clean_dict = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in data.items()})
        return FishboneDataset(**clean_dict)
    raise TypeError(f"Expected FishboneDataset, DataFrame, list of dicts/causes, or dict, got {type(data).__name__}")


# ==============================================================================
# 3. Kepner-Tregoe Is/Is-Not Scoping Matrix
# ==============================================================================

KTDimension = Literal["WHAT", "WHERE", "WHEN", "EXTENT"]
KT_DIMENSIONS: tuple[KTDimension, ...] = ("WHAT", "WHERE", "WHEN", "EXTENT")


class IsIsNotRow(pydantic.BaseModel):
    """One row of a Kepner-Tregoe Is/Is-Not problem scoping matrix."""

    dimension: KTDimension
    is_data: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    is_not_data: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    distinctions: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    changes: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None

    @pydantic.field_validator("dimension", mode="before")
    @classmethod
    def normalize_dimension(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        clean = v.strip()
        if not clean:
            raise ValueError("must not be blank or whitespace-only")
        upper = clean.upper()
        if upper in KT_DIMENSIONS:
            return upper
        raise ValueError(
            f"Invalid Kepner-Tregoe dimension: '{clean}'. Must be one of {list(KT_DIMENSIONS)}."
        )

    @pydantic.field_validator("is_data", "is_not_data", mode="before")
    @classmethod
    def reject_blank_data_fields(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @pydantic.field_validator("distinctions", "changes", mode="before")
    @classmethod
    def normalize_optional_fields(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip() if isinstance(v, str) else v


class IsIsNotMatrix(pydantic.BaseModel):
    """Kepner-Tregoe Is/Is-Not matrix scoping a problem across 4 dimensions."""

    problem_statement: Annotated[
        str, pydantic.Field(default="Problem Statement", min_length=1, max_length=2000)
    ]
    rows: list[IsIsNotRow] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("problem_statement", mode="before")
    @classmethod
    def reject_blank_problem_statement(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        return v.strip() if isinstance(v, str) else v

    @property
    def is_complete(self) -> bool:
        """Return True if all 4 KT dimensions (WHAT, WHERE, WHEN, EXTENT) are present."""
        present = {row.dimension for row in self.rows}
        return set(get_args(KTDimension)).issubset(present)

    @pydantic.model_validator(mode="after")
    def check_unique_dimensions(self) -> "IsIsNotMatrix":
        if not self.rows:
            raise ValueError("IsIsNotMatrix must contain at least one row")
        dupes = find_duplicates(row.dimension for row in self.rows)
        if dupes:
            raise ValueError(f"duplicate dimensions found: {dupes}")
        return self


IS_IS_NOT_SCHEMA = TableSchema(
    name="Is/Is-Not",
    row_model=IsIsNotRow,
    required_columns=("dimension", "is_data", "is_not_data"),
    optional_columns=("distinctions", "changes"),
    dataset_model=IsIsNotMatrix,
    template_hint="data/is_is_not_template.csv",
)


def load_is_is_not_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded Is/Is-Not ``.csv`` against :data:`IS_IS_NOT_SCHEMA`.

    Returns a DataFrame narrowed to the validated columns (``dimension``, ``is_data``, ``is_not_data``, and optional ``distinctions``, ``changes``).
    Raises :class:`IngestError` (a ``ValueError`` subclass) with a user-safe message on a malformed upload.
    """
    if isinstance(source, str):
        return load_table_from_path(source, IS_IS_NOT_SCHEMA)
    return load_table(source, IS_IS_NOT_SCHEMA)


def validate_is_is_not(
    data: Any,
    problem_statement: str = "Problem Statement",
) -> IsIsNotMatrix:
    """Validate untrusted Is/Is-Not input (IsIsNotMatrix, DataFrame, list of dicts/rows, or dict) at trust boundary.

    Raises :class:`pydantic.ValidationError` on any row or dataset constraint violation,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, IsIsNotMatrix):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in row.items()})
            for row in data.to_dict("records")
        ]
        return IsIsNotMatrix(
            problem_statement=problem_statement,
            rows=[IsIsNotRow(**rec) for rec in records],
        )
    if isinstance(data, list):
        rows: list[IsIsNotRow] = []
        for item in data:
            if isinstance(item, IsIsNotRow):
                rows.append(item)
            elif isinstance(item, dict):
                clean_rec = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in item.items()})
                rows.append(IsIsNotRow(**clean_rec))
            else:
                raise TypeError(f"Expected IsIsNotRow or dict in list, got {type(item).__name__}")
        return IsIsNotMatrix(problem_statement=problem_statement, rows=rows)
    if isinstance(data, dict):
        clean_dict = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in data.items()})
        return IsIsNotMatrix(**clean_dict)
    raise TypeError(f"Expected IsIsNotMatrix, DataFrame, list of dicts/rows, or dict, got {type(data).__name__}")

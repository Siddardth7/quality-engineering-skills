"""
quality_core/rca/export.py
Structured multi-sheet Excel exporter for Root Cause Analysis (RCA) suite.

Serializes 5-Why causal chains, 6M Fishbone (Ishikawa) cause-and-effect diagrams,
and Kepner-Tregoe Is/Is-Not problem scoping matrices into styled .xlsx workbooks
using shared table formatting primitives (quality_core.io.write_table_sheet).

Qualitative Domain Declaration:
Root Cause Analysis is a qualitative deductive problem-solving methodology without
numerical formulas or statistical calculation constants. Live formula arithmetic
verification is explicitly N/A for this domain. Exported workbooks serve as structured,
styled qualitative engineering records. Formula-injection security is strictly enforced
for all user-supplied text cells via sanitize_cell / write_table_sheet.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from typing import Any

import openpyxl
import pandas as pd

from quality_core.io import write_table_sheet
from quality_core.rca.fishbone import categorize_fishbone
from quality_core.rca.five_why import validate_five_why_chain
from quality_core.rca.is_is_not import scope_is_is_not
from quality_core.rca.schema import (
    KT_DIMENSIONS,
    FishboneCause,
    FishboneDataset,
    FiveWhyChain,
    FiveWhyStep,
    IsIsNotMatrix,
    IsIsNotRow,
    validate_fishbone,
    validate_five_why,
    validate_is_is_not,
)

__all__ = [
    # Constants
    "FISHBONE_COLUMN_WIDTHS",
    "FISHBONE_EXPORT_COLUMNS",
    "FISHBONE_SHEET_TITLE",
    "FIVE_WHY_COLUMN_WIDTHS",
    "FIVE_WHY_EXPORT_COLUMNS",
    "FIVE_WHY_SHEET_TITLE",
    "IS_IS_NOT_COLUMN_WIDTHS",
    "IS_IS_NOT_EXPORT_COLUMNS",
    "IS_IS_NOT_SHEET_TITLE",
    # Builders & Exporters
    "build_rca_workbook",
    "export_fishbone_workbook",
    "export_five_why_workbook",
    "export_is_is_not_workbook",
    "export_rca_workbook",
    # Benchmark Constructors
    "benchmark_fishbone_dataset",
    "benchmark_five_why_chain",
    "benchmark_is_is_not_matrix",
    "benchmark_rca_datasets",
]

# ==============================================================================
# Layout Constants
# ==============================================================================

# Sheet 1: 5-Why Analysis
FIVE_WHY_SHEET_TITLE: str = "5-Why Analysis"

FIVE_WHY_EXPORT_COLUMNS: tuple[str, ...] = (
    "Step",
    "Why",
    "Because",
    "Reverse_Therefore",
    "Reversible",
    "Systemic_Classification",
    "Anti_Patterns",
)

FIVE_WHY_COLUMN_WIDTHS: dict[str, float] = {
    "Step": 8.0,
    "Why": 36.0,
    "Because": 42.0,
    "Reverse_Therefore": 46.0,
    "Reversible": 12.0,
    "Systemic_Classification": 24.0,
    "Anti_Patterns": 32.0,
}

# Sheet 2: 6M Fishbone
FISHBONE_SHEET_TITLE: str = "6M Fishbone"

FISHBONE_EXPORT_COLUMNS: tuple[str, ...] = (
    "Category",
    "Cause",
    "Sub_Category",
    "Branch_Status",
    "Is_Duplicate",
)

FISHBONE_COLUMN_WIDTHS: dict[str, float] = {
    "Category": 16.0,
    "Cause": 45.0,
    "Sub_Category": 22.0,
    "Branch_Status": 16.0,
    "Is_Duplicate": 14.0,
}

# Sheet 3: Kepner-Tregoe Is-Is Not
IS_IS_NOT_SHEET_TITLE: str = "Kepner-Tregoe Is-Is Not"

IS_IS_NOT_EXPORT_COLUMNS: tuple[str, ...] = (
    "Dimension",
    "IS",
    "IS_NOT",
    "Distinction",
    "Change",
    "Candidate_Hypothesis",
    "Hypothesis_Paired",
)

IS_IS_NOT_COLUMN_WIDTHS: dict[str, float] = {
    "Dimension": 14.0,
    "IS": 34.0,
    "IS_NOT": 34.0,
    "Distinction": 30.0,
    "Change": 30.0,
    "Candidate_Hypothesis": 40.0,
    "Hypothesis_Paired": 18.0,
}


# ==============================================================================
# Helper Table Generators
# ==============================================================================


def _build_five_why_df(data: Any) -> pd.DataFrame:
    """Validate and format 5-Why causal chain data into an export DataFrame."""
    chain = validate_five_why(data)
    validation = validate_five_why_chain(chain)

    step_ap_map: dict[int, list[str]] = {}
    for ap in validation.anti_patterns:
        if ap.step_number is not None:
            step_ap_map.setdefault(ap.step_number, []).append(ap.code)

    records: list[dict[str, Any]] = []
    for step_eval in validation.link_evaluations:
        step_num = step_eval.step_number
        ap_list = step_ap_map.get(step_num, [])
        anti_pattern_str = "; ".join(ap_list) if ap_list else ""
        reversible_str = "Yes" if step_eval.is_reversible else "No"

        records.append(
            {
                "Step": step_num,
                "Why": step_eval.why,
                "Because": step_eval.because,
                "Reverse_Therefore": step_eval.reverse_statement,
                "Reversible": reversible_str,
                "Systemic_Classification": validation.systemic_assessment.classification,
                "Anti_Patterns": anti_pattern_str,
            }
        )

    return pd.DataFrame(records, columns=list(FIVE_WHY_EXPORT_COLUMNS))


def _build_fishbone_df(data: Any) -> pd.DataFrame:
    """Validate and format 6M Fishbone dataset into an export DataFrame."""
    dataset = validate_fishbone(data)
    cat_result = categorize_fishbone(dataset)

    seen_causes: set[str] = set()
    records: list[dict[str, Any]] = []

    for cause in dataset.causes:
        cause_text = cause.cause
        norm_key = cause_text.strip().lower()
        is_dup = norm_key in seen_causes
        seen_causes.add(norm_key)

        branch_cnt = cat_result.branch_counts.get(cause.category, 0)
        branch_status = "Active" if branch_cnt >= 2 else "Bare Leg / Few Causes"

        records.append(
            {
                "Category": cause.category,
                "Cause": cause_text,
                "Sub_Category": cause.sub_category or "",
                "Branch_Status": branch_status,
                "Is_Duplicate": "Yes" if is_dup else "No",
            }
        )

    return pd.DataFrame(records, columns=list(FISHBONE_EXPORT_COLUMNS))


def _build_is_is_not_df(data: Any) -> pd.DataFrame:
    """Validate and format Kepner-Tregoe Is/Is-Not matrix into an export DataFrame."""
    matrix = validate_is_is_not(data)
    scoping_result = scope_is_is_not(matrix)

    candidate_map = {c["dimension"]: c for c in scoping_result.candidate_causes}

    dim_order = {d: i for i, d in enumerate(KT_DIMENSIONS)}
    sorted_rows = sorted(matrix.rows, key=lambda r: dim_order.get(r.dimension, 999))

    records: list[dict[str, Any]] = []
    for row in sorted_rows:
        cause_info = candidate_map.get(row.dimension)
        if cause_info is not None:
            candidate_hyp = cause_info["hypothesis"]
            is_paired = cause_info["is_paired"]
        else:
            candidate_hyp = ""
            is_paired = False

        records.append(
            {
                "Dimension": row.dimension,
                "IS": row.is_data,
                "IS_NOT": row.is_not_data,
                "Distinction": row.distinctions or "",
                "Change": row.changes or "",
                "Candidate_Hypothesis": candidate_hyp,
                "Hypothesis_Paired": "Yes" if is_paired else "No",
            }
        )

    return pd.DataFrame(records, columns=list(IS_IS_NOT_EXPORT_COLUMNS))


# ==============================================================================
# Workbook Builders & Exporters
# ==============================================================================


def build_rca_workbook(
    five_why: FiveWhyChain | pd.DataFrame | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    fishbone: FishboneDataset | pd.DataFrame | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    is_is_not: IsIsNotMatrix | pd.DataFrame | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    *,
    title: str = "RCA Investigation",
) -> openpyxl.Workbook:
    """Build a styled openpyxl Workbook containing one or more RCA sheets.

    Args:
        five_why: Optional 5-Why chain (FiveWhyChain, DataFrame, list, or dict).
        fishbone: Optional 6M Fishbone dataset (FishboneDataset, DataFrame, list, or dict).
        is_is_not: Optional Kepner-Tregoe matrix (IsIsNotMatrix, DataFrame, list, or dict).
        title: Study title. When only one tool is exported and a custom title is given,
            it overrides the default sheet title.

    Returns:
        openpyxl.Workbook with styled tables for all provided RCA tools in canonical order.

    Raises:
        ValueError: If all three arguments (five_why, fishbone, is_is_not) are None.
        TypeError: If any provided argument has an unsupported data type.
        pydantic.ValidationError: If any dataset violates schema constraints.
    """
    if five_why is None and fishbone is None and is_is_not is None:
        raise ValueError(
            "At least one RCA dataset (five_why, fishbone, or is_is_not) must be provided."
        )

    num_tools = sum(1 for x in (five_why, fishbone, is_is_not) if x is not None)
    sheets_to_create: list[tuple[str, pd.DataFrame, tuple[str, ...], dict[str, float]]] = []

    if five_why is not None:
        df_5w = _build_five_why_df(five_why)
        sheet_title = (
            title
            if num_tools == 1 and title != "RCA Investigation"
            else FIVE_WHY_SHEET_TITLE
        )
        sheets_to_create.append((
            sheet_title,
            df_5w,
            FIVE_WHY_EXPORT_COLUMNS,
            FIVE_WHY_COLUMN_WIDTHS,
        ))

    if fishbone is not None:
        df_fb = _build_fishbone_df(fishbone)
        sheet_title = (
            title
            if num_tools == 1 and title != "RCA Investigation"
            else FISHBONE_SHEET_TITLE
        )
        sheets_to_create.append((
            sheet_title,
            df_fb,
            FISHBONE_EXPORT_COLUMNS,
            FISHBONE_COLUMN_WIDTHS,
        ))

    if is_is_not is not None:
        df_in = _build_is_is_not_df(is_is_not)
        sheet_title = (
            title
            if num_tools == 1 and title != "RCA Investigation"
            else IS_IS_NOT_SHEET_TITLE
        )
        sheets_to_create.append((
            sheet_title,
            df_in,
            IS_IS_NOT_EXPORT_COLUMNS,
            IS_IS_NOT_COLUMN_WIDTHS,
        ))

    wb = openpyxl.Workbook()
    for idx, (sh_title, df, cols, widths) in enumerate(sheets_to_create):
        ws = wb.active if idx == 0 else wb.create_sheet()
        write_table_sheet(
            ws,
            df,
            title=sh_title,
            columns=cols,
            col_widths=widths,
        )

    return wb


def export_rca_workbook(
    five_why: FiveWhyChain | pd.DataFrame | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    fishbone: FishboneDataset | pd.DataFrame | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    is_is_not: IsIsNotMatrix | pd.DataFrame | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    *,
    title: str = "RCA Investigation",
) -> bytes:
    """Export an RCA multi-sheet or single-tool workbook to serialized .xlsx bytes."""
    wb = build_rca_workbook(
        five_why=five_why,
        fishbone=fishbone,
        is_is_not=is_is_not,
        title=title,
    )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_five_why_workbook(
    chain: Any, *, title: str = FIVE_WHY_SHEET_TITLE
) -> bytes:
    """Export a 5-Why causal chain to a single-sheet .xlsx workbook."""
    wb = build_rca_workbook(five_why=chain, title=title)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_fishbone_workbook(
    dataset: Any, *, title: str = FISHBONE_SHEET_TITLE
) -> bytes:
    """Export a 6M Fishbone dataset to a single-sheet .xlsx workbook."""
    wb = build_rca_workbook(fishbone=dataset, title=title)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_is_is_not_workbook(
    matrix: Any, *, title: str = IS_IS_NOT_SHEET_TITLE
) -> bytes:
    """Export a Kepner-Tregoe Is/Is-Not matrix to a single-sheet .xlsx workbook."""
    wb = build_rca_workbook(is_is_not=matrix, title=title)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ==============================================================================
# Benchmark Data Constructors
# ==============================================================================

_BENCHMARK_FIVE_WHY_STEPS: tuple[FiveWhyStep, ...] = (
    FiveWhyStep(
        step_number=1,
        why="Why was the bearing worn out?",
        because="It had dried up.",
    ),
    FiveWhyStep(
        step_number=2,
        why="Why did the bearing dry out?",
        because="The operator did not carry out shift autonomous maintenance routines.",
    ),
    FiveWhyStep(
        step_number=3,
        why="Why did the operator not follow the maintenance routine completely?",
        because="He was not properly trained during the induction.",
    ),
    FiveWhyStep(
        step_number=4,
        why="Why was he not trained in the induction?",
        because="Its induction program lost this outside the sheet.",
    ),
    FiveWhyStep(
        step_number=5,
        why="Why was this missing on the sheet?",
        because="The induction plan was not signed by Engineering (Systemic Root Cause).",
    ),
)

_BENCHMARK_FISHBONE_CAUSES: tuple[FishboneCause, ...] = (
    FishboneCause(
        category="Man",
        cause="Operator fatigue during end-of-shift assembly cycle",
        sub_category="Fatigue",
    ),
    FishboneCause(
        category="Man",
        cause="Inconsistent rod seal insertion technique across shifts",
        sub_category="Training",
    ),
    FishboneCause(
        category="Machine",
        cause="CNC rod turning lathe spindle runout exceeding 0.015 mm",
        sub_category="Tooling",
    ),
    FishboneCause(
        category="Machine",
        cause="Pneumatic seal crimping fixture misalignment",
        sub_category="Equipment",
    ),
    FishboneCause(
        category="Method",
        cause="Work instruction missing torque sequence for cylinder tie-rods",
        sub_category="Standard Work",
    ),
    FishboneCause(
        category="Method",
        cause="Inadequate lubrication specification for rod wiper assembly",
        sub_category="Process",
    ),
    FishboneCause(
        category="Material",
        cause="NBR rod seal batch hardness variation (Durometer 65 vs 75 Shore A)",
        sub_category="Incoming Material",
    ),
    FishboneCause(
        category="Material",
        cause="Anodized aluminum barrel bore surface roughness out of spec",
        sub_category="Raw Material",
    ),
    FishboneCause(
        category="Measurement",
        cause="Air leakage test pressure decay gage uncalibrated (drift > 0.05 bar)",
        sub_category="Calibration",
    ),
    FishboneCause(
        category="Measurement",
        cause="Dial indicator rod concentricity fixture deflection",
        sub_category="Gage R&R",
    ),
    FishboneCause(
        category="Environment",
        cause="Assembly cleanroom ambient temperature fluctuation (+/- 8 deg C)",
        sub_category="Temperature",
    ),
    FishboneCause(
        category="Environment",
        cause="Airborne particulate contamination in seal staging area",
        sub_category="Cleanliness",
    ),
)

_BENCHMARK_IS_IS_NOT_ROWS: tuple[IsIsNotRow, ...] = (
    IsIsNotRow(
        dimension="WHAT",
        is_data="Pneumatic cylinder stroke binding and seal leakage requiring manual teardown rework",
        is_not_data="Piston rod surface defect or electrical control circuit failure",
        distinctions="Cylinder bottom mounting face non-parallelism and seal groove distortion",
        changes="Bar stock feed misalignment resulting in undersized cut blank length",
    ),
    IsIsNotRow(
        dimension="WHERE",
        is_data="Cylinder bottom workpiece at CNC milling station (DMC 50H) hydraulic fixture",
        is_not_data="Piston rod CNC lathe turning station (Index G200)",
        distinctions="Hydraulic vice clamping standard depth requires minimum blank mass",
        changes="Sawing station backstop guide position adjusted without laser verification",
    ),
    IsIsNotRow(
        dimension="WHEN",
        is_data="During post-assembly pneumatic pressure decay acceptance testing (trial run 802 units)",
        is_not_data="During initial raw bar stock receiving inspection or pre-machining staging",
        distinctions="Defect manifests only under pressurized stroke test after cylinder tie-rod torquing",
        changes="Production shift handover between saw operator and CNC milling operator",
    ),
    IsIsNotRow(
        dimension="EXTENT",
        is_data="52 out of 802 units (6.48% baseline defect rate), concentrated in blanks with saw_weight < 0.540 kg (15.6% failure rate)",
        is_not_data="All 802 units defective (750 units passed acceptance) or uniform across all blank weights",
        distinctions="Failure rate increases 1.99x for each 1-sigma decrease in saw cut blank weight",
        changes="Sawing cut blank weight variation increased prior to milling operation",
    ),
)


def benchmark_five_why_chain() -> FiveWhyChain:
    """Return a self-contained benchmark FiveWhyChain (Ford Global 8D bearing induction study)."""
    return FiveWhyChain(
        problem_statement="Hole positions outside of tolerance on CNC drilling station",
        steps=list(_BENCHMARK_FIVE_WHY_STEPS),
        root_cause="The induction plan was not signed by Engineering",
    )


def benchmark_fishbone_dataset() -> FishboneDataset:
    """Return a self-contained benchmark FishboneDataset (Pneumatic cylinder functional defect across 6M)."""
    return FishboneDataset(
        effect="Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
        causes=list(_BENCHMARK_FISHBONE_CAUSES),
    )


def benchmark_is_is_not_matrix() -> IsIsNotMatrix:
    """Return a self-contained benchmark IsIsNotMatrix (4-dimension KT problem boundary scoping)."""
    return IsIsNotMatrix(
        problem_statement="Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
        rows=list(_BENCHMARK_IS_IS_NOT_ROWS),
    )


def benchmark_rca_datasets() -> tuple[FiveWhyChain, FishboneDataset, IsIsNotMatrix]:
    """Return a tuple of fresh benchmark datasets: (five_why, fishbone, is_is_not)."""
    return (
        benchmark_five_why_chain(),
        benchmark_fishbone_dataset(),
        benchmark_is_is_not_matrix(),
    )

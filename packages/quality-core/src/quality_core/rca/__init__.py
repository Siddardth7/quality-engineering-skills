"""
quality_core.rca

Root Cause Analysis (RCA) suite: schema definitions, validation boundaries,
and domain models for 5-Why problem solving, 6M Fishbone cause-and-effect
diagrams, and Kepner-Tregoe Is/Is-Not scoping matrices.
"""

from __future__ import annotations

from quality_core.rca.export import (
    FISHBONE_COLUMN_WIDTHS,
    FISHBONE_EXPORT_COLUMNS,
    FISHBONE_SHEET_TITLE,
    FIVE_WHY_COLUMN_WIDTHS,
    FIVE_WHY_EXPORT_COLUMNS,
    FIVE_WHY_SHEET_TITLE,
    IS_IS_NOT_COLUMN_WIDTHS,
    IS_IS_NOT_EXPORT_COLUMNS,
    IS_IS_NOT_SHEET_TITLE,
    benchmark_fishbone_dataset,
    benchmark_five_why_chain,
    benchmark_is_is_not_matrix,
    benchmark_rca_datasets,
    build_rca_workbook,
    export_fishbone_workbook,
    export_five_why_workbook,
    export_is_is_not_workbook,
    export_rca_workbook,
)
from quality_core.rca.fishbone import (
    FishboneCategorizationResult,
    categorize_fishbone,
)
from quality_core.rca.five_why import (
    AntiPatternFinding,
    FiveWhyLinkEval,
    FiveWhyValidationResult,
    SystemicAssessment,
    validate_five_why_chain,
)
from quality_core.rca.is_is_not import (
    CandidateCause,
    IsIsNotScopingResult,
    scope_is_is_not,
)
from quality_core.rca.schema import (
    FISHBONE_SCHEMA,
    FIVE_WHY_SCHEMA,
    IS_IS_NOT_SCHEMA,
    Category6M,
    FishboneCause,
    FishboneDataset,
    FiveWhyChain,
    FiveWhyStep,
    IngestError,
    IsIsNotMatrix,
    IsIsNotRow,
    KTDimension,
    load_fishbone_csv,
    load_five_why_csv,
    load_is_is_not_csv,
    validate_fishbone,
    validate_five_why,
    validate_is_is_not,
)

__all__ = [
    # 5-Why
    "AntiPatternFinding",
    "FIVE_WHY_COLUMN_WIDTHS",
    "FIVE_WHY_EXPORT_COLUMNS",
    "FIVE_WHY_SCHEMA",
    "FIVE_WHY_SHEET_TITLE",
    "FiveWhyChain",
    "FiveWhyLinkEval",
    "FiveWhyStep",
    "FiveWhyValidationResult",
    "SystemicAssessment",
    "benchmark_five_why_chain",
    "export_five_why_workbook",
    "load_five_why_csv",
    "validate_five_why",
    "validate_five_why_chain",
    # Fishbone
    "Category6M",
    "FISHBONE_COLUMN_WIDTHS",
    "FISHBONE_EXPORT_COLUMNS",
    "FISHBONE_SCHEMA",
    "FISHBONE_SHEET_TITLE",
    "FishboneCategorizationResult",
    "FishboneCause",
    "FishboneDataset",
    "benchmark_fishbone_dataset",
    "categorize_fishbone",
    "export_fishbone_workbook",
    "load_fishbone_csv",
    "validate_fishbone",
    # Is/Is-Not
    "CandidateCause",
    "IS_IS_NOT_COLUMN_WIDTHS",
    "IS_IS_NOT_EXPORT_COLUMNS",
    "IS_IS_NOT_SCHEMA",
    "IS_IS_NOT_SHEET_TITLE",
    "IsIsNotMatrix",
    "IsIsNotRow",
    "IsIsNotScopingResult",
    "KTDimension",
    "benchmark_is_is_not_matrix",
    "export_is_is_not_workbook",
    "load_is_is_not_csv",
    "scope_is_is_not",
    "validate_is_is_not",
    # Combined RCA Exporters & Benchmarks
    "benchmark_rca_datasets",
    "build_rca_workbook",
    "export_rca_workbook",
    # Error
    "IngestError",
]


"""
copq — Cost of Poor Quality (COPQ) suite for quality engineering.

Exports the COPQ schema, row and dataset models, PAF taxonomy, ingest loaders, financial estimator engine,
and live-formula Excel exporters.
"""

from __future__ import annotations

from quality_core.copq.estimator import (
    COPQEstimationResult,
    estimate_copq,
)
from quality_core.copq.export import (
    COPQ_COL_WIDTHS,
    COPQ_LEDGER_COLUMNS,
    PAF_SUMMARY_COL_WIDTHS,
    PAF_SUMMARY_COLUMNS,
    benchmark_copq_dataset,
    build_copq_workbook,
    export_copq_excel,
    export_copq_workbook,
)
from quality_core.copq.schema import (
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

__all__ = [
    "COPQ_COL_WIDTHS",
    "COPQ_LEDGER_COLUMNS",
    "COPQ_SCHEMA",
    "COPQDataset",
    "COPQEstimationResult",
    "CostItem",
    "IngestError",
    "PAF_CATEGORY_ALIASES",
    "PAF_CATEGORY_VALUES",
    "PAF_SUMMARY_COLUMNS",
    "PAF_SUMMARY_COL_WIDTHS",
    "PAFCategory",
    "benchmark_copq_dataset",
    "build_copq_workbook",
    "export_copq_excel",
    "export_copq_workbook",
    "estimate_copq",
    "load_copq_csv",
    "validate_copq",
]

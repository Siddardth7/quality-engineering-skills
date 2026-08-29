"""
ncr — Nonconformance Reporting (NCR) suite for quality engineering.

Exports the NCR schema, row and dataset models, disposition vocabulary, ingest loaders,
deterministic defect-statement and disposition recommendation engines, and live-formula Excel exporters.
"""

from __future__ import annotations

from quality_core.ncr.export import (
    DISPOSITION_SUMMARY_COLUMNS,
    NCR_COL_WIDTHS,
    NCR_EXPORT_COLUMNS,
    benchmark_ncr_dataset,
    build_ncr_workbook,
    export_ncr_excel,
    export_ncr_workbook,
)
from quality_core.ncr.nonconformance import (
    DispositionRecommendation,
    NonconformanceWriteResult,
    recommend_disposition,
    write_nonconformance,
)
from quality_core.ncr.schema import (
    DISPOSITION_ALIASES,
    DISPOSITION_VALUES,
    NCR_SCHEMA,
    Disposition,
    IngestError,
    NCRDataset,
    NonconformanceRecord,
    load_ncr_csv,
    validate_ncr,
)

__all__ = [
    "DISPOSITION_ALIASES",
    "DISPOSITION_SUMMARY_COLUMNS",
    "DISPOSITION_VALUES",
    "Disposition",
    "DispositionRecommendation",
    "IngestError",
    "NCR_COL_WIDTHS",
    "NCR_EXPORT_COLUMNS",
    "NCR_SCHEMA",
    "NCRDataset",
    "NonconformanceRecord",
    "NonconformanceWriteResult",
    "benchmark_ncr_dataset",
    "build_ncr_workbook",
    "export_ncr_excel",
    "export_ncr_workbook",
    "load_ncr_csv",
    "recommend_disposition",
    "validate_ncr",
    "write_nonconformance",
]

"""
ncr — Nonconformance Reporting (NCR) suite for quality engineering.

Exports the NCR schema, row and dataset models, disposition vocabulary, ingest loaders,
and deterministic defect-statement and disposition recommendation engines.
"""

from __future__ import annotations

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
    "DISPOSITION_VALUES",
    "Disposition",
    "DispositionRecommendation",
    "IngestError",
    "NCR_SCHEMA",
    "NCRDataset",
    "NonconformanceRecord",
    "NonconformanceWriteResult",
    "load_ncr_csv",
    "recommend_disposition",
    "validate_ncr",
    "write_nonconformance",
]

"""
ncr — Nonconformance Reporting (NCR) suite for quality engineering.

Exports the NCR schema, row and dataset models, disposition vocabulary, and ingest loaders.
"""

from __future__ import annotations

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
    "IngestError",
    "NCR_SCHEMA",
    "NCRDataset",
    "NonconformanceRecord",
    "load_ncr_csv",
    "validate_ncr",
]

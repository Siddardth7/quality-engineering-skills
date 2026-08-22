"""
copq — Cost of Poor Quality (COPQ) suite for quality engineering.

Exports the COPQ schema, row and dataset models, PAF taxonomy, and ingest loaders.
"""

from __future__ import annotations

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

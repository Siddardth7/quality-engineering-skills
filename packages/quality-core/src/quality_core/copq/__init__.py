"""
copq — Cost of Poor Quality (COPQ) suite for quality engineering.

Exports the COPQ schema, row and dataset models, PAF taxonomy, ingest loaders, and financial estimator engine.
"""

from __future__ import annotations

from quality_core.copq.estimator import (
    COPQEstimationResult,
    estimate_copq,
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
    "COPQ_SCHEMA",
    "COPQDataset",
    "COPQEstimationResult",
    "CostItem",
    "IngestError",
    "PAF_CATEGORY_ALIASES",
    "PAF_CATEGORY_VALUES",
    "PAFCategory",
    "estimate_copq",
    "load_copq_csv",
    "validate_copq",
]

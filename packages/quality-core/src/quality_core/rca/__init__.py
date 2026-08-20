"""
quality_core.rca

Root Cause Analysis (RCA) suite: schema definitions, validation boundaries,
and domain models for 5-Why problem solving, 6M Fishbone cause-and-effect
diagrams, and Kepner-Tregoe Is/Is-Not scoping matrices.
"""

from __future__ import annotations

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
    "FIVE_WHY_SCHEMA",
    "FiveWhyChain",
    "FiveWhyStep",
    "load_five_why_csv",
    "validate_five_why",
    # Fishbone
    "Category6M",
    "FISHBONE_SCHEMA",
    "FishboneCause",
    "FishboneDataset",
    "load_fishbone_csv",
    "validate_fishbone",
    # Is/Is-Not
    "IS_IS_NOT_SCHEMA",
    "IsIsNotMatrix",
    "IsIsNotRow",
    "KTDimension",
    "load_is_is_not_csv",
    "validate_is_is_not",
    # Error
    "IngestError",
]

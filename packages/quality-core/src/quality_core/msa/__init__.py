"""Measurement Systems Analysis (MSA) primitives for Quality Platform apps.

Implements AIAG MSA 4th Edition Gage R&R methods (Average-and-Range and ANOVA),
schema validation models, and core constants.

`gage_rr` contains `compute_gage_rr` and the underlying calculation engines.
`schema` contains `GageStudyRow`, `GageStudyDataset`, `GAGE_STUDY_SCHEMA`,
and `load_gage_study_csv`.
`export` contains `export_msa_workbook` and `build_msa_workbook`.
"""

from __future__ import annotations

from quality_core.msa.export import (
    build_msa_workbook,
    export_msa_workbook,
)
from quality_core.msa.gage_rr import (
    _ANOVA_ALPHA,
    _K1,
    _K2,
    _K3,
    _SS_CANCELLATION_FLOOR,
    _STUDY_VARIATION_SIGMA,
    METHOD,
    METHOD_ANOVA,
    METHOD_NOTE,
    METHOD_NOTE_ANOVA,
    _anova_method,
    _average_and_range_method,
    _compute_ndc,
    _compute_verdict,
    _k_constant,
    compute_gage_rr,
)
from quality_core.msa.schema import (
    GAGE_STUDY_SCHEMA,
    GageStudyDataset,
    GageStudyRow,
    IngestError,
    load_gage_study_csv,
)

__all__ = [
    "METHOD",
    "METHOD_ANOVA",
    "METHOD_NOTE",
    "METHOD_NOTE_ANOVA",
    "compute_gage_rr",
    "build_msa_workbook",
    "export_msa_workbook",
    "_K1",
    "_K2",
    "_K3",
    "_STUDY_VARIATION_SIGMA",
    "_ANOVA_ALPHA",
    "_SS_CANCELLATION_FLOOR",
    "_average_and_range_method",
    "_anova_method",
    "_k_constant",
    "_compute_ndc",
    "_compute_verdict",
    "GageStudyRow",
    "GageStudyDataset",
    "GAGE_STUDY_SCHEMA",
    "load_gage_study_csv",
    "IngestError",
]

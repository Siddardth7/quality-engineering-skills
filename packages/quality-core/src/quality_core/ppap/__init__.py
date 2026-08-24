"""
Production Part Approval Process (PPAP) Core Engine — deterministic 18-element auditor,
Table 4.1 submission/retention matrix, applicability rules, PSW field validator,
and cross-engine linkage.
"""

from __future__ import annotations

from quality_core.ppap.applicability import (
    APPLICABILITY_VERDICTS,
    CONDITIONAL_ELEMENTS,
    ApplicabilityResult,
    ApplicabilityVerdict,
    ElementApplicability,
    assess_applicability,
)
from quality_core.ppap.schema import (
    EVIDENCE_STATUS_ALIASES,
    EVIDENCE_STATUS_VALUES,
    PPAP_ELEMENT_ALIASES,
    PPAP_ELEMENT_IDS,
    PPAP_ELEMENT_NAMES,
    PPAP_ELEMENT_NUMBERS,
    PPAP_PACKAGE_SCHEMA,
    REASON_FOR_SUBMISSION_ALIASES,
    REASON_FOR_SUBMISSION_VALUES,
    SUBMISSION_LEVEL_ALIASES,
    SUBMISSION_LEVEL_DESCRIPTIONS,
    SUBMISSION_LEVELS,
    EvidenceItem,
    EvidenceStatus,
    IngestError,
    PPAPElementId,
    PPAPPackage,
    ReasonForSubmission,
    SubmissionLevel,
    load_ppap_csv,
    validate_ppap,
)

__all__ = [
    "APPLICABILITY_VERDICTS",
    "ApplicabilityResult",
    "ApplicabilityVerdict",
    "CONDITIONAL_ELEMENTS",
    "EVIDENCE_STATUS_ALIASES",
    "EVIDENCE_STATUS_VALUES",
    "ElementApplicability",
    "EvidenceItem",
    "EvidenceStatus",
    "IngestError",
    "PPAPElementId",
    "PPAPPackage",
    "PPAP_ELEMENT_ALIASES",
    "PPAP_ELEMENT_IDS",
    "PPAP_ELEMENT_NAMES",
    "PPAP_ELEMENT_NUMBERS",
    "PPAP_PACKAGE_SCHEMA",
    "REASON_FOR_SUBMISSION_ALIASES",
    "REASON_FOR_SUBMISSION_VALUES",
    "ReasonForSubmission",
    "SUBMISSION_LEVELS",
    "SUBMISSION_LEVEL_ALIASES",
    "SUBMISSION_LEVEL_DESCRIPTIONS",
    "SubmissionLevel",
    "assess_applicability",
    "load_ppap_csv",
    "validate_ppap",
]

"""
Production Part Approval Process (PPAP) Core Engine — deterministic 18-element auditor,
Table 4.1 submission/retention matrix, applicability rules, PSW field validator,
Initial Process Studies capability gate, and cross-engine linkage.
"""

from __future__ import annotations

from quality_core.ppap.linkage import (
    LINKABLE_ELEMENTS,
    LinkageElementResult,
    LinkageReport,
    LinkageVerdict,
    validate_element_linkage,
    validate_linked_evidence,
)
from quality_core.ppap.process_study import (
    ACCEPTANCE_THRESHOLD_CAPABLE,
    ACCEPTANCE_THRESHOLD_POTENTIALLY_CAPABLE,
    ACTION_ATTRIBUTE_DATA,
    ACTION_BETWEEN_1_33_AND_1_67,
    ACTION_GREATER_THAN_1_67,
    ACTION_INSUFFICIENT_SAMPLE,
    ACTION_LESS_THAN_1_33,
    ACTION_UNSTABLE,
    MINIMUM_INITIAL_STUDY_SAMPLES,
    MINIMUM_INITIAL_STUDY_SUBGROUPS,
    AcceptanceBand,
    IndexType,
    ProcessStudyResult,
    StudyVerdict,
    assess_initial_process_study,
)

__all__ = [
    "ACCEPTANCE_THRESHOLD_CAPABLE",
    "ACCEPTANCE_THRESHOLD_POTENTIALLY_CAPABLE",
    "ACTION_ATTRIBUTE_DATA",
    "ACTION_BETWEEN_1_33_AND_1_67",
    "ACTION_GREATER_THAN_1_67",
    "ACTION_INSUFFICIENT_SAMPLE",
    "ACTION_LESS_THAN_1_33",
    "ACTION_UNSTABLE",
    "AcceptanceBand",
    "IndexType",
    "LINKABLE_ELEMENTS",
    "LinkageElementResult",
    "LinkageReport",
    "LinkageVerdict",
    "MINIMUM_INITIAL_STUDY_SAMPLES",
    "MINIMUM_INITIAL_STUDY_SUBGROUPS",
    "ProcessStudyResult",
    "StudyVerdict",
    "assess_initial_process_study",
    "validate_element_linkage",
    "validate_linked_evidence",
]

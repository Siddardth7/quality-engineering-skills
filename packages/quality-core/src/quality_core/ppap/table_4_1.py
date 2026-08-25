"""
AIAG PPAP 4th Edition (June 2006) Section 4: Table 4.1 & Table 4.2 Submission and Retention Matrix.

This module encodes the 18-element Production Part Approval Process requirement matrix
across all five submission levels (Levels 1–5) as typed, immutable cited data, along with
the verbatim AIAG standard legend and submission level definitions.

Reuses the shared canonical PPAP element vocabulary (PPAP_ELEMENT_IDS, PPAPElementId)
and submission levels (SUBMISSION_LEVELS, SubmissionLevel) from `quality_core.ppap.schema`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from quality_core.ppap.schema import (
    PPAP_ELEMENT_IDS,
    SUBMISSION_LEVELS,
    PPAPElementId,
    SubmissionLevel,
)

RequirementCode = Literal["S", "R", "*", "CUSTOMER_DEFINED"]

REQUIREMENT_CODES: tuple[RequirementCode, ...] = ("S", "R", "*", "CUSTOMER_DEFINED")

# Export alias matching shared vocabulary
ELEMENT_IDS: tuple[PPAPElementId, ...] = PPAP_ELEMENT_IDS

TABLE_4_1_LEGEND: Mapping[RequirementCode, str] = MappingProxyType({
    "S": "The organization shall submit to the customer and retain a copy of records or documentation items at appropriate locations.",
    "R": "The organization shall retain at appropriate locations and make available to the customer upon request.",
    "*": "The organization shall retain at appropriate locations and submit to the customer upon request.",
    "CUSTOMER_DEFINED": "Warrant and other requirements as defined by the customer.",
})

SUBMISSION_LEVEL_DESCRIPTIONS: Mapping[int, str] = MappingProxyType({
    1: "Warrant only (and for designated appearance items, an Appearance Approval Report) submitted to the customer.",
    2: "Warrant with product samples and limited supporting data submitted to the customer.",
    3: "Warrant with product samples and complete supporting data submitted to the customer.",
    4: "Warrant and other requirements as defined by the customer.",
    5: "Warrant with product samples and complete supporting data reviewed at the organization's manufacturing location.",
})

# Table 4.2 Retention / Submission Requirements Matrix (18 elements × 5 levels = 90 cells)
TABLE_4_1_MATRIX: Mapping[tuple[PPAPElementId, SubmissionLevel], RequirementCode] = MappingProxyType({
    # 2.2.1 Design Record (for all other components/details)
    ("2.2.1", 1): "R",
    ("2.2.1", 2): "S",
    ("2.2.1", 3): "S",
    ("2.2.1", 4): "*",
    ("2.2.1", 5): "R",
    # 2.2.2 Engineering Change Documents (if any)
    ("2.2.2", 1): "R",
    ("2.2.2", 2): "S",
    ("2.2.2", 3): "S",
    ("2.2.2", 4): "*",
    ("2.2.2", 5): "R",
    # 2.2.3 Customer Engineering Approval (if required)
    ("2.2.3", 1): "R",
    ("2.2.3", 2): "R",
    ("2.2.3", 3): "S",
    ("2.2.3", 4): "*",
    ("2.2.3", 5): "R",
    # 2.2.4 Design FMEA (if design responsible)
    ("2.2.4", 1): "R",
    ("2.2.4", 2): "R",
    ("2.2.4", 3): "S",
    ("2.2.4", 4): "*",
    ("2.2.4", 5): "R",
    # 2.2.5 Process Flow Diagrams
    ("2.2.5", 1): "R",
    ("2.2.5", 2): "R",
    ("2.2.5", 3): "S",
    ("2.2.5", 4): "*",
    ("2.2.5", 5): "R",
    # 2.2.6 Process FMEA
    ("2.2.6", 1): "R",
    ("2.2.6", 2): "R",
    ("2.2.6", 3): "S",
    ("2.2.6", 4): "*",
    ("2.2.6", 5): "R",
    # 2.2.7 Control Plan
    ("2.2.7", 1): "R",
    ("2.2.7", 2): "R",
    ("2.2.7", 3): "S",
    ("2.2.7", 4): "*",
    ("2.2.7", 5): "R",
    # 2.2.8 Measurement System Analysis Studies (Gage R&R)
    ("2.2.8", 1): "R",
    ("2.2.8", 2): "R",
    ("2.2.8", 3): "S",
    ("2.2.8", 4): "*",
    ("2.2.8", 5): "R",
    # 2.2.9 Dimensional Results
    ("2.2.9", 1): "R",
    ("2.2.9", 2): "S",
    ("2.2.9", 3): "S",
    ("2.2.9", 4): "*",
    ("2.2.9", 5): "R",
    # 2.2.10 Material / Performance Test Results
    ("2.2.10", 1): "R",
    ("2.2.10", 2): "S",
    ("2.2.10", 3): "S",
    ("2.2.10", 4): "*",
    ("2.2.10", 5): "R",
    # 2.2.11 Initial Process Studies
    ("2.2.11", 1): "R",
    ("2.2.11", 2): "R",
    ("2.2.11", 3): "S",
    ("2.2.11", 4): "*",
    ("2.2.11", 5): "R",
    # 2.2.12 Qualified Laboratory Documentation
    ("2.2.12", 1): "R",
    ("2.2.12", 2): "S",
    ("2.2.12", 3): "S",
    ("2.2.12", 4): "*",
    ("2.2.12", 5): "R",
    # 2.2.13 Appearance Approval Report (AAR)
    ("2.2.13", 1): "S",
    ("2.2.13", 2): "S",
    ("2.2.13", 3): "S",
    ("2.2.13", 4): "*",
    ("2.2.13", 5): "R",
    # 2.2.14 Sample Production Parts
    ("2.2.14", 1): "R",
    ("2.2.14", 2): "S",
    ("2.2.14", 3): "S",
    ("2.2.14", 4): "*",
    ("2.2.14", 5): "R",
    # 2.2.15 Master Sample
    ("2.2.15", 1): "R",
    ("2.2.15", 2): "R",
    ("2.2.15", 3): "R",
    ("2.2.15", 4): "*",
    ("2.2.15", 5): "R",
    # 2.2.16 Checking Aids
    ("2.2.16", 1): "R",
    ("2.2.16", 2): "R",
    ("2.2.16", 3): "R",
    ("2.2.16", 4): "*",
    ("2.2.16", 5): "R",
    # 2.2.17 Customer-Specific Requirements
    ("2.2.17", 1): "R",
    ("2.2.17", 2): "R",
    ("2.2.17", 3): "R",
    ("2.2.17", 4): "*",
    ("2.2.17", 5): "R",
    # 2.2.18 Part Submission Warrant (PSW)
    ("2.2.18", 1): "S",
    ("2.2.18", 2): "S",
    ("2.2.18", 3): "S",
    ("2.2.18", 4): "S",
    ("2.2.18", 5): "R",
})


def lookup_requirement(element_id: str, level: int) -> RequirementCode:
    """Look up the AIAG Table 4.1/4.2 retention/submission requirement code.

    Args:
        element_id: Canonical AIAG element requirement ID ('2.2.1' .. '2.2.18').
        level: Submission Level (1, 2, 3, 4, 5).

    Returns:
        RequirementCode: 'S' (Submit & Retain), 'R' (Retain only), '*' (Retain & Submit upon request),
        or 'CUSTOMER_DEFINED' (Level 4 customer-defined).

    Raises:
        ValueError: If element_id is not in PPAP_ELEMENT_IDS or level is not in SUBMISSION_LEVELS.
    """
    if level not in SUBMISSION_LEVELS:
        raise ValueError(f"Invalid submission level {level!r}. Must be one of {SUBMISSION_LEVELS}.")
    if element_id not in PPAP_ELEMENT_IDS:
        raise ValueError(f"Invalid element_id {element_id!r}. Must be one of {PPAP_ELEMENT_IDS}.")
    return TABLE_4_1_MATRIX[(element_id, level)]  # type: ignore[index]


def requirement_legend(code: RequirementCode) -> str:
    """Return the verbatim AIAG PPAP 4th Edition legend description for a requirement code.

    Args:
        code: RequirementCode ('S', 'R', '*', 'CUSTOMER_DEFINED').

    Returns:
        Verbatim standard legend description string.

    Raises:
        ValueError: If code is not a recognized requirement code.
    """
    if code not in TABLE_4_1_LEGEND:
        raise ValueError(f"Invalid requirement code {code!r}. Must be one of {REQUIREMENT_CODES}.")
    return TABLE_4_1_LEGEND[code]


def submission_level_description(level: int) -> str:
    """Return the verbatim AIAG PPAP 4th Edition description for a submission level.

    Args:
        level: Submission Level (1, 2, 3, 4, 5).

    Returns:
        Verbatim level description string from Section 4.

    Raises:
        ValueError: If level is not in SUBMISSION_LEVELS (1..5).
    """
    if level not in SUBMISSION_LEVEL_DESCRIPTIONS:
        raise ValueError(f"Invalid submission level {level!r}. Must be one of {SUBMISSION_LEVELS}.")
    return SUBMISSION_LEVEL_DESCRIPTIONS[level]


def elements_required_at_level(
    level: int, code: RequirementCode = "S"
) -> tuple[str, ...]:
    """Return elements required with a specific requirement code at a submission level.

    Args:
        level: Submission Level (1, 2, 3, 4, 5).
        code: RequirementCode filter (default 'S' for submitted elements).

    Returns:
        Tuple of element_id strings matching the code at that level.

    Raises:
        ValueError: If level is invalid or filter code is invalid.
    """
    if level not in SUBMISSION_LEVELS:
        raise ValueError(f"Invalid submission level {level!r}. Must be one of {SUBMISSION_LEVELS}.")
    if code not in REQUIREMENT_CODES:
        raise ValueError(f"Invalid requirement code filter {code!r}. Must be one of {REQUIREMENT_CODES}.")

    return tuple(
        element_id
        for element_id in PPAP_ELEMENT_IDS
        if TABLE_4_1_MATRIX[(element_id, level)] == code
    )

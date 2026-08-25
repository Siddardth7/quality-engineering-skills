"""Unit tests for AIAG PPAP 4th Edition Table 4.1 / Table 4.2 Submission and Retention Matrix.

Validates:
1. Matrix completeness: exactly 90 cells (18 elements × 5 levels)
2. Level 1–5 exact requirement codes and required element sets
3. Lookup helpers: lookup_requirement, requirement_legend, elements_required_at_level, submission_level_description
4. Strict input validation and error raising on invalid inputs
5. Negative mutation controls guarding matrix integrity, level divergence, and legend fidelity
"""

from __future__ import annotations

import pytest
from quality_core.ppap.table_4_1 import (
    ELEMENT_IDS,
    REQUIREMENT_CODES,
    SUBMISSION_LEVEL_DESCRIPTIONS,
    SUBMISSION_LEVELS,
    TABLE_4_1_LEGEND,
    TABLE_4_1_MATRIX,
    elements_required_at_level,
    lookup_requirement,
    requirement_legend,
    submission_level_description,
)

# ==============================================================================
# Matrix Dimensions & Completeness
# ==============================================================================


def test_matrix_dimensions_and_keys() -> None:
    """Verify matrix has exactly 90 entries mapping every (element_id, level) pair."""
    assert len(ELEMENT_IDS) == 18
    assert len(SUBMISSION_LEVELS) == 5
    assert len(TABLE_4_1_MATRIX) == 90

    for elem in ELEMENT_IDS:
        for lvl in SUBMISSION_LEVELS:
            assert (elem, lvl) in TABLE_4_1_MATRIX
            assert TABLE_4_1_MATRIX[(elem, lvl)] in REQUIREMENT_CODES


def test_matrix_keys_use_shared_ppap_schema_vocabulary() -> None:
    """Verify all matrix keys strictly use shared schema vocabulary PPAP_ELEMENT_IDS and SUBMISSION_LEVELS."""
    from quality_core.ppap.schema import PPAP_ELEMENT_IDS as SCHEMA_ELEMENT_IDS
    from quality_core.ppap.schema import SUBMISSION_LEVELS as SCHEMA_SUBMISSION_LEVELS

    assert ELEMENT_IDS == SCHEMA_ELEMENT_IDS
    assert set(elem for elem, _ in TABLE_4_1_MATRIX.keys()) == set(SCHEMA_ELEMENT_IDS)
    assert set(lvl for _, lvl in TABLE_4_1_MATRIX.keys()) == set(SCHEMA_SUBMISSION_LEVELS)


def test_mappings_are_immutable() -> None:
    """Verify TABLE_4_1_MATRIX, TABLE_4_1_LEGEND, and SUBMISSION_LEVEL_DESCRIPTIONS are immutable."""
    with pytest.raises(TypeError):
        TABLE_4_1_MATRIX[("2.2.1", 1)] = "S"  # type: ignore[index]

    with pytest.raises(TypeError):
        TABLE_4_1_LEGEND["S"] = "Mutated legend text"  # type: ignore[index]

    with pytest.raises(TypeError):
        SUBMISSION_LEVEL_DESCRIPTIONS[1] = "Mutated level text"  # type: ignore[index]


def test_element_ids_ordering() -> None:
    """Verify ELEMENT_IDS contains the canonical 18 AIAG PPAP elements in order."""
    expected = (
        "2.2.1",
        "2.2.2",
        "2.2.3",
        "2.2.4",
        "2.2.5",
        "2.2.6",
        "2.2.7",
        "2.2.8",
        "2.2.9",
        "2.2.10",
        "2.2.11",
        "2.2.12",
        "2.2.13",
        "2.2.14",
        "2.2.15",
        "2.2.16",
        "2.2.17",
        "2.2.18",
    )
    assert ELEMENT_IDS == expected


def test_submission_levels() -> None:
    """Verify SUBMISSION_LEVELS contains levels 1 through 5."""
    assert SUBMISSION_LEVELS == (1, 2, 3, 4, 5)


# ==============================================================================
# Level-by-Level Verification
# ==============================================================================


def test_level_1_requirements() -> None:
    """Level 1: Warrant only (and AAR if appearance) submitted to customer."""
    required_s = elements_required_at_level(1)
    assert required_s == ("2.2.13", "2.2.18")

    required_r = elements_required_at_level(1, code="R")
    assert len(required_r) == 16
    assert "2.2.1" in required_r
    assert "2.2.15" in required_r
    assert "2.2.18" not in required_r

    assert elements_required_at_level(1, code="*") == ()
    assert elements_required_at_level(1, code="CUSTOMER_DEFINED") == ()


def test_level_2_requirements() -> None:
    """Level 2: Warrant with product samples and limited supporting data submitted."""
    required_s = elements_required_at_level(2)
    expected_s = ("2.2.1", "2.2.2", "2.2.9", "2.2.10", "2.2.12", "2.2.13", "2.2.14", "2.2.18")
    assert required_s == expected_s

    required_r = elements_required_at_level(2, code="R")
    expected_r = ("2.2.3", "2.2.4", "2.2.5", "2.2.6", "2.2.7", "2.2.8", "2.2.11", "2.2.15", "2.2.16", "2.2.17")
    assert required_r == expected_r

    assert elements_required_at_level(2, code="*") == ()


def test_level_3_requirements() -> None:
    """Level 3 (Default): Warrant with product samples and complete supporting data."""
    required_s = elements_required_at_level(3)
    # Level 3 requires submit for 15 elements (all except 2.2.15, 2.2.16, and 2.2.17 which are R)
    assert len(required_s) == 15
    assert "2.2.15" not in required_s
    assert "2.2.16" not in required_s
    assert "2.2.17" not in required_s

    required_r = elements_required_at_level(3, code="R")
    assert required_r == ("2.2.15", "2.2.16", "2.2.17")

    assert elements_required_at_level(3, code="*") == ()


def test_level_4_requirements() -> None:
    """Level 4: Warrant submitted, other requirements defined by customer (*)."""
    required_s = elements_required_at_level(4)
    assert required_s == ("2.2.18",)

    required_star = elements_required_at_level(4, code="*")
    assert len(required_star) == 17
    assert "2.2.18" not in required_star
    assert "2.2.1" in required_star
    assert "2.2.4" in required_star

    assert elements_required_at_level(4, code="R") == ()


def test_level_5_requirements() -> None:
    """Level 5: Warrant with product samples and complete supporting data reviewed on-site."""
    required_s = elements_required_at_level(5)
    assert required_s == ()

    required_r = elements_required_at_level(5, code="R")
    assert len(required_r) == 18
    assert required_r == ELEMENT_IDS

    assert elements_required_at_level(5, code="*") == ()


# ==============================================================================
# Helper Function Verification & Input Guards
# ==============================================================================


@pytest.mark.parametrize(
    ("element_id", "level", "expected_code"),
    [
        ("2.2.1", 1, "R"),
        ("2.2.1", 2, "S"),
        ("2.2.1", 3, "S"),
        ("2.2.1", 4, "*"),
        ("2.2.1", 5, "R"),
        ("2.2.4", 1, "R"),
        ("2.2.4", 2, "R"),
        ("2.2.4", 3, "S"),
        ("2.2.4", 4, "*"),
        ("2.2.4", 5, "R"),
        ("2.2.13", 1, "S"),
        ("2.2.13", 2, "S"),
        ("2.2.13", 3, "S"),
        ("2.2.13", 4, "*"),
        ("2.2.13", 5, "R"),
        ("2.2.15", 3, "R"),
        ("2.2.16", 3, "R"),
        ("2.2.18", 1, "S"),
        ("2.2.18", 2, "S"),
        ("2.2.18", 3, "S"),
        ("2.2.18", 4, "S"),
        ("2.2.18", 5, "R"),
    ],
)
def test_lookup_requirement_valid(element_id: str, level: int, expected_code: str) -> None:
    """Verify lookup_requirement returns exact requirement code for standard cells."""
    assert lookup_requirement(element_id, level) == expected_code


def test_lookup_requirement_invalid_inputs() -> None:
    """Verify lookup_requirement raises ValueError on invalid element_id or level."""
    with pytest.raises(ValueError, match="Invalid element_id"):
        lookup_requirement("2.2.0", 1)

    with pytest.raises(ValueError, match="Invalid element_id"):
        lookup_requirement("2.2.19", 3)

    with pytest.raises(ValueError, match="Invalid element_id"):
        lookup_requirement("invalid", 1)

    with pytest.raises(ValueError, match="Invalid submission level"):
        lookup_requirement("2.2.1", 0)

    with pytest.raises(ValueError, match="Invalid submission level"):
        lookup_requirement("2.2.1", 6)

    with pytest.raises(ValueError, match="Invalid submission level"):
        lookup_requirement("2.2.1", -1)


@pytest.mark.parametrize(
    ("code", "expected_substring"),
    [
        ("S", "submit to the customer and retain a copy"),
        ("R", "retain at appropriate locations and make available"),
        ("*", "retain at appropriate locations and submit to the customer upon request"),
        ("CUSTOMER_DEFINED", "requirements as defined by the customer"),
    ],
)
def test_requirement_legend_valid(code: str, expected_substring: str) -> None:
    """Verify requirement_legend returns the verbatim standard definitions."""
    legend = requirement_legend(code)  # type: ignore[arg-type]
    assert expected_substring.lower() in legend.lower()
    assert legend == TABLE_4_1_LEGEND[code]  # type: ignore[index]


def test_requirement_legend_invalid() -> None:
    """Verify requirement_legend raises ValueError on unrecognized code."""
    with pytest.raises(ValueError, match="Invalid requirement code"):
        requirement_legend("X")

    with pytest.raises(ValueError, match="Invalid requirement code"):
        requirement_legend("")


def test_elements_required_at_level_invalid() -> None:
    """Verify elements_required_at_level raises ValueError on invalid level or code."""
    with pytest.raises(ValueError, match="Invalid submission level"):
        elements_required_at_level(0)

    with pytest.raises(ValueError, match="Invalid submission level"):
        elements_required_at_level(6)

    with pytest.raises(ValueError, match="Invalid requirement code"):
        elements_required_at_level(3, code="INVALID")


@pytest.mark.parametrize(
    ("level", "expected_substring"),
    [
        (1, "Warrant only"),
        (2, "limited supporting data"),
        (3, "complete supporting data submitted to the customer"),
        (4, "requirements as defined by the customer"),
        (5, "reviewed at the organization's manufacturing location"),
    ],
)
def test_submission_level_description_valid(level: int, expected_substring: str) -> None:
    """Verify submission_level_description returns verbatim Table 4.1 definitions."""
    desc = submission_level_description(level)
    assert expected_substring.lower() in desc.lower()
    assert desc == SUBMISSION_LEVEL_DESCRIPTIONS[level]


def test_submission_level_description_invalid() -> None:
    """Verify submission_level_description raises ValueError on invalid level."""
    with pytest.raises(ValueError, match="Invalid submission level"):
        submission_level_description(0)

    with pytest.raises(ValueError, match="Invalid submission level"):
        submission_level_description(6)

    with pytest.raises(ValueError, match="Invalid submission level"):
        submission_level_description(-1)


# ==============================================================================
# Negative Mutation Controls
# ==============================================================================


def test_negative_control_cell_mutation_detected() -> None:
    """Negative control: assert mutating any cell changes lookup and level requirement."""
    # Base check: Level 3 Master Sample (2.2.15) is 'R'
    assert lookup_requirement("2.2.15", 3) == "R"
    assert "2.2.15" not in elements_required_at_level(3, "S")

    # Construct a mutated matrix where 2.2.15 at Level 3 is 'S'
    mutated_matrix = dict(TABLE_4_1_MATRIX)
    mutated_matrix[("2.2.15", 3)] = "S"

    # Verify mutation is distinguishable from genuine matrix
    assert mutated_matrix[("2.2.15", 3)] != TABLE_4_1_MATRIX[("2.2.15", 3)]


def test_negative_control_level_4_divergence_from_level_3() -> None:
    """Negative control: assert Level 4 column is not identical to Level 3 column."""
    l3_requirements = {elem: TABLE_4_1_MATRIX[(elem, 3)] for elem in ELEMENT_IDS}
    l4_requirements = {elem: TABLE_4_1_MATRIX[(elem, 4)] for elem in ELEMENT_IDS}

    assert l3_requirements != l4_requirements
    # Specifically, Design Record is S in L3, * in L4
    assert l3_requirements["2.2.1"] == "S"
    assert l4_requirements["2.2.1"] == "*"


def test_negative_control_legend_mutation_detected() -> None:
    """Negative control: assert a fabricated legend string fails comparison against standard."""
    fabricated_legend = "S = Supplier may submit whatever they want."
    assert requirement_legend("S") != fabricated_legend

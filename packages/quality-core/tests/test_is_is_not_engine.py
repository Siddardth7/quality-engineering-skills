"""
Unit tests for deterministic Kepner-Tregoe Is/Is-Not scoping and hypothesis synthesis engine (quality_core.rca.is_is_not).

Standards References:
- Charles H. Kepner & Benjamin B. Tregoe, The New Rational Manager (1997), Chapters 2 & 3.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section 4.
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Section D2.

Tests:
1. CandidateCause and IsIsNotScopingResult dataclass serialization and field validations.
2. Positive controls:
   - Full 4-dimension KT matrix (WHAT, WHERE, WHEN, EXTENT) -> ACCEPT verdict, 4 paired candidate causes.
   - Reference Sentinel-8D pneumatic cylinder benchmark dataset.
   - Input polymorphism: IsIsNotMatrix, pd.DataFrame, list[dict], list[IsIsNotRow], dict with rows, single-row dict.
   - Candidate cause hypothesis synthesis across all 4 distinction/change permutations.
   - Custom problem statement propagation.
3. Negative controls & anti-pattern detection:
   - Empty dataset / matrix ([], DataFrame(), {"rows": []}) -> REJECT verdict, valid=False.
   - Partial dimensions (< 4 dimensions) -> WARNING verdict, missing_dimensions list, boundary guidance.
   - Missing distinctions or changes -> WARNING verdict with specific KT Chapter 2 guidance.
   - Invalid dimension strings (e.g. "WHO", "WHY") -> pydantic.ValidationError.
   - Duplicate dimension entries -> pydantic.ValidationError.
4. Boundary & error conditions:
   - Invalid problem_statement types (bool, int, float, list) -> TypeError.
   - Blank / whitespace problem_statement -> ValueError.
   - Unsupported data types (bool, int, float, None, str) -> TypeError.
   - Invalid rows payload in dict -> TypeError.
   - Invalid item types in list -> TypeError.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pydantic
import pytest
from quality_core.canvas.rca import SAMPLE_IS_IS_NOT_ROWS
from quality_core.rca.is_is_not import (
    CandidateCause,
    IsIsNotScopingResult,
    scope_is_is_not,
)
from quality_core.rca.schema import (
    KT_DIMENSIONS,
    IsIsNotMatrix,
    IsIsNotRow,
)

# ---------------------------------------------------------------------------
# Test Fixtures & Datasets
# ---------------------------------------------------------------------------

_VALID_4DIM_ROWS = [
    {
        "dimension": "WHAT",
        "is_data": "Filter #1 leaking oil at housing gasket",
        "is_not_data": "Filters #2 through #5 leaking",
        "distinctions": "Square-cornered gasket design on #1 filter",
        "changes": "Gasket supplied by new vendor Acme Corp",
    },
    {
        "dimension": "WHERE",
        "is_data": "North compressor room main lubrication header",
        "is_not_data": "South compressor room or auxiliary return lines",
        "distinctions": "North room operates at elevated ambient temperature (42 C)",
        "changes": "Ventilation exhaust fan serviced last week",
    },
    {
        "dimension": "WHEN",
        "is_data": "First observed Monday 08:00 shift startup",
        "is_not_data": "Prior Friday operating run or weekend idle",
        "distinctions": "System cold-start pressurized cycle after 48-hour shutdown",
        "changes": "Lubrication pump startup sequence modified",
    },
    {
        "dimension": "EXTENT",
        "is_data": "Continuous seepage at 250 mL/hour, 1 of 5 filter units",
        "is_not_data": "Catastrophic blowout or all 5 units leaking",
        "distinctions": "Seepage localized to lower seal flange sector",
        "changes": "Flange bolt torque specification updated to 45 Nm",
    },
]


# ---------------------------------------------------------------------------
# 1. Dataclass Serialization Tests
# ---------------------------------------------------------------------------


def test_candidate_cause_dataclass_and_to_dict() -> None:
    """CandidateCause constructs correctly and returns dictionary representation."""
    cause = CandidateCause(
        dimension="WHAT",
        distinction="Square-cornered gasket",
        change="New vendor Acme Corp",
        hypothesis="Square gasket from new vendor causes oil leak.",
        is_paired=True,
    )
    assert cause.dimension == "WHAT"
    assert cause.distinction == "Square-cornered gasket"
    assert cause.change == "New vendor Acme Corp"
    assert cause.hypothesis == "Square gasket from new vendor causes oil leak."
    assert cause.is_paired is True

    d = cause.to_dict()
    assert d == {
        "dimension": "WHAT",
        "distinction": "Square-cornered gasket",
        "change": "New vendor Acme Corp",
        "hypothesis": "Square gasket from new vendor causes oil leak.",
        "is_paired": True,
    }


def test_candidate_cause_default_is_paired() -> None:
    """CandidateCause defaults is_paired to False when omitted."""
    cause = CandidateCause(
        dimension="WHERE",
        distinction="Elevated temperature",
        change=None,
        hypothesis="Investigate what changed around elevated temperature.",
    )
    assert cause.is_paired is False
    assert cause.change is None
    d = cause.to_dict()
    assert d["is_paired"] is False
    assert d["change"] is None


def test_is_is_not_scoping_result_dataclass_and_to_dict() -> None:
    """IsIsNotScopingResult constructs correctly and returns serializable dict with isolated copies."""
    result = IsIsNotScopingResult(
        basis="Kepner & Tregoe (1997) / AIAG CQI-20 / Ford Global 8D",
        valid=True,
        verdict="ACCEPT",
        problem_statement="Filter #1 oil leak",
        total_rows=4,
        dimension_coverage={"WHAT": True, "WHERE": True, "WHEN": True, "EXTENT": True},
        complete_dimensions=["WHAT", "WHERE", "WHEN", "EXTENT"],
        missing_dimensions=[],
        candidate_causes=[
            {
                "dimension": "WHAT",
                "distinction": "Square gasket",
                "change": "New vendor",
                "hypothesis": "New vendor gasket caused leak.",
                "is_paired": True,
            }
        ],
        warnings=[],
        recommendations=["Proceed to test hypotheses against all facts."],
    )
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_rows == 4
    assert result.complete_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert result.missing_dimensions == []

    d = result.to_dict()
    assert d["basis"] == "Kepner & Tregoe (1997) / AIAG CQI-20 / Ford Global 8D"
    assert d["valid"] is True
    assert d["verdict"] == "ACCEPT"
    assert d["problem_statement"] == "Filter #1 oil leak"
    assert d["total_rows"] == 4
    assert d["dimension_coverage"] == {"WHAT": True, "WHERE": True, "WHEN": True, "EXTENT": True}
    assert d["complete_dimensions"] == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert d["missing_dimensions"] == []
    assert len(d["candidate_causes"]) == 1
    assert len(d["recommendations"]) == 1

    # Verify returned collections are independent copies
    d["complete_dimensions"].append("EXTRA")
    assert "EXTRA" not in result.complete_dimensions


# ---------------------------------------------------------------------------
# 2. Positive Controls: Full Matrix & Hypothesis Synthesis
# ---------------------------------------------------------------------------


def test_scope_is_is_not_full_4dim_accept() -> None:
    """Full 4-dimension KT matrix with distinctions and changes yields ACCEPT verdict and 4 paired causes."""
    result = scope_is_is_not(
        data=_VALID_4DIM_ROWS,
        problem_statement="Filter #1 oil leak during startup",
    )
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_rows == 4
    assert result.complete_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert result.missing_dimensions == []
    assert result.dimension_coverage == {d: True for d in KT_DIMENSIONS}
    assert len(result.warnings) == 0
    assert len(result.candidate_causes) == 4
    assert all(c["is_paired"] is True for c in result.candidate_causes)
    assert any("Problem boundary is fully scoped" in r for r in result.recommendations)

    # Check hypothesis text format
    what_cause = next(c for c in result.candidate_causes if c["dimension"] == "WHAT")
    assert "Square-cornered gasket design on #1 filter" in what_cause["hypothesis"]
    assert "Gasket supplied by new vendor Acme Corp" in what_cause["hypothesis"]
    assert "Filter #1 oil leak during startup" in what_cause["hypothesis"]


def test_scope_is_is_not_sample_sentinel_8d_benchmark() -> None:
    """Sentinel-8D benchmark dataset yields ACCEPT verdict, 4 paired causes, and blank weight hypothesis."""
    result = scope_is_is_not(
        data=SAMPLE_IS_IS_NOT_ROWS,
        problem_statement="Pneumatic cylinder assembly rework (stroke binding & seal leakage)",
    )
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_rows == 4
    assert result.complete_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert result.missing_dimensions == []
    assert len(result.candidate_causes) == 4
    assert all(c["is_paired"] is True for c in result.candidate_causes)

    extent_cause = next(c for c in result.candidate_causes if c["dimension"] == "EXTENT")
    assert "1.99x" in extent_cause["hypothesis"]
    assert "Sawing cut blank weight variation" in extent_cause["hypothesis"]


# ---------------------------------------------------------------------------
# 3. Input Polymorphism Tests
# ---------------------------------------------------------------------------


def test_scope_is_is_not_input_is_is_not_matrix() -> None:
    """Ingest IsIsNotMatrix object directly."""
    matrix = IsIsNotMatrix(
        problem_statement="Matrix problem statement",
        rows=[
            IsIsNotRow(
                dimension="WHAT",
                is_data="Defect A",
                is_not_data="Defect B",
                distinctions="Dist A",
                changes="Change A",
            ),
            IsIsNotRow(
                dimension="WHERE",
                is_data="Line 1",
                is_not_data="Line 2",
                distinctions="Dist W",
                changes="Change W",
            ),
            IsIsNotRow(
                dimension="WHEN",
                is_data="Shift 1",
                is_not_data="Shift 2",
                distinctions="Dist T",
                changes="Change T",
            ),
            IsIsNotRow(
                dimension="EXTENT",
                is_data="10 ppm",
                is_not_data="100 ppm",
                distinctions="Dist E",
                changes="Change E",
            ),
        ],
    )
    # Use matrix's internal problem statement
    res1 = scope_is_is_not(data=matrix)
    assert res1.valid is True
    assert res1.verdict == "ACCEPT"
    assert res1.problem_statement == "Matrix problem statement"

    # Override problem statement via argument
    res2 = scope_is_is_not(data=matrix, problem_statement="Overridden statement")
    assert res2.problem_statement == "Overridden statement"


def test_scope_is_is_not_input_dataframe() -> None:
    """Ingest pandas DataFrame with standard column headers."""
    df = pd.DataFrame(_VALID_4DIM_ROWS)
    result = scope_is_is_not(data=df, problem_statement="DataFrame test")
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_rows == 4
    assert result.complete_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]


def test_scope_is_is_not_input_list_of_is_is_not_rows() -> None:
    """Ingest list of IsIsNotRow model instances."""
    row_objs = [
        IsIsNotRow(
            dimension=r["dimension"],
            is_data=r["is_data"],
            is_not_data=r["is_not_data"],
            distinctions=r.get("distinctions"),
            changes=r.get("changes"),
        )
        for r in _VALID_4DIM_ROWS
    ]
    result = scope_is_is_not(data=row_objs, problem_statement="List of IsIsNotRow test")
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_rows == 4


def test_scope_is_is_not_input_dict_with_rows() -> None:
    """Ingest dict containing 'problem_statement' and 'rows' list with 1 row."""
    payload = {
        "problem_statement": "Dict payload problem statement",
        "rows": [_VALID_4DIM_ROWS[0]],
    }
    result = scope_is_is_not(data=payload)
    assert result.valid is True
    assert result.verdict == "WARNING"
    assert result.problem_statement == "Dict payload problem statement"
    assert result.total_rows == 1
    assert result.complete_dimensions == ["WHAT"]

    # Override problem statement
    res_override = scope_is_is_not(data=payload, problem_statement="Custom Statement")
    assert res_override.problem_statement == "Custom Statement"


def test_scope_is_is_not_input_dict_without_rows_key_raises_validation_error() -> None:
    """Ingesting a dict without 'rows' key (missing rows field) raises pydantic.ValidationError."""
    single = {
        "dimension": "WHAT",
        "is_data": "Surface scratch",
        "is_not_data": "Internal crack",
        "distinctions": "Top face only",
        "changes": "New handling tray",
    }
    with pytest.raises(pydantic.ValidationError):
        scope_is_is_not(data=single, problem_statement="Single row test")


def test_scope_is_is_not_default_problem_statement() -> None:
    """When problem_statement is None and not in data, defaults to 'Problem Statement'."""
    result = scope_is_is_not(data=_VALID_4DIM_ROWS)
    assert result.problem_statement == "Problem Statement"


# ---------------------------------------------------------------------------
# 4. Hypothesis Synthesis Permutations
# ---------------------------------------------------------------------------


def test_hypothesis_synthesis_distinction_without_change() -> None:
    """Dimension with distinction but no change yields is_paired=False and KT Chapter 2 investigation warning."""
    rows = [
        {
            "dimension": "WHAT",
            "is_data": "Leak on unit 1",
            "is_not_data": "Units 2-5",
            "distinctions": "Square-cornered gasket",
            "changes": None,
        },
        {
            "dimension": "WHERE",
            "is_data": "North room",
            "is_not_data": "South room",
            "distinctions": "High ambient temp",
            "changes": "Exhaust fan serviced",
        },
        {
            "dimension": "WHEN",
            "is_data": "Monday 8am",
            "is_not_data": "Friday",
            "distinctions": "Cold start",
            "changes": "Sequence changed",
        },
        {
            "dimension": "EXTENT",
            "is_data": "1 of 5",
            "is_not_data": "All 5",
            "distinctions": "Lower flange",
            "changes": "Torque updated",
        },
    ]
    result = scope_is_is_not(data=rows)
    assert result.valid is True
    assert result.verdict == "WARNING"
    what_cause = next(c for c in result.candidate_causes if c["dimension"] == "WHAT")
    assert what_cause["is_paired"] is False
    assert what_cause["change"] is None
    assert "investigate what changed in, on, around, or about this distinction" in what_cause["hypothesis"]
    assert any("Dimension 'WHAT' has distinctions recorded ('Square-cornered gasket') but is missing associated changes" in w for w in result.warnings)
    assert any("KT Chapter 2" in r for r in result.recommendations)


def test_hypothesis_synthesis_change_without_distinction() -> None:
    """Dimension with change but no distinction yields is_paired=False and distinction investigation warning."""
    rows = [
        {
            "dimension": "WHAT",
            "is_data": "Leak on unit 1",
            "is_not_data": "Units 2-5",
            "distinctions": None,
            "changes": "New vendor gasket",
        },
        {
            "dimension": "WHERE",
            "is_data": "North room",
            "is_not_data": "South room",
            "distinctions": "High ambient temp",
            "changes": "Exhaust fan serviced",
        },
        {
            "dimension": "WHEN",
            "is_data": "Monday 8am",
            "is_not_data": "Friday",
            "distinctions": "Cold start",
            "changes": "Sequence changed",
        },
        {
            "dimension": "EXTENT",
            "is_data": "1 of 5",
            "is_not_data": "All 5",
            "distinctions": "Lower flange",
            "changes": "Torque updated",
        },
    ]
    result = scope_is_is_not(data=rows)
    assert result.valid is True
    assert result.verdict == "WARNING"
    what_cause = next(c for c in result.candidate_causes if c["dimension"] == "WHAT")
    assert what_cause["is_paired"] is False
    assert what_cause["distinction"] == ""
    assert what_cause["change"] == "New vendor gasket"
    assert "investigate what distinguishes the IS data from the IS NOT data" in what_cause["hypothesis"]
    assert any("Dimension 'WHAT' has changes recorded ('New vendor gasket') but is missing distinctions" in w for w in result.warnings)
    assert any("Determine what is unique or distinctive about the 'WHAT' IS data" in r for r in result.recommendations)


def test_hypothesis_synthesis_missing_both_distinction_and_change() -> None:
    """Dimension with neither distinction nor change adds no candidate cause and warns about missing both."""
    rows = [
        {
            "dimension": "WHAT",
            "is_data": "Leak on unit 1",
            "is_not_data": "Units 2-5",
            "distinctions": None,
            "changes": None,
        },
        {
            "dimension": "WHERE",
            "is_data": "North room",
            "is_not_data": "South room",
            "distinctions": "High ambient temp",
            "changes": "Exhaust fan serviced",
        },
        {
            "dimension": "WHEN",
            "is_data": "Monday 8am",
            "is_not_data": "Friday",
            "distinctions": "Cold start",
            "changes": "Sequence changed",
        },
        {
            "dimension": "EXTENT",
            "is_data": "1 of 5",
            "is_not_data": "All 5",
            "distinctions": "Lower flange",
            "changes": "Torque updated",
        },
    ]
    result = scope_is_is_not(data=rows)
    assert result.valid is True
    assert result.verdict == "WARNING"
    # WHAT row did not produce a candidate cause
    assert len(result.candidate_causes) == 3
    assert not any(c["dimension"] == "WHAT" for c in result.candidate_causes)
    assert any("Dimension 'WHAT' has IS and IS NOT data but is missing both distinctions and changes." in w for w in result.warnings)
    assert any("Identify what is distinctive about the IS data compared to the IS NOT data for 'WHAT'" in r for r in result.recommendations)


# ---------------------------------------------------------------------------
# 5. Negative Controls & Anti-Pattern Detection
# ---------------------------------------------------------------------------


def test_negative_empty_list_rejects() -> None:
    """Empty list returns valid=False, verdict=REJECT, and 0 candidate causes."""
    result = scope_is_is_not(data=[], problem_statement="Empty problem")
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert result.total_rows == 0
    assert result.complete_dimensions == []
    assert result.missing_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert result.candidate_causes == []
    assert result.warnings == ["Is/Is-Not matrix contains no scoping rows."]
    assert any("Populate problem boundary observations" in r for r in result.recommendations)


def test_negative_empty_dataframe_rejects() -> None:
    """Empty DataFrame returns valid=False, verdict=REJECT."""
    df_empty = pd.DataFrame()
    result = scope_is_is_not(data=df_empty)
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert result.total_rows == 0
    assert result.missing_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]


def test_negative_empty_rows_in_dict_rejects() -> None:
    """Dict with empty rows list returns valid=False, verdict=REJECT."""
    payload = {"problem_statement": "Valid statement", "rows": []}
    result = scope_is_is_not(data=payload)
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert result.total_rows == 0
    assert result.problem_statement == "Valid statement"


def test_negative_partial_dimensions_warning() -> None:
    """Partial dimensions (e.g. only WHAT and WHERE) returns WARNING verdict and lists missing dimensions."""
    rows = [
        {
            "dimension": "WHAT",
            "is_data": "Leak on unit 1",
            "is_not_data": "Units 2-5",
            "distinctions": "Square gasket",
            "changes": "New vendor",
        },
        {
            "dimension": "WHERE",
            "is_data": "North room",
            "is_not_data": "South room",
            "distinctions": "High temp",
            "changes": "Exhaust fan",
        },
    ]
    result = scope_is_is_not(data=rows)
    assert result.valid is True
    assert result.verdict == "WARNING"
    assert result.total_rows == 2
    assert result.complete_dimensions == ["WHAT", "WHERE"]
    assert result.missing_dimensions == ["WHEN", "EXTENT"]
    assert result.dimension_coverage == {
        "WHAT": True,
        "WHERE": True,
        "WHEN": False,
        "EXTENT": False,
    }
    assert any("missing dimensions WHEN, EXTENT" in w for w in result.warnings)
    assert any("Scope the unexamined dimensions (WHEN, EXTENT)" in r for r in result.recommendations)


def test_negative_invalid_dimension_raises_validation_error() -> None:
    """Invalid dimension string (e.g. 'WHO') raises pydantic.ValidationError."""
    bad_rows = [
        {
            "dimension": "WHO",
            "is_data": "Operator A",
            "is_not_data": "Operator B",
        }
    ]
    with pytest.raises(pydantic.ValidationError):
        scope_is_is_not(data=bad_rows)


def test_negative_duplicate_dimensions_raise_validation_error() -> None:
    """Duplicate dimensions in matrix raise pydantic.ValidationError."""
    dup_rows = [
        {
            "dimension": "WHAT",
            "is_data": "Defect 1",
            "is_not_data": "Defect 2",
        },
        {
            "dimension": "WHAT",
            "is_data": "Defect 3",
            "is_not_data": "Defect 4",
        },
    ]
    with pytest.raises(pydantic.ValidationError):
        scope_is_is_not(data=dup_rows)


# ---------------------------------------------------------------------------
# 6. Boundary & Error Conditions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_ps",
    [
        True,
        False,
        123,
        45.6,
        ["problem"],
        {"text": "problem"},
    ],
)
def test_scope_is_is_not_invalid_problem_statement_type(bad_ps: Any) -> None:
    """Non-string or bool problem_statement raises TypeError."""
    with pytest.raises(TypeError, match="problem_statement must be a string or None"):
        scope_is_is_not(data=_VALID_4DIM_ROWS, problem_statement=bad_ps)


@pytest.mark.parametrize(
    "blank_ps",
    [
        "",
        "   ",
        "\t\n  ",
    ],
)
def test_scope_is_is_not_blank_problem_statement_raises_value_error(blank_ps: str) -> None:
    """Blank or whitespace-only problem_statement raises ValueError."""
    with pytest.raises(ValueError, match="problem_statement must not be blank or whitespace-only"):
        scope_is_is_not(data=_VALID_4DIM_ROWS, problem_statement=blank_ps)


@pytest.mark.parametrize(
    "bad_dict_ps",
    [
        {"problem_statement": True, "rows": _VALID_4DIM_ROWS},
        {"problem_statement": 123, "rows": _VALID_4DIM_ROWS},
        {"problem_statement": "", "rows": _VALID_4DIM_ROWS},
        {"problem_statement": "   ", "rows": _VALID_4DIM_ROWS},
    ],
)
def test_scope_is_is_not_invalid_problem_statement_in_dict(bad_dict_ps: dict[str, Any]) -> None:
    """Invalid problem_statement inside dict raises ValueError."""
    with pytest.raises(ValueError, match="problem_statement must not be blank or whitespace-only"):
        scope_is_is_not(data=bad_dict_ps)


@pytest.mark.parametrize(
    "bad_data",
    [
        None,
        True,
        False,
        123,
        45.67,
        "not a matrix",
    ],
)
def test_scope_is_is_not_unsupported_data_type(bad_data: Any) -> None:
    """Unsupported data types raise TypeError."""
    with pytest.raises(TypeError, match="Expected IsIsNotMatrix, DataFrame, list of dicts/rows, or dict"):
        scope_is_is_not(data=bad_data)


def test_scope_is_is_not_invalid_rows_in_dict() -> None:
    """Non-list rows key in dict raises TypeError."""
    with pytest.raises(TypeError, match="Expected list for rows in dict"):
        scope_is_is_not(data={"rows": "not a list"})


def test_scope_is_is_not_invalid_items_in_list() -> None:
    """Non-dict and non-IsIsNotRow items in list raise TypeError."""
    with pytest.raises(TypeError, match="Expected IsIsNotRow or dict in list"):
        scope_is_is_not(data=[123, 456])

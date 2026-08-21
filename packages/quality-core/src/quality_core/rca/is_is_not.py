"""
is_is_not.py
Deterministic Kepner-Tregoe Is/Is-Not problem scoping and hypothesis synthesis engine.

Implements structured 4-dimension problem boundary specification (WHAT, WHERE, WHEN, EXTENT)
and 4 analytical columns (IS, IS NOT, DISTINCTIONS, CHANGES) per Kepner & Tregoe (1997)
Chapters 2 & 3, AIAG CQI-20 Section 4, and Ford Global 8D (D2). Detects unexamined dimensions,
missing distinctions and changes, synthesizes candidate root-cause hypotheses by pairing
distinctions with changes, and provides structured recommendations.

Standards References:
- Charles H. Kepner & Benjamin B. Tregoe, The New Rational Manager (Updated Edition, 1997), Chapters 2 & 3.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section 4 & Figure 24.
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Section D2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from quality_core.rca.schema import (
    KT_DIMENSIONS,
    IsIsNotMatrix,
    validate_is_is_not,
)

__all__ = [
    "CandidateCause",
    "IsIsNotScopingResult",
    "scope_is_is_not",
]

_STANDARDS_BASIS = "Kepner & Tregoe (1997) / AIAG CQI-20 / Ford Global 8D"


@dataclass
class CandidateCause:
    """Hypothesized root cause synthesized from Kepner-Tregoe distinctions and changes."""

    dimension: str
    distinction: str
    change: str | None
    hypothesis: str
    is_paired: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of candidate cause."""
        return {
            "dimension": self.dimension,
            "distinction": self.distinction,
            "change": self.change,
            "hypothesis": self.hypothesis,
            "is_paired": self.is_paired,
        }


@dataclass
class IsIsNotScopingResult:
    """Structured result of Kepner-Tregoe Is/Is-Not matrix scoping and cause synthesis."""

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    problem_statement: str
    total_rows: int
    dimension_coverage: dict[str, bool]
    complete_dimensions: list[str]
    missing_dimensions: list[str]
    candidate_causes: list[dict[str, Any]]
    warnings: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of scoping result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "problem_statement": self.problem_statement,
            "total_rows": self.total_rows,
            "dimension_coverage": dict(self.dimension_coverage),
            "complete_dimensions": list(self.complete_dimensions),
            "missing_dimensions": list(self.missing_dimensions),
            "candidate_causes": list(self.candidate_causes),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
        }


def scope_is_is_not(
    data: Any,
    problem_statement: str | None = None,
) -> IsIsNotScopingResult:
    """Scope, validate, and synthesize root-cause hypotheses from a Kepner-Tregoe Is/Is-Not matrix.

    Evaluates problem boundary completeness across the 4 canonical KT dimensions
    (WHAT, WHERE, WHEN, EXTENT), identifies missing distinctions and changes per
    Kepner & Tregoe (1997) Chapter 2, synthesizes candidate root-cause hypotheses
    by pairing distinctions with changes per Chapter 3, and generates actionable
    engineering recommendations.

    Parameters
    ----------
    data : Any
        Untrusted Is/Is-Not dataset: IsIsNotMatrix, pd.DataFrame, list of dicts/IsIsNotRows, or dict.
    problem_statement : str | None, optional
        Problem statement describing the deviation or defect being scoped. If None,
        inferred from dataset or defaults to 'Problem Statement'.

    Returns
    -------
    IsIsNotScopingResult
        Structured scoping and hypothesis synthesis output containing verdict,
        dimension coverage, candidate causes, warnings, and recommendations.

    Raises
    ------
    TypeError
        If data is not a supported type (e.g. integer, None, float) or problem_statement is not a string.
    ValueError
        If problem_statement is blank or whitespace-only.
    pydantic.ValidationError
        If rows contain invalid dimensions, blank required fields, or duplicate dimensions.
    """
    if isinstance(problem_statement, bool) or (
        problem_statement is not None and not isinstance(problem_statement, str)
    ):
        raise TypeError(
            f"problem_statement must be a string or None, got {type(problem_statement).__name__}"
        )
    if problem_statement is not None and not problem_statement.strip():
        raise ValueError("problem_statement must not be blank or whitespace-only")

    if isinstance(data, bool) or not isinstance(data, (IsIsNotMatrix, pd.DataFrame, list, dict)):
        raise TypeError(
            f"Expected IsIsNotMatrix, DataFrame, list of dicts/rows, or dict, got {type(data).__name__}"
        )

    # Resolve effective problem statement
    effective_problem: str
    if isinstance(data, IsIsNotMatrix):
        effective_problem = (
            problem_statement.strip() if problem_statement is not None else data.problem_statement
        )
    elif isinstance(data, dict) and "problem_statement" in data:
        raw_ps = data["problem_statement"]
        if isinstance(raw_ps, bool) or not isinstance(raw_ps, str) or not raw_ps.strip():
            raise ValueError("problem_statement must not be blank or whitespace-only")
        effective_problem = problem_statement.strip() if problem_statement is not None else raw_ps.strip()
    else:
        effective_problem = problem_statement.strip() if problem_statement is not None else "Problem Statement"

    # Check for empty data structures
    is_empty = False
    if isinstance(data, list) and len(data) == 0:
        is_empty = True
    elif isinstance(data, pd.DataFrame) and len(data) == 0:
        is_empty = True
    elif isinstance(data, dict) and "rows" in data:
        if not isinstance(data["rows"], list):
            raise TypeError(f"Expected list for rows in dict, got {type(data['rows']).__name__}")
        if len(data["rows"]) == 0:
            is_empty = True

    if is_empty:
        return IsIsNotScopingResult(
            basis=_STANDARDS_BASIS,
            valid=False,
            verdict="REJECT",
            problem_statement=effective_problem,
            total_rows=0,
            dimension_coverage={d: False for d in KT_DIMENSIONS},
            complete_dimensions=[],
            missing_dimensions=list(KT_DIMENSIONS),
            candidate_causes=[],
            warnings=["Is/Is-Not matrix contains no scoping rows."],
            recommendations=[
                "Populate problem boundary observations across all 4 Kepner-Tregoe dimensions (WHAT, WHERE, WHEN, EXTENT)."
            ],
        )

    # Validate through quality_core.rca.schema.validate_is_is_not
    matrix = validate_is_is_not(data, problem_statement=effective_problem)

    present_dim_set = {row.dimension for row in matrix.rows}
    dimension_coverage: dict[str, bool] = {dim: (dim in present_dim_set) for dim in KT_DIMENSIONS}
    complete_dimensions: list[str] = [dim for dim in KT_DIMENSIONS if dim in present_dim_set]
    missing_dimensions: list[str] = [dim for dim in KT_DIMENSIONS if dim not in present_dim_set]

    candidate_causes: list[CandidateCause] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    for row in matrix.rows:
        dim = row.dimension
        dist = row.distinctions
        chg = row.changes

        if dist is not None and chg is not None:
            hypothesis = (
                f"Distinction in {dim} ('{dist}') combined with change ('{chg}') "
                f"may explain why '{effective_problem}' occurred."
            )
            candidate_causes.append(
                CandidateCause(
                    dimension=dim,
                    distinction=dist,
                    change=chg,
                    hypothesis=hypothesis,
                    is_paired=True,
                )
            )
        elif dist is not None and chg is None:
            hypothesis = (
                f"Distinction in {dim} ('{dist}') without identified change: "
                f"investigate what changed in, on, around, or about this distinction per KT Chapter 2."
            )
            candidate_causes.append(
                CandidateCause(
                    dimension=dim,
                    distinction=dist,
                    change=None,
                    hypothesis=hypothesis,
                    is_paired=False,
                )
            )
            warnings.append(
                f"Dimension '{dim}' has distinctions recorded ('{dist}') but is missing associated changes."
            )
            recommendations.append(
                f"Investigate what changed in, on, around, or about the distinction '{dist}' in '{dim}' per KT Chapter 2."
            )
        elif dist is None and chg is not None:
            hypothesis = (
                f"Change in {dim} ('{chg}') without identified distinction: "
                f"investigate what distinguishes the IS data from the IS NOT data regarding this change."
            )
            candidate_causes.append(
                CandidateCause(
                    dimension=dim,
                    distinction="",
                    change=chg,
                    hypothesis=hypothesis,
                    is_paired=False,
                )
            )
            warnings.append(
                f"Dimension '{dim}' has changes recorded ('{chg}') but is missing distinctions between IS and IS NOT data."
            )
            recommendations.append(
                f"Determine what is unique or distinctive about the '{dim}' IS data compared to the IS NOT data to contextualize the observed change."
            )
        else:
            warnings.append(
                f"Dimension '{dim}' has IS and IS NOT data but is missing both distinctions and changes."
            )
            recommendations.append(
                f"Identify what is distinctive about the IS data compared to the IS NOT data for '{dim}', and what changed in or around that distinction per KT Chapter 2."
            )

    if missing_dimensions:
        warnings.append(
            f"Incomplete KT problem scope: missing dimensions {', '.join(missing_dimensions)}. "
            f"Complete all 4 dimensions (WHAT, WHERE, WHEN, EXTENT) to fully isolate the problem boundary."
        )
        recommendations.append(
            f"Scope the unexamined dimensions ({', '.join(missing_dimensions)}) using comparative IS vs IS NOT questioning per Kepner & Tregoe (1997)."
        )

    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    if warnings:
        verdict = "WARNING"
        valid = True
    else:
        verdict = "ACCEPT"
        valid = True
        recommendations.append(
            "Problem boundary is fully scoped across all 4 KT dimensions with paired distinctions and changes. "
            "Proceed to test candidate cause hypotheses against all IS and IS NOT facts."
        )

    return IsIsNotScopingResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        problem_statement=effective_problem,
        total_rows=len(matrix.rows),
        dimension_coverage=dimension_coverage,
        complete_dimensions=complete_dimensions,
        missing_dimensions=missing_dimensions,
        candidate_causes=[c.to_dict() for c in candidate_causes],
        warnings=warnings,
        recommendations=recommendations,
    )

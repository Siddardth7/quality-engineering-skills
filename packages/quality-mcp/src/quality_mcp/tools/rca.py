"""
rca.py
FastMCP tools for 5-Why and 6M Fishbone Root Cause Analysis (RCA) validation and visual canvas rendering.

Exposes deterministic 5-Why causal chain validation, reverse therefore logic checking,
anti-pattern detection, systemic root cause classification, 6M Fishbone categorization,
empty branch detection, and themed HTML canvas generation from quality_core.rca and
quality_core.canvas to AI agents and MCP client hosts.

Standards References:
- Kaoru Ishikawa, Guide to Quality Control (2nd Revised Edition, 1986), Chapter 3.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section 5 & Section G1.
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Section D4 & D7.
- Nancy R. Tague, The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005), Chapter 5.
"""

from __future__ import annotations

from typing import Annotated, Any

import pydantic
from pydantic import Field
from quality_core.canvas.rca import (
    SAMPLE_FISHBONE_CAUSES,
    SAMPLE_FIVE_WHY_STEPS,
    FishboneCanvas,
    FiveWhyCanvas,
)
from quality_core.io.validate import clean_pydantic_message
from quality_core.rca.fishbone import categorize_fishbone as _categorize_fishbone
from quality_core.rca.five_why import validate_five_why_chain
from quality_core.rca.schema import CATEGORY_6M_VALUES

__all__ = [
    "categorize_fishbone",
    "render_5why_canvas",
    "render_fishbone_canvas",
    "validate_5why",
]

_STANDARDS_BASIS = "AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox"
_FISHBONE_STANDARDS_BASIS = "Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox"


def validate_5why(
    steps: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "List of 5-Why step dictionaries. Each dictionary contains "
                "'step_number' (int >= 1), 'why' (str), and 'because' (str). "
                "If omitted or None, loads the standard reference Ford Global 8D bearing induction case."
            ),
        ),
    ] = None,
    problem_statement: Annotated[
        str,
        Field(description="Problem statement describing the observed failure effect or defect."),
    ] = "Problem Statement",
    root_cause: Annotated[
        str | None,
        Field(description="Optional explicit root cause statement. If omitted, uses the terminal step's explanation."),
    ] = None,
    leg_type: Annotated[
        str | None,
        Field(description="Optional 3-Legged 5-Why leg classification: 'occurrence', 'escape', or 'systemic'."),
    ] = None,
) -> dict[str, Any]:
    """Validate a 5-Why causal chain for forward consistency, reverse logic, and anti-patterns.

    Deterministic FastMCP tool wrapping `quality_core.rca.five_why.validate_five_why_chain`.
    Evaluates forward "Why -> Because" drill-down, bottom-up "Because -> Therefore" reverse
    necessity per AIAG CQI-20 / RULE 3, detects circular reasoning loops and superficial/blame-terminal
    operator causes per ASQ Quality Toolbox & Ford Global 8D / RULE 4, classifies systemic vs
    individual causes, and outputs structured findings and recommendations.

    Parameters
    ----------
    steps : list[dict[str, Any]] | None, optional
        List of step dictionaries with keys `step_number`, `why`, `because`. If None,
        loads the reference Ford Global 8D bearing induction benchmark case.
    problem_statement : str, default "Problem Statement"
        The top-level problem or defect statement being investigated.
    root_cause : str | None, optional
        Explicit terminal root cause statement.
    leg_type : str | None, optional
        Optional 3-Legged 5-Why leg classification ('occurrence', 'escape', or 'systemic').

    Returns
    -------
    dict[str, Any]
        Structured validation output containing:
        - basis: Standards attribution string ("AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox")
        - valid: Boolean indicating whether the chain is valid without hard anti-patterns
        - verdict: Categorical evaluation verdict ("ACCEPT", "WARNING", "REJECT")
        - reversibility_score: Numerical score in [0.0, 1.0]
        - problem_statement: Evaluated problem statement
        - root_cause: Isolated terminal root cause
        - total_steps: Number of steps evaluated
        - link_evaluations: List of step-by-step link evaluations with reverse statements
        - anti_patterns: List of detected anti-pattern findings
        - systemic_assessment: Systemic root cause classification breakdown
        - recommendations: Actionable engineering recommendations
        - leg_type: Leg type classification if provided

    Raises
    ------
    TypeError
        If steps is not a list/None, or any field has an invalid data type.
    ValueError
        If problem_statement is empty.
    """
    if isinstance(problem_statement, bool) or not isinstance(problem_statement, str):
        raise TypeError(f"problem_statement must be a string, got {type(problem_statement).__name__}")
    if not problem_statement.strip():
        raise ValueError("problem_statement must not be empty.")

    if root_cause is not None:
        if isinstance(root_cause, bool) or not isinstance(root_cause, str):
            raise TypeError(f"root_cause must be a string or None, got {type(root_cause).__name__}")

    if leg_type is not None:
        if isinstance(leg_type, bool) or not isinstance(leg_type, str):
            raise TypeError(f"leg_type must be a string or None, got {type(leg_type).__name__}")

    prob: str
    rc: str | None
    lt: str | None
    raw_steps: list[dict[str, Any]]

    if steps is None:
        raw_steps = SAMPLE_FIVE_WHY_STEPS
        prob = "Hole positions outside of tolerance on CNC drilling station" if problem_statement == "Problem Statement" else problem_statement
        rc = "The induction plan was not signed by Engineering" if root_cause is None else root_cause
        lt = "occurrence" if leg_type is None else leg_type
    else:
        if isinstance(steps, (str, dict, int, bool)) or not isinstance(steps, list):
            raise TypeError(f"steps must be a list of dictionaries or None, got {type(steps).__name__}: {steps!r}")
        for idx, item in enumerate(steps):
            if not isinstance(item, dict):
                raise TypeError(f"steps item at index {idx} must be a dict, got {type(item).__name__}: {item!r}")
        raw_steps = steps
        prob = problem_statement
        rc = root_cause
        lt = leg_type

    if len(raw_steps) == 0:
        return {
            "basis": _STANDARDS_BASIS,
            "valid": False,
            "verdict": "REJECT",
            "reversibility_score": 0.0,
            "problem_statement": prob,
            "root_cause": rc or "",
            "total_steps": 0,
            "link_evaluations": [],
            "anti_patterns": [
                {
                    "code": "PREMATURE_TERMINATION",
                    "severity": "error",
                    "step_number": None,
                    "message": "FiveWhyChain must contain at least one step.",
                    "recommendation": "Provide at least one Why/Because step in the chain.",
                }
            ],
            "systemic_assessment": {
                "classification": "UNCLASSIFIED",
                "is_systemic": False,
                "terminal_cause": "",
                "systemic_factors": [],
                "recommendations": ["Add steps to enable root cause analysis."],
            },
            "recommendations": ["FiveWhyChain must contain at least one step."],
            "leg_type": lt,
        }

    try:
        result = validate_five_why_chain(
            data=raw_steps,
            problem_statement=prob,
            root_cause=rc,
            leg_type=lt,
        )
        return result.to_dict()
    except pydantic.ValidationError as exc:
        errs = exc.errors()
        err_msg = str(errs[0].get("msg", "invalid value")) if errs else "invalid value"
        clean_msg = clean_pydantic_message(err_msg)


        return {
            "basis": _STANDARDS_BASIS,
            "valid": False,
            "verdict": "REJECT",
            "reversibility_score": 0.0,
            "problem_statement": prob,
            "root_cause": rc or "",
            "total_steps": len(raw_steps),
            "link_evaluations": [],
            "anti_patterns": [
                {
                    "code": "SCHEMA_VALIDATION_ERROR",
                    "severity": "error",
                    "step_number": None,
                    "message": clean_msg,
                    "recommendation": "Correct step sequence numbers, ensure consecutive numbering from 1, and provide non-blank text.",
                }
            ],
            "systemic_assessment": {
                "classification": "UNCLASSIFIED",
                "is_systemic": False,
                "terminal_cause": "",
                "systemic_factors": [],
                "recommendations": ["Resolve schema errors before evaluating causality."],
            },
            "recommendations": [f"Schema validation error: {clean_msg}"],
            "leg_type": lt,
        }


def render_5why_canvas(
    steps: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional list of 5-Why step dictionaries. Each dictionary contains "
                "'step_number' (int >= 1), 'why' (str), and 'because' (str). "
                "If omitted or None, loads the standard reference Ford Global 8D benchmark dataset."
            ),
        ),
    ] = None,
    problem_statement: Annotated[
        str,
        Field(description="Problem statement describing the observed failure effect or defect."),
    ] = "Problem Statement",
    root_cause: Annotated[
        str | None,
        Field(description="Optional explicit root cause statement."),
    ] = None,
    leg_type: Annotated[
        str | None,
        Field(description="Optional 3-Legged 5-Why leg classification: 'occurrence', 'escape', or 'systemic'."),
    ] = None,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "5-Why Root Cause Analysis Canvas",
    theme: Annotated[
        str,
        Field(description="Color theme palette: 'dark' (default) or 'light'."),
    ] = "dark",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive visual HTML canvas for a 5-Why Root Cause Analysis dataset.

    Deterministic FastMCP tool wrapping `quality_core.canvas.rca.FiveWhyCanvas`.
    Ingests 5-Why steps, evaluates causal reversibility, checks for anti-patterns,
    and generates a styled HTML canvas view with summary KPI cards and reverse logic arrows.

    Parameters
    ----------
    steps : list[dict[str, Any]] | None, optional
        List of 5-Why step dictionaries. If None, loads the reference sample dataset.
    problem_statement : str, default "Problem Statement"
        The top-level problem or defect statement.
    root_cause : str | None, optional
        Explicit terminal root cause statement.
    leg_type : str | None, optional
        Optional 3-Legged 5-Why leg classification.
    title : str, default "5-Why Root Cause Analysis Canvas"
        Title of the 5-Why canvas.
    theme : str, default "dark"
        Color theme: "dark" or "light".
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable markup.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - title: The canvas title (str)
        - rows_count: Total number of rendered steps (int)
        - steps_count: Total number of rendered steps (int)
        - verdict: Validation verdict (str)
        - valid: Boolean validity status (bool)
        - reversibility_score: Reversibility score (float)
        - summary: Summary metrics breakdown (dict)
        - html: Rendered HTML string (str)

    Raises
    ------
    TypeError
        If steps is not a list/None, title/theme/problem_statement are not strings,
        standalone is not a boolean, or any step is not a dictionary.
    ValueError
        If title or problem_statement is empty, or theme is not 'dark'/'light'.
    """
    if isinstance(standalone, int) and not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")
    if not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if isinstance(problem_statement, bool) or not isinstance(problem_statement, str):
        raise TypeError(f"problem_statement must be a string, got {type(problem_statement).__name__}")
    if not problem_statement.strip():
        raise ValueError("problem_statement must not be empty.")

    if theme not in ("dark", "light"):
        raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

    if steps is None:
        canvas = FiveWhyCanvas.load_sample(title=title)
        if problem_statement != "Problem Statement":
            canvas.set_problem_statement(problem_statement)
        if root_cause is not None:
            canvas.set_root_cause(root_cause)
        if leg_type is not None:
            canvas.set_leg_type(leg_type)
    else:
        if isinstance(steps, (str, dict, int, bool)) or not isinstance(steps, list):
            raise TypeError(f"steps must be a list of dictionaries or None, got {type(steps).__name__}: {steps!r}")
        canvas = FiveWhyCanvas(
            title=title,
            problem_statement=problem_statement,
            root_cause=root_cause,
            leg_type=leg_type,
        )
        for idx, item in enumerate(steps):
            if not isinstance(item, dict):
                raise TypeError(f"steps item at index {idx} must be a dict, got {type(item).__name__}: {item!r}")
            step_dict = dict(item)
            if "step_number" not in step_dict and "StepNumber" not in step_dict and "step" not in step_dict and "id" not in step_dict:
                step_dict["step_number"] = idx + 1
            canvas.add_step(step_dict)

    html_content = canvas.to_html(theme=theme, standalone=standalone)  # type: ignore[arg-type]
    summary = canvas.get_summary()

    return {
        "title": canvas.title,
        "rows_count": len(canvas.steps),
        "steps_count": len(canvas.steps),
        "verdict": summary.get("verdict", "EMPTY"),
        "valid": summary.get("valid", False),
        "reversibility_score": summary.get("reversibility_score", 0.0),
        "summary": summary,
        "html": html_content,
    }


def categorize_fishbone(
    causes: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "List of 6M Fishbone cause dictionaries. Each dictionary contains "
                "'category' (str: Man, Machine, Method, Material, Measurement, Environment or recognized alias), "
                "'cause' (str), and optional 'sub_category' (str). "
                "If omitted or None, loads the standard reference Sentinel-8D Pneumatic Cylinder benchmark dataset."
            ),
        ),
    ] = None,
    effect: Annotated[
        str,
        Field(description="Problem effect statement describing the failure or defect mode."),
    ] = "Problem Effect",
    effect_statement: Annotated[
        str | None,
        Field(description="Optional alias for effect statement. If provided, overrides 'effect'."),
    ] = None,
    check_balance: Annotated[
        bool,
        Field(description="Whether to check for branch concentration / imbalance."),
    ] = True,
    balance_threshold: Annotated[
        float,
        Field(description="Threshold fraction (0.0 to 1.0) above which a single branch triggers an imbalance warning when total causes >= 3. Default is 0.75."),
    ] = 0.75,
) -> dict[str, Any]:
    """Categorize, validate, and audit a 6M Fishbone cause-and-effect dataset.

    Deterministic FastMCP tool wrapping `quality_core.rca.fishbone.categorize_fishbone`.
    Normalizes cause categories across the canonical 6M taxonomy (Man, Machine, Method,
    Material, Measurement, Environment), detects empty branches / bare legs per Ishikawa (1986)
    & AIAG CQI-20 Section G1, identifies duplicate causes, audits branch concentration balance
    against `balance_threshold`, and outputs structured findings and recommendations.

    Parameters
    ----------
    causes : list[dict[str, Any]] | None, optional
        List of cause dictionaries with keys `category`, `cause`, and optional `sub_category`.
        If None, loads the reference Sentinel-8D Pneumatic Cylinder benchmark dataset.
    effect : str, default "Problem Effect"
        The top-level failure effect or defect statement.
    effect_statement : str | None, optional
        Optional alias for effect statement.
    check_balance : bool, default True
        Whether to evaluate branch concentration / imbalance.
    balance_threshold : float, default 0.75
        Fractional concentration threshold.

    Returns
    -------
    dict[str, Any]
        Structured categorization and audit output.

    Raises
    ------
    TypeError
        If causes is not a list/None, effect/effect_statement is not a string, or check_balance is not a boolean.
    ValueError
        If effect/effect_statement is empty or balance_threshold is out of range.
    """
    if isinstance(check_balance, int) and not isinstance(check_balance, bool):
        raise TypeError(f"check_balance must be a boolean, got {type(check_balance).__name__}: {check_balance!r}")
    if not isinstance(check_balance, bool):
        raise TypeError(f"check_balance must be a boolean, got {type(check_balance).__name__}: {check_balance!r}")

    if isinstance(balance_threshold, bool) or not isinstance(balance_threshold, (int, float)):
        raise TypeError(f"balance_threshold must be a float, got {type(balance_threshold).__name__}: {balance_threshold!r}")
    if not (0.0 < balance_threshold <= 1.0):
        raise ValueError("balance_threshold must be a float between 0 and 1.")

    eff_input = effect_statement if effect_statement is not None else effect
    if isinstance(eff_input, bool) or not isinstance(eff_input, str):
        raise TypeError(f"effect must be a string, got {type(eff_input).__name__}")
    if not eff_input.strip():
        raise ValueError("effect must not be empty.")

    eff: str
    raw_causes: list[dict[str, Any]]

    if causes is None:
        raw_causes = SAMPLE_FISHBONE_CAUSES
        eff = "Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)" if eff_input == "Problem Effect" else eff_input.strip()
    else:
        if isinstance(causes, (str, dict, int, bool)) or not isinstance(causes, list):
            raise TypeError(f"causes must be a list of dictionaries or None, got {type(causes).__name__}: {causes!r}")
        for idx, item in enumerate(causes):
            if not isinstance(item, dict):
                raise TypeError(f"causes item at index {idx} must be a dict, got {type(item).__name__}: {item!r}")
        raw_causes = causes
        eff = eff_input.strip()

    if len(raw_causes) == 0:
        return {
            "basis": _FISHBONE_STANDARDS_BASIS,
            "valid": False,
            "verdict": "REJECT",
            "effect_statement": eff,
            "total_causes": 0,
            "branch_counts": {b: 0 for b in CATEGORY_6M_VALUES},
            "grouped_causes": {b: [] for b in CATEGORY_6M_VALUES},
            "empty_branches": list(CATEGORY_6M_VALUES),
            "duplicate_causes": [],
            "uncategorized_causes": [],
            "warnings": ["Fishbone dataset contains no causes."],
            "recommendations": ["Populate brainstormed causes across the 6M categories (Man, Machine, Method, Material, Measurement, Environment)."],
        }

    try:
        result = _categorize_fishbone(
            data=raw_causes,
            effect_statement=eff,
            check_balance=check_balance,
            balance_threshold=balance_threshold,
        )
        return result.to_dict()
    except pydantic.ValidationError as exc:
        errs = exc.errors()
        err_msg = str(errs[0].get("msg", "invalid value")) if errs else "invalid value"
        clean_msg = clean_pydantic_message(err_msg)
        return {
            "basis": _FISHBONE_STANDARDS_BASIS,
            "valid": False,
            "verdict": "REJECT",
            "effect_statement": eff,
            "total_causes": len(raw_causes),
            "branch_counts": {b: 0 for b in CATEGORY_6M_VALUES},
            "grouped_causes": {b: [] for b in CATEGORY_6M_VALUES},
            "empty_branches": list(CATEGORY_6M_VALUES),
            "duplicate_causes": [],
            "uncategorized_causes": [],
            "warnings": [f"Schema validation error: {clean_msg}"],
            "recommendations": ["Correct cause categories or field constraints to enable categorization."],
        }


def render_fishbone_canvas(
    causes: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional list of 6M Fishbone cause dictionaries. Each dictionary contains "
                "'category' (str), 'cause' (str), and optional 'sub_category' (str). "
                "If omitted or None, loads the standard reference Sentinel-8D Pneumatic Cylinder benchmark dataset."
            ),
        ),
    ] = None,
    effect: Annotated[
        str,
        Field(description="Problem effect statement describing the failure or defect mode."),
    ] = "Problem Effect",
    effect_statement: Annotated[
        str | None,
        Field(description="Optional alias for effect statement. If provided, overrides 'effect'."),
    ] = None,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "6M Fishbone Cause-and-Effect Canvas",
    theme: Annotated[
        str,
        Field(description="Color theme palette: 'dark' (default) or 'light'."),
    ] = "dark",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
    balance_threshold: Annotated[
        float,
        Field(description="Threshold fraction for branch concentration balance check. Default is 0.75."),
    ] = 0.75,
) -> dict[str, Any]:
    """Render an interactive visual HTML/SVG canvas for a 6M Fishbone dataset.

    Deterministic FastMCP tool wrapping `quality_core.canvas.rca.FishboneCanvas`.
    Ingests 6M causes, evaluates branch distribution, detects empty legs and duplicates,
    and generates a styled HTML/SVG Ishikawa diagram with summary KPI cards.

    Parameters
    ----------
    causes : list[dict[str, Any]] | None, optional
        List of 6M cause dictionaries. If None, loads the reference sample dataset.
    effect : str, default "Problem Effect"
        The top-level failure effect or defect statement.
    effect_statement : str | None, optional
        Optional alias for effect statement.
    title : str, default "6M Fishbone Cause-and-Effect Canvas"
        Title of the Fishbone canvas.
    theme : str, default "dark"
        Color theme: "dark" or "light".
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable markup.
    balance_threshold : float, default 0.75
        Threshold fraction for branch balance check.

    Returns
    -------
    dict[str, Any]
        Dictionary containing title, rows_count, causes_count, verdict, valid, summary, and html.

    Raises
    ------
    TypeError
        If causes is not a list/None, title/theme/effect are not strings, standalone is not a boolean,
        or any cause is not a dictionary.
    ValueError
        If title or effect is empty, or theme is not 'dark'/'light'.
    """
    if isinstance(standalone, int) and not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")
    if not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    eff_input = effect_statement if effect_statement is not None else effect
    if isinstance(eff_input, bool) or not isinstance(eff_input, str):
        raise TypeError(f"effect must be a string, got {type(eff_input).__name__}")
    if not eff_input.strip():
        raise ValueError("effect must not be empty.")

    if theme not in ("dark", "light"):
        raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

    if isinstance(balance_threshold, bool) or not isinstance(balance_threshold, (int, float)):
        raise TypeError(f"balance_threshold must be a float, got {type(balance_threshold).__name__}: {balance_threshold!r}")
    if not (0.0 < balance_threshold <= 1.0):
        raise ValueError("balance_threshold must be a float between 0 and 1.")

    if causes is None:
        canvas = FishboneCanvas.load_sample(title=title)
        if eff_input != "Problem Effect":
            canvas.set_effect(eff_input.strip())
    else:
        if isinstance(causes, (str, dict, int, bool)) or not isinstance(causes, list):
            raise TypeError(f"causes must be a list of dictionaries or None, got {type(causes).__name__}: {causes!r}")
        canvas = FishboneCanvas(
            title=title,
            effect=eff_input.strip(),
            balance_threshold=balance_threshold,
        )
        for idx, item in enumerate(causes):
            if not isinstance(item, dict):
                raise TypeError(f"causes item at index {idx} must be a dict, got {type(item).__name__}: {item!r}")
            canvas.add_cause(item)

    html_content = canvas.to_html(theme=theme, standalone=standalone)  # type: ignore[arg-type]
    summary = canvas.get_summary()

    return {
        "title": canvas.title,
        "rows_count": len(canvas.causes),
        "causes_count": len(canvas.causes),
        "verdict": summary.get("verdict", "EMPTY"),
        "valid": summary.get("valid", False),
        "summary": summary,
        "html": html_content,
    }


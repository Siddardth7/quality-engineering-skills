"""
canvas.py
FMEA, SPC, MSA, Control Plan, and 5-Why visual canvas rendering tools for Model Context Protocol (MCP).

Exposes styled interactive HTML canvas generation and risk/stability/MSA/ControlPlan/5-Why summary metrics
from quality_core.canvas to AI agents and MCP client hosts.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field
from quality_core.canvas import (
    ControlPlanCanvas,
    FMEACanvas,
    MSACanvas,
    NCRCanvas,
    SPCCanvas,
)

from quality_mcp.tools.rca import (
    render_5why_canvas,
    render_fishbone_canvas,
    render_is_is_not_canvas,
    render_isisnot_canvas,
)


def render_fmea_canvas(
    dataset: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional list of FMEA row dictionaries. Each dictionary contains "
                "id, process_step, component, function, failure_mode, effect, severity, "
                "cause, occurrence, current_control, detection, and optional ai_candidate flag. "
                "If omitted or None, loads the standard reference automotive sample dataset."
            ),
        ),
    ] = None,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "AIAG & VDA 2019 Process FMEA Canvas",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive visual HTML canvas for an AIAG-VDA 2019 FMEA dataset.

    Deterministic function wrapping `quality_core.canvas.FMEACanvas`. Ingests FMEA
    rows, computes AIAG-VDA 2019 Action Priority and RPN for every item using
    `quality_core.scoring`, and generates a themed HTML canvas view with summary metrics.

    Parameters
    ----------
    dataset : list[dict[str, Any]] | None, optional
        List of FMEA row dictionaries. If None, loads the reference sample dataset.
    title : str, default "AIAG & VDA 2019 Process FMEA Canvas"
        Title of the FMEA canvas.
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable markup.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - ``"title"``: The canvas title (str).
        - ``"rows_count"``: Total number of rendered rows (int).
        - ``"summary"``: Risk summary statistics breakdown (dict).
        - ``"html"``: Rendered HTML string (str).

    Raises
    ------
    TypeError
        If dataset is not a list/None, title is not a string, standalone is not a boolean,
        or any row in dataset is not a dictionary.
    ValueError
        If title is empty, or any row contains invalid/out-of-range data.
    """
    if isinstance(standalone, int) and not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")
    if not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if dataset is None:
        canvas = FMEACanvas.load_sample(title=title)
    else:
        if isinstance(dataset, (str, dict, int, bool)) or not isinstance(dataset, list):
            raise TypeError(f"dataset must be a list of dictionaries or None, got {type(dataset).__name__}: {dataset!r}")
        canvas = FMEACanvas(title=title)
        for idx, item in enumerate(dataset):
            if not isinstance(item, dict):
                raise TypeError(f"dataset item at index {idx} must be a dict, got {type(item).__name__}: {item!r}")
            canvas.add_row(item)

    html_content = canvas.to_html(standalone=standalone)
    summary = canvas.get_summary()

    return {
        "title": canvas.title,
        "rows_count": len(canvas.rows),
        "summary": summary,
        "html": html_content,
    }


def render_spc_canvas(
    chart_type: Annotated[
        str,
        Field(
            description=(
                "SPC chart type. Supported: 'Xbar-R', 'Xbar-S', 'I-MR', 'p', 'c', 'u'. Default is 'Xbar-R'."
            ),
        ),
    ] = "Xbar-R",
    data: Annotated[
        list[list[float]] | list[float] | None,
        Field(
            description=(
                "Measurement observations. For 'Xbar-R' / 'Xbar-S', provide a 2D list of subgroups (e.g. [[10.1, 10.0], ...]). "
                "For 'I-MR', 'p', 'c', 'u', provide a 1D list of values or counts. "
                "If omitted or None, loads the reference AIAG SPC 4th Ed. Xbar-R shaft diameters benchmark dataset."
            ),
        ),
    ] = None,
    usl: Annotated[
        float | None,
        Field(description="Upper Specification Limit for capability evaluation."),
    ] = None,
    lsl: Annotated[
        float | None,
        Field(description="Lower Specification Limit for capability evaluation."),
    ] = None,
    sample_sizes: Annotated[
        list[float] | None,
        Field(description="Inspection sample sizes per subgroup (required for 'p' and 'u' attribute charts)."),
    ] = None,
    rule_set: Annotated[
        str,
        Field(description="Run-rule detection ruleset: 'Western Electric' (default) or 'Nelson'."),
    ] = "Western Electric",
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "AIAG SPC Control Chart Canvas",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive visual HTML/SVG canvas for an SPC Control Chart dataset.

    Deterministic function wrapping `quality_core.canvas.SPCCanvas`. Ingests measurement
    data, computes control limits and run rules via `quality_core.spc`, enforces the
    stability-before-capability rule, and generates a themed HTML5/SVG canvas view.

    Parameters
    ----------
    chart_type : str, default "Xbar-R"
        Type of Shewhart control chart.
    data : list[list[float]] | list[float] | None, optional
        Subgroups or observations. If None, loads the AIAG benchmark sample dataset.
    usl : float | None, optional
        Upper specification limit.
    lsl : float | None, optional
        Lower specification limit.
    sample_sizes : list[float] | None, optional
        Subgroup sample sizes for attribute charts.
    rule_set : str, default "Western Electric"
        Run-rule detection set.
    title : str, default "AIAG SPC Control Chart Canvas"
        Title of the SPC canvas.
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable container.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - ``"title"``: Canvas title (str).
        - ``"chart_type"``: Chart type (str).
        - ``"in_control"``: Process statistical control status (bool).
        - ``"stable"``: Process stability status (bool).
        - ``"violations_count"``: Total detected run-rule violations (int).
        - ``"violations"``: List of violation dictionaries (list[dict]).
        - ``"capability"``: Process capability metrics if in-control and specs given, else None (dict | None).
        - ``"html"``: Rendered HTML string (str).
    """
    if isinstance(standalone, int) and not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")
    if not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if data is None:
        canvas = SPCCanvas.load_sample(
            chart_type=chart_type,
            title=title,
            usl=usl if usl is not None else 10.5,
            lsl=lsl if lsl is not None else 9.5,
        )
    else:
        canvas = SPCCanvas(
            chart_type=chart_type,
            title=title,
            usl=usl,
            lsl=lsl,
            rule_set=rule_set,
            sample_sizes=sample_sizes,
            data=data,
        )

    html_content = canvas.to_html(standalone=standalone)
    summary = canvas.get_summary()

    return {
        "title": canvas.title,
        "chart_type": canvas.chart_type,
        "in_control": summary["in_control"],
        "stable": summary["stable"],
        "violations_count": summary["violations_count"],
        "violations": summary["violations"],
        "capability": summary["capability"],
        "html": html_content,
    }


def render_msa_canvas(
    measurements: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional list of Gage R&R measurement records with keys 'part', 'appraiser', 'trial', and 'measurement'. "
                "If omitted or None, loads the standard reference AIAG MSA 4th Edition 10x3x3 crossed study benchmark dataset."
            ),
        ),
    ] = None,
    method: Annotated[
        str,
        Field(description="Gage R&R method: 'anova' (recommended) or 'average_and_range'. Default is 'anova'."),
    ] = "anova",
    tolerance: Annotated[
        float | None,
        Field(description="Optional engineering tolerance (USL - LSL) for % Tolerance metrics."),
    ] = None,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "AIAG MSA Gage R&R Canvas",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive visual HTML/SVG canvas for a Gage R&R dataset.

    Deterministic function wrapping `quality_core.canvas.MSACanvas`. Ingests Gage R&R
    measurements, calculates variance components, ANOVA interaction test, %GRR, and ndc
    via `quality_core.msa`, and generates a themed HTML5/SVG canvas view with an Operator x Part
    Interaction Plot and Variance Components bar chart.

    Parameters
    ----------
    measurements : list[dict[str, Any]] | None, optional
        List of measurement records. If None, loads the AIAG reference benchmark study.
    method : str, default "anova"
        Analysis method: "anova" or "average_and_range".
    tolerance : float | None, optional
        Engineering specification tolerance.
    title : str, default "AIAG MSA Gage R&R Canvas"
        Title of the MSA canvas.
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable container.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - ``"title"``: Canvas title (str).
        - ``"method"``: Method used (str).
        - ``"verdict"``: AIAG acceptance verdict (str).
        - ``"ndc"``: Number of distinct categories (int).
        - ``"pgrr_study"``: %GRR of study variation (float).
        - ``"pgrr_tolerance"``: %GRR of tolerance if tolerance provided, else None (float | None).
        - ``"interaction_significant"``: Whether part x appraiser interaction is statistically significant (bool | None).
        - ``"summary"``: Statistical summary dictionary (dict).
        - ``"html"``: Rendered HTML string (str).
    """
    if isinstance(standalone, int) and not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")
    if not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if measurements is None:
        canvas = MSACanvas.load_sample(
            method=method,
            title=title,
            tolerance=tolerance if tolerance is not None else 4.42,
        )
    else:
        canvas = MSACanvas(
            method=method,
            title=title,
            tolerance=tolerance,
            measurements=measurements,
        )

    html_content = canvas.to_html(standalone=standalone)
    summary = canvas.get_summary()

    return {
        "title": canvas.title,
        "method": canvas.method,
        "verdict": canvas.verdict,
        "ndc": canvas.ndc,
        "pgrr_study": canvas.pgrr_study,
        "pgrr_tolerance": canvas.pgrr_tolerance,
        "interaction_significant": canvas.interaction_significant,
        "summary": summary,
        "html": html_content,
    }


def render_controlplan_canvas(
    dataset: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional list of Control Plan row dictionaries. Each dictionary contains "
                "characteristic, measurement_method, sample_size, frequency, reaction_plan, "
                "and optional lsl, usl, target, recommended_chart, source_cause_id, and "
                "sample_plan_is_placeholder. If omitted or None, loads the standard reference sample dataset."
            ),
        ),
    ] = None,
    fmea: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional list of FMEA row dictionaries to evaluate bidirectional PFMEA linkage. "
                "If provided, flags orphan characteristics and identifies uncovered FMEA failure modes."
            ),
        ),
    ] = None,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "AIAG APQP Control Plan Matrix Canvas",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive visual HTML matrix canvas for an AIAG APQP Control Plan dataset.

    Deterministic function wrapping `quality_core.canvas.ControlPlanCanvas`. Ingests Control Plan
    rows, performs specification tolerance checks and optional PFMEA bidirectional linkage verification
    using `quality_core.controlplan`, and generates a themed HTML canvas view with summary metrics.

    Parameters
    ----------
    dataset : list[dict[str, Any]] | None, optional
        List of Control Plan row dictionaries. If None, loads the reference sample dataset.
    fmea : list[dict[str, Any]] | None, optional
        List of FMEA row dictionaries to evaluate bidirectional PFMEA linkage.
    title : str, default "AIAG APQP Control Plan Matrix Canvas"
        Title of the Control Plan canvas.
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable markup.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - ``"title"``: The canvas title (str).
        - ``"rows_count"``: Total number of rendered rows (int).
        - ``"valid"``: Boolean indicating whether all characteristics are valid without orphan linkages (bool).
        - ``"summary"``: Control Plan summary statistics breakdown (dict).
        - ``"findings"``: List of validation findings and orphan warnings (list[str]).
        - ``"html"``: Rendered HTML string (str).

    Raises
    ------
    TypeError
        If dataset or fmea is not a list/None, title is not a string, standalone is not a boolean,
        or any item in dataset/fmea is not a dictionary.
    ValueError
        If title is empty, or any row contains invalid/out-of-range data.
    """
    if isinstance(standalone, int) and not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")
    if not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if fmea is not None:
        if isinstance(fmea, (str, dict, int, bool)) or not isinstance(fmea, list):
            raise TypeError(f"fmea must be a list of dictionaries or None, got {type(fmea).__name__}: {fmea!r}")
        for idx, item in enumerate(fmea):
            if not isinstance(item, dict):
                raise TypeError(f"fmea item at index {idx} must be a dict, got {type(item).__name__}: {item!r}")

    if dataset is None:
        canvas = ControlPlanCanvas.load_sample(title=title)
        if fmea is not None:
            canvas.validate_linkage(fmea)
    else:
        if isinstance(dataset, (str, dict, int, bool)) or not isinstance(dataset, list):
            raise TypeError(f"dataset must be a list of dictionaries or None, got {type(dataset).__name__}: {dataset!r}")
        canvas = ControlPlanCanvas(title=title)
        for idx, item in enumerate(dataset):
            if not isinstance(item, dict):
                raise TypeError(f"dataset item at index {idx} must be a dict, got {type(item).__name__}: {item!r}")
            row_dict = dict(item)
            if "id" not in row_dict and "ID" not in row_dict:
                row_dict["id"] = idx + 1
            canvas.add_row(row_dict)
        if fmea is not None:
            canvas.validate_linkage(fmea)

    html_content = canvas.to_html(standalone=standalone)
    summary = canvas.get_summary()
    valid = (
        (summary["orphan_count"] == 0)
        and (summary["uncovered_fms_count"] == 0)
        and (summary["warning_count"] == 0)
    )
    findings = list(summary["all_findings"])

    return {
        "title": canvas.title,
        "rows_count": len(canvas.rows),
        "valid": valid,
        "summary": summary,
        "findings": findings,
        "html": html_content,
    }


def render_ncr_canvas(
    records: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional list of Nonconformance Record dictionaries. Each dictionary contains "
                "record_id, part_lot_id, defect_description, requirement_violated, quantity_affected, "
                "detection_point, and optional disposition, severity, rationale, approval_authority. "
                "If omitted or None, loads the standard reference automotive/machining sample dataset."
            ),
        ),
    ] = None,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "Nonconformance Report (NCR) Canvas",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive visual HTML canvas for an ISO 9001 §8.7 Nonconformance Report dataset.

    Deterministic function wrapping `quality_core.canvas.NCRCanvas`. Ingests Nonconformance
    records, computes disposition breakdown and MRB gate metrics, and generates a themed HTML
    canvas card log.

    Parameters
    ----------
    records : list[dict[str, Any]] | None, optional
        List of Nonconformance Record dictionaries. If None, loads the reference sample dataset.
    title : str, default "Nonconformance Report (NCR) Canvas"
        Title of the NCR canvas.
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable markup.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - ``"title"``: The canvas title (str).
        - ``"rows_count"``: Total number of rendered records (int).
        - ``"summary"``: NCR summary statistics breakdown (dict).
        - ``"html"``: Rendered HTML string (str).

    Raises
    ------
    TypeError
        If records is not a list/None, title is not a string, standalone is not a boolean,
        or any item in records is not a dictionary.
    ValueError
        If title is empty, or any record contains invalid data.
    """
    if type(standalone) is not bool:
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if records is None:
        canvas = NCRCanvas(title=title)
        from quality_core.canvas.ncr import SAMPLE_NCR_RECORDS
        for r in SAMPLE_NCR_RECORDS:
            canvas.add_record(r)
    else:
        if isinstance(records, (str, dict, int, bool)) or not isinstance(records, list):
            raise TypeError(f"records must be a list of dictionaries or None, got {type(records).__name__}: {records!r}")
        canvas = NCRCanvas(title=title)
        for idx, item in enumerate(records):
            if not isinstance(item, dict):
                raise TypeError(f"records item at index {idx} must be a dict, got {type(item).__name__}: {item!r}")
            canvas.add_record(item)

    html_content = canvas.to_html(standalone=standalone)
    summary = canvas.get_summary()

    return {
        "title": canvas.title,
        "rows_count": len(canvas.records),
        "summary": summary,
        "html": html_content,
    }


__all__ = [
    "render_5why_canvas",
    "render_controlplan_canvas",
    "render_fishbone_canvas",
    "render_fmea_canvas",
    "render_is_is_not_canvas",
    "render_isisnot_canvas",
    "render_msa_canvas",
    "render_ncr_canvas",
    "render_spc_canvas",
]


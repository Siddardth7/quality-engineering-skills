"""
canvas.py
FMEA and SPC visual canvas rendering tools for Model Context Protocol (MCP).

Exposes styled interactive HTML canvas generation and risk/stability summary metrics
from quality_core.canvas to AI agents and MCP client hosts.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field
from quality_core.canvas import FMEACanvas, SPCCanvas


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


__all__ = [
    "render_fmea_canvas",
    "render_spc_canvas",
]

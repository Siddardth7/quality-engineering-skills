"""
canvas.py
FMEA visual canvas rendering tool for Model Context Protocol (MCP).

Exposes styled interactive HTML canvas generation and risk summary metrics
from quality_core.canvas to AI agents and MCP client hosts.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field
from quality_core.canvas import FMEACanvas


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

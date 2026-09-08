"""
eight_d.py
FastMCP tools for Ford Global 8D / AIAG CQI-20 8D problem-solving reports.

Exposes the already-merged quality_core 8D surface over MCP as a transport layer only:
whole-report discipline validation and closure-gate evaluation, one hypothetical state
transition, and themed HTML canvas rendering. Every payload is the core engine's own
``to_dict()`` returned verbatim — this module computes no verdict, threshold, or caption
of its own and therefore asserts no standard of its own.

Standards References (as already cited by the wrapped engines, not by this module):
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018).

Citation basis in the returned payloads:
- Every finding carries ``citation_basis``: ``"RULE"`` (a ``RULE-8D-*`` row in
  quality_core/rca/CITATIONS.tsv quoting the Ford Global 8D Manual or AIAG CQI-20),
  ``"PDD"`` (a numbered Process Design Decision in quality_core/rca/ASSUMPTIONS_LOG.md —
  a platform choice, not a manual clause), or ``"PLATFORM_UNCITED"`` (neither).
- Every gate reason carries ``rule_id``: a ``RULE-8D-*`` id (manual-backed), a ``PDD-8D-*``
  id (platform decision, **not** a standards citation), or ``None`` (a pure adjacency-graph
  fact with no citation to make).
Read those two fields to tell a standards requirement from a platform heuristic; do not
infer it from the wording of a message.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

import pydantic
from pydantic import Field
from quality_core.canvas.eight_d import SAMPLE_EIGHT_D_REPORT, EightDCanvas
from quality_core.io.validate import clean_pydantic_message
from quality_core.rca.eight_d import EightDState
from quality_core.rca.eight_d import transition_eight_d as _transition_eight_d
from quality_core.rca.eight_d_disciplines import validate_8d as _validate_8d
from quality_core.rca.eight_d_schema import EightDReport, validate_eight_d

__all__ = [
    "advance_8d",
    "render_8d_canvas",
    "validate_8d",
]


def _coerce_report(report: dict[str, Any] | None) -> EightDReport:
    """Validate an untrusted 8D report dict at the trust boundary, or load the benchmark sample.

    Follows the ``validate_psw`` convention for whole-nested-dict input: a pydantic failure is
    re-raised as a ``ValueError`` carrying a cleaned message, never swallowed into a
    REJECT-shaped placeholder payload (a whole 8D report has no natural "empty" placeholder).
    """
    if report is not None and not isinstance(report, dict):
        raise TypeError(f"report must be a dict or None, got {type(report).__name__}")
    payload = SAMPLE_EIGHT_D_REPORT if report is None else report
    try:
        return validate_eight_d(payload)
    except pydantic.ValidationError as exc:
        errs = exc.errors()
        err_msg = str(errs[0].get("msg", "invalid value")) if errs else "invalid value"
        raise ValueError(clean_pydantic_message(err_msg)) from exc


def validate_8d(
    report: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Whole 8D report dictionary (report_id, status, current_discipline, and the "
                "optional d0-d8 discipline records). If omitted or None, loads the benchmark "
                "sample 8D report."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Validate a whole 8D report: every discipline engine plus every closure gate, read-only.

    Deterministic FastMCP tool wrapping `quality_core.rca.eight_d_disciplines.validate_8d`.
    The core result's `to_dict()` is returned verbatim, with no field renamed, dropped, or
    added by this transport layer.

    Two distinct `closeable` flags exist and they legitimately disagree — do not conflate them:

    - `result["closeable"]` is the **whole-report** gate: True only when `gate_reasons` is
      empty, which includes the D3-to-D4 linked-NCR gate (`PDD-8D-008`).
    - `result["d8"]["closeable"]` is **closure-evidence only**: whether the D8 record itself
      is complete. It can be True while the whole-report flag is False.

    `d4` is deliberately absent from the result: `validate_d4_root_cause` needs the raw 5-Why
    chains, which an `EightDReport` does not persist. D4's closure-relevant answer surfaces as
    a `ROOT_CAUSE_REJECTED` gate reason instead.

    Citation basis: each finding's `citation_basis` is `"RULE"` (a `RULE-8D-*` citation of the
    Ford Global 8D Manual / AIAG CQI-20), `"PDD"` (a numbered Process Design Decision — a
    platform choice, not a manual requirement), or `"PLATFORM_UNCITED"` (neither). Each gate
    reason's `rule_id` is a `RULE-8D-*` id, a `PDD-8D-*` id (again a platform decision, not a
    standards citation), or `None` for `ILLEGAL_TRANSITION`, which is a pure adjacency fact.

    Parameters
    ----------
    report : dict[str, Any] | None, optional
        Whole 8D report dictionary. If None, loads the benchmark sample report.

    Returns
    -------
    dict[str, Any]
        The core `EightDValidationResult.to_dict()` payload, unmodified:
        - verdict: "ACCEPT" | "WARNING" | "REJECT" (str)
        - valid: Whether the report is advisory-clean (bool)
        - state: Current 8D state, "D0".."D8" or "CLOSED" (str)
        - closeable: Whole-report closure gate, i.e. gate_reasons is empty (bool)
        - gate_reasons: List of {code, message, rule_id} blocking reasons (list)
        - d0, d1, d2, d3, d5, d6, d7: Per-discipline result dict or None
        - d8: D8 closure result dict, never None, carrying its own closure-evidence `closeable`
        - report: The validated report as JSON-mode dict

    Raises
    ------
    TypeError
        If report is not a dict or None.
    ValueError
        If report fails 8D schema validation.
    """
    return _validate_8d(_coerce_report(report)).to_dict()


def advance_8d(
    report: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Whole 8D report dictionary to evaluate the transition against. If omitted or "
                "None, loads the benchmark sample 8D report (currently at D8, status OPEN)."
            ),
        ),
    ] = None,
    target: Annotated[
        str,
        Field(
            description=(
                "Target 8D state for the attempted transition: 'D0'-'D8' or 'CLOSED'. "
                "Required and non-empty. A non-adjacent target is a normal BLOCKED result, "
                "not an error."
            ),
        ),
    ] = "",
) -> dict[str, Any]:
    """Evaluate one hypothetical adjacent 8D transition against the supplied report.

    Deterministic FastMCP tool wrapping `quality_core.rca.eight_d.transition_eight_d`, whose
    `to_dict()` is returned verbatim with no transport-layer reshaping.

    **This server persists no report between calls.** Nothing is advanced server-side: the
    tool evaluates the transition for the report you pass in, and the would-be new report is
    returned inside `result["report"]`. The calling host is responsible for carrying that dict
    forward into its next `validate_8d` / `advance_8d` / `render_8d_canvas` call. A host that
    assumes server-side state will silently lose the advanced report. The core function itself
    is pure — it deep-copies and never mutates the report it is given.

    An illegal or non-adjacent target is **not** an error: it returns `verdict="BLOCKED"` with
    a single `ILLEGAL_TRANSITION` reason whose `rule_id` is `None`.

    Citation basis: each reason's `rule_id` is a `RULE-8D-GATE-*` id (cited to the Ford Global
    8D Manual / AIAG CQI-20 in quality_core/rca/CITATIONS.tsv), a `PDD-8D-*` id (a numbered
    Process Design Decision — a platform choice, **not** a standards requirement), or `None`
    where no citation applies. Read `rule_id` rather than the message wording to tell which.

    Parameters
    ----------
    report : dict[str, Any] | None, optional
        Whole 8D report dictionary. If None, loads the benchmark sample report.
    target : str
        Target 8D state, e.g. "CLOSED". Required and non-empty.

    Returns
    -------
    dict[str, Any]
        The core `EightDTransitionResult.to_dict()` payload, unmodified:
        - verdict: "ADVANCED" | "BLOCKED" (str)
        - previous_state: State before the attempted transition (str)
        - state: Resulting state; unchanged from previous_state when BLOCKED (str)
        - reasons: List of {code, message, rule_id} blocking reasons (list)
        - report: The resulting report as a JSON-mode dict — the host must carry this forward

    Raises
    ------
    TypeError
        If report is not a dict or None, or target is not a string.
    ValueError
        If target is empty, or report fails 8D schema validation.
    """
    if isinstance(target, bool) or not isinstance(target, str):
        raise TypeError(f"target must be a string, got {type(target).__name__}: {target!r}")
    if not target.strip():
        raise ValueError("target must not be empty.")

    return _transition_eight_d(_coerce_report(report), cast(EightDState, target)).to_dict()


def render_8d_canvas(
    report: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Whole 8D report dictionary to render. If omitted or None, loads the benchmark "
                "sample 8D report."
            ),
        ),
    ] = None,
    theme: Annotated[
        str,
        Field(description="Color theme palette: 'dark' (default) or 'light'."),
    ] = "dark",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "8D Problem Solving Canvas",
) -> dict[str, Any]:
    """Render an interactive visual HTML canvas for one 8D report.

    Deterministic FastMCP tool wrapping `quality_core.canvas.eight_d.EightDCanvas`. Renders
    D0-D8 cards plus the closure-gate panel, and returns the canvas's own
    `validate_8d(...).to_dict()` payload unmodified under `validation`.

    The two `closeable` flags stay at distinct JSON paths, exactly as the canvas keeps them
    under separate badge labels: the hoisted top-level `closeable` is the **whole-report**
    gate, and the D8 closure-evidence flag is reachable only at
    `result["validation"]["d8"]["closeable"]`. Neither is ever collapsed onto the other.

    Citation basis: findings carry `citation_basis` (`"RULE"` / `"PDD"` /
    `"PLATFORM_UNCITED"`) and gate reasons carry `rule_id` (`RULE-8D-*` / `PDD-8D-*` /
    `None`) inside `validation`. `PDD` and `PLATFORM_UNCITED` mark platform decisions and
    uncited platform heuristics respectively — not AIAG/Ford/CQI-20 requirements.

    Parameters
    ----------
    report : dict[str, Any] | None, optional
        Whole 8D report dictionary. If None, loads the benchmark sample report.
    theme : str, default "dark"
        Color theme: "dark" or "light".
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable markup.
    title : str, default "8D Problem Solving Canvas"
        Title of the 8D canvas.

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - title: The canvas title (str)
        - verdict: Whole-report verdict (str)
        - state: Current 8D state (str)
        - closeable: Whole-report closure gate (bool)
        - validation: The full `validate_8d(...).to_dict()` payload, unmodified (dict)
        - html: Rendered HTML string (str)

    Raises
    ------
    TypeError
        If report is not a dict or None, title is not a string, or standalone is not a boolean.
    ValueError
        If title is empty, theme is not 'dark'/'light', or report fails 8D schema validation.
    """
    if not isinstance(standalone, bool):
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if theme not in ("dark", "light"):
        raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

    canvas = EightDCanvas(_coerce_report(report), title=title)
    html_content = canvas.to_html(theme=theme, standalone=standalone)  # type: ignore[arg-type]
    validation = canvas.to_dict()["validation"]

    return {
        "title": canvas.title,
        "verdict": validation["verdict"],
        "state": validation["state"],
        "closeable": validation["closeable"],
        "validation": validation,
        "html": html_content,
    }

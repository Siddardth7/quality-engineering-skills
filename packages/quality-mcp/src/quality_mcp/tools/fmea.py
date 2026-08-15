"""
fmea.py
FMEA risk scoring tool for Model Context Protocol (MCP).

Exposes deterministic AIAG-VDA 2019 Action Priority and RPN calculations from
quality_core.scoring to AI agents and MCP client hosts.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field
from quality_core.scoring import action_priority, rpn


def lookup_fmea_ap(
    severity: Annotated[int, Field(strict=True, description="Severity rating (1–10 on the AIAG-VDA scale)")],
    occurrence: Annotated[int, Field(strict=True, description="Occurrence rating (1–10 on the AIAG-VDA scale)")],
    detection: Annotated[int, Field(strict=True, description="Detection rating (1–10 on the AIAG-VDA scale)")],
) -> dict[str, Any]:
    """Look up AIAG-VDA 2019 Action Priority and calculate RPN for an FMEA item.

    Pure deterministic function wrapping `quality_core.scoring.action_priority` and
    `quality_core.scoring.rpn`. Maps discrete Severity, Occurrence, and Detection
    ratings (1–10 scale) to Risk Priority Number (RPN) and Action Priority (AP) level.

    Parameters
    ----------
    severity : int
        Severity rating (1–10 on the AIAG-VDA scale).
    occurrence : int
        Occurrence rating (1–10 on the AIAG-VDA scale).
    detection : int
        Detection rating (1–10 on the AIAG-VDA scale).

    Returns
    -------
    dict[str, Any]
        Dictionary containing input ratings and calculated risk metrics:
        - ``"severity"``: The input severity score (int).
        - ``"occurrence"``: The input occurrence score (int).
        - ``"detection"``: The input detection score (int).
        - ``"rpn"``: Risk Priority Number (S × O × D) (int).
        - ``"action_priority"``: AIAG-VDA Action Priority level ("High", "Medium", or "Low") (str).

    Raises
    ------
    TypeError
        If severity, occurrence, or detection is not an integer (or is a boolean).
    ValueError
        If severity, occurrence, or detection is outside the 1–10 scale.
    """
    for name, val in (("Severity", severity), ("Occurrence", occurrence), ("Detection", detection)):
        if isinstance(val, bool) or not isinstance(val, int):
            raise TypeError(f"{name} score must be an integer, got {type(val).__name__}: {val!r}")

    rpn_val = rpn(severity, occurrence, detection)
    ap_val = action_priority(severity, occurrence, detection)

    return {
        "severity": severity,
        "occurrence": occurrence,
        "detection": detection,
        "rpn": rpn_val,
        "action_priority": ap_val,
    }

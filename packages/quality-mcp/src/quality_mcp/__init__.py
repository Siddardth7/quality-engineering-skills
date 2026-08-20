"""Quality Platform Model Context Protocol (MCP) server package.

Exposes quality-core deterministic engines to AI agents via Model Context Protocol endpoints.
"""

from __future__ import annotations

__version__ = "0.5.0"

from quality_mcp.server import (
    calculate_gage_rr,
    calculate_spc_chart,
    categorize_fishbone,
    lookup_fmea_ap,
    mcp,
    ping,
    render_5why_canvas,
    render_controlplan_canvas,
    render_fishbone_canvas,
    render_fmea_canvas,
    render_msa_canvas,
    render_spc_canvas,
    validate_5why,
    validate_control_plan,
)

__all__ = [
    "__version__",
    "calculate_gage_rr",
    "calculate_spc_chart",
    "categorize_fishbone",
    "lookup_fmea_ap",
    "mcp",
    "ping",
    "render_5why_canvas",
    "render_controlplan_canvas",
    "render_fishbone_canvas",
    "render_fmea_canvas",
    "render_msa_canvas",
    "render_spc_canvas",
    "validate_5why",
    "validate_control_plan",
]


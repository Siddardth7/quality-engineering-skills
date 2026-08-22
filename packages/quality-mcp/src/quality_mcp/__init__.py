"""Quality Platform Model Context Protocol (MCP) server package.

Exposes quality-core deterministic engines to AI agents via Model Context Protocol endpoints.
"""

from __future__ import annotations

__version__ = "0.7.0"

from quality_mcp.server import (
    calculate_gage_rr,
    calculate_spc_chart,
    categorize_fishbone,
    estimate_copq,
    lookup_fmea_ap,
    mcp,
    ping,
    recommend_disposition,
    render_5why_canvas,
    render_controlplan_canvas,
    render_copq_canvas,
    render_fishbone_canvas,
    render_fmea_canvas,
    render_is_is_not_canvas,
    render_isisnot_canvas,
    render_msa_canvas,
    render_ncr_canvas,
    render_spc_canvas,
    scope_is_is_not,
    validate_5why,
    validate_control_plan,
    write_ncr,
)

__all__ = [
    "__version__",
    "calculate_gage_rr",
    "calculate_spc_chart",
    "categorize_fishbone",
    "estimate_copq",
    "lookup_fmea_ap",
    "mcp",
    "ping",
    "recommend_disposition",
    "render_5why_canvas",
    "render_controlplan_canvas",
    "render_copq_canvas",
    "render_fishbone_canvas",
    "render_fmea_canvas",
    "render_is_is_not_canvas",
    "render_isisnot_canvas",
    "render_msa_canvas",
    "render_ncr_canvas",
    "render_spc_canvas",
    "scope_is_is_not",
    "validate_5why",
    "validate_control_plan",
    "write_ncr",
]

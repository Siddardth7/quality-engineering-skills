"""
server.py
Model Context Protocol (MCP) server for Quality Platform.

Exposes quality-core deterministic engineering engines to AI agents over standard MCP
transports using the FastMCP framework.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from quality_mcp import __version__
from quality_mcp.tools.canvas import (
    render_5why_canvas,
    render_controlplan_canvas,
    render_fishbone_canvas,
    render_fmea_canvas,
    render_is_is_not_canvas,
    render_isisnot_canvas,
    render_msa_canvas,
    render_ncr_canvas,
    render_spc_canvas,
)
from quality_mcp.tools.controlplan import validate_control_plan
from quality_mcp.tools.fmea import lookup_fmea_ap
from quality_mcp.tools.msa import calculate_gage_rr
from quality_mcp.tools.ncr import (
    recommend_disposition,
    write_ncr,
)
from quality_mcp.tools.rca import (
    categorize_fishbone,
    scope_is_is_not,
    validate_5why,
)
from quality_mcp.tools.spc import calculate_spc_chart

mcp = FastMCP("quality-mcp")

# Register tools on the FastMCP instance
mcp.tool()(lookup_fmea_ap)
mcp.tool()(render_5why_canvas)
mcp.tool()(render_controlplan_canvas)
mcp.tool()(render_fishbone_canvas)
mcp.tool()(render_fmea_canvas)
mcp.tool()(render_isisnot_canvas)
mcp.tool()(render_msa_canvas)
mcp.tool()(render_ncr_canvas)
mcp.tool()(render_spc_canvas)
mcp.tool()(calculate_spc_chart)
mcp.tool()(calculate_gage_rr)
mcp.tool()(categorize_fishbone)
mcp.tool()(scope_is_is_not)
mcp.tool()(validate_5why)
mcp.tool()(validate_control_plan)
mcp.tool()(write_ncr)
mcp.tool()(recommend_disposition)


@mcp.tool()
def ping() -> dict[str, str]:
    """Health check endpoint confirming MCP server availability and version."""
    return {
        "status": "ok",
        "server": "quality-mcp",
        "version": __version__,
    }


def main() -> None:
    """Entry point for the quality-mcp console script."""
    mcp.run()


if __name__ == "__main__":
    main()

__all__ = [
    "calculate_gage_rr",
    "calculate_spc_chart",
    "categorize_fishbone",
    "lookup_fmea_ap",
    "main",
    "mcp",
    "ping",
    "recommend_disposition",
    "render_5why_canvas",
    "render_controlplan_canvas",
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

"""Quality Platform Model Context Protocol (MCP) server package.

Exposes quality-core deterministic engines to AI agents via Model Context Protocol endpoints.
"""

from __future__ import annotations

__version__ = "0.2.0"

from quality_mcp.server import (
    calculate_spc_chart,
    lookup_fmea_ap,
    mcp,
    ping,
    render_fmea_canvas,
    render_spc_canvas,
)

__all__ = [
    "__version__",
    "calculate_spc_chart",
    "lookup_fmea_ap",
    "mcp",
    "ping",
    "render_fmea_canvas",
    "render_spc_canvas",
]

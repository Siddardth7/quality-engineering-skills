"""Quality Platform Model Context Protocol (MCP) server package.

Exposes quality-core deterministic engines to AI agents via Model Context Protocol endpoints.
"""

from __future__ import annotations

__version__ = "0.1.0"

from quality_mcp.server import lookup_fmea_ap, mcp, ping

__all__ = ["__version__", "lookup_fmea_ap", "mcp", "ping"]

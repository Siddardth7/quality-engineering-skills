"""Unit tests for quality_mcp FastMCP server and ping health check tool."""

from __future__ import annotations

import asyncio
import runpy
import warnings
from unittest.mock import patch

import quality_mcp
from quality_mcp import __version__
from quality_mcp.server import lookup_fmea_ap, main, mcp, ping, render_fmea_canvas


def test_ping_returns_correct_dict() -> None:
    """Invoke ping() and assert return value and schema match specification."""
    result = ping()
    expected = {
        "status": "ok",
        "server": "quality-mcp",
        "version": "0.2.0",
    }
    assert result == expected
    assert result["status"] == "ok"
    assert result["server"] == "quality-mcp"
    assert result["version"] == __version__
    assert isinstance(result, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in result.items())


def test_mcp_instance_configuration() -> None:
    """Verify FastMCP server instance metadata and registered tool list."""
    assert mcp.name == "quality-mcp"
    tools = asyncio.run(mcp.list_tools())
    tool_names = [tool.name for tool in tools]
    assert "ping" in tool_names
    assert "lookup_fmea_ap" in tool_names
    assert "render_fmea_canvas" in tool_names

    # Verify tool execution via FastMCP interface
    _, content = asyncio.run(mcp.call_tool("ping", {}))
    assert content == {
        "status": "ok",
        "server": "quality-mcp",
        "version": __version__,
    }

    _, ap_content = asyncio.run(
        mcp.call_tool("lookup_fmea_ap", {"severity": 10, "occurrence": 10, "detection": 10})
    )
    assert ap_content == {
        "severity": 10,
        "occurrence": 10,
        "detection": 10,
        "rpn": 1000,
        "action_priority": "High",
    }

    _, canvas_content = asyncio.run(mcp.call_tool("render_fmea_canvas", {}))
    assert canvas_content["rows_count"] == 6
    assert "summary" in canvas_content
    assert "html" in canvas_content


def test_main_invokes_mcp_run() -> None:
    """main() entry point must call mcp.run() once."""
    with patch.object(mcp, "run") as mock_run:
        main()
        mock_run.assert_called_once_with()


def test_main_dunder_execution() -> None:
    """Executing server.py as __main__ must invoke main() and run FastMCP.run()."""
    with patch("mcp.server.fastmcp.FastMCP.run") as mock_fastmcp_run:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            runpy.run_module("quality_mcp.server", run_name="__main__", alter_sys=False)
        mock_fastmcp_run.assert_called_once_with()


def test_package_exports() -> None:
    """Package root __init__.py must re-export mcp, ping, lookup_fmea_ap, render_fmea_canvas, and __version__ correctly."""
    assert quality_mcp.mcp is mcp
    assert quality_mcp.ping is ping
    assert quality_mcp.lookup_fmea_ap is lookup_fmea_ap
    assert quality_mcp.render_fmea_canvas is render_fmea_canvas
    assert quality_mcp.__version__ == "0.2.0"
    assert set(quality_mcp.__all__) == {"__version__", "lookup_fmea_ap", "mcp", "ping", "render_fmea_canvas"}
    assert sorted(quality_mcp.__all__) == ["__version__", "lookup_fmea_ap", "mcp", "ping", "render_fmea_canvas"]

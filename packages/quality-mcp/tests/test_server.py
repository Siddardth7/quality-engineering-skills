"""Unit tests for quality_mcp FastMCP server and ping health check tool."""

from __future__ import annotations

import asyncio
import runpy
import warnings
from unittest.mock import patch

import quality_mcp
from quality_mcp import __version__
from quality_mcp.server import (
    calculate_gage_rr,
    calculate_spc_chart,
    lookup_fmea_ap,
    main,
    mcp,
    ping,
    render_fmea_canvas,
    render_msa_canvas,
    render_spc_canvas,
)


def test_ping_returns_correct_dict() -> None:
    """Invoke ping() and assert return value and schema match specification."""
    result = ping()
    expected = {
        "status": "ok",
        "server": "quality-mcp",
        "version": "0.3.0",
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
    assert "render_msa_canvas" in tool_names
    assert "render_spc_canvas" in tool_names
    assert "calculate_spc_chart" in tool_names
    assert "calculate_gage_rr" in tool_names

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

    _, spc_canvas_content = asyncio.run(mcp.call_tool("render_spc_canvas", {}))
    assert spc_canvas_content["chart_type"] == "Xbar-R"
    assert spc_canvas_content["in_control"] is True
    assert "html" in spc_canvas_content

    _, msa_canvas_content = asyncio.run(mcp.call_tool("render_msa_canvas", {}))
    assert msa_canvas_content["method"] == "anova"
    assert msa_canvas_content["verdict"] == "Reject"
    assert "html" in msa_canvas_content


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
    """Package root __init__.py must re-export mcp, ping, lookup_fmea_ap, render_fmea_canvas, render_msa_canvas, render_spc_canvas, calculate_spc_chart, calculate_gage_rr, and __version__ correctly."""
    assert quality_mcp.mcp is mcp
    assert quality_mcp.ping is ping
    assert quality_mcp.lookup_fmea_ap is lookup_fmea_ap
    assert quality_mcp.render_fmea_canvas is render_fmea_canvas
    assert quality_mcp.render_msa_canvas is render_msa_canvas
    assert quality_mcp.render_spc_canvas is render_spc_canvas
    assert quality_mcp.calculate_spc_chart is calculate_spc_chart
    assert quality_mcp.calculate_gage_rr is calculate_gage_rr
    assert quality_mcp.__version__ == "0.3.0"
    assert set(quality_mcp.__all__) == {
        "__version__",
        "calculate_gage_rr",
        "calculate_spc_chart",
        "lookup_fmea_ap",
        "mcp",
        "ping",
        "render_fmea_canvas",
        "render_msa_canvas",
        "render_spc_canvas",
    }
    assert sorted(quality_mcp.__all__) == [
        "__version__",
        "calculate_gage_rr",
        "calculate_spc_chart",
        "lookup_fmea_ap",
        "mcp",
        "ping",
        "render_fmea_canvas",
        "render_msa_canvas",
        "render_spc_canvas",
    ]

"""Unit and integration tests for quality_mcp FMEA canvas rendering tool."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import quality_mcp.tools
from mcp.shared.memory import create_connected_server_and_client_session
from quality_mcp.server import mcp
from quality_mcp.tools.canvas import render_fmea_canvas

# ---------------------------------------------------------------------------
# Direct Function Execution Tests
# ---------------------------------------------------------------------------


def test_render_fmea_canvas_default_sample() -> None:
    """Invoking render_fmea_canvas with default arguments renders reference sample canvas."""
    result = render_fmea_canvas()

    assert result["title"] == "AIAG & VDA 2019 Process FMEA Canvas"
    assert result["rows_count"] == 6
    assert isinstance(result["summary"], dict)
    assert result["summary"]["total_rows"] == 6
    assert result["summary"]["high_count"] == 2
    assert result["summary"]["medium_count"] == 2
    assert result["summary"]["low_count"] == 2
    assert result["summary"]["max_rpn"] == 480
    assert result["summary"]["ai_candidate_count"] == 1

    html_str = result["html"]
    assert "<!DOCTYPE html>" in html_str
    assert "Inverter SMT Assembly" in html_str
    assert "AIAG &amp; VDA 2019" in html_str


def test_render_fmea_canvas_custom_dataset_embedded() -> None:
    """Render custom FMEA dataset with standalone=False."""
    custom_rows = [
        {
            "id": 101,
            "process_step": "Laser Welding",
            "component": "Busbar Joint",
            "function": "High-current conduction",
            "failure_mode": "Incomplete weld penetration",
            "effect": "Localized overheating & resistance rise",
            "severity": 9,
            "cause": "Laser power drop during seam weld",
            "occurrence": 5,
            "current_control": "100% In-line pyrometer weld monitoring",
            "detection": 2,
            "ai_candidate": False,
        }
    ]

    result = render_fmea_canvas(
        dataset=custom_rows,
        title="Battery Module Welding FMEA",
        standalone=False,
    )

    assert result["title"] == "Battery Module Welding FMEA"
    assert result["rows_count"] == 1
    assert result["summary"]["total_rows"] == 1
    assert result["summary"]["high_count"] == 1
    assert result["summary"]["medium_count"] == 0
    assert result["summary"]["low_count"] == 0
    assert result["summary"]["max_rpn"] == 90

    html_str = result["html"]
    assert "<!DOCTYPE html>" not in html_str
    assert "Laser Welding" in html_str
    assert "Busbar Joint" in html_str


def test_render_fmea_canvas_empty_dataset() -> None:
    """Render canvas with empty dataset list."""
    result = render_fmea_canvas(dataset=[], title="Empty Canvas", standalone=True)
    assert result["title"] == "Empty Canvas"
    assert result["rows_count"] == 0
    assert result["summary"]["total_rows"] == 0
    assert "No FMEA items recorded in canvas." in result["html"]


@pytest.mark.parametrize(
    ("invalid_dataset", "expected_err_type", "match_str"),
    [
        ("not-a-list", TypeError, "dataset must be a list of dictionaries or None"),
        (12345, TypeError, "dataset must be a list of dictionaries or None"),
        ({"id": 1}, TypeError, "dataset must be a list of dictionaries or None"),
        ([123], TypeError, "dataset item at index 0 must be a dict"),
        ([{"id": 1, "process_step": "Step", "component": "Comp", "function": "Func", "failure_mode": "Mode", "effect": "Effect", "severity": 15, "cause": "Cause", "occurrence": 5, "current_control": "Ctrl", "detection": 5}], ValueError, "severity must be between 1 and 10"),
    ],
)
def test_render_fmea_canvas_invalid_dataset_raises(
    invalid_dataset: Any,
    expected_err_type: type[Exception],
    match_str: str,
) -> None:
    """Invalid dataset types or row entries raise appropriate errors."""
    with pytest.raises(expected_err_type, match=match_str):
        render_fmea_canvas(dataset=invalid_dataset)


@pytest.mark.parametrize(
    ("invalid_title", "expected_err_type", "match_str"),
    [
        (123, TypeError, "title must be a string"),
        (True, TypeError, "title must be a string"),
        ("   ", ValueError, "title must not be empty"),
    ],
)
def test_render_fmea_canvas_invalid_title_raises(
    invalid_title: Any,
    expected_err_type: type[Exception],
    match_str: str,
) -> None:
    """Invalid title types or blank strings raise appropriate errors."""
    with pytest.raises(expected_err_type, match=match_str):
        render_fmea_canvas(title=invalid_title)


@pytest.mark.parametrize(
    "invalid_standalone",
    ["true", 1, 0, None, [True]],
)
def test_render_fmea_canvas_invalid_standalone_raises(invalid_standalone: Any) -> None:
    """Non-bool standalone parameter raises TypeError."""
    with pytest.raises(TypeError, match="standalone must be a boolean"):
        render_fmea_canvas(standalone=invalid_standalone)


def test_tools_reexport_render_fmea_canvas() -> None:
    """quality_mcp.tools namespace re-exports render_fmea_canvas."""
    assert hasattr(quality_mcp.tools, "render_fmea_canvas")
    assert quality_mcp.tools.render_fmea_canvas is render_fmea_canvas
    assert "render_fmea_canvas" in quality_mcp.tools.__all__


# ---------------------------------------------------------------------------
# MCP In-Process Client Round-Trip Tests
# ---------------------------------------------------------------------------


def test_mcp_client_roundtrip_render_fmea_canvas() -> None:
    """Call render_fmea_canvas through in-process MCP client session."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Discover registered tools
            tools_response = await client.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]
            assert "render_fmea_canvas" in tool_names

            # 2. Call default canvas
            result = await client.call_tool("render_fmea_canvas", {})
            assert not result.isError
            assert result.structuredContent is not None
            assert result.structuredContent["rows_count"] == 6
            assert "<!DOCTYPE html>" in result.structuredContent["html"]

            # 3. Call with custom title and embedded option
            custom_result = await client.call_tool(
                "render_fmea_canvas",
                {"title": "Embedded MCP Canvas", "standalone": False},
            )
            assert not custom_result.isError
            assert custom_result.structuredContent is not None
            assert custom_result.structuredContent["title"] == "Embedded MCP Canvas"
            assert "<!DOCTYPE html>" not in custom_result.structuredContent["html"]

    asyncio.run(_run())


def test_mcp_client_roundtrip_render_fmea_canvas_error() -> None:
    """Call render_fmea_canvas with invalid data over client session produces isError response."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                "render_fmea_canvas",
                {
                    "dataset": [
                        {
                            "id": 1,
                            "process_step": "Step",
                            "component": "Comp",
                            "function": "Func",
                            "failure_mode": "Mode",
                            "effect": "Effect",
                            "severity": 99,  # out of range
                            "cause": "Cause",
                            "occurrence": 5,
                            "current_control": "Ctrl",
                            "detection": 5,
                        }
                    ]
                },
            )
            assert result.isError

    asyncio.run(_run())

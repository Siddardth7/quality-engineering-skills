"""Unit and integration tests for quality_mcp FMEA canvas rendering tool."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import quality_mcp.tools
from mcp.shared.memory import create_connected_server_and_client_session
from quality_mcp.server import mcp
from quality_mcp.tools.canvas import (
    render_fmea_canvas,
    render_msa_canvas,
    render_spc_canvas,
)

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


# ---------------------------------------------------------------------------
# render_spc_canvas Tests
# ---------------------------------------------------------------------------


def test_render_spc_canvas_default_sample() -> None:
    """Invoking render_spc_canvas with default arguments renders AIAG benchmark Xbar-R canvas."""
    result = render_spc_canvas()

    assert result["title"] == "AIAG SPC Control Chart Canvas"
    assert result["chart_type"] == "Xbar-R"
    assert result["in_control"] is True
    assert result["stable"] is True
    assert result["violations_count"] == 0
    assert result["violations"] == []
    assert result["capability"] is not None
    assert result["capability"]["cp"] > 1.0

    html_str = result["html"]
    assert "<!DOCTYPE html>" in html_str
    assert "AIAG SPC 4th Edition" in html_str
    assert "Primary Control Chart View" in html_str
    assert "<svg" in html_str
    assert "IN CONTROL" in html_str


def test_render_spc_canvas_custom_dataset_embedded() -> None:
    """Render custom I-MR dataset with standalone=False and spec limits."""
    data = [10.0, 10.1, 9.9, 10.2, 9.8, 10.0]
    result = render_spc_canvas(
        chart_type="I-MR",
        data=data,
        usl=11.0,
        lsl=9.0,
        title="Custom Coating Thickness",
        standalone=False,
    )

    assert result["title"] == "Custom Coating Thickness"
    assert result["chart_type"] == "I-MR"
    assert result["in_control"] is True
    assert result["capability"] is not None

    html_str = result["html"]
    assert "<!DOCTYPE html>" not in html_str
    assert "Custom Coating Thickness" in html_str
    assert "<svg" in html_str


def test_render_spc_canvas_out_of_control_stability_gate() -> None:
    """Render out-of-control dataset with capability suppressed and stability notice rendered."""
    ooc_data = [
        [10.0, 10.1, 9.9, 10.0, 10.1],
        [10.0, 10.0, 10.1, 9.9, 10.0],
        [10.1, 9.9, 10.0, 10.1, 10.0],
        [10.0, 10.1, 10.0, 9.9, 10.0],
        [10.0, 10.0, 10.0, 10.1, 10.0],
        [15.0, 15.0, 15.0, 15.0, 15.0],  # Outlier
    ]
    result = render_spc_canvas(
        chart_type="Xbar-R",
        data=ooc_data,
        usl=12.0,
        lsl=8.0,
        title="Out of Control Process",
    )

    assert result["in_control"] is False
    assert result["stable"] is False
    assert result["violations_count"] > 0
    assert len(result["violations"]) > 0
    assert result["capability"] is None

    html_str = result["html"]
    assert "OUT OF CONTROL" in html_str
    assert "Stability Gate Notice" in html_str


@pytest.mark.parametrize(
    ("invalid_kwargs", "expected_err_type", "match_str"),
    [
        ({"title": ""}, ValueError, "title must not be empty"),
        ({"title": 123}, TypeError, "title must be a string"),
        ({"title": True}, TypeError, "title must be a string"),
        ({"standalone": "yes"}, TypeError, "standalone must be a boolean"),
        ({"standalone": 1}, TypeError, "standalone must be a boolean"),
        ({"chart_type": "InvalidChart"}, ValueError, "Unknown or unsupported chart_type"),
        ({"usl": 9.0, "lsl": 11.0}, ValueError, "USL cannot be less than LSL"),
    ],
)
def test_render_spc_canvas_invalid_arguments_raise(
    invalid_kwargs: dict[str, Any],
    expected_err_type: type[Exception],
    match_str: str,
) -> None:
    """Invalid arguments to render_spc_canvas raise descriptive Type/ValueError."""
    with pytest.raises(expected_err_type, match=match_str):
        render_spc_canvas(**invalid_kwargs)


def test_render_spc_canvas_package_exports() -> None:
    """render_spc_canvas is re-exported from quality_mcp and quality_mcp.tools."""
    import quality_mcp
    import quality_mcp.tools

    assert hasattr(quality_mcp, "render_spc_canvas")
    assert hasattr(quality_mcp.tools, "render_spc_canvas")
    assert "render_spc_canvas" in quality_mcp.__all__
    assert "render_spc_canvas" in quality_mcp.tools.__all__


def test_mcp_client_roundtrip_render_spc_canvas_success() -> None:
    """Call render_spc_canvas over in-process FastMCP client session successfully."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools_response = await client.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]
            assert "render_spc_canvas" in tool_names

            result = await client.call_tool("render_spc_canvas", {})
            assert not result.isError
            assert result.structuredContent is not None
            assert result.structuredContent["chart_type"] == "Xbar-R"
            assert result.structuredContent["in_control"] is True
            assert "<!DOCTYPE html>" in result.structuredContent["html"]

    asyncio.run(_run())


def test_mcp_client_roundtrip_render_spc_canvas_error() -> None:
    """Call render_spc_canvas with invalid data over client session produces isError response."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                "render_spc_canvas",
                {
                    "chart_type": "Xbar-R",
                    "data": [10.0, 10.1],  # 1D data to Xbar-R
                },
            )
            assert result.isError

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# render_msa_canvas Tests
# ---------------------------------------------------------------------------


def test_render_msa_canvas_default_sample() -> None:
    """Invoking render_msa_canvas with default arguments renders AIAG benchmark Gage R&R canvas."""
    result = render_msa_canvas()

    assert result["title"] == "AIAG MSA Gage R&R Canvas"
    assert result["method"] == "anova"
    assert result["verdict"] == "Reject"
    assert result["ndc"] == 6
    assert result["pgrr_study"] > 0
    assert result["pgrr_tolerance"] is not None
    assert result["interaction_significant"] is False
    assert isinstance(result["summary"], dict)
    assert result["summary"]["n_parts"] == 10
    assert result["summary"]["n_appraisers"] == 3
    assert result["summary"]["n_trials"] == 3

    html_str = result["html"]
    assert "<!DOCTYPE html>" in html_str
    assert "AIAG MSA 4th Edition" in html_str
    assert "Operator × Part Interaction Plot" in html_str
    assert "Variance Component Breakdown" in html_str
    assert "<svg" in html_str
    assert "REJECT" in html_str


def test_render_msa_canvas_custom_dataset_embedded() -> None:
    """Render custom dataset with standalone=False and tolerance."""
    custom_data = [
        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 2.0},
        {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 2.2},
        {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 2.5},
        {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 2.5},
        {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 4.0},
        {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 4.2},
        {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 4.5},
        {"part": "P2", "appraiser": "B", "trial": 2, "measurement": 4.5},
        {"part": "P3", "appraiser": "A", "trial": 1, "measurement": 6.0},
        {"part": "P3", "appraiser": "A", "trial": 2, "measurement": 6.2},
        {"part": "P3", "appraiser": "B", "trial": 1, "measurement": 6.5},
        {"part": "P3", "appraiser": "B", "trial": 2, "measurement": 6.5},
    ]

    result = render_msa_canvas(
        measurements=custom_data,
        method="average_and_range",
        tolerance=8.0,
        title="Custom Gage Study Canvas",
        standalone=False,
    )

    assert result["title"] == "Custom Gage Study Canvas"
    assert result["method"] == "average_and_range"
    assert result["verdict"] == "Marginal"
    assert result["ndc"] == 10
    assert result["pgrr_tolerance"] is not None

    html_str = result["html"]
    assert "<!DOCTYPE html>" not in html_str
    assert "Custom Gage Study Canvas" in html_str
    assert "MARGINAL" in html_str


@pytest.mark.parametrize(
    ("invalid_kwargs", "expected_err_type", "match_str"),
    [
        ({"title": ""}, ValueError, "title must not be empty"),
        ({"title": 123}, TypeError, "title must be a string"),
        ({"title": True}, TypeError, "title must be a string"),
        ({"standalone": "yes"}, TypeError, "standalone must be a boolean"),
        ({"standalone": 1}, TypeError, "standalone must be a boolean"),
        ({"measurements": "not-a-list"}, TypeError, "measurements must be a list"),
        ({"measurements": [123]}, TypeError, "Expected dict or MSACanvasMeasurement"),
        ({"method": "invalid_method"}, ValueError, "Unknown or unsupported method"),
        ({"tolerance": -2.0}, ValueError, "tolerance must be a positive finite float"),
    ],
)
def test_render_msa_canvas_invalid_arguments_raise(
    invalid_kwargs: dict[str, Any],
    expected_err_type: type[Exception],
    match_str: str,
) -> None:
    """Invalid arguments to render_msa_canvas raise descriptive Type/ValueError."""
    with pytest.raises(expected_err_type, match=match_str):
        render_msa_canvas(**invalid_kwargs)


def test_render_msa_canvas_package_exports() -> None:
    """render_msa_canvas is re-exported from quality_mcp and quality_mcp.tools."""
    import quality_mcp
    import quality_mcp.tools

    assert hasattr(quality_mcp, "render_msa_canvas")
    assert hasattr(quality_mcp.tools, "render_msa_canvas")
    assert "render_msa_canvas" in quality_mcp.__all__
    assert "render_msa_canvas" in quality_mcp.tools.__all__


def test_mcp_client_roundtrip_render_msa_canvas_success() -> None:
    """Call render_msa_canvas over in-process FastMCP client session successfully."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools_response = await client.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]
            assert "render_msa_canvas" in tool_names

            result = await client.call_tool("render_msa_canvas", {})
            assert not result.isError
            assert result.structuredContent is not None
            assert result.structuredContent["method"] == "anova"
            assert result.structuredContent["verdict"] == "Reject"
            assert "<!DOCTYPE html>" in result.structuredContent["html"]

    asyncio.run(_run())


def test_mcp_client_roundtrip_render_msa_canvas_error() -> None:
    """Call render_msa_canvas with invalid data over client session produces isError response."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                "render_msa_canvas",
                {
                    "measurements": [
                        {"part": "", "appraiser": "A", "trial": 1, "measurement": 10.0}
                    ],  # Empty part raises ValueError
                },
            )
            assert result.isError

    asyncio.run(_run())



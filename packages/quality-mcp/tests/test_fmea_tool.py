"""Unit and integration tests for quality_mcp FMEA Action Priority tool."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
import quality_mcp.tools
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.scoring import HIGH, LOW, MEDIUM
from quality_mcp.server import mcp
from quality_mcp.tools.fmea import lookup_fmea_ap

# --- Direct execution & AIAG-VDA worked examples ---


@pytest.mark.parametrize(
    ("severity", "occurrence", "detection", "expected_rpn", "expected_ap"),
    [
        (10, 10, 10, 1000, HIGH),  # worst case: catastrophic, frequent, undetectable
        (1, 1, 1, 1, LOW),  # best case: negligible, rare, obvious
        (9, 5, 1, 45, MEDIUM),  # S 9-10 / O 4-5 / D 1 — handbook drops this to Medium
        (9, 1, 1, 9, LOW),  # S 9-10 / O 1 / D 1 — rare + reliably detected
        (10, 1, 10, 100, LOW),  # S 9-10 / O 1 / D 7-10 — rare: Low even if undetectable
        (10, 2, 2, 40, LOW),  # high severity does not auto-escalate when rare + detectable
        (8, 7, 1, 56, MEDIUM),  # S 7-8 / O 6-7 / D 1
        (7, 8, 2, 112, HIGH),  # S 7-8 / O 8-10 / D 2-4
        (5, 10, 1, 50, MEDIUM),  # S 4-6 / O 8-10 / D 1
        (5, 5, 6, 150, LOW),  # S 4-6 / O 4-5 / D 5-6
        (4, 4, 4, 64, LOW),  # S 4-6 / O 4-5 / D 2-4
        (3, 10, 10, 300, MEDIUM),  # S 2-3 / O 8-10 / D 7-10
        (3, 6, 10, 180, LOW),  # S 2-3 / O 6-7 / D 7-10
        (1, 10, 10, 100, LOW),  # Severity 1 is always Low regardless of O and D
        (7, 5, 5, 175, MEDIUM),  # S 7-8 / O 4-5 / D 5-6
    ],
)
def test_lookup_fmea_ap_worked_examples(
    severity: int,
    occurrence: int,
    detection: int,
    expected_rpn: int,
    expected_ap: str,
) -> None:
    """Verify lookup_fmea_ap calculates standard AIAG-VDA 2019 AP and RPN."""
    result = lookup_fmea_ap(severity, occurrence, detection)
    assert result == {
        "severity": severity,
        "occurrence": occurrence,
        "detection": detection,
        "rpn": expected_rpn,
        "action_priority": expected_ap,
    }
    assert isinstance(result["severity"], int)
    assert isinstance(result["occurrence"], int)
    assert isinstance(result["detection"], int)
    assert isinstance(result["rpn"], int)
    assert isinstance(result["action_priority"], str)


def test_lookup_fmea_ap_full_cube_validity() -> None:
    """Sweep all 1,000 S/O/D combinations ensuring deterministic non-null results."""
    for s in range(1, 11):
        for o in range(1, 11):
            for d in range(1, 11):
                res = lookup_fmea_ap(s, o, d)
                assert res["severity"] == s
                assert res["occurrence"] == o
                assert res["detection"] == d
                assert res["rpn"] == s * o * d
                assert res["action_priority"] in (HIGH, MEDIUM, LOW)


# --- Negative mutation controls ---


@pytest.mark.parametrize(
    ("severity", "occurrence", "detection", "bad_param"),
    [
        (0, 5, 5, "Severity"),
        (11, 5, 5, "Severity"),
        (-1, 5, 5, "Severity"),
        (5, 0, 5, "Occurrence"),
        (5, 11, 5, "Occurrence"),
        (5, -2, 5, "Occurrence"),
        (5, 5, 0, "Detection"),
        (5, 5, 11, "Detection"),
        (5, 5, -5, "Detection"),
    ],
)
def test_lookup_fmea_ap_rejects_out_of_range_scores(
    severity: int, occurrence: int, detection: int, bad_param: str
) -> None:
    """Out-of-range integer scores must raise ValueError."""
    with pytest.raises(ValueError, match=f"{bad_param} score .* is out of range"):
        lookup_fmea_ap(severity, occurrence, detection)


@pytest.mark.parametrize(
    ("severity", "occurrence", "detection", "bad_param"),
    [
        (True, 5, 5, "Severity"),
        (False, 5, 5, "Severity"),
        (5.5, 5, 5, "Severity"),
        ("5", 5, 5, "Severity"),
        (None, 5, 5, "Severity"),
        (5, True, 5, "Occurrence"),
        (5, False, 5, "Occurrence"),
        (5, 3.2, 5, "Occurrence"),
        (5, "high", 5, "Occurrence"),
        (5, None, 5, "Occurrence"),
        (5, 5, True, "Detection"),
        (5, 5, False, "Detection"),
        (5, 5, 8.0, "Detection"),
        (5, 5, "10", "Detection"),
        (5, 5, None, "Detection"),
    ],
)
def test_lookup_fmea_ap_rejects_non_integer_types(
    severity: Any, occurrence: Any, detection: Any, bad_param: str
) -> None:
    """Non-integer (or boolean) inputs must raise TypeError."""
    with pytest.raises(TypeError, match=f"{bad_param} score must be an integer"):
        lookup_fmea_ap(severity, occurrence, detection)


# --- FastMCP Tool Registration & Metadata ---


def test_fastmcp_tool_registration() -> None:
    """Verify lookup_fmea_ap is registered in the FastMCP tool registry with valid schema."""
    tools = asyncio.run(mcp.list_tools())
    tool_map = {tool.name: tool for tool in tools}
    assert "lookup_fmea_ap" in tool_map

    tool = tool_map["lookup_fmea_ap"]
    assert tool.description is not None
    assert "Action Priority" in tool.description
    assert tool.inputSchema is not None
    assert isinstance(tool.inputSchema, dict)
    assert tool.inputSchema.get("type") == "object"

    props = tool.inputSchema.get("properties", {})
    assert "severity" in props
    assert "occurrence" in props
    assert "detection" in props
    assert props["severity"].get("type") == "integer"
    assert props["occurrence"].get("type") == "integer"
    assert props["detection"].get("type") == "integer"


def test_fastmcp_call_tool_interface() -> None:
    """Call lookup_fmea_ap via FastMCP call_tool interface directly."""
    _, content = asyncio.run(
        mcp.call_tool("lookup_fmea_ap", {"severity": 9, "occurrence": 5, "detection": 1})
    )
    assert content == {
        "severity": 9,
        "occurrence": 5,
        "detection": 1,
        "rpn": 45,
        "action_priority": "Medium",
    }


# --- In-process MCP Client Session Round-trip ---


def test_client_session_fmea_tool_discovery() -> None:
    """In-process MCP client discovers lookup_fmea_ap tool during handshake."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "quality-mcp"

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            assert "lookup_fmea_ap" in tool_names

            fmea_tool = next(t for t in tools_result.tools if t.name == "lookup_fmea_ap")
            assert fmea_tool.description is not None
            assert "AIAG-VDA" in fmea_tool.description or "Action Priority" in fmea_tool.description
            assert fmea_tool.inputSchema is not None
            assert "severity" in fmea_tool.inputSchema.get("properties", {})

    asyncio.run(_run())


def test_client_session_call_fmea_success_roundtrip() -> None:
    """In-process client calls lookup_fmea_ap and receives structured and serialized JSON responses."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            # Test worst-case safety-critical item
            res = await session.call_tool(
                "lookup_fmea_ap",
                {"severity": 10, "occurrence": 10, "detection": 10},
            )
            assert res.isError is False
            expected_payload = {
                "severity": 10,
                "occurrence": 10,
                "detection": 10,
                "rpn": 1000,
                "action_priority": "High",
            }
            assert res.structuredContent == expected_payload
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)
            assert res.content[0].type == "text"
            assert json.loads(res.content[0].text) == expected_payload

            # Test rare safety-critical item
            res_rare = await session.call_tool(
                "lookup_fmea_ap",
                {"severity": 10, "occurrence": 2, "detection": 2},
            )
            assert res_rare.isError is False
            expected_rare = {
                "severity": 10,
                "occurrence": 2,
                "detection": 2,
                "rpn": 40,
                "action_priority": "Low",
            }
            assert res_rare.structuredContent == expected_rare
            assert json.loads(res_rare.content[0].text) == expected_rare

    asyncio.run(_run())


def test_client_session_call_fmea_out_of_range_negative_control() -> None:
    """In-process client calling lookup_fmea_ap with out-of-range rating returns protocol error."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool(
                "lookup_fmea_ap",
                {"severity": 11, "occurrence": 5, "detection": 5},
            )
            assert res.isError is True
            assert res.structuredContent is None
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)
            assert "Severity score 11 is out of range" in res.content[0].text

    asyncio.run(_run())


def test_client_session_call_fmea_invalid_type_negative_control() -> None:
    """In-process client calling lookup_fmea_ap with invalid types returns protocol error."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool(
                "lookup_fmea_ap",
                {"severity": "invalid", "occurrence": 5, "detection": 5},
            )
            assert res.isError is True
            assert res.structuredContent is None
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)

    asyncio.run(_run())


# --- Tools Package Exports ---


def test_tools_package_exports() -> None:
    """quality_mcp.tools package re-exports lookup_fmea_ap, render_fmea_canvas, and calculate_spc_chart."""
    assert quality_mcp.tools.lookup_fmea_ap is lookup_fmea_ap
    assert quality_mcp.tools.render_fmea_canvas is quality_mcp.tools.render_fmea_canvas
    assert sorted(quality_mcp.tools.__all__) == ["calculate_spc_chart", "lookup_fmea_ap", "render_fmea_canvas"]

"""
In-process FastMCP client-server round-trip tests for the 8D tools (E11, #214).

Validates over the memory transport, for validate_8d / advance_8d / render_8d_canvas:
1. Tool discovery — each tool is advertised with its inputSchema properties.
2. Dual-payload parity — structuredContent == json.loads(content[0].text).
3. The four-way equality chain (structuredContent == parsed text == direct tool call ==
   core engine .to_dict()) — the schema-parity acceptance proof, never a hand dict.
4. Protocol-level error isolation — a bad call returns isError without poisoning the session.
"""

from __future__ import annotations

import asyncio
import copy
import json
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.canvas.eight_d import SAMPLE_EIGHT_D_REPORT
from quality_core.rca.eight_d import transition_eight_d as core_transition_8d
from quality_core.rca.eight_d_disciplines import validate_8d as core_validate_8d
from quality_core.rca.eight_d_schema import validate_eight_d
from quality_mcp.server import mcp
from quality_mcp.tools.eight_d import advance_8d, render_8d_canvas, validate_8d


def _linked_ncr_invalid_report() -> dict[str, Any]:
    rep = copy.deepcopy(SAMPLE_EIGHT_D_REPORT)
    rep["d3"]["linked_ncr_validation"] = {
        "is_valid": False,
        "record_count": 2,
        "findings": ["linked NCR records could not be verified"],
    }
    return rep


def _parsed(result: Any) -> dict[str, Any]:
    """structuredContent, asserted equal to the deserialized text payload."""
    assert not result.isError
    text = next(c for c in result.content if isinstance(c, TextContent))
    parsed = json.loads(text.text)
    assert result.structuredContent == parsed
    assert isinstance(parsed, dict)
    return parsed


# ---------------------------------------------------------------------------
# 1. Tool discovery
# ---------------------------------------------------------------------------


def test_eight_d_tools_discoverable() -> None:
    """All three 8D tools are advertised with their expected inputSchema properties."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()
            tools = {t.name: t for t in (await session.list_tools()).tools}
            assert {"validate_8d", "advance_8d", "render_8d_canvas"} <= set(tools)
            assert "report" in tools["validate_8d"].inputSchema.get("properties", {})
            advance_props = tools["advance_8d"].inputSchema.get("properties", {})
            assert "report" in advance_props
            assert "target" in advance_props
            canvas_props = tools["render_8d_canvas"].inputSchema.get("properties", {})
            for key in ("report", "theme", "standalone", "title"):
                assert key in canvas_props

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 2. Four-way parity
# ---------------------------------------------------------------------------


def test_validate_8d_roundtrip_parity() -> None:
    """validate_8d: structuredContent == parsed text == direct call == core to_dict()."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()
            structured = _parsed(await session.call_tool("validate_8d", arguments={}))
            assert structured == validate_8d()
            assert structured == core_validate_8d(validate_eight_d(SAMPLE_EIGHT_D_REPORT)).to_dict()

            rep = _linked_ncr_invalid_report()
            custom = _parsed(await session.call_tool("validate_8d", arguments={"report": rep}))
            assert custom == validate_8d(rep)
            assert custom["closeable"] is False
            assert custom["d8"]["closeable"] is True

    asyncio.run(_run())


def test_advance_8d_roundtrip_parity() -> None:
    """advance_8d: four-way parity for CLOSED (advance) and D2 (illegal/BLOCKED)."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()
            closed = _parsed(
                await session.call_tool("advance_8d", arguments={"target": "CLOSED"})
            )
            assert closed == advance_8d(target="CLOSED")
            assert closed == core_transition_8d(
                validate_eight_d(SAMPLE_EIGHT_D_REPORT), "CLOSED"
            ).to_dict()
            assert closed["verdict"] == "ADVANCED"

            blocked = _parsed(await session.call_tool("advance_8d", arguments={"target": "D2"}))
            assert blocked["verdict"] == "BLOCKED"
            assert blocked["reasons"][0]["code"] == "ILLEGAL_TRANSITION"
            assert blocked["reasons"][0]["rule_id"] is None

    asyncio.run(_run())


def test_render_8d_canvas_roundtrip_parity() -> None:
    """render_8d_canvas: dual-payload + direct-call parity, closeable kept distinct."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()
            payload = _parsed(await session.call_tool("render_8d_canvas", arguments={}))
            assert payload == render_8d_canvas()
            oracle = core_validate_8d(validate_eight_d(SAMPLE_EIGHT_D_REPORT)).to_dict()
            assert payload["validation"] == oracle
            assert payload["closeable"] == oracle["closeable"]

            rep = _linked_ncr_invalid_report()
            custom = _parsed(
                await session.call_tool("render_8d_canvas", arguments={"report": rep})
            )
            assert custom["closeable"] is False
            assert custom["validation"]["d8"]["closeable"] is True
            assert custom["closeable"] != custom["validation"]["d8"]["closeable"]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 3. Error isolation
# ---------------------------------------------------------------------------


def test_eight_d_error_isolation() -> None:
    """Bad calls return isError and never poison later calls in the same session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()
            baseline = _parsed(await session.call_tool("validate_8d", arguments={}))

            assert (
                await session.call_tool("validate_8d", arguments={"report": "not-a-dict"})
            ).isError
            assert (await session.call_tool("validate_8d", arguments={"report": {}})).isError
            assert (await session.call_tool("advance_8d", arguments={"target": ""})).isError
            assert (
                await session.call_tool("render_8d_canvas", arguments={"theme": "neon"})
            ).isError

            after = _parsed(await session.call_tool("validate_8d", arguments={}))
            assert after == baseline

    asyncio.run(_run())

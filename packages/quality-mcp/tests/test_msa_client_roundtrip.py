"""Integration tests proving in-process MCP client-server round-trip for calculate_gage_rr.

Validates:
1. FastMCP server initialization and calculate_gage_rr tool discovery over in-process memory transport.
2. Real-world AIAG MSA 4th Edition benchmark dataset (10x3x3 crossed study) executed through session.call_tool().
3. Dual-payload parity: structuredContent dictionary vs JSON-deserialized content[0].text.
4. Exact numerical parity with direct quality_core.msa computations for ANOVA and Average-and-Range methods.
5. Verification against extracted MSA test fixture (Table A 4 / A 5 reference values).
6. Protocol-level error handling: empty data, single part, single appraiser, single trial,
   unbalanced datasets, invalid method names, negative tolerance, and unknown tools return isError=True.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.msa import (
    METHOD,
    METHOD_ANOVA,
    compute_gage_rr,
    load_gage_study_csv,
)
from quality_mcp.server import mcp

_AIAG_REFERENCE_STUDY_CSV = (
    Path(__file__).resolve().parents[2]
    / "quality-core"
    / "tests"
    / "data"
    / "aiag_reference_study.csv"
)

# Synthetic Example B dataset (3 parts x 2 appraisers x 2 trials)
_EXAMPLE_B_DATA: list[dict[str, Any]] = [
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


def test_mcp_client_session_handshake_and_tool_discovery() -> None:
    """In-process MCP client session initializes and discovers calculate_gage_rr with valid schema."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "quality-mcp"
            assert init_result.serverInfo.version is not None

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            assert "calculate_gage_rr" in tool_names

            msa_tool = next(t for t in tools_result.tools if t.name == "calculate_gage_rr")
            assert msa_tool.description is not None
            assert "Gage R&R" in msa_tool.description or "AIAG" in msa_tool.description
            assert msa_tool.inputSchema is not None
            properties = msa_tool.inputSchema.get("properties", {})
            assert "measurements" in properties
            assert "method" in properties
            assert "tolerance" in properties

    asyncio.run(_run())


def test_mcp_client_aiag_reference_anova_roundtrip_dual_payload_parity() -> None:
    """In-process client calls calculate_gage_rr for AIAG 10x3x3 study using ANOVA; verifies dual-payload parity and oracle match."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            df = load_gage_study_csv(str(_AIAG_REFERENCE_STUDY_CSV))
            records: list[dict[str, Any]] = df.to_dict(orient="records")

            args: dict[str, Any] = {
                "measurements": records,
                "method": METHOD_ANOVA,
                "tolerance": 4.42,
            }
            res = await session.call_tool("calculate_gage_rr", args)

            assert res.isError is False
            assert res.structuredContent is not None
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)

            # 1. Dual-payload parity: structuredContent vs serialized text
            structured = res.structuredContent
            serialized = json.loads(res.content[0].text)
            assert structured == serialized

            # 2. Compare directly with core engine calculation
            core_direct = compute_gage_rr(records, method=METHOD_ANOVA, tolerance=4.42)
            assert structured["basis"] == "AIAG MSA 4th Edition"
            assert structured["method"] == METHOD_ANOVA
            assert pytest.approx(structured["ev"]) == core_direct["ev"]
            assert pytest.approx(structured["av"]) == core_direct["av"]
            assert pytest.approx(structured["grr"]) == core_direct["grr"]
            assert pytest.approx(structured["pv"]) == core_direct["pv"]
            assert pytest.approx(structured["tv"]) == core_direct["tv"]
            assert pytest.approx(structured["pev_study"]) == core_direct["pev_study"]
            assert pytest.approx(structured["pav_study"]) == core_direct["pav_study"]
            assert pytest.approx(structured["pgrr_study"]) == core_direct["pgrr_study"]
            assert pytest.approx(structured["ppv_study"]) == core_direct["ppv_study"]
            assert pytest.approx(structured["pgrr_tolerance"]) == core_direct["pgrr_tolerance"]
            assert structured["ndc"] == core_direct["ndc"]
            assert structured["verdict"] == core_direct["verdict"]
            assert structured["interaction"] == core_direct["interaction"]
            assert structured["interaction_significant"] == core_direct["interaction_significant"]
            assert pytest.approx(structured["interaction_f"]) == core_direct["interaction_f"]

            # 3. AIAG published Table A 4 / A 5 reference oracle values
            assert structured["ev"] == pytest.approx(0.199933, rel=2e-4)
            assert structured["av"] == pytest.approx(0.226838, rel=2e-4)
            assert structured["grr"] == pytest.approx(0.302373, rel=2e-4)
            assert structured["pv"] == pytest.approx(1.042327, rel=2e-4)
            assert structured["tv"] == pytest.approx(1.085, abs=1e-3)
            assert structured["interaction_f"] == pytest.approx(0.434, abs=1e-3)
            assert structured["interaction_significant"] is False
            assert structured["interaction"] == 0.0
            assert structured["ndc"] == 4
            assert structured["verdict"] == "Reject"

    asyncio.run(_run())


def test_mcp_client_average_and_range_roundtrip_dual_payload_parity() -> None:
    """In-process client calls calculate_gage_rr for Example B with Average-and-Range; verifies dual-payload parity and direct engine match."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            args: dict[str, Any] = {
                "measurements": _EXAMPLE_B_DATA,
                "method": METHOD,
                "tolerance": 8.0,
            }
            res = await session.call_tool("calculate_gage_rr", args)

            assert res.isError is False
            assert res.structuredContent is not None
            structured = res.structuredContent
            serialized = json.loads(res.content[0].text)
            assert structured == serialized

            core_direct = compute_gage_rr(_EXAMPLE_B_DATA, method=METHOD, tolerance=8.0)
            assert structured["basis"] == "AIAG MSA 4th Edition"
            assert structured["method"] == METHOD
            assert pytest.approx(structured["ev"]) == core_direct["ev"]
            assert pytest.approx(structured["av"]) == core_direct["av"]
            assert pytest.approx(structured["grr"]) == core_direct["grr"]
            assert pytest.approx(structured["pv"]) == core_direct["pv"]
            assert pytest.approx(structured["tv"]) == core_direct["tv"]
            assert pytest.approx(structured["pgrr_study"]) == core_direct["pgrr_study"]
            assert pytest.approx(structured["pgrr_tolerance"]) == core_direct["pgrr_tolerance"]
            assert structured["ndc"] == core_direct["ndc"]
            assert structured["verdict"] == core_direct["verdict"]
            assert structured["interaction"] is None
            assert structured["interaction_f"] is None
            assert structured["interaction_significant"] is None

    asyncio.run(_run())


def test_mcp_client_validation_error_empty_measurements() -> None:
    """Empty measurements list over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool("calculate_gage_rr", {"measurements": []})
            assert res.isError is True
            assert len(res.content) == 1
            assert "at least one measurement" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_validation_error_single_part() -> None:
    """Fewer than 2 parts over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            data = [
                {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
                {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.1},
                {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.0},
                {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 10.1},
            ]
            res = await session.call_tool("calculate_gage_rr", {"measurements": data})
            assert res.isError is True
            assert "at least 2 parts" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_validation_error_single_appraiser() -> None:
    """Fewer than 2 appraisers over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            data = [
                {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
                {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.1},
                {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 10.0},
                {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 10.1},
            ]
            res = await session.call_tool("calculate_gage_rr", {"measurements": data})
            assert res.isError is True
            assert "at least 2 appraisers" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_validation_error_single_trial() -> None:
    """Fewer than 2 trials over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            data = [
                {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
                {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.1},
                {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 10.0},
                {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 10.1},
            ]
            res = await session.call_tool("calculate_gage_rr", {"measurements": data})
            assert res.isError is True
            assert "at least 2 trials" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_validation_error_unbalanced_data() -> None:
    """Unbalanced trials across cells over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            data = [
                {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
                {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.1},
                {"part": "P1", "appraiser": "A", "trial": 3, "measurement": 10.2},
                {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.0},
                {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 10.1},
                {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 10.0},
                {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 10.1},
                {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 10.0},
                {"part": "P2", "appraiser": "B", "trial": 2, "measurement": 10.1},
            ]
            res = await session.call_tool("calculate_gage_rr", {"measurements": data})
            assert res.isError is True
            assert "Data is unbalanced" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_validation_error_invalid_method() -> None:
    """Unknown method name over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool(
                "calculate_gage_rr",
                {"measurements": _EXAMPLE_B_DATA, "method": "unsupported_method"},
            )
            assert res.isError is True
            assert "Unknown method" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_validation_error_negative_tolerance() -> None:
    """Negative tolerance over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool(
                "calculate_gage_rr",
                {"measurements": _EXAMPLE_B_DATA, "tolerance": -2.0},
            )
            assert res.isError is True
            assert "positive finite" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_unknown_tool_error() -> None:
    """Calling nonexistent tool returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool("nonexistent_msa_tool", {})
            assert res.isError is True

    asyncio.run(_run())

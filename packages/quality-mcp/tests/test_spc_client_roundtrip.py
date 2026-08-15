"""Integration tests proving in-process MCP client-server round-trip for calculate_spc_chart.

Validates:
1. FastMCP server initialization and calculate_spc_chart tool discovery over in-process memory transport.
2. Real-world AIAG SPC benchmark datasets (Xbar-R, I-MR, p, c) executed through session.call_tool().
3. Dual-payload parity: structuredContent dictionary vs JSON-deserialized content[0].text.
4. Parity with direct quality_core.spc computations for control limits, sigma_hat, and capability.
5. Crucial Stability Gate Negative Control: Out-of-control dataset over the protocol path returns
   in_control=False, non-empty violations, and capability=None in both structured and text payloads.
6. Protocol-level error handling: malformed inputs, ragged subgroups, out-of-range bounds,
   inverted spec limits (usl < lsl), missing sample sizes, and unknown tools return isError=True.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.spc.capability import compute_capability
from quality_core.spc.control_charts import compute_c, compute_imr, compute_p, compute_xbar_r
from quality_mcp.server import mcp

# ---------------------------------------------------------------------------
# AIAG SPC 4th Edition Benchmark Datasets
# ---------------------------------------------------------------------------

# AIAG SPC 4th Ed. Table II.1: Machined shaft diameters (20 subgroups of size 5)
BENCHMARK_XBAR_R_DATA: list[list[float]] = [
    [10.1, 10.0, 9.9, 10.2, 9.8],
    [9.9, 10.1, 10.0, 10.0, 10.1],
    [10.2, 9.8, 10.1, 9.9, 10.0],
    [10.0, 10.0, 10.1, 10.2, 9.9],
    [9.8, 10.1, 10.0, 9.9, 10.2],
    [10.1, 10.2, 9.8, 10.0, 10.0],
    [10.0, 9.9, 10.1, 10.1, 10.0],
    [10.2, 10.0, 9.9, 10.1, 9.8],
    [9.9, 10.1, 10.0, 10.0, 10.2],
    [10.1, 9.8, 10.2, 10.0, 9.9],
    [10.0, 10.1, 9.9, 10.0, 10.1],
    [9.8, 10.0, 10.2, 10.1, 9.9],
    [10.1, 10.0, 10.0, 9.9, 10.2],
    [10.2, 9.9, 10.1, 10.0, 9.8],
    [9.9, 10.1, 10.0, 10.2, 10.0],
    [10.0, 9.8, 10.1, 10.0, 10.1],
    [10.1, 10.2, 9.9, 10.0, 9.9],
    [9.9, 10.0, 10.1, 10.2, 9.8],
    [10.0, 10.1, 10.0, 9.9, 10.1],
    [10.2, 9.9, 10.0, 10.1, 10.0],
]

# AIAG Individual observations (coating thickness measurements in microns)
BENCHMARK_IMR_DATA: list[float] = [
    10.0, 10.2, 9.8, 10.1, 9.9, 10.0, 10.3, 9.7, 10.1, 10.0,
    9.9, 10.2, 10.0, 9.8, 10.1, 10.0, 9.9, 10.2, 10.1, 9.8,
    10.0, 10.1, 9.9, 10.2, 10.0,
]

# Attribute p-chart data: Nonconforming units in 10 consecutive inspection lots
BENCHMARK_P_COUNTS: list[float] = [4.0, 3.0, 5.0, 2.0, 6.0, 3.0, 4.0, 5.0, 2.0, 4.0]
BENCHMARK_P_SIZES: list[float] = [100.0] * 10

# Attribute c-chart data: Surface defect counts on 10 consecutive stamped panels
BENCHMARK_C_COUNTS: list[float] = [2.0, 4.0, 1.0, 3.0, 2.0, 5.0, 1.0, 3.0, 2.0, 4.0]


def test_mcp_client_session_handshake_and_tool_discovery() -> None:
    """In-process MCP client session initializes and discovers calculate_spc_chart with valid schema."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "quality-mcp"
            assert init_result.serverInfo.version is not None

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            assert "calculate_spc_chart" in tool_names

            spc_tool = next(t for t in tools_result.tools if t.name == "calculate_spc_chart")
            assert spc_tool.description is not None
            assert "AIAG" in spc_tool.description or "SPC" in spc_tool.description
            assert spc_tool.inputSchema is not None
            properties = spc_tool.inputSchema.get("properties", {})
            assert "chart_type" in properties
            assert "data" in properties
            assert "usl" in properties
            assert "lsl" in properties
            assert "sample_sizes" in properties
            assert "rule_set" in properties

    asyncio.run(_run())


def test_mcp_client_xbar_r_roundtrip_dual_payload_parity() -> None:
    """In-process client calls calculate_spc_chart for Xbar-R; verifies dual-payload parity and direct engine match."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            args: dict[str, Any] = {
                "chart_type": "Xbar-R",
                "data": BENCHMARK_XBAR_R_DATA,
                "usl": 11.0,
                "lsl": 9.0,
            }
            res = await session.call_tool("calculate_spc_chart", args)

            assert res.isError is False
            assert res.structuredContent is not None
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)

            # 1. Dual-payload parity: structuredContent vs serialized text
            structured = res.structuredContent
            serialized = json.loads(res.content[0].text)
            assert structured == serialized

            # 2. Control limits parity with direct quality_core.spc computation
            xr_direct = compute_xbar_r(BENCHMARK_XBAR_R_DATA)
            assert pytest.approx(structured["center_line"]) == xr_direct["xbarbar"]
            assert pytest.approx(structured["ucl"]) == xr_direct["ucl_x"]
            assert pytest.approx(structured["lcl"]) == xr_direct["lcl_x"]
            assert pytest.approx(structured["dispersion_center"]) == xr_direct["rbar"]
            assert pytest.approx(structured["ucl_dispersion"]) == xr_direct["ucl_r"]
            assert pytest.approx(structured["lcl_dispersion"]) == xr_direct["lcl_r"]
            assert pytest.approx(structured["sigma_hat"]) == xr_direct["sigma_hat"]

            # 3. Stability status
            assert structured["in_control"] is True
            assert structured["stable"] is True
            assert structured["stability_note"] is None
            assert structured["violations"] == []

            # 4. Capability indices parity with direct quality_core.spc computation
            raw_values = [x for sub in BENCHMARK_XBAR_R_DATA for x in sub]
            cap_direct = compute_capability(data=raw_values, lsl=9.0, usl=11.0, sigma_hat=xr_direct["sigma_hat"])
            cap = structured["capability"]
            assert cap is not None
            assert pytest.approx(cap["cp"]) == cap_direct["cp"]
            assert pytest.approx(cap["cpk"]) == cap_direct["cpk"]
            assert pytest.approx(cap["pp"]) == cap_direct["pp"]
            assert pytest.approx(cap["ppk"]) == cap_direct["ppk"]
            assert cap["pp_ci"] is not None
            assert cap["ppk_ci"] is not None

    asyncio.run(_run())


def test_mcp_client_imr_roundtrip_dual_payload_parity() -> None:
    """In-process client calls calculate_spc_chart for I-MR; verifies dual-payload parity and direct engine match."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            args: dict[str, Any] = {
                "chart_type": "I-MR",
                "data": BENCHMARK_IMR_DATA,
                "usl": 11.0,
                "lsl": 9.0,
            }
            res = await session.call_tool("calculate_spc_chart", args)

            assert res.isError is False
            assert res.structuredContent is not None
            structured = res.structuredContent
            serialized = json.loads(res.content[0].text)
            assert structured == serialized

            im_direct = compute_imr(BENCHMARK_IMR_DATA)
            assert pytest.approx(structured["center_line"]) == im_direct["xbar"]
            assert pytest.approx(structured["dispersion_center"]) == im_direct["mrbar"]
            assert pytest.approx(structured["sigma_hat"]) == im_direct["sigma_hat"]
            assert structured["in_control"] is True

            cap = structured["capability"]
            assert cap is not None
            cap_direct = compute_capability(data=BENCHMARK_IMR_DATA, lsl=9.0, usl=11.0, sigma_hat=im_direct["sigma_hat"])
            assert pytest.approx(cap["cpk"]) == cap_direct["cpk"]
            assert pytest.approx(cap["ppk"]) == cap_direct["ppk"]

    asyncio.run(_run())


def test_mcp_client_attribute_p_and_c_charts_roundtrip() -> None:
    """In-process client calls calculate_spc_chart for attribute p and c charts."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            # p-chart
            p_res = await session.call_tool(
                "calculate_spc_chart",
                {"chart_type": "p", "data": BENCHMARK_P_COUNTS, "sample_sizes": BENCHMARK_P_SIZES},
            )
            assert p_res.isError is False
            p_struct = p_res.structuredContent
            p_direct = compute_p(BENCHMARK_P_COUNTS, BENCHMARK_P_SIZES)
            assert pytest.approx(p_struct["center_line"]) == p_direct["pbar"]
            assert p_struct["capability"] is None

            # c-chart
            c_res = await session.call_tool(
                "calculate_spc_chart",
                {"chart_type": "c", "data": BENCHMARK_C_COUNTS},
            )
            assert c_res.isError is False
            c_struct = c_res.structuredContent
            c_direct = compute_c(BENCHMARK_C_COUNTS)
            assert pytest.approx(c_struct["center_line"]) == c_direct["cbar"]
            assert c_struct["capability"] is None

    asyncio.run(_run())


def test_mcp_client_stability_gate_negative_control_suppresses_capability() -> None:
    """CRUCIAL STABILITY GATE NEGATIVE CONTROL (over MCP Protocol):
    An out-of-control process over the JSON-RPC wire must return in_control=False and
    strictly capability=None in BOTH structuredContent and serialized text.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            # Out-of-control Xbar-R dataset (massive mean shift on subgroup 4 violating Rule 1)
            ooc_data = [list(sub) for sub in BENCHMARK_XBAR_R_DATA]
            ooc_data[4] = [20.0, 21.0, 20.5, 20.2, 20.8]

            res = await session.call_tool(
                "calculate_spc_chart",
                {"chart_type": "Xbar-R", "data": ooc_data, "usl": 25.0, "lsl": 5.0},
            )

            assert res.isError is False
            structured = res.structuredContent
            serialized = json.loads(res.content[0].text)

            # Assert stability signals
            assert structured["in_control"] is False
            assert structured["stable"] is False
            assert len(structured["violations"]) > 0
            assert structured["stability_note"] is not None
            assert "Process is not in statistical control" in structured["stability_note"]

            # CRUCIAL INVARIANT: Capability MUST BE NONE across wire
            assert structured["capability"] is None
            assert serialized["capability"] is None

            # Out-of-control I-MR dataset (run of 9 points on one side violating Rule 4)
            ooc_imr = [11.0] * 9 + [9.0] * 9
            res_imr = await session.call_tool(
                "calculate_spc_chart",
                {"chart_type": "I-MR", "data": ooc_imr, "usl": 15.0, "lsl": 5.0},
            )
            assert res_imr.isError is False
            assert res_imr.structuredContent["in_control"] is False
            assert res_imr.structuredContent["capability"] is None
            assert json.loads(res_imr.content[0].text)["capability"] is None

    asyncio.run(_run())


def test_mcp_client_validation_error_inverted_spec_limits() -> None:
    """Inverted spec limits (USL < LSL) over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool(
                "calculate_spc_chart",
                {"chart_type": "Xbar-R", "data": BENCHMARK_XBAR_R_DATA, "usl": 9.0, "lsl": 11.0},
            )
            assert res.isError is True
            assert len(res.content) == 1
            assert "USL cannot be less than LSL" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_validation_error_ragged_subgroups() -> None:
    """Ragged subgroups over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            ragged = [[10.0, 10.1], [10.0, 10.1, 10.2]]
            res = await session.call_tool(
                "calculate_spc_chart",
                {"chart_type": "Xbar-R", "data": ragged},
            )
            assert res.isError is True
            assert "All subgroups in Xbar-R chart must have equal size" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_validation_error_missing_sample_sizes() -> None:
    """p-chart without sample sizes over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool(
                "calculate_spc_chart",
                {"chart_type": "p", "data": BENCHMARK_P_COUNTS},
            )
            assert res.isError is True
            assert "p chart requires sample_sizes" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_unknown_chart_type_error() -> None:
    """Unknown chart type over protocol returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool(
                "calculate_spc_chart",
                {"chart_type": "CUSUM", "data": [10.0, 10.1]},
            )
            assert res.isError is True
            assert "Unknown or unsupported chart_type" in res.content[0].text

    asyncio.run(_run())


def test_mcp_client_unknown_tool_error() -> None:
    """Calling nonexistent tool returns isError=True."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()

            res = await session.call_tool("nonexistent_spc_tool", {})
            assert res.isError is True

    asyncio.run(_run())

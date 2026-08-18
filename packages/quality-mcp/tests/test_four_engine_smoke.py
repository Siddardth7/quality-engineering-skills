"""
Integration smoke test exercising all 4 wrapped quality engineering engines through one FastMCP client session.

Checkpoint validation for Milestone 5 (v0.5.0):
1. FMEA Engine: lookup_fmea_ap (AIAG-VDA 2019 Action Priority & RPN scoring).
2. SPC Engine: calculate_spc_chart (AIAG SPC 4th Edition control charts, Western Electric rules, capability).
3. MSA Engine: calculate_gage_rr (AIAG MSA 4th Edition crossed Gage R&R ANOVA & Average-and-Range).
4. Control Plan Engine: validate_control_plan (AIAG Control Plan schema validation & PFMEA linkage).

Proves that all four domain engines coexist on a single FastMCP server instance, can be discovered
and executed sequentially across a single client session without crosstalk, and maintain independent
error isolation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session
from quality_mcp.server import mcp

# Test fixtures for 4-engine smoke testing
_SPC_OBSERVATIONS = [
    [10.1, 10.0, 9.9, 10.2, 9.8],
    [9.9, 10.1, 10.0, 10.0, 10.1],
    [10.2, 9.8, 10.1, 9.9, 10.0],
    [10.0, 10.0, 10.1, 10.2, 9.9],
]

_MSA_MEASUREMENTS: list[dict[str, Any]] = [
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

_CONTROL_PLAN_ROWS: list[dict[str, Any]] = [
    {
        "characteristic": "Shaft Outer Diameter",
        "measurement_method": "Laser micrometer",
        "sample_size": 5,
        "frequency": "per hour",
        "reaction_plan": "Segregate nonconforming parts; adjust grinding offset.",
        "lsl": 9.80,
        "usl": 10.20,
        "target": 10.00,
        "recommended_chart": "Xbar-R",
        "source_cause_id": "F1::F1-M1::F1-M1-C1",
    }
]

_FMEA_ROWS: list[dict[str, Any]] = [
    {
        "ID": 1,
        "Process_Step": "Grinding",
        "Component": "Drive Shaft",
        "Function": "Transmit torque",
        "Failure_Mode": "Shaft Outer Diameter",
        "Effect": "Bearing assembly interference",
        "Severity": 8,
        "Cause": "Grinding wheel wear",
        "Occurrence": 4,
        "Current_Control": "Laser micrometer",
        "Detection": 3,
    }
]


def test_four_engines_end_to_end_single_mcp_session() -> None:
    """Execute all four quality engineering tools (FMEA, SPC, MSA, Control Plan) sequentially within one MCP session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            init_res = await session.initialize()
            assert init_res.serverInfo.name == "quality-mcp"

            # 1. Discover all four tools
            tools_res = await session.list_tools()
            tool_names = {t.name for t in tools_res.tools}
            expected_tools = {
                "lookup_fmea_ap",
                "calculate_spc_chart",
                "calculate_gage_rr",
                "validate_control_plan",
            }
            assert expected_tools.issubset(tool_names)

            # 2. Engine 1: FMEA Action Priority Lookup
            fmea_res = await session.call_tool(
                "lookup_fmea_ap",
                arguments={"severity": 9, "occurrence": 4, "detection": 3},
            )
            assert not fmea_res.isError
            fmea_data = fmea_res.structuredContent
            assert fmea_data["severity"] == 9
            assert fmea_data["occurrence"] == 4
            assert fmea_data["detection"] == 3
            assert fmea_data["rpn"] == 108
            assert fmea_data["action_priority"] == "High"

            # 3. Engine 2: Statistical Process Control (SPC)
            spc_res = await session.call_tool(
                "calculate_spc_chart",
                arguments={
                    "chart_type": "Xbar-R",
                    "data": _SPC_OBSERVATIONS,
                    "usl": 11.0,
                    "lsl": 9.0,
                },
            )
            assert not spc_res.isError
            spc_data = spc_res.structuredContent
            assert spc_data["basis"] == "AIAG SPC 4th Edition"
            assert spc_data["chart_type"] == "Xbar-R"
            assert spc_data["in_control"] is True
            assert spc_data["capability"] is not None
            assert spc_data["capability"]["cpk"] > 1.33

            # 4. Engine 3: Measurement Systems Analysis (MSA)
            msa_res = await session.call_tool(
                "calculate_gage_rr",
                arguments={
                    "measurements": _MSA_MEASUREMENTS,
                    "method": "anova",
                    "tolerance": 8.0,
                },
            )
            assert not msa_res.isError
            msa_data = msa_res.structuredContent
            assert msa_data["basis"] == "AIAG MSA 4th Edition"
            assert msa_data["method"] == "anova"
            assert msa_data["ndc"] == 9
            assert msa_data["verdict"] == "Marginal"

            # 5. Engine 4: Control Plan & PFMEA Linkage
            cp_res = await session.call_tool(
                "validate_control_plan",
                arguments={
                    "plan": _CONTROL_PLAN_ROWS,
                    "fmea": _FMEA_ROWS,
                },
            )
            assert not cp_res.isError
            cp_data = cp_res.structuredContent
            assert cp_data["basis"] == "AIAG Control Plan"
            assert cp_data["valid"] is True
            assert cp_data["schema_valid"] is True
            assert cp_data["linkage_checked"] is True
            assert cp_data["linkage_valid"] is True
            assert cp_data["linked_rows"] == 1
            assert cp_data["orphan_characteristics"] == []

    asyncio.run(_run())


def test_four_engines_error_isolation_single_session() -> None:
    """An error in one tool does not affect subsequent executions of other tools in the same session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Trigger error in FMEA (out of range score)
            bad_fmea = await session.call_tool(
                "lookup_fmea_ap",
                arguments={"severity": 15, "occurrence": 5, "detection": 5},
            )
            assert bad_fmea.isError is True

            # 2. Subsequent SPC call remains healthy
            spc_res = await session.call_tool(
                "calculate_spc_chart",
                arguments={
                    "chart_type": "Xbar-R",
                    "data": _SPC_OBSERVATIONS,
                    "usl": 11.0,
                    "lsl": 9.0,
                },
            )
            assert not spc_res.isError
            assert spc_res.structuredContent["in_control"] is True

            # 3. Trigger error in MSA (unbalanced measurements)
            bad_msa = await session.call_tool(
                "calculate_gage_rr",
                arguments={
                    "measurements": [
                        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 2.0},
                        {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 2.5},
                        {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 2.5},
                    ]
                },
            )
            assert bad_msa.isError is True

            # 4. Subsequent Control Plan call remains healthy
            cp_res = await session.call_tool(
                "validate_control_plan",
                arguments={"plan": _CONTROL_PLAN_ROWS},
            )
            assert not cp_res.isError
            assert cp_res.structuredContent["valid"] is True

    asyncio.run(_run())

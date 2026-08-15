"""Integration tests proving in-process MCP client-server round-trip for FMEA Action Priority.

Validates session initialization, tool discovery, real-world automotive DFMEA/PFMEA
dataset round-trip execution across 12 diverse failure modes spanning High, Medium,
and Low Action Priority (AP), dual structuredContent and serialized text content parity
against quality_core.scoring, and protocol-level negative controls for out-of-range
scores, invalid types, and unknown tools.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.scoring import HIGH, LOW, MEDIUM, action_priority, rpn
from quality_mcp.server import mcp

# ---------------------------------------------------------------------------
# Real-World Automotive DFMEA/PFMEA Benchmark Dataset (12 Diverse Failure Modes)
# ---------------------------------------------------------------------------

AUTOMOTIVE_FMEA_BENCHMARK_DATASET: list[dict[str, Any]] = [
    {
        "id": "DFMEA-INV-001",
        "subsystem": "Traction Inverter",
        "item": "Inverter gate driver desaturation protection circuit",
        "failure_mode": "Gate driver desaturation during high-torque acceleration",
        "severity": 10,
        "occurrence": 4,
        "detection": 4,
        "expected_ap": HIGH,
    },
    {
        "id": "DFMEA-BBW-002",
        "subsystem": "Brake-by-Wire",
        "item": "Hydraulic pressure transducer",
        "failure_mode": "Brake-by-wire pressure transducer calibration drift",
        "severity": 9,
        "occurrence": 5,
        "detection": 1,
        "expected_ap": MEDIUM,
    },
    {
        "id": "PFMEA-BAT-003",
        "subsystem": "High Voltage Battery",
        "item": "Pouch cell stacking process",
        "failure_mode": "Li-ion pouch cell separator puncture from foreign particulate",
        "severity": 10,
        "occurrence": 6,
        "detection": 8,
        "expected_ap": HIGH,
    },
    {
        "id": "DFMEA-SAS-004",
        "subsystem": "Steering System",
        "item": "Steering angle optical encoder",
        "failure_mode": "Steering angle sensor CAN bus frame drop",
        "severity": 8,
        "occurrence": 3,
        "detection": 2,
        "expected_ap": LOW,
    },
    {
        "id": "PFMEA-MOT-005",
        "subsystem": "Traction Motor",
        "item": "Stator hairpin winding varnish impregnation",
        "failure_mode": "Traction motor stator insulation dielectric breakdown",
        "severity": 8,
        "occurrence": 7,
        "detection": 1,
        "expected_ap": MEDIUM,
    },
    {
        "id": "DFMEA-GBX-006",
        "subsystem": "Reduction Gearbox",
        "item": "Output shaft rotary lip seal",
        "failure_mode": "Gearbox oil seal extrusion under thermal cycling",
        "severity": 6,
        "occurrence": 4,
        "detection": 3,
        "expected_ap": LOW,
    },
    {
        "id": "DFMEA-HVC-007",
        "subsystem": "High Voltage Distribution",
        "item": "Main positive/negative contactor contacts",
        "failure_mode": "HV contactor contact welding under short-circuit fault",
        "severity": 9,
        "occurrence": 2,
        "detection": 3,
        "expected_ap": LOW,
    },
    {
        "id": "DFMEA-BMS-008",
        "subsystem": "Battery Management System",
        "item": "Passive cell balancing circuit",
        "failure_mode": "BMS passive balancing shunt resistor thermal fatigue",
        "severity": 7,
        "occurrence": 5,
        "detection": 5,
        "expected_ap": MEDIUM,
    },
    {
        "id": "PFMEA-EPS-009",
        "subsystem": "Electric Power Steering",
        "item": "Torque sensor PCB soldering",
        "failure_mode": "Steering torque sensor PCB solder joint fatigue crack",
        "severity": 8,
        "occurrence": 8,
        "detection": 4,
        "expected_ap": HIGH,
    },
    {
        "id": "DFMEA-EAX-010",
        "subsystem": "E-Axle Planetary Gearset",
        "item": "Planetary carrier needle bearings",
        "failure_mode": "Planetary carrier needle bearing cage fatigue fracture",
        "severity": 7,
        "occurrence": 8,
        "detection": 2,
        "expected_ap": HIGH,
    },
    {
        "id": "DFMEA-OBC-011",
        "subsystem": "On-Board Charger",
        "item": "DC link filtering capacitor",
        "failure_mode": "OBC DC bus capacitor dielectric degradation",
        "severity": 5,
        "occurrence": 8,
        "detection": 2,
        "expected_ap": MEDIUM,
    },
    {
        "id": "PFMEA-THM-012",
        "subsystem": "Thermal Management System",
        "item": "Electric coolant pump assembly",
        "failure_mode": "Coolant pump impeller cavitation erosion under high flow",
        "severity": 4,
        "occurrence": 4,
        "detection": 4,
        "expected_ap": LOW,
    },
]


# ---------------------------------------------------------------------------
# Handshake & Tool Discovery
# ---------------------------------------------------------------------------


def test_client_session_handshake_and_fmea_discovery() -> None:
    """In-process client initializes session and discovers registered lookup_fmea_ap tool."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "quality-mcp"

            tools_result = await session.list_tools()
            tool_names = [tool.name for tool in tools_result.tools]
            assert "lookup_fmea_ap" in tool_names

            fmea_tool = next(t for t in tools_result.tools if t.name == "lookup_fmea_ap")
            assert fmea_tool.description is not None
            assert len(fmea_tool.description) > 0
            assert "Action Priority" in fmea_tool.description or "AIAG-VDA" in fmea_tool.description
            assert fmea_tool.inputSchema is not None
            assert isinstance(fmea_tool.inputSchema, dict)
            assert fmea_tool.inputSchema.get("type") == "object"

            props = fmea_tool.inputSchema.get("properties", {})
            assert "severity" in props
            assert "occurrence" in props
            assert "detection" in props
            assert props["severity"].get("type") == "integer"
            assert props["occurrence"].get("type") == "integer"
            assert props["detection"].get("type") == "integer"

            required = fmea_tool.inputSchema.get("required", [])
            assert "severity" in required
            assert "occurrence" in required
            assert "detection" in required

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Real-World Automotive DFMEA/PFMEA Dataset Roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    AUTOMOTIVE_FMEA_BENCHMARK_DATASET,
    ids=[c["id"] for c in AUTOMOTIVE_FMEA_BENCHMARK_DATASET],
)
def test_client_session_automotive_fmea_roundtrip_dataset(case: dict[str, Any]) -> None:
    """In-process client evaluates real-world automotive failure mode and verifies dual payload parity."""
    sev = case["severity"]
    occ = case["occurrence"]
    det = case["detection"]

    # Compute expected values directly from core scoring engines
    expected_rpn = rpn(sev, occ, det)
    expected_ap = action_priority(sev, occ, det)

    assert expected_ap == case["expected_ap"]

    expected_payload = {
        "severity": sev,
        "occurrence": occ,
        "detection": det,
        "rpn": expected_rpn,
        "action_priority": expected_ap,
    }

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            res = await session.call_tool(
                "lookup_fmea_ap",
                {"severity": sev, "occurrence": occ, "detection": det},
            )

            # Protocol-level success assertions
            assert res.isError is False

            # Dual assertions: structuredContent and serialized JSON in content[0].text
            assert res.structuredContent == expected_payload
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)
            assert res.content[0].type == "text"
            assert json.loads(res.content[0].text) == expected_payload

    asyncio.run(_run())


def test_client_session_automotive_dataset_ap_distribution() -> None:
    """Verify that the benchmark dataset contains a balanced spread of High, Medium, and Low AP."""
    ap_counts: dict[str, int] = {HIGH: 0, MEDIUM: 0, LOW: 0}
    for item in AUTOMOTIVE_FMEA_BENCHMARK_DATASET:
        ap = action_priority(item["severity"], item["occurrence"], item["detection"])
        ap_counts[ap] += 1

    assert len(AUTOMOTIVE_FMEA_BENCHMARK_DATASET) == 12
    assert ap_counts[HIGH] > 0
    assert ap_counts[MEDIUM] > 0
    assert ap_counts[LOW] > 0
    assert ap_counts[HIGH] == 4
    assert ap_counts[MEDIUM] == 4
    assert ap_counts[LOW] == 4


# ---------------------------------------------------------------------------
# Negative Controls: Out-of-Range Integer Scores
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("severity", "occurrence", "detection", "out_of_range_field"),
    [
        (11, 5, 5, "Severity"),
        (0, 5, 5, "Severity"),
        (5, 0, 5, "Occurrence"),
        (5, 12, 5, "Occurrence"),
        (5, 5, -1, "Detection"),
        (5, 5, 15, "Detection"),
    ],
)
def test_client_session_out_of_range_scores_negative_control(
    severity: int, occurrence: int, detection: int, out_of_range_field: str
) -> None:
    """In-process client calling lookup_fmea_ap with out-of-range integer scores returns protocol error."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            res = await session.call_tool(
                "lookup_fmea_ap",
                {"severity": severity, "occurrence": occurrence, "detection": detection},
            )

            assert res.isError is True
            assert res.structuredContent is None
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)
            assert res.content[0].type == "text"
            assert f"{out_of_range_field} score" in res.content[0].text
            assert "out of range" in res.content[0].text

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Negative Controls: Invalid Types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("severity", "occurrence", "detection", "invalid_field"),
    [
        ("10", 5, 5, "Severity"),
        (5, "high", 5, "Occurrence"),
        (5, 5, "10", "Detection"),
        (True, 5, 5, "Severity"),
        (5, False, 5, "Occurrence"),
        (5, 5, True, "Detection"),
        (5.5, 5, 5, "Severity"),
        (5, 3.2, 5, "Occurrence"),
        (5, 5, 4.8, "Detection"),
        (None, 5, 5, "Severity"),
        (5, None, 5, "Occurrence"),
        (5, 5, None, "Detection"),
    ],
)
def test_client_session_invalid_types_negative_control(
    severity: Any, occurrence: Any, detection: Any, invalid_field: str
) -> None:
    """In-process client calling lookup_fmea_ap with non-integer or boolean types returns protocol error."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            res = await session.call_tool(
                "lookup_fmea_ap",
                {"severity": severity, "occurrence": occurrence, "detection": detection},
            )

            assert res.isError is True
            assert res.structuredContent is None
            assert len(res.content) >= 1
            assert isinstance(res.content[0], TextContent)
            assert res.content[0].type == "text"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Negative Controls: Unknown Tool Name
# ---------------------------------------------------------------------------


def test_client_session_unknown_tool_negative_control() -> None:
    """In-process client calling an unknown tool name returns protocol error."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            res = await session.call_tool(
                "nonexistent_fmea_tool",
                {"severity": 10, "occurrence": 10, "detection": 10},
            )

            assert res.isError is True
            assert res.structuredContent is None
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)
            assert res.content[0].type == "text"
            assert "Unknown tool: nonexistent_fmea_tool" in res.content[0].text

    asyncio.run(_run())

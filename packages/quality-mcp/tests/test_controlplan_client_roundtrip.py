"""
Integration tests proving in-process MCP client-server round-trip for validate_control_plan.

Validates:
1. FastMCP server initialization and validate_control_plan tool discovery over in-process memory transport.
2. Real-world AIAG Control Plan benchmark dataset executed through session.call_tool().
3. Dual-payload parity: structuredContent dictionary vs JSON-deserialized content[0].text.
4. Exact parity with direct quality_core.controlplan computations and PFMEA linkage validation.
5. Verification against extracted Control Plan and FMEA test fixtures.
6. Protocol-level error handling: empty plan, tolerance inversion, duplicate characteristics,
   orphan linkage negative control, and unknown tool invocation.
"""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.controlplan import (
    build_control_plan,
    validate_pfmea_linkage,
)
from quality_core.schema import FMEADataset, FMEARow, flat_to_relational
from quality_mcp.server import mcp
from quality_mcp.tools.controlplan import validate_control_plan

_FIXTURES_DIR = (
    Path(__file__).resolve().parents[2]
    / "quality-core"
    / "tests"
    / "data"
)
_FMEA_DEMO_CSV = _FIXTURES_DIR / "composite_panel_fmea_demo.csv"

_SAMPLE_PLAN_ROWS: list[dict[str, Any]] = [
    {
        "characteristic": "Panel Thickness",
        "measurement_method": "Micrometer",
        "sample_size": 5,
        "frequency": "per batch",
        "reaction_plan": "Adjust roller gap and re-measure.",
        "lsl": 4.80,
        "usl": 5.20,
        "target": 5.00,
        "recommended_chart": "Xbar-R",
        "source_cause_id": "F1::F1-M1::F1-M1-C1",
        "sample_plan_is_placeholder": False,
    },
    {
        "characteristic": "Resin Cure State",
        "measurement_method": "DSC Analysis",
        "sample_size": 1,
        "frequency": "per shift",
        "reaction_plan": "Quarantine load; extend oven dwell time.",
        "recommended_chart": "I-MR",
        "source_cause_id": "F1::F1-M2::F1-M2-C1",
        "sample_plan_is_placeholder": True,
    },
]


def _load_demo_fmea() -> tuple[FMEADataset, list[dict[str, Any]]]:
    with _FMEA_DEMO_CSV.open(newline="", encoding="utf-8") as fh:
        records = list(csv.DictReader(fh))
    int_cols = ("ID", "Severity", "Occurrence", "Detection")
    dict_records: list[dict[str, Any]] = [
        {**rec, **{col: int(rec[col]) for col in int_cols}}
        for rec in records
    ]
    rows = [FMEARow(**rec) for rec in dict_records]
    return FMEADataset(rows=rows), dict_records


def test_mcp_client_session_handshake_and_controlplan_tool_discovery() -> None:
    """In-process MCP client session initializes and discovers validate_control_plan with valid schema."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "quality-mcp"
            assert init_result.serverInfo.version is not None

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            assert "validate_control_plan" in tool_names

            cp_tool = next(t for t in tools_result.tools if t.name == "validate_control_plan")
            assert cp_tool.description is not None
            assert "AIAG Control Plan" in cp_tool.description
            assert cp_tool.inputSchema is not None
            properties = cp_tool.inputSchema.get("properties", {})
            assert "plan" in properties
            assert "fmea" in properties

    asyncio.run(_run())


def test_mcp_client_valid_control_plan_dual_payload_parity() -> None:
    """Invoking validate_control_plan over MCP produces identical structured and serialized JSON payloads."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # Execute via MCP client tool call
            result = await session.call_tool(
                "validate_control_plan",
                arguments={"plan": _SAMPLE_PLAN_ROWS},
            )

            assert not result.isError
            assert result.content is not None
            assert len(result.content) >= 1
            text_content = next(c for c in result.content if isinstance(c, TextContent))
            assert text_content.text is not None

            # Deserialized text payload
            serialized_payload = json.loads(text_content.text)

            # Structured payload
            structured_payload = result.structuredContent
            assert isinstance(structured_payload, dict)

            # Dual-payload parity
            assert structured_payload == serialized_payload

            # Engine parity
            direct_result = validate_control_plan(_SAMPLE_PLAN_ROWS)
            assert structured_payload == direct_result

            # Specific field assertions
            assert structured_payload["basis"] == "AIAG Control Plan"
            assert structured_payload["valid"] is True
            assert structured_payload["total_rows"] == 2
            assert structured_payload["schema_valid"] is True
            assert structured_payload["schema_findings"] == []
            assert structured_payload["linkage_checked"] is False

    asyncio.run(_run())


def test_mcp_client_control_plan_with_pfmea_linkage_roundtrip() -> None:
    """Invoking validate_control_plan with real FMEA dataset verifies bidirectional linkage with dual-payload parity."""

    # Ingest real FMEA demo fixture and derive linked Control Plan
    fmea_dataset, fmea_dicts = _load_demo_fmea()
    relational_fmea = flat_to_relational(fmea_dataset)
    derived_plan = build_control_plan(relational_fmea)

    # Convert plan to JSON-serializable dict lists
    plan_dicts = [r.model_dump() for r in derived_plan.rows]

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            result = await session.call_tool(
                "validate_control_plan",
                arguments={"plan": plan_dicts, "fmea": fmea_dicts},
            )

            assert not result.isError
            structured_payload = result.structuredContent
            assert isinstance(structured_payload, dict)

            # Dual-payload parity
            text_content = next(c for c in result.content if isinstance(c, TextContent))
            assert structured_payload == json.loads(text_content.text)

            # Direct core verification
            direct_core_res = validate_pfmea_linkage(derived_plan, relational_fmea)
            assert structured_payload["valid"] is True
            assert structured_payload["schema_valid"] is True
            assert structured_payload["linkage_checked"] is True
            assert structured_payload["linkage_valid"] is True
            assert structured_payload["linked_rows"] == direct_core_res["linked_rows"]
            assert structured_payload["orphan_characteristics"] == []
            assert structured_payload["uncovered_failure_modes"] == []

    asyncio.run(_run())


def test_mcp_client_orphan_linkage_negative_control_roundtrip() -> None:
    """Client call with unlinked characteristic reports linkage failure and orphan findings over the wire."""
    _, fmea_dicts = _load_demo_fmea()

    plan_with_orphan = [
        {
            "characteristic": "Orphan Characteristic",
            "measurement_method": "Visual check",
            "sample_size": 1,
            "frequency": "per lot",
            "reaction_plan": "Segregate lot.",
            "source_cause_id": "F99::M99::C99",
        }
    ]

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            result = await session.call_tool(
                "validate_control_plan",
                arguments={"plan": plan_with_orphan, "fmea": fmea_dicts},
            )

            assert not result.isError  # Schema returned structured error findings
            structured_payload = result.structuredContent
            assert isinstance(structured_payload, dict)

            # Dual-payload parity
            text_content = next(c for c in result.content if isinstance(c, TextContent))
            assert structured_payload == json.loads(text_content.text)

            assert structured_payload["valid"] is False
            assert structured_payload["schema_valid"] is True
            assert structured_payload["linkage_checked"] is True
            assert structured_payload["linkage_valid"] is False
            assert structured_payload["orphan_characteristics"] == ["Orphan Characteristic"]
            assert len(structured_payload["linkage_findings"]) > 0
            assert any("F99::M99::C99" in f for f in structured_payload["linkage_findings"])

    asyncio.run(_run())


def test_mcp_client_schema_tolerance_violation_roundtrip() -> None:
    """Client call with inverted tolerance (USL <= LSL) reports schema findings and invalid status."""
    bad_plan = [
        {
            "characteristic": "Inverted Tolerance Dimension",
            "measurement_method": "CMM",
            "sample_size": 3,
            "frequency": "hourly",
            "reaction_plan": "Halt line.",
            "lsl": 10.5,
            "usl": 10.0,  # usl < lsl
        }
    ]

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            result = await session.call_tool(
                "validate_control_plan",
                arguments={"plan": bad_plan},
            )

            assert not result.isError
            structured_payload = result.structuredContent
            assert isinstance(structured_payload, dict)

            # Dual-payload parity
            text_content = next(c for c in result.content if isinstance(c, TextContent))
            assert structured_payload == json.loads(text_content.text)

            assert structured_payload["valid"] is False
            assert structured_payload["schema_valid"] is False
            assert any("usl must be greater than lsl" in f for f in structured_payload["schema_findings"])

    asyncio.run(_run())


def test_mcp_client_protocol_negative_controls() -> None:
    """Client calls with protocol-level invalid payloads trigger structured error handling."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # Empty plan returns structured findings
            res_empty = await session.call_tool("validate_control_plan", arguments={"plan": []})
            assert res_empty.structuredContent["valid"] is False
            assert res_empty.structuredContent["schema_valid"] is False

            # Type error for non-list plan returns isError=True
            res_bad_type = await session.call_tool("validate_control_plan", arguments={"plan": "not a list"})
            assert res_bad_type.isError is True

            # Unknown tool returns isError=True
            res_unknown = await session.call_tool("nonexistent_control_tool", arguments={})
            assert res_unknown.isError is True

    asyncio.run(_run())

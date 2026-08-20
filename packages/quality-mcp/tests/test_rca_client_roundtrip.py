"""
Integration tests proving in-process MCP client-server round-trip for all six RCA FastMCP tools.

Validates:
1. FastMCP server initialization, handshake, and tool discovery for all 6 RCA tools:
   validate_5why, categorize_fishbone, scope_is_is_not, render_5why_canvas, render_fishbone_canvas, render_isisnot_canvas.
2. Real-world benchmark execution across reference datasets (Sentinel-8D Pneumatic Cylinder & Ford Global 8D bearing induction).
3. Dual-payload parity: structuredContent dictionary vs JSON-deserialized content[0].text.
4. Exact parity with direct quality_core.rca engine functions and quality_core.canvas.rca controllers.
5. Visual canvas rendering across themes (dark/light) and modes (standalone/embeddable).
6. Multi-method chained workflow execution across a single session without crosstalk or state pollution.
7. In-process session error isolation.
8. Protocol-level negative controls and error handling.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.canvas.rca import (
    SAMPLE_FISHBONE_CAUSES,
    SAMPLE_FIVE_WHY_STEPS,
    SAMPLE_IS_IS_NOT_ROWS,
    FishboneCanvas,
    FiveWhyCanvas,
    IsIsNotCanvas,
)
from quality_core.rca.fishbone import categorize_fishbone as core_categorize_fishbone
from quality_core.rca.five_why import validate_five_why_chain
from quality_core.rca.is_is_not import scope_is_is_not as core_scope_is_is_not
from quality_mcp.server import mcp
from quality_mcp.tools.rca import (
    categorize_fishbone,
    render_5why_canvas,
    render_fishbone_canvas,
    render_isisnot_canvas,
    scope_is_is_not,
    validate_5why,
)

# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

_CUSTOM_FIVE_WHY_STEPS: list[dict[str, Any]] = [
    {
        "step_number": 1,
        "why": "Why did the CNC drilling station produce out-of-spec hole positions?",
        "because": "Drill bit drifted during high-feed cycle.",
    },
    {
        "step_number": 2,
        "why": "Why did the drill bit drift during high-feed cycle?",
        "because": "Spindle collet clamping pressure was below minimum specification.",
    },
    {
        "step_number": 3,
        "why": "Why was spindle collet clamping pressure below minimum specification?",
        "because": "Pneumatic regulator diaphragm had cracked.",
    },
    {
        "step_number": 4,
        "why": "Why had the pneumatic regulator diaphragm cracked?",
        "because": "Preventive maintenance interval for pneumatic seals was exceeded.",
    },
    {
        "step_number": 5,
        "why": "Why was the preventive maintenance interval exceeded?",
        "because": "Maintenance management system lacked automated work-order generation for pneumatic components.",
    },
]

_CIRCULAR_FIVE_WHY_STEPS: list[dict[str, Any]] = [
    {"step_number": 1, "why": "Why did conveyor stop?", "because": "The drive belt jammed in the pulley."},
    {"step_number": 2, "why": "Why did drive belt jam?", "because": "The motor shaft stopped turning."},
    {"step_number": 3, "why": "Why did motor shaft stop turning?", "because": "The drive belt jammed in the pulley."},
]

_CUSTOM_FISHBONE_CAUSES: list[dict[str, Any]] = [
    {"category": "Man", "cause": "Operator skipped torque verification", "sub_category": "Training"},
    {"category": "Machine", "cause": "Spindle collet runout exceeded tolerance", "sub_category": "Tooling"},
    {"category": "Method", "cause": "Work instruction lacked step-by-step clamping check", "sub_category": "Standard Work"},
    {"category": "Material", "cause": "Raw bar stock diameter variation", "sub_category": "Incoming Quality"},
    {"category": "Measurement", "cause": "Air gage calibration expired", "sub_category": "Metrology"},
    {"category": "Environment", "cause": "Ambient temperature swing caused fixture expansion", "sub_category": "HVAC"},
]

_CUSTOM_KT_MATRIX: list[dict[str, Any]] = [
    {
        "dimension": "WHAT",
        "is_data": "Hole position deviation on Station 3",
        "is_not_data": "Hole position deviation on Stations 1, 2, or 4",
        "distinctions": "Station 3 uses high-speed pneumatic collet",
        "changes": "Collet regulator replaced 2 weeks ago",
    },
    {
        "dimension": "WHERE",
        "is_data": "Top mounting flange bore #4",
        "is_not_data": "Side flange bores #1-#3",
        "distinctions": "Bore #4 has deepest drill depth (45 mm)",
        "changes": "New carbide drill tool vendor",
    },
    {
        "dimension": "WHEN",
        "is_data": "First hour of morning shift startup",
        "is_not_data": "Mid-shift or afternoon run",
        "distinctions": "Cold hydraulic oil / low line air pressure",
        "changes": "Compressor startup cycle changed to 06:30",
    },
    {
        "dimension": "EXTENT",
        "is_data": "0.15 mm radial offset, 12 of 50 parts",
        "is_not_data": "Total scrap (>0.50 mm) or 100% defective",
        "distinctions": "Defect clusters at batch start",
        "changes": "Warm-up cycle shortened from 15 min to 5 min",
    },
]


# ---------------------------------------------------------------------------
# 1. FastMCP Client Session Handshake & Tool Discovery
# ---------------------------------------------------------------------------


def test_mcp_client_session_handshake_and_rca_tool_discovery() -> None:
    """In-process FastMCP client session initializes and discovers all six RCA tools with valid schemas."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "quality-mcp"
            assert init_result.serverInfo.version is not None

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]

            # All 6 RCA tools must be registered and discoverable
            expected_rca_tools = {
                "validate_5why",
                "categorize_fishbone",
                "scope_is_is_not",
                "render_5why_canvas",
                "render_fishbone_canvas",
                "render_isisnot_canvas",
            }
            assert expected_rca_tools.issubset(set(tool_names))

            # Validate inputSchema for validate_5why
            tool_5why = next(t for t in tools_result.tools if t.name == "validate_5why")
            assert tool_5why.description is not None
            assert "5-Why" in tool_5why.description
            assert tool_5why.inputSchema is not None
            props_5why = tool_5why.inputSchema.get("properties", {})
            assert "steps" in props_5why
            assert "problem_statement" in props_5why
            assert "root_cause" in props_5why
            assert "leg_type" in props_5why

            # Validate inputSchema for categorize_fishbone
            tool_fishbone = next(t for t in tools_result.tools if t.name == "categorize_fishbone")
            assert tool_fishbone.description is not None
            assert "6M Fishbone" in tool_fishbone.description
            assert tool_fishbone.inputSchema is not None
            props_fishbone = tool_fishbone.inputSchema.get("properties", {})
            assert "causes" in props_fishbone
            assert "effect" in props_fishbone
            assert "check_balance" in props_fishbone
            assert "balance_threshold" in props_fishbone

            # Validate inputSchema for scope_is_is_not
            tool_kt = next(t for t in tools_result.tools if t.name == "scope_is_is_not")
            assert tool_kt.description is not None
            assert "Kepner-Tregoe" in tool_kt.description
            assert tool_kt.inputSchema is not None
            props_kt = tool_kt.inputSchema.get("properties", {})
            assert "matrix" in props_kt
            assert "problem_statement" in props_kt

            # Validate inputSchema for render_5why_canvas
            tool_5why_canvas = next(t for t in tools_result.tools if t.name == "render_5why_canvas")
            assert tool_5why_canvas.inputSchema is not None
            props_5why_canvas = tool_5why_canvas.inputSchema.get("properties", {})
            assert "steps" in props_5why_canvas
            assert "theme" in props_5why_canvas
            assert "standalone" in props_5why_canvas

            # Validate inputSchema for render_fishbone_canvas
            tool_fishbone_canvas = next(t for t in tools_result.tools if t.name == "render_fishbone_canvas")
            assert tool_fishbone_canvas.inputSchema is not None
            props_fishbone_canvas = tool_fishbone_canvas.inputSchema.get("properties", {})
            assert "causes" in props_fishbone_canvas
            assert "theme" in props_fishbone_canvas
            assert "standalone" in props_fishbone_canvas

            # Validate inputSchema for render_isisnot_canvas
            tool_kt_canvas = next(t for t in tools_result.tools if t.name == "render_isisnot_canvas")
            assert tool_kt_canvas.inputSchema is not None
            props_kt_canvas = tool_kt_canvas.inputSchema.get("properties", {})
            assert "matrix" in props_kt_canvas
            assert "theme" in props_kt_canvas
            assert "standalone" in props_kt_canvas

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 2. 5-Why Client Round-Trip Dual-Payload & Direct Engine Parity
# ---------------------------------------------------------------------------


def test_mcp_client_validate_5why_roundtrip_dual_payload_parity() -> None:
    """Invoking validate_5why over MCP produces identical structured and serialized JSON payloads with exact core parity."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Default arguments (Ford Global 8D bearing induction benchmark case)
            result_default = await session.call_tool("validate_5why", arguments={})
            assert not result_default.isError
            assert result_default.content is not None
            text_content = next(c for c in result_default.content if isinstance(c, TextContent))
            assert text_content.text is not None

            # Deserialized payload vs structuredContent parity
            serialized_payload = json.loads(text_content.text)
            structured_payload = result_default.structuredContent
            assert isinstance(structured_payload, dict)
            assert structured_payload == serialized_payload

            # Direct tool function parity
            direct_result = validate_5why()
            assert structured_payload == direct_result

            # Core engine parity
            core_result = validate_five_why_chain(
                data=SAMPLE_FIVE_WHY_STEPS,
                problem_statement="Hole positions outside of tolerance on CNC drilling station",
                root_cause="The induction plan was not signed by Engineering",
                leg_type="occurrence",
            ).to_dict()
            assert structured_payload == core_result

            # Specific standards fields
            assert structured_payload["basis"] == "AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox"
            assert structured_payload["valid"] is True
            assert structured_payload["verdict"] == "ACCEPT"
            assert structured_payload["reversibility_score"] == 1.0
            assert structured_payload["total_steps"] == 5
            assert structured_payload["systemic_assessment"]["is_systemic"] is True
            assert structured_payload["leg_type"] == "occurrence"

            # 2. Custom valid 5-Why steps
            result_custom = await session.call_tool(
                "validate_5why",
                arguments={
                    "steps": _CUSTOM_FIVE_WHY_STEPS,
                    "problem_statement": "Hole position deviation on Station 3",
                    "root_cause": "Maintenance management system lacked automated work-order generation for pneumatic components",
                    "leg_type": "occurrence",
                },
            )
            assert not result_custom.isError
            custom_structured = result_custom.structuredContent
            custom_text = next(c for c in result_custom.content if isinstance(c, TextContent))
            assert custom_structured == json.loads(custom_text.text)

            direct_custom = validate_5why(
                steps=_CUSTOM_FIVE_WHY_STEPS,
                problem_statement="Hole position deviation on Station 3",
                root_cause="Maintenance management system lacked automated work-order generation for pneumatic components",
                leg_type="occurrence",
            )
            assert custom_structured == direct_custom
            assert custom_structured["valid"] is True
            assert custom_structured["verdict"] == "ACCEPT"
            assert custom_structured["total_steps"] == 5

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 3. 6M Fishbone Client Round-Trip Dual-Payload & Direct Engine Parity
# ---------------------------------------------------------------------------


def test_mcp_client_categorize_fishbone_roundtrip_dual_payload_parity() -> None:
    """Invoking categorize_fishbone over MCP produces identical structured and serialized JSON payloads with exact core parity."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Default arguments (Sentinel-8D Pneumatic Cylinder benchmark case)
            result_default = await session.call_tool("categorize_fishbone", arguments={})
            assert not result_default.isError
            assert result_default.content is not None
            text_content = next(c for c in result_default.content if isinstance(c, TextContent))
            assert text_content.text is not None

            # Dual-payload parity
            serialized_payload = json.loads(text_content.text)
            structured_payload = result_default.structuredContent
            assert isinstance(structured_payload, dict)
            assert structured_payload == serialized_payload

            # Direct tool function parity
            direct_result = categorize_fishbone()
            assert structured_payload == direct_result

            # Core engine parity
            core_result = core_categorize_fishbone(
                data=SAMPLE_FISHBONE_CAUSES,
                effect_statement="Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
                check_balance=True,
                balance_threshold=0.75,
            ).to_dict()
            assert structured_payload == core_result

            # Specific standards fields
            assert structured_payload["basis"] == "Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox"
            assert structured_payload["valid"] is True
            assert structured_payload["verdict"] == "ACCEPT"
            assert structured_payload["total_causes"] == 12
            assert structured_payload["empty_branches"] == []
            assert structured_payload["duplicate_causes"] == []

            # 2. Custom 6M causes
            result_custom = await session.call_tool(
                "categorize_fishbone",
                arguments={
                    "causes": _CUSTOM_FISHBONE_CAUSES,
                    "effect": "CNC drilling hole position deviation",
                    "check_balance": True,
                    "balance_threshold": 0.75,
                },
            )
            assert not result_custom.isError
            custom_structured = result_custom.structuredContent
            custom_text = next(c for c in result_custom.content if isinstance(c, TextContent))
            assert custom_structured == json.loads(custom_text.text)

            direct_custom = categorize_fishbone(
                causes=_CUSTOM_FISHBONE_CAUSES,
                effect="CNC drilling hole position deviation",
            )
            assert custom_structured == direct_custom
            assert custom_structured["valid"] is True
            assert custom_structured["verdict"] == "ACCEPT"
            assert custom_structured["total_causes"] == 6
            assert custom_structured["empty_branches"] == []

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4. Kepner-Tregoe Is/Is-Not Client Round-Trip Dual-Payload & Direct Engine Parity
# ---------------------------------------------------------------------------


def test_mcp_client_scope_is_is_not_roundtrip_dual_payload_parity() -> None:
    """Invoking scope_is_is_not over MCP produces identical structured and serialized JSON payloads with exact core parity."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Default arguments (Sentinel-8D benchmark dataset)
            result_default = await session.call_tool("scope_is_is_not", arguments={})
            assert not result_default.isError
            assert result_default.content is not None
            text_content = next(c for c in result_default.content if isinstance(c, TextContent))
            assert text_content.text is not None

            # Dual-payload parity
            serialized_payload = json.loads(text_content.text)
            structured_payload = result_default.structuredContent
            assert isinstance(structured_payload, dict)
            assert structured_payload == serialized_payload

            # Direct tool function parity
            direct_result = scope_is_is_not()
            assert structured_payload == direct_result

            # Core engine parity
            core_result = core_scope_is_is_not(
                data=SAMPLE_IS_IS_NOT_ROWS,
                problem_statement="Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
            ).to_dict()
            assert structured_payload == core_result

            # Specific standards fields
            assert structured_payload["basis"] == "Kepner & Tregoe (1997) / AIAG CQI-20 / Ford Global 8D"
            assert structured_payload["valid"] is True
            assert structured_payload["verdict"] == "ACCEPT"
            assert structured_payload["total_rows"] == 4
            assert structured_payload["complete_dimensions"] == ["WHAT", "WHERE", "WHEN", "EXTENT"]
            assert structured_payload["missing_dimensions"] == []
            assert len(structured_payload["candidate_causes"]) == 4

            # 2. Custom 4-dimension matrix
            result_custom = await session.call_tool(
                "scope_is_is_not",
                arguments={
                    "matrix": _CUSTOM_KT_MATRIX,
                    "problem_statement": "Hole position deviation on Station 3",
                },
            )
            assert not result_custom.isError
            custom_structured = result_custom.structuredContent
            custom_text = next(c for c in result_custom.content if isinstance(c, TextContent))
            assert custom_structured == json.loads(custom_text.text)

            direct_custom = scope_is_is_not(
                matrix=_CUSTOM_KT_MATRIX,
                problem_statement="Hole position deviation on Station 3",
            )
            assert custom_structured == direct_custom
            assert custom_structured["valid"] is True
            assert custom_structured["verdict"] == "ACCEPT"
            assert custom_structured["total_rows"] == 4
            assert len(custom_structured["candidate_causes"]) == 4

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 5. Visual Canvas Rendering Client Round-Trip
# ---------------------------------------------------------------------------


def test_mcp_client_canvas_rendering_roundtrip() -> None:
    """Execute render_5why_canvas, render_fishbone_canvas, and render_isisnot_canvas over MCP across themes and modes."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. render_5why_canvas — Default (Dark Standalone)
            res_5why_dark = await session.call_tool("render_5why_canvas", arguments={"theme": "dark", "standalone": True})
            assert not res_5why_dark.isError
            payload_5why_dark = res_5why_dark.structuredContent
            text_5why_dark = next(c for c in res_5why_dark.content if isinstance(c, TextContent))
            assert payload_5why_dark == json.loads(text_5why_dark.text)
            assert payload_5why_dark["rows_count"] == 5
            assert payload_5why_dark["steps_count"] == 5
            assert payload_5why_dark["valid"] is True
            assert payload_5why_dark["verdict"] == "ACCEPT"
            assert payload_5why_dark["reversibility_score"] == 1.0
            assert "<!DOCTYPE html>" in payload_5why_dark["html"]

            # Direct canvas and tool parity
            c_5why = FiveWhyCanvas.load_sample()
            assert payload_5why_dark["html"] == c_5why.to_html(theme="dark", standalone=True)
            assert payload_5why_dark["summary"] == c_5why.get_summary()
            assert payload_5why_dark == render_5why_canvas(theme="dark", standalone=True)

            # render_5why_canvas — Custom (Light Embeddable)
            res_5why_light = await session.call_tool(
                "render_5why_canvas",
                arguments={
                    "steps": _CUSTOM_FIVE_WHY_STEPS,
                    "problem_statement": "Custom 5-Why Problem",
                    "theme": "light",
                    "standalone": False,
                },
            )
            assert not res_5why_light.isError
            payload_5why_light = res_5why_light.structuredContent
            assert "<!DOCTYPE html>" not in payload_5why_light["html"]
            assert payload_5why_light["rows_count"] == 5
            assert payload_5why_light["verdict"] == "ACCEPT"
            assert payload_5why_light["reversibility_score"] == 1.0
            assert payload_5why_light == render_5why_canvas(
                steps=_CUSTOM_FIVE_WHY_STEPS,
                problem_statement="Custom 5-Why Problem",
                theme="light",
                standalone=False,
            )

            # 2. render_fishbone_canvas — Default (Dark Standalone)
            res_fb_dark = await session.call_tool("render_fishbone_canvas", arguments={"theme": "dark", "standalone": True})
            assert not res_fb_dark.isError
            payload_fb_dark = res_fb_dark.structuredContent
            text_fb_dark = next(c for c in res_fb_dark.content if isinstance(c, TextContent))
            assert payload_fb_dark == json.loads(text_fb_dark.text)
            assert payload_fb_dark["rows_count"] == 12
            assert payload_fb_dark["causes_count"] == 12
            assert payload_fb_dark["valid"] is True
            assert payload_fb_dark["verdict"] == "ACCEPT"
            assert "<!DOCTYPE html>" in payload_fb_dark["html"]

            # Direct canvas and tool parity
            c_fb = FishboneCanvas.load_sample()
            assert payload_fb_dark["html"] == c_fb.to_html(theme="dark", standalone=True)
            assert payload_fb_dark["summary"] == c_fb.get_summary()
            assert payload_fb_dark == render_fishbone_canvas(theme="dark", standalone=True)

            # render_fishbone_canvas — Custom (Light Embeddable)
            res_fb_light = await session.call_tool(
                "render_fishbone_canvas",
                arguments={
                    "causes": _CUSTOM_FISHBONE_CAUSES,
                    "effect": "Custom Fishbone Effect",
                    "theme": "light",
                    "standalone": False,
                },
            )
            assert not res_fb_light.isError
            payload_fb_light = res_fb_light.structuredContent
            assert "<!DOCTYPE html>" not in payload_fb_light["html"]
            assert payload_fb_light["rows_count"] == 6
            assert payload_fb_light["causes_count"] == 6
            assert payload_fb_light["verdict"] == "ACCEPT"
            assert payload_fb_light == render_fishbone_canvas(
                causes=_CUSTOM_FISHBONE_CAUSES,
                effect="Custom Fishbone Effect",
                theme="light",
                standalone=False,
            )

            # 3. render_isisnot_canvas — Default (Dark Standalone)
            res_kt_dark = await session.call_tool("render_isisnot_canvas", arguments={"theme": "dark", "standalone": True})
            assert not res_kt_dark.isError
            payload_kt_dark = res_kt_dark.structuredContent
            text_kt_dark = next(c for c in res_kt_dark.content if isinstance(c, TextContent))
            assert payload_kt_dark == json.loads(text_kt_dark.text)
            assert payload_kt_dark["rows_count"] == 4
            assert payload_kt_dark["dimensions_count"] == 4
            assert payload_kt_dark["valid"] is True
            assert payload_kt_dark["verdict"] == "ACCEPT"
            assert "<!DOCTYPE html>" in payload_kt_dark["html"]

            # Direct canvas and tool parity
            c_kt = IsIsNotCanvas.load_sample()
            assert payload_kt_dark["html"] == c_kt.to_html(theme="dark", standalone=True)
            assert payload_kt_dark["summary"] == c_kt.get_summary()
            assert payload_kt_dark == render_isisnot_canvas(theme="dark", standalone=True)

            # render_isisnot_canvas — Custom (Light Embeddable)
            res_kt_light = await session.call_tool(
                "render_isisnot_canvas",
                arguments={
                    "matrix": _CUSTOM_KT_MATRIX,
                    "problem_statement": "Custom KT Problem",
                    "theme": "light",
                    "standalone": False,
                },
            )
            assert not res_kt_light.isError
            payload_kt_light = res_kt_light.structuredContent
            assert "<!DOCTYPE html>" not in payload_kt_light["html"]
            assert payload_kt_light["rows_count"] == 4
            assert payload_kt_light == render_isisnot_canvas(
                matrix=_CUSTOM_KT_MATRIX,
                problem_statement="Custom KT Problem",
                theme="light",
                standalone=False,
            )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 6. Multi-Method Chained RCA Workflow Session Without Crosstalk
# ---------------------------------------------------------------------------


def test_mcp_client_multi_tool_chained_rca_session() -> None:
    """Execute sequential 4-stage RCA workflow (KT -> Fishbone -> 5-Why -> Canvases) in one session without state pollution."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # Stage 1: Problem Boundary Scoping via Kepner-Tregoe Is/Is-Not
            kt_res = await session.call_tool(
                "scope_is_is_not",
                arguments={
                    "matrix": _CUSTOM_KT_MATRIX,
                    "problem_statement": "Hole position deviation on Station 3 CNC drilling station",
                },
            )
            assert not kt_res.isError
            kt_data = kt_res.structuredContent
            assert kt_data["valid"] is True
            assert kt_data["verdict"] == "ACCEPT"
            assert len(kt_data["candidate_causes"]) == 4

            # Extract synthesized candidate causes from Stage 1
            synthesized_causes: list[dict[str, Any]] = [
                {
                    "category": "Machine" if "collet" in cc["hypothesis"].lower() or "drill" in cc["hypothesis"].lower() else "Method",
                    "cause": cc["hypothesis"],
                    "sub_category": cc["dimension"],
                }
                for cc in kt_data["candidate_causes"]
            ]

            # Stage 2: 6M Fishbone Categorization & Empty Branch Check
            # Combine brainstormed causes with synthesized candidate causes
            combined_causes = _CUSTOM_FISHBONE_CAUSES + synthesized_causes
            fb_res = await session.call_tool(
                "categorize_fishbone",
                arguments={
                    "causes": combined_causes,
                    "effect": "Hole position deviation on Station 3 CNC drilling station",
                    "check_balance": True,
                    "balance_threshold": 0.75,
                },
            )
            assert not fb_res.isError
            fb_data = fb_res.structuredContent
            assert fb_data["valid"] is True
            assert fb_data["verdict"] == "ACCEPT"
            assert fb_data["total_causes"] == 10
            assert fb_data["empty_branches"] == []

            # Stage 3: 5-Why Causal Chain Validation & Systemic Root Cause Classification
            why_res = await session.call_tool(
                "validate_5why",
                arguments={
                    "steps": _CUSTOM_FIVE_WHY_STEPS,
                    "problem_statement": "Hole position deviation on Station 3 CNC drilling station",
                    "root_cause": "Maintenance management system lacked automated work-order generation for pneumatic components",
                    "leg_type": "occurrence",
                },
            )
            assert not why_res.isError
            why_data = why_res.structuredContent
            assert why_data["valid"] is True
            assert why_data["verdict"] == "ACCEPT"
            assert why_data["reversibility_score"] == 1.0
            assert why_data["total_steps"] == 5
            assert why_data["systemic_assessment"]["is_systemic"] is True

            # Stage 4: Visual Canvas Artifact Generation for all 3 Stages
            canvas_kt = await session.call_tool(
                "render_isisnot_canvas",
                arguments={
                    "matrix": _CUSTOM_KT_MATRIX,
                    "problem_statement": "Hole position deviation on Station 3 CNC drilling station",
                    "theme": "dark",
                    "standalone": True,
                },
            )
            assert not canvas_kt.isError
            assert "<!DOCTYPE html>" in canvas_kt.structuredContent["html"]

            canvas_fb = await session.call_tool(
                "render_fishbone_canvas",
                arguments={
                    "causes": combined_causes,
                    "effect": "Hole position deviation on Station 3 CNC drilling station",
                    "theme": "dark",
                    "standalone": True,
                },
            )
            assert not canvas_fb.isError
            assert "<!DOCTYPE html>" in canvas_fb.structuredContent["html"]

            canvas_5why = await session.call_tool(
                "render_5why_canvas",
                arguments={
                    "steps": _CUSTOM_FIVE_WHY_STEPS,
                    "problem_statement": "Hole position deviation on Station 3 CNC drilling station",
                    "theme": "dark",
                    "standalone": True,
                },
            )
            assert not canvas_5why.isError
            assert "<!DOCTYPE html>" in canvas_5why.structuredContent["html"]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 7. In-Process Session Error Isolation
# ---------------------------------------------------------------------------


def test_mcp_client_rca_session_error_isolation() -> None:
    """An error in one tool does not affect subsequent executions of other RCA tools in the same session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Trigger error in 5-Why (malformed non-list steps)
            bad_why = await session.call_tool(
                "validate_5why",
                arguments={"steps": "not-a-list"},
            )
            assert bad_why.isError is True

            # 2. Subsequent Is/Is-Not call remains healthy
            kt_res = await session.call_tool("scope_is_is_not", arguments={})
            assert not kt_res.isError
            assert kt_res.structuredContent["valid"] is True
            assert kt_res.structuredContent["verdict"] == "ACCEPT"

            # 3. Trigger error in Fishbone (invalid causes type)
            bad_fb = await session.call_tool(
                "categorize_fishbone",
                arguments={"causes": 12345},
            )
            assert bad_fb.isError is True

            # 4. Subsequent 5-Why call with valid steps remains healthy
            valid_why = await session.call_tool("validate_5why", arguments={})
            assert not valid_why.isError
            assert valid_why.structuredContent["valid"] is True
            assert valid_why.structuredContent["verdict"] == "ACCEPT"

            # 5. Subsequent canvas call remains healthy
            canvas_res = await session.call_tool("render_5why_canvas", arguments={})
            assert not canvas_res.isError
            assert canvas_res.structuredContent["valid"] is True

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 8. Protocol-Level Negative Controls & Error Resilience
# ---------------------------------------------------------------------------


def test_mcp_client_protocol_negative_controls() -> None:
    """Client calls with protocol-level invalid payloads trigger structured error handling or isError."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Circular reasoning loop in 5-Why returns structured REJECT with CIRCULAR_REASONING anti-pattern
            res_circular = await session.call_tool(
                "validate_5why",
                arguments={"steps": _CIRCULAR_FIVE_WHY_STEPS, "problem_statement": "Conveyor line stopped"},
            )
            assert not res_circular.isError
            data_circular = res_circular.structuredContent
            assert data_circular["valid"] is False
            assert data_circular["verdict"] == "REJECT"
            assert any(ap["code"] == "CIRCULAR_REASONING" for ap in data_circular["anti_patterns"])

            # 2. Premature termination in 5-Why (steps=[]) returns structured REJECT with PREMATURE_TERMINATION
            res_empty_why = await session.call_tool(
                "validate_5why",
                arguments={"steps": [], "problem_statement": "No steps"},
            )
            assert not res_empty_why.isError
            data_empty_why = res_empty_why.structuredContent
            assert data_empty_why["valid"] is False
            assert data_empty_why["verdict"] == "REJECT"
            assert any(ap["code"] == "PREMATURE_TERMINATION" for ap in data_empty_why["anti_patterns"])

            # 3. Empty Fishbone causes (causes=[]) returns structured REJECT with 6 empty branches
            res_empty_fb = await session.call_tool(
                "categorize_fishbone",
                arguments={"causes": [], "effect": "No causes defect"},
            )
            assert not res_empty_fb.isError
            data_empty_fb = res_empty_fb.structuredContent
            assert data_empty_fb["valid"] is False
            assert data_empty_fb["verdict"] == "REJECT"
            assert len(data_empty_fb["empty_branches"]) == 6
            assert any("contains no causes" in w for w in data_empty_fb["warnings"])

            # 4. Empty Is/Is-Not matrix (matrix=[]) returns structured REJECT with 4 missing dimensions
            res_empty_kt = await session.call_tool(
                "scope_is_is_not",
                arguments={"matrix": [], "problem_statement": "No matrix defect"},
            )
            assert not res_empty_kt.isError
            data_empty_kt = res_empty_kt.structuredContent
            assert data_empty_kt["valid"] is False
            assert data_empty_kt["verdict"] == "REJECT"
            assert data_empty_kt["missing_dimensions"] == ["WHAT", "WHERE", "WHEN", "EXTENT"]
            assert any("contains no scoping rows" in w for w in data_empty_kt["warnings"])

            # 5. Type error on tool arguments returns isError=True
            res_type_err_why = await session.call_tool("validate_5why", arguments={"steps": "invalid"})
            assert res_type_err_why.isError is True

            res_type_err_fb = await session.call_tool("categorize_fishbone", arguments={"causes": "invalid"})
            assert res_type_err_fb.isError is True

            res_type_err_kt = await session.call_tool("scope_is_is_not", arguments={"matrix": "invalid"})
            assert res_type_err_kt.isError is True

            # 6. Unknown tool invocation returns isError=True
            res_unknown = await session.call_tool("nonexistent_rca_tool", arguments={})
            assert res_unknown.isError is True

            # 7. Value errors on canvas tools return isError=True
            res_bad_theme = await session.call_tool("render_5why_canvas", arguments={"theme": "neon"})
            assert res_bad_theme.isError is True

            res_empty_title = await session.call_tool("render_fishbone_canvas", arguments={"title": "   "})
            assert res_empty_title.isError is True

            res_empty_prob = await session.call_tool("render_isisnot_canvas", arguments={"problem_statement": "   "})
            assert res_empty_prob.isError is True

    asyncio.run(_run())

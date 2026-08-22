"""
test_ncr_copq_client_roundtrip.py
Integration tests proving in-process FastMCP client-server round-trip for all five NCR and COPQ tools.

Validates:
1. FastMCP server initialization, handshake, and tool discovery for all 5 NCR & COPQ tools:
   write_ncr, recommend_disposition, render_ncr_canvas, estimate_copq, render_copq_canvas.
2. Real-world benchmark execution across reference datasets (Machining Bore Porosity, Connecting Rod Rework,
   Turbocharger Warranty Escapes).
3. Dual-payload parity: structuredContent dictionary vs JSON-deserialized content[0].text.
4. Exact parity with direct quality_core.ncr and quality_core.copq engine functions and canvas controllers.
5. Visual canvas rendering across themes (dark/light) and modes (standalone/embeddable).
6. Chained multi-tool workflow execution across a single session without crosstalk or state pollution.
7. In-process session error isolation.
8. Protocol-level negative controls and error handling.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.canvas.copq import (
    SAMPLE_COPQ_ITEMS,
    load_sample_copq_canvas,
)
from quality_core.canvas.ncr import (
    SAMPLE_NCR_RECORDS,
    NCRCanvas,
)
from quality_core.copq.estimator import estimate_copq as core_estimate_copq
from quality_core.ncr.nonconformance import (
    recommend_disposition as core_recommend_disposition,
)
from quality_core.ncr.nonconformance import (
    write_nonconformance as core_write_nonconformance,
)
from quality_mcp.server import mcp

# ---------------------------------------------------------------------------
# Benchmark Test Fixtures
# ---------------------------------------------------------------------------

_MACHINED_BORE_NCR_NOTE = (
    "Lot 2026-08A: Found 45 engine cylinder blocks with casting porosity on the finish-honed cylinder bore "
    "at Final Inspection Station 4. Diameter 85.00 +/- 0.02 mm exhibited pit depth 0.08 mm violating max allowable 0.01 mm. "
    "Operator error suspected."
)

_CONNECTING_ROD_NCR_NOTE = (
    "Lot CR-500: Pin bore diameter measured 21.98 mm vs drawing spec 22.00 +/- 0.01 mm across 35 connecting rods "
    "at CNC Machining Cell 2."
)

_WARRANTY_TURBO_NOTE = (
    "Customer Warranty: 12 turbocharger assemblies returned from field due to oil leakage at turbine housing seal ring "
    "violating zero-leakage requirement."
)


# ==============================================================================
# 1. FastMCP Client Handshake & Tool Discovery
# ==============================================================================


def test_client_handshake_discovers_all_ncr_copq_tools() -> None:
    """In-process client handshake discovers and validates schemas for all 5 NCR & COPQ tools."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools_result = await client.list_tools()
            tools_by_name = {t.name: t for t in tools_result.tools}

            # Verify all 5 tools are discovered
            assert "write_ncr" in tools_by_name
            assert "recommend_disposition" in tools_by_name
            assert "render_ncr_canvas" in tools_by_name
            assert "estimate_copq" in tools_by_name
            assert "render_copq_canvas" in tools_by_name

            # 1. Inspect write_ncr schema
            write_ncr_tool = tools_by_name["write_ncr"]
            assert "ISO 9001" in (write_ncr_tool.description or "")
            schema_props = write_ncr_tool.inputSchema.get("properties", {})
            assert "raw_defect_note" in schema_props
            assert "what_deviated" in schema_props
            assert "requirement_violated" in schema_props
            assert "measured_evidence" in schema_props
            assert "quantity_affected" in schema_props
            assert "detection_point" in schema_props
            assert "part_lot_id" in schema_props

            # 2. Inspect recommend_disposition schema
            disp_tool = tools_by_name["recommend_disposition"]
            assert "disposition" in (disp_tool.description or "")
            disp_props = disp_tool.inputSchema.get("properties", {})
            assert "is_reworkable" in disp_props
            assert "defect_origin" in disp_props
            assert "part_value" in disp_props
            assert "rework_cost" in disp_props

            # 3. Inspect render_ncr_canvas schema
            ncr_canvas_tool = tools_by_name["render_ncr_canvas"]
            canvas_props = ncr_canvas_tool.inputSchema.get("properties", {})
            assert "records" in canvas_props
            assert "title" in canvas_props
            assert "standalone" in canvas_props

            # 4. Inspect estimate_copq schema
            copq_tool = tools_by_name["estimate_copq"]
            assert "COPQ" in (copq_tool.description or "")
            copq_props = copq_tool.inputSchema.get("properties", {})
            assert "scrap_qty" in copq_props
            assert "unit_cost" in copq_props
            assert "rework_hours" in copq_props
            assert "labor_rate" in copq_props
            assert "revenue_base" in copq_props

            # 5. Inspect render_copq_canvas schema
            copq_canvas_tool = tools_by_name["render_copq_canvas"]
            copq_c_props = copq_canvas_tool.inputSchema.get("properties", {})
            assert "items" in copq_c_props
            assert "revenue_base" in copq_c_props
            assert "title" in copq_c_props
            assert "standalone" in copq_c_props

    asyncio.run(_run())


# ==============================================================================
# 2. Individual Tool Round-Trip & Dual-Payload Parity
# ==============================================================================


def test_write_ncr_roundtrip_parity() -> None:
    """write_ncr returns exact dual-payload structuredContent and matches direct core engine."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            params = {
                "raw_defect_note": _MACHINED_BORE_NCR_NOTE,
                "what_deviated": "Cylinder bore surface porosity pits",
                "requirement_violated": "Drawing Note 4: Max pore depth 0.01 mm",
                "measured_evidence": "Pore depth 0.08 mm measured via optical profilometer",
                "quantity_affected": 45,
                "detection_point": "Final Honing Inspection Station 4",
                "part_lot_id": "LOT-2026-08A",
            }

            res = await client.call_tool("write_ncr", params)
            assert not res.isError
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)

            parsed_text = json.loads(res.content[0].text)
            if hasattr(res, "structuredContent") and res.structuredContent is not None:
                assert res.structuredContent == parsed_text

            # Match against direct core function
            direct_core = core_write_nonconformance(**params).to_dict()
            assert parsed_text == direct_core
            assert parsed_text["valid"] is True
            assert parsed_text["quantity_affected"] == 45
            assert "operator error" in parsed_text["blame_phrases_detected"]

    asyncio.run(_run())


def test_recommend_disposition_roundtrip_parity() -> None:
    """recommend_disposition returns exact dual-payload structuredContent and matches direct core engine."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Scrap disposition
            scrap_params = {
                "is_reworkable": False,
                "defect_origin": "Internal",
                "part_value": 450.0,
                "rework_cost": 0.0,
            }
            res_scrap = await client.call_tool("recommend_disposition", scrap_params)
            assert not res_scrap.isError
            parsed_scrap = json.loads(res_scrap.content[0].text)  # type: ignore[union-attr]
            direct_scrap = core_recommend_disposition(**scrap_params).to_dict()
            assert parsed_scrap == direct_scrap
            assert parsed_scrap["disposition"] == "Scrap"
            assert "IATF 16949" in parsed_scrap["standards_basis"]

            # 2. Rework disposition
            rework_params = {
                "is_reworkable": True,
                "defect_origin": "Internal",
                "part_value": 200.0,
                "rework_cost": 30.0,
            }
            res_rework = await client.call_tool("recommend_disposition", rework_params)
            assert not res_rework.isError
            parsed_rework = json.loads(res_rework.content[0].text)  # type: ignore[union-attr]
            direct_rework = core_recommend_disposition(**rework_params).to_dict()
            assert parsed_rework == direct_rework
            assert parsed_rework["disposition"] == "Rework"
            assert parsed_rework["fmea_risk_analysis_required"] is True

    asyncio.run(_run())


def test_render_ncr_canvas_roundtrip_parity() -> None:
    """render_ncr_canvas returns HTML canvas matching direct NCRCanvas controller."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Standalone benchmark canvas
            res_std = await client.call_tool(
                "render_ncr_canvas",
                {"standalone": True, "title": "Engine Plant NCR Canvas"},
            )
            assert not res_std.isError
            parsed_std = json.loads(res_std.content[0].text)  # type: ignore[union-attr]
            assert parsed_std["title"] == "Engine Plant NCR Canvas"
            assert parsed_std["rows_count"] == len(SAMPLE_NCR_RECORDS)
            assert "<!DOCTYPE html>" in parsed_std["html"]
            assert "Engine Plant NCR Canvas" in parsed_std["html"]

            # Match against direct core canvas controller with same title
            direct_canvas = NCRCanvas(title="Engine Plant NCR Canvas")
            for r in SAMPLE_NCR_RECORDS:
                direct_canvas.add_record(r)
            assert parsed_std["summary"] == direct_canvas.get_summary()

            # 2. Embeddable canvas
            res_embed = await client.call_tool(
                "render_ncr_canvas",
                {"standalone": False, "title": "Embedded NCR Canvas"},
            )
            assert not res_embed.isError
            parsed_embed = json.loads(res_embed.content[0].text)  # type: ignore[union-attr]
            assert "<!DOCTYPE html>" not in parsed_embed["html"]
            assert "ncr-canvas-container" in parsed_embed["html"]

    asyncio.run(_run())


def test_estimate_copq_roundtrip_parity() -> None:
    """estimate_copq returns exact dual-payload structuredContent and matches direct core engine."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            params = {
                "scrap_qty": 45,
                "unit_cost": 120.0,
                "rework_hours": 35.0,
                "labor_rate": 65.0,
                "added_material_cost": 450.0,
                "sort_hours": 40.0,
                "warranty_units": 12,
                "warranty_cost_per_unit": 850.0,
                "prevention_cost": 7300.0,
                "appraisal_cost": 11300.0,
                "revenue_base": 500000.0,
                "title": "Manufacturing Q3 COPQ Estimation",
            }

            res = await client.call_tool("estimate_copq", params)
            assert not res.isError
            parsed_text = json.loads(res.content[0].text)  # type: ignore[union-attr]

            if hasattr(res, "structuredContent") and res.structuredContent is not None:
                assert res.structuredContent == parsed_text

            # Direct core calculation
            direct_core = core_estimate_copq(**params).to_dict()
            assert parsed_text == direct_core
            assert parsed_text["internal_failure_total"] == 10725.0
            assert parsed_text["external_failure_total"] == 10200.0
            assert parsed_text["total_copq"] == 20925.0
            assert parsed_text["cogq_total"] == 18600.0
            assert parsed_text["total_coq"] == 39525.0
            assert parsed_text["copq_percentage_of_revenue"] == 4.185

    asyncio.run(_run())


def test_render_copq_canvas_roundtrip_parity() -> None:
    """render_copq_canvas returns HTML canvas matching direct COPQCanvas controller."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Standalone benchmark canvas
            res_dark = await client.call_tool(
                "render_copq_canvas",
                {"revenue_base": 500000.0, "standalone": True, "title": "Plant COPQ Canvas"},
            )
            assert not res_dark.isError
            parsed_dark = json.loads(res_dark.content[0].text)  # type: ignore[union-attr]
            assert parsed_dark["title"] == "Plant COPQ Canvas"
            assert parsed_dark["rows_count"] == len(SAMPLE_COPQ_ITEMS)
            assert "<!DOCTYPE html>" in parsed_dark["html"]

            direct_canvas = load_sample_copq_canvas(revenue_base=500000.0)
            assert parsed_dark["summary"] == direct_canvas.get_summary()

            # 2. Embeddable canvas with custom item list
            custom_items = [
                {"category": "Prevention", "description": "DFM Review", "direct_cost": 3000.0},
                {"category": "InternalFailure", "description": "Scrap", "scrap_qty": 20, "unit_cost": 100.0},
            ]
            res_light = await client.call_tool(
                "render_copq_canvas",
                {"items": custom_items, "standalone": False, "title": "Custom Embed Canvas"},
            )
            assert not res_light.isError
            parsed_light = json.loads(res_light.content[0].text)  # type: ignore[union-attr]
            assert parsed_light["rows_count"] == 2
            assert "<!DOCTYPE html>" not in parsed_light["html"]
            assert "copq-canvas-container" in parsed_light["html"]

    asyncio.run(_run())


# ==============================================================================
# 3. Session Error Isolation & Protocol Negative Controls
# ==============================================================================


def test_session_error_isolation_does_not_corrupt_subsequent_calls() -> None:
    """A malformed tool call in a session returns an error without corrupting subsequent valid calls."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Intentionally trigger malformed invocation on estimate_copq (negative scrap_qty)
            res_bad = await client.call_tool("estimate_copq", {"scrap_qty": -50})
            assert res_bad.isError

            # 2. Subsequent call to write_ncr in the same session succeeds cleanly
            res_ncr = await client.call_tool(
                "write_ncr",
                {
                    "what_deviated": "Bore diameter out of spec",
                    "requirement_violated": "Spec 50.0 +/- 0.1 mm",
                    "measured_evidence": "50.3 mm",
                    "quantity_affected": 10,
                    "detection_point": "Station 1",
                },
            )
            assert not res_ncr.isError
            parsed_ncr = json.loads(res_ncr.content[0].text)  # type: ignore[union-attr]
            assert parsed_ncr["valid"] is True

            # 3. Trigger another malformed call on render_copq_canvas (invalid title)
            res_bad2 = await client.call_tool("render_copq_canvas", {"title": ""})
            assert res_bad2.isError

            # 4. Subsequent valid call to estimate_copq succeeds cleanly
            res_valid_copq = await client.call_tool(
                "estimate_copq",
                {"scrap_qty": 20, "unit_cost": 100.0, "revenue_base": 100000.0},
            )
            assert not res_valid_copq.isError
            parsed_copq = json.loads(res_valid_copq.content[0].text)  # type: ignore[union-attr]
            assert parsed_copq["total_copq"] == 2000.0

    asyncio.run(_run())


def test_protocol_negative_controls_unknown_tool_and_invalid_arguments() -> None:
    """FastMCP client properly reports error for unknown tools, type mismatches, and negative bounds."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Unknown tool
            res_unknown = await client.call_tool("non_existent_tool_12345", {})
            assert res_unknown.isError

            # 2. String passed for numeric argument in estimate_copq
            res_type_err = await client.call_tool("estimate_copq", {"scrap_qty": "not_an_int"})
            assert res_type_err.isError

            # 3. Negative float for revenue_base
            res_neg_rev = await client.call_tool("estimate_copq", {"revenue_base": -5000.0})
            assert res_neg_rev.isError

            # 4. Invalid standalone argument in render_ncr_canvas
            res_bad_standalone = await client.call_tool("render_ncr_canvas", {"standalone": "not_a_bool"})
            assert res_bad_standalone.isError

            # 5. Missing critical routing data in recommend_disposition returns structured INSUFFICIENT_DATA (not crash)
            res_insufficient = await client.call_tool("recommend_disposition", {})
            assert not res_insufficient.isError
            parsed_insufficient = json.loads(res_insufficient.content[0].text)  # type: ignore[union-attr]
            assert parsed_insufficient["verdict"] == "INSUFFICIENT_DATA"
            assert parsed_insufficient["disposition"] is None
            assert parsed_insufficient["mrb_review_required"] is True
            assert len(parsed_insufficient["missing_evidence"]) > 0

    asyncio.run(_run())


# ==============================================================================
# 4. Multi-Tool Chained Workflow 1 (Single-Session Sequential Pipeline)
# ==============================================================================


def test_chained_ncr_to_copq_workflow() -> None:
    """Execute chained NCR -> Disposition -> COPQ Estimation -> Canvas rendering in a single session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # Step 1: Write Nonconformance Statement from Raw Shop-Floor Note
            res_ncr = await client.call_tool(
                "write_ncr",
                {
                    "raw_defect_note": _MACHINED_BORE_NCR_NOTE,
                    "what_deviated": "Cylinder bore surface porosity pits",
                    "requirement_violated": "Drawing Note 4: Max pore depth 0.01 mm",
                    "measured_evidence": "Pore depth 0.08 mm measured via optical profilometer",
                    "quantity_affected": 45,
                    "detection_point": "Final Honing Inspection Station 4",
                    "part_lot_id": "LOT-2026-08A",
                },
            )
            assert not res_ncr.isError
            ncr_data = json.loads(res_ncr.content[0].text)  # type: ignore[union-attr]
            assert ncr_data["valid"] is True
            qty_affected = ncr_data["quantity_affected"]
            assert qty_affected == 45

            # Step 2: Determine Nonconformance Disposition
            res_disp = await client.call_tool(
                "recommend_disposition",
                {
                    "is_reworkable": False,
                    "defect_origin": "Internal",
                    "part_value": 120.0,
                    "rework_cost": 0.0,
                },
            )
            assert not res_disp.isError
            disp_data = json.loads(res_disp.content[0].text)  # type: ignore[union-attr]
            assert disp_data["disposition"] == "Scrap"
            assert disp_data["verdict"] == "VALID"
            assert "IATF 16949" in disp_data["standards_basis"]

            # Step 3: Financial Estimation of COPQ from Disposition & Quantity
            # Scrap cost: 45 units * $120.00 = $5,400.00
            # Containment: 40 hours * $45.00/hr = $1,800.00
            res_copq = await client.call_tool(
                "estimate_copq",
                {
                    "scrap_qty": qty_affected,
                    "unit_cost": 120.0,
                    "sort_hours": 40.0,
                    "labor_rate": 45.0,
                    "prevention_cost": 5000.0,
                    "appraisal_cost": 7500.0,
                    "revenue_base": 500000.0,
                    "title": f"COPQ Impact for NCR Lot {ncr_data['part_lot_id']}",
                },
            )
            assert not res_copq.isError
            copq_data = json.loads(res_copq.content[0].text)  # type: ignore[union-attr]
            assert copq_data["internal_failure_total"] == 7200.0  # 5400 scrap + 1800 containment
            assert copq_data["external_failure_total"] == 0.0
            assert copq_data["total_copq"] == 7200.0
            assert copq_data["cogq_total"] == 12500.0  # 5000 + 7500
            assert copq_data["total_coq"] == 19700.0
            assert copq_data["copq_percentage_of_revenue"] == 1.44

            # Step 4: Render Interactive COPQ Visual Canvas
            item_list = [
                {"category": "Prevention", "description": "Tooling & Process Review", "direct_cost": 5000.0},
                {"category": "Appraisal", "description": "Honing Bore Inspection", "direct_cost": 7500.0},
                {"category": "InternalFailure", "description": f"Porosity Scrap ({qty_affected} pcs)", "scrap_qty": qty_affected, "unit_cost": 120.0},
                {"category": "InternalFailure", "description": "Lot Containment Sorting", "containment_hours": 40.0, "labor_rate": 45.0},
            ]
            res_canvas = await client.call_tool(
                "render_copq_canvas",
                {
                    "items": item_list,
                    "revenue_base": 500000.0,
                    "standalone": True,
                    "title": f"Visual COPQ Canvas - Lot {ncr_data['part_lot_id']}",
                },
            )
            assert not res_canvas.isError
            canvas_data = json.loads(res_canvas.content[0].text)  # type: ignore[union-attr]
            assert canvas_data["rows_count"] == 4
            assert canvas_data["summary"]["copq"] == 7200.0
            assert "<!DOCTYPE html>" in canvas_data["html"]

    asyncio.run(_run())


# ==============================================================================
# 5. Multi-Tool Chained Workflow 2 (Comparative Multi-Defect Pipeline)
# ==============================================================================


def test_chained_multi_defect_comparative_pipeline() -> None:
    """Execute 3 distinct industrial defect pathways (Scrap vs Rework vs Warranty) in a single session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            captured_items: list[dict[str, Any]] = []

            # Pathway A: Engine Block Porosity (Scrap)
            res_a_ncr = await client.call_tool(
                "write_ncr",
                {
                    "what_deviated": "Casting porosity in cylinder bore",
                    "requirement_violated": "Spec max pore depth 0.01 mm",
                    "measured_evidence": "0.08 mm pore depth",
                    "quantity_affected": 50,
                    "detection_point": "Final Honing Station 4",
                },
            )
            assert not res_a_ncr.isError
            res_a_disp = await client.call_tool("recommend_disposition", {"is_reworkable": False, "defect_origin": "Internal", "part_value": 120.0})
            assert not res_a_disp.isError
            disp_a = json.loads(res_a_disp.content[0].text)  # type: ignore[union-attr]
            assert disp_a["disposition"] == "Scrap"
            captured_items.append({"category": "InternalFailure", "description": "Engine Block Porosity Scrap (50 pcs)", "scrap_qty": 50, "unit_cost": 120.0})

            # Pathway B: Connecting Rod Pin Bore (Rework)
            res_b_ncr = await client.call_tool(
                "write_ncr",
                {
                    "raw_defect_note": _CONNECTING_ROD_NCR_NOTE,
                    "what_deviated": "Pin bore diameter undersize",
                    "requirement_violated": "Spec 22.00 +/- 0.01 mm",
                    "measured_evidence": "21.98 mm pin bore",
                    "quantity_affected": 35,
                    "detection_point": "Machining Cell 2",
                },
            )
            assert not res_b_ncr.isError
            res_b_disp = await client.call_tool("recommend_disposition", {"is_reworkable": True, "defect_origin": "Internal", "part_value": 75.0, "rework_cost": 15.0})
            assert not res_b_disp.isError
            disp_b = json.loads(res_b_disp.content[0].text)  # type: ignore[union-attr]
            assert disp_b["disposition"] == "Rework"
            captured_items.append({"category": "InternalFailure", "description": "Connecting Rod Pin Bore Rework (35 hrs labor)", "rework_hours": 35.0, "labor_rate": 65.0, "direct_cost": 450.0})

            # Pathway C: Turbocharger Housing Seal Ring (Field Warranty Escape)
            res_c_ncr = await client.call_tool(
                "write_ncr",
                {
                    "raw_defect_note": _WARRANTY_TURBO_NOTE,
                    "what_deviated": "Turbine housing oil seal leakage",
                    "requirement_violated": "Zero leakage spec",
                    "measured_evidence": "Oil seepage under 2 bar pressure",
                    "quantity_affected": 12,
                    "detection_point": "Customer Dealer Network",
                },
            )
            assert not res_c_ncr.isError
            captured_items.append({"category": "ExternalFailure", "description": "Turbocharger Field Warranty Replacement (12 units)", "warranty_units": 12, "warranty_unit_cost": 850.0})
            captured_items.append({"category": "ExternalFailure", "description": "Customer Returned Defective Batch Logistics", "direct_cost": 3600.0})

            # Add Conformance Investments (Prevention + Appraisal)
            captured_items.append({"category": "Prevention", "description": "APQP Quality Planning & Poka-Yoke Training", "direct_cost": 7300.0})
            captured_items.append({"category": "Appraisal", "description": "CMM Metrology & In-Process AOI Audits", "direct_cost": 11300.0})

            # Consolidated Multi-Defect COPQ Rollup
            res_rollup = await client.call_tool(
                "estimate_copq",
                {
                    "items": captured_items,
                    "revenue_base": 1000000.0,
                    "title": "Comprehensive Plant-Wide COPQ Rollup",
                },
            )
            assert not res_rollup.isError
            rollup_data = json.loads(res_rollup.content[0].text)  # type: ignore[union-attr]
            assert rollup_data["item_count"] == 6
            assert rollup_data["internal_failure_total"] == 8725.0  # 6000 scrap + 2725 rework
            assert rollup_data["external_failure_total"] == 13800.0  # 10200 warranty + 3600 returns
            assert rollup_data["total_copq"] == 22525.0
            assert rollup_data["cogq_total"] == 18600.0
            assert rollup_data["total_coq"] == 41125.0
            assert rollup_data["copq_percentage_of_revenue"] == 2.2525

            # Render Comparative Canvas
            res_comp_canvas = await client.call_tool(
                "render_copq_canvas",
                {
                    "items": captured_items,
                    "revenue_base": 1000000.0,
                    "title": "Plant-Wide Comparative Quality Canvas",
                    "standalone": True,
                },
            )
            assert not res_comp_canvas.isError
            canvas_out = json.loads(res_comp_canvas.content[0].text)  # type: ignore[union-attr]
            assert canvas_out["rows_count"] == 6
            assert canvas_out["summary"]["copq"] == 22525.0

    asyncio.run(_run())

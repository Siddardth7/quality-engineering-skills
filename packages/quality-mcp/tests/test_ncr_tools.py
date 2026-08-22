"""
test_ncr_tools.py
Unit and integration round-trip tests for NCR FastMCP tools (write_ncr, recommend_disposition, render_ncr_canvas).

Tests:
1. Direct function executions and parameter checking.
2. Dual-payload parity across in-process FastMCP memory transport client sessions.
3. Negative controls and error handling.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from quality_mcp.server import mcp
from quality_mcp.tools.canvas import render_ncr_canvas
from quality_mcp.tools.ncr import recommend_disposition, write_ncr

# ==============================================================================
# 1. Direct Function Invocation Tests
# ==============================================================================


def test_write_ncr_direct() -> None:
    """write_ncr returns structured dict with valid nonconformance statement."""
    res = write_ncr(
        raw_defect_note="Found 50 parts oversized at turning station 2.",
        what_deviated="Shaft diameter oversized",
        requirement_violated="Spec 12.00 +/- 0.05 mm",
        measured_evidence="12.20 mm",
        quantity_affected=50,
        detection_point="Turning Station 2",
        part_lot_id="LOT-100",
    )
    assert isinstance(res, dict)
    assert res["valid"] is True
    assert "LOT-100" in res["statement"]
    assert res["quantity_affected"] == 50
    assert res["standards_basis"] == "ISO 9001:2015 §8.7 / IATF 16949:2016 §8.7"


def test_recommend_disposition_direct() -> None:
    """recommend_disposition returns structured disposition recommendation."""
    res = recommend_disposition(
        is_reworkable=True,
        defect_origin="Internal",
        rework_cost=5.0,
        part_value=50.0,
    )
    assert isinstance(res, dict)
    assert res["disposition"] == "Rework"
    assert res["verdict"] == "VALID"
    assert res["fmea_risk_analysis_required"] is True


def test_recommend_disposition_negative_control_direct() -> None:
    """recommend_disposition returns INSUFFICIENT_DATA when parameters are missing."""
    res = recommend_disposition()
    assert res["disposition"] is None
    assert res["verdict"] == "INSUFFICIENT_DATA"
    assert "is_reworkable" in res["missing_evidence"]


def test_render_ncr_canvas_direct_default() -> None:
    """render_ncr_canvas with None records renders the default 5 benchmark records."""
    res = render_ncr_canvas()
    assert isinstance(res, dict)
    assert res["title"] == "Nonconformance Report (NCR) Canvas"
    assert res["rows_count"] == 5
    assert "<!DOCTYPE html>" in res["html"]
    assert "summary" in res
    assert res["summary"]["total_records"] == 5


def test_render_ncr_canvas_direct_custom() -> None:
    """render_ncr_canvas renders custom records in embeddable mode."""
    custom_records = [
        {
            "record_id": "NCR-999",
            "part_lot_id": "LOT-999",
            "defect_description": "Custom flaw",
            "requirement_violated": "Spec 001",
            "quantity_affected": 5,
            "detection_point": "Gate A",
            "disposition": "Scrap",
        }
    ]
    res = render_ncr_canvas(records=custom_records, title="Custom Title", standalone=False)
    assert res["title"] == "Custom Title"
    assert res["rows_count"] == 1
    assert "<!DOCTYPE html>" not in res["html"]
    assert '<div class="ncr-canvas-container"' in res["html"]


def test_render_ncr_canvas_type_and_value_errors() -> None:
    """render_ncr_canvas raises TypeError and ValueError on invalid inputs."""
    with pytest.raises(TypeError, match="standalone must be a boolean"):
        render_ncr_canvas(standalone=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="title must be a string"):
        render_ncr_canvas(title=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="title must not be empty"):
        render_ncr_canvas(title="   ")

    with pytest.raises(TypeError, match="records must be a list of dictionaries"):
        render_ncr_canvas(records="invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="records item at index 0 must be a dict"):
        render_ncr_canvas(records=[123])  # type: ignore[list-item]


# ==============================================================================
# 2. FastMCP In-Process Client Round-Trip Tests
# ==============================================================================


def test_mcp_client_roundtrip_ncr_tools() -> None:
    """FastMCP in-process client invokes write_ncr, recommend_disposition, and render_ncr_canvas with payload parity."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # Tool Discovery
            tools = await client.list_tools()
            tool_names = {t.name for t in tools.tools}
            assert "write_ncr" in tool_names
            assert "recommend_disposition" in tool_names
            assert "render_ncr_canvas" in tool_names

            # 1. write_ncr round-trip
            write_res = await client.call_tool(
                "write_ncr",
                {
                    "what_deviated": "Bore diameter oversized",
                    "requirement_violated": "DWG-101: 25.00 +/- 0.05 mm",
                    "measured_evidence": "25.12 mm",
                    "quantity_affected": 20,
                    "detection_point": "CMM Cell 2",
                    "part_lot_id": "LOT-BORE-20",
                },
            )
            assert write_res.structuredContent is not None
            assert write_res.structuredContent["valid"] is True
            assert "LOT-BORE-20" in write_res.structuredContent["statement"]

            # Text-content parity check
            text_payload = json.loads(write_res.content[0].text)  # type: ignore[union-attr]
            assert text_payload == write_res.structuredContent

            # 2. recommend_disposition round-trip
            disp_res = await client.call_tool(
                "recommend_disposition",
                {
                    "is_reworkable": True,
                    "defect_origin": "Internal",
                    "rework_cost": 15.0,
                    "part_value": 120.0,
                },
            )
            assert disp_res.structuredContent is not None
            assert disp_res.structuredContent["disposition"] == "Rework"
            assert disp_res.structuredContent["verdict"] == "VALID"
            disp_text = json.loads(disp_res.content[0].text)  # type: ignore[union-attr]
            assert disp_text == disp_res.structuredContent

            # 3. recommend_disposition negative control round-trip
            neg_res = await client.call_tool("recommend_disposition", {})
            assert neg_res.structuredContent is not None
            assert neg_res.structuredContent["disposition"] is None
            assert neg_res.structuredContent["verdict"] == "INSUFFICIENT_DATA"

            # 4. render_ncr_canvas round-trip
            canvas_res = await client.call_tool("render_ncr_canvas", {})
            assert canvas_res.structuredContent is not None
            assert canvas_res.structuredContent["rows_count"] == 5
            canvas_text = json.loads(canvas_res.content[0].text)  # type: ignore[union-attr]
            assert canvas_text == canvas_res.structuredContent

    asyncio.run(_run())

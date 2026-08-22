"""
test_copq_tools.py
Unit and integration round-trip tests for COPQ FastMCP tools (estimate_copq, render_copq_canvas).

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
from quality_mcp.tools.canvas import render_copq_canvas
from quality_mcp.tools.copq import estimate_copq

# ==============================================================================
# 1. Direct Function Invocation Tests
# ==============================================================================


def test_estimate_copq_direct() -> None:
    """estimate_copq returns structured dict with accurate PAF calculations."""
    res = estimate_copq(
        scrap_qty=50,
        unit_cost=100.0,
        rework_hours=20.0,
        labor_rate=60.0,
        sort_hours=10.0,
        warranty_units=5,
        warranty_cost_per_unit=500.0,
        prevention_cost=3000.0,
        appraisal_cost=4000.0,
        revenue_base=500000.0,
        title="Direct Estimation Test",
    )
    assert isinstance(res, dict)
    assert res["title"] == "Direct Estimation Test"
    assert res["internal_failure_total"] == 6800.0  # 5000 + 1200 + 600
    assert res["external_failure_total"] == 2500.0  # 2500
    assert res["total_copq"] == 9300.0
    assert res["prevention_total"] == 3000.0
    assert res["appraisal_total"] == 4000.0
    assert res["cogq_total"] == 7000.0
    assert res["total_coq"] == 16300.0
    assert res["copq_percentage_of_revenue"] == 1.86
    assert "standards_basis" in res


def test_estimate_copq_with_items_direct() -> None:
    """estimate_copq correctly aggregates itemized dictionaries."""
    items = [
        {"category": "Prevention", "description": "Training", "direct_cost": 2500.0},
        {"category": "Appraisal", "description": "Audit", "direct_cost": 3500.0},
        {"category": "InternalFailure", "description": "Scrap", "scrap_qty": 10, "unit_cost": 80.0},
        {"category": "ExternalFailure", "description": "Warranty", "warranty_units": 2, "warranty_unit_cost": 600.0},
    ]
    res = estimate_copq(items=items)
    assert res["item_count"] == 4
    assert res["prevention_total"] == 2500.0
    assert res["appraisal_total"] == 3500.0
    assert res["internal_failure_total"] == 800.0
    assert res["external_failure_total"] == 1200.0
    assert res["total_copq"] == 2000.0
    assert res["cogq_total"] == 6000.0
    assert res["total_coq"] == 8000.0


def test_render_copq_canvas_direct() -> None:
    """render_copq_canvas returns dict with HTML and summary metrics."""
    res = render_copq_canvas(revenue_base=1000000.0, standalone=True)
    assert isinstance(res, dict)
    assert "html" in res
    assert "summary" in res
    assert res["rows_count"] > 0
    assert "<!DOCTYPE html>" in res["html"]
    assert "PAF Cost of Quality Distribution" in res["html"]


def test_render_copq_canvas_custom_items_direct() -> None:
    """render_copq_canvas works with custom item list and embeddable mode."""
    custom_items = [
        {"category": "Prevention", "description": "Poka-yoke tooling", "direct_cost": 1500.0},
        {"category": "InternalFailure", "description": "Rework", "rework_hours": 10.0, "labor_rate": 50.0},
    ]
    res = render_copq_canvas(items=custom_items, standalone=False, title="Custom COPQ Canvas")
    assert res["title"] == "Custom COPQ Canvas"
    assert res["rows_count"] == 2
    assert "<!DOCTYPE html>" not in res["html"]
    assert "copq-canvas-container" in res["html"]


# ==============================================================================
# 2. In-Process FastMCP Memory Transport Client Tests
# ==============================================================================


def test_mcp_client_roundtrip_copq_tools() -> None:
    """Validate in-process memory transport client invocation and dual-payload parity."""

    async def _run() -> None:
        server = mcp._mcp_server

        async with create_connected_server_and_client_session(server) as client:
            tools_res = await client.list_tools()
            tool_names = {t.name for t in tools_res.tools}
            assert "estimate_copq" in tool_names
            assert "render_copq_canvas" in tool_names

            # 1. Test estimate_copq tool execution
            res_calc = await client.call_tool(
                "estimate_copq",
                {
                    "scrap_qty": 30,
                    "unit_cost": 150.0,
                    "rework_hours": 15.0,
                    "labor_rate": 70.0,
                    "warranty_units": 4,
                    "warranty_cost_per_unit": 600.0,
                    "prevention_cost": 4000.0,
                    "appraisal_cost": 6000.0,
                    "revenue_base": 500000.0,
                    "title": "Client Roundtrip COPQ",
                },
            )
            assert not res_calc.isError
            assert len(res_calc.content) == 1
            text_payload = json.loads(res_calc.content[0].text)  # type: ignore[union-attr]

            if hasattr(res_calc, "structuredContent") and res_calc.structuredContent is not None:
                assert res_calc.structuredContent == text_payload

            assert text_payload["total_copq"] == 7950.0  # (30*150=4500) + (15*70=1050) + (4*600=2400) = 7950
            assert text_payload["total_coq"] == 17950.0  # 7950 + 10000
            assert text_payload["copq_percentage_of_revenue"] == 1.59

            # 2. Test render_copq_canvas tool execution
            res_canvas = await client.call_tool(
                "render_copq_canvas",
                {
                    "revenue_base": 500000.0,
                    "title": "Client Roundtrip Canvas",
                    "standalone": True,
                },
            )
            assert not res_canvas.isError
            canvas_payload = json.loads(res_canvas.content[0].text)  # type: ignore[union-attr]
            assert canvas_payload["title"] == "Client Roundtrip Canvas"
            assert "html" in canvas_payload
            assert "<!DOCTYPE html>" in canvas_payload["html"]

    asyncio.run(_run())


# ==============================================================================
# 3. Negative Controls & Error Handling
# ==============================================================================


def test_estimate_copq_validation_errors() -> None:
    """Invalid parameter values raise ValueError or TypeError in estimate_copq."""
    with pytest.raises(ValueError, match="scrap_qty must be >= 0"):
        estimate_copq(scrap_qty=-10)

    with pytest.raises(TypeError, match="scrap_qty cannot be a boolean"):
        estimate_copq(scrap_qty=True)  # type: ignore[arg-type]


def test_render_copq_canvas_validation_errors() -> None:
    """Invalid arguments in render_copq_canvas raise appropriate exceptions."""
    with pytest.raises(TypeError, match="standalone must be a boolean"):
        render_copq_canvas(standalone="true")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="title must be a string"):
        render_copq_canvas(title=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="title must not be empty"):
        render_copq_canvas(title="")

    with pytest.raises(TypeError, match="revenue_base must be a number"):
        render_copq_canvas(revenue_base="500000")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="revenue_base must be >= 0.0"):
        render_copq_canvas(revenue_base=-100.0)

    with pytest.raises(TypeError, match="items must be a list of dictionaries or None"):
        render_copq_canvas(items="invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="items element at index 0 must be a dict"):
        render_copq_canvas(items=["not_a_dict"])  # type: ignore[list-item]

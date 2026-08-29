"""Unit tests for quality_mcp FastMCP server and ping health check tool."""

from __future__ import annotations

import asyncio
import runpy
import warnings
from unittest.mock import patch

import quality_mcp
from quality_mcp import __version__
from quality_mcp.server import (
    assess_ppap_capability,
    audit_ppap_package,
    calculate_gage_rr,
    calculate_otif,
    calculate_spc_chart,
    calculate_supplier_ppm,
    calculate_vendor_scorecard,
    categorize_fishbone,
    estimate_copq,
    evaluate_escalation,
    generate_scar,
    lookup_fmea_ap,
    lookup_ppap_requirement,
    main,
    mcp,
    ping,
    recommend_disposition,
    render_5why_canvas,
    render_controlplan_canvas,
    render_copq_canvas,
    render_fishbone_canvas,
    render_fmea_canvas,
    render_is_is_not_canvas,
    render_isisnot_canvas,
    render_msa_canvas,
    render_ncr_canvas,
    render_ppap_canvas,
    render_spc_canvas,
    render_sqe_canvas,
    scope_is_is_not,
    validate_5why,
    validate_control_plan,
    validate_psw,
    write_ncr,
)


def test_ping_returns_correct_dict() -> None:
    """Invoke ping() and assert return value and schema match specification."""
    result = ping()
    expected = {
        "status": "ok",
        "server": "quality-mcp",
        "version": "0.9.0",
    }
    assert result == expected
    assert result["status"] == "ok"
    assert result["server"] == "quality-mcp"
    assert result["version"] == __version__
    assert isinstance(result, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in result.items())


def test_mcp_instance_configuration() -> None:
    """Verify FastMCP server instance metadata and registered tool list."""
    assert mcp.name == "quality-mcp"
    tools = asyncio.run(mcp.list_tools())
    tool_names = [tool.name for tool in tools]
    assert "ping" in tool_names
    assert "lookup_fmea_ap" in tool_names
    assert "render_5why_canvas" in tool_names
    assert "render_controlplan_canvas" in tool_names
    assert "render_copq_canvas" in tool_names
    assert "render_fishbone_canvas" in tool_names
    assert "render_fmea_canvas" in tool_names
    assert "render_isisnot_canvas" in tool_names
    assert "render_msa_canvas" in tool_names
    assert "render_spc_canvas" in tool_names
    assert "calculate_spc_chart" in tool_names
    assert "calculate_gage_rr" in tool_names
    assert "categorize_fishbone" in tool_names
    assert "scope_is_is_not" in tool_names
    assert "validate_5why" in tool_names
    assert "validate_control_plan" in tool_names
    assert "write_ncr" in tool_names
    assert "recommend_disposition" in tool_names
    assert "render_ncr_canvas" in tool_names
    assert "estimate_copq" in tool_names
    assert "assess_ppap_capability" in tool_names
    assert "audit_ppap_package" in tool_names
    assert "lookup_ppap_requirement" in tool_names
    assert "render_ppap_canvas" in tool_names
    assert "validate_psw" in tool_names
    assert "calculate_supplier_ppm" in tool_names
    assert "calculate_otif" in tool_names
    assert "calculate_vendor_scorecard" in tool_names
    assert "evaluate_escalation" in tool_names
    assert "generate_scar" in tool_names
    assert "render_sqe_canvas" in tool_names

    # Exactly 31 tools registered (25 baseline + 6 SQE), each name unique.
    assert len(tool_names) == 31
    assert len(set(tool_names)) == 31

    # Verify tool execution via FastMCP interface
    _, content = asyncio.run(mcp.call_tool("ping", {}))
    assert content == {
        "status": "ok",
        "server": "quality-mcp",
        "version": __version__,
    }

    _, ap_content = asyncio.run(
        mcp.call_tool("lookup_fmea_ap", {"severity": 10, "occurrence": 10, "detection": 10})
    )
    assert ap_content == {
        "severity": 10,
        "occurrence": 10,
        "detection": 10,
        "rpn": 1000,
        "action_priority": "High",
    }

    _, canvas_content = asyncio.run(mcp.call_tool("render_fmea_canvas", {}))
    assert canvas_content["rows_count"] == 6
    assert "summary" in canvas_content
    assert "html" in canvas_content

    _, cp_canvas_content = asyncio.run(mcp.call_tool("render_controlplan_canvas", {}))
    assert cp_canvas_content["rows_count"] == 6
    assert "summary" in cp_canvas_content
    assert "html" in cp_canvas_content

    _, spc_canvas_content = asyncio.run(mcp.call_tool("render_spc_canvas", {}))
    assert spc_canvas_content["chart_type"] == "Xbar-R"
    assert spc_canvas_content["in_control"] is True
    assert "html" in spc_canvas_content

    _, msa_canvas_content = asyncio.run(mcp.call_tool("render_msa_canvas", {}))
    assert msa_canvas_content["method"] == "anova"
    assert msa_canvas_content["verdict"] == "Reject"
    assert "html" in msa_canvas_content

    _, cp_content = asyncio.run(
        mcp.call_tool(
            "validate_control_plan",
            {
                "plan": [
                    {
                        "characteristic": "Bore Diameter",
                        "measurement_method": "Bore gauge",
                        "sample_size": 5,
                        "frequency": "per shift",
                        "reaction_plan": "Stop line.",
                    }
                ]
            },
        )
    )
    assert cp_content["valid"] is True
    assert cp_content["schema_valid"] is True

    _, kt_content = asyncio.run(mcp.call_tool("scope_is_is_not", {}))
    assert kt_content["valid"] is True
    assert kt_content["verdict"] == "ACCEPT"
    assert kt_content["total_rows"] == 4

    _, kt_canvas_content = asyncio.run(mcp.call_tool("render_isisnot_canvas", {}))
    assert kt_canvas_content["rows_count"] == 4
    assert kt_canvas_content["verdict"] == "ACCEPT"
    assert "html" in kt_canvas_content

    _, why_content = asyncio.run(mcp.call_tool("validate_5why", {}))
    assert why_content["valid"] is True
    assert why_content["verdict"] == "ACCEPT"
    assert why_content["total_steps"] == 5

    _, why_canvas_content = asyncio.run(mcp.call_tool("render_5why_canvas", {}))
    assert why_canvas_content["rows_count"] == 5
    assert why_canvas_content["verdict"] == "ACCEPT"
    assert "html" in why_canvas_content

    _, fishbone_content = asyncio.run(mcp.call_tool("categorize_fishbone", {}))
    assert fishbone_content["valid"] is True
    assert fishbone_content["verdict"] == "ACCEPT"
    assert fishbone_content["total_causes"] == 12

    _, fishbone_canvas_content = asyncio.run(mcp.call_tool("render_fishbone_canvas", {}))
    assert fishbone_canvas_content["rows_count"] == 12
    assert fishbone_canvas_content["verdict"] == "ACCEPT"
    assert "html" in fishbone_canvas_content

    _, ncr_write_content = asyncio.run(
        mcp.call_tool(
            "write_ncr",
            {
                "raw_defect_note": "Found 10 bad parts at incoming inspection.",
                "requirement_violated": "Spec-100",
                "measured_evidence": "Measured out of spec",
                "what_deviated": "Bore diameter out of spec",
                "quantity_affected": 10,
                "detection_point": "Receiving Inspection",
            },
        )
    )
    assert ncr_write_content["valid"] is True
    assert "statement" in ncr_write_content

    _, ncr_disp_content = asyncio.run(
        mcp.call_tool(
            "recommend_disposition",
            {
                "is_reworkable": True,
                "defect_origin": "Internal",
            },
        )
    )
    assert ncr_disp_content["disposition"] == "Rework"
    assert ncr_disp_content["verdict"] == "VALID"

    _, ncr_canvas_content = asyncio.run(mcp.call_tool("render_ncr_canvas", {}))
    assert ncr_canvas_content["rows_count"] == 5
    assert "summary" in ncr_canvas_content
    assert "html" in ncr_canvas_content

    _, copq_calc_content = asyncio.run(
        mcp.call_tool(
            "estimate_copq",
            {
                "scrap_qty": 20,
                "unit_cost": 50.0,
                "rework_hours": 10.0,
                "labor_rate": 50.0,
                "revenue_base": 100000.0,
            },
        )
    )
    assert copq_calc_content["total_copq"] == 1500.0
    assert copq_calc_content["copq_percentage_of_revenue"] == 1.5

    _, copq_canvas_content = asyncio.run(mcp.call_tool("render_copq_canvas", {}))
    assert copq_canvas_content["rows_count"] == 9
    assert "summary" in copq_canvas_content
    assert "html" in copq_canvas_content

    _, audit_content = asyncio.run(mcp.call_tool("audit_ppap_package", {}))
    assert audit_content["package_verdict"] == "INDETERMINATE"
    assert "basis" in audit_content

    _, req_content = asyncio.run(
        mcp.call_tool("lookup_ppap_requirement", {"element_id": "2.2.4", "submission_level": 3})
    )
    assert req_content["requirement_code"] == "S"
    assert req_content["element_id"] == "2.2.4"

    _, psw_content = asyncio.run(mcp.call_tool("validate_psw", {}))
    assert psw_content["verdict"] == "COMPLETE"
    assert "basis" in psw_content

    _, cap_content = asyncio.run(
        mcp.call_tool(
            "assess_ppap_capability",
            {
                "precomputed_index_type": "Ppk",
                "precomputed_index_value": 1.85,
                "precomputed_sample_size": 125,
                "precomputed_subgroup_count": 25,
            },
        )
    )
    assert cap_content["verdict"] == "ACCEPTABLE"
    assert "basis" in cap_content

    _, ppap_canvas_content = asyncio.run(mcp.call_tool("render_ppap_canvas", {}))
    assert ppap_canvas_content["rows_count"] == 18
    assert "summary" in ppap_canvas_content
    assert "html" in ppap_canvas_content

    _, ppm_content = asyncio.run(mcp.call_tool("calculate_supplier_ppm", {}))
    assert ppm_content["verdict"] == "MEASURED"
    assert ppm_content["ppm"] == 400.0

    _, otif_content = asyncio.run(mcp.call_tool("calculate_otif", {}))
    assert otif_content["verdict"] == "MEASURED"
    assert otif_content["on_time_pct"] == 100.0

    _, scorecard_content = asyncio.run(mcp.call_tool("calculate_vendor_scorecard", {}))
    assert scorecard_content["verdict"] == "RATED"
    assert scorecard_content["band"] == "B"

    _, escalation_content = asyncio.run(mcp.call_tool("evaluate_escalation", {}))
    assert escalation_content["tier"] == "MONITOR"

    _, scar_content = asyncio.run(mcp.call_tool("generate_scar", {}))
    assert scar_content["status"] == "AWAITING_SUPPLIER_RESPONSE"
    assert scar_content["root_cause"] is None

    _, sqe_canvas_content = asyncio.run(mcp.call_tool("render_sqe_canvas", {}))
    assert sqe_canvas_content["rows_count"] == 6
    assert "summary" in sqe_canvas_content
    assert "html" in sqe_canvas_content


def test_main_invokes_mcp_run() -> None:
    """main() entry point must call mcp.run() once."""
    with patch.object(mcp, "run") as mock_run:
        main()
        mock_run.assert_called_once_with()


def test_main_dunder_execution() -> None:
    """Executing server.py as __main__ must invoke main() and run FastMCP.run()."""
    with patch("mcp.server.fastmcp.FastMCP.run") as mock_fastmcp_run:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            runpy.run_module("quality_mcp.server", run_name="__main__", alter_sys=False)
        mock_fastmcp_run.assert_called_once_with()


def test_package_exports() -> None:
    """Package root __init__.py must re-export all tools and __version__ correctly."""
    assert quality_mcp.mcp is mcp
    assert quality_mcp.ping is ping
    assert quality_mcp.lookup_fmea_ap is lookup_fmea_ap
    assert quality_mcp.render_5why_canvas is render_5why_canvas
    assert quality_mcp.render_controlplan_canvas is render_controlplan_canvas
    assert quality_mcp.render_fishbone_canvas is render_fishbone_canvas
    assert quality_mcp.render_fmea_canvas is render_fmea_canvas
    assert quality_mcp.render_msa_canvas is render_msa_canvas
    assert quality_mcp.render_ncr_canvas is render_ncr_canvas
    assert quality_mcp.render_copq_canvas is render_copq_canvas
    assert quality_mcp.render_spc_canvas is render_spc_canvas
    assert quality_mcp.calculate_spc_chart is calculate_spc_chart
    assert quality_mcp.calculate_gage_rr is calculate_gage_rr
    assert quality_mcp.categorize_fishbone is categorize_fishbone
    assert quality_mcp.validate_5why is validate_5why
    assert quality_mcp.validate_control_plan is validate_control_plan
    assert quality_mcp.scope_is_is_not is scope_is_is_not
    assert quality_mcp.render_isisnot_canvas is render_isisnot_canvas
    assert quality_mcp.render_is_is_not_canvas is render_is_is_not_canvas
    assert quality_mcp.write_ncr is write_ncr
    assert quality_mcp.recommend_disposition is recommend_disposition
    assert quality_mcp.estimate_copq is estimate_copq
    assert quality_mcp.assess_ppap_capability is assess_ppap_capability
    assert quality_mcp.audit_ppap_package is audit_ppap_package
    assert quality_mcp.lookup_ppap_requirement is lookup_ppap_requirement
    assert quality_mcp.render_ppap_canvas is render_ppap_canvas
    assert quality_mcp.validate_psw is validate_psw
    assert quality_mcp.calculate_supplier_ppm is calculate_supplier_ppm
    assert quality_mcp.calculate_otif is calculate_otif
    assert quality_mcp.calculate_vendor_scorecard is calculate_vendor_scorecard
    assert quality_mcp.evaluate_escalation is evaluate_escalation
    assert quality_mcp.generate_scar is generate_scar
    assert quality_mcp.render_sqe_canvas is render_sqe_canvas
    assert quality_mcp.__version__ == "0.9.0"
    assert set(quality_mcp.__all__) == {
        "__version__",
        "assess_ppap_capability",
        "audit_ppap_package",
        "calculate_gage_rr",
        "calculate_otif",
        "calculate_spc_chart",
        "calculate_supplier_ppm",
        "calculate_vendor_scorecard",
        "categorize_fishbone",
        "estimate_copq",
        "evaluate_escalation",
        "generate_scar",
        "lookup_fmea_ap",
        "lookup_ppap_requirement",
        "mcp",
        "ping",
        "recommend_disposition",
        "render_5why_canvas",
        "render_controlplan_canvas",
        "render_copq_canvas",
        "render_fishbone_canvas",
        "render_fmea_canvas",
        "render_is_is_not_canvas",
        "render_isisnot_canvas",
        "render_msa_canvas",
        "render_ncr_canvas",
        "render_ppap_canvas",
        "render_spc_canvas",
        "render_sqe_canvas",
        "scope_is_is_not",
        "validate_5why",
        "validate_control_plan",
        "validate_psw",
        "write_ncr",
    }
    assert sorted(quality_mcp.__all__) == [
        "__version__",
        "assess_ppap_capability",
        "audit_ppap_package",
        "calculate_gage_rr",
        "calculate_otif",
        "calculate_spc_chart",
        "calculate_supplier_ppm",
        "calculate_vendor_scorecard",
        "categorize_fishbone",
        "estimate_copq",
        "evaluate_escalation",
        "generate_scar",
        "lookup_fmea_ap",
        "lookup_ppap_requirement",
        "mcp",
        "ping",
        "recommend_disposition",
        "render_5why_canvas",
        "render_controlplan_canvas",
        "render_copq_canvas",
        "render_fishbone_canvas",
        "render_fmea_canvas",
        "render_is_is_not_canvas",
        "render_isisnot_canvas",
        "render_msa_canvas",
        "render_ncr_canvas",
        "render_ppap_canvas",
        "render_spc_canvas",
        "render_sqe_canvas",
        "scope_is_is_not",
        "validate_5why",
        "validate_control_plan",
        "validate_psw",
        "write_ncr",
    ]


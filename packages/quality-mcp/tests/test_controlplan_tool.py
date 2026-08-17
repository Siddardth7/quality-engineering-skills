"""
Tests for validate_control_plan FastMCP tool in quality_mcp.tools.controlplan.
"""

from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from quality_mcp.server import mcp
from quality_mcp.tools.controlplan import validate_control_plan

_VALID_PLAN_ROW = {
    "characteristic": "Bore Diameter",
    "measurement_method": "Bore gauge",
    "sample_size": 5,
    "frequency": "per shift",
    "reaction_plan": "Stop line; notify quality engineer.",
    "lsl": 24.90,
    "usl": 25.10,
    "target": 25.00,
    "recommended_chart": "Xbar-R",
    "source_cause_id": "F1::M1::C1",
    "sample_plan_is_placeholder": True,
}

_VALID_FMEA_ROW = {
    "ID": 1,
    "Process_Step": "Machining",
    "Component": "Housing",
    "Function": "Enclose piston",
    "Failure_Mode": "Bore out of spec",
    "Effect": "Piston seizure",
    "Severity": 9,
    "Cause": "Tool wear",
    "Occurrence": 4,
    "Current_Control": "Bore gauge",
    "Detection": 3,
}


def test_validate_control_plan_valid_schema_without_fmea() -> None:
    res = validate_control_plan([_VALID_PLAN_ROW])
    assert res["basis"] == "AIAG Control Plan"
    assert res["valid"] is True
    assert res["total_rows"] == 1
    assert res["schema_valid"] is True
    assert res["schema_findings"] == []
    assert res["linkage_checked"] is False
    assert res["linkage_valid"] is None
    assert res["linked_rows"] is None
    assert res["orphan_characteristics"] == []
    assert res["uncovered_failure_modes"] == []


def test_validate_control_plan_empty_plan_rejected() -> None:
    res = validate_control_plan([])
    assert res["valid"] is False
    assert res["total_rows"] == 0
    assert res["schema_valid"] is False
    assert len(res["schema_findings"]) > 0
    assert "at least one characteristic row" in res["schema_findings"][0]


def test_validate_control_plan_tolerance_violation_rejected() -> None:
    bad_row = dict(_VALID_PLAN_ROW)
    bad_row["lsl"] = 25.10
    bad_row["usl"] = 24.90  # usl <= lsl
    res = validate_control_plan([bad_row])
    assert res["valid"] is False
    assert res["schema_valid"] is False
    assert any("usl must be greater than lsl" in f for f in res["schema_findings"])


def test_validate_control_plan_duplicate_characteristics_rejected() -> None:
    row1 = dict(_VALID_PLAN_ROW)
    row2 = dict(_VALID_PLAN_ROW)
    res = validate_control_plan([row1, row2])
    assert res["valid"] is False
    assert res["schema_valid"] is False
    assert any("duplicate characteristic" in f for f in res["schema_findings"])


def test_validate_control_plan_type_errors() -> None:
    with pytest.raises(TypeError, match="plan must be a list"):
        validate_control_plan("not a list")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="fmea must be a list"):
        validate_control_plan([_VALID_PLAN_ROW], fmea="not a list")  # type: ignore[arg-type]


def test_validate_control_plan_item_type_error_in_plan() -> None:
    res = validate_control_plan(["not a dict"])  # type: ignore[list-item]
    assert res["valid"] is False
    assert res["schema_valid"] is False
    assert any("Expected ControlPlanRow or dict" in f for f in res["schema_findings"])


def test_validate_control_plan_with_valid_fmea_linkage() -> None:
    fmea_data = [_VALID_FMEA_ROW]
    # Build control plan matching the FMEA function/failure_mode/cause (F1::F1-M1::F1-M1-C1)
    plan_row = {
        "characteristic": "Housing — Bore out of spec",
        "measurement_method": "Bore gauge",
        "sample_size": 5,
        "frequency": "per shift",
        "reaction_plan": "Contain and investigate.",
        "source_cause_id": "F1::F1-M1::F1-M1-C1",
    }
    res = validate_control_plan([plan_row], fmea=fmea_data)
    assert res["valid"] is True
    assert res["schema_valid"] is True
    assert res["linkage_checked"] is True
    assert res["linkage_valid"] is True
    assert res["linked_rows"] == 1
    assert res["orphan_characteristics"] == []
    assert res["uncovered_failure_modes"] == []


def test_validate_control_plan_orphan_linkage_negative_control() -> None:
    fmea_data = [_VALID_FMEA_ROW]
    # Control Plan row has unresolvable source_cause_id
    orphan_row = {
        "characteristic": "Orphan Characteristic",
        "measurement_method": "Visual check",
        "sample_size": 1,
        "frequency": "each lot",
        "reaction_plan": "Segregate.",
        "source_cause_id": "999::999-M1::999-C1",
    }
    res = validate_control_plan([orphan_row], fmea=fmea_data)
    assert res["valid"] is False
    assert res["schema_valid"] is True
    assert res["linkage_checked"] is True
    assert res["linkage_valid"] is False
    assert res["orphan_characteristics"] == ["Orphan Characteristic"]
    assert res["uncovered_failure_modes"] == ["F1::F1-M1"]
    assert any("Orphan characteristic 'Orphan Characteristic'" in f for f in res["linkage_findings"])


def test_validate_control_plan_invalid_fmea_input() -> None:
    bad_fmea = [{"invalid_key": 123}]
    res = validate_control_plan([_VALID_PLAN_ROW], fmea=bad_fmea)
    assert res["valid"] is False
    assert res["schema_valid"] is True
    assert res["linkage_valid"] is False
    assert len(res["linkage_findings"]) > 0
    assert any("Invalid FMEA input" in f for f in res["linkage_findings"])


def test_validate_control_plan_fmea_exception_handling() -> None:
    bad_fmea_items = ["not a dict"]
    res = validate_control_plan([_VALID_PLAN_ROW], fmea=bad_fmea_items)  # type: ignore[list-item]
    assert res["valid"] is False
    assert res["schema_valid"] is True
    assert res["linkage_valid"] is False
    assert any("FMEA processing error" in f for f in res["linkage_findings"])


def test_validate_control_plan_schema_invalid_prevents_linkage() -> None:
    bad_plan = [dict(_VALID_PLAN_ROW, lsl=25.0, usl=24.0)]
    fmea_data = [_VALID_FMEA_ROW]
    res = validate_control_plan(bad_plan, fmea=fmea_data)
    assert res["valid"] is False
    assert res["schema_valid"] is False
    assert res["linkage_valid"] is False
    assert any("Cannot verify PFMEA linkage" in f for f in res["linkage_findings"])


@pytest.mark.anyio
async def test_validate_control_plan_fastmcp_roundtrip() -> None:
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        res = await client.call_tool(
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
        assert res.structuredContent is not None
        assert res.structuredContent["valid"] is True
        assert res.structuredContent["basis"] == "AIAG Control Plan"
        assert res.structuredContent["schema_valid"] is True

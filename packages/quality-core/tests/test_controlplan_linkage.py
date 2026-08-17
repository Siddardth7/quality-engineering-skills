"""
Tests for quality_core.controlplan.connector.validate_pfmea_linkage.
"""

from __future__ import annotations

from quality_core.controlplan.connector import build_control_plan, validate_pfmea_linkage
from quality_core.controlplan.schema import ControlPlanDataset, ControlPlanRow
from quality_core.schema.relational import (
    Cause,
    Control,
    Effect,
    FailureLink,
    FailureMode,
    Function,
    RelationalFMEA,
)


def _fm(
    fm_id: str,
    description: str,
    s: int = 5,
    o: int = 5,
    d: int = 5,
    *,
    row_id: int = 1,
) -> FailureMode:
    return FailureMode(
        id=fm_id,
        description=description,
        effects=[Effect(id=f"{fm_id}-E1", description="Effect", severity=s)],
        causes=[Cause(id=f"{fm_id}-C1", description="Cause", occurrence=o)],
        controls=[Control(id=f"{fm_id}-CT1", description="Control", detection=d)],
        links=[
            FailureLink(row_id=row_id, effect_id=f"{fm_id}-E1", cause_id=f"{fm_id}-C1", control_id=f"{fm_id}-CT1")
        ],
    )


def _good_row(characteristic: str, source_cause_id: str | None = None) -> ControlPlanRow:
    return ControlPlanRow(
        characteristic=characteristic,
        measurement_method="Measurement Gauge",
        sample_size=5,
        frequency="per shift",
        reaction_plan="Contain and rework.",
        source_cause_id=source_cause_id,
    )


def test_validate_pfmea_linkage_clean_full_linkage() -> None:
    fm1 = _fm("M1", "Mode 1", row_id=1)
    fm2 = _fm("M2", "Mode 2", row_id=2)
    fmea = RelationalFMEA(functions=[Function(id="F1", process_step="Step", component="Comp", description="Fn", failure_modes=[fm1, fm2])])

    plan = build_control_plan(fmea)
    result = validate_pfmea_linkage(plan, fmea)

    assert result["valid"] is True
    assert result["total_rows"] == 2
    assert result["linked_rows"] == 2
    assert result["orphan_characteristics"] == []
    assert result["uncovered_failure_modes"] == []
    assert result["findings"] == []


def test_validate_pfmea_linkage_flags_orphan_missing_source_cause_id() -> None:
    fm1 = _fm("M1", "Mode 1", row_id=1)
    fmea = RelationalFMEA(functions=[Function(id="F1", process_step="Step", component="Comp", description="Fn", failure_modes=[fm1])])

    # Hand-crafted row with source_cause_id = None
    row = _good_row("Orphan Characteristic", source_cause_id=None)
    plan = ControlPlanDataset(rows=[row])

    result = validate_pfmea_linkage(plan, fmea)

    assert result["valid"] is False
    assert result["total_rows"] == 1
    assert result["linked_rows"] == 0
    assert result["orphan_characteristics"] == ["Orphan Characteristic"]
    assert "missing source_cause_id" in result["findings"][0]
    assert result["uncovered_failure_modes"] == ["F1::M1"]


def test_validate_pfmea_linkage_flags_orphan_invalid_source_cause_id() -> None:
    fm1 = _fm("M1", "Mode 1", row_id=1)
    fmea = RelationalFMEA(functions=[Function(id="F1", process_step="Step", component="Comp", description="Fn", failure_modes=[fm1])])

    # Hand-crafted row pointing to non-existent cause
    row = _good_row("Orphan with Bad ID", source_cause_id="F99::M99::C99")
    plan = ControlPlanDataset(rows=[row])

    result = validate_pfmea_linkage(plan, fmea)

    assert result["valid"] is False
    assert result["total_rows"] == 1
    assert result["linked_rows"] == 0
    assert result["orphan_characteristics"] == ["Orphan with Bad ID"]
    assert "F99::M99::C99" in result["findings"][0]
    assert result["uncovered_failure_modes"] == ["F1::M1"]


def test_validate_pfmea_linkage_flags_uncovered_fmea_modes() -> None:
    fm1 = _fm("M1", "Mode 1", row_id=1)
    fm2 = _fm("M2", "Mode 2", row_id=2)
    fmea = RelationalFMEA(functions=[Function(id="F1", process_step="Step", component="Comp", description="Fn", failure_modes=[fm1, fm2])])

    # Control Plan only covers M1
    row1 = _good_row("Comp — Mode 1", source_cause_id="F1::M1::M1-C1")
    plan = ControlPlanDataset(rows=[row1])

    result = validate_pfmea_linkage(plan, fmea)

    assert result["valid"] is True  # no orphan rows
    assert result["total_rows"] == 1
    assert result["linked_rows"] == 1
    assert result["orphan_characteristics"] == []
    assert result["uncovered_failure_modes"] == ["F1::M2"]
    assert any("Uncovered FMEA failure mode 'F1::M2'" in f for f in result["findings"])


def test_validate_pfmea_linkage_empty_fmea_and_empty_plan() -> None:
    fmea = RelationalFMEA(functions=[])
    plan = ControlPlanDataset(rows=[])

    result = validate_pfmea_linkage(plan, fmea)

    assert result["valid"] is True
    assert result["total_rows"] == 0
    assert result["linked_rows"] == 0
    assert result["orphan_characteristics"] == []
    assert result["uncovered_failure_modes"] == []
    assert result["findings"] == []

"""Unit tests for quality_core.canvas (FMEACanvasRow and FMEACanvas controller).

Verifies 100% line & branch coverage across all models, controller operations,
deterministic scoring recalculations, CRUD lifecycle, summary statistics, and HTML rendering.
"""

from __future__ import annotations

from typing import Any

import pytest
from quality_core.canvas import (
    SAMPLE_CONTROL_PLAN_ROWS,
    SAMPLE_FMEA_ROWS,
    SAMPLE_MSA_STUDY_DATA,
    SAMPLE_SPC_XBAR_R_DATA,
    ControlPlanCanvas,
    ControlPlanCanvasRow,
    FMEACanvas,
    FMEACanvasRow,
    MSACanvas,
    MSACanvasMeasurement,
    SPCCanvas,
    SPCCanvasSubgroup,
    load_sample_canvas,
    load_sample_controlplan_canvas,
    load_sample_msa_canvas,
    load_sample_spc_canvas,
)
from quality_core.schema import FMEADataset, FMEARow, flat_to_relational
from quality_core.scoring import HIGH, LOW, MEDIUM

# ---------------------------------------------------------------------------
# FMEACanvasRow Unit Tests
# ---------------------------------------------------------------------------


def test_row_valid_construction() -> None:
    """Instantiate a valid row and verify deterministic scoring."""
    row = FMEACanvasRow(
        id=1,
        process_step="Inverter SMT",
        component="Gate Driver",
        function="Desat Protection",
        failure_mode="Overcurrent tripping",
        effect="Loss of drive",
        severity=10,
        cause="Voltage transient",
        occurrence=4,
        current_control="AOI + functional test",
        detection=4,
        ai_candidate=False,
    )
    assert row.id == 1
    assert row.severity == 10
    assert row.occurrence == 4
    assert row.detection == 4
    assert row.rpn == 160
    assert row.action_priority == HIGH
    assert not row.ai_candidate


def test_row_from_dict_snake_case() -> None:
    """from_dict parses snake_case keys correctly."""
    data = {
        "id": 2,
        "process_step": "Machining",
        "component": "Brake Valve",
        "function": "Pressure control",
        "failure_mode": "Calibration drift",
        "effect": "Degraded braking",
        "severity": 9,
        "cause": "Thermal fatigue",
        "occurrence": 5,
        "current_control": "Calibrated sweep",
        "detection": 1,
        "ai_candidate": True,
    }
    row = FMEACanvasRow.from_dict(data)
    assert row.id == 2
    assert row.rpn == 45
    assert row.action_priority == MEDIUM
    assert row.ai_candidate is True
    assert row.to_dict()["action_priority"] == MEDIUM


def test_row_from_dict_pascal_case() -> None:
    """from_dict parses PascalCase / uppercase schema keys."""
    data = {
        "ID": 3,
        "Process_Step": "Stacking",
        "Component": "Battery Cell",
        "Function": "Layer isolation",
        "Failure_Mode": "Separator puncture",
        "Effect": "Thermal runaway",
        "Severity": 10,
        "Cause": "Particulate contamination",
        "Occurrence": 6,
        "Current_Control": "Visual inspection",
        "Detection": 8,
        "AI_Candidate": False,
    }
    row = FMEACanvasRow.from_dict(data)
    assert row.id == 3
    assert row.process_step == "Stacking"
    assert row.rpn == 480
    assert row.action_priority == HIGH
    assert row.ai_candidate is False


def test_row_from_dict_defaults_ai_candidate_false() -> None:
    """from_dict defaults ai_candidate to False if omitted."""
    data = {
        "id": 4,
        "process_step": "Winding",
        "component": "Stator",
        "function": "Insulation",
        "failure_mode": "Dielectric breakdown",
        "effect": "Ground fault",
        "severity": 8,
        "cause": "Varnish void",
        "occurrence": 7,
        "current_control": "Dielectric test",
        "detection": 1,
    }
    row = FMEACanvasRow.from_dict(data)
    assert row.ai_candidate is False
    assert row.action_priority == MEDIUM


def test_row_from_dict_non_dict_raises() -> None:
    """from_dict raises TypeError on non-dict input."""
    with pytest.raises(TypeError, match="data must be a dictionary"):
        FMEACanvasRow.from_dict("invalid")  # type: ignore[arg-type]


def test_row_from_dict_missing_field_raises() -> None:
    """from_dict raises ValueError if a mandatory field is missing."""
    with pytest.raises(ValueError, match="Missing required field 'id' or 'ID'"):
        FMEACanvasRow.from_dict({"process_step": "Test"})


@pytest.mark.parametrize(
    "invalid_id",
    [-1, 0, "1", True, False, 1.5, None],
)
def test_row_invalid_id_raises(invalid_id: object) -> None:
    """Invalid row ID raises ValueError."""
    with pytest.raises(ValueError, match="id must be a positive integer"):
        FMEACanvasRow(
            id=invalid_id,  # type: ignore[arg-type]
            process_step="Step",
            component="Comp",
            function="Func",
            failure_mode="Mode",
            effect="Effect",
            severity=5,
            cause="Cause",
            occurrence=5,
            current_control="Control",
            detection=5,
        )


@pytest.mark.parametrize(
    "str_field",
    [
        "process_step",
        "component",
        "function",
        "failure_mode",
        "effect",
        "cause",
        "current_control",
    ],
)
def test_row_empty_string_fields_raise(str_field: str) -> None:
    """Empty or non-string text fields raise ValueError."""
    kwargs: dict[str, object] = {
        "id": 1,
        "process_step": "Step",
        "component": "Comp",
        "function": "Func",
        "failure_mode": "Mode",
        "effect": "Effect",
        "severity": 5,
        "cause": "Cause",
        "occurrence": 5,
        "current_control": "Control",
        "detection": 5,
    }
    kwargs[str_field] = "   "
    with pytest.raises(ValueError, match=f"{str_field} must be a non-empty string"):
        FMEACanvasRow(**kwargs)  # type: ignore[arg-type]

    kwargs[str_field] = 123
    with pytest.raises(ValueError, match=f"{str_field} must be a non-empty string"):
        FMEACanvasRow(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("num_field", ["severity", "occurrence", "detection"])
def test_row_invalid_rating_types_raise(num_field: str) -> None:
    """Non-integer types for S, O, D raise TypeError."""
    kwargs: dict[str, object] = {
        "id": 1,
        "process_step": "Step",
        "component": "Comp",
        "function": "Func",
        "failure_mode": "Mode",
        "effect": "Effect",
        "severity": 5,
        "cause": "Cause",
        "occurrence": 5,
        "current_control": "Control",
        "detection": 5,
    }
    kwargs[num_field] = "5"
    with pytest.raises(TypeError, match=f"{num_field} must be an integer"):
        FMEACanvasRow(**kwargs)  # type: ignore[arg-type]

    kwargs[num_field] = True
    with pytest.raises(TypeError, match=f"{num_field} must be an integer"):
        FMEACanvasRow(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("num_field", ["severity", "occurrence", "detection"])
@pytest.mark.parametrize("out_of_bound_val", [0, 11, -5, 100])
def test_row_out_of_bounds_ratings_raise(num_field: str, out_of_bound_val: int) -> None:
    """Out-of-range S, O, D ratings raise ValueError."""
    kwargs: dict[str, object] = {
        "id": 1,
        "process_step": "Step",
        "component": "Comp",
        "function": "Func",
        "failure_mode": "Mode",
        "effect": "Effect",
        "severity": 5,
        "cause": "Cause",
        "occurrence": 5,
        "current_control": "Control",
        "detection": 5,
    }
    kwargs[num_field] = out_of_bound_val
    with pytest.raises(ValueError, match=f"{num_field} must be between 1 and 10"):
        FMEACanvasRow(**kwargs)  # type: ignore[arg-type]


def test_row_invalid_ai_candidate_type_raises() -> None:
    """Non-bool ai_candidate raises TypeError."""
    with pytest.raises(TypeError, match="ai_candidate must be a boolean"):
        FMEACanvasRow(
            id=1,
            process_step="Step",
            component="Comp",
            function="Func",
            failure_mode="Mode",
            effect="Effect",
            severity=5,
            cause="Cause",
            occurrence=5,
            current_control="Control",
            detection=5,
            ai_candidate="true",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# FMEACanvas Controller Unit Tests
# ---------------------------------------------------------------------------


def test_canvas_default_initialization() -> None:
    """Canvas initializes with default title and empty rows."""
    canvas = FMEACanvas()
    assert canvas.title == "AIAG & VDA 2019 Process FMEA Canvas"
    assert canvas.description == "Interactive single-writer visual FMEA canvas with deterministic scoring."
    assert canvas.rows == []
    summary = canvas.get_summary()
    assert summary == {
        "total_rows": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "max_rpn": 0,
        "ai_candidate_count": 0,
    }


def test_canvas_invalid_metadata_raises() -> None:
    """Invalid title or description raises ValueError."""
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        FMEACanvas(title="   ")
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        FMEACanvas(title=123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="description must be a non-empty string"):
        FMEACanvas(description="")
    with pytest.raises(ValueError, match="description must be a non-empty string"):
        FMEACanvas(description=None)  # type: ignore[arg-type]


def test_canvas_invalid_rows_type_raises() -> None:
    """Non-list rows argument raises TypeError."""
    with pytest.raises(TypeError, match="rows must be a list"):
        FMEACanvas(rows={"id": 1})  # type: ignore[arg-type]


def test_canvas_initialization_with_rows_list() -> None:
    """Initializing FMEACanvas with a list of rows populates them."""
    row = FMEACanvasRow(
        id=1,
        process_step="Step",
        component="Comp",
        function="Func",
        failure_mode="Mode",
        effect="Effect",
        severity=5,
        cause="Cause",
        occurrence=5,
        current_control="Ctrl",
        detection=5,
    )
    canvas = FMEACanvas(
        rows=[
            row,
            {
                "id": 2,
                "process_step": "Step 2",
                "component": "Comp",
                "function": "Func",
                "failure_mode": "Mode",
                "effect": "Effect",
                "severity": 6,
                "cause": "Cause",
                "occurrence": 6,
                "current_control": "Ctrl",
                "detection": 6,
            },
        ]
    )
    assert len(canvas.rows) == 2
    assert canvas.get_row(1) is not None
    assert canvas.get_row(2) is not None


def test_canvas_load_sample_and_convenience_function() -> None:
    """load_sample and load_sample_canvas construct populated canvas instances."""
    canvas = FMEACanvas.load_sample()
    assert len(canvas.rows) == len(SAMPLE_FMEA_ROWS)
    assert len(canvas.rows) == 6

    # Verify deterministic scoring of sample rows
    row1 = canvas.get_row(1)
    assert row1 is not None
    assert row1.rpn == 160
    assert row1.action_priority == HIGH

    row2 = canvas.get_row(2)
    assert row2 is not None
    assert row2.rpn == 45
    assert row2.action_priority == MEDIUM

    row4 = canvas.get_row(4)
    assert row4 is not None
    assert row4.rpn == 48
    assert row4.action_priority == LOW

    # Convenience function parity
    canvas2 = load_sample_canvas()
    assert canvas2.to_dict() == canvas.to_dict()


def test_canvas_get_row_valid_and_missing() -> None:
    """get_row retrieves existing row or returns None."""
    canvas = FMEACanvas.load_sample()
    assert canvas.get_row(1) is not None
    assert canvas.get_row(999) is None

    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.get_row("1")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.get_row(True)  # type: ignore[arg-type]


def test_canvas_add_row_variants() -> None:
    """add_row accepts FMEACanvasRow instance and dicts."""
    canvas = FMEACanvas()

    # Add via dict
    r1 = canvas.add_row(
        {
            "id": 10,
            "process_step": "Test Step",
            "component": "Sensor",
            "function": "Sense",
            "failure_mode": "No signal",
            "effect": "Warning",
            "severity": 8,
            "cause": "Open circuit",
            "occurrence": 3,
            "current_control": "Continuity check",
            "detection": 2,
        }
    )
    assert r1.id == 10
    assert r1.action_priority == LOW
    assert len(canvas.rows) == 1

    # Add via FMEACanvasRow instance
    r2 = FMEACanvasRow(
        id=20,
        process_step="Step 2",
        component="Module",
        function="Compute",
        failure_mode="Freeze",
        effect="Loss",
        severity=10,
        cause="Watchdog timeout",
        occurrence=10,
        current_control="None",
        detection=10,
    )
    canvas.add_row(r2)
    assert len(canvas.rows) == 2

    # Duplicate ID raises ValueError
    with pytest.raises(ValueError, match="Row with ID 10 already exists in canvas."):
        canvas.add_row(r1)

    # Invalid type raises TypeError
    with pytest.raises(TypeError, match="row must be an FMEACanvasRow or dict"):
        canvas.add_row(["invalid"])  # type: ignore[arg-type]


def test_canvas_edit_row_and_recalculation() -> None:
    """edit_row updates text and recalculates RPN / Action Priority deterministically."""
    canvas = FMEACanvas.load_sample()

    # Row 6 is initially Severity 6, Occurrence 4, Detection 3 -> RPN 72, Low
    initial_row = canvas.get_row(6)
    assert initial_row is not None
    assert initial_row.rpn == 72
    assert initial_row.action_priority == LOW

    # Edit severity and occurrence to escalate risk to High
    updated = canvas.edit_row(6, severity=10, occurrence=10, detection=10)
    assert updated.severity == 10
    assert updated.occurrence == 10
    assert updated.detection == 10
    assert updated.rpn == 1000
    assert updated.action_priority == HIGH
    assert canvas.get_row(6) is updated

    # Edit text fields and PascalCase field names
    updated_text = canvas.edit_row(
        6,
        Process_Step="Updated Assembly",
        Failure_Mode="Catastrophic breakdown",
        AI_Candidate=True,
    )
    assert updated_text.process_step == "Updated Assembly"
    assert updated_text.failure_mode == "Catastrophic breakdown"
    assert updated_text.ai_candidate is True

    # Change row ID to unused ID
    moved = canvas.edit_row(6, id=60)
    assert moved.id == 60
    assert canvas.get_row(6) is None
    assert canvas.get_row(60) is not None

    # Change row ID to existing ID raises ValueError
    with pytest.raises(ValueError, match="Cannot change row ID to 1: ID already exists in canvas."):
        canvas.edit_row(60, id=1)

    # Unknown field raises ValueError
    with pytest.raises(ValueError, match="Unknown field 'unsupported_field' in row update"):
        canvas.edit_row(60, unsupported_field="bad")

    # Non-existent row raises KeyError
    with pytest.raises(KeyError, match="Row with ID 999 not found in canvas."):
        canvas.edit_row(999, severity=5)

    # Invalid row_id type raises TypeError
    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.edit_row("60", severity=5)  # type: ignore[arg-type]


def test_canvas_delete_row() -> None:
    """delete_row removes row and updates summary."""
    canvas = FMEACanvas.load_sample()
    assert len(canvas.rows) == 6

    deleted = canvas.delete_row(1)
    assert deleted.id == 1
    assert len(canvas.rows) == 5
    assert canvas.get_row(1) is None

    with pytest.raises(KeyError, match="Row with ID 1 not found in canvas."):
        canvas.delete_row(1)

    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.delete_row(False)  # type: ignore[arg-type]


def test_canvas_summary_metrics() -> None:
    """Verify summary counts, max RPN, and AI candidate metrics."""
    canvas = FMEACanvas.load_sample()
    summary = canvas.get_summary()

    assert summary["total_rows"] == 6
    assert summary["high_count"] == 2
    assert summary["medium_count"] == 2
    assert summary["low_count"] == 2
    assert summary["max_rpn"] == 480
    assert summary["ai_candidate_count"] == 1

    dict_repr = canvas.to_dict()
    assert dict_repr["title"] == canvas.title
    assert len(dict_repr["rows"]) == 6
    assert dict_repr["summary"] == summary


def test_canvas_to_html_standalone_and_embedded() -> None:
    """to_html produces well-formed standalone HTML5 and embedded markup."""
    canvas = FMEACanvas.load_sample(
        title="Custom <Automotive> FMEA",
        description="FMEA for & Testing 'quotes' & \"escapes\"",
    )

    # Standalone HTML dark theme
    html_dark = canvas.to_html(standalone=True, theme="dark")
    assert "<!DOCTYPE html>" in html_dark
    assert "<html lang=\"en\">" in html_dark
    assert "Custom &lt;Automotive&gt; FMEA" in html_dark
    assert "FMEA for &amp; Testing &#x27;quotes&#x27; &amp; &quot;escapes&quot;" in html_dark
    assert "AIAG &amp; VDA 2019" in html_dark
    assert "[AI Candidate]" in html_dark
    assert "Verified" in html_dark
    assert "High" in html_dark
    assert "Medium" in html_dark
    assert "Low" in html_dark
    assert "Total Items" in html_dark
    assert "Max RPN" in html_dark

    # Embedded HTML light theme
    html_light = canvas.to_html(standalone=False, theme="light")
    assert "<!DOCTYPE html>" not in html_light
    assert "<div class=\"qes-fmea-canvas\"" in html_light
    assert "background-color:#ffffff" in html_light or "background-color:#f8fafc" in html_light


def test_canvas_to_html_empty_rows_state() -> None:
    """to_html renders empty state row when no rows exist."""
    canvas = FMEACanvas()
    html_out = canvas.to_html(standalone=False)
    assert "No FMEA items recorded in canvas." in html_out
    assert "Total Items" in html_out


def test_canvas_to_html_invalid_arguments_raise() -> None:
    """to_html validates standalone and theme arguments."""
    canvas = FMEACanvas()
    with pytest.raises(TypeError, match="standalone must be a boolean"):
        canvas.to_html(standalone="true")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="theme must be 'dark' or 'light'"):
        canvas.to_html(theme="solarized")


# ---------------------------------------------------------------------------
# SPCCanvas & SPCCanvasSubgroup Unit Tests
# ---------------------------------------------------------------------------


def test_spc_canvas_init_valid_sample() -> None:
    """Test default construction and load_sample for SPCCanvas."""
    assert len(SAMPLE_SPC_XBAR_R_DATA) == 20
    subgroup = SPCCanvasSubgroup(id=1, values=[10.1, 10.0])
    assert subgroup.to_dict()["id"] == 1
    assert subgroup.to_dict()["values"] == [10.1, 10.0]

    canvas = SPCCanvas.load_sample(title="Engine Shaft Diameters", usl=10.5, lsl=9.5)
    assert canvas.title == "Engine Shaft Diameters"
    assert canvas.chart_type == "Xbar-R"
    assert len(canvas.subgroups) == 20
    assert len(canvas.points) == 20
    assert canvas.in_control is True
    assert canvas.stable is True
    assert canvas.violations == []
    assert canvas.capability is not None
    assert canvas.capability["cp"] > 1.0
    assert canvas.capability["cpk"] > 1.0

    helper_canvas = load_sample_spc_canvas()
    assert helper_canvas.title == "AIAG SPC Control Chart Canvas"
    assert len(helper_canvas.subgroups) == 20


def test_spc_canvas_init_invalid() -> None:
    """SPCCanvas validates title, chart_type, and spec limits on init."""
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        SPCCanvas(title="")

    with pytest.raises(ValueError, match="title must be a non-empty string"):
        SPCCanvas(title=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Unknown or unsupported chart_type"):
        SPCCanvas(chart_type="NonexistentChart")

    with pytest.raises(ValueError, match="USL cannot be less than LSL"):
        SPCCanvas(usl=9.0, lsl=10.0)


def test_spc_canvas_set_data_supported_charts() -> None:
    """SPCCanvas supports Xbar-R, Xbar-S, I-MR, p, c, and u charts."""
    # Xbar-S
    canvas_xs = SPCCanvas(chart_type="Xbar-S", usl=11.0, lsl=9.0)
    canvas_xs.set_data([[10.0, 10.1, 9.9, 10.0], [10.1, 10.0, 10.2, 9.9]])
    assert canvas_xs.in_control is True
    assert len(canvas_xs.points) == 2
    assert canvas_xs.dispersion_center > 0

    # I-MR
    canvas_imr = SPCCanvas(chart_type="I-MR", usl=12.0, lsl=8.0)
    canvas_imr.set_data([10.0, 10.2, 9.8, 10.1, 9.9])
    assert canvas_imr.in_control is True
    assert len(canvas_imr.points) == 5
    assert canvas_imr.capability is not None

    # p chart
    canvas_p = SPCCanvas(chart_type="p", sample_sizes=[100.0, 100.0, 100.0])
    canvas_p.set_data([2.0, 3.0, 1.0])
    assert canvas_p.in_control is True
    assert len(canvas_p.points) == 3

    # c chart
    canvas_c = SPCCanvas(chart_type="c")
    canvas_c.set_data([5.0, 4.0, 6.0, 3.0])
    assert canvas_c.in_control is True
    assert len(canvas_c.points) == 4

    # u chart
    canvas_u = SPCCanvas(chart_type="u", sample_sizes=[10.0, 10.0, 10.0])
    canvas_u.set_data([2.0, 3.0, 1.0])
    assert canvas_u.in_control is True
    assert len(canvas_u.points) == 3


def test_spc_canvas_set_data_invalid() -> None:
    """SPCCanvas validates input dimensions, sizes, and requirements."""
    canvas_xr = SPCCanvas(chart_type="Xbar-R")

    # 1D data to Xbar-R
    with pytest.raises(ValueError, match="requires data as a list of subgroups"):
        canvas_xr.set_data([10.0, 10.1])  # type: ignore[arg-type]

    # Ragged subgroups
    with pytest.raises(ValueError, match="All subgroups in Xbar-R chart must have equal size"):
        canvas_xr.set_data([[10.0, 10.1], [10.0, 10.1, 10.2]])

    # Subgroup size n=1 for Xbar-R
    with pytest.raises(ValueError, match="subgroup size between 2 and 10"):
        canvas_xr.set_data([[10.0], [10.1]])

    # Subgroup size n=11 for Xbar-R
    with pytest.raises(ValueError, match="subgroup size between 2 and 10"):
        canvas_xr.set_data([[10.0] * 11, [10.1] * 11])

    # Xbar-S subgroup size n=13
    canvas_xs = SPCCanvas(chart_type="Xbar-S")
    with pytest.raises(ValueError, match="subgroup size between 2 and 12"):
        canvas_xs.set_data([[10.0] * 13, [10.1] * 13])

    # 2D data to I-MR
    canvas_imr = SPCCanvas(chart_type="I-MR")
    with pytest.raises(ValueError, match="requires data as a 1D list of values"):
        canvas_imr.set_data([[10.0, 10.1], [9.9, 10.0]])  # type: ignore[arg-type]

    # I-MR less than 2 values
    with pytest.raises(ValueError, match="requires at least two values"):
        canvas_imr.set_data([10.0])

    # p chart missing sample_sizes
    canvas_p = SPCCanvas(chart_type="p")
    with pytest.raises(ValueError, match="p chart requires sample_sizes"):
        canvas_p.set_data([2.0, 3.0])


def test_spc_canvas_single_writer_edit_subgroup() -> None:
    """SPCCanvas.edit_subgroup modifies data deterministically and recalculates."""
    canvas = SPCCanvas.load_sample(title="Editable Canvas")
    original_mean_0 = canvas.points[0]

    # Edit subgroup 0
    canvas.edit_subgroup(0, [10.5, 10.5, 10.5, 10.5, 10.5])
    assert canvas.points[0] == 10.5
    assert canvas.points[0] != original_mean_0
    assert canvas.subgroups[0].point_value == 10.5

    # Index out of range
    with pytest.raises(IndexError, match="out of range"):
        canvas.edit_subgroup(99, [10.0, 10.0, 10.0, 10.0, 10.0])

    # Empty new_values
    with pytest.raises(ValueError, match="non-empty list"):
        canvas.edit_subgroup(0, [])

    # Subgroup length mismatch
    with pytest.raises(ValueError, match="Subgroup size mismatch"):
        canvas.edit_subgroup(0, [10.0, 10.0])

    # Edit subgroup on 1D chart
    canvas_imr = SPCCanvas(chart_type="I-MR", data=[10.0, 10.1, 9.9])
    with pytest.raises(TypeError, match="edit_subgroup is for 2D charts"):
        canvas_imr.edit_subgroup(0, [10.0])


def test_spc_canvas_single_writer_edit_point() -> None:
    """SPCCanvas.edit_point modifies 1D observation and recalculates."""
    canvas = SPCCanvas(chart_type="I-MR", data=[10.0, 10.1, 9.9])
    canvas.edit_point(1, 10.5)
    assert canvas.points[1] == 10.5
    assert canvas.subgroups[1].point_value == 10.5

    with pytest.raises(IndexError, match="out of range"):
        canvas.edit_point(10, 10.0)

    canvas_xr = SPCCanvas.load_sample()
    with pytest.raises(TypeError, match="edit_point is for 1D charts"):
        canvas_xr.edit_point(0, 10.0)


def test_spc_canvas_stability_gate_suppresses_capability() -> None:
    """SPCCanvas strictly suppresses capability when process has out-of-control signals."""
    # Out of control dataset (severe outlier)
    ooc_data = [
        [10.0, 10.1, 9.9, 10.0, 10.1],
        [10.0, 10.0, 10.1, 9.9, 10.0],
        [10.1, 9.9, 10.0, 10.1, 10.0],
        [10.0, 10.1, 10.0, 9.9, 10.0],
        [10.0, 10.0, 10.0, 10.1, 10.0],
        [15.0, 15.0, 15.0, 15.0, 15.0],  # Outlier
    ]
    canvas = SPCCanvas(chart_type="Xbar-R", usl=12.0, lsl=8.0, data=ooc_data)
    assert canvas.in_control is False
    assert canvas.stable is False
    assert len(canvas.violations) > 0
    assert canvas.stability_note is not None
    assert canvas.capability is None

    # Verify HTML renders stability notice
    html_out = canvas.to_html(standalone=False)
    assert "OUT OF CONTROL" in html_out
    assert "Stability Gate Notice" in html_out


def test_spc_canvas_to_dict_and_summary() -> None:
    """SPCCanvas to_dict and get_summary serialize complete state."""
    canvas = SPCCanvas.load_sample(usl=11.0, lsl=9.0)
    summary = canvas.get_summary()
    assert summary["title"] == canvas.title
    assert summary["chart_type"] == "Xbar-R"
    assert summary["in_control"] is True
    assert summary["violations_count"] == 0
    assert summary["capability"] is not None

    state_dict = canvas.to_dict()
    assert len(state_dict["subgroups"]) == 20
    assert state_dict["subgroups"][0]["id"] == 1
    assert "values" in state_dict["subgroups"][0]


def test_spc_canvas_to_html_standalone_and_embedded() -> None:
    """SPCCanvas to_html produces standalone HTML5 document and embedded container."""
    canvas = SPCCanvas.load_sample(title="Piston Pin Diameters & Specs")

    # Standalone HTML
    html_doc = canvas.to_html(standalone=True)
    assert "<!DOCTYPE html>" in html_doc
    assert "<html lang=\"en\">" in html_doc
    assert "Piston Pin Diameters &amp; Specs" in html_doc
    assert "<svg" in html_doc
    assert "UCL" in html_doc
    assert "LCL" in html_doc
    assert "CL" in html_doc
    assert "Cp" in html_doc
    assert "Cpk" in html_doc

    # Embedded HTML
    html_embed = canvas.to_html(standalone=False)
    assert "<!DOCTYPE html>" not in html_embed
    assert "Primary Control Chart View" in html_embed

    # Empty data canvas
    empty_canvas = SPCCanvas()
    empty_html = empty_canvas.to_html(standalone=False)
    assert "No data to display." in empty_html


def test_spc_canvas_set_data_with_sample_sizes_and_empty_recalculate() -> None:
    """Test set_data updating sample_sizes on initialized canvas and empty data recalculation."""
    canvas = SPCCanvas(chart_type="p")
    # Calling _recalculate with no data
    canvas._recalculate()
    assert canvas.data == []

    # Updating data with explicit sample_sizes in set_data
    canvas.set_data([3.0, 4.0, 2.0], sample_sizes=[50.0, 50.0, 50.0])
    assert canvas.sample_sizes == [50.0, 50.0, 50.0]
    assert len(canvas.points) == 3


def test_spc_canvas_svg_edge_cases_flat_and_single_point_and_many_points() -> None:
    """Test SVG generation when dataset is flat, has 1 point, or has > 25 points."""
    # Flat dataset (constant values)
    flat_data = [[10.0, 10.0], [10.0, 10.0]]
    flat_canvas = SPCCanvas(chart_type="Xbar-R", data=flat_data)
    flat_html = flat_canvas.to_html()
    assert "<svg" in flat_html

    # Single subgroup (2D)
    single_canvas = SPCCanvas(chart_type="Xbar-R", data=[[10.0, 10.1]])
    single_html = single_canvas.to_html()
    assert "<svg" in single_html

    # Single observation (1D)
    single_1d_canvas = SPCCanvas(chart_type="c", data=[5.0])
    single_1d_html = single_1d_canvas.to_html()
    assert "<svg" in single_1d_html

    # More than 25 points to test x-axis label skipping
    many_pts = [10.0 + (i % 3) * 0.1 for i in range(35)]
    many_canvas = SPCCanvas(chart_type="I-MR", data=many_pts)
    many_html = many_canvas.to_html()
    assert "<svg" in many_html


def test_spc_canvas_nelson_and_one_sided_specs() -> None:
    """Test SPCCanvas with Nelson rules and one-sided specification limits."""
    # Nelson rule set on sample data triggers Nelson Rule 7 (stratification) -> capability withheld
    nelson_canvas = SPCCanvas(chart_type="Xbar-R", rule_set="Nelson", usl=11.0, data=SAMPLE_SPC_XBAR_R_DATA)
    assert nelson_canvas.rule_set == "Nelson"
    assert nelson_canvas.in_control is False
    assert len(nelson_canvas.violations) > 0
    assert nelson_canvas.capability is None

    # Nelson on clean in-control data -> capability calculated
    clean_nelson = SPCCanvas(chart_type="I-MR", rule_set="Nelson", usl=12.0, lsl=8.0, data=[10.0, 10.2, 9.8, 10.1, 9.9, 10.0])
    assert clean_nelson.in_control is True
    assert clean_nelson.capability is not None
    assert clean_nelson.capability["cpk"] is not None

    # LSL only
    lsl_canvas = SPCCanvas(chart_type="I-MR", lsl=8.0, data=[10.0, 10.2, 9.8, 10.1])
    assert lsl_canvas.capability is not None
    assert lsl_canvas.capability["cpk"] is not None


# ---------------------------------------------------------------------------
# MSACanvasMeasurement & MSACanvas Unit Tests
# ---------------------------------------------------------------------------


def test_msa_canvas_measurement_valid_and_to_dict() -> None:
    """MSACanvasMeasurement constructs correctly and serializes to dict."""
    m = MSACanvasMeasurement(id=1, part="P01", appraiser="A", trial=1, measurement=0.29)
    assert m.id == 1
    assert m.part == "P01"
    assert m.appraiser == "A"
    assert m.trial == 1
    assert m.measurement == 0.29
    d = m.to_dict()
    assert d == {"id": 1, "part": "P01", "appraiser": "A", "trial": 1, "measurement": 0.29}


def test_msa_canvas_measurement_from_dict_variations() -> None:
    """from_dict handles snake_case, PascalCase, and alternate key aliases."""
    # Standard snake_case
    m1 = MSACanvasMeasurement.from_dict({"id": 5, "part": "P02", "appraiser": "B", "trial": 2, "measurement": 1.45})
    assert m1.id == 5
    assert m1.part == "P02"
    assert m1.appraiser == "B"
    assert m1.trial == 2
    assert m1.measurement == 1.45

    # PascalCase & value alias
    m2 = MSACanvasMeasurement.from_dict({"ID": "10", "Part": "P03", "Appraiser": "C", "Trial": "3", "value": "2.5"})
    assert m2.id == 10
    assert m2.part == "P03"
    assert m2.appraiser == "C"
    assert m2.trial == 3
    assert m2.measurement == 2.5


@pytest.mark.parametrize(
    ("invalid_dict", "expected_err", "match_str"),
    [
        ("not-a-dict", TypeError, "Expected dict"),
        ({"id": "bad-id"}, ValueError, "Invalid measurement id"),
        ({"part": ""}, ValueError, "missing or empty 'part'"),
        ({"part": "P1", "appraiser": ""}, ValueError, "missing or empty 'appraiser'"),
        ({"part": "P1", "appraiser": "A", "trial": "zero"}, ValueError, "Trial must be a positive integer"),
        ({"part": "P1", "appraiser": "A", "trial": 0}, ValueError, "Trial must be a positive integer"),
        ({"part": "P1", "appraiser": "A", "trial": 1, "measurement": "invalid"}, ValueError, "Invalid measurement numeric value"),
    ],
)
def test_msa_canvas_measurement_from_dict_errors(
    invalid_dict: Any,
    expected_err: type[Exception],
    match_str: str,
) -> None:
    """Invalid dictionaries raise ValueError or TypeError in MSACanvasMeasurement.from_dict."""
    with pytest.raises(expected_err, match=match_str):
        MSACanvasMeasurement.from_dict(invalid_dict)


def test_msa_canvas_initialization_and_validation() -> None:
    """MSACanvas initialization validates title, method, and tolerance."""
    canvas = MSACanvas(method="anova", title="Custom Title", tolerance=5.0)
    assert canvas.title == "Custom Title"
    assert canvas.method == "anova"
    assert canvas.tolerance == 5.0

    # Invalid title
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        MSACanvas(title="")
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        MSACanvas(title=True)  # type: ignore[arg-type]

    # Invalid method
    with pytest.raises(ValueError, match="Unknown or unsupported method"):
        MSACanvas(method="invalid_method")

    # Invalid tolerance
    with pytest.raises(ValueError, match="tolerance must be a positive finite float"):
        MSACanvas(tolerance=-1.0)
    with pytest.raises(ValueError, match="tolerance must be a positive finite float"):
        MSACanvas(tolerance=0.0)
    with pytest.raises(ValueError, match="tolerance must be a positive finite float"):
        MSACanvas(tolerance=True)  # type: ignore[arg-type]


def test_msa_canvas_load_sample_and_convenience_helper() -> None:
    """load_sample and load_sample_msa_canvas load the 90-row AIAG benchmark dataset."""
    assert len(SAMPLE_MSA_STUDY_DATA) == 90
    canvas = MSACanvas.load_sample()
    assert len(canvas.measurements) == 90
    assert canvas.n_parts == 10
    assert canvas.n_appraisers == 3
    assert canvas.n_trials == 3
    assert canvas.verdict == "Reject"
    assert canvas.ndc == 6
    assert pytest.approx(canvas.grr, rel=1e-3) == 0.225791

    canvas_helper = load_sample_msa_canvas(method="average_and_range", title="A&R Study", tolerance=4.42)
    assert canvas_helper.title == "A&R Study"
    assert canvas_helper.method == "average_and_range"
    assert len(canvas_helper.measurements) == 90
    assert canvas_helper.verdict == "Reject"
    assert canvas_helper.ndc == 6
    assert pytest.approx(canvas_helper.grr, rel=1e-3) == 0.226378


def test_msa_canvas_single_writer_crud_lifecycle() -> None:
    """MSACanvas single-writer CRUD: add, update, delete, set_data, and recalculate."""
    # Synthetic Example B (3 parts x 2 appraisers x 2 trials)
    example_b: list[dict[str, Any]] = [
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

    canvas = MSACanvas(method="anova", tolerance=8.0)
    assert len(canvas.measurements) == 0
    assert canvas.verdict == "Pending"

    # set_data with dict list
    canvas.set_data(example_b)
    assert len(canvas.measurements) == 12
    assert canvas.n_parts == 3
    assert canvas.verdict == "Marginal"

    # set_data with MSACanvasMeasurement list
    meas_objs = [MSACanvasMeasurement(id=i, part=r["part"], appraiser=r["appraiser"], trial=r["trial"], measurement=r["measurement"]) for i, r in enumerate(example_b, 1)]
    canvas.set_data(meas_objs)
    assert len(canvas.measurements) == 12

    # set_data invalid type
    with pytest.raises(TypeError, match="measurements must be a list"):
        canvas.set_data("invalid")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Expected dict or MSACanvasMeasurement"):
        canvas.set_data([123])  # type: ignore[list-item]

    # update_measurement
    grr_before = canvas.grr
    updated = canvas.update_measurement(1, measurement=3.5, part="P1", appraiser="A", trial=1)
    assert updated.measurement == 3.5
    assert canvas.grr != grr_before

    # update_measurement errors
    with pytest.raises(KeyError, match="Measurement with id=999 not found"):
        canvas.update_measurement(999, measurement=3.0)
    with pytest.raises(ValueError, match="Invalid numeric measurement"):
        canvas.update_measurement(1, measurement="bad-float")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="part cannot be empty"):
        canvas.update_measurement(1, part="")
    with pytest.raises(ValueError, match="appraiser cannot be empty"):
        canvas.update_measurement(1, appraiser="")
    with pytest.raises(ValueError, match="trial must be a positive integer"):
        canvas.update_measurement(1, trial=0)

    # delete_measurement
    assert canvas.delete_measurement(1) is True
    assert canvas.delete_measurement(999) is False

    # add_measurement (MSACanvasMeasurement and dict)
    new_m = canvas.add_measurement({"part": "P1_mod", "appraiser": "A_mod", "trial": 1, "measurement": 2.0})
    assert new_m.id > 0
    new_obj = canvas.add_measurement(MSACanvasMeasurement(id=0, part="P1_mod", appraiser="A_mod", trial=1, measurement=2.1))
    assert new_obj.id > new_m.id

    with pytest.raises(TypeError, match="Expected dict or MSACanvasMeasurement"):
        canvas.add_measurement("bad-input")  # type: ignore[arg-type]


def test_msa_canvas_summary_and_to_dict() -> None:
    """get_summary and to_dict provide full serializable summaries."""
    canvas = MSACanvas.load_sample()
    summary = canvas.get_summary()
    assert summary["title"] == "AIAG MSA Gage R&R Canvas"
    assert summary["method"] == "anova"
    assert summary["measurements_count"] == 90
    assert summary["n_parts"] == 10
    assert summary["verdict"] == "Reject"

    d = canvas.to_dict()
    assert d["title"] == "AIAG MSA Gage R&R Canvas"
    assert len(d["measurements"]) == 90
    assert d["summary"] == summary


def test_msa_canvas_html_rendering_and_verdict_styles() -> None:
    """to_html generates valid HTML5 and covers Accept, Marginal, Reject, and Pending styles."""
    # 1. Reject verdict (Sample dataset)
    sample_canvas = MSACanvas.load_sample(tolerance=4.42)
    sample_html = sample_canvas.to_html(standalone=True)
    assert "<!DOCTYPE html>" in sample_html
    assert "REJECT" in sample_html
    assert "Operator × Part Interaction Plot" in sample_html
    assert "Variance Component Breakdown" in sample_html
    assert "<svg" in sample_html

    # 2. Embedded HTML (standalone=False)
    embedded_html = sample_canvas.to_html(standalone=False)
    assert "<!DOCTYPE html>" not in embedded_html
    assert '<div class="msa-canvas-container"' in embedded_html

    # 3. Marginal verdict (Example B)
    example_b = [
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
    marginal_canvas = MSACanvas(method="anova", tolerance=8.0, measurements=example_b)
    marginal_html = marginal_canvas.to_html()
    assert "MARGINAL" in marginal_html

    # 4. Accept verdict (High part spread, tiny measurement noise)
    accept_data = [
        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.00},
        {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.01},
        {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.00},
        {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 10.01},
        {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 20.00},
        {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 20.01},
        {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 20.00},
        {"part": "P2", "appraiser": "B", "trial": 2, "measurement": 20.01},
        {"part": "P3", "appraiser": "A", "trial": 1, "measurement": 30.00},
        {"part": "P3", "appraiser": "A", "trial": 2, "measurement": 30.01},
        {"part": "P3", "appraiser": "B", "trial": 1, "measurement": 30.00},
        {"part": "P3", "appraiser": "B", "trial": 2, "measurement": 30.01},
    ]
    accept_canvas = MSACanvas(method="anova", tolerance=50.0, measurements=accept_data)
    assert accept_canvas.verdict == "Accept"
    accept_html = accept_canvas.to_html()
    assert "ACCEPT" in accept_html

    # 5. Pending / Empty canvas HTML
    empty_canvas = MSACanvas(method="anova")
    empty_html = empty_canvas.to_html()
    assert "PENDING" in empty_html
    assert "No measurement data" in empty_html


def test_msa_canvas_svg_edge_cases_and_non_zero_interaction() -> None:
    """Test SVG generation when dataset has non-zero interaction, flat values, or single part."""
    # Non-zero interaction dataset
    int_data = [
        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 1.0},
        {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 1.1},
        {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 5.0},
        {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 5.1},
        {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 5.0},
        {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 5.1},
        {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 1.0},
        {"part": "P2", "appraiser": "B", "trial": 2, "measurement": 1.1},
    ]
    int_canvas = MSACanvas(method="anova", tolerance=10.0, measurements=int_data)
    assert int_canvas.interaction_significant is True
    int_html = int_canvas.to_html()
    assert "Interaction: Significant" in int_html
    assert "Part × Appraiser (INT)" in int_html

    # Flat values
    flat_data = [
        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.0},
        {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.0},
        {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 10.0},
        {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 10.0},
        {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 10.0},
        {"part": "P2", "appraiser": "B", "trial": 2, "measurement": 10.0},
    ]
    flat_canvas = MSACanvas(method="average_and_range", measurements=flat_data)
    flat_html = flat_canvas.to_html()
    assert "<svg" in flat_html

    # Empty canvas recalculate
    empty_canvas = MSACanvas()
    empty_canvas.recalculate()
    assert empty_canvas.verdict == "Pending"
    assert empty_canvas.measurements == []

    # Update measurement with trial=None
    sample_c = MSACanvas.load_sample()
    updated = sample_c.update_measurement(1, measurement=0.42)
    assert updated.measurement == 0.42
    assert updated.trial == 1

    # Sparse / single-point appraiser SVG branch coverage
    sparse_canvas = MSACanvas(
        measurements=[
            {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 1.0},
            {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 2.0},
        ]
    )
    sparse_html = sparse_canvas.to_html()
    assert "<svg" in sparse_html


# ---------------------------------------------------------------------------
# ControlPlanCanvasRow Unit Tests
# ---------------------------------------------------------------------------


def test_controlplan_row_valid_construction() -> None:
    """Instantiate a valid ControlPlanCanvasRow with full and minimal parameters."""
    # Full parameters
    row_full = ControlPlanCanvasRow(
        id=1,
        characteristic="Bore diameter",
        measurement_method="Air gage",
        sample_size=5,
        frequency="hourly",
        reaction_plan="Adjust tool offset and re-measure",
        lsl=10.0,
        usl=10.5,
        target=10.25,
        recommended_chart="Xbar-R",
        source_cause_id="1::1::1-C1",
        sample_plan_is_placeholder=False,
        validation_status="valid",
        findings=[],
    )
    assert row_full.id == 1
    assert row_full.characteristic == "Bore diameter"
    assert row_full.lsl == 10.0
    assert row_full.usl == 10.5
    assert row_full.target == 10.25
    assert row_full.recommended_chart == "Xbar-R"
    assert row_full.source_cause_id == "1::1::1-C1"
    assert row_full.sample_plan_is_placeholder is False
    assert row_full.validation_status == "valid"
    assert row_full.findings == []

    # Minimal parameters
    row_min = ControlPlanCanvasRow(
        id=2,
        characteristic="Weld bead width",
        measurement_method="Visual inspection",
        sample_size=1,
        frequency="per shift",
        reaction_plan="Stop line and quarantine batch",
    )
    assert row_min.id == 2
    assert row_min.lsl is None
    assert row_min.usl is None
    assert row_min.target is None
    assert row_min.recommended_chart is None
    assert row_min.source_cause_id is None
    assert row_min.sample_plan_is_placeholder is False
    assert row_min.validation_status == "valid"
    assert row_min.findings == []


def test_controlplan_row_to_dict_and_from_dict_snake_case() -> None:
    """to_dict and from_dict roundtrip with snake_case keys."""
    data = {
        "id": 3,
        "characteristic": "Coating thickness",
        "measurement_method": "Magnetic eddy current",
        "sample_size": 3,
        "frequency": "per roll",
        "reaction_plan": "Adjust coater speed",
        "lsl": 20.0,
        "usl": 30.0,
        "target": 25.0,
        "recommended_chart": "Xbar-S",
        "source_cause_id": "3::1::1-C1",
        "sample_plan_is_placeholder": False,
        "validation_status": "valid",
        "findings": [],
    }
    row = ControlPlanCanvasRow.from_dict(data)
    assert row.id == 3
    assert row.characteristic == "Coating thickness"
    assert row.recommended_chart == "Xbar-S"
    assert row.to_dict() == data


def test_controlplan_row_from_dict_pascal_case() -> None:
    """from_dict parses PascalCase keys correctly."""
    data = {
        "ID": 4,
        "Characteristic": "Crimping pull force",
        "Measurement_Method": "Tensile pull tester",
        "Sample_Size": 10,
        "Frequency": "per lot",
        "Reaction_Plan": "Quarantine lot and notify QA",
        "LSL": 50.0,
        "USL": 100.0,
        "Target": 75.0,
        "Recommended_Chart": "p",
        "Source_Cause_ID": "4::1::2-C1",
        "Sample_Plan_Is_Placeholder": False,
        "Validation_Status": "valid",
        "Findings": ["Initial review ok."],
    }
    row = ControlPlanCanvasRow.from_dict(data)
    assert row.id == 4
    assert row.characteristic == "Crimping pull force"
    assert row.measurement_method == "Tensile pull tester"
    assert row.sample_size == 10
    assert row.frequency == "per lot"
    assert row.reaction_plan == "Quarantine lot and notify QA"
    assert row.lsl == 50.0
    assert row.usl == 100.0
    assert row.target == 75.0
    assert row.recommended_chart == "p"
    assert row.source_cause_id == "4::1::2-C1"
    assert row.findings == ["Initial review ok."]


def test_controlplan_row_from_dict_enum_and_defaults() -> None:
    """from_dict handles recommended_chart with .value attribute and default fields."""
    class ChartEnum:
        value = "I-MR"

    data = {
        "id": 5,
        "characteristic": "Voltage output",
        "measurement_method": "DMM",
        "sample_size": 1,
        "frequency": "continuous",
        "reaction_plan": "Isolate circuit",
        "recommended_chart": ChartEnum(),
    }
    row = ControlPlanCanvasRow.from_dict(data)
    assert row.recommended_chart == "I-MR"
    assert row.lsl is None
    assert row.usl is None
    assert row.target is None
    assert row.source_cause_id is None
    assert row.sample_plan_is_placeholder is False
    assert row.validation_status == "valid"
    assert row.findings == []


def test_controlplan_row_from_dict_errors() -> None:
    """from_dict raises TypeError on non-dict and ValueError on missing required fields."""
    with pytest.raises(TypeError, match="data must be a dictionary"):
        ControlPlanCanvasRow.from_dict(["not a dict"])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Missing required field 'id' or 'ID'"):
        ControlPlanCanvasRow.from_dict({"characteristic": "Test", "measurement_method": "M", "sample_size": 1, "frequency": "F", "reaction_plan": "R"})

    with pytest.raises(ValueError, match="Missing required field 'characteristic' or 'Characteristic'"):
        ControlPlanCanvasRow.from_dict({"id": 1, "measurement_method": "M", "sample_size": 1, "frequency": "F", "reaction_plan": "R"})


def test_controlplan_row_placeholder_derivation() -> None:
    """Automatic finding and status derivation when sample_plan_is_placeholder=True."""
    # When status is "valid", flips to "placeholder" and appends finding
    row1 = ControlPlanCanvasRow(
        id=1,
        characteristic="Characteristic 1",
        measurement_method="Method",
        sample_size=1,
        frequency="hourly",
        reaction_plan="Reaction",
        sample_plan_is_placeholder=True,
    )
    assert row1.validation_status == "placeholder"
    assert "Sample plan contains placeholder values." in row1.findings

    # When finding already present, does not duplicate
    row2 = ControlPlanCanvasRow(
        id=2,
        characteristic="Characteristic 2",
        measurement_method="Method",
        sample_size=1,
        frequency="hourly",
        reaction_plan="Reaction",
        sample_plan_is_placeholder=True,
        findings=["Sample plan contains placeholder values."],
    )
    assert row2.findings.count("Sample plan contains placeholder values.") == 1

    # When status is "warning", preserves status
    row3 = ControlPlanCanvasRow(
        id=3,
        characteristic="Characteristic 3",
        measurement_method="Method",
        sample_size=1,
        frequency="hourly",
        reaction_plan="Reaction",
        sample_plan_is_placeholder=True,
        validation_status="warning",
    )
    assert row3.validation_status == "warning"
    assert "Sample plan contains placeholder values." in row3.findings


def test_controlplan_row_whitespace_stripping_and_source_cause_coercion() -> None:
    """String fields are stripped and blank source_cause_id is coerced to None."""
    row = ControlPlanCanvasRow(
        id=1,
        characteristic="  Bore diameter  ",
        measurement_method="  Air gage  ",
        sample_size=5,
        frequency="  hourly  ",
        reaction_plan="  Adjust tool  ",
        source_cause_id="   ",
    )
    assert row.characteristic == "Bore diameter"
    assert row.measurement_method == "Air gage"
    assert row.frequency == "hourly"
    assert row.reaction_plan == "Adjust tool"
    assert row.source_cause_id is None


@pytest.mark.parametrize(
    ("field_name", "kwargs", "expected_err", "match_str"),
    [
        ("id", {"id": "1"}, TypeError, "id must be an integer"),
        ("id_bool", {"id": True}, TypeError, "id must be an integer"),
        ("id_neg", {"id": 0}, ValueError, "id must be a positive integer"),
        ("char_type", {"characteristic": 123}, TypeError, "characteristic must be a string"),
        ("char_empty", {"characteristic": "   "}, ValueError, "characteristic must be a non-empty string"),
        ("method_type", {"measurement_method": None}, TypeError, "measurement_method must be a string"),
        ("method_empty", {"measurement_method": ""}, ValueError, "measurement_method must be a non-empty string"),
        ("freq_type", {"frequency": False}, TypeError, "frequency must be a string"),
        ("freq_empty", {"frequency": "  "}, ValueError, "frequency must be a non-empty string"),
        ("react_type", {"reaction_plan": 456}, TypeError, "reaction_plan must be a string"),
        ("react_empty", {"reaction_plan": ""}, ValueError, "reaction_plan must be a non-empty string"),
        ("sample_size_type", {"sample_size": "5"}, TypeError, "sample_size must be an integer"),
        ("sample_size_bool", {"sample_size": True}, TypeError, "sample_size must be an integer"),
        ("sample_size_val", {"sample_size": 0}, ValueError, "sample_size must be >= 1"),
        ("placeholder_type", {"sample_plan_is_placeholder": "yes"}, TypeError, "sample_plan_is_placeholder must be a boolean"),
        ("source_cause_type", {"source_cause_id": 123}, TypeError, "source_cause_id must be a string or None"),
        ("lsl_type", {"lsl": "low"}, TypeError, "lsl must be a float or None"),
        ("lsl_bool", {"lsl": True}, TypeError, "lsl must be a float or None"),
        ("usl_type", {"usl": "high"}, TypeError, "usl must be a float or None"),
        ("target_type", {"target": "mid"}, TypeError, "target must be a float or None"),
        ("lsl_nan", {"lsl": float("nan")}, ValueError, "lsl cannot be NaN or Inf"),
        ("usl_inf", {"usl": float("inf")}, ValueError, "usl cannot be NaN or Inf"),
        ("target_neginf", {"target": float("-inf")}, ValueError, "target cannot be NaN or Inf"),
        ("usl_le_lsl", {"lsl": 10.0, "usl": 5.0}, ValueError, "usl must be greater than lsl"),
        ("usl_eq_lsl", {"lsl": 10.0, "usl": 10.0}, ValueError, "usl must be greater than lsl"),
        ("target_lt_lsl", {"lsl": 10.0, "usl": 20.0, "target": 9.0}, ValueError, "target cannot be less than lsl"),
        ("target_gt_usl", {"lsl": 10.0, "usl": 20.0, "target": 21.0}, ValueError, "target cannot be greater than usl"),
        ("chart_type", {"recommended_chart": 123}, TypeError, "recommended_chart must be a string or None"),
        ("chart_val", {"recommended_chart": "invalid_chart"}, ValueError, "Invalid recommended_chart 'invalid_chart'"),
        ("findings_type", {"findings": "not a list"}, TypeError, "findings must be a list"),
        ("status_type", {"validation_status": 123}, TypeError, "validation_status must be a string"),
    ],
)
def test_controlplan_row_validation_errors(
    field_name: str,
    kwargs: dict[str, Any],
    expected_err: type[Exception],
    match_str: str,
) -> None:
    """Invalid parameter types and values raise descriptive Type/ValueError."""
    base_kwargs: dict[str, Any] = {
        "id": 1,
        "characteristic": "Characteristic",
        "measurement_method": "Method",
        "sample_size": 5,
        "frequency": "hourly",
        "reaction_plan": "Reaction",
    }
    base_kwargs.update(kwargs)
    with pytest.raises(expected_err, match=match_str):
        ControlPlanCanvasRow(**base_kwargs)


# ---------------------------------------------------------------------------
# ControlPlanCanvas Controller Unit Tests
# ---------------------------------------------------------------------------


def test_controlplan_canvas_initialization() -> None:
    """Initialize ControlPlanCanvas with defaults, custom metadata, and rows."""
    # Default init
    canvas_default = ControlPlanCanvas()
    assert canvas_default.title == "AIAG APQP Control Plan Matrix Canvas"
    assert canvas_default.description == "Interactive single-writer visual Control Plan canvas with validation findings."
    assert canvas_default.rows == []

    # Custom metadata and rows
    row1 = ControlPlanCanvasRow(
        id=1,
        characteristic="Length",
        measurement_method="Caliper",
        sample_size=3,
        frequency="per hour",
        reaction_plan="Adjust cutter",
        source_cause_id="1::1::1-C1",
    )
    row2_dict = {
        "id": 2,
        "characteristic": "Width",
        "measurement_method": "Micrometer",
        "sample_size": 5,
        "frequency": "per shift",
        "reaction_plan": "Adjust guide",
        "source_cause_id": "1::1::2-C1",
    }
    canvas_custom = ControlPlanCanvas(
        rows=[row1, row2_dict],
        title="Custom Canvas",
        description="Custom Description",
    )
    assert canvas_custom.title == "Custom Canvas"
    assert canvas_custom.description == "Custom Description"
    assert len(canvas_custom.rows) == 2
    assert canvas_custom.get_row(1) == row1
    assert canvas_custom.get_row(2) is not None


@pytest.mark.parametrize(
    ("kwargs", "expected_err", "match_str"),
    [
        ({"title": ""}, ValueError, "title must be a non-empty string"),
        ({"title": "   "}, ValueError, "title must be a non-empty string"),
        ({"title": 123}, ValueError, "title must be a non-empty string"),
        ({"title": True}, ValueError, "title must be a non-empty string"),
        ({"description": ""}, ValueError, "description must be a non-empty string"),
        ({"description": "  "}, ValueError, "description must be a non-empty string"),
        ({"description": None}, ValueError, "description must be a non-empty string"),
        ({"description": False}, ValueError, "description must be a non-empty string"),
        ({"rows": "not a list"}, TypeError, "rows must be a list"),
        ({"rows": 123}, TypeError, "rows must be a list"),
    ],
)
def test_controlplan_canvas_init_validation_errors(
    kwargs: dict[str, Any], expected_err: type[Exception], match_str: str
) -> None:
    """Invalid title, description, or rows parameter types raise errors."""
    with pytest.raises(expected_err, match=match_str):
        ControlPlanCanvas(**kwargs)


def test_controlplan_canvas_load_sample() -> None:
    """load_sample returns canvas with the 6 benchmark items and expected summary metrics."""
    assert len(SAMPLE_CONTROL_PLAN_ROWS) == 6
    canvas = ControlPlanCanvas.load_sample()
    assert len(canvas.rows) == 6
    assert canvas.rows[0].characteristic == "Gate driver desaturation during high-torque acceleration"
    assert canvas.rows[1].lsl == 0.0
    assert canvas.rows[1].usl == 100.0
    assert canvas.rows[1].target == 50.0

    summary = canvas.get_summary()
    assert summary["total_rows"] == 6
    assert summary["valid_count"] == 4
    assert summary["orphan_count"] == 1  # Row 6 has source_cause_id=None
    assert summary["placeholder_count"] == 1  # Row 5 has sample_plan_is_placeholder=True with source_cause_id
    assert summary["warning_count"] == 0
    assert summary["uncovered_fms_count"] == 0


def test_controlplan_canvas_crud_operations() -> None:
    """Perform CRUD operations on ControlPlanCanvas."""
    canvas = ControlPlanCanvas()

    # 1. add_row with ControlPlanCanvasRow
    row1 = ControlPlanCanvasRow(
        id=10,
        characteristic="Bore diameter",
        measurement_method="Air gage",
        sample_size=5,
        frequency="hourly",
        reaction_plan="Adjust tool",
        source_cause_id="1::1::1-C1",
    )
    added1 = canvas.add_row(row1)
    assert added1.id == 10
    assert canvas.get_row(10) == row1

    # 2. add_row with dict
    added2 = canvas.add_row(
        {
            "id": 20,
            "characteristic": "Seal height",
            "measurement_method": "Height gage",
            "sample_size": 2,
            "frequency": "per batch",
            "reaction_plan": "Adjust press",
            "source_cause_id": "2::1::1-C1",
        }
    )
    assert added2.id == 20
    assert canvas.get_row(20) is not None

    # 3. add_row auto-stamps orphan when source_cause_id is None
    added3 = canvas.add_row(
        {
            "id": 30,
            "characteristic": "Paint gloss",
            "measurement_method": "Gloss meter",
            "sample_size": 1,
            "frequency": "per shift",
            "reaction_plan": "Adjust viscosity",
            "source_cause_id": None,
        }
    )
    assert added3.validation_status == "orphan"
    assert "Orphan characteristic 'Paint gloss': missing source_cause_id." in added3.findings

    # 4. get_row missing and type checks
    assert canvas.get_row(999) is None
    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.get_row("10")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.get_row(True)  # type: ignore[arg-type]

    # 5. add_row duplicate ID error and type error
    with pytest.raises(ValueError, match="Row with ID 10 already exists"):
        canvas.add_row(row1)
    with pytest.raises(TypeError, match="row must be a ControlPlanCanvasRow or dict"):
        canvas.add_row(["not a row"])  # type: ignore[arg-type]

    # 6. edit_row in place and PascalCase
    edited = canvas.edit_row(10, Characteristic="Updated Bore", Sample_Size=8, Target=10.2)
    assert edited.characteristic == "Updated Bore"
    assert edited.sample_size == 8
    assert edited.target == 10.2

    # 7. edit_row changing ID to new ID
    edited_id = canvas.edit_row(10, id=15)
    assert edited_id.id == 15
    assert canvas.get_row(10) is None
    assert canvas.get_row(15) is not None

    # 8. edit_row errors (non-existent, duplicate ID, unknown field, invalid type)
    with pytest.raises(KeyError, match="Row with ID 999 not found"):
        canvas.edit_row(999, characteristic="Does not exist")
    with pytest.raises(ValueError, match="Cannot change row ID to 20: ID already exists"):
        canvas.edit_row(15, id=20)
    with pytest.raises(ValueError, match="Unknown field 'unknown_column'"):
        canvas.edit_row(15, unknown_column="value")
    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.edit_row("15", characteristic="Test")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.edit_row(False, characteristic="Test")  # type: ignore[arg-type]

    # 9. edit_row setting source_cause_id to None stamps orphan finding
    edited_orphan = canvas.edit_row(15, source_cause_id=None)
    assert edited_orphan.validation_status == "orphan"
    assert "missing source_cause_id" in edited_orphan.findings[0]

    # 10. delete_row
    deleted = canvas.delete_row(15)
    assert deleted.id == 15
    assert canvas.get_row(15) is None
    with pytest.raises(KeyError, match="Row with ID 15 not found"):
        canvas.delete_row(15)
    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.delete_row("20")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="row_id must be an integer"):
        canvas.delete_row(True)  # type: ignore[arg-type]


def test_controlplan_canvas_validate_linkage_fmea_none() -> None:
    """validate_linkage with fmea=None evaluates orphan status based solely on source_cause_id."""
    canvas = ControlPlanCanvas()
    canvas.add_row(
        {
            "id": 1,
            "characteristic": "Char 1",
            "measurement_method": "Method 1",
            "sample_size": 1,
            "frequency": "hourly",
            "reaction_plan": "Reaction 1",
            "source_cause_id": "1::1::1-C1",
            "sample_plan_is_placeholder": False,
        }
    )
    canvas.add_row(
        {
            "id": 2,
            "characteristic": "Char 2",
            "measurement_method": "Method 2",
            "sample_size": 1,
            "frequency": "hourly",
            "reaction_plan": "Reaction 2",
            "source_cause_id": None,
            "sample_plan_is_placeholder": False,
        }
    )
    canvas.add_row(
        {
            "id": 3,
            "characteristic": "Char 3",
            "measurement_method": "Method 3",
            "sample_size": 1,
            "frequency": "hourly",
            "reaction_plan": "Reaction 3",
            "source_cause_id": "1::1::2-C1",
            "sample_plan_is_placeholder": True,
        }
    )

    res = canvas.validate_linkage(None)
    assert res["valid"] is False
    assert res["total_rows"] == 3
    assert res["linked_rows"] == 2
    assert res["orphan_characteristics"] == ["Char 2"]
    assert res["uncovered_failure_modes"] == []
    assert len(res["findings"]) == 1

    assert canvas.get_row(1).validation_status == "valid"
    assert canvas.get_row(2).validation_status == "orphan"
    assert canvas.get_row(3).validation_status == "placeholder"


def test_controlplan_canvas_validate_linkage_with_fmea_list_and_relational() -> None:
    """validate_linkage with FMEA list and RelationalFMEA models."""
    fmea_list = [
        {
            "ID": 1,
            "Process_Step": "Inverter SMT",
            "Component": "Gate Driver",
            "Function": "Desat Protection",
            "Failure_Mode": "Overcurrent tripping",
            "Effect": "Loss of propulsion",
            "Severity": 10,
            "Cause": "Voltage transient",
            "Occurrence": 4,
            "Current_Control": "AOI",
            "Detection": 4,
        },
        {
            "ID": 2,
            "Process_Step": "Machining",
            "Component": "Brake Valve",
            "Function": "Pressure control",
            "Failure_Mode": "Calibration drift",
            "Effect": "Degraded braking",
            "Severity": 9,
            "Cause": "Thermal fatigue",
            "Occurrence": 5,
            "Current_Control": "Sweep",
            "Detection": 1,
        },
    ]

    cp_rows = [
        {
            "id": 1,
            "characteristic": "Gate Driver Desat",
            "measurement_method": "AOI",
            "sample_size": 5,
            "frequency": "hourly",
            "reaction_plan": "Investigate",
            "source_cause_id": "F1::F1-M1::F1-M1-C1",  # Linked to step 1
            "sample_plan_is_placeholder": False,
        },
        {
            "id": 2,
            "characteristic": "Unlinked Char",
            "measurement_method": "Visual",
            "sample_size": 1,
            "frequency": "daily",
            "reaction_plan": "Quarantine",
            "source_cause_id": "99::99::99-C1",  # Invalid source_cause_id
            "sample_plan_is_placeholder": False,
        },
        {
            "id": 3,
            "characteristic": "Missing ID Char",
            "measurement_method": "Gage",
            "sample_size": 1,
            "frequency": "hourly",
            "reaction_plan": "Stop",
            "source_cause_id": None,
            "sample_plan_is_placeholder": True,
        },
        {
            "id": 4,
            "characteristic": "Linked Placeholder Char",
            "measurement_method": "AOI",
            "sample_size": 1,
            "frequency": "per batch",
            "reaction_plan": "Investigate",
            "source_cause_id": "F1::F1-M1::F1-M1-C1",  # Linked and placeholder
            "sample_plan_is_placeholder": True,
        },
    ]

    # Test with list of dicts
    canvas = ControlPlanCanvas(rows=cp_rows)
    linkage_res = canvas.validate_linkage(fmea_list)
    assert linkage_res["valid"] is False
    assert "Unlinked Char" in linkage_res["orphan_characteristics"]
    assert "Missing ID Char" in linkage_res["orphan_characteristics"]
    assert "F2::F2-M1" in linkage_res["uncovered_failure_modes"]

    assert canvas.get_row(1).validation_status == "valid"
    assert canvas.get_row(2).validation_status == "orphan"
    assert "not found in FMEA" in canvas.get_row(2).findings[0]
    assert canvas.get_row(3).validation_status == "orphan"
    assert "missing source_cause_id" in canvas.get_row(3).findings[0]
    assert canvas.get_row(4).validation_status == "placeholder"

    # Test with RelationalFMEA object directly
    fmea_rows = [FMEARow(**r) for r in fmea_list]
    relational = flat_to_relational(FMEADataset(rows=fmea_rows))
    canvas2 = ControlPlanCanvas(rows=cp_rows, fmea=relational)
    summary2 = canvas2.get_summary()
    assert summary2["uncovered_fms_count"] == 1
    assert "F2::F2-M1" in summary2["uncovered_failure_modes"]


def test_controlplan_canvas_add_and_edit_row_orphan_branch_coverage() -> None:
    """Exercise branches where orphan finding is already present and validation_status is error."""
    canvas = ControlPlanCanvas()

    # 1. add_row with pre-existing orphan finding and validation_status="error"
    orphan_msg = "Orphan characteristic 'Pre-existing Orphan': missing source_cause_id."
    row_err = ControlPlanCanvasRow(
        id=1,
        characteristic="Pre-existing Orphan",
        measurement_method="Method",
        sample_size=1,
        frequency="hourly",
        reaction_plan="Plan",
        source_cause_id=None,
        validation_status="error",
        findings=[orphan_msg],
    )
    added = canvas.add_row(row_err)
    assert added.validation_status == "error"
    assert added.findings.count(orphan_msg) == 1

    # 2. edit_row setting source_cause_id=None when orphan message already in findings
    # and validation_status is error
    edited = canvas.edit_row(
        1,
        source_cause_id=None,
        findings=[orphan_msg],
        validation_status="error",
    )
    assert edited.validation_status == "error"
    assert edited.findings.count(orphan_msg) == 1


def test_controlplan_canvas_validate_linkage_type_error() -> None:
    """validate_linkage raises TypeError on invalid fmea input."""
    canvas = ControlPlanCanvas()
    with pytest.raises(TypeError, match="fmea must be a RelationalFMEA, list of dicts, or None"):
        canvas.validate_linkage("invalid_fmea")  # type: ignore[arg-type]


def test_controlplan_canvas_get_summary_and_to_dict() -> None:
    """get_summary and to_dict provide complete state inspection."""
    canvas = ControlPlanCanvas()
    canvas.add_row(
        {
            "id": 1,
            "characteristic": "C1",
            "measurement_method": "M1",
            "sample_size": 1,
            "frequency": "F1",
            "reaction_plan": "R1",
            "source_cause_id": "1::1::1-C1",
        }
    )
    # Add a row with error validation_status
    err_row = ControlPlanCanvasRow(
        id=2,
        characteristic="C2",
        measurement_method="M2",
        sample_size=1,
        frequency="F2",
        reaction_plan="R2",
        source_cause_id="1::1::2-C1",
        validation_status="error",
        findings=["Tolerance error"],
    )
    canvas.add_row(err_row)

    summary = canvas.get_summary()
    assert summary["total_rows"] == 2
    assert summary["valid_count"] == 1
    assert summary["warning_count"] == 1

    d = canvas.to_dict()
    assert d["title"] == canvas.title
    assert d["description"] == canvas.description
    assert len(d["rows"]) == 2
    assert d["summary"] == summary
    assert d["linkage_checked"] is False


def test_controlplan_canvas_to_html_themes_and_modes() -> None:
    """to_html supports standalone/embedded modes, dark/light themes, and custom badges."""
    canvas = ControlPlanCanvas.load_sample()

    # 1. Standalone dark theme (default)
    html_dark = canvas.to_html(standalone=True, theme="dark")
    assert "<!DOCTYPE html>" in html_dark
    assert "<html lang=\"en\">" in html_dark
    assert "AIAG APQP Control Plan Matrix Canvas" in html_dark
    assert "Total Characteristics" in html_dark
    assert "Fully Verified" in html_dark
    assert "Orphan Characteristics" in html_dark
    assert "Placeholder Plans" in html_dark
    assert "Uncovered FMEA Modes" in html_dark
    assert "Deterministic computation via quality_core.controlplan" in html_dark

    # 2. Embeddable container light theme
    html_light = canvas.to_html(standalone=False, theme="light")
    assert "<!DOCTYPE html>" not in html_light
    assert "<div class=\"qes-controlplan-canvas\"" in html_light
    assert "#ffffff" in html_light  # Light card background

    # 3. Empty canvas state
    empty_canvas = ControlPlanCanvas(title="Empty Canvas", description="No rows")
    empty_html = empty_canvas.to_html(standalone=False)
    assert "No Control Plan items recorded in canvas." in empty_html

    # 4. Custom status badge and error badge
    custom_canvas = ControlPlanCanvas()
    custom_canvas.add_row(
        ControlPlanCanvasRow(
            id=1,
            characteristic="Custom Row",
            measurement_method="Method",
            sample_size=1,
            frequency="hourly",
            reaction_plan="Plan",
            source_cause_id="1::1::1-C1",
            validation_status="custom_status",
        )
    )
    custom_canvas.add_row(
        ControlPlanCanvasRow(
            id=2,
            characteristic="Error Row",
            measurement_method="Method",
            sample_size=1,
            frequency="hourly",
            reaction_plan="Plan",
            source_cause_id="1::1::2-C1",
            validation_status="error",
        )
    )
    custom_html = custom_canvas.to_html()
    assert "Custom_Status" in custom_html
    assert "Tolerance Error" in custom_html


def test_controlplan_canvas_to_html_uncovered_failure_modes_alert() -> None:
    """to_html renders alert box when uncovered FMEA failure modes exist."""
    fmea_list = [
        {
            "ID": 1,
            "Process_Step": "Step 1",
            "Component": "Comp 1",
            "Function": "Func 1",
            "Failure_Mode": "Critical Stalling Mode",
            "Effect": "Vehicle Stop",
            "Severity": 10,
            "Cause": "Cause 1",
            "Occurrence": 5,
            "Current_Control": "Ctrl",
            "Detection": 5,
        }
    ]
    canvas = ControlPlanCanvas(fmea=fmea_list)
    html_out = canvas.to_html()
    assert "Uncovered PFMEA Failure Modes" in html_out
    assert "F1::F1-M1" in html_out


def test_controlplan_canvas_to_html_escaping() -> None:
    """to_html escapes special HTML characters in text fields."""
    dangerous_canvas = ControlPlanCanvas(
        title="<script>alert('title')</script>",
        description="<b>bold & daring</b>",
    )
    dangerous_canvas.add_row(
        {
            "id": 1,
            "characteristic": "<img src=x onerror=alert('char')>",
            "measurement_method": "Method & <test>",
            "sample_size": 1,
            "frequency": "freq > 1 & < 5",
            "reaction_plan": "Plan \"quoted\" & dangerous",
            "source_cause_id": "1::1::<test>-C1",
        }
    )
    html_out = dangerous_canvas.to_html()
    assert "<script>alert" not in html_out
    assert "&lt;script&gt;alert" in html_out
    assert "&lt;img src=x" in html_out
    assert "&amp;" in html_out
    assert "&quot;quoted&quot;" in html_out


@pytest.mark.parametrize(
    ("kwargs", "expected_err", "match_str"),
    [
        ({"standalone": "yes"}, TypeError, "standalone must be a boolean"),
        ({"standalone": 1}, TypeError, "standalone must be a boolean"),
        ({"theme": "neon"}, ValueError, "theme must be 'dark' or 'light'"),
        ({"theme": "dark_mode"}, ValueError, "theme must be 'dark' or 'light'"),
    ],
)
def test_controlplan_canvas_to_html_parameter_errors(
    kwargs: dict[str, Any], expected_err: type[Exception], match_str: str
) -> None:
    """Invalid standalone and theme parameters raise errors."""
    canvas = ControlPlanCanvas()
    with pytest.raises(expected_err, match=match_str):
        canvas.to_html(**kwargs)


def test_load_sample_controlplan_canvas_helper() -> None:
    """load_sample_controlplan_canvas helper constructs loaded canvas correctly."""
    canvas = load_sample_controlplan_canvas(
        title="Convenience Canvas",
        description="Convenience Description",
    )
    assert canvas.title == "Convenience Canvas"
    assert canvas.description == "Convenience Description"
    assert len(canvas.rows) == 6


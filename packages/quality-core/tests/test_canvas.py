"""Unit tests for quality_core.canvas (FMEACanvasRow and FMEACanvas controller).

Verifies 100% line & branch coverage across all models, controller operations,
deterministic scoring recalculations, CRUD lifecycle, summary statistics, and HTML rendering.
"""

from __future__ import annotations

import pytest
from quality_core.canvas import (
    SAMPLE_FMEA_ROWS,
    FMEACanvas,
    FMEACanvasRow,
    load_sample_canvas,
)
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

from __future__ import annotations

import ast
import datetime

import pytest
from quality_core.canvas.sqe import (
    SQECanvas,
    SQECanvasRow,
    _number,
    load_sample_sqe_canvas,
    render_sqe,
)
from quality_core.sqe import EscalationResult, ScorecardDimensionResult, ScorecardResult


def row(supplier="SUP-1", verdict="RATED", band="A", tier="NONE", cost=True):
    dims = [
        ScorecardDimensionResult("quality", "ppm", 12.0, 98.0, .6, 58.8, "MEASURED", None, {"ppm": 12}),
        ScorecardDimensionResult("delivery", "otif_pct", 95.0, 95.0, .4, 38.0, "MEASURED", None,
                                 {"on_time_pct": 97.0, "in_full_pct": 98.0, "otif_pct": 95.0}),
    ]
    if cost:
        dims.append(ScorecardDimensionResult("cost", "copq", 123.0, 90.0, .1, 9.0, "MEASURED", None, {"copq": 123}))
    score = ScorecardResult(supplier, datetime.date(2026, 1, 1), datetime.date(2026, 1, 31),
                            "Jan <2026>", verdict, 96.8 if verdict == "RATED" else None,
                            band if verdict == "RATED" else None, dims, {"is_heuristic": True},
                            [] if cost else [{"dimension": "cost", "reason": "not provided"}],
                            "missing <evidence>" if verdict != "RATED" else None, ["warn <x>"])
    esc = EscalationResult(supplier, tier, verdict, [], [], None,
                           "reason <x>" if verdict != "RATED" else None, {}, "basis <x>")
    return SQECanvasRow(supplier, score, esc, "Name <script>alert(1)</script>")


def test_row_controller_and_serialization():
    r = row()
    c = SQECanvas([r, r.__dict__], title="Title <x>")
    assert c.rows == [r, r]
    assert c.title == "Title <x>"
    assert c.to_dict()["rows"][0]["supplier_id"] == "SUP-1"
    assert c.load_sample() is c
    assert len(c.rows) == 6
    assert isinstance(load_sample_sqe_canvas(), SQECanvas)
    assert "SQE Vendor" in render_sqe([r], theme="light", standalone=False)
    assert "SQE Vendor" in render_sqe(SQECanvas([r]))


@pytest.mark.parametrize("theme", ["dark", "light", " DARK "])
@pytest.mark.parametrize("standalone", [True, False])
def test_render_modes_and_all_benchmarks(theme, standalone):
    out = load_sample_sqe_canvas().to_html(theme, standalone)
    assert "<!DOCTYPE html>" in out if standalone else "<!DOCTYPE html>" not in out
    for label in ("PPM", "OTIF", "on-time", "in-full", "COPQ / cost", "Composite score", "Band", "Escalation tier"):
        assert label in out
    for value in ("A", "B", "C", "NONE", "MONITOR", "SCAR_REQUIRED", "CONTAINMENT_REQUIRED", "EXECUTIVE_REVIEW", "INDETERMINATE"):
        assert value in out
    assert "no standards citation" in out


def test_empty_omitted_indeterminate_and_escaping():
    empty = SQECanvas(title="<script>alert(1)</script>").to_html()
    assert "No supplier scorecard results" in empty and "&lt;script&gt;" in empty
    out = SQECanvas([row(verdict="INDETERMINATE", band=None, tier="INDETERMINATE", cost=False)]).to_html()
    assert "UNRATED" in out and "INDETERMINATE" in out and "missing &lt;evidence&gt;" in out
    assert "not scored/omitted" in out and "<script>" not in out
    assert "Name &lt;script&gt;alert(1)&lt;/script&gt;" in out


def test_validation_and_number_formatting():
    with pytest.raises(TypeError):
        SQECanvas(title=None)
    with pytest.raises(ValueError):
        SQECanvas(title=" ")
    with pytest.raises(TypeError):
        SQECanvas(rows="bad")
    with pytest.raises(TypeError):
        SQECanvas(["bad"])
    with pytest.raises(TypeError):
        SQECanvas([{}])
    c = SQECanvas([row()])
    with pytest.raises(ValueError):
        c.to_html("blue")
    with pytest.raises(TypeError):
        c.to_html(standalone=1)
    assert render_sqe([], title="T")
    with pytest.raises(TypeError):
        SQECanvasRow("", row().scorecard, row().escalation)
    with pytest.raises(TypeError):
        SQECanvasRow("x", object(), row().escalation)
    with pytest.raises(TypeError):
        SQECanvasRow("x", row().scorecard, object())
    with pytest.raises(TypeError):
        SQECanvasRow("x", row().scorecard, row().escalation, 1)
    assert SQECanvasRow("x", row().scorecard, row().escalation).supplier_name is None
    assert _number(None) == "—"


def test_canvas_has_no_engine_arithmetic_or_recomputed_metrics():
    tree = ast.parse(__import__("pathlib").Path("packages/quality-core/src/quality_core/canvas/sqe.py").read_text())
    forbidden = {"evaluate_escalation", "ScorecardConfig", "OTIFConfig"}
    assert not {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} & forbidden
    arithmetic = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
    assert not any(isinstance(n, ast.BinOp) and isinstance(n.op, arithmetic) for n in ast.walk(tree))

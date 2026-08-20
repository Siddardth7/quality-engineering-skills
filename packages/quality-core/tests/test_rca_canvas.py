"""
Unit and integration tests for FiveWhyCanvas controller and rendering (quality_core.canvas.rca).

Tests:
1. FiveWhyCanvasStep dataclass:
   - Field validations: step_number, why, because, is_reversible, reverse_therefore, systemic_classification, anti_pattern_badge.
   - Serialization: to_dict() and from_dict() with snake_case, PascalCase, and alias keys.
   - Rejection of invalid types, blank strings, non-integers, and non-booleans.
2. FiveWhyCanvas controller:
   - Initialization parameters and validation.
   - Step CRUD: add_step (dict and object), remove_step, get_step, clear_steps.
   - Sorting by step_number via steps and rows properties.
   - Mutators: set_problem_statement, set_root_cause, set_leg_type.
   - validate() execution and step metadata enrichment.
   - get_summary() metrics for empty, valid, warning, and error states.
   - load_sample() benchmark dataset loader.
3. Themed HTML rendering (to_html):
   - Dark theme (default) vs light theme.
   - Standalone HTML5 document vs embeddable container markup.
   - Empty canvas placeholder rendering.
   - Badges: ACCEPT, WARNING, REJECT, other; SYSTEMIC, TECHNICAL_PROCESS, HUMAN_INDIVIDUAL, unclassified.
   - Findings & recommendations alert box rendering permutations.
   - HTML entity escaping across all user-supplied text.
   - Leg type tag rendering.
4. Helper functions: load_sample_5why_canvas and render_five_why with FiveWhyChain, list of dicts, list of steps, None.
"""

from __future__ import annotations

import pytest
from quality_core.canvas.rca import (
    SAMPLE_FIVE_WHY_STEPS,
    FiveWhyCanvas,
    FiveWhyCanvasStep,
    load_sample_5why_canvas,
    render_five_why,
)
from quality_core.rca.schema import FiveWhyChain, FiveWhyStep


def test_sample_five_why_steps_constant_structure() -> None:
    """SAMPLE_FIVE_WHY_STEPS is a list of 5 benchmark dictionaries matching Ford 8D."""
    assert len(SAMPLE_FIVE_WHY_STEPS) == 5
    assert SAMPLE_FIVE_WHY_STEPS[0]["step_number"] == 1
    assert "bearing" in SAMPLE_FIVE_WHY_STEPS[0]["why"].lower()
    assert SAMPLE_FIVE_WHY_STEPS[4]["systemic_classification"] == "SYSTEMIC"

# ---------------------------------------------------------------------------
# 1. FiveWhyCanvasStep Dataclass Unit Tests
# ---------------------------------------------------------------------------


def test_canvas_step_valid_construction_and_to_dict() -> None:
    """FiveWhyCanvasStep constructs cleanly and exports dictionary."""
    step = FiveWhyCanvasStep(
        step_number=1,
        why="Why did machine stop?",
        because="Fuse blew.",
        reverse_therefore="Because fuse blew, therefore machine stopped.",
        is_reversible=True,
        systemic_classification="TECHNICAL_PROCESS",
        anti_pattern_badge=None,
    )
    assert step.step_number == 1
    assert step.why == "Why did machine stop?"
    assert step.because == "Fuse blew."
    assert step.is_reversible is True
    assert step.systemic_classification == "TECHNICAL_PROCESS"

    d = step.to_dict()
    assert d["step_number"] == 1
    assert d["why"] == "Why did machine stop?"
    assert d["because"] == "Fuse blew."
    assert d["is_reversible"] is True


def test_canvas_step_from_dict_snake_and_pascal_case() -> None:
    """from_dict supports snake_case, PascalCase, and alias keys."""
    # snake_case
    s1 = FiveWhyCanvasStep.from_dict({
        "step_number": 2,
        "why": "Why fuse blew?",
        "because": "Overcurrent.",
        "reverse_therefore": "Because overcurrent, therefore fuse blew.",
        "is_reversible": True,
        "systemic_classification": "SYSTEMIC",
        "anti_pattern_badge": "CIRCULAR_REASONING",
    })
    assert s1.step_number == 2
    assert s1.anti_pattern_badge == "CIRCULAR_REASONING"

    # PascalCase
    s2 = FiveWhyCanvasStep.from_dict({
        "StepNumber": 3,
        "Why": "Why overcurrent?",
        "Because": "Motor bearing seized.",
        "ReverseTherefore": "Because bearing seized, therefore overcurrent.",
        "IsReversible": False,
        "SystemicClassification": "TECHNICAL_PROCESS",
        "AntiPatternBadge": None,
    })
    assert s2.step_number == 3
    assert s2.why == "Why overcurrent?"
    assert s2.is_reversible is False

    # Aliases: step and id
    s3 = FiveWhyCanvasStep.from_dict({
        "step": 4,
        "why": "Why bearing seized?",
        "because": "No grease.",
    })
    assert s3.step_number == 4

    s4 = FiveWhyCanvasStep.from_dict({
        "ID": 5,
        "why": "Why no grease?",
        "because": "Lubrication schedule missing.",
    })
    assert s4.step_number == 5


def test_canvas_step_validation_errors() -> None:
    """FiveWhyCanvasStep rejects invalid types and blank values."""
    # Invalid step_number
    with pytest.raises(ValueError, match="step_number must be a positive integer"):
        FiveWhyCanvasStep(step_number=0, why="Why?", because="Because.")

    with pytest.raises(ValueError, match="step_number must be a positive integer"):
        FiveWhyCanvasStep(step_number=True, why="Why?", because="Because.")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="step_number must be a positive integer"):
        FiveWhyCanvasStep(step_number="1", why="Why?", because="Because.")  # type: ignore[arg-type]

    # Blank why / because
    with pytest.raises(ValueError, match="why must be a non-empty string"):
        FiveWhyCanvasStep(step_number=1, why="   ", because="Because.")

    with pytest.raises(ValueError, match="because must be a non-empty string"):
        FiveWhyCanvasStep(step_number=1, why="Why?", because="")

    # Non-boolean is_reversible
    with pytest.raises(TypeError, match="is_reversible must be a boolean"):
        FiveWhyCanvasStep(step_number=1, why="Why?", because="Because.", is_reversible="true")  # type: ignore[arg-type]

    # Non-string reverse_therefore
    with pytest.raises(TypeError, match="reverse_therefore must be a string"):
        FiveWhyCanvasStep(step_number=1, why="Why?", because="Because.", reverse_therefore=123)  # type: ignore[arg-type]

    # Non-string systemic_classification
    with pytest.raises(TypeError, match="systemic_classification must be a string"):
        FiveWhyCanvasStep(step_number=1, why="Why?", because="Because.", systemic_classification=None)  # type: ignore[arg-type]

    # Invalid anti_pattern_badge
    with pytest.raises(ValueError, match="anti_pattern_badge must be a non-empty string or None"):
        FiveWhyCanvasStep(step_number=1, why="Why?", because="Because.", anti_pattern_badge="")

    # from_dict invalid type and missing field
    with pytest.raises(TypeError, match="data must be a dictionary"):
        FiveWhyCanvasStep.from_dict("not-a-dict")  # type: ignore[arg-type]

    with pytest.raises(KeyError, match="Missing required field"):
        FiveWhyCanvasStep.from_dict({"step_number": 1, "why": "Why?"})


# ---------------------------------------------------------------------------
# 2. FiveWhyCanvas Controller Unit Tests
# ---------------------------------------------------------------------------


def test_canvas_initialization_and_validation() -> None:
    """Canvas initializes with valid parameters and rejects invalid strings."""
    canvas = FiveWhyCanvas(
        title="Custom 5-Why",
        description="Custom description",
        problem_statement="Hole out of tolerance",
        root_cause="Engineering sign-off missing",
        leg_type="occurrence",
    )
    assert canvas.title == "Custom 5-Why"
    assert canvas.description == "Custom description"
    assert canvas.problem_statement == "Hole out of tolerance"
    assert canvas.root_cause == "Engineering sign-off missing"
    assert canvas.leg_type == "occurrence"
    assert len(canvas.steps) == 0

    # Rejection of blank / invalid types
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        FiveWhyCanvas(title="")

    with pytest.raises(ValueError, match="title must be a non-empty string"):
        FiveWhyCanvas(title=True)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="description must be a string"):
        FiveWhyCanvas(description=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="problem_statement must be a non-empty string"):
        FiveWhyCanvas(problem_statement="   ")


def test_canvas_step_crud_operations() -> None:
    """Test step addition, retrieval, removal, clearing, and row ordering."""
    canvas = FiveWhyCanvas()

    # Add from dict
    s1 = canvas.add_step({"step_number": 2, "why": "Why 2?", "because": "Because 2."})
    assert s1.step_number == 2

    # Add from FiveWhyCanvasStep
    s2 = canvas.add_step(FiveWhyCanvasStep(step_number=1, why="Why 1?", because="Because 1."))
    assert s2.step_number == 1

    # Steps are returned sorted by step_number
    assert [s.step_number for s in canvas.steps] == [1, 2]
    assert [s.step_number for s in canvas.rows] == [1, 2]

    # Retrieve step
    assert canvas.get_step(1) is not None
    assert canvas.get_step(1).because == "Because 1."  # type: ignore[union-attr]
    assert canvas.get_step(99) is None

    # Remove step
    assert canvas.remove_step(1) is True
    assert canvas.remove_step(99) is False
    assert len(canvas.steps) == 1

    # Clear steps
    canvas.clear_steps()
    assert len(canvas.steps) == 0

    # Type errors in CRUD
    with pytest.raises(TypeError, match="step must be a FiveWhyCanvasStep or dict"):
        canvas.add_step("invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="step_number must be an integer"):
        canvas.get_step("1")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="step_number must be an integer"):
        canvas.remove_step(True)  # type: ignore[arg-type]


def test_canvas_mutators() -> None:
    """Test mutators for problem_statement, root_cause, and leg_type."""
    canvas = FiveWhyCanvas()

    # set_problem_statement
    canvas.set_problem_statement("Updated problem statement")
    assert canvas.problem_statement == "Updated problem statement"
    with pytest.raises(ValueError, match="problem_statement must be a non-empty string"):
        canvas.set_problem_statement("  ")

    # set_root_cause
    canvas.set_root_cause("Root cause text")
    assert canvas.root_cause == "Root cause text"
    canvas.set_root_cause("   ")
    assert canvas.root_cause is None
    canvas.set_root_cause(None)
    assert canvas.root_cause is None
    with pytest.raises(TypeError, match="root_cause must be a string or None"):
        canvas.set_root_cause(123)  # type: ignore[arg-type]

    # set_leg_type
    canvas.set_leg_type("escape")
    assert canvas.leg_type == "escape"
    canvas.set_leg_type("   ")
    assert canvas.leg_type is None
    canvas.set_leg_type(None)
    assert canvas.leg_type is None
    with pytest.raises(TypeError, match="leg_type must be a string or None"):
        canvas.set_leg_type(123)  # type: ignore[arg-type]


def test_canvas_validate_and_summary() -> None:
    """Canvas validate() updates step metadata and get_summary() produces causal KPIs."""
    canvas = FiveWhyCanvas(
        problem_statement="Bearing failed",
        leg_type="occurrence",
    )

    # Empty canvas validate raises ValueError
    with pytest.raises(ValueError, match="Canvas contains no steps to validate"):
        canvas.validate()

    # Empty canvas summary returns EMPTY verdict
    empty_summary = canvas.get_summary()
    assert empty_summary["verdict"] == "EMPTY"
    assert empty_summary["total_steps"] == 0
    assert empty_summary["valid"] is False

    # Add valid steps
    canvas.add_step({"step_number": 1, "why": "Why did bearing fail?", "because": "Lubricant dried out."})
    canvas.add_step({"step_number": 2, "why": "Why did lubricant dry out?", "because": "Autonomous maintenance routine was omitted."})
    canvas.add_step({"step_number": 3, "why": "Why was routine omitted?", "because": "Induction training procedure lacked maintenance checklist."})

    res = canvas.validate()
    assert res.valid is True
    assert res.verdict == "ACCEPT"

    # Verify step metadata updated
    step1 = canvas.get_step(1)
    assert step1 is not None
    assert step1.is_reversible is True
    assert "Because Lubricant dried out, therefore" in step1.reverse_therefore or "Because lubricant dried out, therefore" in step1.reverse_therefore

    step3 = canvas.get_step(3)
    assert step3 is not None
    assert step3.systemic_classification == "SYSTEMIC"

    # Summary
    summary = canvas.get_summary()
    assert summary["valid"] is True
    assert summary["verdict"] == "ACCEPT"
    assert summary["reversibility_score"] == 1.0
    assert summary["classification"] == "SYSTEMIC"
    assert summary["is_systemic"] is True
    assert summary["hard_antipatterns_count"] == 0


def test_canvas_summary_error_state() -> None:
    """When canvas steps violate schema (e.g. non-consecutive numbers), get_summary returns ERROR state."""
    canvas = FiveWhyCanvas()
    canvas.add_step({"step_number": 1, "why": "Why 1?", "because": "Because 1."})
    canvas.add_step({"step_number": 3, "why": "Why 3?", "because": "Because 3."})  # Non-consecutive

    summary = canvas.get_summary()
    assert summary["valid"] is False
    assert summary["verdict"] == "ERROR"
    assert len(summary["findings"]) > 0


def test_canvas_load_sample() -> None:
    """load_sample() loads reference Ford Global 8D bearing induction dataset."""
    canvas = FiveWhyCanvas.load_sample(title="Sample 8D Canvas")
    assert canvas.title == "Sample 8D Canvas"
    assert len(canvas.steps) == 5
    assert canvas.leg_type == "occurrence"
    assert canvas.steps[0].why == "Why was the bearing worn out?"
    assert canvas.steps[4].because == "The induction plan was not signed by Engineering (Systemic Root Cause)."


# ---------------------------------------------------------------------------
# 3. Themed HTML Canvas Rendering Tests
# ---------------------------------------------------------------------------


def test_to_html_themes_and_standalone() -> None:
    """Canvas renders in dark and light themes, and standalone vs embedded modes."""
    canvas = FiveWhyCanvas.load_sample()

    # Dark theme standalone
    html_dark = canvas.to_html(theme="dark", standalone=True)
    assert "<!DOCTYPE html>" in html_dark
    assert "qes-five-why-canvas" in html_dark
    assert "Hole positions outside of tolerance" in html_dark
    assert "AIAG CQI-20" in html_dark
    assert "OCCURRENCE" in html_dark

    # Light theme embedded
    html_light = canvas.to_html(theme="light", standalone=False)
    assert "<!DOCTYPE html>" not in html_light
    assert "qes-five-why-canvas" in html_light

    # Invalid theme
    with pytest.raises(ValueError, match="theme must be 'dark' or 'light'"):
        canvas.to_html(theme="blue")  # type: ignore[arg-type]


def test_to_html_empty_canvas() -> None:
    """Empty canvas renders placeholder message."""
    canvas = FiveWhyCanvas(title="Empty Canvas")
    html_out = canvas.to_html()
    assert "No 5-Why steps recorded in canvas" in html_out
    assert "EMPTY" in html_out


def test_to_html_badges_and_alert_boxes() -> None:
    """Test rendering of verdict badges, classification badges, and alert boxes."""
    # 1. Reject canvas with circular reasoning and blame
    canvas = FiveWhyCanvas(problem_statement="Machine stopped")
    canvas.add_step({"step_number": 1, "why": "Why stopped?", "because": "Machine stopped."})
    canvas.add_step({"step_number": 2, "why": "Why stopped?", "because": "Operator forgot to check."})

    html_rej = canvas.to_html()
    assert "Rejected" in html_rej
    assert "Anti-Pattern: CIRCULAR_REASONING" in html_rej
    assert "Individual Human" in html_rej
    assert "Identified Causal Findings / Anti-Patterns:" in html_rej

    # 2. Warning canvas with non-causal jump
    canvas_warn = FiveWhyCanvas(problem_statement="Pump failed")
    canvas_warn.add_step({"step_number": 1, "why": "Why pump failed?", "because": "Seal tore."})
    canvas_warn.add_step({"step_number": 2, "why": "Why coffee machine cold?", "because": "Heater broken."})
    canvas_warn.add_step({"step_number": 3, "why": "Why heater broken?", "because": "Engineering sign-off missing."})

    html_warn = canvas_warn.to_html()
    assert "Warning" in html_warn


def test_to_html_escaping() -> None:
    """HTML entities in title, problem statement, why, and because are escaped."""
    canvas = FiveWhyCanvas(
        title="<script>alert('xss')</script>",
        problem_statement="Defect & Problem > Tolerance",
        root_cause="<b>Root Cause</b>",
    )
    canvas.add_step({
        "step_number": 1,
        "why": "Why <test>?",
        "because": "Because & <result>.",
    })
    html_out = canvas.to_html()
    assert "<script>" not in html_out
    assert "&lt;script&gt;alert" in html_out
    assert "Defect &amp; Problem &gt; Tolerance" in html_out
    assert "&lt;b&gt;Root Cause&lt;/b&gt;" in html_out
    assert "&lt;test&gt;" in html_out
    assert "&amp; &lt;result&gt;" in html_out


# ---------------------------------------------------------------------------
# 4. Helper Functions Unit Tests
# ---------------------------------------------------------------------------


def test_load_sample_5why_canvas_helper() -> None:
    """load_sample_5why_canvas returns loaded FiveWhyCanvas."""
    canvas = load_sample_5why_canvas(title="Helper Sample Canvas")
    assert isinstance(canvas, FiveWhyCanvas)
    assert canvas.title == "Helper Sample Canvas"
    assert len(canvas.steps) == 5


def test_render_five_why_helper() -> None:
    """render_five_why supports None, FiveWhyChain, list of dicts, and list of FiveWhyCanvasStep."""
    # 1. None -> loads sample
    h1 = render_five_why()
    assert "qes-five-why-canvas" in h1
    assert "Bearing Induction Training System" in h1

    # 2. FiveWhyChain
    chain = FiveWhyChain(
        problem_statement="Test chain",
        steps=[
            FiveWhyStep(step_number=1, why="Why 1?", because="Because 1."),
            FiveWhyStep(step_number=2, why="Why 2?", because="Because policy missing."),
        ],
    )
    h2 = render_five_why(chain=chain, theme="light", standalone=False)
    assert "Test chain" in h2
    assert "<!DOCTYPE html>" not in h2

    # 3. List of dicts
    dict_list = [
        {"step_number": 1, "why": "Why A?", "because": "Because B."},
        {"step_number": 2, "why": "Why B?", "because": "Because standard missing."},
    ]
    h3 = render_five_why(chain=dict_list, problem_statement="Problem A")
    assert "Problem A" in h3

    # 4. List of FiveWhyCanvasStep
    step_list = [
        FiveWhyCanvasStep(step_number=1, why="Why X?", because="Because Y."),
    ]
    h4 = render_five_why(chain=step_list)
    assert "Why X?" in h4

    # 5. Invalid chain types
    with pytest.raises(TypeError, match="chain must be FiveWhyChain, list of dicts, or None"):
        render_five_why(chain=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Expected FiveWhyCanvasStep or dict in chain list"):
        render_five_why(chain=["not-a-step"])  # type: ignore[list-item]


def test_to_html_unpopulated_reverse_therefore_and_empty_recs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Canvas step with empty reverse_therefore and empty summary recs renders cleanly."""
    canvas = FiveWhyCanvas(title="Raw Canvas")
    canvas.add_step(FiveWhyCanvasStep(step_number=1, why="Why raw?", because="Because raw.", reverse_therefore=""))

    # Mock get_summary to return empty findings and recommendations to cover recs_html = ""
    monkeypatch.setattr(
        canvas,
        "get_summary",
        lambda: {
            "total_steps": 1,
            "reversibility_score": 1.0,
            "verdict": "ACCEPT",
            "classification": "SYSTEMIC",
            "findings": [],
            "recommendations": [],
        },
    )

    html_out = canvas.to_html()
    assert "Raw Canvas" in html_out
    assert "Why raw?" in html_out
    assert "Reverse Check (Therefore):" not in html_out
    assert "Engineering Recommendations &amp; Corrective Action:" not in html_out

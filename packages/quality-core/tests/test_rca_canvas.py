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

from unittest.mock import patch

import pytest
from quality_core.canvas.rca import (
    SAMPLE_FISHBONE_CAUSES,
    SAMPLE_FISHBONE_DATASET,
    SAMPLE_FIVE_WHY_STEPS,
    SAMPLE_IS_IS_NOT_MATRIX,
    SAMPLE_IS_IS_NOT_ROWS,
    FishboneCanvas,
    FishboneCanvasCause,
    FiveWhyCanvas,
    FiveWhyCanvasStep,
    IsIsNotCanvas,
    IsIsNotCanvasRow,
    load_sample_5why_canvas,
    load_sample_fishbone_canvas,
    load_sample_is_is_not_canvas,
    render_fishbone,
    render_five_why,
    render_is_is_not,
)
from quality_core.rca.schema import (
    CATEGORY_6M_VALUES,
    FishboneCause,
    FishboneDataset,
    FiveWhyChain,
    FiveWhyStep,
    IsIsNotMatrix,
    IsIsNotRow,
)


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


# ==============================================================================
# 5. 6M Fishbone Canvas Unit Tests
# ==============================================================================


def test_sample_fishbone_constants() -> None:
    """SAMPLE_FISHBONE_CAUSES has 12 benchmark causes across 6M and dataset matches."""
    assert len(SAMPLE_FISHBONE_CAUSES) == 12
    assert "effect" in SAMPLE_FISHBONE_DATASET
    assert len(SAMPLE_FISHBONE_DATASET["causes"]) == 12
    # Verify each 6M category is represented with 2 causes
    counts = {b: 0 for b in CATEGORY_6M_VALUES}
    for c in SAMPLE_FISHBONE_CAUSES:
        counts[c["category"]] += 1
    assert all(cnt == 2 for cnt in counts.values())


# ---------------------------------------------------------------------------
# FishboneCanvasCause Unit Tests
# ---------------------------------------------------------------------------


def test_fishbone_canvas_cause_construction_and_to_dict() -> None:
    """FishboneCanvasCause constructs cleanly, normalizes aliases, and exports dictionary."""
    cause = FishboneCanvasCause(
        category="manpower",
        cause="Operator fatigue during shift",
        sub_category="Fatigue",
        is_duplicate=False,
    )
    assert cause.category == "Man"
    assert cause.cause == "Operator fatigue during shift"
    assert cause.sub_category == "Fatigue"
    assert cause.is_duplicate is False

    d = cause.to_dict()
    assert d["category"] == "Man"
    assert d["cause"] == "Operator fatigue during shift"
    assert d["sub_category"] == "Fatigue"
    assert d["is_duplicate"] is False


def test_fishbone_canvas_cause_from_dict_snake_and_pascal_case() -> None:
    """FishboneCanvasCause.from_dict supports snake_case, PascalCase, and alias keys."""
    # snake_case
    c1 = FishboneCanvasCause.from_dict({
        "category": "Machine",
        "cause": "Lathe spindle runout",
        "sub_category": "Tooling",
        "is_duplicate": True,
    })
    assert c1.category == "Machine"
    assert c1.is_duplicate is True

    # PascalCase
    c2 = FishboneCanvasCause.from_dict({
        "Category": "Method",
        "Cause": "Standard work missing",
        "SubCategory": "Process",
        "IsDuplicate": False,
    })
    assert c2.category == "Method"
    assert c2.cause == "Standard work missing"

    # Aliases: branch and description
    c3 = FishboneCanvasCause.from_dict({
        "branch": "equipment",
        "description": "Fixture loose",
        "subcategory": "Mounting",
    })
    assert c3.category == "Machine"
    assert c3.cause == "Fixture loose"
    assert c3.sub_category == "Mounting"

    # Aliases: text and Subcategory
    c4 = FishboneCanvasCause.from_dict({
        "Branch": "inspection",
        "Text": "Gage drift",
        "Subcategory": "Calibration",
    })
    assert c4.category == "Measurement"
    assert c4.cause == "Gage drift"


def test_fishbone_canvas_cause_validation_errors() -> None:
    """FishboneCanvasCause rejects invalid types, blank values, and invalid categories."""
    # Invalid category
    with pytest.raises(ValueError, match="category must be a non-empty string"):
        FishboneCanvasCause(category="", cause="Valid cause")

    with pytest.raises(ValueError, match="Invalid 6M category"):
        FishboneCanvasCause(category="Software", cause="Valid cause")

    # Blank cause
    with pytest.raises(ValueError, match="cause must be a non-empty string"):
        FishboneCanvasCause(category="Man", cause="   ")

    with pytest.raises(ValueError, match="cause must be a non-empty string"):
        FishboneCanvasCause(category="Man", cause=123)  # type: ignore[arg-type]

    # Non-boolean is_duplicate
    with pytest.raises(TypeError, match="is_duplicate must be a boolean"):
        FishboneCanvasCause(category="Man", cause="Valid cause", is_duplicate="true")  # type: ignore[arg-type]

    # Non-dict in from_dict
    with pytest.raises(TypeError, match="data must be a dictionary"):
        FishboneCanvasCause.from_dict("not-a-dict")  # type: ignore[arg-type]

    # Missing required field in from_dict
    with pytest.raises(KeyError, match="Missing required field"):
        FishboneCanvasCause.from_dict({"category": "Man"})  # missing cause

    with pytest.raises(KeyError, match="Missing required field"):
        FishboneCanvasCause.from_dict({"cause": "Valid cause"})  # missing category


def test_fishbone_canvas_cause_sub_category_blank_handling() -> None:
    """Blank or whitespace-only sub_category becomes None."""
    c = FishboneCanvasCause(category="Man", cause="Valid", sub_category="   ")
    assert c.sub_category is None

    c2 = FishboneCanvasCause(category="Man", cause="Valid", sub_category=None)
    assert c2.sub_category is None


def test_fishbone_canvas_cause_canonical_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When CATEGORY_6M_ALIASES does not contain lowercase key, canonical CATEGORY_6M_VALUES matches."""
    import quality_core.canvas.rca as canvas_rca_mod

    monkeypatch.setattr(canvas_rca_mod, "CATEGORY_6M_ALIASES", {})
    c = canvas_rca_mod.FishboneCanvasCause(category="Man", cause="Direct canonical cause")
    assert c.category == "Man"
    assert c.cause == "Direct canonical cause"


# ---------------------------------------------------------------------------
# FishboneCanvas Controller Unit Tests
# ---------------------------------------------------------------------------


def test_fishbone_canvas_initialization_and_validation() -> None:
    """FishboneCanvas validates title, description, effect, and balance_threshold on init."""
    canvas = FishboneCanvas(
        title="Custom Fishbone Canvas",
        description="Custom description",
        effect="Cylinder stroke binding",
        balance_threshold=0.80,
    )
    assert canvas.title == "Custom Fishbone Canvas"
    assert canvas.description == "Custom description"
    assert canvas.effect == "Cylinder stroke binding"
    assert canvas.balance_threshold == 0.80
    assert len(canvas.causes) == 0
    assert len(canvas.rows) == 0

    # Invalid title
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        FishboneCanvas(title="")

    with pytest.raises(ValueError, match="title must be a non-empty string"):
        FishboneCanvas(title=123)  # type: ignore[arg-type]

    # Invalid description
    with pytest.raises(TypeError, match="description must be a string"):
        FishboneCanvas(description=123)  # type: ignore[arg-type]

    # Invalid effect
    with pytest.raises(ValueError, match="effect must be a non-empty string"):
        FishboneCanvas(effect="")

    with pytest.raises(ValueError, match="effect must be a non-empty string"):
        FishboneCanvas(effect=None)  # type: ignore[arg-type]

    # Invalid balance_threshold
    with pytest.raises(ValueError, match="balance_threshold must be a float between 0 and 1"):
        FishboneCanvas(balance_threshold=0.0)

    with pytest.raises(ValueError, match="balance_threshold must be a float between 0 and 1"):
        FishboneCanvas(balance_threshold=1.5)

    with pytest.raises(ValueError, match="balance_threshold must be a float between 0 and 1"):
        FishboneCanvas(balance_threshold=True)  # type: ignore[arg-type]


def test_fishbone_canvas_crud_operations() -> None:
    """FishboneCanvas supports add_cause, remove_cause, get_causes_by_category, clear_causes, and set_effect."""
    canvas = FishboneCanvas()

    # 1. Add cause as dict and object
    c1 = canvas.add_cause({"category": "Man", "cause": "Operator fatigue", "sub_category": "Shift"})
    assert isinstance(c1, FishboneCanvasCause)
    assert len(canvas.causes) == 1

    c2_obj = FishboneCanvasCause(category="Machine", cause="Spindle runout")
    c2 = canvas.add_cause(c2_obj)
    assert c2 is c2_obj
    assert len(canvas.causes) == 2

    # Invalid cause type
    with pytest.raises(TypeError, match="cause must be a FishboneCanvasCause or dict"):
        canvas.add_cause("not-a-cause")  # type: ignore[arg-type]

    # 2. get_causes_by_category (including alias support)
    man_causes = canvas.get_causes_by_category("Man")
    assert len(man_causes) == 1
    assert man_causes[0].cause == "Operator fatigue"

    man_alias_causes = canvas.get_causes_by_category("manpower")
    assert len(man_alias_causes) == 1

    with pytest.raises(TypeError, match="category must be a string"):
        canvas.get_causes_by_category(123)  # type: ignore[arg-type]

    # 3. remove_cause by int, str, and object
    # Add third cause
    c3 = canvas.add_cause({"category": "Method", "cause": "Missing torque spec"})
    assert len(canvas.causes) == 3

    # Remove by int index
    assert canvas.remove_cause(0) is True
    assert len(canvas.causes) == 2
    assert canvas.remove_cause(99) is False  # out of bounds

    # Remove by str text (case-insensitive)
    assert canvas.remove_cause("  spindle runout  ") is True
    assert len(canvas.causes) == 1
    assert canvas.remove_cause("non-existent cause") is False

    # Remove by object
    assert canvas.remove_cause(c3) is True
    assert len(canvas.causes) == 0
    assert canvas.remove_cause(c3) is False  # already removed

    # Invalid type to remove_cause
    with pytest.raises(TypeError, match="index_or_cause must be an int, str, or FishboneCanvasCause"):
        canvas.remove_cause([1, 2, 3])  # type: ignore[arg-type]

    # 4. clear_causes
    canvas.add_cause({"category": "Man", "cause": "Cause 1"})
    canvas.add_cause({"category": "Machine", "cause": "Cause 2"})
    assert len(canvas.causes) == 2
    canvas.clear_causes()
    assert len(canvas.causes) == 0

    # 5. set_effect
    canvas.set_effect("New problem effect")
    assert canvas.effect == "New problem effect"

    with pytest.raises(ValueError, match="effect must be a non-empty string"):
        canvas.set_effect("")

    with pytest.raises(ValueError, match="effect must be a non-empty string"):
        canvas.set_effect(None)  # type: ignore[arg-type]


def test_fishbone_canvas_categorize_and_duplicate_marking() -> None:
    """categorize() executes validation and marks is_duplicate=True on duplicate causes."""
    canvas = FishboneCanvas(effect="Cylinder binding")
    canvas.add_cause({"category": "Man", "cause": "Torque error"})
    canvas.add_cause({"category": "Method", "cause": "torque error"})  # duplicate
    canvas.add_cause({"category": "Machine", "cause": "Spindle loose"})

    result = canvas.categorize()
    assert result.valid is True
    assert result.verdict == "WARNING"
    assert len(result.duplicate_causes) == 1
    assert canvas.causes[0].is_duplicate is True
    assert canvas.causes[1].is_duplicate is True
    assert canvas.causes[2].is_duplicate is False


def test_fishbone_canvas_categorize_empty_raises() -> None:
    """categorize() on an empty canvas raises ValueError."""
    canvas = FishboneCanvas()
    with pytest.raises(ValueError, match="Canvas contains no causes to categorize"):
        canvas.categorize()


def test_fishbone_canvas_get_summary_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_summary() handles empty, valid, warning, and error states."""
    # 1. Empty state
    canvas_empty = FishboneCanvas()
    sum_empty = canvas_empty.get_summary()
    assert sum_empty["total_causes"] == 0
    assert sum_empty["valid"] is False
    assert sum_empty["verdict"] == "EMPTY"
    assert sum_empty["empty_branches_count"] == 6

    # 2. Sample valid state
    canvas_sample = FishboneCanvas.load_sample()
    sum_sample = canvas_sample.get_summary()
    assert sum_sample["total_causes"] == 12
    assert sum_sample["active_branches_count"] == 6
    assert sum_sample["empty_branches_count"] == 0
    assert sum_sample["valid"] is True
    assert sum_sample["verdict"] == "ACCEPT"
    assert sum_sample["top_branch"] is not None

    # 3. Error state (mocked exception in categorize)
    canvas_err = FishboneCanvas()
    canvas_err.add_cause({"category": "Man", "cause": "Cause 1"})
    monkeypatch.setattr(canvas_err, "categorize", lambda: (_ for _ in ()).throw(RuntimeError("Categorization crashed")))
    sum_err = canvas_err.get_summary()
    assert sum_err["valid"] is False
    assert sum_err["verdict"] == "ERROR"
    assert "Categorization crashed" in sum_err["findings"][0]


def test_fishbone_canvas_to_html_themes_and_standalone() -> None:
    """to_html() renders dark and light themes, standalone and embeddable modes."""
    canvas = FishboneCanvas.load_sample(title="Interactive 6M Canvas")

    # 1. Dark theme standalone (default)
    html_dark = canvas.to_html(theme="dark", standalone=True)
    assert "<!DOCTYPE html>" in html_dark
    assert "Interactive 6M Canvas" in html_dark
    assert "qes-fishbone-canvas" in html_dark
    assert "<svg" in html_dark
    assert "PROBLEM EFFECT" in html_dark
    assert "Verified (ACCEPT)" in html_dark

    # 2. Light theme embeddable
    html_light = canvas.to_html(theme="light", standalone=False)
    assert "<!DOCTYPE html>" not in html_light
    assert "Interactive 6M Canvas" in html_light
    assert "qes-fishbone-canvas" in html_light

    # 3. Invalid theme
    with pytest.raises(ValueError, match="theme must be 'dark' or 'light'"):
        canvas.to_html(theme="neon")  # type: ignore[arg-type]


def test_fishbone_canvas_to_html_verdicts_and_escaping(monkeypatch: pytest.MonkeyPatch) -> None:
    """to_html() renders WARNING, REJECT, other verdicts and escapes HTML entities."""
    # 1. WARNING verdict with bare legs and duplicates
    canvas_warn = FishboneCanvas(
        title="<script>alert('xss')</script>",
        effect="Effect with <b>HTML</b> & tags",
    )
    canvas_warn.add_cause({"category": "Man", "cause": "Operator & <assistant> fatigue", "sub_category": "Shift & Handover"})
    canvas_warn.add_cause({"category": "Man", "cause": "Operator & <assistant> fatigue"})  # duplicate

    html_warn = canvas_warn.to_html()
    assert "<script>" not in html_warn
    assert "&lt;script&gt;alert" in html_warn
    assert "Effect with &lt;b&gt;HTML&lt;/b&gt; &amp; tags" in html_warn
    assert "Operator &amp; &lt;assistant&gt; fatigue" in html_warn
    assert "Shift &amp; Handover" in html_warn
    assert "Warning" in html_warn
    assert "DUPLICATE" in html_warn
    assert "Identified 6M Branch Findings:" in html_warn

    # 2. REJECT verdict badge rendering
    canvas_rej = FishboneCanvas()
    canvas_rej.add_cause({"category": "Man", "cause": "Cause 1"})
    monkeypatch.setattr(
        canvas_rej,
        "get_summary",
        lambda: {
            "total_causes": 1,
            "active_branches_count": 1,
            "empty_branches_count": 5,
            "empty_branches": ["Machine", "Method", "Material", "Measurement", "Environment"],
            "branch_counts": {b: (1 if b == "Man" else 0) for b in CATEGORY_6M_VALUES},
            "valid": False,
            "verdict": "REJECT",
            "top_branch": "Man",
            "top_branch_count": 1,
            "top_branch_percentage": 1.0,
            "findings": ["Severe validation error"],
            "recommendations": ["Fix input data"],
        },
    )
    html_rej = canvas_rej.to_html()
    assert "Rejected" in html_rej

    # 3. Other verdict badge rendering (e.g. CUSTOM)
    monkeypatch.setattr(
        canvas_rej,
        "get_summary",
        lambda: {
            "total_causes": 0,
            "active_branches_count": 0,
            "empty_branches_count": 6,
            "empty_branches": list(CATEGORY_6M_VALUES),
            "branch_counts": {b: 0 for b in CATEGORY_6M_VALUES},
            "valid": False,
            "verdict": "CUSTOM_STATUS",
            "top_branch": None,
            "top_branch_count": 0,
            "top_branch_percentage": 0.0,
            "findings": [],
            "recommendations": [],
        },
    )
    html_custom = canvas_rej.to_html()
    assert "CUSTOM_STATUS" in html_custom

    # 4. Cause with unmapped category (bypassing grouped 6M branches)
    canvas_unmapped = FishboneCanvas()
    cause_raw = FishboneCanvasCause(category="Man", cause="Original")
    # Mutate category to an unrecognized one to test branch line 1086
    object.__setattr__(cause_raw, "category", "UnmappedCategory")
    canvas_unmapped._causes.append(cause_raw)
    html_unmapped = canvas_unmapped.to_html()
    assert "qes-fishbone-canvas" in html_unmapped


# ---------------------------------------------------------------------------
# Helper Functions Unit Tests
# ---------------------------------------------------------------------------


def test_load_sample_fishbone_canvas_helper() -> None:
    """load_sample_fishbone_canvas returns loaded FishboneCanvas with 12 causes."""
    canvas = load_sample_fishbone_canvas(title="Helper Sample Canvas")
    assert isinstance(canvas, FishboneCanvas)
    assert canvas.title == "Helper Sample Canvas"
    assert len(canvas.causes) == 12


def test_render_fishbone_helper() -> None:
    """render_fishbone supports None, FishboneDataset, list of dicts, and list of causes."""
    # 1. None -> loads sample
    h1 = render_fishbone()
    assert "qes-fishbone-canvas" in h1
    assert "Pneumatic cylinder" in h1

    # 2. None with custom effect
    h1_custom_eff = render_fishbone(effect="Custom failure mode effect")
    assert "Custom failure mode effect" in h1_custom_eff

    # 3. FishboneDataset
    causes_objs = [FishboneCause(category="Man", cause="Operator error")]
    ds = FishboneDataset(effect="Dataset Effect", causes=causes_objs)
    h2 = render_fishbone(causes=ds, theme="light", standalone=False)
    assert "Dataset Effect" in h2
    assert "<!DOCTYPE html>" not in h2

    # 4. list of dicts
    dict_list = [
        {"category": "Machine", "cause": "Fixture loose"},
        {"category": "Method", "cause": "Procedure vague"},
    ]
    h3 = render_fishbone(causes=dict_list, effect="Dict Effect")
    assert "Dict Effect" in h3
    assert "Fixture loose" in h3

    # 5. list of FishboneCanvasCause
    canvas_cause_list = [
        FishboneCanvasCause(category="Material", cause="Hardness high"),
    ]
    h4 = render_fishbone(causes=canvas_cause_list)
    assert "Hardness high" in h4

    # 6. list of FishboneCause
    fb_cause_list = [
        FishboneCause(category="Measurement", cause="Gage worn"),
    ]
    h5 = render_fishbone(causes=fb_cause_list)
    assert "Gage worn" in h5

    # 7. Invalid causes type
    with pytest.raises(TypeError, match="causes must be FishboneDataset, list of dicts/causes, or None"):
        render_fishbone(causes=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Expected FishboneCanvasCause, FishboneCause, or dict in causes list"):
        render_fishbone(causes=["not-a-cause"])  # type: ignore[list-item]


# ==============================================================================
# 3. Kepner-Tregoe Is/Is-Not Canvas Controller & Rendering Unit Tests
# ==============================================================================


def test_sample_is_is_not_constants_structure() -> None:
    """SAMPLE_IS_IS_NOT_ROWS and SAMPLE_IS_IS_NOT_MATRIX match Sentinel-8D benchmark structure."""
    assert len(SAMPLE_IS_IS_NOT_ROWS) == 4
    dims = [r["dimension"] for r in SAMPLE_IS_IS_NOT_ROWS]
    assert dims == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert "problem_statement" in SAMPLE_IS_IS_NOT_MATRIX
    assert SAMPLE_IS_IS_NOT_MATRIX["rows"] == SAMPLE_IS_IS_NOT_ROWS


# ---------------------------------------------------------------------------
# IsIsNotCanvasRow Dataclass Tests
# ---------------------------------------------------------------------------


def test_is_is_not_canvas_row_valid_construction_and_to_dict() -> None:
    """IsIsNotCanvasRow constructs correctly and serializes to dictionary."""
    row = IsIsNotCanvasRow(
        dimension="WHAT",
        is_data="Pneumatic cylinder stroke binding",
        is_not_data="Piston rod surface damage",
        distinctions="Bottom mounting face non-parallelism",
        changes="Bar stock feed misalignment",
        candidate_cause="Undersized blank causes clamping distortion",
    )
    assert row.dimension == "WHAT"
    assert row.is_data == "Pneumatic cylinder stroke binding"
    assert row.is_not_data == "Piston rod surface damage"
    assert row.distinctions == "Bottom mounting face non-parallelism"
    assert row.changes == "Bar stock feed misalignment"
    assert row.candidate_cause == "Undersized blank causes clamping distortion"

    d = row.to_dict()
    assert d["dimension"] == "WHAT"
    assert d["is_data"] == "Pneumatic cylinder stroke binding"
    assert d["is_not_data"] == "Piston rod surface damage"
    assert d["distinctions"] == "Bottom mounting face non-parallelism"
    assert d["changes"] == "Bar stock feed misalignment"
    assert d["candidate_cause"] == "Undersized blank causes clamping distortion"


def test_is_is_not_canvas_row_from_dict_snake_and_pascal_case() -> None:
    """IsIsNotCanvasRow.from_dict parses snake_case, PascalCase, and alias keys."""
    # 1. snake_case
    r1 = IsIsNotCanvasRow.from_dict({
        "dimension": "WHERE",
        "is_data": "CNC milling station",
        "is_not_data": "CNC lathe station",
        "distinctions": "Vice clamping standard",
        "changes": "Backstop guide adjusted",
        "candidate_cause": "Backstop adjustment without laser verification",
    })
    assert r1.dimension == "WHERE"
    assert r1.is_data == "CNC milling station"
    assert r1.is_not_data == "CNC lathe station"
    assert r1.distinctions == "Vice clamping standard"
    assert r1.changes == "Backstop guide adjusted"
    assert r1.candidate_cause == "Backstop adjustment without laser verification"

    # 2. PascalCase & aliases (dim, is, is_not, distinction, change, cause)
    r2 = IsIsNotCanvasRow.from_dict({
        "Dim": "WHEN",
        "Is": "Post-assembly test",
        "IsNot": "Receiving inspection",
        "Distinction": "Pressurized stroke test",
        "Change": "Shift handover",
        "Cause": "Lack of checkweigher",
    })
    assert r2.dimension == "WHEN"
    assert r2.is_data == "Post-assembly test"
    assert r2.is_not_data == "Receiving inspection"
    assert r2.distinctions == "Pressurized stroke test"
    assert r2.changes == "Shift handover"
    assert r2.candidate_cause == "Lack of checkweigher"

    # 3. hypothesis alias
    r3 = IsIsNotCanvasRow.from_dict({
        "dimension": "EXTENT",
        "is_data": "52 of 802 units",
        "is_not_data": "All 802 units",
        "hypothesis": "Weight variation driver",
    })
    assert r3.dimension == "EXTENT"
    assert r3.candidate_cause == "Weight variation driver"
    assert r3.distinctions is None
    assert r3.changes is None


def test_is_is_not_canvas_row_validation_errors() -> None:
    """IsIsNotCanvasRow raises ValueError / TypeError on invalid fields."""
    # 1. Invalid dimension: bool, non-str, empty, non-KT
    with pytest.raises(ValueError, match="dimension must be a non-empty string"):
        IsIsNotCanvasRow(dimension=True, is_data="X", is_not_data="Y")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="dimension must be a non-empty string"):
        IsIsNotCanvasRow(dimension="", is_data="X", is_not_data="Y")

    with pytest.raises(ValueError, match="Invalid Kepner-Tregoe dimension"):
        IsIsNotCanvasRow(dimension="WHO", is_data="X", is_not_data="Y")

    # 2. Invalid is_data / is_not_data: bool, non-str, empty
    with pytest.raises(ValueError, match="is_data must be a non-empty string"):
        IsIsNotCanvasRow(dimension="WHAT", is_data=False, is_not_data="Y")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="is_data must be a non-empty string"):
        IsIsNotCanvasRow(dimension="WHAT", is_data="   ", is_not_data="Y")

    with pytest.raises(ValueError, match="is_not_data must be a non-empty string"):
        IsIsNotCanvasRow(dimension="WHAT", is_data="X", is_not_data=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="is_not_data must be a non-empty string"):
        IsIsNotCanvasRow(dimension="WHAT", is_data="X", is_not_data="   ")

    # 3. Optional fields: bool -> TypeError, non-str -> TypeError
    with pytest.raises(TypeError, match="distinctions must be a string or None"):
        IsIsNotCanvasRow(dimension="WHAT", is_data="X", is_not_data="Y", distinctions=True)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="changes must be a string or None"):
        IsIsNotCanvasRow(dimension="WHAT", is_data="X", is_not_data="Y", changes=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="candidate_cause must be a string or None"):
        IsIsNotCanvasRow(dimension="WHAT", is_data="X", is_not_data="Y", candidate_cause=["bad"])  # type: ignore[arg-type]

    # 4. Optional fields whitespace stripped to None
    row_clean = IsIsNotCanvasRow(
        dimension="WHAT",
        is_data="X",
        is_not_data="Y",
        distinctions="   ",
        changes="",
        candidate_cause="  \t\n  ",
    )
    assert row_clean.distinctions is None
    assert row_clean.changes is None
    assert row_clean.candidate_cause is None

    # 5. from_dict non-dict -> TypeError
    with pytest.raises(TypeError, match="data must be a dictionary"):
        IsIsNotCanvasRow.from_dict("not-a-dict")  # type: ignore[arg-type]

    # 6. from_dict missing required fields -> KeyError
    with pytest.raises(KeyError, match="Missing required field: 'dimension'"):
        IsIsNotCanvasRow.from_dict({"is_data": "X", "is_not_data": "Y"})


# ---------------------------------------------------------------------------
# IsIsNotCanvas Controller Unit Tests
# ---------------------------------------------------------------------------


def test_is_is_not_canvas_init_and_validation() -> None:
    """IsIsNotCanvas initializes with defaults and validates input arguments."""
    canvas = IsIsNotCanvas()
    assert canvas.title == "Kepner-Tregoe Is/Is-Not Scoping Canvas"
    assert "Comparative Problem Boundary Scoping" in canvas.description
    assert canvas.problem_statement == "Problem Statement"
    assert len(canvas.rows) == 0

    # Custom init
    c2 = IsIsNotCanvas(
        title="Custom Title",
        description="Custom Desc",
        problem_statement="Custom Problem",
    )
    assert c2.title == "Custom Title"
    assert c2.description == "Custom Desc"
    assert c2.problem_statement == "Custom Problem"

    # Validation errors
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        IsIsNotCanvas(title="")
    with pytest.raises(ValueError, match="title must be a non-empty string"):
        IsIsNotCanvas(title=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="description must be a string"):
        IsIsNotCanvas(description=123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="problem_statement must be a non-empty string"):
        IsIsNotCanvas(problem_statement="")
    with pytest.raises(ValueError, match="problem_statement must be a non-empty string"):
        IsIsNotCanvas(problem_statement=False)  # type: ignore[arg-type]


def test_is_is_not_canvas_crud_and_sorting() -> None:
    """IsIsNotCanvas supports row CRUD operations and canonical KT sequence sorting."""
    canvas = IsIsNotCanvas()

    # 1. add_row via dict (added in reverse order: EXTENT, WHEN, WHERE, WHAT)
    canvas.add_row({
        "dimension": "EXTENT",
        "is_data": "52 units",
        "is_not_data": "All units",
    })
    canvas.add_row({
        "dimension": "WHEN",
        "is_data": "Post-assembly test",
        "is_not_data": "Receiving",
    })
    canvas.add_row(
        IsIsNotCanvasRow(
            dimension="WHERE",
            is_data="Milling station",
            is_not_data="Lathe station",
        )
    )
    canvas.add_row(
        IsIsNotCanvasRow(
            dimension="WHAT",
            is_data="Binding defect",
            is_not_data="Surface defect",
        )
    )

    # 2. rows property sorts according to canonical KT_DIMENSIONS sequence (WHAT, WHERE, WHEN, EXTENT)
    row_dims = [r.dimension for r in canvas.rows]
    assert row_dims == ["WHAT", "WHERE", "WHEN", "EXTENT"]

    # 3. get_row_by_dimension
    what_row = canvas.get_row_by_dimension("WHAT")
    assert what_row is not None
    assert what_row.is_data == "Binding defect"

    # Case-insensitive lookup
    assert canvas.get_row_by_dimension("what") is what_row
    assert canvas.get_row_by_dimension("  where  ") is not None
    assert canvas.get_row_by_dimension("NON_EXISTENT") is None

    # Invalid dimension argument type
    with pytest.raises(TypeError, match="dimension must be a string"):
        canvas.get_row_by_dimension(123)  # type: ignore[arg-type]

    # 4. get_rows_by_dimension
    assert len(canvas.get_rows_by_dimension("WHEN")) == 1
    assert len(canvas.get_rows_by_dimension("NON_EXISTENT")) == 0

    # 5. add_row invalid type
    with pytest.raises(TypeError, match="row must be an IsIsNotCanvasRow or dict"):
        canvas.add_row(["invalid"])  # type: ignore[arg-type]

    # 6. remove_row by dimension string
    assert canvas.remove_row("what") is True
    assert canvas.remove_row("what") is False  # Already removed
    assert [r.dimension for r in canvas.rows] == ["WHERE", "WHEN", "EXTENT"]

    # 7. remove_row by IsIsNotCanvasRow object
    where_row = canvas.get_row_by_dimension("WHERE")
    assert where_row is not None
    assert canvas.remove_row(where_row) is True
    assert canvas.remove_row(where_row) is False
    assert [r.dimension for r in canvas.rows] == ["WHEN", "EXTENT"]

    # 8. remove_row by integer index
    assert canvas.remove_row(0) is True  # Removes WHEN
    assert canvas.remove_row(99) is False  # Index out of bounds
    assert [r.dimension for r in canvas.rows] == ["EXTENT"]

    # remove_row invalid type (bool, float)
    with pytest.raises(TypeError, match="dimension_or_index must be str, int, or IsIsNotCanvasRow"):
        canvas.remove_row(True)  # type: ignore[arg-type]

    # 9. set_problem_statement
    canvas.set_problem_statement("Updated problem statement")
    assert canvas.problem_statement == "Updated problem statement"

    with pytest.raises(ValueError, match="problem_statement must be a non-empty string"):
        canvas.set_problem_statement("")
    with pytest.raises(ValueError, match="problem_statement must be a non-empty string"):
        canvas.set_problem_statement(False)  # type: ignore[arg-type]

    # 10. clear_rows
    canvas.clear_rows()
    assert len(canvas.rows) == 0


def test_is_is_not_canvas_scope_and_summary() -> None:
    """IsIsNotCanvas.scope() and get_summary() return structured metrics across states."""
    canvas = IsIsNotCanvas(problem_statement="Filter leak")

    # 1. Empty canvas summary
    s_empty = canvas.get_summary()
    assert s_empty["total_rows"] == 0
    assert s_empty["valid"] is False
    assert s_empty["verdict"] == "EMPTY"
    assert s_empty["complete_dimensions_count"] == 0
    assert s_empty["missing_dimensions_count"] == 4
    assert s_empty["candidate_causes_count"] == 0
    assert "Canvas contains no Is/Is-Not rows." in s_empty["findings"]

    # Empty canvas scope() raises ValueError
    with pytest.raises(ValueError, match="Canvas contains no rows to scope."):
        canvas.scope()

    # 2. Populate full sample
    canvas = IsIsNotCanvas.load_sample()
    assert len(canvas.rows) == 4

    result = canvas.scope()
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert len(result.candidate_causes) == 4

    # Verify candidate cause synthesis updated rows
    for r in canvas.rows:
        assert r.candidate_cause is not None

    s_full = canvas.get_summary()
    assert s_full["total_rows"] == 4
    assert s_full["valid"] is True
    assert s_full["verdict"] == "ACCEPT"
    assert s_full["complete_dimensions_count"] == 4
    assert s_full["missing_dimensions_count"] == 0
    assert s_full["candidate_causes_count"] == 4
    assert len(s_full["findings"]) == 0
    assert len(s_full["recommendations"]) > 0

    # 3. Error state summary (mocking scope failure)
    with patch.object(canvas, "scope", side_effect=RuntimeError("Simulated engine fault")):
        s_err = canvas.get_summary()
        assert s_err["total_rows"] == 4
        assert s_err["valid"] is False
        assert s_err["verdict"] == "ERROR"
        assert s_err["findings"] == ["Simulated engine fault"]


def test_is_is_not_canvas_scope_populates_empty_candidate_causes() -> None:
    """canvas.scope() populates candidate_cause on rows where it was initially None."""
    canvas = IsIsNotCanvas()
    canvas.add_row({
        "dimension": "WHAT",
        "is_data": "Stroke binding",
        "is_not_data": "Rod damage",
        "distinctions": "Face non-parallelism",
        "changes": "Feed misalignment",
    })
    # Before scoping, candidate_cause is None
    what_row = canvas.get_row_by_dimension("WHAT")
    assert what_row is not None
    assert what_row.candidate_cause is None

    result = canvas.scope()
    assert result.valid is True
    assert what_row.candidate_cause is not None
    assert "Face non-parallelism" in what_row.candidate_cause


# ---------------------------------------------------------------------------
# Themed HTML Rendering Tests
# ---------------------------------------------------------------------------


def test_is_is_not_canvas_to_html_themes_and_standalone() -> None:
    """to_html renders dark/light themes, standalone documents, and embeddable containers."""
    canvas = IsIsNotCanvas.load_sample()

    # 1. Dark theme standalone (default)
    h_dark = canvas.to_html(theme="dark", standalone=True)
    assert "<!DOCTYPE html>" in h_dark
    assert "<html lang=\"en\">" in h_dark
    assert "qes-is-is-not-canvas" in h_dark
    assert "Fully Scoped (ACCEPT)" in h_dark
    assert "4/4" in h_dark

    # 2. Light theme embeddable
    h_light = canvas.to_html(theme="light", standalone=False)
    assert "<!DOCTYPE html>" not in h_light
    assert "qes-is-is-not-canvas" in h_light
    assert "#ffffff" in h_light  # Light card background

    # 3. Invalid theme
    with pytest.raises(ValueError, match="theme must be 'dark' or 'light'"):
        canvas.to_html(theme="neon")  # type: ignore[arg-type]


def test_is_is_not_canvas_to_html_empty_and_verdict_branches() -> None:
    """to_html handles empty canvas, WARNING, REJECT, and custom verdict states."""
    # 1. Empty canvas
    c_empty = IsIsNotCanvas(title="Empty Canvas")
    h_empty = c_empty.to_html()
    assert "No Kepner-Tregoe Is/Is-Not rows recorded in canvas" in h_empty
    assert "0/4" in h_empty

    # 2. Warning state (partial dimensions)
    c_warn = IsIsNotCanvas()
    c_warn.add_row({
        "dimension": "WHAT",
        "is_data": "Stroke binding",
        "is_not_data": "Rod damage",
    })
    h_warn = c_warn.to_html()
    assert "Warning (Incomplete)" in h_warn
    assert "Identified Boundary &amp; Scoping Findings:" in h_warn

    # 3. Reject verdict badge
    c_rej = IsIsNotCanvas()
    with patch.object(
        c_rej,
        "get_summary",
        return_value={
            "total_rows": 1,
            "valid": False,
            "verdict": "REJECT",
            "complete_dimensions_count": 0,
            "missing_dimensions_count": 4,
            "candidate_causes_count": 0,
            "findings": ["Rejection finding"],
            "recommendations": ["Fix issues"],
        },
    ):
        h_rej = c_rej.to_html()
        assert "Rejected" in h_rej

    # 4. Custom verdict badge
    with patch.object(
        c_rej,
        "get_summary",
        return_value={
            "total_rows": 1,
            "valid": False,
            "verdict": "CUSTOM_STATUS",
            "complete_dimensions_count": 0,
            "missing_dimensions_count": 4,
            "candidate_causes_count": 0,
            "findings": [],
            "recommendations": ["Custom rec"],
        },
    ):
        h_custom = c_rej.to_html()
        assert "CUSTOM_STATUS" in h_custom


def test_is_is_not_canvas_to_html_alert_box_branches() -> None:
    """to_html covers all combinations of findings and recommendations in alert box."""
    canvas = IsIsNotCanvas()
    canvas.add_row({
        "dimension": "WHAT",
        "is_data": "Leak",
        "is_not_data": "No leak",
    })

    # 1. Both findings and recommendations empty -> recs_html is empty
    with patch.object(
        canvas,
        "get_summary",
        return_value={
            "total_rows": 1,
            "valid": True,
            "verdict": "ACCEPT",
            "complete_dimensions_count": 1,
            "missing_dimensions_count": 3,
            "candidate_causes_count": 0,
            "findings": [],
            "recommendations": [],
        },
    ):
        h_none = canvas.to_html()
        assert "Identified Boundary &amp; Scoping Findings:" not in h_none
        assert "Engineering Recommendations &amp; Hypothesis Testing:" not in h_none

    # 2. Findings only, no recommendations
    with patch.object(
        canvas,
        "get_summary",
        return_value={
            "total_rows": 1,
            "valid": True,
            "verdict": "WARNING",
            "complete_dimensions_count": 1,
            "missing_dimensions_count": 3,
            "candidate_causes_count": 0,
            "findings": ["Only finding"],
            "recommendations": [],
        },
    ):
        h_findings_only = canvas.to_html()
        assert "Identified Boundary &amp; Scoping Findings:" in h_findings_only
        assert "Only finding" in h_findings_only
        assert "Engineering Recommendations &amp; Hypothesis Testing:" not in h_findings_only

    # 3. Recommendations only, no findings
    with patch.object(
        canvas,
        "get_summary",
        return_value={
            "total_rows": 1,
            "valid": True,
            "verdict": "ACCEPT",
            "complete_dimensions_count": 1,
            "missing_dimensions_count": 3,
            "candidate_causes_count": 0,
            "findings": [],
            "recommendations": ["Only recommendation"],
        },
    ):
        h_recs_only = canvas.to_html()
        assert "Identified Boundary &amp; Scoping Findings:" not in h_recs_only
        assert "Engineering Recommendations &amp; Hypothesis Testing:" in h_recs_only
        assert "Only recommendation" in h_recs_only


def test_is_is_not_canvas_to_html_escaping() -> None:
    """to_html escapes special HTML characters in title, problem statement, and row fields."""
    canvas = IsIsNotCanvas(
        title="<Escaped Title & Co>",
        description="<Dangerous Script>",
        problem_statement="<Deviation & Error>",
    )
    canvas.add_row({
        "dimension": "WHAT",
        "is_data": "<Leak observed in sector 1>",
        "is_not_data": "<No leak in sector 2>",
        "distinctions": "<Distinction & Fact>",
        "changes": "<Change & Adjustment>",
        "candidate_cause": "<Hypothesis & Cause>",
    })
    html_out = canvas.to_html()
    assert "&lt;Escaped Title &amp; Co&gt;" in html_out
    assert "&lt;Dangerous Script&gt;" in html_out
    assert "&lt;Deviation &amp; Error&gt;" in html_out
    assert "&lt;Leak observed in sector 1&gt;" in html_out
    assert "&lt;No leak in sector 2&gt;" in html_out
    assert "&lt;Distinction &amp; Fact&gt;" in html_out
    assert "&lt;Change &amp; Adjustment&gt;" in html_out
    assert "&lt;Hypothesis &amp; Cause&gt;" in html_out


# ---------------------------------------------------------------------------
# Helper Functions Unit Tests
# ---------------------------------------------------------------------------


def test_load_sample_is_is_not_canvas_helper() -> None:
    """load_sample_is_is_not_canvas returns loaded IsIsNotCanvas with 4 rows."""
    canvas = load_sample_is_is_not_canvas(title="Helper Sample Canvas")
    assert isinstance(canvas, IsIsNotCanvas)
    assert canvas.title == "Helper Sample Canvas"
    assert len(canvas.rows) == 4


def test_render_is_is_not_helper() -> None:
    """render_is_is_not supports None, IsIsNotMatrix, list of dicts/rows/canvas_rows, and dict."""
    # 1. None -> loads sample
    h1 = render_is_is_not()
    assert "qes-is-is-not-canvas" in h1
    assert "Pneumatic cylinder" in h1

    # 2. None with custom problem statement
    h1_custom_ps = render_is_is_not(problem_statement="Custom problem statement")
    assert "Custom problem statement" in h1_custom_ps

    # 3. IsIsNotMatrix
    matrix_obj = IsIsNotMatrix(
        problem_statement="Matrix Problem",
        rows=[
            IsIsNotRow(
                dimension="WHAT",
                is_data="Defect A",
                is_not_data="Defect B",
            )
        ],
    )
    h2 = render_is_is_not(matrix=matrix_obj, theme="light", standalone=False)
    assert "Matrix Problem" in h2
    assert "<!DOCTYPE html>" not in h2

    # 4. list of dicts
    dict_list = [
        {"dimension": "WHAT", "is_data": "Defect A", "is_not_data": "Defect B"},
        {"dimension": "WHERE", "is_data": "Station 1", "is_not_data": "Station 2"},
    ]
    h3 = render_is_is_not(matrix=dict_list, problem_statement="Dict List Problem")
    assert "Dict List Problem" in h3
    assert "Station 1" in h3

    # 5. list of IsIsNotCanvasRow
    canvas_row_list = [
        IsIsNotCanvasRow(dimension="WHEN", is_data="Morning", is_not_data="Night"),
    ]
    h4 = render_is_is_not(matrix=canvas_row_list)
    assert "Morning" in h4

    # 6. list of IsIsNotRow
    schema_row_list = [
        IsIsNotRow(dimension="EXTENT", is_data="10%", is_not_data="0%"),
    ]
    h5 = render_is_is_not(matrix=schema_row_list)
    assert "10%" in h5

    # 7. dict with rows list
    dict_with_rows = {
        "problem_statement": "Dict with rows",
        "rows": [
            {"dimension": "WHAT", "is_data": "D1", "is_not_data": "D2"},
            IsIsNotCanvasRow(dimension="WHERE", is_data="S1", is_not_data="S2"),
            IsIsNotRow(dimension="WHEN", is_data="T1", is_not_data="T2"),
        ],
    }
    h6 = render_is_is_not(matrix=dict_with_rows)
    assert "Dict with rows" in h6
    assert "D1" in h6
    assert "S1" in h6
    assert "T1" in h6

    # 8. Invalid matrix types & list items
    with pytest.raises(TypeError, match="Expected IsIsNotCanvasRow, IsIsNotRow, or dict in matrix list"):
        render_is_is_not(matrix=["invalid-item"])  # type: ignore[list-item]

    with pytest.raises(TypeError, match="Expected list for rows in dict"):
        render_is_is_not(matrix={"rows": "not-a-list"})

    with pytest.raises(TypeError, match="Expected dict, IsIsNotCanvasRow, or IsIsNotRow in rows"):
        render_is_is_not(matrix={"rows": [123]})

    with pytest.raises(TypeError, match="matrix must be IsIsNotMatrix, list of dicts/rows, dict, or None"):
        render_is_is_not(matrix=123)  # type: ignore[arg-type]



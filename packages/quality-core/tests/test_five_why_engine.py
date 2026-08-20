"""
Unit tests for deterministic 5-Why Root Cause Analysis engine (quality_core.rca.five_why).

Tests:
1. Helper functions: tokenization, content tokens, Jaccard similarity, human blame detection, systemic resolution detection.
2. Dataclass serialization: FiveWhyLinkEval, AntiPatternFinding, SystemicAssessment, FiveWhyValidationResult.
3. Positive controls:
   - Valid 5-step Ford Global 8D bearing induction benchmark case (ACCEPT, valid=True, systemic).
   - Valid 5-step chain with pronoun continuity reaching 1.0 reversibility score.
   - Valid 3-step chain terminating at systemic work instruction policy.
   - Valid chain with intermediate operator error resolved systemically in later steps.
   - Forward ("Why -> Because") and reverse ("Because -> Therefore") evaluation logic.
   - Variations in input formats: FiveWhyChain, DataFrame, list of dicts, list of FiveWhyStep.
   - Custom problem_statement, root_cause override, and leg_type propagation.
4. Negative controls & anti-pattern detection:
   - CIRCULAR_REASONING: repeating problem statement.
   - CIRCULAR_REASONING: repeating earlier step explanation.
   - BLAME_TERMINAL_OPERATOR_ERROR: terminating at operator mistake without systemic resolution.
   - PREMATURE_TERMINATION: 1-step or 2-step chain ending at immediate physical symptom.
   - NON_CAUSAL_JUMP: disconnected step transition with disjoint vocabulary and no pronoun bridge.
5. Systemic classification: SYSTEMIC vs TECHNICAL_PROCESS vs HUMAN_INDIVIDUAL.
6. Score threshold branches: ACCEPT (score >= 0.80), WARNING (0.50 <= score < 0.80), REJECT (score < 0.50 or hard anti-pattern).
7. Input boundary & error handling: TypeError on unsupported types, ValidationError on invalid steps.
"""

from __future__ import annotations

import pandas as pd
import pydantic
import pytest
from quality_core.rca.five_why import (
    AntiPatternFinding,
    FiveWhyLinkEval,
    FiveWhyValidationResult,
    SystemicAssessment,
    _content_tokens,
    _has_systemic_resolution,
    _is_human_blame_statement,
    _jaccard_similarity,
    _tokenize,
    validate_five_why_chain,
)
from quality_core.rca.schema import FiveWhyChain, FiveWhyStep

# ---------------------------------------------------------------------------
# Benchmark Data Fixtures
# ---------------------------------------------------------------------------

_FORD_8D_STEPS = [
    {
        "step_number": 1,
        "why": "Why was the bearing worn out?",
        "because": "It had dried up.",
    },
    {
        "step_number": 2,
        "why": "Why did the bearing dry out?",
        "because": "The operator did not carry out shift autonomous maintenance routines.",
    },
    {
        "step_number": 3,
        "why": "Why did the operator not follow the maintenance routine completely?",
        "because": "He was not properly trained during the induction.",
    },
    {
        "step_number": 4,
        "why": "Why was he not trained in the induction?",
        "because": "Its induction program lost this outside the sheet.",
    },
    {
        "step_number": 5,
        "why": "Why was this missing on the sheet?",
        "because": "The induction plan was not signed by Engineering (Systemic Root Cause).",
    },
]

_PRONOUN_CONTINUOUS_STEPS = [
    {
        "step_number": 1,
        "why": "Why was the bearing worn out?",
        "because": "The bearing dried up.",
    },
    {
        "step_number": 2,
        "why": "Why did it dry up?",
        "because": "The operator did not carry out shift autonomous maintenance routines.",
    },
    {
        "step_number": 3,
        "why": "Why did the operator not follow the maintenance routine completely?",
        "because": "He was not properly trained during the induction.",
    },
    {
        "step_number": 4,
        "why": "Why was he not trained in the induction?",
        "because": "Its induction program lost this outside the sheet.",
    },
    {
        "step_number": 5,
        "why": "Why was this missing on the sheet?",
        "because": "The induction plan was not signed by Engineering (Systemic Root Cause).",
    },
]


# ---------------------------------------------------------------------------
# 1. Helper Functions Unit Tests
# ---------------------------------------------------------------------------


def test_tokenize_and_content_tokens() -> None:
    """Test text tokenization and stop-word filtering."""
    text = "The operator did NOT carry out the shift maintenance routine!"
    tokens = _tokenize(text)
    assert "operator" in tokens
    assert "not" in tokens
    assert "maintenance" in tokens
    assert "routine" in tokens

    content = _content_tokens(text)
    assert "operator" in content
    assert "maintenance" in content
    assert "routine" in content
    assert "the" not in content
    assert "did" not in content
    assert "out" not in content


def test_jaccard_similarity_edges() -> None:
    """Test Jaccard similarity edge cases (empty sets, disjoint sets, identical sets)."""
    assert _jaccard_similarity(set(), set()) == 0.0
    assert _jaccard_similarity({"motor", "bearing"}, set()) == 0.0
    assert _jaccard_similarity(set(), {"motor", "bearing"}) == 0.0

    set_a = {"bearing", "lubrication", "oil"}
    set_b = {"bearing", "lubrication", "oil"}
    assert _jaccard_similarity(set_a, set_b) == 1.0

    set_c = {"conveyor", "sensor"}
    assert _jaccard_similarity(set_a, set_c) == 0.0

    set_d = {"bearing", "heat"}
    # intersection: {'bearing'} (1), union: {'bearing', 'lubrication', 'oil', 'heat'} (4) -> 0.25
    assert _jaccard_similarity(set_a, set_d) == 0.25


def test_is_human_blame_statement() -> None:
    """Test detection of human error blame statements vs systemic or technical statements."""
    # Explicit phrases
    assert _is_human_blame_statement("Operator error during setup.") is True
    assert _is_human_blame_statement("Technician forgot to tighten the bolt.") is True
    assert _is_human_blame_statement("Worker mistake due to carelessness.") is True
    assert _is_human_blame_statement("The assembler was not paying attention.") is True
    assert _is_human_blame_statement("Operator did not follow work instructions.") is True

    # Noun + verb combinations
    assert _is_human_blame_statement("The machinist skipped the calibration step.") is True
    assert _is_human_blame_statement("The inspector overlooked the defect.") is True

    # Non-blame statements
    assert _is_human_blame_statement("The bearing dried up due to high temperature.") is False
    assert _is_human_blame_statement("The induction plan was not signed by Engineering.") is False
    assert _is_human_blame_statement("Voltage spike occurred on the power grid.") is False


def test_has_systemic_resolution() -> None:
    """Test detection of systemic policies, training, and error-proofing factors."""
    # Terms
    assert _has_systemic_resolution("Engineering did not update the procedure.") is True
    assert _has_systemic_resolution("The maintenance checklist was missing step 4.") is True
    assert _has_systemic_resolution("No pokayoke errorproofing device installed.") is True
    assert _has_systemic_resolution("Autonomous maintenance schedule was not established.") is True

    # Phrases
    assert _has_systemic_resolution("The training program did not cover this machine.") is True
    assert _has_systemic_resolution("Work instruction lacked sign-off.") is True
    assert _has_systemic_resolution("Missing poka-yoke on the fixture.") is True

    # Non-systemic
    assert _has_systemic_resolution("Operator was distracted.") is False
    assert _has_systemic_resolution("Hydraulic pump seal ruptured.") is False


# ---------------------------------------------------------------------------
# 2. Dataclass Serialization Tests
# ---------------------------------------------------------------------------


def test_dataclasses_to_dict() -> None:
    """Test to_dict serialization on all 5-Why result dataclasses."""
    link = FiveWhyLinkEval(
        step_number=1,
        why="Why did it stop?",
        because="Fuse blew.",
        reverse_statement="Because fuse blew, therefore it stopped.",
        is_reversible=True,
        reversibility_score=1.0,
        notes="All sound.",
    )
    link_dict = link.to_dict()
    assert link_dict["step_number"] == 1
    assert link_dict["why"] == "Why did it stop?"
    assert link_dict["because"] == "Fuse blew."
    assert link_dict["is_reversible"] is True

    anti = AntiPatternFinding(
        code="CIRCULAR_REASONING",
        severity="error",
        step_number=3,
        message="Step 3 circular reasoning.",
        recommendation="Reformulate step.",
    )
    anti_dict = anti.to_dict()
    assert anti_dict["code"] == "CIRCULAR_REASONING"
    assert anti_dict["severity"] == "error"
    assert anti_dict["step_number"] == 3

    systemic = SystemicAssessment(
        classification="SYSTEMIC",
        is_systemic=True,
        terminal_cause="Policy missing.",
        systemic_factors=["policy"],
        recommendations=["Update policy."],
    )
    sys_dict = systemic.to_dict()
    assert sys_dict["classification"] == "SYSTEMIC"
    assert sys_dict["is_systemic"] is True

    res = FiveWhyValidationResult(
        basis="AIAG CQI-20",
        valid=True,
        verdict="ACCEPT",
        reversibility_score=1.0,
        problem_statement="Machine stopped",
        root_cause="Policy missing",
        total_steps=1,
        link_evaluations=[link],
        anti_patterns=[anti],
        systemic_assessment=systemic,
        recommendations=["Update policy."],
        leg_type="occurrence",
    )
    res_dict = res.to_dict()
    assert res_dict["basis"] == "AIAG CQI-20"
    assert res_dict["valid"] is True
    assert res_dict["verdict"] == "ACCEPT"
    assert res_dict["leg_type"] == "occurrence"
    assert len(res_dict["link_evaluations"]) == 1
    assert len(res_dict["anti_patterns"]) == 1


# ---------------------------------------------------------------------------
# 3. Positive Controls & Benchmark Causal Chains
# ---------------------------------------------------------------------------


def test_validate_five_why_ford_8d_benchmark() -> None:
    """Ford Global 8D bearing induction benchmark case passes with ACCEPT, valid=True, and SYSTEMIC."""
    result = validate_five_why_chain(
        data=_FORD_8D_STEPS,
        problem_statement="Hole positions outside of tolerance on CNC drilling station",
        root_cause="The induction plan was not signed by Engineering",
        leg_type="occurrence",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.reversibility_score == 1.0
    assert result.total_steps == 5
    assert result.problem_statement == "Hole positions outside of tolerance on CNC drilling station"
    assert result.root_cause == "The induction plan was not signed by Engineering"
    assert result.leg_type == "occurrence"

    # Reverse statements check
    assert "Because It had dried up, therefore Hole positions outside of tolerance on CNC drilling station." in result.link_evaluations[0].reverse_statement
    assert "Because The operator did not carry out shift autonomous maintenance routines, therefore It had dried up." in result.link_evaluations[1].reverse_statement

    # Systemic assessment
    assert result.systemic_assessment.classification == "SYSTEMIC"
    assert result.systemic_assessment.is_systemic is True
    assert "induction" in result.systemic_assessment.systemic_factors or "engineering" in result.systemic_assessment.systemic_factors
    assert any("permanent corrective action" in r for r in result.recommendations)


def test_validate_five_why_pronoun_continuous_chain() -> None:
    """Pronoun-linked 5-step chain achieves 1.0 reversibility score and passes with ACCEPT."""
    result = validate_five_why_chain(
        data=_PRONOUN_CONTINUOUS_STEPS,
        problem_statement="Hole positions outside of tolerance on CNC drilling station",
        root_cause="The induction plan was not signed by Engineering",
    )
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.reversibility_score == 1.0
    for link in result.link_evaluations:
        assert link.is_reversible is True
        assert link.reversibility_score == 1.0


def test_validate_five_why_valid_3step_systemic_chain() -> None:
    """Valid 3-step chain terminating at systemic work instruction passes with ACCEPT."""
    steps = [
        {"step_number": 1, "why": "Why did the motor overheat?", "because": "The cooling fan stopped turning."},
        {"step_number": 2, "why": "Why did the cooling fan stop?", "because": "The electrical fuse blew from an incorrect rating."},
        {"step_number": 3, "why": "Why was an incorrect rating installed?", "because": "The maintenance work instruction lacked a fuse specification table."},
    ]
    result = validate_five_why_chain(
        data=steps,
        problem_statement="Motor overheated during shift",
    )
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.reversibility_score == 1.0
    assert result.systemic_assessment.classification == "SYSTEMIC"
    assert result.systemic_assessment.is_systemic is True


def test_validate_five_why_intermediate_human_blame_statement() -> None:
    """Intermediate step with human error statement is noted and resolved systemically in subsequent steps."""
    steps = [
        {"step_number": 1, "why": "Why was part out of tolerance?", "because": "Drill offset was wrong."},
        {"step_number": 2, "why": "Why was offset wrong?", "because": "The operator forgot to check the offset table."},
        {"step_number": 3, "why": "Why did operator forget?", "because": "Workstation setup procedure lacked a sign-off checklist."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Part out of tolerance")
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.link_evaluations[1].notes is not None
    assert "Intermediate human factor identified" in result.link_evaluations[1].notes


def test_validate_five_why_default_problem_statement_fallback() -> None:
    """When problem_statement is default 'Problem Statement', reverse statement of Step 1 falls back to step.why."""
    steps = [
        {"step_number": 1, "why": "Why did pump stop?", "because": "Impeller seized from debris."},
        {"step_number": 2, "why": "Why did debris enter impeller?", "because": "Suction strainer mesh was torn."},
        {"step_number": 3, "why": "Why was suction strainer torn?", "because": "Preventive maintenance inspection procedure was not scheduled."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Problem Statement")
    assert result.link_evaluations[0].reverse_statement == "Because Impeller seized from debris, therefore Why did pump stop?."


def test_validate_five_why_input_data_types() -> None:
    """validate_five_why_chain accepts FiveWhyChain, DataFrame, list of FiveWhyStep, and list of dicts."""
    # 1. FiveWhyChain
    fw_chain = FiveWhyChain(
        problem_statement="Conveyor stopped",
        steps=[
            FiveWhyStep(step_number=1, why="Why stopped?", because="Belt slipped."),
            FiveWhyStep(step_number=2, why="Why belt slipped?", because="Tensioner bracket loose."),
            FiveWhyStep(step_number=3, why="Why bracket loose?", because="Standard torque specification omitted from assembly procedure."),
        ],
    )
    res1 = validate_five_why_chain(fw_chain)
    assert res1.valid is True
    assert res1.total_steps == 3

    # 2. DataFrame
    df = pd.DataFrame([
        {"step_number": 1, "why": "Why stopped?", "because": "Belt slipped."},
        {"step_number": 2, "why": "Why belt slipped?", "because": "Tensioner bracket loose."},
        {"step_number": 3, "why": "Why bracket loose?", "because": "Standard torque specification omitted from assembly procedure."},
    ])
    res2 = validate_five_why_chain(df, problem_statement="Conveyor stopped")
    assert res2.valid is True

    # 3. List of FiveWhyStep objects
    step_objs = [
        FiveWhyStep(step_number=1, why="Why stopped?", because="Belt slipped."),
        FiveWhyStep(step_number=2, why="Why belt slipped?", because="Tensioner bracket loose."),
        FiveWhyStep(step_number=3, why="Why bracket loose?", because="Standard torque specification omitted from assembly procedure."),
    ]
    res3 = validate_five_why_chain(step_objs, problem_statement="Conveyor stopped")
    assert res3.valid is True

    # 4. List of dicts
    dict_steps = [
        {"step_number": 1, "why": "Why stopped?", "because": "Belt slipped."},
        {"step_number": 2, "why": "Why belt slipped?", "because": "Tensioner bracket loose."},
        {"step_number": 3, "why": "Why bracket loose?", "because": "Standard torque specification omitted from assembly procedure."},
    ]
    res4 = validate_five_why_chain(dict_steps, problem_statement="Conveyor stopped")
    assert res4.valid is True


# ---------------------------------------------------------------------------
# 4. Negative Controls & Anti-Pattern Rejections
# ---------------------------------------------------------------------------


def test_circular_reasoning_with_problem_statement_rejected() -> None:
    """Chain where step repeats problem statement is flagged with CIRCULAR_REASONING and rejected."""
    steps = [
        {"step_number": 1, "why": "Why did the engine stall?", "because": "The engine stalled unexpectedly."},
        {"step_number": 2, "why": "Why did it stall unexpectedly?", "because": "Fuel flow stopped due to clogged filter."},
        {"step_number": 3, "why": "Why was filter clogged?", "because": "Preventative maintenance procedure was missing filter replacement interval."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Engine stalled unexpectedly")
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert any(ap.code == "CIRCULAR_REASONING" and ap.step_number == 1 for ap in result.anti_patterns)
    assert result.link_evaluations[0].is_reversible is False
    assert result.link_evaluations[0].reversibility_score == 0.0


def test_circular_reasoning_between_steps_rejected() -> None:
    """Chain where Step 3 repeats Step 1 is flagged with CIRCULAR_REASONING and rejected."""
    steps = [
        {"step_number": 1, "why": "Why did conveyor stop?", "because": "The drive belt jammed in the pulley."},
        {"step_number": 2, "why": "Why did drive belt jam?", "because": "The motor shaft stopped turning."},
        {"step_number": 3, "why": "Why did motor shaft stop turning?", "because": "The drive belt jammed in the pulley."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Conveyor line stopped")
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert any(ap.code == "CIRCULAR_REASONING" and ap.step_number == 3 for ap in result.anti_patterns)
    assert result.link_evaluations[2].is_reversible is False
    assert result.link_evaluations[2].reversibility_score == 0.0


def test_blame_terminal_operator_error_rejected() -> None:
    """Chain terminating at operator error without systemic resolution is flagged with BLAME_TERMINAL_OPERATOR_ERROR and rejected."""
    steps = [
        {"step_number": 1, "why": "Why was hole off-center?", "because": "The drill fixture was misaligned."},
        {"step_number": 2, "why": "Why was drill fixture misaligned?", "because": "The operator forgot to tighten clamp bolts."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Hole off-center")
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert result.systemic_assessment.classification == "HUMAN_INDIVIDUAL"
    assert result.systemic_assessment.is_systemic is False
    assert any(ap.code == "BLAME_TERMINAL_OPERATOR_ERROR" for ap in result.anti_patterns)
    assert result.link_evaluations[1].is_reversible is False
    assert result.link_evaluations[1].reversibility_score == 0.0


def test_premature_termination_warning() -> None:
    """Chain terminating in < 3 steps at technical process cause produces PREMATURE_TERMINATION warning."""
    steps = [
        {"step_number": 1, "why": "Why did lamp burn out?", "because": "Filament melted from excessive voltage."},
        {"step_number": 2, "why": "Why was voltage excessive?", "because": "Transformer primary coil shorted internally."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Lamp burned out")
    assert result.systemic_assessment.classification == "TECHNICAL_PROCESS"
    assert result.systemic_assessment.is_systemic is False
    assert any(ap.code == "PREMATURE_TERMINATION" for ap in result.anti_patterns)
    # Reversibility score is high (1.0) and PREMATURE_TERMINATION is warning, so verdict is ACCEPT
    assert result.verdict == "ACCEPT"
    assert result.valid is True


def test_non_causal_jump_detection() -> None:
    """Step with completely disjoint vocabulary and no pronoun bridge generates NON_CAUSAL_JUMP warning."""
    steps = [
        {"step_number": 1, "why": "Why did the bearing overheat?", "because": "The grease dried up completely."},
        {"step_number": 2, "why": "Why did warehouse inventory mismatch yesterday?", "because": "Barcode scanner battery voltage dropped."},
        {"step_number": 3, "why": "Why did scanner battery drop?", "because": "Charging dock maintenance procedure was missing."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Bearing overheated")
    assert any(ap.code == "NON_CAUSAL_JUMP" and ap.step_number == 2 for ap in result.anti_patterns)
    assert result.link_evaluations[1].reversibility_score <= 0.3
    # Step 1: 1.0, Step 2: 0.3, Step 3: 1.0 -> avg = 0.7667 -> WARNING verdict
    assert result.verdict == "WARNING"
    assert result.valid is True


def test_non_causal_jump_with_pronoun_reference_passes() -> None:
    """Step with pronoun reference ('it', 'this', 'that') does not trigger NON_CAUSAL_JUMP."""
    steps = [
        {"step_number": 1, "why": "Why did bearing seize?", "because": "Lubricant dried up."},
        {"step_number": 2, "why": "Why did it dry up?", "because": "Autonomous maintenance routine was omitted."},
        {"step_number": 3, "why": "Why was routine omitted?", "because": "Induction training procedure lacked maintenance checklist."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Bearing seized")
    assert not any(ap.code == "NON_CAUSAL_JUMP" for ap in result.anti_patterns)
    assert result.verdict == "ACCEPT"


def test_reversibility_score_under_half_triggers_rejection() -> None:
    """Chain with multiple non-causal jumps bringing score < 0.50 results in REJECT verdict."""
    steps = [
        {"step_number": 1, "why": "Why did bearing seize?", "because": "Lubricant dried up."},
        {"step_number": 2, "why": "Why did warehouse scanner fail?", "because": "Battery discharged."},
        {"step_number": 3, "why": "Why did cafeteria coffee machine leak?", "because": "Water valve cracked."},
        {"step_number": 4, "why": "Why did office printer jam?", "because": "Paper tray misaligned."},
    ]
    result = validate_five_why_chain(data=steps, problem_statement="Bearing seized")
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert result.reversibility_score < 0.50


# ---------------------------------------------------------------------------
# 5. Input Boundaries & Error Handling
# ---------------------------------------------------------------------------


def test_validate_five_why_type_errors() -> None:
    """Passing unsupported types raises TypeError."""
    with pytest.raises(TypeError, match="Expected FiveWhyChain, DataFrame, list of dicts/steps, or dict"):
        validate_five_why_chain(12345)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Expected FiveWhyChain, DataFrame, list of dicts/steps, or dict"):
        validate_five_why_chain("not a chain")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Expected FiveWhyChain, DataFrame, list of dicts/steps, or dict"):
        validate_five_why_chain(None)  # type: ignore[arg-type]


def test_validate_five_why_schema_validation_errors() -> None:
    """Passing invalid steps raises pydantic.ValidationError."""
    # Empty steps list
    with pytest.raises(pydantic.ValidationError, match="FiveWhyChain must contain at least one step"):
        validate_five_why_chain([])

    # Non-consecutive step numbers
    with pytest.raises(pydantic.ValidationError, match="step numbers must be consecutive"):
        validate_five_why_chain([
            {"step_number": 1, "why": "Why?", "because": "Because 1."},
            {"step_number": 3, "why": "Why?", "because": "Because 3."},
        ])

    # Blank why string
    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        validate_five_why_chain([
            {"step_number": 1, "why": "   ", "because": "Because 1."},
        ])


def test_stem_and_jaccard_helpers() -> None:
    """Test _stem and _jaccard_similarity helper functions directly."""
    from quality_core.rca.five_why import _jaccard_similarity, _stem

    assert _stem("testing") == "test"
    assert _stem("verification") == "verific"
    assert _stem("measurement") == "measure"
    assert _stem("operational") == "operation"
    assert _stem("quickly") == "quick"
    assert _stem("supplies") == "supply"
    assert _stem("queries") == "query"
    assert _stem("short") == "short"
    assert _stem("no") == "no"

    assert _jaccard_similarity(set(), {"a"}) == 0.0
    assert _jaccard_similarity({"a"}, set()) == 0.0
    assert _jaccard_similarity({"a", "b"}, {"b", "c"}) == 1 / 3


def test_recommendation_deduplication() -> None:
    """Test recommendation synthesis deduplication across multiple anti-patterns."""
    steps = [
        {"step_number": 1, "why": "Why did bearing seize?", "because": "Lubricant dried out."},
        {"step_number": 2, "why": "Why random jump alpha?", "because": "Transformer burned out."},
        {"step_number": 3, "why": "Why random jump beta?", "because": "Software crashed."},
    ]
    res = validate_five_why_chain(steps, problem_statement="Problem")
    assert len(res.recommendations) == len(set(res.recommendations))

"""
Positive scorecards and negative controls for 5-Why Root Cause Analysis (quality_core.rca.five_why).

Benchmark references:
1. Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Section D4 (Bearing Induction Case).
2. Nancy R. Tague, The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005), Chapter 5.
3. AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section 5 (3-Legged 5-Why).

Negative controls:
- Injected circular loop -> REJECT.
- Injected blame-terminal operator error -> REJECT.
- Injected non-causal disconnect -> WARNING or REJECT.
"""

from __future__ import annotations

from quality_core.rca.five_why import validate_five_why_chain

# ---------------------------------------------------------------------------
# 1. Positive Scorecards vs Published Benchmarks
# ---------------------------------------------------------------------------


def test_scorecard_ford_global_8d_bearing_case() -> None:
    """Benchmark: Ford Global 8D Hole Position / Bearing Induction Case (p. 42).

    1. Why was the bearing worn out? -> Because it had dried up.
    2. Why did the bearing dry out? -> Because the operator did not carry out shift autonomous maintenance routines.
    3. Why did the operator not follow routine? -> Because he was not properly trained during the induction.
    4. Why was he not trained in induction? -> Because its induction program lost this outside the sheet.
    5. Why was this missing on sheet? -> Because the induction plan was not signed by Engineering.
    """
    steps = [
        {"step_number": 1, "why": "Why was the bearing worn out?", "because": "It had dried up."},
        {"step_number": 2, "why": "Why did the bearing dry out?", "because": "The operator did not carry out shift autonomous maintenance routines."},
        {"step_number": 3, "why": "Why did the operator not follow the maintenance routine completely?", "because": "He was not properly trained during the induction."},
        {"step_number": 4, "why": "Why was he not trained in the induction?", "because": "Its induction program lost this outside the sheet."},
        {"step_number": 5, "why": "Why was this missing on the sheet?", "because": "The induction plan was not signed by Engineering (Systemic Root Cause)."},
    ]

    result = validate_five_why_chain(
        data=steps,
        problem_statement="Hole positions outside of tolerance on CNC drilling station",
        root_cause="The induction plan was not signed by Engineering",
        leg_type="occurrence",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.reversibility_score == 1.0
    assert result.total_steps == 5
    assert result.systemic_assessment.classification == "SYSTEMIC"
    assert result.systemic_assessment.is_systemic is True


def test_scorecard_asq_quality_toolbox_travel_hassles_case() -> None:
    """Benchmark: ASQ The Quality Toolbox (2nd Ed, p. 515) Root Cause Investigation.

    Causal chain drilling down past immediate operational symptoms to systemic training program omission.
    """
    steps = [
        {"step_number": 1, "why": "Why did the sales representative miss the client meeting?", "because": "The scheduled airport shuttle arrived 45 minutes late."},
        {"step_number": 2, "why": "Why did the shuttle arrive late?", "because": "The driver encountered heavy congestion on Highway 101."},
        {"step_number": 3, "why": "Why did the driver take the congested Highway 101?", "because": "The driver was unfamiliar with alternative detour routes."},
        {"step_number": 4, "why": "Why was the driver unfamiliar with detour routes?", "because": "No standard driver route training program exists in fleet management."},
    ]

    result = validate_five_why_chain(
        data=steps,
        problem_statement="Sales representative missed key client presentation",
        root_cause="No standard driver route training program exists in fleet management",
        leg_type="occurrence",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.reversibility_score == 1.0
    assert result.total_steps == 4
    assert result.systemic_assessment.classification == "SYSTEMIC"
    assert result.systemic_assessment.is_systemic is True
    assert len(result.anti_patterns) == 0


def test_scorecard_aiag_cqi20_three_legged_5why() -> None:
    """Benchmark: AIAG CQI-20 Section 5 3-Legged 5-Why (Occurrence, Escape, Systemic legs)."""
    # Leg 1: Occurrence
    occ_steps = [
        {"step_number": 1, "why": "Why did the seal leak oil?", "because": "The rubber seal experienced excessive abrasive wear."},
        {"step_number": 2, "why": "Why did the seal experience excessive wear?", "because": "The shaft surface finish was rougher than Ra 0.4 um."},
        {"step_number": 3, "why": "Why was the shaft finish too rough?", "because": "Grinding wheel dressing procedure was not performed per schedule."},
    ]
    occ_res = validate_five_why_chain(
        data=occ_steps,
        problem_statement="Oil leak from pump drive seal",
        leg_type="occurrence",
    )
    assert occ_res.valid is True
    assert occ_res.verdict == "ACCEPT"
    assert occ_res.leg_type == "occurrence"
    assert occ_res.systemic_assessment.is_systemic is True

    # Leg 2: Escape / Non-Detection
    esc_steps = [
        {"step_number": 1, "why": "Why was the rough shaft shipped to assembly?", "because": "The in-process surface roughness check was bypassed."},
        {"step_number": 2, "why": "Why was the roughness check bypassed?", "because": "The profilometer calibration was expired and locked out."},
        {"step_number": 3, "why": "Why was the profilometer not calibrated?", "because": "The quality control plan omitted a gauge calibration schedule."},
    ]
    esc_res = validate_five_why_chain(
        data=esc_steps,
        problem_statement="Defective shaft escaped to final assembly",
        leg_type="escape",
    )
    assert esc_res.valid is True
    assert esc_res.verdict == "ACCEPT"
    assert esc_res.leg_type == "escape"
    assert esc_res.systemic_assessment.is_systemic is True

    # Leg 3: Systemic Planning
    sys_steps = [
        {"step_number": 1, "why": "Why did APQP planning fail to anticipate dressing frequency?", "because": "The PFMEA did not identify grinding wheel wear as a special cause."},
        {"step_number": 2, "why": "Why was wheel wear omitted from PFMEA?", "because": "The technical design review guideline lacked grinding process risk checklists."},
        {"step_number": 3, "why": "Why was the guideline missing risk checklists?", "because": "Engineering governance procedure for lessons learned was not established."},
    ]
    sys_res = validate_five_why_chain(
        data=sys_steps,
        problem_statement="Systemic planning process failed to prevent shaft defect",
        leg_type="systemic",
    )
    assert sys_res.valid is True
    assert sys_res.verdict == "ACCEPT"
    assert sys_res.leg_type == "systemic"
    assert sys_res.systemic_assessment.is_systemic is True


# ---------------------------------------------------------------------------
# 2. Mandatory Negative Control Scorecards
# ---------------------------------------------------------------------------


def test_scorecard_negative_control_injected_circular_loop() -> None:
    """Negative Control: Injecting circular reasoning repeating Step 1 forces REJECT verdict."""
    bad_steps = [
        {"step_number": 1, "why": "Why was the bearing worn out?", "because": "The drive bearing dried up completely."},
        {"step_number": 2, "why": "Why did the bearing dry out?", "because": "The autonomous maintenance routine was omitted."},
        {"step_number": 3, "why": "Why was maintenance routine omitted?", "because": "The drive bearing dried up completely."},  # Exact circular repeat of Step 1
    ]
    result = validate_five_why_chain(
        data=bad_steps,
        problem_statement="Hole positions outside of tolerance",
    )
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert any(ap.code == "CIRCULAR_REASONING" for ap in result.anti_patterns)


def test_scorecard_negative_control_injected_blame_terminal_cause() -> None:
    """Negative Control: Terminating at operator error without systemic resolution forces REJECT verdict."""
    bad_steps = [
        {"step_number": 1, "why": "Why was the bearing worn out?", "because": "It had dried up."},
        {"step_number": 2, "why": "Why did the bearing dry out?", "because": "The operator did not carry out maintenance routines."},
        {"step_number": 3, "why": "Why did the operator not carry out routines?", "because": "The technician forgot to check the machine."},  # Terminal operator blame
    ]
    result = validate_five_why_chain(
        data=bad_steps,
        problem_statement="Bearing worn out",
    )
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert result.systemic_assessment.classification == "HUMAN_INDIVIDUAL"
    assert any(ap.code == "BLAME_TERMINAL_OPERATOR_ERROR" for ap in result.anti_patterns)


def test_scorecard_negative_control_injected_non_causal_jump() -> None:
    """Negative Control: Injecting non-causal disconnected step generates warning finding and degrades score."""
    bad_steps = [
        {"step_number": 1, "why": "Why was the bearing worn out?", "because": "It had dried up."},
        {"step_number": 2, "why": "Why did cafeteria refrigerator temperature rise?", "because": "Thermostat sensor malfunctioned."},
        {"step_number": 3, "why": "Why did thermostat malfunction?", "because": "Vendor engineering specification was missing."},
    ]
    result = validate_five_why_chain(
        data=bad_steps,
        problem_statement="Bearing worn out",
    )
    assert any(ap.code == "NON_CAUSAL_JUMP" and ap.step_number == 2 for ap in result.anti_patterns)
    assert result.reversibility_score < 1.0
    assert result.verdict in ("WARNING", "REJECT")

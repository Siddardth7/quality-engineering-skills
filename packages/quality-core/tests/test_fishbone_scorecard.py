"""
Positive scorecards and negative controls for 6M Fishbone Cause-and-Effect Analysis (quality_core.rca.fishbone).

Benchmark references:
1. Sentinel-8D Pneumatic Cylinder Manufacturing Case Study (12 causes across 6M).
2. Kaoru Ishikawa, Guide to Quality Control (2nd Revised Edition, 1986), Chapter 3 (Wave Solder / Dispersion Case).
3. AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section G1 & Figure 34.
4. Nancy R. Tague, The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005), Chapter 5.

Mandatory negative controls:
- Injected empty dataset -> REJECT.
- Injected empty branch / bare leg omission -> WARNING.
- Injected duplicate causes within and across categories -> WARNING.
- Injected single-branch operator bias concentration (>= 75%) -> WARNING.
"""

from __future__ import annotations

from quality_core.canvas.rca import SAMPLE_FISHBONE_CAUSES
from quality_core.rca.fishbone import categorize_fishbone
from quality_core.rca.schema import CATEGORY_6M_VALUES

# ---------------------------------------------------------------------------
# 1. Positive Scorecards vs Published Benchmarks
# ---------------------------------------------------------------------------


def test_scorecard_sentinel_8d_pneumatic_cylinder_case() -> None:
    """Benchmark 1: Sentinel-8D Pneumatic Cylinder Case Study (12 causes balanced across 6M).

    Validates all 6 branches populated, zero duplicate causes, balanced concentration,
    and returns ACCEPT verdict with actionable verification recommendation.
    """
    result = categorize_fishbone(
        data=SAMPLE_FISHBONE_CAUSES,
        effect_statement="Pneumatic cylinder stroke binding and seal leakage",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_causes == 12
    assert result.empty_branches == []
    assert len(result.duplicate_causes) == 0
    assert len(result.uncategorized_causes) == 0
    assert len(result.warnings) == 0
    for branch in CATEGORY_6M_VALUES:
        assert result.branch_counts[branch] == 2
        assert len(result.grouped_causes[branch]) == 2
    assert any("well-balanced" in r for r in result.recommendations)


def test_scorecard_ishikawa_1986_wave_solder_dispersion_case() -> None:
    """Benchmark 2: Kaoru Ishikawa (1986) Chapter 3 Wave Solder Bridging Defect Case.

    Validates 6M dispersion branching: raw materials, equipment, method of work,
    measuring method, workers, and environment.
    """
    wave_solder_causes = [
        {"category": "Man", "cause": "Soldering iron angle inconsistent among operators", "sub_category": "Technique"},
        {"category": "Machine", "cause": "Preheater temperature sensor calibration drift", "sub_category": "Sensor"},
        {"category": "Method", "cause": "PCB conveyor speed setting too high for board thickness", "sub_category": "Standard Work"},
        {"category": "Material", "cause": "Solder alloy purity contaminated with copper (> 0.3%)", "sub_category": "Alloy"},
        {"category": "Measurement", "cause": "Dross height inspection gauge worn out", "sub_category": "Gage"},
        {"category": "Environment", "cause": "Flux exhaust hood draft air velocity insufficient", "sub_category": "Ventilation"},
    ]

    result = categorize_fishbone(
        data=wave_solder_causes,
        effect_statement="Wave soldering bridging defects on PCB through-hole joints",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_causes == 6
    assert result.empty_branches == []
    assert all(result.branch_counts[b] == 1 for b in CATEGORY_6M_VALUES)
    assert len(result.warnings) == 0


def test_scorecard_aiag_cqi20_figure34_stamping_case() -> None:
    """Benchmark 3: AIAG CQI-20 Figure 34 6M Cause-and-Effect Analysis (Stamping Hole Burr Defect)."""
    stamping_causes = [
        {"category": "Man Power", "cause": "Die changeover setup personnel not certified", "sub_category": "Skill"},
        {"category": "Machine", "cause": "Punch press guide bushing excessive clearance", "sub_category": "Tooling"},
        {"category": "Method", "cause": "Die sharpening frequency interval omitted in PM plan", "sub_category": "Maintenance"},
        {"category": "Material", "cause": "Sheet steel tensile yield strength variation batch-to-batch", "sub_category": "Raw Material"},
        {"category": "Measure", "cause": "Optical burr height micrometer zero-point offset", "sub_category": "Metrology"},
        {"category": "Environment", "cause": "Press shop ambient humidity causing coil surface condensation", "sub_category": "Humidity"},
    ]

    result = categorize_fishbone(
        data=stamping_causes,
        effect_statement="Excessive burr height on stamped bracket holes",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_causes == 6
    assert result.empty_branches == []
    # Verify alias normalization in scorecard
    assert result.branch_counts["Man"] == 1
    assert result.branch_counts["Measurement"] == 1


# ---------------------------------------------------------------------------
# 2. Mandatory Negative Control Scorecards
# ---------------------------------------------------------------------------


def test_scorecard_negative_control_empty_dataset() -> None:
    """Negative Control 1: Injected empty dataset forces REJECT verdict."""
    result = categorize_fishbone(
        data=[],
        effect_statement="Uninvestigated defect mode",
    )

    assert result.valid is False
    assert result.verdict == "REJECT"
    assert result.total_causes == 0
    assert len(result.empty_branches) == 6
    assert any("contains no causes" in w for w in result.warnings)


def test_scorecard_negative_control_bare_leg_omission() -> None:
    """Negative Control 2: Bare leg omission (omitting Material & Environment) forces WARNING verdict.

    Grounding: AIAG CQI-20 Section G1 ("Pay attention to legs that are bare").
    """
    incomplete_causes = [
        {"category": "Man", "cause": "Operator hurried"},
        {"category": "Machine", "cause": "Spindle loose"},
        {"category": "Method", "cause": "Procedure omitted step"},
        {"category": "Measurement", "cause": "Gage uncalibrated"},
    ]

    result = categorize_fishbone(
        data=incomplete_causes,
        effect_statement="Assembly defect",
    )

    assert result.valid is True
    assert result.verdict == "WARNING"
    assert "Material" in result.empty_branches
    assert "Environment" in result.empty_branches
    assert any("bare legs" in w.lower() or "empty branches" in w.lower() for w in result.warnings)
    assert any("AIAG CQI-20" in r for r in result.recommendations)


def test_scorecard_negative_control_duplicate_cause_injection() -> None:
    """Negative Control 3: Injected duplicate cause text across branches forces WARNING verdict."""
    causes_with_dupe = [
        {"category": "Man", "cause": "Operator skipped calibration routine"},
        {"category": "Measurement", "cause": "Operator skipped calibration routine"},  # Duplicate
        {"category": "Machine", "cause": "Gage clamp cracked"},
        {"category": "Method", "cause": "Missing inspection work instruction"},
        {"category": "Material", "cause": "Shaft diameter oversize"},
        {"category": "Environment", "cause": "Gage lab thermal variation"},
    ]

    result = categorize_fishbone(
        data=causes_with_dupe,
        effect_statement="Dimensional defect",
    )

    assert result.valid is True
    assert result.verdict == "WARNING"
    assert len(result.duplicate_causes) == 1
    assert result.duplicate_causes[0]["category"] == "Measurement"
    assert result.duplicate_causes[0]["duplicate_of_category"] == "Man"
    assert any("duplicate cause entries" in w for w in result.warnings)


def test_scorecard_negative_control_single_branch_concentration_bias() -> None:
    """Negative Control 4: Injected operator-bias concentration (>= 75% in Man) forces WARNING verdict.

    Grounding: Internal heuristic preventing single-branch tunnel vision.
    """
    biased_causes = [
        {"category": "Man", "cause": "Operator did not read work instruction"},
        {"category": "Man", "cause": "Operator distraction during assembly"},
        {"category": "Man", "cause": "Operator hurried shift handover"},
        {"category": "Machine", "cause": "Pneumatic crimper low pressure"},
    ]  # 3/4 = 75% in Man

    result = categorize_fishbone(
        data=biased_causes,
        effect_statement="Crimping defect",
        balance_threshold=0.75,
    )

    assert result.valid is True
    assert result.verdict == "WARNING"
    assert any("Branch concentration imbalance: 'Man'" in w for w in result.warnings)
    assert any("tunnel vision" in w for w in result.warnings)
    assert any("Broaden brainstorming" in r for r in result.recommendations)

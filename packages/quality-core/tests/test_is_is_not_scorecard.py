"""
Benchmark scorecards and negative controls for Kepner-Tregoe Is/Is-Not Scoping (quality_core.rca.is_is_not).

Standards & Benchmark references:
1. Sentinel-8D Pneumatic Cylinder Manufacturing Case Study (8D_Report.md).
2. Charles H. Kepner & Benjamin B. Tregoe, The New Rational Manager (1997), Chapters 2 & 3 (Filter Leaking Case, p. 1438–1446).
3. AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section 4 & Figure 24 (Comparative Bounding Case).
4. Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Section D2.

Mandatory negative controls:
- Empty matrix rejection -> REJECT verdict, valid=False.
- Partial dimension bounding -> WARNING verdict with un-scoped dimension guidance.
- Missing distinctions or changes -> WARNING verdict with KT Chapter 2 investigation guidance.
"""

from __future__ import annotations

from quality_core.canvas.rca import SAMPLE_IS_IS_NOT_ROWS
from quality_core.rca.is_is_not import scope_is_is_not

# ---------------------------------------------------------------------------
# 1. Positive Benchmark Scorecards
# ---------------------------------------------------------------------------


def test_scorecard_sentinel_8d_pneumatic_cylinder_benchmark() -> None:
    """Benchmark 1: Sentinel-8D Pneumatic Cylinder Manufacturing Case Study.

    Validates complete 4-dimension KT problem boundary scoping isolating
    saw cut blank weight variation (< 0.540 kg) as the driver for CNC milling
    clamping depth distortion and assembly stroke binding / seal leakage rework.
    """
    result = scope_is_is_not(
        data=SAMPLE_IS_IS_NOT_ROWS,
        problem_statement="Pneumatic cylinder functional defect requiring assembly rework (stroke binding & seal leakage)",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_rows == 4
    assert result.complete_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert result.missing_dimensions == []
    assert len(result.candidate_causes) == 4
    assert all(c["is_paired"] is True for c in result.candidate_causes)
    assert len(result.warnings) == 0

    # Verify cause synthesis for each dimension
    causes_by_dim = {c["dimension"]: c for c in result.candidate_causes}
    assert "Cylinder bottom mounting face non-parallelism" in causes_by_dim["WHAT"]["distinction"]
    assert "Bar stock feed misalignment" in causes_by_dim["WHAT"]["change"]

    assert "Hydraulic vice clamping standard depth" in causes_by_dim["WHERE"]["distinction"]
    assert "Sawing station backstop guide position adjusted" in causes_by_dim["WHERE"]["change"]

    assert "Defect manifests only under pressurized stroke test" in causes_by_dim["WHEN"]["distinction"]
    assert "Production shift handover" in causes_by_dim["WHEN"]["change"]

    assert "1.99x" in causes_by_dim["EXTENT"]["distinction"]
    assert "Sawing cut blank weight variation" in causes_by_dim["EXTENT"]["change"]


def test_scorecard_kepner_tregoe_1997_filter_leaking_case() -> None:
    """Benchmark 2: Kepner & Tregoe (1997) Chapter 3 Filter Leaking Case.

    Isolates oil leakage deviation on Number One Filter compared to Numbers Two-Five,
    identifying the square-cornered gasket from the new supplier as the root cause.
    """
    kt_filter_rows = [
        {
            "dimension": "WHAT",
            "is_data": "Number One Filter leaking oil at casing joint",
            "is_not_data": "Numbers Two, Three, Four, and Five Filters leaking",
            "distinctions": "Square-cornered gasket design installed on Number One Filter",
            "changes": "New supplier for square-cornered gaskets introduced last month",
        },
        {
            "dimension": "WHERE",
            "is_data": "Main compressor station lubrication loop (Unit #1)",
            "is_not_data": "Units #2-#5 or auxiliary return circuits",
            "distinctions": "Unit #1 located adjacent to north wall ventilation duct",
            "changes": "Ventilation duct baffle angle adjusted 2 weeks ago",
        },
        {
            "dimension": "WHEN",
            "is_data": "First noticed Monday morning at 07:30 startup",
            "is_not_data": "Prior continuous operations during Friday afternoon shift",
            "distinctions": "System cold-start at 15 C after 48-hour weekend shutdown",
            "changes": "Startup pressurization ramp-up rate accelerated",
        },
        {
            "dimension": "EXTENT",
            "is_data": "1 of 5 filters leaking, loss rate 12 liters per day",
            "is_not_data": "All 5 filters or minor cosmetic weeping (< 100 mL/day)",
            "distinctions": "Filter #1 received gasket from batch lot #884A",
            "changes": "Batch #884A manufactured with thinner elastomer cross-section",
        },
    ]

    result = scope_is_is_not(
        data=kt_filter_rows,
        problem_statement="Number One Filter leaking oil",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_rows == 4
    assert result.complete_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert result.missing_dimensions == []
    assert len(result.candidate_causes) == 4
    assert all(c["is_paired"] is True for c in result.candidate_causes)
    assert len(result.warnings) == 0

    what_cause = next(c for c in result.candidate_causes if c["dimension"] == "WHAT")
    assert "Square-cornered gasket design installed on Number One Filter" in what_cause["hypothesis"]
    assert "New supplier for square-cornered gaskets" in what_cause["hypothesis"]


def test_scorecard_aiag_cqi20_comparative_bounding_case() -> None:
    """Benchmark 3: AIAG CQI-20 Comparative Bounding Case (2nd Edition, Section 4 & Figure 24).

    Evaluates automotive transmission valve body pressure loss across 4 dimensions.
    """
    cqi20_rows = [
        {
            "dimension": "WHAT",
            "is_data": "Main spool bore pressure leakage exceeding 5.0 bar specification limit",
            "is_not_data": "Secondary solenoid circuit pressure loss or accumulator sealing defect",
            "distinctions": "Bore 3 hard-anodized surface finish roughness Ra > 0.6 um",
            "changes": "Honing tool holder #4 refurbished with new diamond sleeve",
        },
        {
            "dimension": "WHERE",
            "is_data": "Line 2 CNC honing station #4 spindle B",
            "is_not_data": "Line 1 or Line 3 honing stations or spindle A",
            "distinctions": "Spindle B coolant delivery nozzle partially clogged",
            "changes": "Coolant filtration bag replacement interval extended",
        },
        {
            "dimension": "WHEN",
            "is_data": "First production batch after tool changeover on shift 1",
            "is_not_data": "Mid-batch steady state or end-of-life tool cycles",
            "distinctions": "Initial 50 parts machined before thermal expansion stabilization",
            "changes": "Pre-warmup cycle duration reduced from 15 min to 5 min",
        },
        {
            "dimension": "EXTENT",
            "is_data": "18 out of 500 valve bodies (3.6% failure rate), concentrated in cavity #2",
            "is_not_data": "100% defect rate across all 4 casting cavities",
            "distinctions": "Cavity #2 core pin wear allowance tighter than cavities 1, 3, 4",
            "changes": "Core pin replaced with alternate supplier component",
        },
    ]

    result = scope_is_is_not(
        data=cqi20_rows,
        problem_statement="Transmission valve body pressure loss during high-temperature durability cycle",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_rows == 4
    assert result.complete_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert result.missing_dimensions == []
    assert len(result.candidate_causes) == 4
    assert all(c["is_paired"] is True for c in result.candidate_causes)
    assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# 2. Mandatory Negative Controls
# ---------------------------------------------------------------------------


def test_negative_control_empty_matrix_rejection() -> None:
    """Empty matrix is rejected with REJECT verdict and valid=False."""
    result = scope_is_is_not(
        data=[],
        problem_statement="Empty scoping dataset",
    )
    assert result.valid is False
    assert result.verdict == "REJECT"
    assert result.total_rows == 0
    assert result.complete_dimensions == []
    assert result.missing_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert len(result.candidate_causes) == 0
    assert "Is/Is-Not matrix contains no scoping rows." in result.warnings


def test_negative_control_partial_dimension_bounding() -> None:
    """Partial bounding (e.g. only WHAT and WHEN) yields WARNING verdict and flags missing dimensions."""
    partial_rows = [
        {
            "dimension": "WHAT",
            "is_data": "Cylinder stroke binding",
            "is_not_data": "Piston rod surface damage",
            "distinctions": "Bottom mounting face non-parallelism",
            "changes": "Bar stock feed misalignment",
        },
        {
            "dimension": "WHEN",
            "is_data": "During acceptance pressure decay testing",
            "is_not_data": "During receiving inspection",
            "distinctions": "Manifests under pressurized stroke",
            "changes": "Shift handover",
        },
    ]
    result = scope_is_is_not(
        data=partial_rows,
        problem_statement="Cylinder binding defect",
    )
    assert result.valid is True
    assert result.verdict == "WARNING"
    assert result.total_rows == 2
    assert result.complete_dimensions == ["WHAT", "WHEN"]
    assert result.missing_dimensions == ["WHERE", "EXTENT"]
    assert any("missing dimensions WHERE, EXTENT" in w for w in result.warnings)
    assert any("Scope the unexamined dimensions (WHERE, EXTENT)" in r for r in result.recommendations)


def test_negative_control_missing_distinction_or_change() -> None:
    """Matrix with complete 4 dimensions but missing distinctions or changes yields WARNING verdict."""
    rows_with_gaps = [
        {
            "dimension": "WHAT",
            "is_data": "Defect A",
            "is_not_data": "Defect B",
            "distinctions": "Distinct feature",
            "changes": None,  # Missing change
        },
        {
            "dimension": "WHERE",
            "is_data": "Station 1",
            "is_not_data": "Station 2",
            "distinctions": None,  # Missing distinction
            "changes": "New tool installed",
        },
        {
            "dimension": "WHEN",
            "is_data": "Shift 1",
            "is_not_data": "Shift 2",
            "distinctions": None,  # Missing both
            "changes": None,
        },
        {
            "dimension": "EXTENT",
            "is_data": "5%",
            "is_not_data": "0%",
            "distinctions": "Concentrated in batch 3",
            "changes": "Raw material supplier changed",  # Complete
        },
    ]
    result = scope_is_is_not(
        data=rows_with_gaps,
        problem_statement="Problem with gap observations",
    )
    assert result.valid is True
    assert result.verdict == "WARNING"
    assert result.total_rows == 4
    assert result.complete_dimensions == ["WHAT", "WHERE", "WHEN", "EXTENT"]
    assert result.missing_dimensions == []

    # 3 warnings for the 3 incomplete rows
    assert len(result.warnings) == 3
    assert any("Dimension 'WHAT' has distinctions recorded ('Distinct feature') but is missing associated changes" in w for w in result.warnings)
    assert any("Dimension 'WHERE' has changes recorded ('New tool installed') but is missing distinctions" in w for w in result.warnings)
    assert any("Dimension 'WHEN' has IS and IS NOT data but is missing both distinctions and changes" in w for w in result.warnings)

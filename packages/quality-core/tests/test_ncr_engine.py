"""
test_ncr_engine.py
Comprehensive unit, boundary, and negative control tests for deterministic Nonconformance Reporting (NCR)
defect-statement and disposition recommendation engines in quality_core.ncr.nonconformance.

Tests:
1. write_nonconformance:
   - Full parameter specification and statement compilation.
   - Raw defect note parsing and heuristic extraction (quantity, part/lot, specs, measurements, detection points).
   - Operator blame phrase detection and statement sanitation.
   - Premature root-cause speculation detection and RCA guidance.
   - Missing field tracking and validation flag logic.
   - Type errors and value errors.
   - NonconformanceWriteResult to_dict serialization.
2. recommend_disposition:
   - ReturnToVendor disposition for external supplier origin.
   - Regrade disposition for secondary specification conformance.
   - UseAsIs disposition for customer concession eligibility.
   - Scrap disposition for non-reworkable, safety-critical, or uneconomical rework.
   - Rework disposition for technically feasible rework with FMEA risk analysis flag.
   - Mandatory load-bearing INSUFFICIENT_DATA negative control on ambiguous/omitted inputs.
   - Type errors, negative cost/value errors, and edge case combinations.
   - DispositionRecommendation to_dict serialization.
"""

from __future__ import annotations

import pytest
from quality_core.ncr.nonconformance import (
    DispositionRecommendation,
    NonconformanceWriteResult,
    recommend_disposition,
    write_nonconformance,
)

# ==============================================================================
# 1. write_nonconformance Tests
# ==============================================================================


def test_write_nonconformance_fully_specified() -> None:
    """write_nonconformance with all explicit parameters produces valid, objective statement."""
    res = write_nonconformance(
        what_deviated="Cast porosity on brake caliper mounting flange",
        requirement_violated="DWG-BRK-004 Rev D: Max surface pore diameter <= 0.50 mm",
        measured_evidence="Measured surface pore diameter 0.85 mm with clustering",
        quantity_affected=45,
        detection_point="Receiving Inspection / CMM Cell 1",
        part_lot_id="LOT-BRK-8821",
        unit_of_measure="pcs",
    )
    assert isinstance(res, NonconformanceWriteResult)
    assert res.valid is True
    assert "LOT-BRK-8821" in res.statement
    assert "Cast porosity" in res.statement
    assert "DWG-BRK-004" in res.statement
    assert "45 pcs" in res.statement
    assert "Receiving Inspection" in res.statement
    assert res.quantity_affected == 45
    assert res.part_lot_id == "LOT-BRK-8821"
    assert len(res.fields_missing) == 0
    assert len(res.fields_populated) == 6
    assert len(res.blame_phrases_detected) == 0
    assert len(res.speculation_detected) == 0
    assert res.standards_basis == "ISO 9001:2015 §8.7 / IATF 16949:2016 §8.7"


def test_write_nonconformance_raw_note_parsing() -> None:
    """write_nonconformance extracts fields from unstructured raw defect text."""
    raw_note = (
        "During receiving inspection at station 1, found lot: LOT-9912 with 50 pcs. "
        "Spec: 12.00 +/- 0.05 mm. Measured: 12.15 mm oversized."
    )
    res = write_nonconformance(raw_defect_note=raw_note)
    assert res.valid is True
    assert res.quantity_affected == 50
    assert res.part_lot_id == "LOT-9912"
    assert res.requirement_violated is not None and "12.00" in res.requirement_violated
    assert res.measured_evidence is not None and "12.15" in res.measured_evidence
    assert res.detection_point is not None and "receiving inspection" in res.detection_point.lower()
    assert res.to_dict()["valid"] is True


def test_write_nonconformance_blame_detection_and_sanitization() -> None:
    """write_nonconformance detects human blame and cleanses statement."""
    raw_note = (
        "Operator forgot to torque bolts at assembly line 2, worker error resulted in loose fasteners. "
        "Drawing spec: 45 Nm. Measured: 20 Nm on 15 units of Part: BKT-200."
    )
    res = write_nonconformance(raw_defect_note=raw_note)
    assert len(res.blame_phrases_detected) > 0
    assert any("operator forgot" in b or "operator" in b for b in res.blame_phrases_detected)
    assert any("worker error" in b or "worker" in b for b in res.blame_phrases_detected)
    assert len(res.warnings) > 0
    assert any("blame" in w.lower() for w in res.warnings)
    assert any("5-why" in r.lower() or "rca" in r.lower() for r in res.recommendations)
    # Statement should have blame phrases removed
    assert "operator forgot" not in res.statement.lower()
    assert "worker error" not in res.statement.lower()


def test_write_nonconformance_speculation_detection_and_sanitization() -> None:
    """write_nonconformance detects premature root cause speculation and issues RCA guidance."""
    raw_note = (
        "Shafts turned out of round at CNC cell 4. Root cause was probably because the supplier sent bad material. "
        "Spec: Roundness <= 0.01 mm. Measured: 0.04 mm on 25 parts of Lot: SFT-77."
    )
    res = write_nonconformance(raw_defect_note=raw_note)
    assert len(res.speculation_detected) > 0
    assert any("root cause was" in s or "because the supplier" in s or "probably because" in s for s in res.speculation_detected)
    assert any("speculation" in w.lower() for w in res.warnings)
    assert any("rca" in r.lower() for r in res.recommendations)
    assert "root cause was" not in res.statement.lower()


def test_write_nonconformance_missing_fields_flags_invalid() -> None:
    """write_nonconformance with incomplete fields sets valid=False and populates fields_missing."""
    res = write_nonconformance(what_deviated="Surface scratch on painted panel")
    assert res.valid is False
    assert "requirement_violated" in res.fields_missing
    assert "measured_evidence" in res.fields_missing
    assert "quantity_affected" in res.fields_missing
    assert "detection_point" in res.fields_missing
    assert any("missing mandatory fields" in w.lower() for w in res.warnings)


def test_write_nonconformance_quantity_formats() -> None:
    """write_nonconformance handles integer and string quantities."""
    res1 = write_nonconformance(
        what_deviated="Leakage",
        requirement_violated="0 sccm",
        measured_evidence="5 sccm",
        quantity_affected=100,
        detection_point="Leak Test",
    )
    assert res1.quantity_affected == 100

    res2 = write_nonconformance(
        what_deviated="Leakage",
        requirement_violated="0 sccm",
        measured_evidence="5 sccm",
        quantity_affected="75 units",
        detection_point="Leak Test",
    )
    assert res2.quantity_affected == 75


def test_write_nonconformance_type_and_value_errors() -> None:
    """write_nonconformance raises TypeError and ValueError on invalid arguments."""
    with pytest.raises(TypeError, match="raw_defect_note must be a string"):
        write_nonconformance(raw_defect_note=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="what_deviated must be a string"):
        write_nonconformance(what_deviated=True)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="quantity_affected cannot be a boolean"):
        write_nonconformance(quantity_affected=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="quantity_affected must be >= 1"):
        write_nonconformance(quantity_affected=0)

    with pytest.raises(ValueError, match="quantity_affected must be >= 1"):
        write_nonconformance(quantity_affected=-5)

    with pytest.raises(ValueError, match="Could not parse integer quantity_affected"):
        write_nonconformance(quantity_affected="no numbers here")

    with pytest.raises(TypeError, match="quantity_affected must be an integer, string, or None"):
        write_nonconformance(quantity_affected=[10])  # type: ignore[arg-type]


def test_write_nonconformance_to_dict_keys() -> None:
    """NonconformanceWriteResult.to_dict() contains all expected keys."""
    res = write_nonconformance(
        what_deviated="Defect A",
        requirement_violated="Spec B",
        measured_evidence="Meas C",
        quantity_affected=10,
        detection_point="Station D",
    )
    d = res.to_dict()
    assert isinstance(d, dict)
    expected_keys = {
        "valid",
        "statement",
        "what_deviated",
        "requirement_violated",
        "measured_evidence",
        "quantity_affected",
        "detection_point",
        "part_lot_id",
        "unit_of_measure",
        "blame_phrases_detected",
        "speculation_detected",
        "fields_populated",
        "fields_missing",
        "warnings",
        "recommendations",
        "standards_basis",
    }
    assert set(d.keys()) == expected_keys


# ==============================================================================
# 2. recommend_disposition Tests
# ==============================================================================


def test_recommend_disposition_return_to_vendor() -> None:
    """recommend_disposition returns ReturnToVendor for supplier defect origin."""
    res = recommend_disposition(
        defect_origin="Supplier",
        defect_description="Incoming raw bar stock surface cracks",
    )
    assert isinstance(res, DispositionRecommendation)
    assert res.disposition == "ReturnToVendor"
    assert res.verdict == "VALID"
    assert "ISO 9001:2015 Clause 8.7.1(b)" in res.rationale
    assert "Supplier Quality Assurance" in res.approval_authority
    assert res.mrb_review_required is False
    assert res.customer_authorization_required is False
    assert res.fmea_risk_analysis_required is False
    assert any("SCAR" in r for r in res.recommendations)


def test_recommend_disposition_regrade() -> None:
    """recommend_disposition returns Regrade when meeting secondary spec without safety issue."""
    res = recommend_disposition(
        is_reworkable=False,
        defect_origin="Internal",
        meets_secondary_spec=True,
        safety_critical=False,
    )
    assert res.disposition == "Regrade"
    assert res.verdict == "VALID"
    assert "IATF 16949:2016 Clause 8.7.1.7" in res.rationale
    assert res.mrb_review_required is True
    assert res.customer_authorization_required is True
    assert res.fmea_risk_analysis_required is False


def test_recommend_disposition_use_as_is() -> None:
    """recommend_disposition returns UseAsIs when customer concession eligible."""
    res = recommend_disposition(
        is_reworkable=False,
        defect_origin="Internal",
        customer_concession_eligible=True,
        safety_critical=False,
    )
    assert res.disposition == "UseAsIs"
    assert res.verdict == "VALID"
    assert "ISO 9001:2015 Clause 8.7.1(d)" in res.rationale
    assert "IATF 16949:2016 Clause 8.7.1.1" in res.rationale
    assert res.mrb_review_required is True
    assert res.customer_authorization_required is True
    assert res.fmea_risk_analysis_required is False


def test_recommend_disposition_scrap_non_reworkable() -> None:
    """recommend_disposition returns Scrap when part is not reworkable."""
    res = recommend_disposition(
        is_reworkable=False,
        defect_origin="Internal",
        meets_secondary_spec=False,
        customer_concession_eligible=False,
    )
    assert res.disposition == "Scrap"
    assert res.verdict == "VALID"
    assert "rendered unusable" in res.rationale
    assert "Quality Manager / Scrap Authority" in res.approval_authority
    assert any("deface" in r or "unusable" in r for r in res.recommendations)


def test_recommend_disposition_scrap_uneconomical_rework() -> None:
    """recommend_disposition returns Scrap when rework cost exceeds part value."""
    res = recommend_disposition(
        is_reworkable=True,
        defect_origin="Internal",
        rework_cost=150.0,
        part_value=100.0,
    )
    assert res.disposition == "Scrap"
    assert res.verdict == "VALID"
    assert any("rework is uneconomical" in w.lower() for w in res.warnings)


def test_recommend_disposition_safety_critical_scrap() -> None:
    """recommend_disposition routes safety critical non-reworkable defects to Scrap."""
    res = recommend_disposition(
        safety_critical=True,
        is_reworkable=False,
        defect_origin="Internal",
    )
    assert res.disposition == "Scrap"
    assert res.verdict == "VALID"
    assert res.mrb_review_required is True
    assert any("safety" in w.lower() for w in res.warnings)


def test_recommend_disposition_rework_success() -> None:
    """recommend_disposition returns Rework when technically reworkable and economical."""
    res = recommend_disposition(
        is_reworkable=True,
        defect_origin="Internal",
        rework_cost=10.0,
        part_value=85.0,
    )
    assert res.disposition == "Rework"
    assert res.verdict == "VALID"
    assert "ISO 9001:2015 Clause 8.7.1(a)" in res.rationale
    assert "IATF 16949:2016 Clause 8.7.1.4" in res.rationale
    assert res.fmea_risk_analysis_required is True
    assert any("FMEA risk analysis" in r for r in res.recommendations)


# ==============================================================================
# 3. Mandatory Load-Bearing INSUFFICIENT_DATA Negative Control Tests
# ==============================================================================


def test_negative_control_insufficient_data_refuses_silent_disposition() -> None:
    """recommend_disposition refuses silent guessing when routing parameters are missing."""
    res = recommend_disposition()
    assert res.disposition is None
    assert res.verdict == "INSUFFICIENT_DATA"
    assert res.mrb_review_required is True
    assert "is_reworkable" in res.missing_evidence
    assert "defect_origin" in res.missing_evidence
    assert "meets_secondary_spec" in res.missing_evidence
    assert "customer_concession_eligible" in res.missing_evidence
    assert "Material Review Board" in res.approval_authority
    assert any("missing critical defect characteristics" in w.lower() for w in res.warnings)
    assert any("convene material review board" in r.lower() for r in res.recommendations)


def test_recommend_disposition_type_and_value_errors() -> None:
    """recommend_disposition raises TypeError and ValueError on invalid inputs."""
    with pytest.raises(TypeError, match="is_reworkable must be a bool"):
        recommend_disposition(is_reworkable="yes")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="meets_secondary_spec must be a bool"):
        recommend_disposition(meets_secondary_spec="true")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="customer_concession_eligible must be a bool"):
        recommend_disposition(customer_concession_eligible=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="safety_critical must be a bool"):
        recommend_disposition(safety_critical="critical")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="rework_cost must be a number"):
        recommend_disposition(rework_cost=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="rework_cost cannot be negative"):
        recommend_disposition(rework_cost=-10.0)

    with pytest.raises(TypeError, match="part_value must be a number"):
        recommend_disposition(part_value="100")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="part_value cannot be negative"):
        recommend_disposition(part_value=-50.0)

    with pytest.raises(TypeError, match="defect_origin must be a string"):
        recommend_disposition(defect_origin=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="severity must be a string"):
        recommend_disposition(severity=456)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="defect_description must be a string"):
        recommend_disposition(defect_description=789)  # type: ignore[arg-type]


def test_recommend_disposition_to_dict_keys() -> None:
    """DispositionRecommendation.to_dict() contains all expected keys."""
    res = recommend_disposition(is_reworkable=True, defect_origin="Internal")
    d = res.to_dict()
    assert isinstance(d, dict)
    expected_keys = {
        "disposition",
        "verdict",
        "rationale",
        "approval_authority",
        "mrb_review_required",
        "customer_authorization_required",
        "fmea_risk_analysis_required",
        "missing_evidence",
        "warnings",
        "recommendations",
        "standards_basis",
    }
    assert set(d.keys()) == expected_keys


def test_write_nonconformance_token_blame_pair() -> None:
    """write_nonconformance detects tokenized noun + verb blame pairs."""
    res = write_nonconformance(raw_defect_note="Technician ignored the calibration cycle at station 4.")
    assert len(res.blame_phrases_detected) > 0
    assert any("technician" in b for b in res.blame_phrases_detected)


def test_write_nonconformance_zero_quantity_string_error() -> None:
    """write_nonconformance raises ValueError when parsed quantity in string is 0."""
    with pytest.raises(ValueError, match="quantity_affected must be >= 1"):
        write_nonconformance(quantity_affected="0 pcs")


def test_write_nonconformance_raw_note_heuristics_combinations() -> None:
    """write_nonconformance exercises all raw text regex extraction branches."""
    # 1. Raw note with no part, no spec, no meas, no det, no qty
    res1 = write_nonconformance(raw_defect_note="Something is broken here")
    assert res1.valid is False

    # 2. Raw note with part lot but no qty
    res2 = write_nonconformance(raw_defect_note="Found defect on Batch: LOT-7788 at line 3")
    assert res2.part_lot_id == "LOT-7788"

    # 3. Explicit what, req, meas overrides raw note
    res3 = write_nonconformance(
        raw_defect_note="Ignored text",
        what_deviated="Explicit flaw",
        requirement_violated="Explicit req",
        measured_evidence="Explicit meas",
        quantity_affected=10,
        detection_point="Explicit point",
        part_lot_id="LOT-EXPLICIT",
    )
    assert res3.what_deviated == "Explicit flaw"
    assert res3.part_lot_id == "LOT-EXPLICIT"


def test_recommend_disposition_supplier_origin_reworkable_warning() -> None:
    """recommend_disposition adds warning when supplier defect is marked reworkable."""
    res = recommend_disposition(defect_origin="Supplier", is_reworkable=True)
    assert res.disposition == "ReturnToVendor"
    assert any("discouraged without vendor authorization" in w for w in res.warnings)


def test_recommend_disposition_safety_critical_reworkable() -> None:
    """recommend_disposition allows rework when safety critical defect is marked reworkable."""
    res = recommend_disposition(
        safety_critical=True,
        is_reworkable=True,
        defect_origin="Internal",
    )
    assert res.disposition == "Rework"
    assert res.verdict == "VALID"
    assert any("Safety/regulatory" in w for w in res.warnings)


def test_recommend_disposition_internal_origin_insufficient_data() -> None:
    """recommend_disposition returns INSUFFICIENT_DATA fallback when internal origin has no disposition criteria."""
    res = recommend_disposition(defect_origin="Internal")
    assert res.disposition is None
    assert res.verdict == "INSUFFICIENT_DATA"
    assert "is_reworkable" in res.missing_evidence


def test_write_nonconformance_pure_blame_raw_note() -> None:
    """write_nonconformance with raw note consisting solely of blame leaves extracted_what as None."""
    res = write_nonconformance(raw_defect_note="Operator error. Worker error.")
    assert res.what_deviated is None
    assert res.valid is False


def test_write_nonconformance_without_what_deviated() -> None:
    """write_nonconformance with no what_deviated and no raw note."""
    res = write_nonconformance(
        requirement_violated="Spec-100",
        measured_evidence="10.5 mm",
        quantity_affected=10,
        detection_point="CMM",
    )
    assert res.what_deviated is None
    assert res.valid is False
    assert "what_deviated" in res.fields_missing


def test_recommend_disposition_reworkable_without_origin() -> None:
    """recommend_disposition with is_reworkable=True but defect_origin=None."""
    res = recommend_disposition(is_reworkable=True)
    assert res.disposition == "Rework"
    assert "defect_origin" in res.missing_evidence


def test_recommend_disposition_scrap_without_origin() -> None:
    """recommend_disposition with is_reworkable=False but defect_origin=None."""
    res = recommend_disposition(is_reworkable=False)
    assert res.disposition == "Scrap"
    assert "defect_origin" in res.missing_evidence


def test_recommend_disposition_supplier_safety_critical_non_reworkable_scraps() -> None:
    """Supplier origin + safety critical + non-reworkable (is_reworkable=False) routes to Scrap with MRB, Safety Officer, defacing, and SCAR."""
    res = recommend_disposition(
        defect_origin="Supplier",
        safety_critical=True,
        is_reworkable=False,
    )
    assert isinstance(res, DispositionRecommendation)
    assert res.disposition == "Scrap"
    assert res.verdict == "VALID"
    assert res.mrb_review_required is True
    assert res.customer_authorization_required is False
    assert res.fmea_risk_analysis_required is False
    assert res.approval_authority == "Quality Manager / Scrap Authority & Safety Officer"
    assert "Safety/regulatory critical characteristic nonconformance." in res.warnings
    assert "Mandatory defacing and scrap witnessing required for safety-critical nonconformance." in res.recommendations
    assert "Issue Supplier Corrective Action Request (SCAR) and debit memo to vendor." in res.recommendations
    assert "IATF 16949:2016 Clause 8.7.1.7" in res.rationale
    assert res.standards_basis == "ISO 9001:2015 §8.7 / IATF 16949:2016 §8.7"


def test_recommend_disposition_supplier_safety_critical_unknown_reworkability_scraps() -> None:
    """Supplier origin + safety critical + unknown reworkability (is_reworkable=None) routes to Scrap and preserves SCAR + defacing."""
    res = recommend_disposition(
        defect_origin="Vendor",
        safety_critical=True,
        is_reworkable=None,
    )
    assert isinstance(res, DispositionRecommendation)
    assert res.disposition == "Scrap"
    assert res.verdict == "VALID"
    assert res.mrb_review_required is True
    assert res.approval_authority == "Quality Manager / Scrap Authority & Safety Officer"
    assert "Mandatory defacing and scrap witnessing required for safety-critical nonconformance." in res.recommendations
    assert "Issue Supplier Corrective Action Request (SCAR) and debit memo to vendor." in res.recommendations
    assert "Safety/regulatory critical characteristic nonconformance." in res.warnings
    assert "is_reworkable" in res.missing_evidence


def test_recommend_disposition_supplier_safety_critical_reworkable_returns_to_vendor() -> None:
    """Supplier origin + safety critical + reworkable (is_reworkable=True) routes to ReturnToVendor with warnings and SCAR."""
    res = recommend_disposition(
        defect_origin="Supplier",
        safety_critical=True,
        is_reworkable=True,
    )
    assert isinstance(res, DispositionRecommendation)
    assert res.disposition == "ReturnToVendor"
    assert res.verdict == "VALID"
    assert res.mrb_review_required is False
    assert res.customer_authorization_required is False
    assert res.fmea_risk_analysis_required is False
    assert res.approval_authority == "Supplier Quality Assurance (SQA) / Purchasing"
    assert "Safety/regulatory critical characteristic nonconformance." in res.warnings
    assert "Defect originated externally from supplier; internal rework is discouraged without vendor authorization." in res.warnings
    assert "Issue Supplier Corrective Action Request (SCAR) and debit memo to vendor." in res.recommendations


def test_recommend_disposition_safety_critical_blocks_regrade_and_concession() -> None:
    """Safety-critical defects cannot be regraded or accepted under concession."""
    # Secondary spec non-reworkable -> Scrap with Safety Officer authority
    res_regrade_non_rework = recommend_disposition(
        safety_critical=True,
        meets_secondary_spec=True,
        is_reworkable=False,
        defect_origin="Internal",
    )
    assert res_regrade_non_rework.disposition == "Scrap"
    assert res_regrade_non_rework.mrb_review_required is True
    assert res_regrade_non_rework.approval_authority == "Quality Manager / Scrap Authority & Safety Officer"
    assert "Mandatory defacing and scrap witnessing required for safety-critical nonconformance." in res_regrade_non_rework.recommendations

    # Secondary spec reworkable -> Rework with FMEA risk analysis
    res_regrade_rework = recommend_disposition(
        safety_critical=True,
        meets_secondary_spec=True,
        is_reworkable=True,
        defect_origin="Internal",
    )
    assert res_regrade_rework.disposition == "Rework"
    assert res_regrade_rework.fmea_risk_analysis_required is True
    assert "Safety/regulatory critical characteristic nonconformance." in res_regrade_rework.warnings

    # Concession non-reworkable -> Scrap with Safety Officer authority
    res_concession_non_rework = recommend_disposition(
        safety_critical=True,
        customer_concession_eligible=True,
        is_reworkable=False,
        defect_origin="Internal",
    )
    assert res_concession_non_rework.disposition == "Scrap"
    assert res_concession_non_rework.mrb_review_required is True
    assert res_concession_non_rework.approval_authority == "Quality Manager / Scrap Authority & Safety Officer"

    # Concession reworkable -> Rework with FMEA risk analysis
    res_concession_rework = recommend_disposition(
        safety_critical=True,
        customer_concession_eligible=True,
        is_reworkable=True,
        defect_origin="Internal",
    )
    assert res_concession_rework.disposition == "Rework"
    assert res_concession_rework.fmea_risk_analysis_required is True
    assert "Safety/regulatory critical characteristic nonconformance." in res_concession_rework.warnings


@pytest.mark.parametrize(
    (
        "defect_origin",
        "safety_critical",
        "is_reworkable",
        "meets_secondary_spec",
        "customer_concession_eligible",
        "expected_disposition",
        "expected_mrb",
        "expected_fmea",
    ),
    [
        # 1. Supplier origin
        ("Supplier", True, False, False, False, "Scrap", True, False),
        ("Supplier", True, None, False, False, "Scrap", True, False),
        ("Supplier", True, True, False, False, "ReturnToVendor", False, False),
        ("Supplier", False, False, False, False, "ReturnToVendor", False, False),
        ("Supplier", False, True, False, False, "ReturnToVendor", False, False),
        ("Supplier", None, False, False, False, "ReturnToVendor", False, False),
        # 2. Internal origin non-safety
        ("Internal", False, False, False, False, "Scrap", False, False),
        ("Internal", False, True, False, False, "Rework", False, True),
        ("Internal", None, False, False, False, "Scrap", False, False),
        ("Internal", None, True, False, False, "Rework", False, True),
        # 3. Internal origin safety-critical
        ("Internal", True, False, False, False, "Scrap", True, False),
        ("Internal", True, None, False, False, "Scrap", True, False),
        ("Internal", True, True, False, False, "Rework", False, True),
        # 4. Secondary spec (Regrade candidate)
        ("Internal", False, False, True, False, "Regrade", True, False),
        ("Internal", None, False, True, False, "Regrade", True, False),
        ("Internal", True, False, True, False, "Scrap", True, False),
        ("Internal", True, True, True, False, "Rework", False, True),
        # 5. Customer concession (UseAsIs candidate)
        ("Internal", False, False, False, True, "UseAsIs", True, False),
        ("Internal", None, False, False, True, "UseAsIs", True, False),
        ("Internal", True, False, False, True, "Scrap", True, False),
        ("Internal", True, True, False, True, "Rework", False, True),
    ],
)
def test_recommend_disposition_safety_critical_matrix(
    defect_origin: str | None,
    safety_critical: bool | None,
    is_reworkable: bool | None,
    meets_secondary_spec: bool | None,
    customer_concession_eligible: bool | None,
    expected_disposition: str,
    expected_mrb: bool,
    expected_fmea: bool,
) -> None:
    """Parametric verification of the 5-disposition matrix under safety_critical vs non-safety paths."""
    res = recommend_disposition(
        defect_origin=defect_origin,
        safety_critical=safety_critical,
        is_reworkable=is_reworkable,
        meets_secondary_spec=meets_secondary_spec,
        customer_concession_eligible=customer_concession_eligible,
    )
    assert res.disposition == expected_disposition
    assert res.verdict == "VALID"
    assert res.mrb_review_required is expected_mrb
    assert res.fmea_risk_analysis_required is expected_fmea




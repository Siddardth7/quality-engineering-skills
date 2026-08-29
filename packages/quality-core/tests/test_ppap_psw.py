"""
test_ppap_psw.py
Unit tests for quality_core.ppap.psw (Milestone 8, Epic 6 / Issue #104).

Verifies 100% line & branch coverage on the Part Submission Warrant (PSW) validator:
- Canonical constants (PSW_FIELD_NAMES, BLANKET_STATEMENT_PATTERNS, literals)
- find_blanket_statements heuristic across all patterns, case variants, word boundaries, and edge cases
- PartSubmissionWarrant Pydantic v2 domain model with alias synchronization, normalizers, and to_dict
- PSWFieldStatus and PSWValidationResult dataclasses, .get_field(), .is_valid(), and .to_dict()
- validate_psw across all 27 Appendix-A fields with valid, missing, invalid, not_applicable, and indeterminate branches
- Conditional branches: Checking Aid (Fields 9 & 10), Reason "Other" (Field 18), Conformance "No" (Field 21)
- Numeric validation: Part Weight (Field 8), Production Rate (Field 23), Duration (Field 24)
- Prohibited blanket statement detection in Field 20 (Results) and Field 25 (Comments)
- 🔒 Mandatory Customer Authority Invariant: Field 27 FOR CUSTOMER USE ONLY, no disposition status emissions
- Cross-consistency validation against PPAPPackage submission metadata
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Any

import pytest
from quality_core.ppap.psw import (
    BLANKET_STATEMENT_PATTERNS,
    PSW_FIELD_NAMES,
    PartSubmissionWarrant,
    PSWFieldStatus,
    PSWValidationResult,
    find_blanket_statements,
    validate_psw,
)
from quality_core.ppap.schema import (
    REASON_FOR_SUBMISSION_VALUES,
    SUBMISSION_LEVELS,
    PPAPPackage,
)

# ==============================================================================
# Helper Fixtures: Canonical Valid Warrant & Package
# ==============================================================================

def make_valid_warrant_dict() -> dict[str, Any]:
    """Return a dictionary containing fully populated valid fields for all 27 PSW fields."""
    return {
        "part_name": "Bracket Assembly Front",
        "customer_part_number": "CPN-12345-A",
        "part_drawing_number": "DWG-98765",
        "engineering_change_level": "Rev B",
        "engineering_change_date": "2026-03-15",
        "additional_engineering_changes": "None",
        "purchase_order_number": "PO-998877",
        "part_weight_kg": 2.450,
        "checking_aid_number": "CHK-AID-01",
        "checking_aid_change_level_date": "Rev A 2026-01-10",
        "organization_name": "Acme Automotive Stamping",
        "organization_code": "ORG-8821",
        "organization_address": "123 Industrial Parkway, Detroit, MI 48201",
        "customer_name": "Global Motors Corp",
        "customer_division": "Powertrain Division",
        "customer_contact": "Jane Doe, Lead Buyer",
        "application": "2027 Electric Crossover EV-Platform",
        "materials_reporting": "IMDS ID #123456789",
        "polymeric_parts_marking": "ISO 11469 / ISO 1043",
        "reason_for_submission": "Initial Submission",
        "submission_level": 3,
        "submission_results": "All dimensional, material, and functional tests meet engineering requirements.",
        "results_dimensional": True,
        "results_material_functional": True,
        "results_appearance": True,
        "results_process_capability": True,
        "declaration_of_conformance": True,
        "customer_tool_tagging": "Tagged Tool #T-9002 per GM 18265",
        "production_rate": 120.0,
        "production_duration_hours": 8.0,
        "explanation_comments": "Regular pilot production run; 300 consecutive parts sampled.",
        "authorized_signature": True,
        "authorized_signature_name": "John Smith, Quality Director",
        "authorized_signature_title": "Director of Quality Assurance",
        "authorized_signature_date": "2026-04-01",
        "authorized_signature_phone": "+1-313-555-0199",
        "authorized_signature_email": "jsmith@acmeauto.com",
    }


def make_valid_package() -> PPAPPackage:
    """Return a matching PPAPPackage for cross-consistency testing."""
    return PPAPPackage(
        part_name="Bracket Assembly Front",
        part_number="CPN-12345-A",
        supplier_name="Acme Automotive Stamping",
        customer_name="Global Motors Corp",
        submission_level=3,
        reason_for_submission="Initial Submission",
        has_checking_aid=True,
    )


# ==============================================================================
# 1. Canonical Constants & Definitions
# ==============================================================================

def test_psw_field_names_count_and_keys() -> None:
    """Verify all 27 Appendix-A fields are defined in PSW_FIELD_NAMES."""
    assert len(PSW_FIELD_NAMES) == 27
    for i in range(1, 28):
        assert i in PSW_FIELD_NAMES
        assert isinstance(PSW_FIELD_NAMES[i], str)
        assert len(PSW_FIELD_NAMES[i]) > 0

    assert PSW_FIELD_NAMES[1] == "Part Name"
    assert PSW_FIELD_NAMES[8] == "Part Weight (kg)"
    assert PSW_FIELD_NAMES[18] == "Reason for Submission"
    assert PSW_FIELD_NAMES[19] == "Submission Level"
    assert PSW_FIELD_NAMES[21] == "Declaration of Conformance"
    assert PSW_FIELD_NAMES[27] == "Customer Disposition (FOR CUSTOMER USE ONLY)"


def test_blanket_statement_patterns() -> None:
    """Verify BLANKET_STATEMENT_PATTERNS contains prohibited phrases."""
    assert len(BLANKET_STATEMENT_PATTERNS) >= 10
    expected_patterns = {
        "meets all specs",
        "meets all specifications",
        "all dimensions conform",
        "all dimensions conforming",
        "all specs met",
        "conforming to drawing",
        "all parts conforming",
        "100% conforming",
        "fully conforming",
        "all requirements met",
        "meets specifications",
        "conforming",
    }
    for p in expected_patterns:
        assert p in BLANKET_STATEMENT_PATTERNS


# ==============================================================================
# 2. Blanket Statement Detection Heuristics (find_blanket_statements)
# ==============================================================================

def test_find_blanket_statements_empty_and_non_string() -> None:
    """Verify helper gracefully handles empty or non-string inputs."""
    assert find_blanket_statements(None) == []
    assert find_blanket_statements("") == []
    assert find_blanket_statements("   ") == []
    assert find_blanket_statements(123) == []  # type: ignore[arg-type]
    assert find_blanket_statements(["list"]) == []  # type: ignore[arg-type]


@pytest.mark.parametrize("pattern", BLANKET_STATEMENT_PATTERNS)
def test_find_blanket_statements_each_pattern(pattern: str) -> None:
    """Verify every prohibited phrase in BLANKET_STATEMENT_PATTERNS is detected."""
    # Exact match
    res1 = find_blanket_statements(pattern)
    assert pattern in res1

    # Mixed uppercase and extra spacing
    mixed = f"  The part  {pattern.upper()}  without test data. "
    res2 = find_blanket_statements(mixed)
    assert pattern in res2


def test_find_blanket_statements_clean_text_no_match() -> None:
    """Verify clean descriptions with actual test details do not trigger false positives."""
    clean_text = "All 32 characteristics measured on CMM #4. Cp=1.82, Cpk=1.67 across 300 parts."
    assert find_blanket_statements(clean_text) == []


def test_find_blanket_statements_word_boundaries() -> None:
    """Verify substring words do not trigger false positive word boundary matches."""
    # 'disconforming' or 'nonconforming' should not match bare 'conforming' if not isolated
    text = "Material was nonconforming before rework."
    # 'nonconforming' has 'non' prefix, should not match 'conforming'
    found = find_blanket_statements(text)
    assert "conforming" not in found


def test_find_blanket_statements_multiple_matches() -> None:
    """Verify multiple blanket statements in one text are all returned."""
    text = "The bracket meets all specs and is 100% conforming to drawing."
    found = find_blanket_statements(text)
    assert "meets all specs" in found
    assert "100% conforming" in found
    assert "conforming to drawing" in found


# ==============================================================================
# 3. PartSubmissionWarrant Pydantic Model & Alias Ingestion
# ==============================================================================

def test_part_submission_warrant_default_init() -> None:
    """Verify default initialization sets fields to None and allows extra attributes."""
    psw = PartSubmissionWarrant()
    assert psw.part_name is None
    assert psw.customer_part_number is None
    assert psw.submission_level is None
    assert psw.declaration_of_conformance is None

    # Serialization
    d = psw.to_dict()
    assert isinstance(d, dict)
    assert "part_name" in d


def test_part_submission_warrant_alias_synchronization() -> None:
    """Verify flexible ingestion aliases map to canonical field names."""
    raw = {
        "part_number": "CPN-999",
        "drawing_number": "DWG-888",
        "po_number": "PO-777",
        "weight": 1.5,
        "supplier_name": "Supplier ABC",
        "supplier_code": "SUP-10",
        "manufacturing_address": "456 Factory Rd",
        "customer": "Customer XYZ",
        "buyer": "Buyer Bob",
        "imds_reported": "IMDS-9999",
        "polymeric_marked": "ISO 11469",
        "tooling_tagged": "Tag #55",
        "production_rate_pieces": 250,
        "run_duration_hours": 12.5,
        "comments": "Special test run",
        "signature": "Alice Johnson",
        "signee_name": "Alice Johnson",
    }
    warrant = PartSubmissionWarrant(**raw)
    assert warrant.customer_part_number == "CPN-999"
    assert warrant.part_drawing_number == "DWG-888"
    assert warrant.purchase_order_number == "PO-777"
    assert warrant.part_weight_kg == 1.5
    assert warrant.organization_name == "Supplier ABC"
    assert warrant.organization_code == "SUP-10"
    assert warrant.organization_address == "456 Factory Rd"
    assert warrant.customer_name == "Customer XYZ"
    assert warrant.customer_contact == "Buyer Bob"
    assert warrant.materials_reporting == "IMDS-9999"
    assert warrant.polymeric_parts_marking == "ISO 11469"
    assert warrant.customer_tool_tagging == "Tag #55"
    assert warrant.production_rate == 250
    assert warrant.production_duration_hours == 12.5
    assert warrant.explanation_comments == "Special test run"
    assert warrant.authorized_signature == "Alice Johnson"
    assert warrant.authorized_signature_name == "Alice Johnson"


def test_part_submission_warrant_secondary_aliases() -> None:
    """Verify secondary aliases (weight_kg, organization, imds_id, explanation)."""
    raw = {
        "weight_kg": 3.75,
        "organization": "Stamping Inc",
        "imds_id": "IMDS-001122",
        "explanation": "Tooling replacement explanation",
    }
    warrant = PartSubmissionWarrant(**raw)
    assert warrant.part_weight_kg == 3.75
    assert warrant.organization_name == "Stamping Inc"
    assert warrant.materials_reporting == "IMDS-001122"
    assert warrant.explanation_comments == "Tooling replacement explanation"


def test_part_submission_warrant_sync_fields_non_dict() -> None:
    """Verify _sync_fields validator passes non-dict data untouched."""
    res = PartSubmissionWarrant._sync_fields("not a dict")
    assert res == "not a dict"


def test_part_submission_warrant_submission_level_normalization() -> None:
    """Verify submission level normalizer handles ints and string aliases."""
    for lvl in (1, 2, 3, 4, 5):
        w = PartSubmissionWarrant(submission_level=lvl)
        assert w.submission_level == lvl

    # String aliases
    assert PartSubmissionWarrant(submission_level="level 1").submission_level == 1
    assert PartSubmissionWarrant(submission_level="level_2").submission_level == 2
    assert PartSubmissionWarrant(submission_level="3").submission_level == 3
    assert PartSubmissionWarrant(submission_level="Level 4").submission_level == 4
    assert PartSubmissionWarrant(submission_level="level 5").submission_level == 5

    # Invalid values remain as passed for validate_psw to flag
    assert PartSubmissionWarrant(submission_level="invalid_lvl").submission_level == "invalid_lvl"
    assert PartSubmissionWarrant(submission_level=99).submission_level == 99

    # Direct classmethod call with non-int/non-string
    assert PartSubmissionWarrant.normalize_submission_level([1, 2]) == [1, 2]


def test_part_submission_warrant_reason_for_submission_normalization() -> None:
    """Verify reason for submission normalizer handles canonical strings and aliases."""
    for reason in REASON_FOR_SUBMISSION_VALUES:
        w = PartSubmissionWarrant(reason_for_submission=reason)
        assert w.reason_for_submission == reason

    # Aliases
    assert PartSubmissionWarrant(reason_for_submission="initial").reason_for_submission == "Initial Submission"
    assert PartSubmissionWarrant(reason_for_submission="engineering change").reason_for_submission == "Engineering Change(s)"
    assert PartSubmissionWarrant(reason_for_submission="other").reason_for_submission == "Other"

    # Unrecognized reason remains as passed
    assert PartSubmissionWarrant(reason_for_submission="unknown reason").reason_for_submission == "unknown reason"

    # Direct classmethod call with non-string
    assert PartSubmissionWarrant.normalize_reason_for_submission(123) == 123


# ==============================================================================
# 4. Dataclasses: PSWFieldStatus & PSWValidationResult
# ==============================================================================

def test_psw_field_status_to_dict() -> None:
    """Verify PSWFieldStatus serialization."""
    status = PSWFieldStatus(
        field_number=1,
        field_name="Part Name",
        verdict="VALID",
        value="Bracket Front",
        details="Part Name provided.",
        is_required=True,
        standard_reference="AIAG PPAP 4th Edition Appendix A Field 1",
    )
    d = status.to_dict()
    assert d == {
        "field_number": 1,
        "field_name": "Part Name",
        "verdict": "VALID",
        "value": "Bracket Front",
        "details": "Part Name provided.",
        "is_required": True,
        "standard_reference": "AIAG PPAP 4th Edition Appendix A Field 1",
    }


def test_psw_validation_result_methods_and_serialization() -> None:
    """Verify PSWValidationResult lookup, is_valid, and serialization."""
    f1 = PSWFieldStatus(field_number=1, field_name="Part Name", verdict="VALID", value="Bracket")
    f9 = PSWFieldStatus(field_number=9, field_name="Checking Aid Number", verdict="NOT_APPLICABLE", value=None)
    f8 = PSWFieldStatus(field_number=8, field_name="Part Weight (kg)", verdict="MISSING", value=None)
    f20 = PSWFieldStatus(field_number=20, field_name="Submission Results", verdict="INVALID", value="bad")

    res = PSWValidationResult(
        verdict="INCOMPLETE",
        fields={1: f1, 9: f9, 8: f8, 20: f20},
        missing_fields=[8],
        invalid_fields=[20],
        indeterminate_fields=[],
        blanket_statement_detected=False,
        blanket_statement_findings=[],
        cross_consistency_findings=[],
        customer_disposition_present=False,
        customer_disposition_warning=None,
        warnings=[],
    )

    # get_field
    assert res.get_field(1) == f1
    assert res.get_field(9) == f9
    assert res.get_field(99) is None

    # is_valid
    assert res.is_valid(1) is True  # VALID
    assert res.is_valid(9) is True  # NOT_APPLICABLE
    assert res.is_valid(8) is False  # MISSING
    assert res.is_valid(20) is False  # INVALID
    assert res.is_valid(99) is False  # Missing field

    # to_dict
    d = res.to_dict()
    assert d["verdict"] == "INCOMPLETE"
    assert d["missing_fields"] == [8]
    assert d["invalid_fields"] == [20]
    assert d["fields"][1]["verdict"] == "VALID"
    assert d["fields"][9]["verdict"] == "NOT_APPLICABLE"


# ==============================================================================
# 5. Full 27-Field Happy Path Validation
# ==============================================================================

def test_validate_psw_complete_happy_path() -> None:
    """Verify a complete, valid warrant yields COMPLETE verdict with 27 valid/n-a fields."""
    raw = make_valid_warrant_dict()
    pkg = make_valid_package()

    # Pass as dict
    res_dict = validate_psw(raw, package=pkg)
    assert res_dict.verdict == "COMPLETE"
    assert len(res_dict.missing_fields) == 0
    assert len(res_dict.invalid_fields) == 0
    assert len(res_dict.indeterminate_fields) == 0
    assert not res_dict.blanket_statement_detected
    assert len(res_dict.cross_consistency_findings) == 0
    assert not res_dict.customer_disposition_present
    assert res_dict.customer_disposition_warning is None

    for i in range(1, 28):
        f = res_dict.get_field(i)
        assert f is not None
        assert f.verdict in ("VALID", "NOT_APPLICABLE")

    # Pass as PartSubmissionWarrant instance
    warrant = PartSubmissionWarrant(**raw)
    res_instance = validate_psw(warrant, package=pkg)
    assert res_instance.verdict == "COMPLETE"


def test_validate_psw_invalid_input_type_raises() -> None:
    """Verify validate_psw raises TypeError when passed non-dict, non-warrant types."""
    with pytest.raises(TypeError, match="psw must be PartSubmissionWarrant or dict"):
        validate_psw("not a valid warrant")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="psw must be PartSubmissionWarrant or dict"):
        validate_psw(12345)  # type: ignore[arg-type]


# ==============================================================================
# 6. Per-Field Comprehensive Branch Coverage (Fields 1 to 27)
# ==============================================================================

# --- Field 1: Part Name ---
def test_field_1_part_name_branches() -> None:
    # Valid
    r_valid = validate_psw({"part_name": "Bracket Front"})
    assert r_valid.get_field(1).verdict == "VALID"  # type: ignore[union-attr]

    # Missing (None)
    r_none = validate_psw({"part_name": None})
    assert r_none.get_field(1).verdict == "MISSING"  # type: ignore[union-attr]

    # Missing (whitespace)
    r_empty = validate_psw({"part_name": "   "})
    assert r_empty.get_field(1).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 2: Customer Part Number ---
def test_field_2_customer_part_number_branches() -> None:
    # Valid
    r_valid = validate_psw({"customer_part_number": "CPN-12345"})
    assert r_valid.get_field(2).verdict == "VALID"  # type: ignore[union-attr]

    # Missing (None)
    r_none = validate_psw({"customer_part_number": None})
    assert r_none.get_field(2).verdict == "MISSING"  # type: ignore[union-attr]

    # Missing (whitespace)
    r_empty = validate_psw({"customer_part_number": "   "})
    assert r_empty.get_field(2).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 3: Part Drawing Number / Org Part Number ---
def test_field_3_drawing_number_branches() -> None:
    # Valid with drawing number
    r_dwg = validate_psw({"part_drawing_number": "DWG-100"})
    assert r_dwg.get_field(3).verdict == "VALID"  # type: ignore[union-attr]
    assert r_dwg.get_field(3).value == "DWG-100"  # type: ignore[union-attr]

    # Valid with org part number when drawing number is None
    r_org = validate_psw({"part_drawing_number": None, "org_part_number": "ORG-PART-99"})
    assert r_org.get_field(3).verdict == "VALID"  # type: ignore[union-attr]
    assert r_org.get_field(3).value == "ORG-PART-99"  # type: ignore[union-attr]

    # Missing when both are None / empty
    r_none = validate_psw({"part_drawing_number": None, "org_part_number": None})
    assert r_none.get_field(3).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"part_drawing_number": "  ", "org_part_number": "  "})
    assert r_empty.get_field(3).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 4: Engineering Change Level ---
def test_field_4_engineering_change_level_branches() -> None:
    # Valid
    r_valid = validate_psw({"engineering_change_level": "Rev C"})
    assert r_valid.get_field(4).verdict == "VALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"engineering_change_level": None})
    assert r_none.get_field(4).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"engineering_change_level": "  "})
    assert r_empty.get_field(4).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 5: Engineering Change Date ---
def test_field_5_engineering_change_date_branches() -> None:
    # Valid str
    r_str = validate_psw({"engineering_change_date": "2026-02-15"})
    assert r_str.get_field(5).verdict == "VALID"  # type: ignore[union-attr]

    # Valid date
    r_date = validate_psw({"engineering_change_date": datetime.date(2026, 2, 15)})
    assert r_date.get_field(5).verdict == "VALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"engineering_change_date": None})
    assert r_none.get_field(5).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"engineering_change_date": "  "})
    assert r_empty.get_field(5).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 6: Additional Engineering Changes ---
def test_field_6_additional_engineering_changes_branches() -> None:
    # Valid with documented changes
    r_with = validate_psw({"additional_engineering_changes": "ECN-101, ECN-102"})
    assert r_with.get_field(6).verdict == "VALID"  # type: ignore[union-attr]
    assert "documented" in r_with.get_field(6).details  # type: ignore[union-attr]

    # Valid when empty / None (optional field)
    r_none = validate_psw({"additional_engineering_changes": None})
    assert r_none.get_field(6).verdict == "VALID"  # type: ignore[union-attr]
    assert "No additional engineering changes" in r_none.get_field(6).details  # type: ignore[union-attr]


# --- Field 7: Purchase Order Number ---
def test_field_7_purchase_order_number_branches() -> None:
    # Valid
    r_valid = validate_psw({"purchase_order_number": "PO-12345"})
    assert r_valid.get_field(7).verdict == "VALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"purchase_order_number": None})
    assert r_none.get_field(7).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"purchase_order_number": "  "})
    assert r_empty.get_field(7).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 8: Part Weight (kg) ---
def test_field_8_part_weight_branches() -> None:
    # Valid positive float / int
    r_float = validate_psw({"part_weight_kg": 2.5})
    assert r_float.get_field(8).verdict == "VALID"  # type: ignore[union-attr]
    assert r_float.get_field(8).value == 2.5  # type: ignore[union-attr]

    r_int = validate_psw({"part_weight_kg": 10})
    assert r_int.get_field(8).verdict == "VALID"  # type: ignore[union-attr]

    # Invalid <= 0
    r_zero = validate_psw({"part_weight_kg": 0.0})
    assert r_zero.get_field(8).verdict == "INVALID"  # type: ignore[union-attr]

    r_neg = validate_psw({"part_weight_kg": -1.2})
    assert r_neg.get_field(8).verdict == "INVALID"  # type: ignore[union-attr]

    # Missing (None)
    r_none = validate_psw({"part_weight_kg": None})
    assert r_none.get_field(8).verdict == "MISSING"  # type: ignore[union-attr]

    # Invalid non-numeric string / type
    w_bad = PartSubmissionWarrant.model_construct(part_weight_kg="not_a_number")  # type: ignore[arg-type]
    r_bad = validate_psw(w_bad)
    assert r_bad.get_field(8).verdict == "INVALID"  # type: ignore[union-attr]


# --- Fields 9 & 10: Checking Aid & Change Level / Date ---
def test_fields_9_and_10_checking_aid_conditional_branches() -> None:
    # Case A: has_checking_aid=True, aid provided -> Field 9 VALID, Field 10 VALID
    r_a = validate_psw(
        {"checking_aid_number": "GAUGE-01", "checking_aid_change_level_date": "Rev 1 2026-01-01"},
        has_checking_aid=True,
    )
    assert r_a.get_field(9).verdict == "VALID"  # type: ignore[union-attr]
    assert r_a.get_field(10).verdict == "VALID"  # type: ignore[union-attr]

    # Case B: has_checking_aid=True, aid missing -> Field 9 MISSING, Field 10 NOT_APPLICABLE
    r_b = validate_psw({"checking_aid_number": None}, has_checking_aid=True)
    assert r_b.get_field(9).verdict == "MISSING"  # type: ignore[union-attr]
    assert r_b.get_field(10).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]

    # Case C: has_checking_aid=True, aid is "N/A" -> Field 9 MISSING
    r_c = validate_psw({"checking_aid_number": "N/A"}, has_checking_aid=True)
    assert r_c.get_field(9).verdict == "MISSING"  # type: ignore[union-attr]

    # Case D: has_checking_aid=True, Field 9 VALID but Field 10 missing/None -> Field 10 MISSING
    r_d1 = validate_psw({"checking_aid_number": "GAUGE-01", "checking_aid_change_level_date": None}, has_checking_aid=True)
    assert r_d1.get_field(9).verdict == "VALID"  # type: ignore[union-attr]
    assert r_d1.get_field(10).verdict == "MISSING"  # type: ignore[union-attr]

    # Case E: has_checking_aid=True, Field 9 VALID but Field 10 is "n/a" -> Field 10 MISSING
    r_d2 = validate_psw({"checking_aid_number": "GAUGE-01", "checking_aid_change_level_date": "N/A"}, has_checking_aid=True)
    assert r_d2.get_field(10).verdict == "MISSING"  # type: ignore[union-attr]

    # Case F: has_checking_aid=False -> Field 9 NOT_APPLICABLE, Field 10 NOT_APPLICABLE
    r_f = validate_psw({"checking_aid_number": "GAUGE-01"}, has_checking_aid=False)
    assert r_f.get_field(9).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]
    assert r_f.get_field(10).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]

    # Case G: has_checking_aid=None (un-surveyed):
    # - If provided and not N/A -> VALID
    r_g1 = validate_psw({"checking_aid_number": "GAUGE-99", "checking_aid_change_level_date": "Rev A"}, has_checking_aid=None)
    assert r_g1.get_field(9).verdict == "VALID"  # type: ignore[union-attr]
    assert r_g1.get_field(10).verdict == "VALID"  # type: ignore[union-attr]

    # - If None / N/A -> NOT_APPLICABLE
    r_g2 = validate_psw({"checking_aid_number": None}, has_checking_aid=None)
    assert r_g2.get_field(9).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]
    assert r_g2.get_field(10).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]

    r_g3 = validate_psw({"checking_aid_number": "none"}, has_checking_aid=None)
    assert r_g3.get_field(9).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]
    assert r_g3.get_field(10).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]


def test_checking_aid_inferred_from_package() -> None:
    """Verify has_checking_aid is inferred from PPAPPackage if not explicitly passed."""
    pkg_with_aid = PPAPPackage(
        part_name="Part A",
        part_number="P-01",
        submission_level=3,
        reason_for_submission="Initial Submission",
        has_checking_aid=True,
    )
    r_pkg = validate_psw({"checking_aid_number": None}, package=pkg_with_aid)
    assert r_pkg.get_field(9).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 11: Organization Name & Code ---
def test_field_11_organization_name_and_code_branches() -> None:
    # Valid with code
    r_code = validate_psw({"organization_name": "Acme Stamping", "organization_code": "ORG-1"})
    assert r_code.get_field(11).verdict == "VALID"  # type: ignore[union-attr]
    assert "Code: ORG-1" in str(r_code.get_field(11).value)  # type: ignore[union-attr]

    # Valid without code
    r_no_code = validate_psw({"organization_name": "Acme Stamping", "organization_code": None})
    assert r_no_code.get_field(11).verdict == "VALID"  # type: ignore[union-attr]
    assert "Code" not in str(r_no_code.get_field(11).value)  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"organization_name": None})
    assert r_none.get_field(11).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"organization_name": "  "})
    assert r_empty.get_field(11).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 12: Organization Manufacturing Address ---
def test_field_12_organization_address_branches() -> None:
    # Valid
    r_valid = validate_psw({"organization_address": "123 Main St"})
    assert r_valid.get_field(12).verdict == "VALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"organization_address": None})
    assert r_none.get_field(12).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"organization_address": "  "})
    assert r_empty.get_field(12).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 13: Customer Name & Division ---
def test_field_13_customer_name_and_division_branches() -> None:
    # Valid with division
    r_div = validate_psw({"customer_name": "Global Motors", "customer_division": "Truck"})
    assert r_div.get_field(13).verdict == "VALID"  # type: ignore[union-attr]
    assert "/ Truck" in str(r_div.get_field(13).value)  # type: ignore[union-attr]

    # Valid without division
    r_no_div = validate_psw({"customer_name": "Global Motors", "customer_division": None})
    assert r_no_div.get_field(13).verdict == "VALID"  # type: ignore[union-attr]
    assert "/ " not in str(r_no_div.get_field(13).value)  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"customer_name": None})
    assert r_none.get_field(13).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"customer_name": "  "})
    assert r_empty.get_field(13).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 14: Customer Contact / Buyer ---
def test_field_14_customer_contact_branches() -> None:
    # Valid
    r_valid = validate_psw({"customer_contact": "Jane Doe"})
    assert r_valid.get_field(14).verdict == "VALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"customer_contact": None})
    assert r_none.get_field(14).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"customer_contact": "  "})
    assert r_empty.get_field(14).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 15: Application ---
def test_field_15_application_branches() -> None:
    # Valid
    r_valid = validate_psw({"application": "2027 EV Program"})
    assert r_valid.get_field(15).verdict == "VALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"application": None})
    assert r_none.get_field(15).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"application": "  "})
    assert r_empty.get_field(15).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 16: Materials Reporting (IMDS) ---
def test_field_16_materials_reporting_branches() -> None:
    # Valid string
    r_str = validate_psw({"materials_reporting": "IMDS #998877"})
    assert r_str.get_field(16).verdict == "VALID"  # type: ignore[union-attr]

    # Valid boolean
    r_bool = validate_psw({"materials_reporting": True})
    assert r_bool.get_field(16).verdict == "VALID"  # type: ignore[union-attr]

    # NOT_APPLICABLE sentinels
    for na_val in ("N/A", "na", "not applicable", " Not Applicable "):
        r_na = validate_psw({"materials_reporting": na_val})
        assert r_na.get_field(16).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"materials_reporting": None})
    assert r_none.get_field(16).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"materials_reporting": "  "})
    assert r_empty.get_field(16).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 17: Polymeric Parts Marking ---
def test_field_17_polymeric_parts_marking_branches() -> None:
    # Valid string
    r_str = validate_psw({"polymeric_parts_marking": "ISO 11469"})
    assert r_str.get_field(17).verdict == "VALID"  # type: ignore[union-attr]

    # Valid boolean
    r_bool = validate_psw({"polymeric_parts_marking": True})
    assert r_bool.get_field(17).verdict == "VALID"  # type: ignore[union-attr]

    # NOT_APPLICABLE sentinels
    for na_val in ("N/A", "na", "not applicable", " Not Applicable "):
        r_na = validate_psw({"polymeric_parts_marking": na_val})
        assert r_na.get_field(17).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"polymeric_parts_marking": None})
    assert r_none.get_field(17).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"polymeric_parts_marking": "  "})
    assert r_empty.get_field(17).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 18: Reason for Submission ---
def test_field_18_reason_for_submission_branches() -> None:
    # All 9 non-Other canonical reasons -> VALID
    for reason in REASON_FOR_SUBMISSION_VALUES:
        if reason == "Other":
            continue
        r = validate_psw({"reason_for_submission": reason})
        assert r.get_field(18).verdict == "VALID"  # type: ignore[union-attr]

    # Reason "Other" WITH Field 25 explanation -> VALID
    r_other_valid = validate_psw({
        "reason_for_submission": "Other",
        "explanation_comments": "Special prototype run for customer validation.",
    })
    assert r_other_valid.get_field(18).verdict == "VALID"  # type: ignore[union-attr]

    # Reason "Other" WITHOUT Field 25 explanation -> INVALID
    r_other_inv1 = validate_psw({"reason_for_submission": "Other", "explanation_comments": None})
    assert r_other_inv1.get_field(18).verdict == "INVALID"  # type: ignore[union-attr]

    r_other_inv2 = validate_psw({"reason_for_submission": "Other", "explanation_comments": "   "})
    assert r_other_inv2.get_field(18).verdict == "INVALID"  # type: ignore[union-attr]

    # Unnormalized alias directly passed via model_construct -> hits line 953 in validate_psw
    w_alias = PartSubmissionWarrant.model_construct(reason_for_submission="initial")
    r_alias = validate_psw(w_alias)
    assert r_alias.get_field(18).verdict == "VALID"  # type: ignore[union-attr]
    assert r_alias.get_field(18).value == "Initial Submission"  # type: ignore[union-attr]

    # Invalid Reason
    r_inv = validate_psw({"reason_for_submission": "Unapproved Reason"})
    assert r_inv.get_field(18).verdict == "INVALID"  # type: ignore[union-attr]

    # Missing Reason
    r_none = validate_psw({"reason_for_submission": None})
    assert r_none.get_field(18).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 19: Submission Level ---
def test_field_19_submission_level_branches() -> None:
    # Levels 1 to 5 -> VALID
    for lvl in SUBMISSION_LEVELS:
        r = validate_psw({"submission_level": lvl})
        assert r.get_field(19).verdict == "VALID"  # type: ignore[union-attr]
        assert r.get_field(19).value == lvl  # type: ignore[union-attr]

    # Submission Level string aliases -> VALID
    r_alias = validate_psw({"submission_level": "level 2"})
    assert r_alias.get_field(19).verdict == "VALID"  # type: ignore[union-attr]
    assert r_alias.get_field(19).value == 2  # type: ignore[union-attr]

    # Unnormalized level alias passed directly via model_construct -> hits line 1020 in validate_psw
    w_unnorm_lvl = PartSubmissionWarrant.model_construct(submission_level="level 4")
    r_unnorm = validate_psw(w_unnorm_lvl)
    assert r_unnorm.get_field(19).verdict == "VALID"  # type: ignore[union-attr]
    assert r_unnorm.get_field(19).value == 4  # type: ignore[union-attr]

    # Invalid Level
    w_inv = PartSubmissionWarrant.model_construct(submission_level=99)  # type: ignore[arg-type]
    r_inv = validate_psw(w_inv)
    assert r_inv.get_field(19).verdict == "INVALID"  # type: ignore[union-attr]

    # Missing Level
    r_none = validate_psw({"submission_level": None})
    assert r_none.get_field(19).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 20: Submission Results ---
def test_field_20_submission_results_branches() -> None:
    # Valid string
    r_str = validate_psw({"submission_results": "Dimensional and material tests meet print specs."})
    assert r_str.get_field(20).verdict == "VALID"  # type: ignore[union-attr]

    # Valid explicit results flags when string is None
    r_flags = validate_psw({
        "submission_results": None,
        "results_dimensional": True,
        "results_material_functional": True,
        "results_appearance": False,
        "results_process_capability": True,
    })
    assert r_flags.get_field(20).verdict == "VALID"  # type: ignore[union-attr]
    assert r_flags.get_field(20).value == {  # type: ignore[union-attr]
        "dimensional": True,
        "material_functional": True,
        "appearance": False,
        "process_capability": True,
    }

    # Prohibited blanket statement in results -> INVALID
    r_bs = validate_psw({"submission_results": "Meets all specs and 100% conforming."})
    assert r_bs.get_field(20).verdict == "INVALID"  # type: ignore[union-attr]
    assert r_bs.blanket_statement_detected is True
    assert len(r_bs.blanket_statement_findings) >= 1

    # Missing results
    r_none = validate_psw({"submission_results": None})
    assert r_none.get_field(20).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 21: Declaration of Conformance ---
def test_field_21_declaration_of_conformance_branches() -> None:
    # Conforming (True, "yes", "y", "conforming", "conforms") -> VALID
    for true_val in (True, "true", "yes", "y", "conforming", "conforms", "YES"):
        r = validate_psw({"declaration_of_conformance": true_val})
        assert r.get_field(21).verdict == "VALID"  # type: ignore[union-attr]
        assert r.get_field(21).value is True  # type: ignore[union-attr]

    # Non-conforming (False, "no", "n", "nonconforming") WITH Field 25 explanation -> VALID
    for false_val in (False, "false", "no", "n", "nonconforming", "NO"):
        r = validate_psw({
            "declaration_of_conformance": false_val,
            "explanation_comments": "Deviation approved under SREA-4001 pending tooling adjustment.",
        })
        assert r.get_field(21).verdict == "VALID"  # type: ignore[union-attr]
        assert r.get_field(21).value is False  # type: ignore[union-attr]

    # Non-conforming WITHOUT Field 25 explanation -> INVALID
    r_no_exp1 = validate_psw({"declaration_of_conformance": False, "explanation_comments": None})
    assert r_no_exp1.get_field(21).verdict == "INVALID"  # type: ignore[union-attr]

    r_no_exp2 = validate_psw({"declaration_of_conformance": "no", "explanation_comments": "   "})
    assert r_no_exp2.get_field(21).verdict == "INVALID"  # type: ignore[union-attr]

    # Invalid value
    r_inv = validate_psw({"declaration_of_conformance": "maybe"})
    assert r_inv.get_field(21).verdict == "INVALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"declaration_of_conformance": None})
    assert r_none.get_field(21).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 22: Customer Tool Tagging / Identification ---
def test_field_22_customer_tool_tagging_branches() -> None:
    # Valid string
    r_str = validate_psw({"customer_tool_tagging": "Tagged GM-1002"})
    assert r_str.get_field(22).verdict == "VALID"  # type: ignore[union-attr]

    # Valid bool
    r_bool = validate_psw({"customer_tool_tagging": True})
    assert r_bool.get_field(22).verdict == "VALID"  # type: ignore[union-attr]

    # NOT_APPLICABLE sentinels
    for na_val in ("N/A", "na", "not applicable", " Not Applicable "):
        r_na = validate_psw({"customer_tool_tagging": na_val})
        assert r_na.get_field(22).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"customer_tool_tagging": None})
    assert r_none.get_field(22).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"customer_tool_tagging": "  "})
    assert r_empty.get_field(22).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 23: Production Rate (Pieces) ---
def test_field_23_production_rate_branches() -> None:
    # Valid positive
    r_pos = validate_psw({"production_rate": 300})
    assert r_pos.get_field(23).verdict == "VALID"  # type: ignore[union-attr]
    assert r_pos.get_field(23).value == 300.0  # type: ignore[union-attr]

    # Invalid <= 0
    r_zero = validate_psw({"production_rate": 0})
    assert r_zero.get_field(23).verdict == "INVALID"  # type: ignore[union-attr]

    r_neg = validate_psw({"production_rate": -50})
    assert r_neg.get_field(23).verdict == "INVALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"production_rate": None})
    assert r_none.get_field(23).verdict == "MISSING"  # type: ignore[union-attr]

    # Non-numeric
    w_bad = PartSubmissionWarrant.model_construct(production_rate="bad_rate")  # type: ignore[arg-type]
    r_bad = validate_psw(w_bad)
    assert r_bad.get_field(23).verdict == "INVALID"  # type: ignore[union-attr]


# --- Field 24: Production Run Duration (Hours) ---
def test_field_24_production_duration_branches() -> None:
    # Valid positive
    r_pos = validate_psw({"production_duration_hours": 8.0})
    assert r_pos.get_field(24).verdict == "VALID"  # type: ignore[union-attr]
    assert r_pos.get_field(24).value == 8.0  # type: ignore[union-attr]

    # Invalid <= 0
    r_zero = validate_psw({"production_duration_hours": 0.0})
    assert r_zero.get_field(24).verdict == "INVALID"  # type: ignore[union-attr]

    r_neg = validate_psw({"production_duration_hours": -2.0})
    assert r_neg.get_field(24).verdict == "INVALID"  # type: ignore[union-attr]

    # Missing
    r_none = validate_psw({"production_duration_hours": None})
    assert r_none.get_field(24).verdict == "MISSING"  # type: ignore[union-attr]

    # Non-numeric
    w_bad = PartSubmissionWarrant.model_construct(production_duration_hours="bad_duration")  # type: ignore[arg-type]
    r_bad = validate_psw(w_bad)
    assert r_bad.get_field(24).verdict == "INVALID"  # type: ignore[union-attr]


# --- Field 25: Explanation / Comments ---
def test_field_25_explanation_comments_branches() -> None:
    # Valid text
    r_valid = validate_psw({"explanation_comments": "Regular pilot production run."})
    assert r_valid.get_field(25).verdict == "VALID"  # type: ignore[union-attr]
    assert r_valid.get_field(25).value == "Regular pilot production run."  # type: ignore[union-attr]

    # Valid None (optional field)
    r_none = validate_psw({"explanation_comments": None})
    assert r_none.get_field(25).verdict == "VALID"  # type: ignore[union-attr]
    assert r_none.get_field(25).value is None  # type: ignore[union-attr]

    # Valid empty (optional field)
    r_empty = validate_psw({"explanation_comments": "   "})
    assert r_empty.get_field(25).verdict == "VALID"  # type: ignore[union-attr]
    assert r_empty.get_field(25).value is None  # type: ignore[union-attr]

    # Prohibited blanket statement in explanation -> INVALID
    r_bs = validate_psw({"explanation_comments": "All dimensions conform without any issues."})
    assert r_bs.get_field(25).verdict == "INVALID"  # type: ignore[union-attr]
    assert r_bs.blanket_statement_detected is True
    assert any("Field 25" in f for f in r_bs.blanket_statement_findings)


# --- Field 26: Organization Authorized Signature ---
def test_field_26_authorized_signature_branches() -> None:
    # Valid with name
    r_name = validate_psw({"authorized_signature_name": "John Doe, Quality Manager"})
    assert r_name.get_field(26).verdict == "VALID"  # type: ignore[union-attr]
    assert r_name.get_field(26).value == "John Doe, Quality Manager"  # type: ignore[union-attr]

    # Valid with string signature
    r_sig_str = validate_psw({"authorized_signature": "John Doe", "authorized_signature_name": None})
    assert r_sig_str.get_field(26).verdict == "VALID"  # type: ignore[union-attr]
    assert r_sig_str.get_field(26).value == "John Doe"  # type: ignore[union-attr]

    # Valid with boolean True signature
    r_sig_bool = validate_psw({"authorized_signature": True, "authorized_signature_name": None})
    assert r_sig_bool.get_field(26).verdict == "VALID"  # type: ignore[union-attr]
    assert "Authorized Signature on file" in str(r_sig_bool.get_field(26).value)  # type: ignore[union-attr]

    # Missing when None, False, or empty
    r_none = validate_psw({"authorized_signature": None, "authorized_signature_name": None})
    assert r_none.get_field(26).verdict == "MISSING"  # type: ignore[union-attr]

    r_false = validate_psw({"authorized_signature": False, "authorized_signature_name": None})
    assert r_false.get_field(26).verdict == "MISSING"  # type: ignore[union-attr]

    r_empty = validate_psw({"authorized_signature": "   ", "authorized_signature_name": "   "})
    assert r_empty.get_field(26).verdict == "MISSING"  # type: ignore[union-attr]


# --- Field 27: Customer Disposition & Mandatory Customer Authority Invariant ---
def test_field_27_customer_disposition_invariant() -> None:
    """Verify Customer Authority Invariant: Field 27 is always NOT_APPLICABLE and never emits dispositions."""
    # Case 1: Unpopulated (supplier normal submission)
    r_empty = validate_psw({"customer_disposition": None})
    f27_empty = r_empty.get_field(27)
    assert f27_empty is not None
    assert f27_empty.verdict == "NOT_APPLICABLE"
    assert not r_empty.customer_disposition_present
    assert r_empty.customer_disposition_warning is None

    # Case 2: Populated (attempted injection of customer approval/rejection)
    for disposition_attempt in ("Approved", "Rejected", "Interim Approval", "Conditionally Approved"):
        full = make_valid_warrant_dict()
        full["customer_disposition"] = disposition_attempt
        r_pop = validate_psw(full)

        f27_pop = r_pop.get_field(27)
        assert f27_pop is not None
        assert f27_pop.verdict == "NOT_APPLICABLE"
        assert r_pop.customer_disposition_present is True
        assert r_pop.customer_disposition_warning is not None
        assert "FOR CUSTOMER USE ONLY" in r_pop.customer_disposition_warning
        assert any("Field 27" in w for w in r_pop.warnings)

        # MANDATORY INVARIANT: Verdict is only COMPLETE/INCOMPLETE/INDETERMINATE, never disposition string
        assert r_pop.verdict in ("COMPLETE", "INCOMPLETE", "INDETERMINATE")
        assert r_pop.verdict not in ("Approved", "Rejected", "Interim Approval", disposition_attempt)


# ==============================================================================
# 7. Cross-Consistency Checks Against PPAPPackage
# ==============================================================================

def test_cross_consistency_checks_all_mismatches() -> None:
    """Verify mismatches between Warrant and PPAPPackage metadata generate findings."""
    pkg = PPAPPackage(
        part_name="Bracket Front",
        part_number="CPN-001",
        supplier_name="Acme Detroit",
        customer_name="Global Motors",
        submission_level=3,
        reason_for_submission="Initial Submission",
        has_checking_aid=True,
    )

    # 1. Part Number Mismatch
    r_pnum = validate_psw(
        {"part_name": "Bracket Front", "customer_part_number": "DIFFERENT-PN", "submission_level": 3, "reason_for_submission": "Initial Submission"},
        package=pkg,
    )
    assert any("Part Number" in f for f in r_pnum.cross_consistency_findings)

    # 2. Part Name Mismatch
    r_pname = validate_psw(
        {"part_name": "Different Name", "customer_part_number": "CPN-001", "submission_level": 3, "reason_for_submission": "Initial Submission"},
        package=pkg,
    )
    assert any("Part Name" in f for f in r_pname.cross_consistency_findings)

    # 3. Submission Level Mismatch
    r_lvl = validate_psw(
        {"part_name": "Bracket Front", "customer_part_number": "CPN-001", "submission_level": 1, "reason_for_submission": "Initial Submission"},
        package=pkg,
    )
    assert any("Submission Level" in f for f in r_lvl.cross_consistency_findings)

    # 4. Reason for Submission Mismatch
    r_reason = validate_psw(
        {"part_name": "Bracket Front", "customer_part_number": "CPN-001", "submission_level": 3, "reason_for_submission": "Engineering Change(s)"},
        package=pkg,
    )
    assert any("Reason for Submission" in f for f in r_reason.cross_consistency_findings)

    # 5. Organization / Supplier Name Mismatch
    r_org = validate_psw(
        {"part_name": "Bracket Front", "customer_part_number": "CPN-001", "organization_name": "Wrong Supplier", "submission_level": 3, "reason_for_submission": "Initial Submission"},
        package=pkg,
    )
    assert any("Organization/Supplier Name" in f for f in r_org.cross_consistency_findings)

    # 6. Customer Name Mismatch
    r_cust = validate_psw(
        {"part_name": "Bracket Front", "customer_part_number": "CPN-001", "customer_name": "Wrong Customer", "submission_level": 3, "reason_for_submission": "Initial Submission"},
        package=pkg,
    )
    assert any("Customer Name" in f for f in r_cust.cross_consistency_findings)

    # 7. Checking Aid Mismatch (Package True, but PSW missing/not applicable)
    r_aid = validate_psw(
        {"part_name": "Bracket Front", "customer_part_number": "CPN-001", "submission_level": 3, "reason_for_submission": "Initial Submission", "checking_aid_number": None},
        package=pkg,
        has_checking_aid=False,  # forces NOT_APPLICABLE on Field 9 while package has True
    )
    assert any("has_checking_aid=True but PSW Checking Aid" in f for f in r_aid.cross_consistency_findings)


def test_cross_consistency_secondary_package_aliases() -> None:
    """Verify cross-consistency checks against package.organization and package.customer aliases."""
    pkg_alt = PPAPPackage(
        part_name="Bracket Front",
        part_number="CPN-001",
        organization="Acme Alt Org",
        customer="Global Alt Cust",
        submission_level=3,
        reason_for_submission="Initial Submission",
    )
    # Matching alt aliases
    r_match = validate_psw(
        {"part_name": "Bracket Front", "customer_part_number": "CPN-001", "organization_name": "Acme Alt Org", "customer_name": "Global Alt Cust", "submission_level": 3, "reason_for_submission": "Initial Submission"},
        package=pkg_alt,
    )
    assert len(r_match.cross_consistency_findings) == 0


# ==============================================================================
# 8. Overall Verdicts (COMPLETE, INCOMPLETE, INDETERMINATE)
# ==============================================================================

def test_overall_verdict_incomplete_conditions() -> None:
    """Verify verdict drives to INCOMPLETE for missing fields, invalid fields, blanket statements, or cross findings."""
    base = make_valid_warrant_dict()

    # 1. Missing field
    w_missing = dict(base)
    w_missing["part_name"] = None
    assert validate_psw(w_missing).verdict == "INCOMPLETE"

    # 2. Invalid field
    w_invalid = dict(base)
    w_invalid["part_weight_kg"] = -10.0
    assert validate_psw(w_invalid).verdict == "INCOMPLETE"

    # 3. Blanket statement
    w_bs = dict(base)
    w_bs["explanation_comments"] = "meets all specifications"
    assert validate_psw(w_bs).verdict == "INCOMPLETE"

    # 4. Cross-consistency mismatch
    pkg = make_valid_package()
    pkg.part_number = "CPN-DIFFERENT"
    assert validate_psw(base, package=pkg).verdict == "INCOMPLETE"


def test_overall_verdict_indeterminate_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify indeterminate branch handling in validate_psw when an indeterminate field occurs."""
    import quality_core.ppap.psw as psw_module

    orig_cls = psw_module.PSWFieldStatus

    def mock_field_status(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("field_number") == 1:
            kwargs["verdict"] = "INDETERMINATE"
        return orig_cls(*args, **kwargs)

    monkeypatch.setattr(psw_module, "PSWFieldStatus", mock_field_status)

    res = validate_psw(make_valid_warrant_dict())
    assert res.verdict == "INDETERMINATE"
    assert 1 in res.indeterminate_fields


# ==============================================================================
# 9. Load-Bearing Mutation & Negative Control Assertions
# ==============================================================================

def test_negative_control_disposition_injection_does_not_override_verdict() -> None:
    """Negative Control: Populating customer disposition with 'Approved' MUST NOT emit 'Approved' verdict."""
    full = make_valid_warrant_dict()
    full["customer_disposition"] = "Approved"

    result = validate_psw(full)
    # The supplier completeness evaluation is COMPLETE, NOT "Approved"
    assert result.verdict == "COMPLETE"
    assert result.verdict != "Approved"
    assert result.get_field(27).verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]
    assert result.customer_disposition_present is True


def test_negative_control_blanket_statement_blocks_complete_verdict() -> None:
    """Negative Control: Prohibited blanket statements MUST drive verdict to INCOMPLETE."""
    full = make_valid_warrant_dict()
    full["submission_results"] = "Bracket meets all specs."

    result = validate_psw(full)
    assert result.verdict == "INCOMPLETE"
    assert result.verdict != "COMPLETE"
    assert result.blanket_statement_detected is True
    assert result.get_field(20).verdict == "INVALID"  # type: ignore[union-attr]


def test_negative_control_reason_other_requires_explanation() -> None:
    """Negative Control: 'Other' reason with blank explanation MUST resolve INVALID."""
    full = make_valid_warrant_dict()
    full["reason_for_submission"] = "Other"
    full["explanation_comments"] = ""

    result = validate_psw(full)
    assert result.verdict == "INCOMPLETE"
    assert result.get_field(18).verdict == "INVALID"  # type: ignore[union-attr]


def test_negative_control_nonconformance_requires_explanation() -> None:
    """Negative Control: Conformance declaration 'No' with blank explanation MUST resolve INVALID."""
    full = make_valid_warrant_dict()
    full["declaration_of_conformance"] = False
    full["explanation_comments"] = ""

    result = validate_psw(full)
    assert result.verdict == "INCOMPLETE"
    assert result.get_field(21).verdict == "INVALID"  # type: ignore[union-attr]


def test_negative_control_boundary_part_weight_zero_and_negative() -> None:
    """Negative Control: Part weight of exactly 0.0 or negative MUST resolve INVALID, while 0.0001 resolves VALID."""
    # Boundary: 0.0 is INVALID
    r_zero = validate_psw(dict(make_valid_warrant_dict(), part_weight_kg=0.0))
    assert r_zero.get_field(8).verdict == "INVALID"  # type: ignore[union-attr]

    # Boundary: negative is INVALID
    r_neg = validate_psw(dict(make_valid_warrant_dict(), part_weight_kg=-0.001))
    assert r_neg.get_field(8).verdict == "INVALID"  # type: ignore[union-attr]

    # Boundary: positive epsilon is VALID
    r_pos = validate_psw(dict(make_valid_warrant_dict(), part_weight_kg=0.0001))
    assert r_pos.get_field(8).verdict == "VALID"  # type: ignore[union-attr]


def test_negative_control_boundary_production_rate_and_duration_bounds() -> None:
    """Negative Control: Production rate and duration <= 0 MUST resolve INVALID, while > 0 resolves VALID."""
    # Rate 0 -> INVALID
    r_rate_0 = validate_psw(dict(make_valid_warrant_dict(), production_rate=0))
    assert r_rate_0.get_field(23).verdict == "INVALID"  # type: ignore[union-attr]

    # Rate 1 -> VALID
    r_rate_1 = validate_psw(dict(make_valid_warrant_dict(), production_rate=1))
    assert r_rate_1.get_field(23).verdict == "VALID"  # type: ignore[union-attr]

    # Duration 0.0 -> INVALID
    r_dur_0 = validate_psw(dict(make_valid_warrant_dict(), production_duration_hours=0.0))
    assert r_dur_0.get_field(24).verdict == "INVALID"  # type: ignore[union-attr]

    # Duration 0.1 -> VALID
    r_dur_pos = validate_psw(dict(make_valid_warrant_dict(), production_duration_hours=0.1))
    assert r_dur_pos.get_field(24).verdict == "VALID"  # type: ignore[union-attr]

# ==============================================================================
# 10. Citations & Assumptions Log Integrity for PSW
# ==============================================================================

def test_ppap_psw_citations_manifest_integrity() -> None:
    ppap_dir = Path(__file__).resolve().parents[1] / "src" / "quality_core" / "ppap"
    manifest_path = ppap_dir / "CITATIONS.tsv"
    log_path = ppap_dir / "ASSUMPTIONS_LOG.md"

    assert manifest_path.exists(), f"CITATIONS.tsv not found at {manifest_path}"
    assert log_path.exists(), f"ASSUMPTIONS_LOG.md not found at {log_path}"

    with manifest_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    assert len(rows) >= 34
    sites = {r["site"] for r in rows}
    assert "RULE 8" in sites
    assert "RULE 9" in sites

    log_content = log_path.read_text(encoding="utf-8")
    assert "## RULE 8: Part Submission Warrant (PSW) 27-Field Form Completeness" in log_content
    assert "## RULE 9: Prohibition on Blanket Statements of Conformance" in log_content

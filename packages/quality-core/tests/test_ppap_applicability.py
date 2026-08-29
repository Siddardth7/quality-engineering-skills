"""
test_ppap_applicability.py
Comprehensive unit tests for quality_core.ppap.applicability (Milestone 8, Epic 3 / Issue #101).

Verifies 100% line & branch coverage on the PPAP element applicability engine:
- Applicability verdict taxonomy and conditional elements tuple
- ElementApplicability and ApplicabilityResult dataclasses and serialization (.to_dict())
- Element lookup (.get_element) by canonical ID, integer, or name alias
- Element applicability predicate (.is_applicable)
- Input normalization and trust boundary validation (_normalize_level, _normalize_reason, _to_element_id, _validate_bool_or_none)
- Default un-surveyed applicability evaluation (all 5 conditionals evaluate INDETERMINATE)
- Conditional element rules with True, False, and None (INDETERMINATE) branches:
  - §2.2.3 Customer Engineering Approval (customer_engineering_approval_required)
  - §2.2.4 Design FMEA (has_design_responsibility)
  - §2.2.13 Appearance Approval Report (appearance_item)
  - §2.2.15 Master Sample (master_sample_waived)
  - §2.2.16 Checking Aids (has_checking_aid)
- Submission Level 4 Indeterminacy Gate:
  - Level 4 negative control (customer_level_4_requirements=None -> all INDETERMINATE)
  - Level 4 explicit requirements via set, list, tuple, and dict with all verdict branches
- Commodity Scope Boundaries (Appendices F, G, H):
  - Bulk materials (Appendix F) via flag or commodity aliases
  - Tires (Appendix G) via flag or commodity aliases
  - Truck industry (Appendix H) via flag or commodity aliases
  - Combinations and multi-boundary notes
- PSW Field 18 Reason for Submission non-narrowing across all 10 canonical triggers
- Integration with PPAPPackage instances (including customer_requirement_set) and raw dictionaries
- Citation manifest integrity against AIAG PPAP 4th Edition
"""

from __future__ import annotations

import csv
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from quality_core.ppap.applicability import (
    APPLICABILITY_VERDICTS,
    CONDITIONAL_ELEMENTS,
    ApplicabilityResult,
    ElementApplicability,
    _normalize_level,
    _normalize_reason,
    _to_element_id,
    _validate_bool_or_none,
    assess_applicability,
)
from quality_core.ppap.schema import (
    PPAP_ELEMENT_IDS,
    PPAP_ELEMENT_NAMES,
    REASON_FOR_SUBMISSION_VALUES,
    SUBMISSION_LEVELS,
    PPAPPackage,
)

# ==============================================================================
# 1. Taxonomy & Constants
# ==============================================================================


def test_applicability_verdicts_constant() -> None:
    assert APPLICABILITY_VERDICTS == (
        "APPLICABLE",
        "NOT_APPLICABLE",
        "INDETERMINATE",
    )


def test_conditional_elements_constant() -> None:
    assert CONDITIONAL_ELEMENTS == (
        "2.2.3",   # Customer Engineering Approval
        "2.2.4",   # Design FMEA
        "2.2.13",  # Appearance Approval Report
        "2.2.15",  # Master Sample
        "2.2.16",  # Checking Aids
    )
    for elem_id in CONDITIONAL_ELEMENTS:
        assert elem_id in PPAP_ELEMENT_IDS


# ==============================================================================
# 2. Dataclasses & Serialization (.to_dict())
# ==============================================================================


def test_element_applicability_dataclass_and_immutability() -> None:
    elem = ElementApplicability(
        element_id="2.2.4",
        element_name="Design Failure Mode and Effects Analysis (Design FMEA)",
        verdict="APPLICABLE",
        rationale="Organization is design-responsible; Design FMEA is required (§2.2.4).",
        standard_reference="AIAG PPAP 4th Edition §2.2.4",
        is_conditional=True,
        condition_met=True,
    )
    assert elem.element_id == "2.2.4"
    assert elem.element_name == "Design Failure Mode and Effects Analysis (Design FMEA)"
    assert elem.verdict == "APPLICABLE"
    assert elem.rationale.startswith("Organization is design-responsible")
    assert elem.standard_reference == "AIAG PPAP 4th Edition §2.2.4"
    assert elem.is_conditional is True
    assert elem.condition_met is True

    # Immutability check (frozen=True)
    with pytest.raises(FrozenInstanceError):
        elem.verdict = "NOT_APPLICABLE"  # type: ignore[misc]

    d = elem.to_dict()
    assert d == {
        "element_id": "2.2.4",
        "element_name": "Design Failure Mode and Effects Analysis (Design FMEA)",
        "verdict": "APPLICABLE",
        "rationale": "Organization is design-responsible; Design FMEA is required (§2.2.4).",
        "standard_reference": "AIAG PPAP 4th Edition §2.2.4",
        "is_conditional": True,
        "condition_met": True,
    }


def test_applicability_result_lookup_and_predicates() -> None:
    elements_map: dict[str, ElementApplicability] = {}
    for elem_id in PPAP_ELEMENT_IDS:
        if elem_id == "2.2.4":
            elements_map[elem_id] = ElementApplicability(
                element_id=elem_id,
                element_name=PPAP_ELEMENT_NAMES[elem_id],
                verdict="APPLICABLE",
                rationale="Required",
                standard_reference="AIAG PPAP 4th Edition",
                is_conditional=True,
                condition_met=True,
            )
        elif elem_id == "2.2.13":
            elements_map[elem_id] = ElementApplicability(
                element_id=elem_id,
                element_name=PPAP_ELEMENT_NAMES[elem_id],
                verdict="NOT_APPLICABLE",
                rationale="Not an appearance item",
                standard_reference="AIAG PPAP 4th Edition",
                is_conditional=True,
                condition_met=False,
            )
        else:
            elements_map[elem_id] = ElementApplicability(
                element_id=elem_id,
                element_name=PPAP_ELEMENT_NAMES[elem_id],
                verdict="APPLICABLE",
                rationale="Mandatory",
                standard_reference="AIAG PPAP 4th Edition",
                is_conditional=False,
                condition_met=None,
            )

    res = ApplicabilityResult(
        package_verdict="APPLICABLE",
        submission_level=3,
        reason_for_submission="Initial Submission",
        elements=elements_map,
        applicable_elements=[eid for eid, e in elements_map.items() if e.verdict == "APPLICABLE"],
        not_applicable_elements=["2.2.13"],
        indeterminate_elements=[],
        scope_boundary_notes=[],
        standards_basis="AIAG PPAP 4th Edition (June 2006)",
    )

    # get_element by canonical string
    e_str = res.get_element("2.2.4")
    assert e_str is not None
    assert e_str.element_id == "2.2.4"

    # get_element by integer (1-indexed)
    e_int = res.get_element(4)
    assert e_int is not None
    assert e_int.element_id == "2.2.4"

    # get_element by alias
    e_alias = res.get_element("dfmea")
    assert e_alias is not None
    assert e_alias.element_id == "2.2.4"

    # get_element invalid / missing
    assert res.get_element("nonexistent") is None
    assert res.get_element(999) is None
    assert res.get_element(object()) is None  # type: ignore[arg-type]

    # is_applicable checks
    assert res.is_applicable("2.2.1") is True
    assert res.is_applicable(1) is True
    assert res.is_applicable("dfmea") is True
    assert res.is_applicable("aar") is False
    assert res.is_applicable("2.2.13") is False
    assert res.is_applicable(13) is False
    assert res.is_applicable("nonexistent") is False
    assert res.is_applicable(999) is False


def test_applicability_result_to_dict_serialization() -> None:
    res = assess_applicability(
        submission_level=3,
        has_design_responsibility=True,
        appearance_item=False,
        has_checking_aid=False,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    d = res.to_dict()

    assert d["package_verdict"] == "APPLICABLE"
    assert d["submission_level"] == 3
    assert d["reason_for_submission"] == "Initial Submission"
    assert isinstance(d["elements"], dict)
    assert len(d["elements"]) == 18
    assert d["elements"]["2.2.1"]["verdict"] == "APPLICABLE"
    assert isinstance(d["applicable_elements"], list)
    assert isinstance(d["not_applicable_elements"], list)
    assert isinstance(d["indeterminate_elements"], list)
    assert d["standards_basis"] == "AIAG PPAP 4th Edition (June 2006)"
    assert d["scope_boundary_notes"] == []


# ==============================================================================
# 3. Helper Functions & Normalization Tests
# ==============================================================================


def test_to_element_id_helper() -> None:
    assert _to_element_id(1) == "2.2.1"
    assert _to_element_id(18) == "2.2.18"
    assert _to_element_id(0) is None
    assert _to_element_id(19) is None

    assert _to_element_id("2.2.1") == "2.2.1"
    assert _to_element_id("2.2.18") == "2.2.18"
    assert _to_element_id("  DFMEA  ") == "2.2.4"
    assert _to_element_id("psw") == "2.2.18"
    assert _to_element_id("unknown") is None
    assert _to_element_id(None) is None
    assert _to_element_id([]) is None


def test_normalize_level_helper() -> None:
    for lvl in SUBMISSION_LEVELS:
        assert _normalize_level(lvl) == lvl

    assert _normalize_level("Level 1") == 1
    assert _normalize_level("l2") == 2
    assert _normalize_level("  Level 3  ") == 3
    assert _normalize_level("4") == 4
    assert _normalize_level("level_5") == 5

    with pytest.raises(ValueError, match="Invalid submission_level: 0"):
        _normalize_level(0)

    with pytest.raises(ValueError, match="Invalid submission_level: 6"):
        _normalize_level(6)

    with pytest.raises(ValueError, match="Invalid submission_level: 'Level 6'"):
        _normalize_level("Level 6")

    with pytest.raises(TypeError, match="submission_level must be an int"):
        _normalize_level(True)

    with pytest.raises(TypeError, match="submission_level must be an int"):
        _normalize_level(None)

    with pytest.raises(TypeError, match="submission_level must be an int"):
        _normalize_level(3.14)


def test_normalize_reason_helper() -> None:
    for reason in REASON_FOR_SUBMISSION_VALUES:
        assert _normalize_reason(reason) == reason

    assert _normalize_reason("initial") == "Initial Submission"
    assert _normalize_reason("  ecn  ") == "Engineering Change(s)"
    assert _normalize_reason("material change") == "Change to Optional Construction or Material"
    assert _normalize_reason("process change") == "Change in Part Processing"
    assert _normalize_reason("discrepancy") == "Correction of Discrepancy"

    with pytest.raises(ValueError, match="Invalid reason_for_submission"):
        _normalize_reason("invalid reason")

    with pytest.raises(TypeError, match="reason_for_submission must be a str"):
        _normalize_reason(123)

    with pytest.raises(TypeError, match="reason_for_submission must be a str"):
        _normalize_reason(None)


def test_validate_bool_or_none_helper() -> None:
    assert _validate_bool_or_none("test_flag", None) is None
    assert _validate_bool_or_none("test_flag", True) is True
    assert _validate_bool_or_none("test_flag", False) is False

    with pytest.raises(TypeError, match="test_flag must be a bool or None"):
        _validate_bool_or_none("test_flag", 1)

    with pytest.raises(TypeError, match="test_flag must be a bool or None"):
        _validate_bool_or_none("test_flag", "true")

    with pytest.raises(TypeError, match="test_flag must be a bool or None"):
        _validate_bool_or_none("test_flag", [])


# ==============================================================================
# 4. Standard Discrete-Part Applicability Evaluation (Levels 1, 2, 3, 5)
# ==============================================================================


def test_assess_applicability_default_invocation_un_surveyed_indeterminate() -> None:
    """When no conditional flags are supplied, all 5 conditionals evaluate to INDETERMINATE."""
    res = assess_applicability()
    assert res.package_verdict == "INDETERMINATE"
    assert res.submission_level == 3
    assert res.reason_for_submission == "Initial Submission"
    assert len(res.elements) == 18

    # 13 unconditional elements must be APPLICABLE
    unconditional_ids = [
        "2.2.1", "2.2.2", "2.2.5", "2.2.6", "2.2.7", "2.2.8",
        "2.2.9", "2.2.10", "2.2.11", "2.2.12", "2.2.14", "2.2.17", "2.2.18",
    ]
    for elem_id in unconditional_ids:
        elem = res.elements[elem_id]
        assert elem.verdict == "APPLICABLE"
        assert elem.is_conditional is False
        assert elem.condition_met is None

    # Check un-surveyed status on 5 conditional elements
    for cond_id in CONDITIONAL_ELEMENTS:
        elem = res.elements[cond_id]
        assert elem.verdict == "INDETERMINATE"
        assert elem.condition_met is None
        assert "Un-surveyed:" in elem.rationale

    assert len(res.applicable_elements) == 13
    assert len(res.not_applicable_elements) == 0
    assert len(res.indeterminate_elements) == 5


def test_assess_applicability_all_conditional_flags_true() -> None:
    res = assess_applicability(
        submission_level=3,
        has_design_responsibility=True,
        appearance_item=True,
        has_checking_aid=True,
        customer_engineering_approval_required=True,
        master_sample_waived=False,
    )
    assert res.package_verdict == "APPLICABLE"
    assert len(res.applicable_elements) == 18
    assert len(res.not_applicable_elements) == 0
    assert len(res.indeterminate_elements) == 0
    for elem_id in PPAP_ELEMENT_IDS:
        elem = res.elements[elem_id]
        assert elem.verdict == "APPLICABLE"
        if elem.is_conditional:
            assert elem.condition_met is True


def test_assess_applicability_all_conditional_flags_false_or_waived() -> None:
    res = assess_applicability(
        submission_level=3,
        has_design_responsibility=False,
        appearance_item=False,
        has_checking_aid=False,
        customer_engineering_approval_required=False,
        master_sample_waived=True,
    )
    assert res.package_verdict == "APPLICABLE"
    assert len(res.applicable_elements) == 13
    assert len(res.not_applicable_elements) == 5
    assert set(res.not_applicable_elements) == set(CONDITIONAL_ELEMENTS)
    for elem_id in CONDITIONAL_ELEMENTS:
        elem = res.elements[elem_id]
        assert elem.verdict == "NOT_APPLICABLE"
        assert elem.condition_met is False


# ==============================================================================
# 5. Conditional Element Rules (§2.2.3, §2.2.4, §2.2.13, §2.2.15, §2.2.16)
# ==============================================================================


def test_rule_section_2_2_3_customer_engineering_approval() -> None:
    # customer_engineering_approval_required is True -> APPLICABLE
    res_true = assess_applicability(customer_engineering_approval_required=True)
    e_true = res_true.elements["2.2.3"]
    assert e_true.verdict == "APPLICABLE"
    assert e_true.condition_met is True
    assert "Customer engineering approval is required" in e_true.rationale
    assert e_true.standard_reference == "AIAG PPAP 4th Edition §2.2.3"

    # customer_engineering_approval_required is False -> NOT_APPLICABLE
    res_false = assess_applicability(customer_engineering_approval_required=False)
    e_false = res_false.elements["2.2.3"]
    assert e_false.verdict == "NOT_APPLICABLE"
    assert e_false.condition_met is False
    assert "Customer engineering approval is not required" in e_false.rationale

    # customer_engineering_approval_required is None -> INDETERMINATE
    res_none = assess_applicability(customer_engineering_approval_required=None)
    e_none = res_none.elements["2.2.3"]
    assert e_none.verdict == "INDETERMINATE"
    assert e_none.condition_met is None
    assert "Un-surveyed: customer engineering approval requirement not specified" in e_none.rationale


def test_rule_section_2_2_4_design_fmea() -> None:
    # has_design_responsibility is True -> APPLICABLE
    res_true = assess_applicability(has_design_responsibility=True)
    e_true = res_true.elements["2.2.4"]
    assert e_true.verdict == "APPLICABLE"
    assert e_true.condition_met is True
    assert "Organization is design-responsible" in e_true.rationale
    assert e_true.standard_reference == "AIAG PPAP 4th Edition §2.2.4"

    # has_design_responsibility is False -> NOT_APPLICABLE
    res_false = assess_applicability(has_design_responsibility=False)
    e_false = res_false.elements["2.2.4"]
    assert e_false.verdict == "NOT_APPLICABLE"
    assert e_false.condition_met is False
    assert "Organization is not design-responsible" in e_false.rationale

    # has_design_responsibility is None -> INDETERMINATE
    res_none = assess_applicability(has_design_responsibility=None)
    e_none = res_none.elements["2.2.4"]
    assert e_none.verdict == "INDETERMINATE"
    assert e_none.condition_met is None
    assert "Un-surveyed: design responsibility not specified" in e_none.rationale


def test_rule_section_2_2_13_appearance_approval_report() -> None:
    # appearance_item is True -> APPLICABLE
    res_true = assess_applicability(appearance_item=True)
    e_true = res_true.elements["2.2.13"]
    assert e_true.verdict == "APPLICABLE"
    assert e_true.condition_met is True
    assert "Part has appearance requirements on the design record" in e_true.rationale
    assert e_true.standard_reference == "AIAG PPAP 4th Edition §2.2.13"

    # appearance_item is False -> NOT_APPLICABLE
    res_false = assess_applicability(appearance_item=False)
    e_false = res_false.elements["2.2.13"]
    assert e_false.verdict == "NOT_APPLICABLE"
    assert e_false.condition_met is False
    assert "Part does not have appearance requirements" in e_false.rationale

    # appearance_item is None -> INDETERMINATE
    res_none = assess_applicability(appearance_item=None)
    e_none = res_none.elements["2.2.13"]
    assert e_none.verdict == "INDETERMINATE"
    assert e_none.condition_met is None
    assert "Un-surveyed: appearance requirement designation on design record not specified" in e_none.rationale


def test_rule_section_2_2_15_master_sample() -> None:
    # master_sample_waived is False -> APPLICABLE (default requirement)
    res_default = assess_applicability(master_sample_waived=False)
    e_def = res_default.elements["2.2.15"]
    assert e_def.verdict == "APPLICABLE"
    assert e_def.condition_met is True
    assert "Master sample retention is required by default" in e_def.rationale
    assert e_def.standard_reference == "AIAG PPAP 4th Edition §2.2.15"

    # master_sample_waived is True -> NOT_APPLICABLE (documented customer waiver)
    res_waived = assess_applicability(master_sample_waived=True)
    e_waived = res_waived.elements["2.2.15"]
    assert e_waived.verdict == "NOT_APPLICABLE"
    assert e_waived.condition_met is False
    assert "Master sample is waived by documented customer agreement" in e_waived.rationale

    # master_sample_waived is None -> INDETERMINATE
    res_none = assess_applicability(master_sample_waived=None)
    e_none = res_none.elements["2.2.15"]
    assert e_none.verdict == "INDETERMINATE"
    assert e_none.condition_met is None
    assert "Un-surveyed: master sample customer waiver status not specified" in e_none.rationale


def test_rule_section_2_2_16_checking_aids() -> None:
    # has_checking_aid is True -> APPLICABLE
    res_true = assess_applicability(has_checking_aid=True)
    e_true = res_true.elements["2.2.16"]
    assert e_true.verdict == "APPLICABLE"
    assert e_true.condition_met is True
    assert "Part-specific assembly or component checking aid exists" in e_true.rationale
    assert e_true.standard_reference == "AIAG PPAP 4th Edition §2.2.16"

    # has_checking_aid is False -> NOT_APPLICABLE
    res_false = assess_applicability(has_checking_aid=False)
    e_false = res_false.elements["2.2.16"]
    assert e_false.verdict == "NOT_APPLICABLE"
    assert e_false.condition_met is False
    assert "No part-specific checking aid exists" in e_false.rationale

    # has_checking_aid is None -> INDETERMINATE
    res_none = assess_applicability(has_checking_aid=None)
    e_none = res_none.elements["2.2.16"]
    assert e_none.verdict == "INDETERMINATE"
    assert e_none.condition_met is None
    assert "Un-surveyed: checking aid existence not specified" in e_none.rationale


# ==============================================================================
# 6. Submission Level 4 Indeterminacy Gate & Explicit Requirements
# ==============================================================================


def test_submission_level_4_negative_control_indeterminate_when_no_requirements() -> None:
    """Negative Control: Level 4 with customer_level_4_requirements=None must resolve INDETERMINATE."""
    res = assess_applicability(submission_level=4, customer_level_4_requirements=None)
    assert res.package_verdict == "INDETERMINATE"
    assert res.submission_level == 4
    assert len(res.indeterminate_elements) == 18
    assert res.applicable_elements == []
    assert res.not_applicable_elements == []

    for elem_id in PPAP_ELEMENT_IDS:
        elem = res.elements[elem_id]
        assert elem.verdict == "INDETERMINATE"
        assert "Submission Level 4 requires customer-defined requirements" in elem.rationale
        assert elem.standard_reference == "AIAG PPAP 4th Edition Section 4 & Table 4.1"
        assert elem.condition_met is None


def test_submission_level_4_with_list_or_set_requirements() -> None:
    reqs_list = ["2.2.1", "2.2.7", "psw", 4, "invalid_item"]
    res = assess_applicability(submission_level="Level 4", customer_level_4_requirements=reqs_list)
    assert res.package_verdict == "APPLICABLE"
    assert set(res.applicable_elements) == {"2.2.1", "2.2.4", "2.2.7", "2.2.18"}
    assert len(res.not_applicable_elements) == 14
    assert res.indeterminate_elements == []

    # Check conditional element in list has condition_met=True
    assert res.elements["2.2.4"].condition_met is True
    # Check conditional element not in list has condition_met=False
    assert res.elements["2.2.13"].condition_met is False

    # Check set and tuple inputs
    reqs_set = {"2.2.18"}
    res_set = assess_applicability(submission_level=4, customer_level_4_requirements=reqs_set)
    assert res_set.applicable_elements == ["2.2.18"]

    reqs_tuple = ("2.2.1", "2.2.18")
    res_tuple = assess_applicability(submission_level=4, customer_level_4_requirements=reqs_tuple)
    assert set(res_tuple.applicable_elements) == {"2.2.1", "2.2.18"}


def test_submission_level_4_with_dict_requirements_all_verdict_branches() -> None:
    reqs_dict: dict[Any, Any] = {
        # Boolean True / String truthy aliases
        "2.2.1": True,
        "2.2.2": "APPLICABLE",
        "2.2.3": "S",
        "2.2.4": "R",
        "2.2.5": "*",
        "2.2.6": "SUBMIT",
        "2.2.7": "RETAIN",
        "2.2.8": "TRUE",
        "2.2.9": "Y",
        "2.2.10": "YES",
        # Boolean False / String falsy aliases
        "2.2.11": False,
        "2.2.12": "NOT_APPLICABLE",
        "2.2.13": "NA",
        "2.2.14": "N/A",
        "2.2.15": "WAIVED",
        "2.2.16": "EXEMPT",
        "2.2.17": "FALSE",
        "2.2.18": "N",
        # Unknown element key (should be ignored safely)
        "99.99": True,
    }
    res = assess_applicability(submission_level=4, customer_level_4_requirements=reqs_dict)
    assert res.package_verdict == "APPLICABLE"
    assert res.applicable_elements == [
        "2.2.1", "2.2.2", "2.2.3", "2.2.4", "2.2.5", "2.2.6", "2.2.7", "2.2.8", "2.2.9", "2.2.10"
    ]
    assert res.not_applicable_elements == [
        "2.2.11", "2.2.12", "2.2.13", "2.2.14", "2.2.15", "2.2.16", "2.2.17", "2.2.18"
    ]
    assert res.indeterminate_elements == []


def test_submission_level_4_with_dict_requirements_indeterminate_branches_and_fallbacks() -> None:
    # Test indeterminate aliases and None
    reqs_dict: dict[Any, Any] = {
        "2.2.1": None,
        "2.2.2": "INDETERMINATE",
        "2.2.3": "UNDECIDED",
        "2.2.4": "?",
        "2.2.5": "UNKNOWN",
        "2.2.6": "NO",             # Test "NO" branch -> NOT_APPLICABLE
        "2.2.7": "CUSTOM_REQUIRED", # Test fallback truthy branch -> APPLICABLE
        # Elements 2.2.8–2.2.18 are omitted from dict -> NOT_APPLICABLE
    }
    res = assess_applicability(submission_level=4, customer_level_4_requirements=reqs_dict)
    assert res.package_verdict == "INDETERMINATE"  # Because indeterminate elements exist
    assert res.indeterminate_elements == ["2.2.1", "2.2.2", "2.2.3", "2.2.4", "2.2.5"]
    assert res.elements["2.2.6"].verdict == "NOT_APPLICABLE"
    assert res.elements["2.2.7"].verdict == "APPLICABLE"
    assert res.elements["2.2.8"].verdict == "NOT_APPLICABLE"
    assert "Element not specified in customer Level 4 requirements." in res.elements["2.2.8"].rationale


def test_submission_level_4_invalid_requirements_type_raises_type_error() -> None:
    with pytest.raises(TypeError, match="customer_level_4_requirements must be a set, list, dict, or None"):
        assess_applicability(submission_level=4, customer_level_4_requirements=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="customer_level_4_requirements must be a set, list, dict, or None"):
        assess_applicability(submission_level=4, customer_level_4_requirements="2.2.1")  # type: ignore[arg-type]


# ==============================================================================
# 7. Commodity Scope Boundaries (Appendices F, G, H)
# ==============================================================================


def test_scope_boundary_bulk_materials_via_flag_and_aliases() -> None:
    # Explicit flag
    res_flag = assess_applicability(is_bulk_material=True)
    assert res_flag.package_verdict == "INDETERMINATE"
    assert len(res_flag.indeterminate_elements) == 18
    assert any("Bulk materials per AIAG PPAP 4th Edition Appendix F" in n for n in res_flag.scope_boundary_notes)

    # Commodity aliases
    bulk_aliases = [
        "bulk", "bulk_material", "bulk material", "bulk materials",
        "chemicals", "chemical", "resin", "resins", "polymer", "polymers",
        "lubricant", "lubricants", "coating", "coatings", "paint", "fluid", "fluids"
    ]
    for alias in bulk_aliases:
        res = assess_applicability(commodity_type=alias)
        assert res.package_verdict == "INDETERMINATE"
        assert len(res.indeterminate_elements) == 18
        assert any("Bulk materials" in n for n in res.scope_boundary_notes)


def test_scope_boundary_tires_via_flag_and_aliases() -> None:
    # Explicit flag
    res_flag = assess_applicability(is_tire=True)
    assert res_flag.package_verdict == "INDETERMINATE"
    assert len(res_flag.indeterminate_elements) == 18
    assert any("Tire industry submissions per AIAG PPAP 4th Edition Appendix G" in n for n in res_flag.scope_boundary_notes)

    # Commodity aliases
    tire_aliases = ["tire", "tires", "tyre", "tyres"]
    for alias in tire_aliases:
        res = assess_applicability(commodity_type=alias)
        assert res.package_verdict == "INDETERMINATE"
        assert len(res.indeterminate_elements) == 18
        assert any("Tire industry" in n for n in res.scope_boundary_notes)


def test_scope_boundary_truck_industry_via_flag_and_aliases() -> None:
    # Explicit flag
    res_flag = assess_applicability(is_truck_industry=True)
    assert res_flag.package_verdict == "INDETERMINATE"
    assert len(res_flag.indeterminate_elements) == 18
    assert any("Truck industry submissions per AIAG PPAP 4th Edition Appendix H" in n for n in res_flag.scope_boundary_notes)

    # Commodity aliases
    truck_aliases = [
        "truck", "trucks", "heavy truck", "heavy trucks",
        "truck_industry", "truck industry", "commercial vehicle", "commercial vehicles"
    ]
    for alias in truck_aliases:
        res = assess_applicability(commodity_type=alias)
        assert res.package_verdict == "INDETERMINATE"
        assert len(res.indeterminate_elements) == 18
        assert any("Truck industry" in n for n in res.scope_boundary_notes)


def test_scope_boundary_combinations_and_in_scope_commodities() -> None:
    # Multi-boundary combination
    res_multi = assess_applicability(is_bulk_material=True, is_tire=True, is_truck_industry=True)
    assert res_multi.package_verdict == "INDETERMINATE"
    assert len(res_multi.scope_boundary_notes) == 3

    # In-scope standard discrete commodities
    in_scope_commodities = ["machined_bracket", "sheet_metal_stamping", "injection_molded_clip", "fastener"]
    for comm in in_scope_commodities:
        res = assess_applicability(
            commodity_type=comm,
            has_design_responsibility=True,
            appearance_item=False,
            has_checking_aid=False,
            customer_engineering_approval_required=False,
            master_sample_waived=False,
        )
        assert res.package_verdict == "APPLICABLE"
        assert res.scope_boundary_notes == []

    # Invalid commodity_type type
    with pytest.raises(TypeError, match="commodity_type must be a str"):
        assess_applicability(commodity_type=123)  # type: ignore[arg-type]


# ==============================================================================
# 8. Reason for Submission Non-Narrowing (RULE 4 & All 10 Reasons)
# ==============================================================================


@pytest.mark.parametrize("reason", REASON_FOR_SUBMISSION_VALUES)
def test_reason_for_submission_all_10_triggers_evaluated_consistently(reason: str) -> None:
    res = assess_applicability(
        submission_level=3,
        reason_for_submission=reason,
        has_design_responsibility=True,
        appearance_item=False,
        has_checking_aid=False,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    assert res.package_verdict == "APPLICABLE"
    assert res.reason_for_submission == reason
    assert len(res.elements) == 18
    # All 13 unconditional elements remain applicable regardless of submission reason
    for elem_id in ["2.2.1", "2.2.2", "2.2.5", "2.2.6", "2.2.7", "2.2.8", "2.2.18"]:
        assert res.elements[elem_id].verdict == "APPLICABLE"


# ==============================================================================
# 9. Input Types & Trust Boundary Integration
# ==============================================================================


def test_assess_applicability_with_ppap_package_instance() -> None:
    pkg = PPAPPackage(
        part_name="Transmission Bracket",
        part_number="TB-4400-A",
        submission_level=2,
        reason_for_submission="Engineering Change(s)",
        has_design_responsibility=False,
        appearance_item=True,
        has_checking_aid=True,
    )
    res = assess_applicability(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    assert res.submission_level == 2
    assert res.reason_for_submission == "Engineering Change(s)"
    assert res.elements["2.2.4"].verdict == "NOT_APPLICABLE"  # has_design_responsibility=False
    assert res.elements["2.2.13"].verdict == "APPLICABLE"     # appearance_item=True
    assert res.elements["2.2.16"].verdict == "APPLICABLE"     # has_checking_aid=True
    assert res.elements["2.2.3"].verdict == "NOT_APPLICABLE"
    assert res.elements["2.2.15"].verdict == "APPLICABLE"
    assert res.package_verdict == "APPLICABLE"

    # Level 4 with customer_requirement_set on PPAPPackage
    pkg_l4 = PPAPPackage(
        part_name="Sensor Bracket",
        part_number="SB-01",
        submission_level=4,
        customer_requirement_set={"2.2.1", "2.2.18"},
    )
    res_l4 = assess_applicability(pkg_l4)
    assert res_l4.submission_level == 4
    assert res_l4.package_verdict == "APPLICABLE"
    assert set(res_l4.applicable_elements) == {"2.2.1", "2.2.18"}

    # Keyword overrides take precedence over package attributes
    res_override = assess_applicability(pkg, has_design_responsibility=True, submission_level=5)
    assert res_override.submission_level == 5
    assert res_override.elements["2.2.4"].verdict == "APPLICABLE"


def test_assess_applicability_with_dict_payload() -> None:
    payload = {
        "submission_level": 3,
        "reason_for_submission": "Correction of Discrepancy",
        "has_design_responsibility": True,
        "appearance_item": False,
        "has_checking_aid": False,
        "customer_engineering_approval_required": True,
        "master_sample_waived": True,
        "customer_level_4_requirements": None,
        "is_bulk_material": False,
        "is_tire": False,
        "is_truck_industry": False,
        "commodity_type": "machined_pin",
    }
    res = assess_applicability(payload)
    assert res.submission_level == 3
    assert res.reason_for_submission == "Correction of Discrepancy"
    assert res.elements["2.2.3"].verdict == "APPLICABLE"      # customer_engineering_approval_required=True
    assert res.elements["2.2.15"].verdict == "NOT_APPLICABLE" # master_sample_waived=True
    assert res.package_verdict == "APPLICABLE"

    # Test dict with scope flags
    payload_bulk = {"is_bulk_material": True}
    res_bulk = assess_applicability(payload_bulk)
    assert res_bulk.package_verdict == "INDETERMINATE"

    payload_tire = {"is_tire": True}
    res_tire = assess_applicability(payload_tire)
    assert res_tire.package_verdict == "INDETERMINATE"

    payload_truck = {"is_truck_industry": True}
    res_truck = assess_applicability(payload_truck)
    assert res_truck.package_verdict == "INDETERMINATE"

    payload_comm = {"commodity_type": "resin"}
    res_comm = assess_applicability(payload_comm)
    assert res_comm.package_verdict == "INDETERMINATE"


def test_assess_applicability_invalid_package_type_raises_type_error() -> None:
    with pytest.raises(TypeError, match="package_or_data must be a PPAPPackage, dict, or None"):
        assess_applicability("invalid string")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="package_or_data must be a PPAPPackage, dict, or None"):
        assess_applicability([1, 2, 3])  # type: ignore[arg-type]


# ==============================================================================
# 10. Unknown Element Fallback & Coverage Corner Cases
# ==============================================================================


def test_unknown_element_in_discrete_evaluation_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover the defensive fallback branch for unrecognized element IDs."""
    import quality_core.ppap.applicability as app_mod

    monkeypatch.setattr(app_mod, "PPAP_ELEMENT_IDS", ("2.2.1", "2.2.99"))
    # PPAP_ELEMENT_NAMES is a MappingProxyType (immutable by RULE 1), so rebind the
    # module-level name to an augmented copy rather than mutating the proxy in place.
    monkeypatch.setattr(
        app_mod,
        "PPAP_ELEMENT_NAMES",
        {**PPAP_ELEMENT_NAMES, "2.2.99": "Synthetic Unknown Element"},
    )

    res = assess_applicability(
        submission_level=3,
        has_design_responsibility=True,
        appearance_item=False,
        has_checking_aid=False,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    assert "2.2.99" in res.elements
    assert res.elements["2.2.99"].verdict == "INDETERMINATE"
    assert "Unknown element: 2.2.99" in res.elements["2.2.99"].rationale
    assert res.package_verdict == "INDETERMINATE"
    assert "2.2.99" in res.indeterminate_elements


# ==============================================================================
# 11. Citations & Assumptions Log Integrity
# ==============================================================================


def test_ppap_citations_manifest_exists_and_matches_assumptions_log() -> None:
    ppap_dir = Path(__file__).resolve().parents[1] / "src" / "quality_core" / "ppap"
    manifest_path = ppap_dir / "CITATIONS.tsv"
    log_path = ppap_dir / "ASSUMPTIONS_LOG.md"

    assert manifest_path.exists(), f"CITATIONS.tsv not found at {manifest_path}"
    assert log_path.exists(), f"ASSUMPTIONS_LOG.md not found at {log_path}"

    with manifest_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    assert len(rows) >= 30
    sites = {r["site"] for r in rows}
    assert "RULE 1" in sites
    assert "RULE 2" in sites
    assert "RULE 3" in sites
    assert "RULE 4" in sites
    assert "RULE 5" in sites
    assert "RULE 6" in sites
    assert "RULE 7" in sites

    log_content = log_path.read_text(encoding="utf-8")
    assert "## RULE 4: Conditional Element Applicability" in log_content
    assert "## RULE 5: Submission Level 4 Indeterminacy Gate" in log_content
    assert "## RULE 6: Scope Boundaries for Non-Discrete Commodities" in log_content
    assert "## RULE 7: Reason for Submission Non-Narrowing" in log_content

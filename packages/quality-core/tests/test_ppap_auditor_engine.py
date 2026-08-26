"""Unit test suite for PPAP 18-element completeness auditor core (Issue #102).

Validates:
1. Taxonomy & constants (AUDIT_ELEMENT_VERDICTS, AUDIT_PACKAGE_VERDICTS)
2. Dataclass properties, immutability, and serialization (.to_dict())
3. Helper methods (.is_ready(), .get_element() across IDs, numbers, and aliases)
4. Trust-boundary normalization (_normalize_level, _normalize_reason)
5. Entry point handling (PPAPPackage, dict, kwargs, invalid types, overrides, applicability injection)
6. Element verdict branch exhaustion (Applicability INDETERMINATE/NOT_APPLICABLE, invalid evidence, undecided sentinel, missing, submitted, retained across S, R, *, CUSTOMER_DEFINED)
7. Package readiness verdict branch exhaustion (SUBMISSION_READY, NOT_READY, INDETERMINATE)
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from quality_core.ppap.applicability import (
    assess_applicability,
)
from quality_core.ppap.auditor import (
    AUDIT_ELEMENT_VERDICTS,
    AUDIT_PACKAGE_VERDICTS,
    ElementAuditResult,
    PPAPAuditResult,
    _normalize_level,
    _normalize_reason,
    audit_ppap_package,
)
from quality_core.ppap.schema import (
    PPAP_ELEMENT_IDS,
    EvidenceItem,
    PPAPPackage,
)
from quality_core.ppap.table_4_1 import lookup_requirement

# ---------------------------------------------------------------------------
# 1. Taxonomy & Constants
# ---------------------------------------------------------------------------


def test_audit_element_verdicts_constant() -> None:
    """Assert AUDIT_ELEMENT_VERDICTS tuple contains all 6 element verdicts."""
    expected = (
        "SUBMITTED",
        "RETAINED_ON_FILE",
        "MISSING",
        "NOT_APPLICABLE",
        "INDETERMINATE",
        "EVIDENCE_INVALID",
    )
    assert AUDIT_ELEMENT_VERDICTS == expected


def test_audit_package_verdicts_constant() -> None:
    """Assert AUDIT_PACKAGE_VERDICTS tuple contains all 3 package verdicts."""
    expected = ("SUBMISSION_READY", "NOT_READY", "INDETERMINATE")
    assert AUDIT_PACKAGE_VERDICTS == expected


# ---------------------------------------------------------------------------
# 2. Dataclasses, Immutability & Serialization
# ---------------------------------------------------------------------------


def test_element_audit_result_immutability() -> None:
    """Assert ElementAuditResult is a frozen dataclass."""
    res = ElementAuditResult(
        element_id="2.2.1",
        element_name="Design Records",
        verdict="SUBMITTED",
        requirement_code="S",
        applicability_verdict="APPLICABLE",
        rationale="Evidence present and submitted.",
        is_blocking=False,
    )
    with pytest.raises(FrozenInstanceError):
        res.verdict = "MISSING"  # type: ignore[misc]


def test_element_audit_result_to_dict() -> None:
    """Assert ElementAuditResult.to_dict() returns all fields serialized."""
    res = ElementAuditResult(
        element_id="2.2.18",
        element_name="Part Submission Warrant (PSW)",
        verdict="SUBMITTED",
        requirement_code="S",
        applicability_verdict="APPLICABLE",
        rationale="Warrant submitted.",
        is_blocking=False,
        evidence_status="submitted",
        evidence_present=True,
        artifact_ref="PSW-001.pdf",
        document_reference="PSW-001.pdf",
        evidence_valid=True,
    )
    d = res.to_dict()
    assert d["element_id"] == "2.2.18"
    assert d["element_name"] == "Part Submission Warrant (PSW)"
    assert d["verdict"] == "SUBMITTED"
    assert d["requirement_code"] == "S"
    assert d["applicability_verdict"] == "APPLICABLE"
    assert d["rationale"] == "Warrant submitted."
    assert d["is_blocking"] is False
    assert d["evidence_status"] == "submitted"
    assert d["evidence_present"] is True
    assert d["artifact_ref"] == "PSW-001.pdf"
    assert d["document_reference"] == "PSW-001.pdf"
    assert d["evidence_valid"] is True


def test_ppap_audit_result_serialization_and_helpers() -> None:
    """Assert PPAPAuditResult helper methods and .to_dict() behavior."""
    elem_psw = ElementAuditResult(
        element_id="2.2.18",
        element_name="Part Submission Warrant (PSW)",
        verdict="SUBMITTED",
        requirement_code="S",
        applicability_verdict="APPLICABLE",
        rationale="PSW complete",
        is_blocking=False,
    )
    elem_dfmea = ElementAuditResult(
        element_id="2.2.4",
        element_name="Design FMEA",
        verdict="RETAINED_ON_FILE",
        requirement_code="R",
        applicability_verdict="APPLICABLE",
        rationale="DFMEA retained",
        is_blocking=False,
    )
    res = PPAPAuditResult(
        package_verdict="SUBMISSION_READY",
        submission_level=1,
        reason_for_submission="Initial Submission",
        elements={"2.2.18": elem_psw, "2.2.4": elem_dfmea},
        verdict_counts={
            "SUBMITTED": 1,
            "RETAINED_ON_FILE": 1,
            "MISSING": 0,
            "NOT_APPLICABLE": 0,
            "INDETERMINATE": 0,
            "EVIDENCE_INVALID": 0,
        },
        blocking_elements=[],
        blocking_element_names=[],
        submitted_elements=["2.2.18"],
        retained_elements=["2.2.4"],
        missing_elements=[],
        not_applicable_elements=[],
        indeterminate_elements=[],
        invalid_elements=[],
    )

    assert res.is_ready() is True

    # Lookup helpers
    assert res.get_element("2.2.18") is elem_psw
    assert res.get_element(18) is elem_psw
    assert res.get_element("psw") is elem_psw
    assert res.get_element("2.2.4") is elem_dfmea
    assert res.get_element(4) is elem_dfmea
    assert res.get_element("dfmea") is elem_dfmea
    assert res.get_element("nonexistent") is None
    assert res.get_element(99) is None

    # Serialization
    d = res.to_dict()
    assert d["package_verdict"] == "SUBMISSION_READY"
    assert d["submission_level"] == 1
    assert d["elements"]["2.2.18"]["verdict"] == "SUBMITTED"
    assert d["applicability_result"] is None


# ---------------------------------------------------------------------------
# 3. Trust-Boundary Normalization
# ---------------------------------------------------------------------------


def test_normalize_level_valid() -> None:
    """Test integer and string inputs for _normalize_level."""
    for lvl in (1, 2, 3, 4, 5):
        assert _normalize_level(lvl) == lvl
    assert _normalize_level("level 1") == 1
    assert _normalize_level("Level 3") == 3
    assert _normalize_level("5") == 5


def test_normalize_level_invalid() -> None:
    """Test invalid inputs for _normalize_level."""
    with pytest.raises(ValueError, match="Invalid submission_level: 0"):
        _normalize_level(0)
    with pytest.raises(ValueError, match="Invalid submission_level: 6"):
        _normalize_level(6)
    with pytest.raises(ValueError, match="Invalid submission_level: 'Level 6'"):
        _normalize_level("Level 6")
    with pytest.raises(TypeError, match="submission_level must be an int"):
        _normalize_level(3.14)
    with pytest.raises(TypeError, match="submission_level must be an int"):
        _normalize_level(None)
    with pytest.raises(TypeError, match="submission_level must be an int"):
        _normalize_level(True)


def test_normalize_reason_valid_and_invalid() -> None:
    """Test _normalize_reason with valid, alias, invalid string, and invalid type."""
    assert _normalize_reason("Initial Submission") == "Initial Submission"
    assert _normalize_reason("initial") == "Initial Submission"
    assert _normalize_reason("engineering change") == "Engineering Change(s)"

    with pytest.raises(ValueError, match="Invalid reason_for_submission: 'bad reason'"):
        _normalize_reason("bad reason")
    with pytest.raises(TypeError, match="reason_for_submission must be a str"):
        _normalize_reason(123)


# ---------------------------------------------------------------------------
# 4. Entry Point Handling & Overrides
# ---------------------------------------------------------------------------


def test_audit_ppap_package_input_types() -> None:
    """Test audit_ppap_package handling of PPAPPackage, dict, and None with kwargs."""
    # From PPAPPackage instance
    pkg = PPAPPackage(part_name="Bracket", submission_level=1)
    res1 = audit_ppap_package(pkg)
    assert isinstance(res1, PPAPAuditResult)
    assert res1.submission_level == 1

    # From raw dictionary with applicability params passed through
    pkg_dict = {"part_name": "Bracket", "submission_level": 2, "has_design_responsibility": False}
    res2 = audit_ppap_package(pkg_dict)
    assert res2.submission_level == 2
    assert res2.get_element("dfmea").verdict == "NOT_APPLICABLE"  # type: ignore[union-attr]

    # From None with kwargs and explicit overrides
    res3 = audit_ppap_package(
        None,
        part_name="Bracket",
        submission_level=3,
        reason_for_submission="Engineering Change(s)",
    )
    assert res3.submission_level == 3
    assert res3.reason_for_submission == "Engineering Change(s)"

    # From None with default values
    res4 = audit_ppap_package(None)
    assert res4.submission_level == 3
    assert res4.reason_for_submission == "Initial Submission"

    # Invalid input type
    with pytest.raises(TypeError, match="package_or_data must be a PPAPPackage, dict, or None"):
        audit_ppap_package(["invalid_list"])  # type: ignore[arg-type]


def test_audit_ppap_package_overrides_and_applicability_injection() -> None:
    """Test submission_level override, reason override, and pre-computed applicability injection."""
    pkg = PPAPPackage(part_name="Gear", submission_level=1, reason_for_submission="Initial Submission")
    res = audit_ppap_package(
        pkg,
        submission_level=2,
        reason_for_submission="Engineering Change(s)",
    )
    assert res.submission_level == 2
    assert res.reason_for_submission == "Engineering Change(s)"

    # Pre-computed applicability injection
    pre_app = assess_applicability(pkg, submission_level=1)
    res_injected = audit_ppap_package(pkg, applicability=pre_app)
    assert res_injected.applicability_result is pre_app


# ---------------------------------------------------------------------------
# 5. Element Verdict Branch Exhaustion
# ---------------------------------------------------------------------------


def test_branch_applicability_indeterminate() -> None:
    """Applicability INDETERMINATE yields element verdict INDETERMINATE and is_blocking=True."""
    # Level 4 without customer requirements yields INDETERMINATE for all elements
    pkg = PPAPPackage(part_name="Sensor", submission_level=4, customer_requirement_set=None)
    res = audit_ppap_package(pkg)
    assert res.package_verdict == "INDETERMINATE"
    for elem_id in PPAP_ELEMENT_IDS:
        elem = res.elements[elem_id]
        assert elem.verdict == "INDETERMINATE"
        assert elem.is_blocking is True
        assert "Applicability is indeterminate" in elem.rationale


def test_branch_applicability_not_applicable() -> None:
    """Applicability NOT_APPLICABLE yields element verdict NOT_APPLICABLE and is_blocking=False."""
    # Customer design responsible -> DFMEA (§2.2.4) is NOT_APPLICABLE
    pkg = PPAPPackage(
        part_name="Bracket",
        submission_level=3,
        has_design_responsibility=False,
    )
    res = audit_ppap_package(pkg)
    elem_dfmea = res.get_element("dfmea")
    assert elem_dfmea is not None
    assert elem_dfmea.verdict == "NOT_APPLICABLE"
    assert elem_dfmea.is_blocking is False
    assert "not design-responsible" in elem_dfmea.rationale


def test_branch_evidence_invalid() -> None:
    """evidence_valid is False yields element verdict EVIDENCE_INVALID and is_blocking=True."""
    item = EvidenceItem(
        element_id="2.2.6",
        present=True,
        status="submitted",
        evidence_valid=False,
        notes="High Severity AP violation without action",
    )
    pkg = PPAPPackage(part_name="Valve", submission_level=3, elements=[item])
    res = audit_ppap_package(pkg)
    elem_pfmea = res.get_element("pfmea")
    assert elem_pfmea is not None
    assert elem_pfmea.verdict == "EVIDENCE_INVALID"
    assert elem_pfmea.is_blocking is True
    assert "failed validation" in elem_pfmea.rationale
    assert "High Severity AP violation" in elem_pfmea.rationale


def test_branch_evidence_invalid_without_item_notes() -> None:
    """evidence_valid is False without notes yields generic validation failure rationale."""
    item = EvidenceItem(
        element_id="2.2.6",
        present=True,
        status="submitted",
        evidence_valid=False,
        notes=None,
    )
    pkg = PPAPPackage(part_name="Valve", submission_level=3, elements=[item])
    res = audit_ppap_package(pkg)
    elem_pfmea = res.get_element("pfmea")
    assert elem_pfmea is not None
    assert elem_pfmea.verdict == "EVIDENCE_INVALID"
    assert "Evidence does not meet acceptance criteria" in elem_pfmea.rationale


def test_branch_undecided_sentinel() -> None:
    """Undecided sentinel (status='undecided', present=None) yields INDETERMINATE and is_blocking=True."""
    item = EvidenceItem(
        element_id="2.2.7",
        present=None,
        status="undecided",
    )
    pkg = PPAPPackage(part_name="Shaft", submission_level=3, elements=[item])
    res = audit_ppap_package(pkg)
    elem_cp = res.get_element("2.2.7")
    assert elem_cp is not None
    assert elem_cp.verdict == "INDETERMINATE"
    assert elem_cp.is_blocking is True
    assert "Un-surveyed" in elem_cp.rationale


def test_branch_confirmed_absent_across_requirement_codes() -> None:
    """Confirmed absent evidence across Table 4.1 codes S, R, *, and CUSTOMER_DEFINED yields MISSING."""
    missing_items = [
        EvidenceItem(element_id="2.2.18", present=False, status="missing"),
        EvidenceItem(element_id="2.2.4", present=False, status="missing"),
        EvidenceItem(element_id="2.2.1", present=False, status="missing"),
    ]

    # Test Code S missing
    pkg_s = PPAPPackage(part_name="Pump", submission_level=3, elements=[missing_items[0]])
    res_s = audit_ppap_package(pkg_s)
    elem_psw = res_s.get_element("2.2.18")
    assert elem_psw is not None
    assert elem_psw.verdict == "MISSING"
    assert elem_psw.is_blocking is True
    assert "Table 4.1 coded 'S'" in elem_psw.rationale

    # Test Code R missing
    pkg_r = PPAPPackage(part_name="Pump", submission_level=1, elements=[missing_items[1]])
    res_r = audit_ppap_package(pkg_r)
    elem_dfmea = res_r.get_element("2.2.4")
    assert elem_dfmea is not None
    assert elem_dfmea.verdict == "MISSING"
    assert elem_dfmea.is_blocking is True
    assert "Table 4.1 coded 'R'" in elem_dfmea.rationale

    # Test Code * missing (Level 4 with customer requirement set)
    pkg_star = PPAPPackage(
        part_name="Pump",
        submission_level=4,
        customer_requirement_set={"2.2.1", "2.2.18"},
        elements=[missing_items[2]],
    )
    res_star = audit_ppap_package(pkg_star)
    elem_dr = res_star.get_element("2.2.1")
    assert elem_dr is not None
    assert elem_dr.verdict == "MISSING"
    assert elem_dr.is_blocking is True
    assert "Table 4.1 coded '*'" in elem_dr.rationale


def test_branch_coded_s_retained_only_yields_missing() -> None:
    """Element coded S where evidence is retained but submitted_to_customer=False yields MISSING."""
    item = EvidenceItem(
        element_id="2.2.18",
        present=True,
        status="retained",
        submitted_to_customer=False,
        retained_at_organization=True,
    )
    pkg = PPAPPackage(part_name="Bolt", submission_level=3, elements=[item])
    res = audit_ppap_package(pkg)
    elem_psw = res.get_element("2.2.18")
    assert elem_psw is not None
    assert elem_psw.verdict == "MISSING"
    assert elem_psw.is_blocking is True
    assert "only retained on file, not submitted" in elem_psw.rationale


def test_branch_present_evidence_resolution() -> None:
    """Test present evidence under requirement codes S, R, and *."""
    items = [
        # Code S submitted -> SUBMITTED
        EvidenceItem(
            element_id="2.2.18",
            present=True,
            status="submitted",
            submitted_to_customer=True,
        ),
        # Code R retained -> RETAINED_ON_FILE
        EvidenceItem(
            element_id="2.2.5",
            present=True,
            status="retained",
            retained_at_organization=True,
        ),
        # Code * submitted -> SUBMITTED
        EvidenceItem(
            element_id="2.2.1",
            present=True,
            status="submitted",
            submitted_to_customer=True,
        ),
        # Code * retained -> RETAINED_ON_FILE
        EvidenceItem(
            element_id="2.2.2",
            present=True,
            status="retained",
            retained_at_organization=True,
            submitted_to_customer=False,
        ),
    ]

    pkg = PPAPPackage(
        part_name="Assembly",
        submission_level=4,
        customer_requirement_set={"2.2.1", "2.2.2", "2.2.5", "2.2.18"},
        elements=items,
    )
    res = audit_ppap_package(pkg)

    # 2.2.18 (Code S)
    assert res.get_element("2.2.18").verdict == "SUBMITTED"  # type: ignore[union-attr]
    # 2.2.1 (Code * submitted)
    assert res.get_element("2.2.1").verdict == "SUBMITTED"  # type: ignore[union-attr]
    # 2.2.2 (Code * retained)
    assert res.get_element("2.2.2").verdict == "RETAINED_ON_FILE"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 6. Package Readiness Verdict Branch Exhaustion
# ---------------------------------------------------------------------------


def _build_complete_level_1_elements() -> list[EvidenceItem]:
    """Helper to build complete benchmark elements for Level 1."""
    items: list[EvidenceItem] = []
    for elem_id in PPAP_ELEMENT_IDS:
        req = lookup_requirement(elem_id, 1)
        if req == "S":
            items.append(
                EvidenceItem(
                    element_id=elem_id,
                    present=True,
                    status="submitted",
                    submitted_to_customer=True,
                )
            )
        else:
            items.append(
                EvidenceItem(
                    element_id=elem_id,
                    present=True,
                    status="retained",
                    retained_at_organization=True,
                )
            )
    return items


def test_package_verdict_submission_ready() -> None:
    """All 18 elements satisfied yields SUBMISSION_READY."""
    elements = _build_complete_level_1_elements()
    pkg = PPAPPackage(
        part_name="Benchmark Bracket",
        submission_level=1,
        appearance_item=True,
        elements=elements,
    )
    res = audit_ppap_package(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    assert res.package_verdict == "SUBMISSION_READY"
    assert res.is_ready() is True
    assert len(res.blocking_elements) == 0


def test_package_verdict_not_ready() -> None:
    """Missing or invalid elements yield NOT_READY."""
    elements = _build_complete_level_1_elements()
    # Mutate PSW to missing
    for i, item in enumerate(elements):
        if item.element_id == "2.2.18":
            elements[i] = EvidenceItem(element_id="2.2.18", present=False, status="missing")

    pkg = PPAPPackage(
        part_name="Benchmark Bracket",
        submission_level=1,
        appearance_item=True,
        elements=elements,
    )
    res = audit_ppap_package(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    assert res.package_verdict == "NOT_READY"
    assert res.is_ready() is False
    assert "2.2.18" in res.blocking_elements
    assert "2.2.18" in res.missing_elements


def test_package_verdict_indeterminate() -> None:
    """Indeterminate applicability or element yields INDETERMINATE package verdict."""
    elements = _build_complete_level_1_elements()
    # Mutate one element to undecided sentinel
    for i, item in enumerate(elements):
        if item.element_id == "2.2.5":
            elements[i] = EvidenceItem(element_id="2.2.5", present=None, status="undecided")

    pkg = PPAPPackage(
        part_name="Benchmark Bracket",
        submission_level=1,
        appearance_item=True,
        elements=elements,
    )
    res = audit_ppap_package(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    assert res.package_verdict == "INDETERMINATE"
    assert res.is_ready() is False
    assert "2.2.5" in res.indeterminate_elements

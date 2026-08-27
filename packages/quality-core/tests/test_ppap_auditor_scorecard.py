"""Scorecard integration tests for PPAP 18-Element Completeness Auditor (Issue #102).

Validates:
1. Benchmark data integration across Submission Levels 1, 2, 3, and 5
2. 🔒 Authority Invariant Negative Control: Proves customer approval dispositions
   (Approved, Interim Approval, Rejected) are NEVER emitted by the completeness auditor
3. Missing vs Not Applicable negative control
4. Level Completeness isolation control
5. Level 4 propagation control (un-specified -> INDETERMINATE vs explicit customer set)
6. Undecided sentinel control (un-surveyed evidence blocks readiness)
7. R vs * rationale wording distinction control
8. Zero duplicated standards data control (AST inspection)
"""

from __future__ import annotations

import ast
import inspect

from quality_core.ppap import auditor
from quality_core.ppap.auditor import audit_ppap_package
from quality_core.ppap.schema import (
    PPAP_ELEMENT_IDS,
    EvidenceItem,
    PPAPPackage,
    SubmissionLevel,
)
from quality_core.ppap.table_4_1 import lookup_requirement


def _create_benchmark_package(
    level: SubmissionLevel,
    appearance_item: bool = False,
    has_design_responsibility: bool = True,
    customer_requirement_set: set[str] | None = None,
) -> PPAPPackage:
    """Construct a fully conforming benchmark PPAP submission package for a given level."""
    elements: list[EvidenceItem] = []

    for elem_id in PPAP_ELEMENT_IDS:
        req = lookup_requirement(elem_id, level)
        if req == "S":
            elements.append(
                EvidenceItem(
                    element_id=elem_id,
                    present=True,
                    status="submitted",
                    submitted_to_customer=True,
                    document_reference=f"DOC-{elem_id}.pdf",
                )
            )
        elif req == "*":
            # Retained on file, available for customer submission on request
            elements.append(
                EvidenceItem(
                    element_id=elem_id,
                    present=True,
                    status="retained",
                    retained_at_organization=True,
                    document_reference=f"DOC-{elem_id}.pdf",
                )
            )
        elif req == "R":
            # Retained at manufacturing location
            elements.append(
                EvidenceItem(
                    element_id=elem_id,
                    present=True,
                    status="retained",
                    retained_at_organization=True,
                    document_reference=f"DOC-{elem_id}.pdf",
                )
            )
        else:  # CUSTOMER_DEFINED
            elements.append(
                EvidenceItem(
                    element_id=elem_id,
                    present=True,
                    status="submitted",
                    submitted_to_customer=True,
                    document_reference=f"DOC-{elem_id}.pdf",
                )
            )

    return PPAPPackage(
        part_name="Precision Machined Housing",
        part_number="HOUSING-001",
        submission_level=level,
        appearance_item=appearance_item,
        has_design_responsibility=has_design_responsibility,
        customer_requirement_set=customer_requirement_set,
        elements=elements,
    )


# ---------------------------------------------------------------------------
# 1. Benchmark Manufacturing Scorecards (Levels 1, 2, 3, 5)
# ---------------------------------------------------------------------------


def test_scorecard_benchmark_level_1() -> None:
    """Level 1 Benchmark: PSW + AAR submitted, remaining 16 retained on file."""
    pkg = _create_benchmark_package(level=1, appearance_item=True)
    res = audit_ppap_package(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )

    assert res.package_verdict == "SUBMISSION_READY"
    assert res.is_ready() is True
    assert res.submission_level == 1
    assert sorted(res.submitted_elements) == ["2.2.13", "2.2.18"]
    assert len(res.blocking_elements) == 0


def test_scorecard_benchmark_level_2() -> None:
    """Level 2 Benchmark: Warrant with product samples and limited supporting data submitted."""
    pkg = _create_benchmark_package(level=2, appearance_item=True)
    res = audit_ppap_package(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )

    assert res.package_verdict == "SUBMISSION_READY"
    assert res.is_ready() is True
    assert res.submission_level == 2
    # Table 4.1 Level 2 submitted items: 2.2.1, 2.2.2, 2.2.9, 2.2.10, 2.2.12, 2.2.13, 2.2.14, 2.2.18
    expected_submitted = ["2.2.1", "2.2.2", "2.2.9", "2.2.10", "2.2.12", "2.2.13", "2.2.14", "2.2.18"]
    assert sorted(res.submitted_elements) == sorted(expected_submitted)
    assert len(res.blocking_elements) == 0


def test_scorecard_benchmark_level_3() -> None:
    """Level 3 Benchmark: Complete supporting data submitted to customer."""
    pkg = _create_benchmark_package(level=3, appearance_item=True)
    res = audit_ppap_package(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )

    assert res.package_verdict == "SUBMISSION_READY"
    assert res.is_ready() is True
    assert res.submission_level == 3
    # At Level 3, all except master sample & checking aids are submitted
    assert "2.2.18" in res.submitted_elements
    assert "2.2.6" in res.submitted_elements
    assert "2.2.7" in res.submitted_elements
    assert len(res.blocking_elements) == 0


def test_scorecard_benchmark_level_5() -> None:
    """Level 5 Benchmark: All 18 elements reviewed at supplier manufacturing location."""
    pkg = _create_benchmark_package(level=5, appearance_item=True)
    res = audit_ppap_package(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )

    assert res.package_verdict == "SUBMISSION_READY"
    assert res.is_ready() is True
    assert res.submission_level == 5
    assert len(res.submitted_elements) == 0
    assert len(res.retained_elements) == 16  # 16 applicable retained + 2 non-applicable (eng approval, checking aids)
    assert len(res.blocking_elements) == 0


# ---------------------------------------------------------------------------
# 2. 🔒 Authority Invariant Negative Control
# ---------------------------------------------------------------------------


def test_authority_invariant_negative_control() -> None:
    """🔒 Customer dispositions (Approved, Interim Approval, Rejected) are NEVER emitted by completeness auditor."""
    forbidden_verdicts = {"Approved", "APPROVED", "Interim Approval", "INTERIM_APPROVAL", "Rejected", "REJECTED"}

    test_packages = [
        _create_benchmark_package(level=1, appearance_item=True),
        _create_benchmark_package(level=2, appearance_item=True),
        _create_benchmark_package(level=3, appearance_item=True),
        _create_benchmark_package(level=5, appearance_item=True),
        PPAPPackage(part_name="Empty Level 1", submission_level=1),
        PPAPPackage(part_name="Empty Level 3", submission_level=3),
        PPAPPackage(part_name="Empty Level 4", submission_level=4),
        PPAPPackage(
            part_name="Invalid Evidence Pkg",
            submission_level=3,
            elements=[EvidenceItem(element_id="2.2.6", present=True, evidence_valid=False)],
        ),
        PPAPPackage(
            part_name="Missing Evidence Pkg",
            submission_level=3,
            elements=[EvidenceItem(element_id="2.2.18", present=False, status="missing")],
        ),
        PPAPPackage(
            part_name="Undecided Pkg",
            submission_level=2,
            elements=[EvidenceItem(element_id="2.2.9", present=None, status="undecided")],
        ),
    ]

    for i, pkg in enumerate(test_packages):
        result = audit_ppap_package(
            pkg,
            customer_engineering_approval_required=False,
            master_sample_waived=False,
        )

        # Assert package verdict does not contain forbidden customer disposition
        assert (
            result.package_verdict not in forbidden_verdicts
        ), f"Pkg {i}: package_verdict '{result.package_verdict}' violated Section 5 Authority Invariant!"

        # Assert element verdicts do not contain forbidden customer disposition
        for elem_id, elem_result in result.elements.items():
            assert (
                elem_result.verdict not in forbidden_verdicts
            ), f"Pkg {i} elem {elem_id}: verdict '{elem_result.verdict}' violated Section 5 Authority Invariant!"

        # Assert verdict counts dictionary keys
        for key in result.verdict_counts:
            assert (
                key not in forbidden_verdicts
            ), f"Pkg {i}: verdict_counts key '{key}' violated Section 5 Authority Invariant!"

        # Assert dictionary serialization contains no forbidden customer disposition verdicts
        res_dict = result.to_dict()
        assert res_dict["package_verdict"] not in forbidden_verdicts


# ---------------------------------------------------------------------------
# 3. Missing vs Not Applicable Negative Control
# ---------------------------------------------------------------------------


def test_missing_vs_not_applicable_control() -> None:
    """Missing evidence for non-applicable element does not block; missing for applicable element blocks."""
    # When customer is design-responsible, DFMEA (§2.2.4) is NOT_APPLICABLE
    pkg_not_app = _create_benchmark_package(level=3, has_design_responsibility=False)
    # Explicitly mark DFMEA as absent / missing
    dfmea_item = EvidenceItem(element_id="2.2.4", present=False, status="missing")
    pkg_not_app.elements = [e for e in pkg_not_app.elements if e.element_id != "2.2.4"] + [dfmea_item]

    res_not_app = audit_ppap_package(
        pkg_not_app,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    elem_dfmea = res_not_app.get_element("dfmea")
    assert elem_dfmea is not None
    assert elem_dfmea.verdict == "NOT_APPLICABLE"
    assert elem_dfmea.is_blocking is False
    assert res_not_app.package_verdict == "SUBMISSION_READY"

    # Conversely, PFMEA (§2.2.6) is always applicable; missing PFMEA MUST block
    pkg_missing_pfmea = _create_benchmark_package(level=3, has_design_responsibility=False)
    pfmea_item = EvidenceItem(element_id="2.2.6", present=False, status="missing")
    pkg_missing_pfmea.elements = [e for e in pkg_missing_pfmea.elements if e.element_id != "2.2.6"] + [pfmea_item]

    res_missing_pfmea = audit_ppap_package(
        pkg_missing_pfmea,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    elem_pfmea = res_missing_pfmea.get_element("pfmea")
    assert elem_pfmea is not None
    assert elem_pfmea.verdict == "MISSING"
    assert elem_pfmea.is_blocking is True
    assert res_missing_pfmea.package_verdict == "NOT_READY"
    assert "2.2.6" in res_missing_pfmea.blocking_elements


# ---------------------------------------------------------------------------
# 4. Level Completeness Control
# ---------------------------------------------------------------------------


def test_level_completeness_control() -> None:
    """Same evidence (PSW + AAR only) evaluated at Level 1 is SUBMISSION_READY, but at Level 3 is NOT_READY."""
    evidence = [
        EvidenceItem(element_id="2.2.18", present=True, status="submitted", submitted_to_customer=True),
        EvidenceItem(element_id="2.2.13", present=True, status="submitted", submitted_to_customer=True),
    ]

    # Level 1: PSW + AAR submitted, remaining 16 retained on file
    for elem_id in PPAP_ELEMENT_IDS:
        if elem_id not in ("2.2.18", "2.2.13"):
            evidence.append(
                EvidenceItem(
                    element_id=elem_id,
                    present=True,
                    status="retained",
                    retained_at_organization=True,
                )
            )

    pkg_lvl1 = PPAPPackage(part_name="Test Part", submission_level=1, appearance_item=True, elements=evidence)
    res_lvl1 = audit_ppap_package(
        pkg_lvl1,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    assert res_lvl1.package_verdict == "SUBMISSION_READY"
    assert len(res_lvl1.blocking_elements) == 0

    # Same package evaluated at Level 3 override
    res_lvl3 = audit_ppap_package(
        pkg_lvl1,
        submission_level=3,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    assert res_lvl3.package_verdict == "NOT_READY"
    # At Level 3, Table 4.1 requires Design Records, ECN, DFMEA, Process Flow,
    # PFMEA, Control Plan, MSA, Dimensional, Material/Perf, Process Studies, Lab, Samples submitted.
    # Because they are only retained in evidence, they resolve to MISSING.
    assert len(res_lvl3.blocking_elements) > 0
    assert "2.2.6" in res_lvl3.blocking_elements
    assert "2.2.7" in res_lvl3.blocking_elements


# ---------------------------------------------------------------------------
# 5. Level 4 Propagation Control
# ---------------------------------------------------------------------------


def test_level_4_propagation_control() -> None:
    """Level 4 without requirements resolves to INDETERMINATE; with explicit requirements resolves deterministically."""
    # Without customer requirements set
    pkg_unspecified = PPAPPackage(part_name="Custom Part", submission_level=4, customer_requirement_set=None)
    res_unspecified = audit_ppap_package(pkg_unspecified)
    assert res_unspecified.package_verdict == "INDETERMINATE"
    assert len(res_unspecified.indeterminate_elements) == 18

    # With explicit customer requirements set: PSW, PFMEA, Control Plan
    req_set: set[str] = {"2.2.18", "2.2.6", "2.2.7"}
    conforming_items = [
        EvidenceItem(element_id="2.2.18", present=True, status="submitted", submitted_to_customer=True),
        EvidenceItem(element_id="2.2.6", present=True, status="submitted", submitted_to_customer=True),
        EvidenceItem(element_id="2.2.7", present=True, status="submitted", submitted_to_customer=True),
    ]
    pkg_specified = PPAPPackage(
        part_name="Custom Part",
        submission_level=4,
        customer_requirement_set=req_set,
        elements=conforming_items,
    )
    res_specified = audit_ppap_package(pkg_specified)
    assert res_specified.package_verdict == "SUBMISSION_READY"
    assert res_specified.get_element("psw").verdict == "SUBMITTED"  # type: ignore[union-attr]
    assert res_specified.get_element("pfmea").verdict == "SUBMITTED"  # type: ignore[union-attr]
    assert res_specified.get_element("control_plan").verdict == "SUBMITTED"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 6. Undecided Sentinel Control
# ---------------------------------------------------------------------------


def test_undecided_sentinel_control() -> None:
    """Un-surveyed elements resolve to INDETERMINATE, never defaulting to present or missing."""
    items = [
        EvidenceItem(element_id="2.2.18", present=True, status="submitted", submitted_to_customer=True),
        EvidenceItem(element_id="2.2.6", present=None, status="undecided"),
    ]
    pkg = PPAPPackage(part_name="Assembly", submission_level=3, elements=items)
    res = audit_ppap_package(
        pkg,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )

    assert res.package_verdict == "INDETERMINATE"
    elem_pfmea = res.get_element("2.2.6")
    assert elem_pfmea is not None
    assert elem_pfmea.verdict == "INDETERMINATE"
    assert elem_pfmea.is_blocking is True
    assert "Un-surveyed" in elem_pfmea.rationale


# ---------------------------------------------------------------------------
# 7. R vs * Rationale Distinction Control
# ---------------------------------------------------------------------------


def test_r_vs_star_rationale_distinction_control() -> None:
    """Rationale for Table 4.1 code R cites 'make available', while code * cites 'submit upon request'."""
    # Code R: Level 1 §2.2.6 PFMEA retained
    pkg_lvl1 = _create_benchmark_package(level=1)
    res_lvl1 = audit_ppap_package(
        pkg_lvl1,
        customer_engineering_approval_required=False,
        master_sample_waived=False,
    )
    elem_r = res_lvl1.get_element("pfmea")
    assert elem_r is not None
    assert elem_r.verdict == "RETAINED_ON_FILE"
    assert "make available to the customer upon request" in elem_r.rationale

    # Code *: Level 4 §2.2.1 Design Record retained
    pkg_lvl4 = _create_benchmark_package(
        level=4, customer_requirement_set={"2.2.1", "2.2.18"}
    )
    res_lvl4 = audit_ppap_package(pkg_lvl4)
    elem_star = res_lvl4.get_element("design_records")
    assert elem_star is not None
    assert elem_star.verdict == "RETAINED_ON_FILE"
    assert "submit to the customer upon request" in elem_star.rationale


# ---------------------------------------------------------------------------
# 8. No Duplicated Standards Data Control
# ---------------------------------------------------------------------------


def test_no_duplicated_standards_data_ast_control() -> None:
    """Assert via AST inspection that auditor.py contains zero hardcoded Table 4.1 matrix data."""
    source = inspect.getsource(auditor)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets.append(node.target)

        for target in targets:
            if isinstance(target, ast.Name):
                # auditor.py must not define any TABLE_4_1 or APPLICABILITY rule constants
                assert "TABLE_4_1" not in target.id, f"Found duplicated matrix constant {target.id} in auditor.py"
                assert "APPLICABILITY_MATRIX" not in target.id

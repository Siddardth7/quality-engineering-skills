"""
ppap.py
FastMCP tools for Production Part Approval Process (PPAP) submission readiness evaluation.

Exposes deterministic PPAP 18-element package completeness auditing, Table 4.1 requirement
matrix lookups, 27-field Part Submission Warrant (PSW) schema validation, Section 2.2.11
Initial Process Studies capability criteria evaluation, and responsive dark/light visual canvas
rendering from `quality_core.ppap` and `quality_core.canvas.ppap` to AI agents and MCP client hosts.

Standards Reference:
- AIAG Production Part Approval Process (PPAP) Reference Manual, 4th Edition (June 2006):
  - Section 2.2 (§2.2.1–§2.2.18) Element Requirements
  - Section 2.2.11 Initial Process Studies
  - Section 4 Submission Levels 1–5 (Table 4.1 / Table 4.2 Matrix)
  - Section 5 Part Submission Status (Customer Authority Invariant)
  - Appendix A Part Submission Warrant (PSW) Completion Instructions
  - Appendices F, G, H Commodity-Specific Applicability Guidelines

🔒 THE SECTION 5 CUSTOMER AUTHORITY INVARIANT:
Per Section 5 (Part Submission Status), customer submission approval status ('Approved',
'Interim Approval', 'Rejected') is assigned exclusively by the customer's authorized
representative. These tools evaluate and report supplier submission readiness only and never
emit, return, or embed customer approval dispositions as tool verdicts.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

import pydantic
from pydantic import Field
from quality_core.canvas.ppap import (
    SAMPLE_PPAP_PACKAGE,
    PPAPCanvas,
)
from quality_core.io.validate import clean_pydantic_message
from quality_core.ppap.auditor import (
    audit_ppap_package as _core_audit_ppap_package,
)
from quality_core.ppap.process_study import (
    ACTION_INSUFFICIENT_SAMPLE,
)
from quality_core.ppap.process_study import (
    assess_initial_process_study as _core_assess_initial_process_study,
)
from quality_core.ppap.psw import (
    validate_psw as _core_validate_psw,
)
from quality_core.ppap.schema import (
    PPAP_ELEMENT_ALIASES,
    PPAP_ELEMENT_IDS,
    PPAP_ELEMENT_NAMES,
    PPAP_ELEMENT_NUMBERS,
    REASON_FOR_SUBMISSION_ALIASES,
    REASON_FOR_SUBMISSION_VALUES,
    SUBMISSION_LEVEL_ALIASES,
    SUBMISSION_LEVELS,
    PPAPElementId,
    ReasonForSubmission,
    SubmissionLevel,
)
from quality_core.ppap.table_4_1 import (
    lookup_requirement as _core_lookup_requirement,
)
from quality_core.ppap.table_4_1 import (
    requirement_legend as _core_requirement_legend,
)
from quality_core.ppap.table_4_1 import (
    submission_level_description as _core_submission_level_description,
)

__all__ = [
    "assess_ppap_capability",
    "audit_ppap_package",
    "lookup_ppap_requirement",
    "render_ppap_canvas",
    "validate_psw",
]

_STANDARDS_BASIS = "AIAG PPAP Reference Manual, 4th Edition (2006)"

_AUTHORITY_NOTICE = (
    "Submission approval status (Approved, Interim Approval, Rejected) is assigned "
    "exclusively by the customer's authorized representative per AIAG PPAP 4th Edition "
    "Section 5. This tool evaluates and reports supplier submission readiness only."
)

# Benchmark Level 3 Part Submission Warrant (PSW) Dataset (Appendix A)
SAMPLE_PSW_RECORD: dict[str, Any] = {
    "part_name": "Transmission Output Shaft",
    "customer_part_number": "PART-SFT-4410",
    "part_drawing_number": "DWG-SFT-4410",
    "engineering_change_level": "Rev D",
    "engineering_change_date": "2026-08-15",
    "additional_engineering_changes": "None",
    "purchase_order_number": "PO-998877",
    "part_weight_kg": 2.450,
    "checking_aid_number": "CHK-FIXTURE-CERT-09",
    "checking_aid_change_level_date": "Rev A 2026-08-15",
    "organization_name": "Acme Precision Driveline Systems",
    "organization_code": "VND-88210",
    "organization_address": "123 Industrial Parkway, Detroit, MI 48201",
    "customer_name": "Apex Automotive Group",
    "customer_division": "Powertrain Division",
    "customer_contact": "Jane Doe, Lead Buyer",
    "application": "8-Speed Automatic Transmission",
    "materials_reporting": "IMDS ID #123456789",
    "polymeric_parts_marking": "ISO 11469 / ISO 1043",
    "reason_for_submission": "Initial Submission",
    "submission_level": 3,
    "submission_results": "All dimensional, material, functional, and capability tests meet engineering specifications.",
    "results_dimensional": True,
    "results_material_functional": True,
    "results_appearance": True,
    "results_process_capability": True,
    "declaration_of_conformance": True,
    "customer_tool_tagging": "Tagged Tool #T-9002 per OEM Standard",
    "production_rate": 120.0,
    "production_duration_hours": 8.0,
    "explanation_comments": "Regular 300-piece pilot production run; 30 sample parts layout inspected.",
    "authorized_signature": True,
    "authorized_signature_name": "John Smith, Quality Director",
    "authorized_signature_title": "Quality Director",
    "authorized_signature_date": "2026-08-21",
    "authorized_signature_phone": "+1-313-555-0199",
    "authorized_signature_email": "jsmith@acmedriveline.com",
}

# Benchmark Initial Process Study Dataset (25 subgroups of size 5 = 125 readings, AIAG SPC 4th Ed.)
SAMPLE_PROCESS_STUDY_DATA: list[list[float]] = [
    [10.0244, 9.9168, 10.06, 10.0752, 9.8439],
    [9.8958, 10.0102, 9.9747, 9.9987, 9.9318],
    [10.0704, 10.0622, 10.0053, 10.0902, 10.0374],
    [9.9313, 10.0295, 9.9233, 10.0703, 9.996],
    [9.9852, 9.9455, 10.0978, 9.9876, 9.9657],
    [9.9718, 10.0426, 10.0292, 10.033, 10.0345],
    [10.1713, 9.9675, 9.959, 9.9349, 10.0493],
    [10.0903, 9.9909, 9.9328, 9.934, 10.052],
    [10.0595, 10.0435, 9.9468, 10.0186, 10.0093],
    [10.0175, 10.0697, 10.0179, 10.0543, 10.0054],
    [10.0231, 10.0505, 9.8834, 9.9744, 9.9624],
    [9.9489, 9.978, 10.1196, 9.9307, 10.0775],
    [9.8654, 9.9732, 10.013, 10.0469, 10.0569],
    [10.0635, 9.9721, 9.963, 10.0686, 9.9847],
    [9.8979, 9.9093, 9.9264, 10.0398, 10.0114],
    [10.0552, 9.9658, 10.0127, 10.05, 9.9753],
    [10.0365, 9.947, 9.971, 9.9695, 9.9043],
    [10.039, 9.9624, 10.001, 10.0385, 10.0357],
    [10.0532, 9.9921, 9.9661, 9.9936, 9.865],
    [9.8842, 9.8942, 9.9202, 10.032, 9.9276],
    [9.9697, 10.1039, 9.9715, 10.059, 9.9253],
    [9.9836, 9.924, 9.9729, 10.0672, 9.8618],
    [10.0348, 10.019, 9.9525, 9.8843, 10.0058],
    [9.9576, 10.0186, 10.0017, 10.1281, 9.9809],
    [9.9181, 10.0143, 10.0176, 10.1087, 10.0668],
]


def audit_ppap_package(
    package: Annotated[
        list[dict[str, Any]] | dict[str, Any] | None,
        Field(
            description=(
                "PPAP submission package data as a list of element evidence dictionaries, "
                "or a complete package dictionary with elements and part metadata. "
                "If omitted or None, loads the standard reference Level 3 automotive transmission shaft sample dataset. "
                "Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the "
                "customer's authorized representative per AIAG PPAP 4th Edition Section 5. "
                "This tool evaluates and reports supplier submission readiness only."
            ),
        ),
    ] = None,
    submission_level: Annotated[
        int | str,
        Field(
            description=(
                "AIAG PPAP Submission Level (1, 2, 3, 4, 5). Default is 3 (Warrant with product samples and complete supporting data)."
            ),
        ),
    ] = 3,
    reason_for_submission: Annotated[
        str,
        Field(
            description=(
                "Reason for PPAP submission (e.g. 'initial_submission', 'engineering_change', 'tooling_change', "
                "'correction_of_discrepancy', 'optional_material_change', 'sub_supplier_change', 'process_change', 'other'). Default is 'initial_submission'."
            ),
        ),
    ] = "initial_submission",
    has_design_responsibility: Annotated[
        bool,
        Field(
            description=(
                "Whether the organization has product design responsibility. If False, Design Records (§2.2.1) "
                "and Design FMEA (§2.2.4) resolve to NOT_APPLICABLE."
            ),
        ),
    ] = True,
    is_designated_appearance_item: Annotated[
        bool,
        Field(
            description=(
                "Whether the part has designated appearance requirements on engineering drawings. "
                "If False, Appearance Approval Report (§2.2.13) resolves to NOT_APPLICABLE."
            ),
        ),
    ] = False,
    has_checking_aid: Annotated[
        bool,
        Field(
            description=(
                "Whether checking fixtures/aids are used for inspection. If False, Checking Aids (§2.2.16) resolves to NOT_APPLICABLE."
            ),
        ),
    ] = False,
    is_bulk_material: Annotated[
        bool,
        Field(
            description=(
                "Whether the item is bulk material (Appendix F). If True, Bulk Material Checklist (§2.2.17) becomes applicable."
            ),
        ),
    ] = False,
    has_customer_engineering_approval: Annotated[
        bool,
        Field(
            description=(
                "Whether customer engineering approval is required before submission (§2.2.3)."
            ),
        ),
    ] = True,
    has_master_sample: Annotated[
        bool,
        Field(
            description=(
                "Whether a master sample is retained at the manufacturing location (§2.2.15)."
            ),
        ),
    ] = True,
    is_catalog_or_blackbox: Annotated[
        bool,
        Field(
            description=(
                "Whether the component is a standard catalog or black-box part without customer design records."
            ),
        ),
    ] = False,
    is_extrapolated_material: Annotated[
        bool,
        Field(
            description=(
                "Whether material performance is extrapolated from historical data without dedicated material test results."
            ),
        ),
    ] = False,
    customer_requirement_set: Annotated[
        list[str] | None,
        Field(
            description=(
                "Optional list of required element IDs for Submission Level 4 (e.g. ['2.2.18', '2.2.6', '2.2.7']). "
                "Level 4 without customer requirements resolves to INDETERMINATE."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Audit a PPAP submission package for 18-element completeness against AIAG PPAP 4th Edition.

    Deterministic FastMCP tool wrapping `quality_core.ppap.auditor.audit_ppap_package`.
    Evaluates evidence presence and applicability across all 18 canonical elements (§2.2.1–§2.2.18)
    against Table 4.1 submission/retention requirements at the requested Submission Level (1–5)
    and Reason for Submission.

    Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the
    customer's authorized representative per AIAG PPAP 4th Edition Section 5.
    This tool evaluates and reports supplier submission readiness only.

    Parameters
    ----------
    package : list[dict[str, Any]] | dict[str, Any] | None, optional
        PPAP package evidence list or dictionary. If None, loads the Level 3 benchmark automotive dataset.
    submission_level : int | str, default 3
        AIAG PPAP Submission Level (1–5).
    reason_for_submission : str, default "initial_submission"
        PSW Reason for Submission.
    has_design_responsibility : bool, default True
        Whether organization has design responsibility.
    is_designated_appearance_item : bool, default False
        Whether item has designated appearance requirements.
    has_checking_aid : bool, default False
        Whether checking aids/fixtures are used.
    is_bulk_material : bool, default False
        Whether part is bulk material per Appendix F.
    has_customer_engineering_approval : bool, default True
        Whether customer engineering approval is required.
    has_master_sample : bool, default True
        Whether master sample is retained.
    is_catalog_or_blackbox : bool, default False
        Whether item is catalog or black-box part.
    is_extrapolated_material : bool, default False
        Whether material data is extrapolated.
    customer_requirement_set : list[str] | None, optional
        Customer-defined required element IDs for Level 4 submissions.

    Returns
    -------
    dict[str, Any]
        Structured dictionary containing package_verdict, submission_level, reason_for_submission,
        18-element results dictionary, verdict_counts, blocking_elements, and standards basis.
    """
    # 1. Type Guards
    if isinstance(submission_level, bool):
        raise TypeError(f"submission_level cannot be a boolean, got {submission_level!r}")
    eff_level: SubmissionLevel
    if isinstance(submission_level, int):
        if submission_level in SUBMISSION_LEVELS:
            eff_level = cast(SubmissionLevel, submission_level)
        else:
            raise ValueError(f"submission_level must be an integer 1–5, got {submission_level}")
    elif isinstance(submission_level, str):
        clean_lvl = submission_level.strip().lower()
        if clean_lvl in SUBMISSION_LEVEL_ALIASES:
            eff_level = SUBMISSION_LEVEL_ALIASES[clean_lvl]
        else:
            raise ValueError(f"Invalid submission_level: '{submission_level}'. Must be 1–5 or recognized alias.")
    else:
        raise TypeError(f"submission_level must be an int or str, got {type(submission_level).__name__}")

    if isinstance(reason_for_submission, bool) or not isinstance(reason_for_submission, str):
        raise TypeError(f"reason_for_submission must be a string, got {type(reason_for_submission).__name__}")
    clean_rsn = reason_for_submission.strip().lower()
    clean_rsn_normalized = clean_rsn.replace("_", " ")
    eff_reason: ReasonForSubmission
    if clean_rsn in REASON_FOR_SUBMISSION_ALIASES:
        eff_reason = REASON_FOR_SUBMISSION_ALIASES[clean_rsn]
    elif clean_rsn_normalized in REASON_FOR_SUBMISSION_ALIASES:
        eff_reason = REASON_FOR_SUBMISSION_ALIASES[clean_rsn_normalized]
    else:
        raise ValueError(
            f"Invalid reason_for_submission: '{reason_for_submission}'. Must be one of {list(REASON_FOR_SUBMISSION_VALUES)}."
        )

    for flag_name, flag_val in (
        ("has_design_responsibility", has_design_responsibility),
        ("is_designated_appearance_item", is_designated_appearance_item),
        ("has_checking_aid", has_checking_aid),
        ("is_bulk_material", is_bulk_material),
        ("has_customer_engineering_approval", has_customer_engineering_approval),
        ("has_master_sample", has_master_sample),
        ("is_catalog_or_blackbox", is_catalog_or_blackbox),
        ("is_extrapolated_material", is_extrapolated_material),
    ):
        if type(flag_val) is not bool:
            raise TypeError(f"{flag_name} must be a boolean, got {type(flag_val).__name__}")

    normalized_l4_reqs: list[PPAPElementId] | None = None
    if customer_requirement_set is not None:
        if isinstance(customer_requirement_set, (str, dict, int, bool)) or not isinstance(
            customer_requirement_set, list
        ):
            raise TypeError(
                f"customer_requirement_set must be a list of strings or None, got {type(customer_requirement_set).__name__}"
            )
        normalized_l4_reqs = []
        for idx, item in enumerate(customer_requirement_set):
            if isinstance(item, bool) or not isinstance(item, str):
                raise TypeError(
                    f"customer_requirement_set item at index {idx} must be a str, got {type(item).__name__}"
                )
            clean_item = item.strip().lower()
            if clean_item in PPAP_ELEMENT_ALIASES:
                normalized_l4_reqs.append(PPAP_ELEMENT_ALIASES[clean_item])
            else:
                raise ValueError(
                    f"Invalid element ID in customer_requirement_set at index {idx}: '{item}'"
                )

    if package is not None:
        if isinstance(package, (str, int, bool)) or not isinstance(package, (list, dict)):
            raise TypeError(f"package must be a list, dict, or None, got {type(package).__name__}")
        if isinstance(package, list):
            for elem_idx, elem_val in enumerate(package):
                if not isinstance(elem_val, dict):
                    raise TypeError(f"package element at index {elem_idx} must be a dict, got {type(elem_val).__name__}")

    # 2. Empty Input Handling
    if package == [] or package == {}:
        empty_elements = {
            elem_id: {
                "element_id": elem_id,
                "element_name": PPAP_ELEMENT_NAMES[elem_id],
                "verdict": "INDETERMINATE",
                "requirement_code": _core_lookup_requirement(elem_id, eff_level),
                "applicability_verdict": "INDETERMINATE",
                "rationale": "No submission package data provided.",
                "is_blocking": False,
                "evidence_status": "undecided",
                "evidence_present": None,
                "artifact_ref": None,
                "document_reference": None,
                "evidence_valid": None,
            }
            for elem_id in PPAP_ELEMENT_IDS
        }
        return {
            "package_verdict": "INDETERMINATE",
            "submission_level": eff_level,
            "reason_for_submission": eff_reason,
            "elements": empty_elements,
            "verdict_counts": {
                "SUBMITTED": 0,
                "RETAINED_ON_FILE": 0,
                "MISSING": 0,
                "NOT_APPLICABLE": 0,
                "INDETERMINATE": 18,
                "EVIDENCE_INVALID": 0,
            },
            "blocking_elements": [],
            "blocking_element_names": [],
            "submitted_elements": [],
            "retained_elements": [],
            "missing_elements": [],
            "not_applicable_elements": [],
            "indeterminate_elements": list(PPAP_ELEMENT_IDS),
            "invalid_elements": [],
            "standards_basis": _STANDARDS_BASIS,
            "applicability_result": None,
            "basis": _STANDARDS_BASIS,
            "authority_notice": _AUTHORITY_NOTICE,
        }

    # 3. Resolve Target Package Payload
    pkg_input: dict[str, Any]
    if package is None:
        pkg_input = dict(SAMPLE_PPAP_PACKAGE)
        pkg_input["submission_level"] = eff_level
        pkg_input["reason_for_submission"] = eff_reason
        pkg_input["has_design_responsibility"] = has_design_responsibility
        pkg_input["designated_appearance_item"] = is_designated_appearance_item
        pkg_input["has_checking_aid"] = has_checking_aid
    elif isinstance(package, list):
        pkg_input = {
            "submission_level": eff_level,
            "reason_for_submission": eff_reason,
            "has_design_responsibility": has_design_responsibility,
            "designated_appearance_item": is_designated_appearance_item,
            "has_checking_aid": has_checking_aid,
            "elements": package,
        }
    else:
        pkg_input = dict(package)

    try:
        audit_res = _core_audit_ppap_package(
            package_or_data=pkg_input,
            submission_level=eff_level if (not isinstance(package, dict) or "submission_level" not in package) else None,
            reason_for_submission=eff_reason if (not isinstance(package, dict) or "reason_for_submission" not in package) else None,
            has_design_responsibility=has_design_responsibility,
            appearance_item=is_designated_appearance_item,
            has_checking_aid=has_checking_aid,
            customer_engineering_approval_required=has_customer_engineering_approval,
            master_sample_waived=not has_master_sample,
            is_bulk_material=is_bulk_material,
            catalog_part=is_catalog_or_blackbox,
            black_box_part=is_catalog_or_blackbox,
            customer_level_4_requirements=normalized_l4_reqs,
        )
        res_dict = audit_res.to_dict()
        res_dict["basis"] = _STANDARDS_BASIS
        res_dict["authority_notice"] = _AUTHORITY_NOTICE
        return res_dict
    except pydantic.ValidationError as exc:
        errs = exc.errors()
        err_msg = str(errs[0].get("msg", "invalid value")) if errs else "invalid value"
        clean_msg = clean_pydantic_message(err_msg)
        return {
            "package_verdict": "INDETERMINATE",
            "submission_level": eff_level,
            "reason_for_submission": eff_reason,
            "elements": {},
            "verdict_counts": {
                "SUBMITTED": 0,
                "RETAINED_ON_FILE": 0,
                "MISSING": 0,
                "NOT_APPLICABLE": 0,
                "INDETERMINATE": 18,
                "EVIDENCE_INVALID": 0,
            },
            "blocking_elements": [],
            "blocking_element_names": [],
            "submitted_elements": [],
            "retained_elements": [],
            "missing_elements": [],
            "not_applicable_elements": [],
            "indeterminate_elements": list(PPAP_ELEMENT_IDS),
            "invalid_elements": [],
            "standards_basis": _STANDARDS_BASIS,
            "applicability_result": None,
            "basis": _STANDARDS_BASIS,
            "findings": [clean_msg],
            "authority_notice": _AUTHORITY_NOTICE,
        }


def lookup_ppap_requirement(
    element: Annotated[
        str | int,
        Field(
            description=(
                "AIAG PPAP canonical element ID ('2.2.1'–'2.2.18'), element number (1–18), or alias "
                "(e.g. 'design_records', 'dfmea', 'process_flow', 'pfmea', 'control_plan', 'msa', "
                "'dimensional_results', 'material_tests', 'initial_process_studies', 'qualified_lab', "
                "'appearance_report', 'sample_product', 'master_sample', 'checking_aids', 'customer_specific', 'psw'). "
                "Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the "
                "customer's authorized representative per AIAG PPAP 4th Edition Section 5. "
                "This tool evaluates and reports supplier submission readiness only."
            ),
        ),
    ] = "2.2.1",
    level: Annotated[
        int | str,
        Field(
            description="AIAG PPAP Submission Level (1, 2, 3, 4, 5). Default is 3.",
        ),
    ] = 3,
) -> dict[str, Any]:
    """Look up Table 4.1 submission/retention requirement codes and verbatim AIAG PPAP standard text.

    Deterministic FastMCP tool wrapping `quality_core.ppap.table_4_1.lookup_requirement`
    and `requirement_legend`.

    Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the
    customer's authorized representative per AIAG PPAP 4th Edition Section 5.
    This tool evaluates and reports supplier submission readiness only.

    Parameters
    ----------
    element : str | int, default "2.2.1"
        AIAG PPAP canonical element ID ('2.2.1'–'2.2.18'), element number (1–18), or alias.
    level : int | str, default 3
        AIAG PPAP Submission Level (1–5).

    Returns
    -------
    dict[str, Any]
        Dictionary containing element_id, element_name, level, requirement_code,
        legend_description, level_description, and standards basis.
    """
    if isinstance(element, bool):
        raise TypeError(f"element cannot be a boolean, got {element!r}")
    element_id: PPAPElementId
    if isinstance(element, int):
        if element in PPAP_ELEMENT_NUMBERS:
            element_id = PPAP_ELEMENT_NUMBERS[element]
        else:
            raise ValueError(f"Invalid element number: {element}. Must be 1–18.")
    elif isinstance(element, str):
        clean_elem = element.strip().lower()
        if clean_elem in PPAP_ELEMENT_ALIASES:
            element_id = PPAP_ELEMENT_ALIASES[clean_elem]
        else:
            raise ValueError(
                f"Invalid element: '{element}'. Must be a canonical AIAG PPAP element ID ('2.2.1'–'2.2.18'), number (1–18), or alias."
            )
    else:
        raise TypeError(f"element must be an int or str, got {type(element).__name__}")

    if isinstance(level, bool):
        raise TypeError(f"level cannot be a boolean, got {level!r}")
    int_level: SubmissionLevel
    if isinstance(level, int):
        if level in SUBMISSION_LEVELS:
            int_level = cast(SubmissionLevel, level)
        else:
            raise ValueError(f"Invalid level: {level}. Must be an integer 1–5.")
    elif isinstance(level, str):
        clean_lvl = level.strip().lower()
        if clean_lvl in SUBMISSION_LEVEL_ALIASES:
            int_level = SUBMISSION_LEVEL_ALIASES[clean_lvl]
        else:
            raise ValueError(f"Invalid level: '{level}'. Must be 1–5 or recognized alias.")
    else:
        raise TypeError(f"level must be an int or str, got {type(level).__name__}")

    req_code = _core_lookup_requirement(element_id, int_level)
    elem_name = PPAP_ELEMENT_NAMES[element_id]
    legend_desc = _core_requirement_legend(req_code)
    lvl_desc = _core_submission_level_description(int_level)

    return {
        "element_id": element_id,
        "element_name": elem_name,
        "level": int_level,
        "requirement_code": req_code,
        "legend_description": legend_desc,
        "level_description": lvl_desc,
        "basis": _STANDARDS_BASIS,
        "authority_notice": _AUTHORITY_NOTICE,
    }


def validate_psw(
    psw_data: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Part Submission Warrant (PSW) field dictionary containing up to 27 Appendix A numbered fields. "
                "If omitted or None, loads the standard reference benchmark Level 3 warrant. "
                "Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the "
                "customer's authorized representative per AIAG PPAP 4th Edition Section 5. "
                "This tool evaluates and reports supplier submission readiness only."
            ),
        ),
    ] = None,
    actual_test_data_supplied: Annotated[
        bool,
        Field(
            description=(
                "Whether actual quantitative/qualitative test results are attached. "
                "Per 4th Edition, blanket statements of conformance are unacceptable."
            ),
        ),
    ] = True,
    has_checking_aid: Annotated[
        bool | None,
        Field(
            description=(
                "Whether a checking aid is applicable for Fields 9 & 10. If None, inferred from psw_data."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Validate a Part Submission Warrant (PSW) against AIAG PPAP 4th Edition Appendix A rules.

    Deterministic FastMCP tool wrapping `quality_core.ppap.psw.validate_psw`.
    Validates up to 27 Appendix A form fields, checks conditional logic, rejects prohibited
    blanket statements of conformance, and evaluates warrant readiness.

    Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the
    customer's authorized representative per AIAG PPAP 4th Edition Section 5.
    This tool evaluates and reports supplier submission readiness only.

    Parameters
    ----------
    psw_data : dict[str, Any] | None, optional
        PSW field dictionary. If None, loads the Level 3 benchmark warrant.
    actual_test_data_supplied : bool, default True
        Whether actual test results are supplied.
    has_checking_aid : bool | None, optional
        Checking aid applicability override.

    Returns
    -------
    dict[str, Any]
        Structured dictionary containing verdict, fields breakdown, missing_fields, invalid_fields,
        blanket_statement_detected, and standards basis.
    """
    if psw_data is not None:
        if isinstance(psw_data, (str, list, int, bool)) or not isinstance(psw_data, dict):
            raise TypeError(f"psw_data must be a dictionary or None, got {type(psw_data).__name__}")

    if type(actual_test_data_supplied) is not bool:
        raise TypeError(
            f"actual_test_data_supplied must be a boolean, got {type(actual_test_data_supplied).__name__}"
        )

    if has_checking_aid is not None and type(has_checking_aid) is not bool:
        raise TypeError(
            f"has_checking_aid must be a boolean or None, got {type(has_checking_aid).__name__}"
        )

    # Empty dictionary input handling
    if psw_data == {}:
        res = _core_validate_psw(
            psw={},
            has_checking_aid=has_checking_aid,
        )
        payload = res.to_dict()
        if not actual_test_data_supplied:
            payload["blanket_statement_detected"] = True
            payload["blanket_statement_findings"].append(
                "Actual quantitative/qualitative test results not supplied per AIAG PPAP 4th Edition."
            )
            payload["verdict"] = "INCOMPLETE"
        payload["basis"] = _STANDARDS_BASIS
        payload["authority_notice"] = _AUTHORITY_NOTICE
        return payload

    data = SAMPLE_PSW_RECORD if psw_data is None else psw_data

    try:
        res = _core_validate_psw(
            psw=data,
            has_checking_aid=has_checking_aid,
        )
        payload = res.to_dict()
        if not actual_test_data_supplied:
            payload["blanket_statement_detected"] = True
            payload["blanket_statement_findings"].append(
                "Actual quantitative/qualitative test results not supplied per AIAG PPAP 4th Edition."
            )
            payload["verdict"] = "INCOMPLETE"
        payload["basis"] = _STANDARDS_BASIS
        payload["authority_notice"] = _AUTHORITY_NOTICE
        return payload
    except pydantic.ValidationError as exc:
        err_msgs: list[str] = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()))
            msg = clean_pydantic_message(err.get("msg", "invalid value"))
            where = f"Field '{loc}'" if loc else "Warrant"
            err_msgs.append(f"{where}: {msg}")
        return {
            "verdict": "INCOMPLETE",
            "fields": {},
            "missing_fields": [],
            "invalid_fields": [],
            "indeterminate_fields": [],
            "blanket_statement_detected": False,
            "blanket_statement_findings": [],
            "cross_consistency_findings": [],
            "customer_disposition_present": False,
            "customer_disposition_warning": None,
            "warnings": err_msgs,
            "standards_basis": _STANDARDS_BASIS,
            "basis": _STANDARDS_BASIS,
            "authority_notice": _AUTHORITY_NOTICE,
        }


def assess_ppap_capability(
    data: Annotated[
        list[list[float]] | list[float] | None,
        Field(
            description=(
                "Measurement observations as 1D list of individual readings or 2D list of subgroups. "
                "If omitted or None, loads the reference AIAG SPC 4th Ed benchmark capability dataset. "
                "Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the "
                "customer's authorized representative per AIAG PPAP 4th Edition Section 5. "
                "This tool evaluates and reports supplier submission readiness only."
            ),
        ),
    ] = None,
    usl: Annotated[
        float | None,
        Field(description="Upper Specification Limit for capability evaluation."),
    ] = None,
    lsl: Annotated[
        float | None,
        Field(description="Lower Specification Limit for capability evaluation."),
    ] = None,
    is_attribute: Annotated[
        bool,
        Field(
            description=(
                "Whether data is attribute/pass-fail. If True, variables capability indices (Ppk/Cpk) are rejected."
            ),
        ),
    ] = False,
    is_ongoing_stable_process: Annotated[
        bool,
        Field(
            description=(
                "When True, evaluates Cpk (within-subgroup capability) for ongoing stable processes; "
                "when False, evaluates Ppk (total variation initial capability) per §2.2.11."
            ),
        ),
    ] = False,
    customer_concurrence: Annotated[
        bool,
        Field(
            description=(
                "Whether customer concurrence was obtained for reduced sample size or alternative study methods."
            ),
        ),
    ] = False,
    alpha: Annotated[
        float,
        Field(description="Significance level for statistical confidence intervals (default 0.05)."),
    ] = 0.05,
) -> dict[str, Any]:
    """Assess initial process study capability indices against AIAG PPAP 4th Edition §2.2.11 criteria.

    Deterministic FastMCP tool wrapping `quality_core.ppap.process_study.assess_initial_process_study`.
    Evaluates Ppk/Cpk capability acceptance criteria bands, enforces stability gates, guards against
    attribute data misuse (§2.2.11.1 Note 2), and requires sample size adequacy (>= 100 samples / >= 25 subgroups).

    Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the
    customer's authorized representative per AIAG PPAP 4th Edition Section 5.
    This tool evaluates and reports supplier submission readiness only.

    Parameters
    ----------
    data : list[list[float]] | list[float] | None, optional
        Observations or subgroups. If None, loads the AIAG SPC benchmark dataset.
    usl : float | None, optional
        Upper Specification Limit.
    lsl : float | None, optional
        Lower Specification Limit.
    is_attribute : bool, default False
        Attribute data flag.
    is_ongoing_stable_process : bool, default False
        When True uses Cpk; when False uses Ppk.
    customer_concurrence : bool, default False
        Whether customer concurrence was obtained.
    alpha : float, default 0.05
        Significance level.

    Returns
    -------
    dict[str, Any]
        Structured capability assessment dictionary with verdict, index_type, index_value, band,
        required_action, rationales, citations, and standards basis.
    """
    for flag_name, flag_val in (
        ("is_attribute", is_attribute),
        ("is_ongoing_stable_process", is_ongoing_stable_process),
        ("customer_concurrence", customer_concurrence),
    ):
        if type(flag_val) is not bool:
            raise TypeError(f"{flag_name} must be a boolean, got {type(flag_val).__name__}")

    if usl is not None:
        if isinstance(usl, bool) or not isinstance(usl, (int, float)):
            raise TypeError(f"usl must be a number or None, got {type(usl).__name__}")
    if lsl is not None:
        if isinstance(lsl, bool) or not isinstance(lsl, (int, float)):
            raise TypeError(f"lsl must be a number or None, got {type(lsl).__name__}")

    if usl is not None and lsl is not None and float(lsl) >= float(usl):
        raise ValueError(f"lsl ({lsl}) must be strictly less than usl ({usl}).")

    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
        raise TypeError(f"alpha must be a float, got {type(alpha).__name__}")
    if float(alpha) <= 0.0 or float(alpha) >= 1.0:
        raise ValueError(f"alpha must be between 0.0 and 1.0 (exclusive), got {alpha}")

    if data is not None:
        if isinstance(data, (str, dict, int, bool)) or not isinstance(data, list):
            raise TypeError(f"data must be a list or None, got {type(data).__name__}")
        for idx, item in enumerate(data):
            if isinstance(item, list):
                for sub_idx, val in enumerate(item):
                    if isinstance(val, bool) or not isinstance(val, (int, float)):
                        raise TypeError(
                            f"data element at [{idx}][{sub_idx}] must be a number, got {type(val).__name__}"
                        )
            elif isinstance(item, bool) or not isinstance(item, (int, float)):
                raise TypeError(f"data element at index {idx} must be a number, got {type(item).__name__}")

    # Empty data handling
    if data == []:
        return {
            "verdict": "INDETERMINATE",
            "index_type": None,
            "index_value": None,
            "band": None,
            "required_action": ACTION_INSUFFICIENT_SAMPLE,
            "rationales": [
                "No measurement data provided for initial process study.",
                "AIAG PPAP 4th Edition §2.2.11 requires variables measurement observations.",
            ],
            "citations": [
                "AIAG PPAP 4th Edition §2.2.11",
            ],
            "stable": None,
            "violations": None,
            "sample_size": 0,
            "subgroup_count": None,
            "is_attribute": is_attribute,
            "customer_concurrence": customer_concurrence,
            "standards_basis": _STANDARDS_BASIS,
            "basis": _STANDARDS_BASIS,
            "authority_notice": _AUTHORITY_NOTICE,
        }

    target_data = SAMPLE_PROCESS_STUDY_DATA if data is None else data
    target_usl = 10.5 if (usl is None and data is None) else usl
    target_lsl = 9.5 if (lsl is None and data is None) else lsl

    res = _core_assess_initial_process_study(
        data=target_data,
        usl=target_usl,
        lsl=target_lsl,
        is_attribute=is_attribute,
        is_ongoing_stable_process=is_ongoing_stable_process,
        customer_concurrence=customer_concurrence,
        alpha=float(alpha),
    )
    payload = res.to_dict()
    payload["basis"] = _STANDARDS_BASIS
    payload["authority_notice"] = _AUTHORITY_NOTICE
    return payload


def render_ppap_canvas(
    elements: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional list of PPAP element evidence dictionaries. "
                "If omitted or None, loads the standard reference Level 3 automotive sample dataset. "
                "Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the "
                "customer's authorized representative per AIAG PPAP 4th Edition Section 5. "
                "This tool evaluates and reports supplier submission readiness only."
            ),
        ),
    ] = None,
    package: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Optional complete PPAP package dictionary with submission metadata and element evidence."
            ),
        ),
    ] = None,
    submission_level: Annotated[
        int | str,
        Field(description="AIAG PPAP Submission Level (1–5). Default is 3."),
    ] = 3,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "AIAG PPAP 4th Edition Checklist Canvas",
    theme: Annotated[
        str,
        Field(description="Color theme: 'dark' (default) or 'light'."),
    ] = "dark",
    standalone: Annotated[
        bool,
        Field(
            description=(
                "If True, returns a complete standalone HTML document; if False, returns an embeddable container."
            ),
        ),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive visual HTML matrix canvas for an AIAG PPAP 4th Edition submission package.

    Deterministic FastMCP tool wrapping `quality_core.canvas.ppap.PPAPCanvas`.
    Renders the 18-element Table 4.1 requirement grid, displays submission readiness, and
    highlights active submission level requirements with responsive dark/light themes.

    Submission approval status (Approved, Interim Approval, Rejected) is assigned exclusively by the
    customer's authorized representative per AIAG PPAP 4th Edition Section 5.
    This tool evaluates and reports supplier submission readiness only.

    Parameters
    ----------
    elements : list[dict[str, Any]] | None, optional
        List of PPAP element evidence dictionaries. If None, loads the Level 3 benchmark sample.
    package : dict[str, Any] | None, optional
        Full package dictionary with submission metadata and elements.
    submission_level : int | str, default 3
        AIAG PPAP Submission Level (1–5).
    title : str, default "AIAG PPAP 4th Edition Checklist Canvas"
        Canvas header title.
    theme : str, default "dark"
        Color theme ('dark' or 'light').
    standalone : bool, default True
        Whether to generate a full standalone HTML5 document or embeddable container.

    Returns
    -------
    dict[str, Any]
        Dictionary containing title, rows_count, submission_level, summary dictionary,
        html string, and standards basis.
    """
    if type(standalone) is not bool:
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if isinstance(title, bool) or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if isinstance(theme, bool) or not isinstance(theme, str):
        raise TypeError(f"theme must be a string, got {type(theme).__name__}: {theme!r}")
    if theme not in ("dark", "light"):
        raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

    if isinstance(submission_level, bool):
        raise TypeError(f"submission_level cannot be a boolean, got {submission_level!r}")
    eff_lvl: SubmissionLevel
    if isinstance(submission_level, int):
        if submission_level in SUBMISSION_LEVELS:
            eff_lvl = cast(SubmissionLevel, submission_level)
        else:
            raise ValueError(f"submission_level must be an integer 1–5, got {submission_level}")
    elif isinstance(submission_level, str):
        clean_lvl = submission_level.strip().lower()
        if clean_lvl in SUBMISSION_LEVEL_ALIASES:
            eff_lvl = SUBMISSION_LEVEL_ALIASES[clean_lvl]
        else:
            raise ValueError(f"Invalid submission_level: '{submission_level}'. Must be 1–5 or recognized alias.")
    else:
        raise TypeError(f"submission_level must be an int or str, got {type(submission_level).__name__}")

    if elements is not None:
        if isinstance(elements, (str, dict, int, bool)) or not isinstance(elements, list):
            raise TypeError(f"elements must be a list of dictionaries or None, got {type(elements).__name__}")
        for idx, item in enumerate(elements):
            if not isinstance(item, dict):
                raise TypeError(f"elements item at index {idx} must be a dict, got {type(item).__name__}")

    if package is not None:
        if isinstance(package, (str, list, int, bool)) or not isinstance(package, dict):
            raise TypeError(f"package must be a dictionary or None, got {type(package).__name__}")

    canvas: PPAPCanvas
    if elements is not None:
        canvas = PPAPCanvas(elements=cast(Any, elements), submission_level=eff_lvl, title=title)
    elif package is not None:
        canvas = PPAPCanvas(package=package, submission_level=eff_lvl, title=title)
    else:
        canvas = PPAPCanvas.load_sample(title=title, submission_level=eff_lvl)

    html_content = canvas.to_html(theme=theme, standalone=standalone)
    summary = canvas.get_summary()

    return {
        "title": canvas.title,
        "rows_count": len(canvas.rows),
        "submission_level": canvas.submission_level,
        "summary": summary,
        "html": html_content,
        "basis": _STANDARDS_BASIS,
        "authority_notice": _AUTHORITY_NOTICE,
    }

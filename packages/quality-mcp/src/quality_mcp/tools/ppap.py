"""
ppap.py
FastMCP tools for AIAG Production Part Approval Process (PPAP) 4th Edition.

Exposes deterministic 18-element PPAP package auditing, Table 4.1 retention/submission
requirement lookup, Part Submission Warrant (PSW) 27-field validation with blanket statement
detection, Initial Process Studies (§2.2.11) capability gate assessment, and responsive
interactive visual HTML checklist canvas matrix rendering from quality_core.ppap and
quality_core.canvas to AI agents and MCP client hosts.

Standards References:
- AIAG Production Part Approval Process (PPAP) Reference Manual, 4th Edition (June 2006):
  - Table 4.1 & Table 4.2 Submission and Retention Matrix (pp. 17–19)
  - Section 2.2 (§2.2.1–§2.2.18) Element Requirements
  - Section 2.2.11 Initial Process Studies (§2.2.11.1–§2.2.11.6)
  - Section 4 Submission Levels 1–5
  - Section 5 Part Submission Status (🔒 Customer Authority Invariant)
  - Appendix A Part Submission Warrant (PSW) Completion Instructions
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
    audit_ppap_package as _audit_ppap_package_core,
)
from quality_core.ppap.process_study import (
    ACTION_INSUFFICIENT_SAMPLE,
)
from quality_core.ppap.process_study import (
    assess_initial_process_study as _assess_initial_process_study_core,
)
from quality_core.ppap.psw import (
    PartSubmissionWarrant,
)
from quality_core.ppap.psw import (
    validate_psw as _validate_psw_core,
)
from quality_core.ppap.schema import (
    PPAP_ELEMENT_ALIASES,
    PPAP_ELEMENT_IDS,
    PPAP_ELEMENT_NAMES,
    PPAP_ELEMENT_NUMBERS,
    SUBMISSION_LEVEL_ALIASES,
    SUBMISSION_LEVELS,
    PPAPElementId,
    PPAPPackage,
    SubmissionLevel,
)
from quality_core.ppap.table_4_1 import (
    REQUIREMENT_CODES,
    TABLE_4_1_LEGEND,
    lookup_requirement,
    requirement_legend,
    submission_level_description,
)

__all__ = [
    "assess_ppap_capability",
    "audit_ppap_package",
    "lookup_ppap_requirement",
    "render_ppap_canvas",
    "validate_psw",
]

_STANDARDS_BASIS: str = "AIAG PPAP Reference Manual, 4th Edition (2006)"

# Deterministic benchmark capability study dataset (25 subgroups of size 5 = 125 samples, capable process)
_BENCHMARK_CAPABILITY_DATA: list[list[float]] = [
    [10.0305, 9.896, 10.075, 10.0941, 9.8049],
    [9.8698, 10.0128, 9.9684, 9.9983, 9.9147],
    [10.0879, 10.0778, 10.0066, 10.1127, 10.0468],
    [9.9141, 10.0369, 9.9041, 10.0878, 9.995],
    [9.9815, 9.9319, 10.1223, 9.9845, 9.9572],
    [9.9648, 10.0532, 10.0365, 10.0413, 10.0431],
    [10.2142, 9.9594, 9.9488, 9.9186, 10.0616],
    [10.1129, 9.9886, 9.916, 9.9176, 10.0651],
    [10.0743, 10.0543, 9.9334, 10.0232, 10.0117],
    [10.0219, 10.0871, 10.0224, 10.0679, 10.0068],
    [10.0289, 10.0631, 9.8543, 9.968, 9.953],
    [9.9361, 9.9725, 10.1495, 9.9134, 10.0968],
    [9.8317, 9.9665, 10.0163, 10.0586, 10.0711],
    [10.0793, 9.9651, 9.9538, 10.0858, 9.9809],
    [9.8724, 9.8867, 9.9081, 10.0497, 10.0142],
    [10.069, 9.9573, 10.0159, 10.0626, 9.9691],
    [10.0457, 9.9338, 9.9637, 9.9618, 9.8804],
    [10.0487, 9.9531, 10.0012, 10.0481, 10.0447],
    [10.0665, 9.9902, 9.9577, 9.992, 9.8313],
    [9.8553, 9.8677, 9.9003, 10.04, 9.9095],
    [9.9622, 10.1299, 9.9644, 10.0738, 9.9066],
    [9.9795, 9.905, 9.9661, 10.084, 9.8273],
    [10.0434, 10.0238, 9.9406, 9.8554, 10.0072],
    [9.9471, 10.0233, 10.0022, 10.1602, 9.9761],
    [9.8977, 10.0179, 10.022, 10.1359, 10.0835],
]

# Benchmark Part Submission Warrant (PSW) dataset matching AIAG Appendix A Level 3 submission
_BENCHMARK_PSW_DATA: dict[str, Any] = {
    "part_name": "Transmission Output Shaft",
    "customer_part_number": "TOS-8842-A",
    "part_drawing_number": "DWG-TOS-8842",
    "engineering_change_level": "Rev C",
    "engineering_change_date": "2026-01-15",
    "purchase_order_number": "PO-99281-2026",
    "part_weight_kg": 2.45,
    "checking_aid_number": "CHK-TOS-01",
    "checking_aid_change_level_date": "Rev B 2025-11-01",
    "organization_name": "Acme Precision Drivetrain Inc.",
    "organization_code": "V-12345",
    "organization_address": "100 Precision Way, Detroit, MI 48202",
    "customer_name": "Apex Motors Corporation",
    "customer_division": "Powertrain Division",
    "customer_contact": "Jane Doe, Senior Quality Engineer",
    "application": "6-Speed Automatic Transmission Model 6T70",
    "materials_reporting": "IMDS ID #12948281",
    "polymeric_parts_marking": "ISO 11469 / ISO 1043",
    "reason_for_submission": "Initial Submission",
    "submission_level": 3,
    "submission_results": {
        "dimensional": True,
        "material_functional": True,
        "appearance": True,
        "process_capability": True,
    },
    "declaration_of_conformance": True,
    "customer_tool_tagging": "Tag #TT-99821 applied per spec",
    "production_rate": 120.0,
    "production_duration_hours": 8.0,
    "explanation_comments": "Initial PPAP Level 3 submission for transmission output shaft production tooling.",
    "authorized_signature": "John Smith",
    "authorized_signature_name": "John Smith",
    "authorized_signature_title": "Quality Assurance Manager",
    "authorized_signature_date": "2026-02-01",
    "authorized_signature_phone": "+1-313-555-0199",
    "authorized_signature_email": "jsmith@acmeprecision.com",
}


def audit_ppap_package(
    package: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "PPAP package dictionary containing header metadata and 18-element evidence records. "
                "If None, falls back to the benchmark Level 3 automotive transmission shaft sample package."
            )
        ),
    ] = None,
    submission_level: Annotated[
        int | str | None,
        Field(
            description="PPAP submission level (1–5) per AIAG PPAP 4th Edition Section 4. If omitted, uses level specified in package or defaults to Level 3."
        ),
    ] = None,
    reason_for_submission: Annotated[
        str | None,
        Field(
            description="Reason for submission per AIAG PPAP 4th Edition Section 3 (e.g., 'INITIAL_SUBMISSION', 'ENGINEERING_CHANGE', 'TOOLING_CHANGE')."
        ),
    ] = None,
    has_design_responsibility: Annotated[
        bool | None,
        Field(description="Flag indicating if the organization has product design responsibility (§2.2.4 DFMEA)."),
    ] = None,
    appearance_item: Annotated[
        bool | None,
        Field(description="Flag indicating if the part is a designated appearance item (§2.2.13 AAR)."),
    ] = None,
    has_checking_aid: Annotated[
        bool | None,
        Field(description="Flag indicating if checking aids are used for the part (§2.2.16 Checking Aids)."),
    ] = None,
    customer_engineering_approval_required: Annotated[
        bool | None,
        Field(description="Flag indicating if customer engineering approval is required (§2.2.3)."),
    ] = None,
    master_sample_waived: Annotated[
        bool | None,
        Field(description="Flag indicating if master sample retention is waived by customer (§2.2.15)."),
    ] = None,
    is_bulk_material: Annotated[
        bool | None,
        Field(description="Flag indicating if product is a bulk material (Appendix F)."),
    ] = None,
    is_tire: Annotated[
        bool | None,
        Field(description="Flag indicating if product is a tire (Appendix G)."),
    ] = None,
    is_truck_industry: Annotated[
        bool | None,
        Field(description="Flag indicating if product is for the truck industry (Appendix H)."),
    ] = None,
    customer_level_4_requirements: Annotated[
        dict[str, str] | None,
        Field(description="Customer-defined requirement codes for Level 4 submissions."),
    ] = None,
    commodity_type: Annotated[
        str | None,
        Field(description="Commodity type classification."),
    ] = None,
) -> dict[str, Any]:
    """Audit an 18-element PPAP package for completeness and supplier submission readiness.

    Joins package evidence against AIAG PPAP 4th Edition Table 4.1 requirement codes and
    conditional applicability rules (§2.2.1–§2.2.18) across Submission Levels 1–5.

    Note on Customer Authority (Section 5): Part submission approval dispositions ('Approved',
    'Interim Approval', 'Rejected') are reserved exclusively for the authorized customer
    representative. This tool audits supplier submission readiness only (SUBMISSION_READY,
    NOT_READY, INDETERMINATE).
    """
    if package is not None and not isinstance(package, dict):
        raise TypeError(f"package must be a dict or None, got {type(package).__name__}")

    if submission_level is not None:
        if isinstance(submission_level, bool) or not isinstance(submission_level, (int, str)):
            raise TypeError(
                f"submission_level must be an integer (1–5) or string, got {type(submission_level).__name__}"
            )

    if reason_for_submission is not None:
        if isinstance(reason_for_submission, bool) or not isinstance(reason_for_submission, str):
            raise TypeError(
                f"reason_for_submission must be a string or None, got {type(reason_for_submission).__name__}"
            )

    bool_flags = [
        ("has_design_responsibility", has_design_responsibility),
        ("appearance_item", appearance_item),
        ("has_checking_aid", has_checking_aid),
        ("customer_engineering_approval_required", customer_engineering_approval_required),
        ("master_sample_waived", master_sample_waived),
        ("is_bulk_material", is_bulk_material),
        ("is_tire", is_tire),
        ("is_truck_industry", is_truck_industry),
    ]
    for flag_name, flag_val in bool_flags:
        if flag_val is not None and type(flag_val) is not bool:
            raise TypeError(f"{flag_name} must be a bool or None, got {type(flag_val).__name__}")

    if customer_level_4_requirements is not None and not isinstance(customer_level_4_requirements, dict):
        raise TypeError(
            f"customer_level_4_requirements must be a dict or None, got {type(customer_level_4_requirements).__name__}"
        )

    if commodity_type is not None and (isinstance(commodity_type, bool) or not isinstance(commodity_type, str)):
        raise TypeError(f"commodity_type must be a string or None, got {type(commodity_type).__name__}")

    pkg_payload: dict[str, Any]
    if package is None:
        pkg_payload = dict(SAMPLE_PPAP_PACKAGE)
    else:
        pkg_payload = package

    applicability_kwargs: dict[str, Any] = {}
    if has_design_responsibility is not None:
        applicability_kwargs["has_design_responsibility"] = has_design_responsibility
    if appearance_item is not None:
        applicability_kwargs["appearance_item"] = appearance_item
    if has_checking_aid is not None:
        applicability_kwargs["has_checking_aid"] = has_checking_aid
    if customer_engineering_approval_required is not None:
        applicability_kwargs["customer_engineering_approval_required"] = customer_engineering_approval_required
    if master_sample_waived is not None:
        applicability_kwargs["master_sample_waived"] = master_sample_waived
    if is_bulk_material is not None:
        applicability_kwargs["is_bulk_material"] = is_bulk_material
    if is_tire is not None:
        applicability_kwargs["is_tire"] = is_tire
    if is_truck_industry is not None:
        applicability_kwargs["is_truck_industry"] = is_truck_industry
    if customer_level_4_requirements is not None:
        applicability_kwargs["customer_level_4_requirements"] = customer_level_4_requirements
    if commodity_type is not None:
        applicability_kwargs["commodity_type"] = commodity_type

    try:
        audit_res = _audit_ppap_package_core(
            pkg_payload,
            submission_level=submission_level,
            reason_for_submission=reason_for_submission,
            **applicability_kwargs,
        )
        res_dict = audit_res.to_dict()
        res_dict["basis"] = _STANDARDS_BASIS
        return res_dict
    except pydantic.ValidationError as exc:
        errs = exc.errors()
        err_msg = str(errs[0].get("msg", "invalid value")) if errs else "invalid value"
        clean_msg = clean_pydantic_message(err_msg)
        raise ValueError(clean_msg) from exc


def lookup_ppap_requirement(
    element_id: Annotated[
        str | int | None,
        Field(
            description=(
                "Canonical PPAP element ID ('2.2.1'–'2.2.18'), element number (1–18), or name alias "
                "(e.g. 'dfmea', 'psw', 'control_plan'). If None, returns all 18 elements for the submission level."
            )
        ),
    ] = None,
    submission_level: Annotated[
        int | str,
        Field(
            description="PPAP submission level (1–5) or alias ('Level 1'–'Level 5'). Defaults to 3."
        ),
    ] = 3,
    code: Annotated[
        str | None,
        Field(
            description="Optional requirement code filter ('S', 'R', '*', 'CUSTOMER_DEFINED') or legend lookup code."
        ),
    ] = None,
) -> dict[str, Any]:
    """Look up AIAG PPAP 4th Edition Table 4.1 submission/retention requirement codes and legend.

    Provides deterministic retrieval of retention/submission requirement codes ('S' = Submit,
    'R' = Retain, '*' = Submit upon request) for any of the 18 PPAP elements (§2.2.1–§2.2.18)
    across Submission Levels 1–5, along with verbatim standard legend descriptions.

    Note on Customer Authority (Section 5): Submission status and final part approval are
    the customer's authority exclusively; Table 4.1 defines supplier submission expectations.
    """
    if type(submission_level) is bool or not isinstance(submission_level, (int, str)):
        raise TypeError(
            f"submission_level must be an integer (1–5) or string, got {type(submission_level).__name__}"
        )

    norm_level: SubmissionLevel
    if isinstance(submission_level, int):
        if submission_level in SUBMISSION_LEVELS:
            norm_level = cast(SubmissionLevel, submission_level)
        else:
            raise ValueError(f"Invalid submission level {submission_level!r}. Must be one of {SUBMISSION_LEVELS}.")
    else:
        clean_str = submission_level.strip().lower()
        if clean_str in SUBMISSION_LEVEL_ALIASES:
            norm_level = SUBMISSION_LEVEL_ALIASES[clean_str]
        else:
            raise ValueError(f"Invalid submission level {submission_level!r}. Must be 1–5 or recognized alias.")

    if element_id is not None:
        if type(element_id) is bool or not isinstance(element_id, (int, str)):
            raise TypeError(f"element_id must be a string, integer (1–18), or None, got {type(element_id).__name__}")

    code_filter: str | None = None
    if code is not None:
        if type(code) is bool or not isinstance(code, str):
            raise TypeError(f"code must be a string or None, got {type(code).__name__}")
        code_filter = code.strip().upper()
        if code_filter not in REQUIREMENT_CODES:
            raise ValueError(f"Invalid requirement code {code!r}. Must be one of {list(REQUIREMENT_CODES)}.")

    if element_id is not None:
        canon_id: PPAPElementId
        if isinstance(element_id, int):
            if element_id in PPAP_ELEMENT_NUMBERS:
                canon_id = PPAP_ELEMENT_NUMBERS[element_id]
            else:
                raise ValueError(f"Invalid element number {element_id}. Must be between 1 and 18.")
        else:
            clean_elem = element_id.strip().lower()
            if clean_elem in PPAP_ELEMENT_ALIASES:
                canon_id = PPAP_ELEMENT_ALIASES[clean_elem]
            else:
                raise ValueError(
                    f"Invalid element_id '{element_id}'. Must be a canonical ID ('2.2.1'–'2.2.18'), "
                    f"number (1–18), or recognized alias."
                )

        req_code = lookup_requirement(canon_id, norm_level)
        req_desc = requirement_legend(req_code)
        elem_name = PPAP_ELEMENT_NAMES[canon_id]

        return {
            "basis": _STANDARDS_BASIS,
            "submission_level": norm_level,
            "submission_level_description": submission_level_description(norm_level),
            "element_id": canon_id,
            "element_name": elem_name,
            "requirement_code": req_code,
            "requirement_description": req_desc,
            "legend": dict(TABLE_4_1_LEGEND),
        }

    # If element_id is None, return all elements for the level (optionally filtered by code)
    elements_list: list[dict[str, Any]] = []
    for elem_id in PPAP_ELEMENT_IDS:
        r_code = lookup_requirement(elem_id, norm_level)
        if code_filter is None or r_code == code_filter:
            elements_list.append({
                "element_id": elem_id,
                "element_name": PPAP_ELEMENT_NAMES[elem_id],
                "requirement_code": r_code,
                "requirement_description": requirement_legend(r_code),
            })

    return {
        "basis": _STANDARDS_BASIS,
        "submission_level": norm_level,
        "submission_level_description": submission_level_description(norm_level),
        "elements": elements_list,
        "total_elements": len(elements_list),
        "required_submit_count": sum(1 for e in elements_list if e["requirement_code"] == "S"),
        "required_retain_count": sum(1 for e in elements_list if e["requirement_code"] == "R"),
        "legend": dict(TABLE_4_1_LEGEND),
    }


def validate_psw(
    psw: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Part Submission Warrant field dictionary matching Appendix A (Fields 1–27) or aliases. "
                "If None, falls back to the benchmark sample PSW dataset."
            )
        ),
    ] = None,
    has_checking_aid: Annotated[
        bool | None,
        Field(description="Optional boolean indicating whether a checking aid is used for the part."),
    ] = None,
    package: Annotated[
        dict[str, Any] | None,
        Field(description="Optional PPAP package dictionary for cross-consistency verification."),
    ] = None,
) -> dict[str, Any]:
    """Validate Part Submission Warrant (PSW) fields per AIAG PPAP 4th Edition Appendix A.

    Evaluates all 27 Appendix A form fields, checks required fields, detects prohibited
    blanket statements of conformance ('meets all specs', '100% conforming', etc.), performs
    package/warrant cross-consistency checks, and flags customer disposition field usage.

    Note on Customer Authority (Section 5): Part submission approval dispositions ('Approved',
    'Interim Approval', 'Rejected') are reserved exclusively for the customer's authorized
    representative. Field 27 is for customer use only; warrant validation evaluates supplier
    form completeness and declaration readiness only.
    """
    if psw is not None and not isinstance(psw, dict):
        raise TypeError(f"psw must be a dict or None, got {type(psw).__name__}")

    if has_checking_aid is not None and type(has_checking_aid) is not bool:
        raise TypeError(f"has_checking_aid must be a bool or None, got {type(has_checking_aid).__name__}")

    if package is not None and not isinstance(package, dict):
        raise TypeError(f"package must be a dict or None, got {type(package).__name__}")

    psw_payload: dict[str, Any]
    if psw is None:
        psw_payload = dict(_BENCHMARK_PSW_DATA)
    else:
        psw_payload = psw

    pkg_instance: PPAPPackage | None = None
    if package is not None:
        try:
            pkg_instance = PPAPPackage(**package)
        except Exception:
            pkg_instance = None

    try:
        warrant_model = PartSubmissionWarrant(**psw_payload)
        val_res = _validate_psw_core(
            warrant_model,
            package=pkg_instance,
            has_checking_aid=has_checking_aid,
        )
        res_dict = val_res.to_dict()
        res_dict["basis"] = _STANDARDS_BASIS
        return res_dict
    except pydantic.ValidationError as exc:
        errs = exc.errors()
        err_msg = str(errs[0].get("msg", "invalid value")) if errs else "invalid value"
        clean_msg = clean_pydantic_message(err_msg)
        raise ValueError(clean_msg) from exc


def assess_ppap_capability(
    data: Annotated[
        list[float] | list[list[float]] | None,
        Field(
            description=(
                "Sample measurement data as 1D list of individual readings or 2D list of subgroups. "
                "If None and no precomputed index provided, loads the benchmark automotive machining capability dataset."
            )
        ),
    ] = None,
    lsl: Annotated[
        float | None,
        Field(description="Lower Specification Limit."),
    ] = None,
    usl: Annotated[
        float | None,
        Field(description="Upper Specification Limit."),
    ] = None,
    is_attribute: Annotated[
        bool,
        Field(description="Flag indicating attribute data. Per §2.2.11.1 Note 2, attribute data cannot yield Ppk/Cpk."),
    ] = False,
    is_ongoing_stable_process: Annotated[
        bool,
        Field(description="If True, evaluates Cpk (within-subgroup); otherwise evaluates Ppk (total variation)."),
    ] = False,
    violations: Annotated[
        list[dict[str, Any]] | None,
        Field(description="Optional list of control-chart out-of-control signals from stability assessment."),
    ] = None,
    customer_concurrence: Annotated[
        bool,
        Field(description="Flag indicating customer concurrence for alternative sample sizes, interim actions, or attribute data."),
    ] = False,
    custom_threshold_capable: Annotated[
        float,
        Field(description="Acceptance threshold for capable process (default 1.67 per §2.2.11.3)."),
    ] = 1.67,
    custom_threshold_potentially_capable: Annotated[
        float,
        Field(description="Acceptance threshold for potentially capable process (default 1.33 per §2.2.11.3)."),
    ] = 1.33,
    precomputed_index_type: Annotated[
        str | None,
        Field(description="Precomputed index type ('Ppk' or 'Cpk') when raw data is omitted."),
    ] = None,
    precomputed_index_value: Annotated[
        float | None,
        Field(description="Precomputed index value when raw data is omitted."),
    ] = None,
    precomputed_sample_size: Annotated[
        int | None,
        Field(description="Precomputed sample size when raw data is omitted."),
    ] = None,
    precomputed_subgroup_count: Annotated[
        int | None,
        Field(description="Precomputed subgroup count when raw data is omitted."),
    ] = None,
) -> dict[str, Any]:
    """Assess Initial Process Studies (§2.2.11) against AIAG PPAP 4th Edition capability criteria.

    Evaluates process capability (Ppk for initial studies, Cpk for known ongoing stable processes)
    against the AIAG acceptance threshold (Ppk/Cpk >= 1.67 for capable, 1.33–1.67 for potentially
    acceptable, < 1.33 for unacceptable), enforces stability rules (§2.2.11.4), sample adequacy
    gates (>= 100 samples / >= 25 subgroups), attribute data prohibition (§2.2.11.1 Note 2),
    and attaches standard-mandated action requirements.

    Note on Customer Authority (Section 5): For results between 1.33 and 1.67, or less than 1.33,
    corrective action plans and customer review/concurrence are required per AIAG PPAP 4th Edition.
    """
    if type(is_attribute) is not bool:
        raise TypeError(f"is_attribute must be a bool, got {type(is_attribute).__name__}")
    if type(is_ongoing_stable_process) is not bool:
        raise TypeError(f"is_ongoing_stable_process must be a bool, got {type(is_ongoing_stable_process).__name__}")
    if type(customer_concurrence) is not bool:
        raise TypeError(f"customer_concurrence must be a bool, got {type(customer_concurrence).__name__}")

    if lsl is not None and (type(lsl) is bool or not isinstance(lsl, (int, float))):
        raise TypeError(f"lsl must be a float or None, got {type(lsl).__name__}")
    if usl is not None and (type(usl) is bool or not isinstance(usl, (int, float))):
        raise TypeError(f"usl must be a float or None, got {type(usl).__name__}")

    if lsl is not None and usl is not None and float(lsl) >= float(usl):
        raise ValueError(f"LSL ({lsl}) must be strictly less than USL ({usl}).")

    if type(custom_threshold_capable) is bool or not isinstance(custom_threshold_capable, (int, float)):
        raise TypeError(f"custom_threshold_capable must be a number, got {type(custom_threshold_capable).__name__}")
    if type(custom_threshold_potentially_capable) is bool or not isinstance(
        custom_threshold_potentially_capable, (int, float)
    ):
        raise TypeError(
            f"custom_threshold_potentially_capable must be a number, got {type(custom_threshold_potentially_capable).__name__}"
        )

    if precomputed_index_type is not None:
        if type(precomputed_index_type) is bool or not isinstance(precomputed_index_type, str):
            raise TypeError(
                f"precomputed_index_type must be a string or None, got {type(precomputed_index_type).__name__}"
            )
        if precomputed_index_type not in ("Ppk", "Cpk"):
            raise ValueError(f"precomputed_index_type must be 'Ppk' or 'Cpk', got {precomputed_index_type!r}")

    if precomputed_index_value is not None:
        if type(precomputed_index_value) is bool or not isinstance(precomputed_index_value, (int, float)):
            raise TypeError(
                f"precomputed_index_value must be a number or None, got {type(precomputed_index_value).__name__}"
            )

    if precomputed_sample_size is not None:
        if type(precomputed_sample_size) is bool or not isinstance(precomputed_sample_size, int):
            raise TypeError(
                f"precomputed_sample_size must be an int or None, got {type(precomputed_sample_size).__name__}"
            )

    if precomputed_subgroup_count is not None:
        if type(precomputed_subgroup_count) is bool or not isinstance(precomputed_subgroup_count, int):
            raise TypeError(
                f"precomputed_subgroup_count must be an int or None, got {type(precomputed_subgroup_count).__name__}"
            )

    if violations is not None:
        if not isinstance(violations, list):
            raise TypeError(f"violations must be a list of dicts or None, got {type(violations).__name__}")
        for idx, item in enumerate(violations):
            if not isinstance(item, dict):
                raise TypeError(f"violations item at index {idx} must be a dict, got {type(item).__name__}")

    input_data: list[float] | list[list[float]] | Any | None = None
    if data is not None:
        if type(data) is bool or not isinstance(data, list):
            raise TypeError(f"data must be a list or None, got {type(data).__name__}")
        if len(data) == 0:
            return {
                "verdict": "INDETERMINATE",
                "index_type": None,
                "index_value": None,
                "band": None,
                "required_action": ACTION_INSUFFICIENT_SAMPLE,
                "rationales": [
                    "Sample size inadequate for initial study (n=0 < 100).",
                    "AIAG PPAP 4th Edition §2.2.11.1 Note 5 requires minimum 25 subgroups / 100 readings without customer concurrence.",
                ],
                "citations": [
                    "AIAG PPAP 4th Edition §2.2.11.1 Note 5",
                    "AIAG PPAP 4th Edition §2.2.11.2",
                ],
                "stable": None,
                "violations": None,
                "sample_size": 0,
                "subgroup_count": None,
                "is_attribute": is_attribute,
                "customer_concurrence": customer_concurrence,
                "basis": _STANDARDS_BASIS,
            }

        for idx, elem in enumerate(data):
            if isinstance(elem, list):
                for sub_idx, sub_elem in enumerate(elem):
                    if type(sub_elem) is bool or not isinstance(sub_elem, (int, float)):
                        raise TypeError(
                            f"data element at [{idx}][{sub_idx}] must be a number, got {type(sub_elem).__name__}"
                        )
            elif type(elem) is bool or not isinstance(elem, (int, float)):
                raise TypeError(
                    f"data element at index {idx} must be a number or list of numbers, got {type(elem).__name__}"
                )
        input_data = data
    elif precomputed_index_value is None and not is_attribute:
        input_data = _BENCHMARK_CAPABILITY_DATA
        if lsl is None and usl is None:
            lsl = 9.5
            usl = 10.5

    try:
        study_res = _assess_initial_process_study_core(
            data=input_data,
            lsl=lsl,
            usl=usl,
            is_attribute=is_attribute,
            is_ongoing_stable_process=is_ongoing_stable_process,
            violations=violations,
            customer_concurrence=customer_concurrence,
            custom_threshold_capable=float(custom_threshold_capable),
            custom_threshold_potentially_capable=float(custom_threshold_potentially_capable),
            precomputed_index_type=cast(Any, precomputed_index_type),
            precomputed_index_value=precomputed_index_value,
            precomputed_sample_size=precomputed_sample_size,
            precomputed_subgroup_count=precomputed_subgroup_count,
        )
        res_dict = study_res.to_dict()
        res_dict["basis"] = _STANDARDS_BASIS
        return res_dict
    except pydantic.ValidationError as exc:
        errs = exc.errors()
        err_msg = str(errs[0].get("msg", "invalid value")) if errs else "invalid value"
        clean_msg = clean_pydantic_message(err_msg)
        raise ValueError(clean_msg) from exc


def render_ppap_canvas(
    package: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Optional PPAP package dictionary or canvas elements dictionary. "
                "If None, loads the benchmark Level 3 automotive transmission shaft sample dataset."
            )
        ),
    ] = None,
    submission_level: Annotated[
        int | str,
        Field(
            description="Active submission level (1–5) to highlight on the canvas table. Defaults to 3."
        ),
    ] = 3,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "AIAG PPAP 4th Edition 18-Element Checklist Canvas",
    theme: Annotated[
        str,
        Field(description="Theme mode for styling: 'dark' or 'light'. Defaults to 'dark'."),
    ] = "dark",
    standalone: Annotated[
        bool,
        Field(description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive visual HTML checklist matrix canvas for a PPAP package.

    Visualizes the AIAG PPAP 4th Edition 18-element checklist matrix across Submission Levels 1–5,
    with active submission level column highlighting, evidence status badges, Table 4.1 requirement
    codes, element audit results, and summary KPI cards.

    Note on Customer Authority (Section 5): Dispositions 'Approved', 'Interim Approval', and
    'Rejected' are customer's authority exclusively per AIAG PPAP 4th Edition Section 5. The canvas
    reports supplier submission readiness (SUBMISSION_READY, NOT_READY, INDETERMINATE).
    """
    if type(standalone) is not bool:
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if type(title) is bool or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if type(theme) is bool or not isinstance(theme, str):
        raise TypeError(f"theme must be a string, got {type(theme).__name__}: {theme!r}")
    clean_theme = theme.strip().lower()
    if clean_theme not in ("dark", "light"):
        raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

    if type(submission_level) is bool or not isinstance(submission_level, (int, str)):
        raise TypeError(
            f"submission_level must be an integer (1–5) or string, got {type(submission_level).__name__}: {submission_level!r}"
        )

    if package is not None and not isinstance(package, dict):
        raise TypeError(f"package must be a dict or None, got {type(package).__name__}: {package!r}")

    canvas: PPAPCanvas
    if package is None:
        canvas = PPAPCanvas.load_sample(title=title, submission_level=submission_level)
    else:
        canvas = PPAPCanvas(package=package, title=title, submission_level=submission_level)

    html_content = canvas.to_html(theme=clean_theme, standalone=standalone)
    summary = canvas.get_summary()

    return {
        "title": canvas.title,
        "rows_count": len(canvas.elements),
        "submission_level": canvas.submission_level,
        "summary": summary,
        "html": html_content,
        "basis": _STANDARDS_BASIS,
    }

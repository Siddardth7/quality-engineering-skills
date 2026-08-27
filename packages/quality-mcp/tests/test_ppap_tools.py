"""
Unit and integration tests for quality_mcp PPAP FastMCP tools.

Exhaustively covers:
1. 100% line & branch coverage on quality_mcp.tools.ppap and related quality_mcp modules.
2. All 5 FastMCP tools: audit_ppap_package, lookup_ppap_requirement, validate_psw,
   assess_ppap_capability, render_ppap_canvas.
3. Schema generation: inspect typing annotations, Field descriptions, and default values.
4. Benchmark dataset fallbacks on None arguments.
5. Empty input handling returning fully-shaped INDETERMINATE/INCOMPLETE payloads.
6. 🔒 Mandatory Section 5 Customer Authority Invariant negative controls.
7. Type guard negative controls (invalid types, non-bool ints, empty strings, invalid levels,
   out-of-range thresholds, invalid spec limits).
8. FastMCP in-process client session round-trip tests with tool discovery and dual-payload parity.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Annotated, Any, get_args, get_origin, get_type_hints

import numpy as np
import pydantic
import pytest
import quality_mcp
import quality_mcp.tools
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from pydantic.fields import FieldInfo
from quality_core.ppap.process_study import (
    ACTION_INSUFFICIENT_SAMPLE,
)
from quality_mcp.server import mcp
from quality_mcp.tools.ppap import (
    _BENCHMARK_PSW_DATA,
    _STANDARDS_BASIS,
    assess_ppap_capability,
    audit_ppap_package,
    lookup_ppap_requirement,
    render_ppap_canvas,
    validate_psw,
)

# ===========================================================================
# 1. Module Exports and Metadata Tests
# ===========================================================================


def test_ppap_module_exports() -> None:
    """quality_mcp and quality_mcp.tools re-export all 5 PPAP tools."""
    tools_list = [
        "assess_ppap_capability",
        "audit_ppap_package",
        "lookup_ppap_requirement",
        "render_ppap_canvas",
        "validate_psw",
    ]
    for name in tools_list:
        assert hasattr(quality_mcp, name)
        assert hasattr(quality_mcp.tools, name)
        assert name in quality_mcp.__all__
        assert name in quality_mcp.tools.__all__


# ===========================================================================
# 2. Parameter Schema & Field Annotations Tests
# ===========================================================================


@pytest.mark.parametrize(
    "tool_fn",
    [
        audit_ppap_package,
        lookup_ppap_requirement,
        validate_psw,
        assess_ppap_capability,
        render_ppap_canvas,
    ],
)
def test_tool_signatures_have_annotated_field_descriptions(tool_fn: Any) -> None:
    """Every parameter of each PPAP tool must be Annotated with Field(description=...)."""
    sig = inspect.signature(tool_fn)
    hints = get_type_hints(tool_fn, include_extras=True)
    for param_name, param in sig.parameters.items():
        assert param_name in hints, f"{tool_fn.__name__}.{param_name} lacks type hint"
        annotated_type = hints[param_name]
        origin = get_origin(annotated_type)
        assert origin is Annotated, f"{tool_fn.__name__}.{param_name} is not Annotated, got {annotated_type}"
        args = get_args(annotated_type)
        field_infos = [arg for arg in args if isinstance(arg, FieldInfo)]
        assert len(field_infos) == 1, f"{tool_fn.__name__}.{param_name} lacks FieldInfo"
        assert field_infos[0].description, f"{tool_fn.__name__}.{param_name} has empty Field description"


# ===========================================================================
# 3. audit_ppap_package Tests
# ===========================================================================


def test_audit_ppap_package_benchmark_fallback() -> None:
    """Passing package=None triggers fallback to benchmark sample Level 3 package."""
    res = audit_ppap_package(None)
    assert isinstance(res, dict)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["submission_level"] == 3
    assert "elements" in res
    assert len(res["elements"]) == 18
    assert res["package_verdict"] in ("SUBMISSION_READY", "NOT_READY", "INDETERMINATE")


def test_audit_ppap_package_empty_input_handled() -> None:
    """Passing an empty dictionary returns a structured INDETERMINATE/NOT_READY audit payload."""
    res = audit_ppap_package({})
    assert isinstance(res, dict)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["package_verdict"] in ("NOT_READY", "INDETERMINATE")
    assert len(res["elements"]) == 18
    assert len(res["indeterminate_elements"]) > 0
    for elem in res["elements"].values():
        assert elem["verdict"] in ("MISSING", "INDETERMINATE", "NOT_APPLICABLE")


@pytest.mark.parametrize(
    "level",
    [1, 2, 3, 4, 5, "Level 1", "level 2", "Level 3", "level 4", "LEVEL 5"],
)
def test_audit_ppap_package_submission_levels(level: int | str) -> None:
    """audit_ppap_package handles all integer levels (1–5) and string aliases."""
    res = audit_ppap_package(None, submission_level=level)
    assert res["basis"] == _STANDARDS_BASIS
    assert 1 <= res["submission_level"] <= 5


def test_audit_ppap_package_conditional_applicability_overrides() -> None:
    """audit_ppap_package applies conditional override flags correctly."""
    # 1. Non-design responsible (DFMEA not applicable)
    res_no_design = audit_ppap_package(
        package=None,
        submission_level=3,
        reason_for_submission="Engineering Change(s)",
        has_design_responsibility=False,
    )
    assert res_no_design["basis"] == _STANDARDS_BASIS
    assert res_no_design["reason_for_submission"] == "Engineering Change(s)"
    assert res_no_design["elements"]["2.2.4"]["verdict"] == "NOT_APPLICABLE"

    # 2. Appearance item override
    res_aar = audit_ppap_package(package=None, appearance_item=True)
    assert res_aar["elements"]["2.2.13"]["applicability_verdict"] == "APPLICABLE"

    # 3. Checking aid override
    res_chk = audit_ppap_package(package=None, has_checking_aid=True)
    assert res_chk["elements"]["2.2.16"]["applicability_verdict"] == "APPLICABLE"

    # 4. Master sample waived
    res_ms = audit_ppap_package(package=None, master_sample_waived=True)
    assert res_ms["elements"]["2.2.15"]["verdict"] == "NOT_APPLICABLE"

    # 5. Customer engineering approval required
    res_cust_eng = audit_ppap_package(package=None, customer_engineering_approval_required=True)
    assert res_cust_eng["elements"]["2.2.3"]["applicability_verdict"] == "APPLICABLE"

    # 6. Bulk material, tire, truck industry commodity overrides
    res_bulk = audit_ppap_package(package=None, is_bulk_material=True)
    assert res_bulk["basis"] == _STANDARDS_BASIS

    res_tire = audit_ppap_package(package=None, is_tire=True)
    assert res_tire["basis"] == _STANDARDS_BASIS

    res_truck = audit_ppap_package(package=None, is_truck_industry=True)
    assert res_truck["basis"] == _STANDARDS_BASIS

    # 7. Level 4 customer-defined requirements
    res_l4 = audit_ppap_package(
        package=None,
        submission_level=4,
        customer_level_4_requirements={"2.2.1": "S", "2.2.2": "R"},
    )
    assert res_l4["submission_level"] == 4

    # 8. Commodity type
    res_comm = audit_ppap_package(package=None, commodity_type="fastener")
    assert res_comm["basis"] == _STANDARDS_BASIS


@pytest.mark.parametrize(
    ("invalid_kwargs", "expected_err", "match_str"),
    [
        ({"package": "not-a-dict"}, TypeError, "package must be a dict or None"),
        ({"package": 123}, TypeError, "package must be a dict or None"),
        ({"submission_level": True}, TypeError, "submission_level must be an integer"),
        ({"submission_level": False}, TypeError, "submission_level must be an integer"),
        ({"submission_level": [1]}, TypeError, "submission_level must be an integer"),
        ({"reason_for_submission": True}, TypeError, "reason_for_submission must be a string"),
        ({"reason_for_submission": 123}, TypeError, "reason_for_submission must be a string"),
        ({"has_design_responsibility": 1}, TypeError, "has_design_responsibility must be a bool"),
        ({"appearance_item": "yes"}, TypeError, "appearance_item must be a bool"),
        ({"has_checking_aid": 0}, TypeError, "has_checking_aid must be a bool"),
        ({"customer_engineering_approval_required": 1}, TypeError, "customer_engineering_approval_required must be a bool"),
        ({"master_sample_waived": "no"}, TypeError, "master_sample_waived must be a bool"),
        ({"is_bulk_material": 1}, TypeError, "is_bulk_material must be a bool"),
        ({"is_tire": "true"}, TypeError, "is_tire must be a bool"),
        ({"is_truck_industry": 1}, TypeError, "is_truck_industry must be a bool"),
        ({"customer_level_4_requirements": "not-a-dict"}, TypeError, "customer_level_4_requirements must be a dict"),
        ({"commodity_type": True}, TypeError, "commodity_type must be a string"),
        ({"commodity_type": 123}, TypeError, "commodity_type must be a string"),
    ],
)
def test_audit_ppap_package_type_guards(
    invalid_kwargs: dict[str, Any],
    expected_err: type[Exception],
    match_str: str,
) -> None:
    """Type guard negative controls for audit_ppap_package."""
    with pytest.raises(expected_err, match=match_str):
        audit_ppap_package(**invalid_kwargs)


def test_audit_ppap_package_validation_error_handling() -> None:
    """Core pydantic validation errors are sanitized to clean ValueErrors."""
    with pytest.raises(ValueError):
        audit_ppap_package(None, submission_level=99)

    with pytest.raises(ValueError):
        audit_ppap_package(package={"submission_level": 99})


# ===========================================================================
# 4. lookup_ppap_requirement Tests
# ===========================================================================


def test_lookup_ppap_requirement_all_elements_level_3() -> None:
    """When element_id is None, returns complete 18-element requirements table for Level 3."""
    res = lookup_ppap_requirement(None, submission_level=3)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["submission_level"] == 3
    assert res["total_elements"] == 18
    assert res["required_submit_count"] > 0
    assert res["required_retain_count"] > 0
    assert len(res["elements"]) == 18
    assert "legend" in res


def test_lookup_ppap_requirement_level_aliases() -> None:
    """lookup_ppap_requirement handles string submission level aliases."""
    res = lookup_ppap_requirement(None, submission_level="Level 3")
    assert res["submission_level"] == 3

    res1 = lookup_ppap_requirement(None, submission_level="level 1")
    assert res1["submission_level"] == 1

    res5 = lookup_ppap_requirement(None, submission_level="LEVEL 5")
    assert res5["submission_level"] == 5


@pytest.mark.parametrize("code_filter", ["S", "R", "*", "CUSTOMER_DEFINED"])
def test_lookup_ppap_requirement_code_filter(code_filter: str) -> None:
    """Filtering by requirement code returns only matching elements."""
    res = lookup_ppap_requirement(None, submission_level=3, code=code_filter)
    assert res["basis"] == _STANDARDS_BASIS
    for elem in res["elements"]:
        assert elem["requirement_code"] == code_filter


@pytest.mark.parametrize(
    ("element_id", "expected_canon_id", "expected_code"),
    [
        ("2.2.1", "2.2.1", "S"),
        ("  2.2.3  ", "2.2.3", "S"),
        (1, "2.2.1", "S"),
        ("dfmea", "2.2.4", "S"),
        ("pfmea", "2.2.6", "S"),
        ("psw", "2.2.18", "S"),
        (18, "2.2.18", "S"),
        ("control_plan", "2.2.7", "S"),
        ("aar", "2.2.13", "S"),
        ("process_flow", "2.2.5", "S"),
    ],
)
def test_lookup_ppap_requirement_single_element_resolution(
    element_id: str | int,
    expected_canon_id: str,
    expected_code: str,
) -> None:
    """Resolves single element by canonical ID, element number (1–18), or name alias."""
    res = lookup_ppap_requirement(element_id, submission_level=3)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["element_id"] == expected_canon_id
    assert res["requirement_code"] == expected_code
    assert "element_name" in res
    assert "requirement_description" in res
    assert "legend" in res


@pytest.mark.parametrize(
    ("invalid_kwargs", "expected_err", "match_str"),
    [
        ({"submission_level": True}, TypeError, "submission_level must be an integer"),
        ({"submission_level": 3.14}, TypeError, "submission_level must be an integer"),
        ({"submission_level": [3]}, TypeError, "submission_level must be an integer"),
        ({"submission_level": 0}, ValueError, "Invalid submission level"),
        ({"submission_level": 6}, ValueError, "Invalid submission level"),
        ({"submission_level": 99}, ValueError, "Invalid submission level"),
        ({"submission_level": "Level 99"}, ValueError, "Invalid submission level"),
        ({"submission_level": "invalid_str"}, ValueError, "Invalid submission level"),
        ({"element_id": True}, TypeError, "element_id must be a string"),
        ({"element_id": 3.14}, TypeError, "element_id must be a string"),
        ({"element_id": [1]}, TypeError, "element_id must be a string"),
        ({"element_id": 0}, ValueError, "Invalid element number"),
        ({"element_id": 19}, ValueError, "Invalid element number"),
        ({"element_id": "unknown_alias_xyz"}, ValueError, "Invalid element_id"),
        ({"code": True}, TypeError, "code must be a string"),
        ({"code": 123}, TypeError, "code must be a string"),
        ({"code": "INVALID_CODE"}, ValueError, "Invalid requirement code"),
    ],
)
def test_lookup_ppap_requirement_negative_controls(
    invalid_kwargs: dict[str, Any],
    expected_err: type[Exception],
    match_str: str,
) -> None:
    """Negative controls and type guards for lookup_ppap_requirement."""
    with pytest.raises(expected_err, match=match_str):
        lookup_ppap_requirement(**invalid_kwargs)


# ===========================================================================
# 5. validate_psw Tests
# ===========================================================================


def test_validate_psw_benchmark_fallback() -> None:
    """Passing psw=None triggers fallback to benchmark Level 3 transmission shaft PSW."""
    res = validate_psw(None)
    assert isinstance(res, dict)
    assert res["basis"] == _STANDARDS_BASIS
    assert len(res["fields"]) == 27
    assert res["verdict"] in ("COMPLETE", "INCOMPLETE")


def test_validate_psw_empty_input_handled() -> None:
    """Passing an empty dictionary returns a structured INCOMPLETE validation result."""
    res = validate_psw({})
    assert isinstance(res, dict)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["verdict"] == "INCOMPLETE"
    assert len(res["missing_fields"]) > 0


def test_validate_psw_with_checking_aid_and_package() -> None:
    """validate_psw verifies checking aid and package cross-consistency."""
    custom_psw = dict(_BENCHMARK_PSW_DATA)
    custom_psw["reason_for_submission"] = "Initial Submission"
    matching_pkg = {
        "part_name": "Transmission Output Shaft",
        "part_number": "TOS-8842-A",
        "customer_part_number": "TOS-8842-A",
        "customer_name": "Apex Motors Corporation",
        "submission_level": 3,
        "has_checking_aid": True,
        "elements": [
            {"element_id": "2.2.18", "status": "submitted", "element_name": "Part Submission Warrant"},
        ],
    }
    res = validate_psw(custom_psw, has_checking_aid=True, package=matching_pkg)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["verdict"] == "COMPLETE"


def test_validate_psw_invalid_package_handled() -> None:
    """Passing an invalid package dictionary falls back gracefully with pkg_instance=None."""
    custom_psw = dict(_BENCHMARK_PSW_DATA)
    res_bad_pkg = validate_psw(custom_psw, package={"elements": "not-a-list"})
    assert res_bad_pkg["basis"] == _STANDARDS_BASIS


def test_validate_psw_blanket_statement_detection() -> None:
    """validate_psw flags prohibited blanket statements of conformance."""
    blanket_psw = dict(_BENCHMARK_PSW_DATA)
    blanket_psw["explanation_comments"] = "Parts meet all specs and are 100% conforming."
    res = validate_psw(blanket_psw)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["blanket_statement_detected"] is True
    assert len(res["blanket_statement_findings"]) > 0


def test_validate_psw_customer_use_field_warning() -> None:
    """Field 27 populated by supplier triggers customer disposition warning."""
    cust_psw = dict(_BENCHMARK_PSW_DATA)
    cust_psw["customer_disposition"] = "Approved"
    cust_psw["customer_signature"] = "Customer Representative"
    res = validate_psw(cust_psw)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["customer_disposition_present"] is True
    assert res["customer_disposition_warning"] is not None


@pytest.mark.parametrize(
    ("invalid_kwargs", "expected_err", "match_str"),
    [
        ({"psw": "not-a-dict"}, TypeError, "psw must be a dict or None"),
        ({"psw": 123}, TypeError, "psw must be a dict or None"),
        ({"has_checking_aid": 1}, TypeError, "has_checking_aid must be a bool"),
        ({"has_checking_aid": "true"}, TypeError, "has_checking_aid must be a bool"),
        ({"package": "not-a-dict"}, TypeError, "package must be a dict or None"),
        ({"package": 123}, TypeError, "package must be a dict or None"),
    ],
)
def test_validate_psw_type_guards(
    invalid_kwargs: dict[str, Any],
    expected_err: type[Exception],
    match_str: str,
) -> None:
    """Type guard negative controls for validate_psw."""
    with pytest.raises(expected_err, match=match_str):
        validate_psw(**invalid_kwargs)


def test_validate_psw_validation_error_sanitized() -> None:
    """Pydantic validation errors in PSW model are caught and raised as clean ValueErrors."""
    bad_psw = {"part_weight_kg": "not-a-number"}
    with pytest.raises(ValueError):
        validate_psw(bad_psw)


# ===========================================================================
# 6. assess_ppap_capability Tests
# ===========================================================================


def test_assess_ppap_capability_benchmark_fallback() -> None:
    """Passing data=None without precomputed index loads benchmark capable dataset."""
    res = assess_ppap_capability(None)
    assert isinstance(res, dict)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["verdict"] == "ACCEPTABLE"
    assert res["index_type"] == "Ppk"
    assert res["index_value"] is not None
    assert res["index_value"] >= 1.67
    assert res["sample_size"] == 125
    assert res["stable"] is None


def test_assess_ppap_capability_benchmark_fallback_with_custom_specs() -> None:
    """Passing data=None with custom specs uses benchmark data with provided specs."""
    res = assess_ppap_capability(None, lsl=9.4, usl=10.6)
    assert isinstance(res, dict)
    assert res["verdict"] == "ACCEPTABLE"
    assert res["sample_size"] == 125


def test_assess_ppap_capability_empty_data_handled() -> None:
    """Passing data=[] returns structured INDETERMINATE payload with sample_size=0."""
    res = assess_ppap_capability(data=[])
    assert isinstance(res, dict)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["verdict"] == "INDETERMINATE"
    assert res["sample_size"] == 0
    assert res["index_value"] is None
    assert "Sample size inadequate" in res["rationales"][0]
    assert res["required_action"] == ACTION_INSUFFICIENT_SAMPLE


def test_assess_ppap_capability_1d_and_2d_data() -> None:
    """assess_ppap_capability supports both 1D list and 2D subgroups list."""
    rng = np.random.default_rng(42)
    data_2d = rng.normal(loc=10.0, scale=0.08, size=(25, 5)).tolist()
    data_1d = rng.normal(loc=10.0, scale=0.08, size=120).tolist()

    res_1d = assess_ppap_capability(data=data_1d, lsl=9.5, usl=10.5)
    assert res_1d["verdict"] == "ACCEPTABLE"
    assert res_1d["sample_size"] == 120

    res_2d = assess_ppap_capability(data=data_2d, lsl=9.5, usl=10.5)
    assert res_2d["verdict"] == "ACCEPTABLE"
    assert res_2d["sample_size"] == 125


def test_assess_ppap_capability_ongoing_stable_process_cpk() -> None:
    """When is_ongoing_stable_process=True, evaluates Cpk instead of Ppk."""
    rng = np.random.default_rng(42)
    data_2d = rng.normal(loc=10.0, scale=0.08, size=(25, 5)).tolist()
    res = assess_ppap_capability(
        data=data_2d,
        lsl=9.5,
        usl=10.5,
        is_ongoing_stable_process=True,
    )
    assert res["basis"] == _STANDARDS_BASIS
    assert res["index_type"] == "Cpk"
    assert res["verdict"] == "ACCEPTABLE"


def test_assess_ppap_capability_stability_violations() -> None:
    """Passing stability violations flags unstable process."""
    rng = np.random.default_rng(42)
    data_2d = rng.normal(loc=10.0, scale=0.08, size=(25, 5)).tolist()
    violations = [{"rule": 1, "index": 5, "description": "1 point > 3 sigma"}]
    res = assess_ppap_capability(
        data=data_2d,
        lsl=9.5,
        usl=10.5,
        violations=violations,
    )
    assert res["basis"] == _STANDARDS_BASIS
    assert res["stable"] is False
    assert res["verdict"] == "INDETERMINATE"
    assert len(res["violations"]) == 1


def test_assess_ppap_capability_attribute_prohibition() -> None:
    """is_attribute=True triggers §2.2.11.1 Note 2 attribute data prohibition."""
    res = assess_ppap_capability(is_attribute=True)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["is_attribute"] is True
    assert res["verdict"] == "NOT_APPLICABLE_ATTRIBUTE_DATA"
    assert any("attribute" in r.lower() for r in res.get("rationales", []))


@pytest.mark.parametrize(
    ("index_val", "expected_verdict", "expected_band"),
    [
        (1.85, "ACCEPTABLE", "GREATER_THAN_1_67"),
        (1.45, "POTENTIALLY_ACCEPTABLE", "BETWEEN_1_33_AND_1_67"),
        (1.10, "UNACCEPTABLE", "LESS_THAN_1_33"),
    ],
)
def test_assess_ppap_capability_precomputed_indices(
    index_val: float,
    expected_verdict: str,
    expected_band: str,
) -> None:
    """Evaluates precomputed Ppk indices against AIAG §2.2.11.3 criteria."""
    res = assess_ppap_capability(
        precomputed_index_type="Ppk",
        precomputed_index_value=index_val,
        precomputed_sample_size=125,
        precomputed_subgroup_count=25,
    )
    assert res["basis"] == _STANDARDS_BASIS
    assert res["verdict"] == expected_verdict
    assert res["band"] == expected_band
    assert res["index_value"] == index_val


def test_assess_ppap_capability_custom_thresholds() -> None:
    """Supports custom acceptance thresholds."""
    res = assess_ppap_capability(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.50,
        precomputed_sample_size=125,
        precomputed_subgroup_count=25,
        custom_threshold_capable=1.40,
        custom_threshold_potentially_capable=1.20,
    )
    assert res["verdict"] == "ACCEPTABLE"


@pytest.mark.parametrize(
    ("invalid_kwargs", "expected_err", "match_str"),
    [
        ({"is_attribute": 1}, TypeError, "is_attribute must be a bool"),
        ({"is_attribute": "yes"}, TypeError, "is_attribute must be a bool"),
        ({"is_ongoing_stable_process": 1}, TypeError, "is_ongoing_stable_process must be a bool"),
        ({"customer_concurrence": "true"}, TypeError, "customer_concurrence must be a bool"),
        ({"lsl": True}, TypeError, "lsl must be a float or None"),
        ({"lsl": "low"}, TypeError, "lsl must be a float or None"),
        ({"usl": True}, TypeError, "usl must be a float or None"),
        ({"usl": "high"}, TypeError, "usl must be a float or None"),
        ({"lsl": 10.5, "usl": 9.5}, ValueError, "LSL .* must be strictly less than USL"),
        ({"lsl": 10.0, "usl": 10.0}, ValueError, "LSL .* must be strictly less than USL"),
        ({"custom_threshold_capable": True}, TypeError, "custom_threshold_capable must be a number"),
        ({"custom_threshold_capable": "1.67"}, TypeError, "custom_threshold_capable must be a number"),
        ({"custom_threshold_potentially_capable": True}, TypeError, "custom_threshold_potentially_capable must be a number"),
        ({"custom_threshold_potentially_capable": "1.33"}, TypeError, "custom_threshold_potentially_capable must be a number"),
        ({"precomputed_index_type": 123}, TypeError, "precomputed_index_type must be a string"),
        ({"precomputed_index_type": True}, TypeError, "precomputed_index_type must be a string"),
        ({"precomputed_index_type": "Z_score"}, ValueError, "precomputed_index_type must be 'Ppk' or 'Cpk'"),
        ({"precomputed_index_value": True}, TypeError, "precomputed_index_value must be a number"),
        ({"precomputed_index_value": "1.5"}, TypeError, "precomputed_index_value must be a number"),
        ({"precomputed_sample_size": True}, TypeError, "precomputed_sample_size must be an int"),
        ({"precomputed_sample_size": "100"}, TypeError, "precomputed_sample_size must be an int"),
        ({"precomputed_sample_size": 100.5}, TypeError, "precomputed_sample_size must be an int"),
        ({"precomputed_subgroup_count": True}, TypeError, "precomputed_subgroup_count must be an int"),
        ({"precomputed_subgroup_count": "25"}, TypeError, "precomputed_subgroup_count must be an int"),
        ({"precomputed_subgroup_count": 25.5}, TypeError, "precomputed_subgroup_count must be an int"),
        ({"violations": "not-a-list"}, TypeError, "violations must be a list"),
        ({"violations": ["not-a-dict"]}, TypeError, "violations item at index 0 must be a dict"),
        ({"data": "not-a-list"}, TypeError, "data must be a list"),
        ({"data": True}, TypeError, "data must be a list"),
        ({"data": ["bad_element"]}, TypeError, "data element at index 0 must be a number"),
        ({"data": [True, 10.0]}, TypeError, "data element at index 0 must be a number"),
        ({"data": [[10.0, "bad_sub_elem"]]}, TypeError, "data element at \\[0\\]\\[1\\] must be a number"),
        ({"data": [[True, 10.0]]}, TypeError, "data element at \\[0\\]\\[0\\] must be a number"),
    ],
)
def test_assess_ppap_capability_negative_controls(
    invalid_kwargs: dict[str, Any],
    expected_err: type[Exception],
    match_str: str,
) -> None:
    """Type guard negative controls for assess_ppap_capability."""
    with pytest.raises(expected_err, match=match_str):
        assess_ppap_capability(**invalid_kwargs)


def test_assess_ppap_capability_pydantic_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pydantic validation errors in assess_ppap_capability are caught and raised as ValueErrors."""
    class DummyModel(pydantic.BaseModel):
        val: int

    def mock_core(*args: Any, **kwargs: Any) -> Any:
        DummyModel(val="not_an_int")  # type: ignore[arg-type]

    monkeypatch.setattr("quality_mcp.tools.ppap._assess_initial_process_study_core", mock_core)
    with pytest.raises(ValueError):
        assess_ppap_capability(data=[10.0, 10.1, 9.9, 10.0])


# ===========================================================================
# 7. render_ppap_canvas Tests
# ===========================================================================


def test_render_ppap_canvas_benchmark_fallback() -> None:
    """Passing package=None renders benchmark Level 3 transmission shaft canvas."""
    res = render_ppap_canvas(None)
    assert isinstance(res, dict)
    assert res["basis"] == _STANDARDS_BASIS
    assert res["title"] == "AIAG PPAP 4th Edition 18-Element Checklist Canvas"
    assert res["rows_count"] == 18
    assert res["submission_level"] == 3
    assert "<!DOCTYPE html>" in res["html"]
    assert "Level 3" in res["html"]


def test_render_ppap_canvas_embedded_and_themes() -> None:
    """Supports standalone=False and dark/light theme options."""
    res_dark_embed = render_ppap_canvas(None, theme="dark", standalone=False)
    assert "<!DOCTYPE html>" not in res_dark_embed["html"]

    res_light = render_ppap_canvas(None, theme="light", standalone=True)
    assert "<!DOCTYPE html>" in res_light["html"]


@pytest.mark.parametrize(
    ("invalid_kwargs", "expected_err", "match_str"),
    [
        ({"standalone": 1}, TypeError, "standalone must be a boolean"),
        ({"standalone": "true"}, TypeError, "standalone must be a boolean"),
        ({"title": 123}, TypeError, "title must be a string"),
        ({"title": True}, TypeError, "title must be a string"),
        ({"title": ""}, ValueError, "title must not be empty"),
        ({"title": "   "}, ValueError, "title must not be empty"),
        ({"theme": 123}, TypeError, "theme must be a string"),
        ({"theme": True}, TypeError, "theme must be a string"),
        ({"theme": "neon"}, ValueError, "theme must be 'dark' or 'light'"),
        ({"submission_level": True}, TypeError, "submission_level must be an integer"),
        ({"submission_level": 3.14}, TypeError, "submission_level must be an integer"),
        ({"package": "not-a-dict"}, TypeError, "package must be a dict or None"),
        ({"package": 123}, TypeError, "package must be a dict or None"),
    ],
)
def test_render_ppap_canvas_negative_controls(
    invalid_kwargs: dict[str, Any],
    expected_err: type[Exception],
    match_str: str,
) -> None:
    """Negative controls and type guards for render_ppap_canvas."""
    with pytest.raises(expected_err, match=match_str):
        render_ppap_canvas(**invalid_kwargs)


# ===========================================================================
# 8. 🔒 Section 5 Customer Authority Invariant Negative Controls
# ===========================================================================


@pytest.mark.parametrize(
    "tool_fn",
    [
        audit_ppap_package,
        lookup_ppap_requirement,
        validate_psw,
        assess_ppap_capability,
        render_ppap_canvas,
    ],
)
def test_section_5_customer_authority_docstring_and_invariant(tool_fn: Any) -> None:
    """Docstrings of all 5 tools must explicitly state the Section 5 Customer Authority Invariant."""
    doc = tool_fn.__doc__ or ""
    assert "Customer Authority" in doc
    assert "Section 5" in doc


def test_section_5_customer_authority_no_customer_approval_verdicts() -> None:
    """No tool returns customer approval dispositions ('Approved', 'Interim Approval', 'Rejected') as part verdicts."""
    forbidden_dispositions = {"Approved", "Interim Approval", "Rejected", "INTERIM_APPROVAL"}

    # 1. audit_ppap_package
    audit_res = audit_ppap_package(None)
    assert audit_res["package_verdict"] not in forbidden_dispositions
    assert audit_res["package_verdict"] in ("SUBMISSION_READY", "NOT_READY", "INDETERMINATE")

    # 2. validate_psw
    psw_res = validate_psw(None)
    assert psw_res["verdict"] not in forbidden_dispositions
    assert psw_res["verdict"] in ("COMPLETE", "INCOMPLETE", "INDETERMINATE")

    # 3. assess_ppap_capability
    cap_res = assess_ppap_capability(
        precomputed_index_type="Ppk",
        precomputed_index_value=1.85,
        precomputed_sample_size=125,
        precomputed_subgroup_count=25,
    )
    assert cap_res["verdict"] not in forbidden_dispositions
    assert cap_res["verdict"] in (
        "ACCEPTABLE",
        "POTENTIALLY_ACCEPTABLE",
        "UNACCEPTABLE",
        "INDETERMINATE",
        "NOT_APPLICABLE_ATTRIBUTE_DATA",
    )


# ===========================================================================
# 9. FastMCP In-Process Client Session Round-Trip & Dual Parity Tests
# ===========================================================================


def test_mcp_client_roundtrip_ppap_tools_discovery() -> None:
    """FastMCP in-process client session discovers all 5 PPAP tools with valid schemas."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools_response = await client.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]

            expected_tools = [
                "assess_ppap_capability",
                "audit_ppap_package",
                "lookup_ppap_requirement",
                "render_ppap_canvas",
                "validate_psw",
            ]
            for tool_name in expected_tools:
                assert tool_name in tool_names
                tool_def = next(t for t in tools_response.tools if t.name == tool_name)
                assert tool_def.description is not None
                assert "AIAG" in tool_def.description or "PPAP" in tool_def.description
                assert tool_def.inputSchema is not None

    asyncio.run(_run())


def test_mcp_client_roundtrip_audit_ppap_package_parity() -> None:
    """audit_ppap_package round-trip over client session verifies dual-payload parity."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool("audit_ppap_package", {"submission_level": 3})
            assert not result.isError
            assert result.structuredContent is not None
            assert len(result.content) == 1
            assert isinstance(result.content[0], TextContent)

            json_text = json.loads(result.content[0].text)
            assert result.structuredContent == json_text
            assert result.structuredContent["basis"] == _STANDARDS_BASIS
            assert result.structuredContent["submission_level"] == 3

    asyncio.run(_run())


def test_mcp_client_roundtrip_lookup_ppap_requirement_parity() -> None:
    """lookup_ppap_requirement round-trip over client session verifies dual-payload parity."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                "lookup_ppap_requirement",
                {"element_id": "2.2.4", "submission_level": 3},
            )
            assert not result.isError
            assert result.structuredContent is not None
            json_text = json.loads(result.content[0].text)
            assert result.structuredContent == json_text
            assert result.structuredContent["element_id"] == "2.2.4"
            assert result.structuredContent["requirement_code"] == "S"

    asyncio.run(_run())


def test_mcp_client_roundtrip_validate_psw_parity() -> None:
    """validate_psw round-trip over client session verifies dual-payload parity."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool("validate_psw", {})
            assert not result.isError
            assert result.structuredContent is not None
            json_text = json.loads(result.content[0].text)
            assert result.structuredContent == json_text
            assert result.structuredContent["verdict"] == "COMPLETE"
            assert result.structuredContent["basis"] == _STANDARDS_BASIS

    asyncio.run(_run())


def test_mcp_client_roundtrip_assess_ppap_capability_parity() -> None:
    """assess_ppap_capability round-trip over client session verifies dual-payload parity."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(
                "assess_ppap_capability",
                {
                    "precomputed_index_type": "Ppk",
                    "precomputed_index_value": 1.85,
                    "precomputed_sample_size": 125,
                    "precomputed_subgroup_count": 25,
                },
            )
            assert not result.isError
            assert result.structuredContent is not None
            json_text = json.loads(result.content[0].text)
            assert result.structuredContent == json_text
            assert result.structuredContent["verdict"] == "ACCEPTABLE"
            assert result.structuredContent["basis"] == _STANDARDS_BASIS

    asyncio.run(_run())


def test_mcp_client_roundtrip_render_ppap_canvas_parity() -> None:
    """render_ppap_canvas round-trip over client session verifies dual-payload parity."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool("render_ppap_canvas", {"submission_level": 3})
            assert not result.isError
            assert result.structuredContent is not None
            json_text = json.loads(result.content[0].text)
            assert result.structuredContent == json_text
            assert result.structuredContent["rows_count"] == 18
            assert "<!DOCTYPE html>" in result.structuredContent["html"]

    asyncio.run(_run())


def test_mcp_client_roundtrip_error_responses() -> None:
    """Passing invalid arguments over client session produces isError responses."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Invalid submission level on lookup
            res1 = await client.call_tool("lookup_ppap_requirement", {"submission_level": 99})
            assert res1.isError

            # 2. Inverted spec limits on capability
            res2 = await client.call_tool("assess_ppap_capability", {"lsl": 10.5, "usl": 9.5})
            assert res2.isError

            # 3. Invalid theme on canvas
            res3 = await client.call_tool("render_ppap_canvas", {"theme": "invalid_theme"})
            assert res3.isError

    asyncio.run(_run())

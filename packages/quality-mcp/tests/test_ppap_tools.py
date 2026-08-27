"""Unit and integration tests for quality_mcp FastMCP PPAP tools.

Tests 18-element package completeness auditing, Table 4.1 matrix lookup,
27-field Part Submission Warrant (PSW) schema validation, Section 2.2.11
Initial Process Studies capability assessment, visual canvas rendering,
and Section 5 Customer Authority Invariant enforcement.
"""

from __future__ import annotations

import asyncio
import inspect
import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from quality_mcp.server import mcp as server_mcp
from quality_mcp.tools.ppap import (
    _AUTHORITY_NOTICE,
    _STANDARDS_BASIS,
    SAMPLE_PSW_RECORD,
    assess_ppap_capability,
    audit_ppap_package,
    lookup_ppap_requirement,
    render_ppap_canvas,
    validate_psw,
)

# ==============================================================================
# 1. audit_ppap_package Tests
# ==============================================================================


def test_audit_ppap_package_default_benchmark() -> None:
    """audit_ppap_package() with default arguments runs against reference Level 3 automotive package."""
    result = audit_ppap_package()
    assert isinstance(result, dict)
    assert result["package_verdict"] == "SUBMISSION_READY"
    assert result["submission_level"] == 3
    assert result["reason_for_submission"] == "Initial Submission"
    assert len(result["elements"]) == 18
    assert result["verdict_counts"]["SUBMITTED"] >= 1
    assert result["basis"] == _STANDARDS_BASIS
    assert "AIAG PPAP" in result["standards_basis"]
    assert result["authority_notice"] == _AUTHORITY_NOTICE
    assert result["blocking_elements"] == []


def test_audit_ppap_package_submission_level_variations() -> None:
    """audit_ppap_package() handles integer and string submission levels."""
    # Integer levels 1..5
    for lvl in (1, 2, 3, 5):
        res = audit_ppap_package(submission_level=lvl)
        assert res["submission_level"] == lvl

    # String aliases
    res_str = audit_ppap_package(submission_level="Level 2")
    assert res_str["submission_level"] == 2
    res_alias = audit_ppap_package(submission_level="level_1")
    assert res_alias["submission_level"] == 1


def test_audit_ppap_package_reason_variations() -> None:
    """audit_ppap_package() handles reason strings with underscores or spaces."""
    res1 = audit_ppap_package(reason_for_submission="initial_submission")
    assert res1["reason_for_submission"] == "Initial Submission"

    res2 = audit_ppap_package(reason_for_submission="engineering_change")
    assert res2["reason_for_submission"] == "Engineering Change(s)"

    res3 = audit_ppap_package(reason_for_submission="Initial Submission")
    assert res3["reason_for_submission"] == "Initial Submission"

    res4 = audit_ppap_package(reason_for_submission="tooling_change")
    assert res4["reason_for_submission"] == "Tooling: Transfer, Replacement, Refurbishment, or additional"


def test_audit_ppap_package_applicability_flags() -> None:
    """audit_ppap_package() respects design responsibility, appearance, checking aid, and bulk flags."""
    # No design responsibility -> 2.2.4 (DFMEA) resolves applicability to NOT_APPLICABLE (2.2.1 Design Records is retained/applicable per AIAG)
    res_no_design = audit_ppap_package(has_design_responsibility=False)
    assert res_no_design["elements"]["2.2.4"]["applicability_verdict"] == "NOT_APPLICABLE"

    # Designated appearance item = False -> 2.2.13 resolves applicability to NOT_APPLICABLE
    res_no_app = audit_ppap_package(is_designated_appearance_item=False)
    assert res_no_app["elements"]["2.2.13"]["applicability_verdict"] == "NOT_APPLICABLE"

    # Checking aid = False -> 2.2.16 resolves applicability to NOT_APPLICABLE
    res_no_chk = audit_ppap_package(has_checking_aid=False)
    assert res_no_chk["elements"]["2.2.16"]["applicability_verdict"] == "NOT_APPLICABLE"

    # Bulk material = True -> 2.2.17 applicable
    res_bulk = audit_ppap_package(is_bulk_material=True)
    assert res_bulk["elements"]["2.2.17"]["applicability_verdict"] in ("APPLICABLE", "NOT_APPLICABLE", "INDETERMINATE")


def test_audit_ppap_package_level_4_requirements() -> None:
    """audit_ppap_package() handles Level 4 customer-defined requirement sets."""
    # Level 4 with specific requirements (canonical IDs and aliases)
    res_l4 = audit_ppap_package(
        submission_level=4,
        customer_requirement_set=["2.2.18", "psw", "2.2.7", "control_plan"],
    )
    assert res_l4["submission_level"] == 4
    assert res_l4["package_verdict"] in ("SUBMISSION_READY", "NOT_READY", "INDETERMINATE")

    # Level 4 without requirements -> INDETERMINATE
    res_l4_none = audit_ppap_package(submission_level=4, customer_requirement_set=None)
    assert res_l4_none["submission_level"] == 4
    assert res_l4_none["package_verdict"] == "INDETERMINATE"


def test_audit_ppap_package_custom_elements_list_and_dict() -> None:
    """audit_ppap_package() accepts custom element list and full package dictionary."""
    custom_elements = [
        {"element_id": "2.2.18", "evidence_status": "submitted", "artifact_ref": "PSW-001"},
        {"element_id": "2.2.1", "evidence_status": "submitted", "artifact_ref": "DWG-001"},
    ]
    res_list = audit_ppap_package(package=custom_elements, submission_level=1)
    assert res_list["submission_level"] == 1
    assert "elements" in res_list

    custom_pkg_dict = {
        "submission_level": 2,
        "reason_for_submission": "Engineering Change(s)",
        "elements": custom_elements,
    }
    res_dict = audit_ppap_package(package=custom_pkg_dict, submission_level=2)
    assert res_dict["submission_level"] == 2
    assert res_dict["reason_for_submission"] == "Engineering Change(s)"


def test_audit_ppap_package_empty_input_handling() -> None:
    """audit_ppap_package() returns fully-shaped INDETERMINATE structure on empty package."""
    for empty_val in ([], {}):
        res = audit_ppap_package(package=empty_val)
        assert res["package_verdict"] == "INDETERMINATE"
        assert res["blocking_elements"] == []
        assert res["verdict_counts"]["INDETERMINATE"] == 18
        assert len(res["elements"]) == 18
        assert res["basis"] == _STANDARDS_BASIS
        assert res["authority_notice"] == _AUTHORITY_NOTICE


def test_audit_ppap_package_pydantic_validation_error_recovery() -> None:
    """audit_ppap_package() recovers from invalid schema fields inside package dictionary."""
    # Passing valid tool-level submission_level but invalid element inside package
    res = audit_ppap_package(
        package={"elements": [{"element_id": "invalid_element_id_xyz", "evidence_status": "submitted"}]},
        submission_level=3,
    )
    assert res["package_verdict"] == "INDETERMINATE"
    assert "findings" in res
    assert res["basis"] == _STANDARDS_BASIS


def test_audit_ppap_package_type_guards() -> None:
    """audit_ppap_package() raises TypeError / ValueError on invalid parameter types."""
    # submission_level type guards
    with pytest.raises(TypeError, match="submission_level cannot be a boolean"):
        audit_ppap_package(submission_level=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="submission_level must be an integer 1–5"):
        audit_ppap_package(submission_level=99)
    with pytest.raises(ValueError, match="Invalid submission_level"):
        audit_ppap_package(submission_level="Level 99")
    with pytest.raises(TypeError, match="submission_level must be an int or str"):
        audit_ppap_package(submission_level=3.14)  # type: ignore[arg-type]

    # reason_for_submission type guards
    with pytest.raises(TypeError, match="reason_for_submission must be a string"):
        audit_ppap_package(reason_for_submission=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="reason_for_submission must be a string"):
        audit_ppap_package(reason_for_submission=123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid reason_for_submission"):
        audit_ppap_package(reason_for_submission="unknown_reason_xyz")

    # Boolean flag type guards
    with pytest.raises(TypeError, match="has_design_responsibility must be a boolean"):
        audit_ppap_package(has_design_responsibility="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="is_designated_appearance_item must be a boolean"):
        audit_ppap_package(is_designated_appearance_item=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="has_checking_aid must be a boolean"):
        audit_ppap_package(has_checking_aid=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="is_bulk_material must be a boolean"):
        audit_ppap_package(is_bulk_material=0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="has_customer_engineering_approval must be a boolean"):
        audit_ppap_package(has_customer_engineering_approval="true")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="has_master_sample must be a boolean"):
        audit_ppap_package(has_master_sample=[])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="is_catalog_or_blackbox must be a boolean"):
        audit_ppap_package(is_catalog_or_blackbox="no")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="is_extrapolated_material must be a boolean"):
        audit_ppap_package(is_extrapolated_material="no")  # type: ignore[arg-type]

    # customer_requirement_set type guards
    with pytest.raises(TypeError, match="customer_requirement_set must be a list"):
        audit_ppap_package(customer_requirement_set="2.2.18")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="customer_requirement_set item at index 0 must be a str"):
        audit_ppap_package(customer_requirement_set=[True])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="Invalid element ID in customer_requirement_set"):
        audit_ppap_package(customer_requirement_set=["invalid_id_xyz"])

    # package type guards
    with pytest.raises(TypeError, match="package must be a list, dict, or None"):
        audit_ppap_package(package="invalid_package_string")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="package element at index 0 must be a dict"):
        audit_ppap_package(package=["not_a_dict"])  # type: ignore[list-item]


# ==============================================================================
# 2. lookup_ppap_requirement Tests
# ==============================================================================


def test_lookup_ppap_requirement_canonical_and_aliases() -> None:
    """lookup_ppap_requirement() resolves canonical IDs, numbers, and aliases across levels."""
    # Canonical ID
    res1 = lookup_ppap_requirement(element="2.2.1", level=3)
    assert res1["element_id"] == "2.2.1"
    assert res1["element_name"] == "Design Records"
    assert res1["level"] == 3
    assert res1["requirement_code"] == "S"
    assert "legend_description" in res1
    assert "level_description" in res1
    assert res1["basis"] == _STANDARDS_BASIS
    assert res1["authority_notice"] == _AUTHORITY_NOTICE

    # Direct canonical string "2.2.18"
    res18 = lookup_ppap_requirement(element="2.2.18", level=1)
    assert res18["element_id"] == "2.2.18"
    assert res18["requirement_code"] == "S"

    # Number 18 -> PSW
    res2 = lookup_ppap_requirement(element=18, level=1)
    assert res2["element_id"] == "2.2.18"
    assert res2["element_name"] == "Part Submission Warrant (PSW)"
    assert res2["requirement_code"] == "S"

    # Alias 'dfmea' at Level 2 (retained)
    res3 = lookup_ppap_requirement(element="dfmea", level=2)
    assert res3["element_id"] == "2.2.4"
    assert res3["requirement_code"] == "R"

    # String level alias
    res4 = lookup_ppap_requirement(element="2.2.6", level="Level 1")
    assert res4["level"] == 1
    assert res4["requirement_code"] == "R"
    res5 = lookup_ppap_requirement(element="2.2.6", level="level_2")
    assert res5["level"] == 2


def test_lookup_ppap_requirement_type_guards() -> None:
    """lookup_ppap_requirement() raises TypeError / ValueError on invalid inputs."""
    # element type guards
    with pytest.raises(TypeError, match="element cannot be a boolean"):
        lookup_ppap_requirement(element=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid element number: 99"):
        lookup_ppap_requirement(element=99)
    with pytest.raises(ValueError, match="Invalid element: 'unknown_elem'"):
        lookup_ppap_requirement(element="unknown_elem")
    with pytest.raises(TypeError, match="element must be an int or str"):
        lookup_ppap_requirement(element=3.14)  # type: ignore[arg-type]

    # level type guards
    with pytest.raises(TypeError, match="level cannot be a boolean"):
        lookup_ppap_requirement(element="2.2.1", level=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Invalid level: 99"):
        lookup_ppap_requirement(element="2.2.1", level=99)
    with pytest.raises(ValueError, match="Invalid level: 'level_99'"):
        lookup_ppap_requirement(element="2.2.1", level="level_99")
    with pytest.raises(TypeError, match="level must be an int or str"):
        lookup_ppap_requirement(element="2.2.1", level=3.14)  # type: ignore[arg-type]


# ==============================================================================
# 3. validate_psw Tests
# ==============================================================================


def test_validate_psw_default_benchmark() -> None:
    """validate_psw() with default arguments validates reference Level 3 warrant."""
    res = validate_psw()
    assert res["verdict"] == "COMPLETE"
    assert len(res["fields"]) == 27
    assert res["missing_fields"] == []
    assert res["invalid_fields"] == []
    assert res["blanket_statement_detected"] is False
    assert res["basis"] == _STANDARDS_BASIS
    assert res["authority_notice"] == _AUTHORITY_NOTICE


def test_validate_psw_custom_dictionary_and_missing_fields() -> None:
    """validate_psw() identifies missing fields on incomplete warrant."""
    partial_psw = {
        "part_name": "Bracket",
        "customer_part_number": "PART-001",
        "submission_level": 3,
    }
    res = validate_psw(psw_data=partial_psw)
    assert res["verdict"] == "INCOMPLETE"
    assert len(res["missing_fields"]) > 0
    assert 3 in res["missing_fields"]  # Field 3: Part Drawing Number
    assert res["basis"] == _STANDARDS_BASIS


def test_validate_psw_empty_input_handling() -> None:
    """validate_psw() returns fully-shaped INCOMPLETE structure on empty dict."""
    res = validate_psw(psw_data={})
    assert res["verdict"] == "INCOMPLETE"
    assert len(res["missing_fields"]) == 22
    assert res["basis"] == _STANDARDS_BASIS
    assert res["authority_notice"] == _AUTHORITY_NOTICE

    # Empty dict with actual_test_data_supplied=False
    res_no_data = validate_psw(psw_data={}, actual_test_data_supplied=False)
    assert res_no_data["verdict"] == "INCOMPLETE"
    assert res_no_data["blanket_statement_detected"] is True


def test_validate_psw_blanket_statement_detection() -> None:
    """validate_psw() detects prohibited blanket statements of conformance."""
    blanket_psw = dict(SAMPLE_PSW_RECORD)
    blanket_psw["submission_results"] = "Parts conform to all drawing specifications."
    res = validate_psw(psw_data=blanket_psw, actual_test_data_supplied=False)
    assert res["blanket_statement_detected"] is True
    assert len(res["blanket_statement_findings"]) > 0


def test_validate_psw_customer_disposition_present() -> None:
    """validate_psw() flags supplier inclusion of customer disposition fields."""
    disp_psw = dict(SAMPLE_PSW_RECORD)
    disp_psw["customer_disposition"] = "Approved"
    res = validate_psw(psw_data=disp_psw)
    assert res["customer_disposition_present"] is True
    assert res["customer_disposition_warning"] is not None


def test_validate_psw_pydantic_validation_error_recovery() -> None:
    """validate_psw() catches pydantic ValidationError without crashing."""
    bad_data_psw = dict(SAMPLE_PSW_RECORD)
    bad_data_psw["part_weight_kg"] = "twenty_kilograms"  # float expected
    res = validate_psw(psw_data=bad_data_psw)
    assert res["verdict"] == "INCOMPLETE"
    assert len(res["warnings"]) > 0
    assert res["basis"] == _STANDARDS_BASIS


def test_validate_psw_type_guards() -> None:
    """validate_psw() raises TypeError on invalid argument types."""
    with pytest.raises(TypeError, match="psw_data must be a dictionary or None"):
        validate_psw(psw_data="not_a_dict")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="actual_test_data_supplied must be a boolean"):
        validate_psw(actual_test_data_supplied="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="has_checking_aid must be a boolean or None"):
        validate_psw(has_checking_aid="no")  # type: ignore[arg-type]


# ==============================================================================
# 4. assess_ppap_capability Tests
# ==============================================================================


def test_assess_ppap_capability_default_benchmark() -> None:
    """assess_ppap_capability() evaluates benchmark AIAG SPC dataset."""
    res = assess_ppap_capability()
    assert res["verdict"] in ("ACCEPTABLE", "POTENTIALLY_ACCEPTABLE", "NEEDS_IMPROVEMENT")
    assert res["index_type"] == "Ppk"
    assert res["index_value"] is not None
    assert res["sample_size"] == 125
    assert res["subgroup_count"] == 25
    assert res["basis"] == _STANDARDS_BASIS
    assert any("AIAG PPAP 4th Edition §2.2.11" in c for c in res["citations"])
    assert res["authority_notice"] == _AUTHORITY_NOTICE


def test_assess_ppap_capability_1d_observations_and_ongoing_process() -> None:
    """assess_ppap_capability() supports 1D observation lists and Cpk calculation."""
    from quality_mcp.tools.ppap import SAMPLE_PROCESS_STUDY_DATA

    flat_data = [x for sub in SAMPLE_PROCESS_STUDY_DATA for x in sub]
    res_1d = assess_ppap_capability(data=flat_data, usl=10.5, lsl=9.5)
    assert res_1d["sample_size"] == 125

    res_cpk = assess_ppap_capability(is_ongoing_stable_process=True)
    assert res_cpk["index_type"] == "Cpk"
    assert res_cpk["index_value"] is not None


def test_assess_ppap_capability_attribute_data_rejection() -> None:
    """assess_ppap_capability() rejects attribute data per §2.2.11.1 Note 2."""
    res = assess_ppap_capability(is_attribute=True)
    assert res["verdict"] == "NOT_APPLICABLE_ATTRIBUTE_DATA"
    assert "Attribute data" in res["rationales"][0]


def test_assess_ppap_capability_empty_and_insufficient_sample() -> None:
    """assess_ppap_capability() handles empty data and insufficient sample size."""
    # Empty data
    res_empty = assess_ppap_capability(data=[])
    assert res_empty["verdict"] == "INDETERMINATE"
    assert res_empty["sample_size"] == 0
    assert res_empty["basis"] == _STANDARDS_BASIS

    # Small sample (< 100 samples / < 25 subgroups) without customer concurrence
    small_data = [[10.0, 10.1, 9.9], [10.2, 10.0, 9.8]]
    res_small = assess_ppap_capability(data=small_data, usl=10.5, lsl=9.5, customer_concurrence=False)
    assert res_small["verdict"] == "INDETERMINATE"


def test_assess_ppap_capability_type_guards() -> None:
    """assess_ppap_capability() raises TypeError / ValueError on invalid inputs."""
    with pytest.raises(TypeError, match="is_attribute must be a boolean"):
        assess_ppap_capability(is_attribute="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="is_ongoing_stable_process must be a boolean"):
        assess_ppap_capability(is_ongoing_stable_process=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="customer_concurrence must be a boolean"):
        assess_ppap_capability(customer_concurrence=None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="usl must be a number or None"):
        assess_ppap_capability(usl="10.5")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="lsl must be a number or None"):
        assess_ppap_capability(lsl=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="lsl .* must be strictly less than usl"):
        assess_ppap_capability(usl=9.0, lsl=10.0)

    with pytest.raises(TypeError, match="alpha must be a float"):
        assess_ppap_capability(alpha="0.05")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="alpha must be between 0.0 and 1.0"):
        assess_ppap_capability(alpha=1.5)
    with pytest.raises(ValueError, match="alpha must be between 0.0 and 1.0"):
        assess_ppap_capability(alpha=-0.01)

    with pytest.raises(TypeError, match="data must be a list or None"):
        assess_ppap_capability(data="invalid_data")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="data element at index 0 must be a number"):
        assess_ppap_capability(data=["not_a_number"])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="data element at \\[0\\]\\[0\\] must be a number"):
        assess_ppap_capability(data=[["not_a_number"]])  # type: ignore[list-item]


# ==============================================================================
# 5. render_ppap_canvas Tests
# ==============================================================================


def test_render_ppap_canvas_default_benchmark() -> None:
    """render_ppap_canvas() renders default Level 3 benchmark matrix canvas."""
    res = render_ppap_canvas()
    assert res["title"] == "AIAG PPAP 4th Edition Checklist Canvas"
    assert res["rows_count"] == 18
    assert res["submission_level"] == 3
    assert "summary" in res
    assert "<!DOCTYPE html>" in res["html"]
    assert "AIAG PPAP" in res["html"]
    assert res["basis"] == _STANDARDS_BASIS
    assert res["authority_notice"] == _AUTHORITY_NOTICE


def test_render_ppap_canvas_themes_and_modes() -> None:
    """render_ppap_canvas() supports dark/light themes, string levels, and container standalone mode."""
    # Light theme with string level alias
    res_light = render_ppap_canvas(theme="light", submission_level="Level 2")
    assert "body" in res_light["html"]
    assert res_light["submission_level"] == 2

    # Non-standalone embeddable container
    res_embed = render_ppap_canvas(standalone=False)
    assert "<!DOCTYPE html>" not in res_embed["html"]
    assert "ppap-canvas-container" in res_embed["html"]


def test_render_ppap_canvas_custom_inputs() -> None:
    """render_ppap_canvas() accepts custom elements list and full package dictionary."""
    custom_elements = [
        {"element_id": "2.2.18", "evidence_status": "submitted", "artifact_ref": "PSW-001"},
    ]
    res1 = render_ppap_canvas(elements=custom_elements, submission_level=1, title="Custom PPAP")
    assert res1["title"] == "Custom PPAP"
    assert res1["submission_level"] == 1

    custom_pkg = {
        "submission_level": 2,
        "elements": custom_elements,
    }
    res2 = render_ppap_canvas(package=custom_pkg)
    assert res2["submission_level"] == 2


def test_render_ppap_canvas_type_guards() -> None:
    """render_ppap_canvas() raises TypeError / ValueError on invalid inputs."""
    with pytest.raises(TypeError, match="standalone must be a boolean"):
        render_ppap_canvas(standalone="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="title must be a string"):
        render_ppap_canvas(title=123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="title must not be empty"):
        render_ppap_canvas(title="   ")

    with pytest.raises(TypeError, match="theme must be a string"):
        render_ppap_canvas(theme=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="theme must be 'dark' or 'light'"):
        render_ppap_canvas(theme="blue")

    with pytest.raises(TypeError, match="submission_level cannot be a boolean"):
        render_ppap_canvas(submission_level=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="submission_level must be an integer 1–5"):
        render_ppap_canvas(submission_level=99)
    with pytest.raises(ValueError, match="Invalid submission_level"):
        render_ppap_canvas(submission_level="Level 99")
    with pytest.raises(TypeError, match="submission_level must be an int or str"):
        render_ppap_canvas(submission_level=3.14)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="elements must be a list"):
        render_ppap_canvas(elements="invalid_elements")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="elements item at index 0 must be a dict"):
        render_ppap_canvas(elements=["not_a_dict"])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="package must be a dictionary or None"):
        render_ppap_canvas(package=["not_a_dict"])  # type: ignore[arg-type]


# ==============================================================================
# 6. Section 5 Customer Authority Invariant Negative Controls
# ==============================================================================


def test_customer_authority_invariant_enforcement() -> None:
    """Verify that NO PPAP tool ever returns customer approval verdicts ('APPROVED', 'INTERIM_APPROVAL', 'REJECTED')."""
    disallowed_verdicts = {"APPROVED", "INTERIM_APPROVAL", "REJECTED"}

    # 1. audit_ppap_package
    audit_res = audit_ppap_package()
    assert audit_res["package_verdict"] not in disallowed_verdicts
    assert audit_res["authority_notice"] == _AUTHORITY_NOTICE
    assert audit_res["basis"] == _STANDARDS_BASIS

    # 2. validate_psw
    psw_res = validate_psw()
    assert psw_res["verdict"] not in disallowed_verdicts
    assert psw_res["authority_notice"] == _AUTHORITY_NOTICE
    assert psw_res["basis"] == _STANDARDS_BASIS

    # 3. assess_ppap_capability
    cap_res = assess_ppap_capability()
    assert cap_res["verdict"] not in disallowed_verdicts
    assert cap_res["authority_notice"] == _AUTHORITY_NOTICE
    assert cap_res["basis"] == _STANDARDS_BASIS

    # 4. Docstring & Field Invariant Verification
    for tool_fn in (
        audit_ppap_package,
        lookup_ppap_requirement,
        validate_psw,
        assess_ppap_capability,
        render_ppap_canvas,
    ):
        doc = inspect.getdoc(tool_fn)
        assert doc is not None
        assert "Section 5" in doc
        assert "customer's authorized representative" in doc


# ==============================================================================
# 7. Dual-Payload FastMCP In-Process Client-Server Session Tests
# ==============================================================================


def test_fastmcp_in_memory_ppap_tools_session() -> None:
    """Test calling all 5 PPAP tools over in-process FastMCP memory transport."""
    async def _run() -> None:
        async with create_connected_server_and_client_session(
            server_mcp._mcp_server,
        ) as client_session:
            # List tools
            tools_list_res = await client_session.list_tools()
            registered_tool_names = [tool.name for tool in tools_list_res.tools]
            assert "audit_ppap_package" in registered_tool_names
            assert "lookup_ppap_requirement" in registered_tool_names
            assert "validate_psw" in registered_tool_names
            assert "assess_ppap_capability" in registered_tool_names
            assert "render_ppap_canvas" in registered_tool_names

            # 1. Call audit_ppap_package
            audit_call = await client_session.call_tool("audit_ppap_package", arguments={})
            assert audit_call.content is not None
            assert len(audit_call.content) > 0
            audit_payload = json.loads(audit_call.content[0].text)  # type: ignore[attr-defined]
            assert audit_payload["submission_level"] == 3
            assert audit_payload["package_verdict"] == "SUBMISSION_READY"

            # 2. Call lookup_ppap_requirement
            lookup_call = await client_session.call_tool(
                "lookup_ppap_requirement", arguments={"element": "psw", "level": 3}
            )
            assert lookup_call.content is not None
            lookup_payload = json.loads(lookup_call.content[0].text)  # type: ignore[attr-defined]
            assert lookup_payload["element_id"] == "2.2.18"
            assert lookup_payload["requirement_code"] == "S"

            # 3. Call validate_psw
            psw_call = await client_session.call_tool("validate_psw", arguments={})
            assert psw_call.content is not None
            psw_payload = json.loads(psw_call.content[0].text)  # type: ignore[attr-defined]
            assert psw_payload["verdict"] == "COMPLETE"

            # 4. Call assess_ppap_capability
            cap_call = await client_session.call_tool("assess_ppap_capability", arguments={})
            assert cap_call.content is not None
            cap_payload = json.loads(cap_call.content[0].text)  # type: ignore[attr-defined]
            assert cap_payload["index_type"] == "Ppk"

            # 5. Call render_ppap_canvas
            canvas_call = await client_session.call_tool("render_ppap_canvas", arguments={})
            assert canvas_call.content is not None
            canvas_payload = json.loads(canvas_call.content[0].text)  # type: ignore[attr-defined]
            assert canvas_payload["rows_count"] == 18
            assert "html" in canvas_payload

    asyncio.run(_run())

"""
test_ppap_client_roundtrip.py
Integration tests proving in-process FastMCP client-server round-trip for all five PPAP tools.

Validates:
1. FastMCP server initialization, handshake, and tool discovery for all 5 AIAG PPAP 4th Edition
   tools: audit_ppap_package, lookup_ppap_requirement, validate_psw, assess_ppap_capability,
   render_ppap_canvas.
2. Three-way payload parity per tool over the benchmark (None) input: structuredContent ==
   JSON-deserialized content[0].text == a DIRECT quality_core.ppap / quality_core.canvas.ppap
   ENGINE call. The engine, not the quality_mcp.tools.ppap wrapper, is the comparison target:
   comparing the wire to the wrapper only proves FastMCP's serialization is faithful, never that
   the wrapper forwards its arguments and configuration to the engine correctly.
3. The chained Control Plan -> PPAP workflow, both halves in a single session (the proof of #105):
   a control plan that passes quality_core.controlplan validation is threaded into the §2.2.7
   Control Plan EvidenceItem as evidence_valid=True and resolves SUBMITTED, and the same plan
   carrying a tolerance violation (usl <= lsl) fails validation, is threaded as
   evidence_valid=False, resolves EVIDENCE_INVALID, and drives the package to NOT_READY.
4. In-process session error isolation: a malformed PPAP call does not corrupt the next call in the
   same session, and does not leak into a fresh session — both directions asserted.
5. Cross-domain non-contamination: PPAP calls interleaved with RCA (validate_5why) and SPC
   (calculate_spc_chart) calls return byte-identical results throughout, in both directions.
6. The Section 5 Customer Authority Invariant asserted AT THE WIRE: no serialized PPAP payload
   ever carries 'Approved', 'Interim Approval', or 'Rejected' as a verdict, and every
   package-level verdict comes from the supplier submission-readiness vocabulary.
"""

from __future__ import annotations

import asyncio
import copy
import json
from typing import Any, Iterator

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.canvas.ppap import SAMPLE_PPAP_PACKAGE, PPAPCanvas
from quality_core.ppap.auditor import audit_ppap_package as core_audit_ppap_package
from quality_core.ppap.process_study import (
    assess_initial_process_study as core_assess_initial_process_study,
)
from quality_core.ppap.psw import PartSubmissionWarrant
from quality_core.ppap.psw import validate_psw as core_validate_psw
from quality_core.ppap.schema import (
    PPAP_ELEMENT_IDS,
    PPAP_ELEMENT_NAMES,
    PPAPElementId,
    SubmissionLevel,
)
from quality_core.ppap.table_4_1 import (
    TABLE_4_1_LEGEND,
    lookup_requirement,
    requirement_legend,
    submission_level_description,
)
from quality_mcp.server import mcp
from quality_mcp.tools.ppap import _BENCHMARK_CAPABILITY_DATA, _BENCHMARK_PSW_DATA

_PPAP_TOOL_NAMES = (
    "audit_ppap_package",
    "lookup_ppap_requirement",
    "validate_psw",
    "assess_ppap_capability",
    "render_ppap_canvas",
)

# The literal basis echo quality_mcp.tools.ppap stamps on every payload. Written out rather than
# imported from the tool module on purpose: the tool's basis string is NOT the engine's own
# standards_basis (the engine says "AIAG PPAP 4th Edition (June 2006)"), so importing the constant
# would make the assertion tautological and a mutated echo would pass.
_PPAP_TOOL_BASIS = "AIAG PPAP Reference Manual, 4th Edition (2006)"

# The tool's own defaults for the benchmark (None) capability call, asserted here because the
# direct-engine comparison has to be fed the SAME configuration the tool forwards.
_BENCHMARK_CAPABILITY_LSL = 9.5
_BENCHMARK_CAPABILITY_USL = 10.5
_THRESHOLD_CAPABLE = 1.67
_THRESHOLD_POTENTIALLY_CAPABLE = 1.33

# render_ppap_canvas's default title / level / theme / standalone, needed for the same reason.
_CANVAS_DEFAULT_TITLE = "AIAG PPAP 4th Edition 18-Element Checklist Canvas"
_DEFAULT_SUBMISSION_LEVEL: SubmissionLevel = 3


# ---------------------------------------------------------------------------
# Chained Control Plan -> PPAP fixtures (§6)
#
# The control plan rows are the fixtures test_controlplan_tool.py already proves the
# quality_core.controlplan behaviour of: _VALID_PLAN_ROW passes schema validation, and the
# tolerance-violation variant (usl <= lsl) fails it with a "usl must be greater than lsl" finding.
# They are duplicated rather than imported because the quality-mcp test package has no conftest.py
# to factor them into and one test module may not import another by path.
# ---------------------------------------------------------------------------

_VALID_PLAN_ROW: dict[str, Any] = {
    "characteristic": "Bore Diameter",
    "measurement_method": "Bore gauge",
    "sample_size": 5,
    "frequency": "per shift",
    "reaction_plan": "Stop line; notify quality engineer.",
    "lsl": 24.90,
    "usl": 25.10,
    "target": 25.00,
    "recommended_chart": "Xbar-R",
    "source_cause_id": "F1::M1::C1",
    "sample_plan_is_placeholder": True,
}

# Injected defect: usl (24.90) <= lsl (25.10) violates the ControlPlanRow tolerance invariant.
# A single-field constraint violation on an otherwise complete row, deliberately NOT a missing
# key — a missing key would exercise a different, less specific validation path.
_BAD_PLAN_ROW: dict[str, Any] = {**_VALID_PLAN_ROW, "lsl": 25.10, "usl": 24.90}

_CONTROL_PLAN_ELEMENT_ID: PPAPElementId = "2.2.7"

# Both applicability flags are REQUIRED, not incidental. The benchmark package leaves §2.2.3
# (customer engineering approval) and §2.2.15 (master sample waiver) un-surveyed, which makes two
# elements INDETERMINATE — and the auditor resolves package INDETERMINATE *before* it ever reaches
# NOT_READY. Without these the invalid half would resolve INDETERMINATE and the chain would pass
# while proving nothing about the EVIDENCE_INVALID path.
_CHAIN_APPLICABILITY: dict[str, Any] = {
    "customer_engineering_approval_required": True,
    "master_sample_waived": False,
}


# ---------------------------------------------------------------------------
# Section 5 Customer Authority Invariant vocabulary (§7)
# ---------------------------------------------------------------------------

# AIAG PPAP 4th Edition Section 5 part submission statuses. These are the customer's authority
# exclusively; no PPAP tool may ever emit one as its own verdict.
_CUSTOMER_DISPOSITIONS = ("approved", "interim approval", "rejected")

# Any payload key whose name carries one of these markers is treated as verdict-bearing.
_VERDICT_KEY_MARKERS = ("verdict", "status", "readiness", "disposition")

# The supplier-readiness vocabulary the audit and the canvas are allowed to resolve to.
_PACKAGE_READINESS_VERDICTS = frozenset({"SUBMISSION_READY", "NOT_READY", "INDETERMINATE"})


def _walk_items(obj: Any) -> Iterator[tuple[str, Any]]:
    """Yield every (key, value) pair anywhere in a nested JSON-shaped payload."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key), value
            yield from _walk_items(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_items(item)


def _walk_strings(obj: Any) -> Iterator[str]:
    """Yield every string anywhere in a nested JSON-shaped payload."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_strings(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item)


def _parsed_payload(result: Any) -> dict[str, Any]:
    """Assert the single-TextContent wire shape and return the deserialized payload.

    Also asserts dual-payload parity (structuredContent == JSON of content[0].text) whenever the
    client surfaced a structuredContent at all; the guard is deliberate, since structuredContent
    is absent on some MCP client versions.
    """
    assert not result.isError
    assert len(result.content) == 1
    assert isinstance(result.content[0], TextContent)
    parsed: dict[str, Any] = json.loads(result.content[0].text)
    if hasattr(result, "structuredContent") and result.structuredContent is not None:
        assert result.structuredContent == parsed
    return parsed


def _with_basis(engine_payload: dict[str, Any]) -> dict[str, Any]:
    """Add the ``basis`` stamp the tool layer appends to a raw engine ``to_dict()``.

    The tool copies the engine result verbatim and adds exactly one key. Building the expected
    dict this way means any drift between the wire payload and the raw engine — a re-derived
    field, a dropped key, a rewritten rationale — fails the parity assertion.

    The result is pushed through one JSON round-trip because that is the only transformation the
    transport is entitled to make: PSW's ``fields`` map is keyed by int field number in Python and
    necessarily arrives string-keyed over the wire. Normalising key TYPE is not the same as
    normalising VALUES — every value still has to match the engine's exactly.
    """
    serialized: dict[str, Any] = json.loads(
        json.dumps({**engine_payload, "basis": _PPAP_TOOL_BASIS})
    )
    return serialized


def _expected_lookup_all(level: SubmissionLevel) -> dict[str, Any]:
    """Recompose lookup_ppap_requirement's whole-level payload from the raw Table 4.1 engine."""
    elements = [
        {
            "element_id": elem_id,
            "element_name": PPAP_ELEMENT_NAMES[elem_id],
            "requirement_code": lookup_requirement(elem_id, level),
            "requirement_description": requirement_legend(lookup_requirement(elem_id, level)),
        }
        for elem_id in PPAP_ELEMENT_IDS
    ]
    return {
        "basis": _PPAP_TOOL_BASIS,
        "submission_level": level,
        "submission_level_description": submission_level_description(level),
        "elements": elements,
        "total_elements": len(elements),
        "required_submit_count": sum(1 for e in elements if e["requirement_code"] == "S"),
        "required_retain_count": sum(1 for e in elements if e["requirement_code"] == "R"),
        "legend": dict(TABLE_4_1_LEGEND),
    }


def _control_plan_note(cp_payload: dict[str, Any]) -> str:
    """Compose the §2.2.7 evidence note from the Control Plan engine's OWN verdict and findings.

    Nothing is re-authored here: on a rejection the controlplan engine's schema_findings are
    carried through verbatim, so the auditor's §2.2.7 rationale ends up quoting the upstream
    engine rather than a string this test invented.
    """
    if cp_payload["valid"]:
        return "Control Plan accepted by quality_core.controlplan schema validation"
    return (
        "Control Plan rejected by quality_core.controlplan schema validation: "
        + "; ".join(cp_payload["schema_findings"])
    )


def _package_with_control_plan_evidence(*, evidence_valid: bool, note: str) -> dict[str, Any]:
    """Build the benchmark package with §2.2.7's EvidenceItem carrying a threaded CP verdict.

    Only the Control Plan element is touched; every other element keeps its benchmark value, so
    the §2.2.7 element is the only thing that can move the package verdict between the two halves.
    """
    package = copy.deepcopy(SAMPLE_PPAP_PACKAGE)
    element = next(
        e for e in package["elements"] if e["element_id"] == _CONTROL_PLAN_ELEMENT_ID
    )
    element["present"] = True
    element["evidence_valid"] = evidence_valid
    element["notes"] = note
    return package


def _assert_no_customer_disposition_verdict(payload: dict[str, Any]) -> None:
    """Assert no value anywhere in a serialized payload stands as a customer disposition.

    Two passes, because the disclaimer text legitimately NAMES the three dispositions while
    reserving them for the customer:
      1. no verdict-bearing key holds one of them, and
      2. no string ANYWHERE is one of them standing alone as a value.
    A disclaimer sentence survives both; a tool that resolved 'Approved' survives neither.
    """
    for key, value in _walk_items(payload):
        if not isinstance(value, str):
            continue
        normalized = value.strip().lower()
        if any(marker in key.lower() for marker in _VERDICT_KEY_MARKERS):
            assert normalized not in _CUSTOMER_DISPOSITIONS, (
                f"customer-authority leak: {key}={value!r}"
            )

    for text in _walk_strings(payload):
        assert text.strip().lower() not in _CUSTOMER_DISPOSITIONS, (
            f"customer-authority leak: bare disposition value {text!r}"
        )


# ---------------------------------------------------------------------------
# Cross-domain interleave fixtures (§5)
#
# AIAG SPC 4th Ed. machined shaft diameters — 10 subgroups of size 5, an in-control process.
# ---------------------------------------------------------------------------

_XBAR_R_DATA: list[list[float]] = [
    [10.1, 10.0, 9.9, 10.2, 9.8],
    [9.9, 10.1, 10.0, 10.0, 10.1],
    [10.2, 9.8, 10.1, 9.9, 10.0],
    [10.0, 10.0, 10.1, 10.2, 9.9],
    [9.8, 10.1, 10.0, 9.9, 10.2],
    [10.1, 10.2, 9.8, 10.0, 10.0],
    [10.0, 9.9, 10.1, 10.1, 10.0],
    [10.2, 10.0, 9.9, 10.1, 9.8],
    [9.9, 10.1, 10.0, 10.0, 10.2],
    [10.1, 9.8, 10.2, 10.0, 9.9],
]

_CROSS_DOMAIN_CALLS: tuple[tuple[str, str, dict[str, Any], dict[str, Any]], ...] = (
    (
        "RCA",
        "validate_5why",
        {},
        {"valid": True, "verdict": "ACCEPT"},
    ),
    (
        "SPC",
        "calculate_spc_chart",
        {"chart_type": "Xbar-R", "data": _XBAR_R_DATA},
        {"chart_type": "Xbar-R", "in_control": True},
    ),
)


# ==============================================================================
# 1. FastMCP Client Handshake & Tool Discovery
# ==============================================================================


def test_client_handshake_discovers_all_ppap_tools() -> None:
    """In-process client handshake discovers and validates schemas for all 5 PPAP tools."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            init_result = await client.initialize()
            assert init_result.serverInfo.name == "quality-mcp"

            tools_by_name = {t.name: t for t in (await client.list_tools()).tools}
            for name in _PPAP_TOOL_NAMES:
                assert name in tools_by_name

            # 1. audit_ppap_package — the package slot and the applicability flags the chained
            #    Control Plan workflow drives it through.
            audit_props = tools_by_name["audit_ppap_package"].inputSchema.get("properties", {})
            assert "package" in audit_props
            assert "submission_level" in audit_props
            assert "reason_for_submission" in audit_props
            assert "customer_engineering_approval_required" in audit_props
            assert "master_sample_waived" in audit_props

            # 2. lookup_ppap_requirement
            lookup_props = tools_by_name["lookup_ppap_requirement"].inputSchema.get(
                "properties", {}
            )
            assert "element_id" in lookup_props
            assert "submission_level" in lookup_props
            assert "code" in lookup_props

            # 3. validate_psw
            psw_props = tools_by_name["validate_psw"].inputSchema.get("properties", {})
            assert "psw" in psw_props
            assert "has_checking_aid" in psw_props
            assert "package" in psw_props

            # 4. assess_ppap_capability
            capability_props = tools_by_name["assess_ppap_capability"].inputSchema.get(
                "properties", {}
            )
            assert "data" in capability_props
            assert "lsl" in capability_props
            assert "usl" in capability_props
            assert "is_attribute" in capability_props
            assert "custom_threshold_capable" in capability_props

            # 5. render_ppap_canvas
            canvas_props = tools_by_name["render_ppap_canvas"].inputSchema.get("properties", {})
            assert "package" in canvas_props
            assert "submission_level" in canvas_props
            assert "title" in canvas_props
            assert "theme" in canvas_props
            assert "standalone" in canvas_props

    asyncio.run(_run())


# ==============================================================================
# 2. Individual Tool Round-Trip & Three-Way Parity (wire == text == direct ENGINE call)
# ==============================================================================


def test_audit_ppap_package_roundtrip_parity() -> None:
    """audit_ppap_package's wire payload equals a direct quality_core.ppap.auditor engine call."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            parsed = _parsed_payload(await client.call_tool("audit_ppap_package", {}))

            direct_engine = core_audit_ppap_package(dict(SAMPLE_PPAP_PACKAGE)).to_dict()
            assert parsed == _with_basis(direct_engine)
            assert parsed["basis"] == _PPAP_TOOL_BASIS
            assert parsed["package_verdict"] in _PACKAGE_READINESS_VERDICTS
            assert len(parsed["elements"]) == 18

    asyncio.run(_run())


def test_lookup_ppap_requirement_roundtrip_parity() -> None:
    """lookup_ppap_requirement's wire payload equals a direct Table 4.1 engine recomposition.

    Both shapes are covered: the whole-level listing (element_id omitted) and the single-element
    lookup, each rebuilt from quality_core.ppap.table_4_1 primitives rather than from the tool.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            parsed_all = _parsed_payload(await client.call_tool("lookup_ppap_requirement", {}))
            assert parsed_all == _expected_lookup_all(_DEFAULT_SUBMISSION_LEVEL)
            assert parsed_all["total_elements"] == 18

            parsed_one = _parsed_payload(
                await client.call_tool(
                    "lookup_ppap_requirement",
                    {"element_id": _CONTROL_PLAN_ELEMENT_ID, "submission_level": 3},
                )
            )
            expected_code = lookup_requirement(_CONTROL_PLAN_ELEMENT_ID, 3)
            assert parsed_one == {
                "basis": _PPAP_TOOL_BASIS,
                "submission_level": 3,
                "submission_level_description": submission_level_description(3),
                "element_id": _CONTROL_PLAN_ELEMENT_ID,
                "element_name": PPAP_ELEMENT_NAMES[_CONTROL_PLAN_ELEMENT_ID],
                "requirement_code": expected_code,
                "requirement_description": requirement_legend(expected_code),
                "legend": dict(TABLE_4_1_LEGEND),
            }

    asyncio.run(_run())


def test_validate_psw_roundtrip_parity() -> None:
    """validate_psw's wire payload equals a direct quality_core.ppap.psw engine call."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            parsed = _parsed_payload(await client.call_tool("validate_psw", {}))

            direct_engine = core_validate_psw(
                PartSubmissionWarrant(**_BENCHMARK_PSW_DATA),
                package=None,
                has_checking_aid=None,
            ).to_dict()
            assert parsed == _with_basis(direct_engine)
            assert parsed["basis"] == _PPAP_TOOL_BASIS
            assert parsed["verdict"] == "COMPLETE"

    asyncio.run(_run())


def test_assess_ppap_capability_roundtrip_parity() -> None:
    """assess_ppap_capability's wire payload equals a direct process_study engine call.

    The direct call is fed the tool's own benchmark dataset AND the tool's own default spec
    limits and acceptance thresholds, because the parity claim is that the tool forwards its
    configuration unchanged — not merely that it calls the engine at all.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            parsed = _parsed_payload(await client.call_tool("assess_ppap_capability", {}))

            direct_engine = core_assess_initial_process_study(
                data=_BENCHMARK_CAPABILITY_DATA,
                lsl=_BENCHMARK_CAPABILITY_LSL,
                usl=_BENCHMARK_CAPABILITY_USL,
                is_attribute=False,
                is_ongoing_stable_process=False,
                violations=None,
                customer_concurrence=False,
                custom_threshold_capable=_THRESHOLD_CAPABLE,
                custom_threshold_potentially_capable=_THRESHOLD_POTENTIALLY_CAPABLE,
                precomputed_index_type=None,
                precomputed_index_value=None,
                precomputed_sample_size=None,
                precomputed_subgroup_count=None,
            ).to_dict()
            assert parsed == _with_basis(direct_engine)
            assert parsed["basis"] == _PPAP_TOOL_BASIS
            assert parsed["index_type"] == "Ppk"
            assert parsed["sample_size"] == 125

    asyncio.run(_run())


def test_render_ppap_canvas_roundtrip_parity() -> None:
    """render_ppap_canvas's wire HTML and summary equal a direct quality_core.canvas.ppap render.

    Compared under exactly the tool's default title / submission level / theme / standalone
    arguments — any of them differing would make the comparison spuriously fail rather than
    meaningfully pass.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            parsed = _parsed_payload(await client.call_tool("render_ppap_canvas", {}))

            canvas = PPAPCanvas.load_sample(
                title=_CANVAS_DEFAULT_TITLE,
                submission_level=_DEFAULT_SUBMISSION_LEVEL,
            )
            assert parsed == {
                "title": canvas.title,
                "rows_count": len(canvas.elements),
                "submission_level": canvas.submission_level,
                "summary": canvas.get_summary(),
                "html": canvas.to_html(theme="dark", standalone=True),
                "basis": _PPAP_TOOL_BASIS,
            }
            assert parsed["rows_count"] == 18
            assert parsed["submission_level"] == _DEFAULT_SUBMISSION_LEVEL

    asyncio.run(_run())


# ==============================================================================
# 3. Chained Control Plan -> PPAP Workflow, Both Halves in One Session
# ==============================================================================


def test_chained_control_plan_to_ppap_valid_and_invalid_halves() -> None:
    """The Control Plan verdict, threaded by the client into §2.2.7, drives the PPAP audit.

    Valid half: a control plan that passes quality_core.controlplan schema validation is threaded
    into the §2.2.7 EvidenceItem as evidence_present=True / evidence_valid=True, and the auditor
    resolves §2.2.7 to the Table 4.1 Level 3 code's verdict (SUBMITTED for code 'S') — NOT MISSING.

    Invalid half: the SAME plan with a tolerance violation (usl 24.90 <= lsl 25.10) fails
    validation, is threaded as evidence_valid=False, and the auditor resolves §2.2.7 to
    EVIDENCE_INVALID and the package to NOT_READY — with the controlplan engine's own finding
    text surfaced verbatim in the §2.2.7 rationale rather than re-authored by the PPAP engine.

    Both halves run in ONE client session, and each audit is additionally checked against a
    direct engine call so a drifted wire payload cannot pass as a correct chain.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # --- Valid half -------------------------------------------------------------
            cp_valid = _parsed_payload(
                await client.call_tool("validate_control_plan", {"plan": [_VALID_PLAN_ROW]})
            )
            assert cp_valid["valid"] is True
            assert cp_valid["schema_valid"] is True
            assert cp_valid["schema_findings"] == []

            # The client THREADS the upstream verdict — nothing is hardcoded True here.
            valid_package = _package_with_control_plan_evidence(
                evidence_valid=cp_valid["valid"],
                note=_control_plan_note(cp_valid),
            )
            valid_evidence = next(
                e
                for e in valid_package["elements"]
                if e["element_id"] == _CONTROL_PLAN_ELEMENT_ID
            )
            assert valid_evidence["present"] is True
            assert valid_evidence["evidence_valid"] is True

            valid_audit = _parsed_payload(
                await client.call_tool(
                    "audit_ppap_package",
                    {"package": valid_package, **_CHAIN_APPLICABILITY},
                )
            )
            valid_cp_element = valid_audit["elements"][_CONTROL_PLAN_ELEMENT_ID]

            expected_code = lookup_requirement(_CONTROL_PLAN_ELEMENT_ID, 3)
            assert valid_cp_element["requirement_code"] == expected_code
            assert valid_cp_element["verdict"] != "MISSING"
            assert valid_cp_element["verdict"] in ("SUBMITTED", "RETAINED_ON_FILE")
            assert valid_cp_element["verdict"] == "SUBMITTED"  # Table 4.1 Level 3 code 'S'
            assert valid_cp_element["evidence_present"] is True
            assert valid_cp_element["evidence_valid"] is True
            assert valid_cp_element["is_blocking"] is False
            assert valid_audit["package_verdict"] == "SUBMISSION_READY"
            assert valid_audit["verdict_counts"]["EVIDENCE_INVALID"] == 0
            assert valid_audit["invalid_elements"] == []

            # --- Invalid half, SAME session ---------------------------------------------
            cp_invalid = _parsed_payload(
                await client.call_tool("validate_control_plan", {"plan": [_BAD_PLAN_ROW]})
            )
            assert cp_invalid["valid"] is False
            assert cp_invalid["schema_valid"] is False
            assert any("usl must be greater than lsl" in f for f in cp_invalid["schema_findings"])

            invalid_package = _package_with_control_plan_evidence(
                evidence_valid=cp_invalid["valid"],
                note=_control_plan_note(cp_invalid),
            )
            invalid_evidence = next(
                e
                for e in invalid_package["elements"]
                if e["element_id"] == _CONTROL_PLAN_ELEMENT_ID
            )
            assert invalid_evidence["present"] is True
            assert invalid_evidence["evidence_valid"] is False

            invalid_audit = _parsed_payload(
                await client.call_tool(
                    "audit_ppap_package",
                    {"package": invalid_package, **_CHAIN_APPLICABILITY},
                )
            )
            invalid_cp_element = invalid_audit["elements"][_CONTROL_PLAN_ELEMENT_ID]

            assert invalid_cp_element["verdict"] == "EVIDENCE_INVALID"
            assert invalid_audit["package_verdict"] == "NOT_READY"
            assert invalid_cp_element["evidence_valid"] is False
            assert invalid_cp_element["is_blocking"] is True
            assert invalid_audit["invalid_elements"] == [_CONTROL_PLAN_ELEMENT_ID]
            assert invalid_audit["blocking_elements"] == [_CONTROL_PLAN_ELEMENT_ID]
            assert invalid_audit["verdict_counts"]["EVIDENCE_INVALID"] == 1
            assert invalid_audit["verdict_counts"]["INDETERMINATE"] == 0

            # The upstream engine's own finding text reached the §2.2.7 rationale verbatim.
            for finding in cp_invalid["schema_findings"]:
                assert finding in invalid_cp_element["rationale"]

            # --- Wire == raw engine, for BOTH halves ------------------------------------
            assert valid_audit == _with_basis(
                core_audit_ppap_package(valid_package, **_CHAIN_APPLICABILITY).to_dict()
            )
            assert invalid_audit == _with_basis(
                core_audit_ppap_package(invalid_package, **_CHAIN_APPLICABILITY).to_dict()
            )

            # The ONLY difference between the two packages is the threaded §2.2.7 verdict, so
            # the readiness flip is attributable to the Control Plan and to nothing else.
            assert valid_audit["submission_level"] == invalid_audit["submission_level"]
            assert (
                valid_audit["verdict_counts"]["NOT_APPLICABLE"]
                == invalid_audit["verdict_counts"]["NOT_APPLICABLE"]
            )

    asyncio.run(_run())


# ==============================================================================
# 4. Session Error Isolation (in-session and across a fresh session)
# ==============================================================================


def test_ppap_session_error_isolation_in_session_and_across_sessions() -> None:
    """A malformed PPAP call poisons neither the rest of its session nor a fresh session.

    Both directions are asserted: the post-error payload equals the pre-error payload inside the
    dirty session, AND it equals the payload a brand-new session — which never saw the error —
    produces for the same call.
    """

    async def _run() -> None:
        # A clean session that never sees an error, used as the cross-session reference.
        async with create_connected_server_and_client_session(mcp._mcp_server) as clean_client:
            clean_audit = _parsed_payload(await clean_client.call_tool("audit_ppap_package", {}))
            clean_psw = _parsed_payload(await clean_client.call_tool("validate_psw", {}))

        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            baseline_audit = _parsed_payload(await client.call_tool("audit_ppap_package", {}))
            assert baseline_audit == clean_audit

            # 1. Bad type: package must be a dict or None.
            assert (
                await client.call_tool("audit_ppap_package", {"package": "not-a-dict"})
            ).isError

            # 2. The very next call in the SAME session is unaffected.
            assert _parsed_payload(await client.call_tool("audit_ppap_package", {})) == (
                baseline_audit
            )

            # 3. Unknown element on a different tool.
            assert (
                await client.call_tool("lookup_ppap_requirement", {"element_id": "2.2.99"})
            ).isError

            # 4. Out-of-range submission level.
            assert (
                await client.call_tool("lookup_ppap_requirement", {"submission_level": 9})
            ).isError

            # 5. Invalid canvas theme.
            assert (await client.call_tool("render_ppap_canvas", {"theme": "neon"})).isError

            # 6. Every PPAP tool still returns the clean-session payload after four failures.
            dirty_audit = _parsed_payload(await client.call_tool("audit_ppap_package", {}))
            dirty_psw = _parsed_payload(await client.call_tool("validate_psw", {}))
            assert dirty_audit == baseline_audit == clean_audit
            assert dirty_psw == clean_psw

        # 7. The other direction: a session opened AFTER the failing one is equally unaffected.
        async with create_connected_server_and_client_session(mcp._mcp_server) as fresh_client:
            assert _parsed_payload(await fresh_client.call_tool("audit_ppap_package", {})) == (
                clean_audit
            )
            assert _parsed_payload(await fresh_client.call_tool("validate_psw", {})) == clean_psw

    asyncio.run(_run())


# ==============================================================================
# 5. Cross-Domain Non-Contamination (PPAP interleaved with RCA and SPC)
# ==============================================================================


def test_cross_domain_calls_do_not_contaminate_ppap_results() -> None:
    """PPAP results are byte-identical before and after RCA and SPC tools run, and vice versa.

    Each interleaved call is also asserted against its own known-good value, so a domain that
    silently returned garbage would not pass as "non-contaminating".
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            baseline_audit = _parsed_payload(await client.call_tool("audit_ppap_package", {}))
            baseline_capability = _parsed_payload(
                await client.call_tool("assess_ppap_capability", {})
            )

            baseline_others: dict[str, dict[str, Any]] = {}
            for domain, tool_name, tool_args, expected in _CROSS_DOMAIN_CALLS:
                other_payload = _parsed_payload(await client.call_tool(tool_name, tool_args))
                for key, value in expected.items():
                    assert other_payload[key] == value, f"{domain}/{tool_name}: {key}"
                baseline_others[tool_name] = other_payload

                repeat_audit = _parsed_payload(await client.call_tool("audit_ppap_package", {}))
                repeat_capability = _parsed_payload(
                    await client.call_tool("assess_ppap_capability", {})
                )
                assert repeat_audit == baseline_audit, f"audit drifted after {domain}/{tool_name}"
                assert repeat_capability == baseline_capability, (
                    f"capability drifted after {domain}/{tool_name}"
                )

            # The reverse direction: the other domains are unchanged by the PPAP calls too.
            for _domain, tool_name, tool_args, _expected in _CROSS_DOMAIN_CALLS:
                assert (
                    _parsed_payload(await client.call_tool(tool_name, tool_args))
                    == baseline_others[tool_name]
                )

    asyncio.run(_run())


# ==============================================================================
# 6. The Section 5 Customer Authority Invariant, Asserted at the Wire
# ==============================================================================


def test_no_customer_disposition_verdict_at_the_wire() -> None:
    """No PPAP payload — benchmark or chained — resolves a customer disposition as its verdict.

    'Approved', 'Interim Approval', and 'Rejected' are the customer's authority exclusively per
    AIAG PPAP 4th Edition Section 5. Every one of the five tools is exercised over the benchmark
    input, plus both halves of the chained Control Plan workflow, since the NOT_READY path is
    exactly where a tool would be tempted to say 'Rejected'.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            for name in _PPAP_TOOL_NAMES:
                _assert_no_customer_disposition_verdict(
                    _parsed_payload(await client.call_tool(name, {}))
                )

            for evidence_valid in (True, False):
                package = _package_with_control_plan_evidence(
                    evidence_valid=evidence_valid,
                    note="Control Plan evidence under audit.",
                )
                audit = _parsed_payload(
                    await client.call_tool(
                        "audit_ppap_package",
                        {"package": package, **_CHAIN_APPLICABILITY},
                    )
                )
                _assert_no_customer_disposition_verdict(audit)
                assert audit["package_verdict"] in _PACKAGE_READINESS_VERDICTS

    asyncio.run(_run())


def test_authority_invariant_is_declared_not_merely_absent() -> None:
    """The canvas states the Section 5 reservation, so the absence check above is not vacuous.

    A payload that simply never mentioned the dispositions would pass
    ``_assert_no_customer_disposition_verdict`` trivially. This asserts the opposite surface: the
    canvas summary NAMES all three dispositions and reserves them for the customer, while the
    canvas's own resolved value stays inside the supplier-readiness vocabulary.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            parsed = _parsed_payload(await client.call_tool("render_ppap_canvas", {}))
            notice = parsed["summary"]["authority_notice"]

            assert "Approved" in notice
            assert "Interim Approval" in notice
            assert "Rejected" in notice
            assert "customer's authorized representative" in notice

            assert parsed["summary"]["submission_readiness"] in _PACKAGE_READINESS_VERDICTS
            _assert_no_customer_disposition_verdict(parsed)

    asyncio.run(_run())

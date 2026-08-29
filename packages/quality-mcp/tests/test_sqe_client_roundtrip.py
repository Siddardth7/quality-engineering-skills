"""
test_sqe_client_roundtrip.py
Integration tests proving in-process FastMCP client-server round-trip for all six SQE tools.

Validates:
1. FastMCP server initialization, handshake, and tool discovery for all 6 Supplier Quality
   Engineering tools: calculate_supplier_ppm, calculate_otif, calculate_vendor_scorecard,
   evaluate_escalation, generate_scar, render_sqe_canvas.
2. Three-way payload parity per tool: structuredContent == JSON-deserialized content[0].text ==
   a DIRECT quality_core.sqe / quality_core.canvas.sqe ENGINE call. The engine, not the
   quality_mcp.tools.sqe wrapper, is the comparison target: comparing the wire to the wrapper
   only proves FastMCP's serialization is faithful, never that the wrapper forwards its
   arguments and config to the engine correctly.
3. Real-world supplier scenario execution (Bracket Machining Supplier SUP-3001, March 2026)
   rather than the bare benchmark fallbacks.
4. In-process session error isolation: a failing call does not poison later calls in the session.
5. Protocol-level negative controls (unknown tool, type mismatch, invalid enum value).
6. Cross-domain non-contamination: SQE calls interleaved with FMEA, SPC, MSA, Control Plan, RCA,
   NCR, COPQ, and PPAP calls in one session return byte-identical SQE results throughout.
7. All three SQE invariants asserted AT THE WIRE (not at the Python docstring): heuristic
   labelling present, no commercial action, no engine-authored root cause.
8. The chained NCR -> SCAR workflow, both halves in a single session: a nonconformity that
   passes quality_core.ncr validation drives generate_scar to ISSUABLE, and the same
   nonconformity carrying an injected defect resolves EVIDENCE_INVALID, is held out of ISSUABLE,
   and surfaces the NCR engine's own findings verbatim over the wire.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Iterator

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.canvas.sqe import SQECanvas, render_sqe
from quality_core.sqe.escalation import evaluate_escalation as core_evaluate_escalation
from quality_core.sqe.otif import calculate_otif as core_calculate_otif
from quality_core.sqe.ppm import calculate_supplier_ppm as core_calculate_supplier_ppm
from quality_core.sqe.scar import generate_scar as core_generate_scar
from quality_core.sqe.schema import (
    SCARRequest,
    SupplierPeriod,
    validate_sqe_delivery,
    validate_sqe_receipt,
)
from quality_core.sqe.scorecard import (
    calculate_vendor_scorecard as core_calculate_vendor_scorecard,
)
from quality_mcp.server import mcp
from quality_mcp.tools.sqe import _scorecard_result_from_payload

_SQE_TOOL_NAMES = (
    "calculate_supplier_ppm",
    "calculate_otif",
    "calculate_vendor_scorecard",
    "evaluate_escalation",
    "generate_scar",
    "render_sqe_canvas",
)

# The four tools that COMPUTE a quality figure and must therefore carry heuristic labelling.
# generate_scar renders sections and dispatches evidence; render_sqe_canvas renders results
# somebody else computed. Neither owns a numeric threshold, so neither emits is_heuristic.
_QUALITY_COMPUTING_TOOL_NAMES = (
    "calculate_supplier_ppm",
    "calculate_otif",
    "calculate_vendor_scorecard",
    "evaluate_escalation",
)


# ---------------------------------------------------------------------------
# Benchmark Test Fixtures — "Bracket Machining Supplier SUP-3001", March 2026
#
# One coherent supplier scenario reused across tools 1-4 so the PPM, OTIF, scorecard, and
# escalation figures are self-consistent. Every asserted numeric value is derived from the
# direct core call in the test body, never hand-computed here.
# ---------------------------------------------------------------------------

_SUP_3001_PERIOD: dict[str, Any] = {
    "supplier_id": "SUP-3001",
    "period_start": "2026-03-01",
    "period_end": "2026-03-31",
    "period_label": "March 2026",
}

_SUP_3001_LOTS: list[dict[str, Any]] = [
    {
        "supplier_id": "SUP-3001",
        "lot_id": "LOT-SUP-3001-A",
        "quantity_received": 4000,
        "receipt_date": "2026-03-04",
        "defect_count": 6,
        "opportunities_per_unit": 3,
    },
    {
        "supplier_id": "SUP-3001",
        "lot_id": "LOT-SUP-3001-B",
        "quantity_received": 3500,
        "receipt_date": "2026-03-13",
        "defect_count": 2,
        "opportunities_per_unit": 3,
    },
    {
        "supplier_id": "SUP-3001",
        "lot_id": "LOT-SUP-3001-C",
        "quantity_received": 2500,
        "receipt_date": "2026-03-25",
        "defect_count": 4,
        "opportunities_per_unit": 3,
    },
]

_SUP_3001_DELIVERIES: list[dict[str, Any]] = [
    {
        "supplier_id": "SUP-3001",
        "order_id": "PO-3001-01",
        "quantity_ordered": 4000,
        "quantity_delivered": 4000,
        "promised_date": "2026-03-04",
        "actual_delivery_date": "2026-03-04",
    },
    {
        "supplier_id": "SUP-3001",
        "order_id": "PO-3001-02",
        "quantity_ordered": 3500,
        "quantity_delivered": 3500,
        "promised_date": "2026-03-12",
        "actual_delivery_date": "2026-03-16",
    },
    {
        "supplier_id": "SUP-3001",
        "order_id": "PO-3001-03",
        "quantity_ordered": 2500,
        "quantity_delivered": 2350,
        "promised_date": "2026-03-25",
        "actual_delivery_date": "2026-03-25",
    },
]

# The SCAR the §2 parity test issues. date_issued is SET here on purpose, so this request
# resolves AWAITING_SUPPLIER_RESPONSE and stays distinct from the §6 chain's ISSUABLE/DRAFT
# pair — the three status branches are then each proven by exactly one call.
_ISSUED_SCAR_REQUEST: dict[str, Any] = {
    "supplier_id": "SUP-3001",
    "issue_description": (
        "Incoming inspection rejected 12 bracket assemblies across three March 2026 receipt "
        "lots for bore diameter above the drawing maximum."
    ),
    "scar_id": "SCAR-2026-3001-01",
    "linked_ncr_id": "NCR-2026-3001-A",
    "date_issued": "2026-04-02",
    "due_date": "2026-04-16",
    "requested_by": "Supplier Quality Engineering",
}

_CANVAS_TITLE = "SUP-3001 Bracket Machining Vendor Scorecard Canvas"


# ---------------------------------------------------------------------------
# Chained NCR -> SCAR fixtures (§6)
# ---------------------------------------------------------------------------

# generate_scar's linked_ncr_evidence is dispatched to quality_core.ncr.schema.validate_ncr /
# NonconformanceRecord — the LOWER-LEVEL record schema, not write_ncr's narrative
# what_deviated / measured_evidence fields.
_VALID_NCR_EVIDENCE: list[dict[str, Any]] = [
    {
        "part_lot_id": "LOT-SUP-3001-A",
        "defect_description": "Bracket bore diameter oversize",
        "requirement_violated": "Drawing Rev C: bore diameter 12.00 +/- 0.02 mm",
        "quantity_affected": 6,
        "detection_point": "Incoming Inspection Station 2",
    }
]

# Injected defect: quantity_affected=0 violates NonconformanceRecord.quantity_affected (ge=1).
# A single-field constraint violation, deliberately NOT a missing key — a missing key would
# exercise a different, less specific validation path.
_INVALID_NCR_EVIDENCE: list[dict[str, Any]] = [
    {
        **_VALID_NCR_EVIDENCE[0],
        "quantity_affected": 0,
    }
]

# date_issued=None is REQUIRED, not incidental: _resolve_status only reaches Rule 5 (ISSUABLE)
# or Rule 4 (DRAFT) when the SCAR was never issued. A request carrying a date_issued resolves
# Rule 3 (AWAITING_SUPPLIER_RESPONSE) for BOTH halves, and the chain would pass while proving
# nothing about the evidence verdict.
_CHAIN_REQUEST_BASE: dict[str, Any] = {
    "supplier_id": "SUP-3001",
    "issue_description": (
        "Incoming inspection found bracket bore diameter oversize on lot LOT-SUP-3001-A."
    ),
    "date_issued": None,
}


# ---------------------------------------------------------------------------
# Cross-domain interleave table (§4)
#
# Every tool/args/expected triple below is already verified in test_server.py, so this suite
# re-derives no arithmetic of its own for the interleaved domains.
# ---------------------------------------------------------------------------

_CROSS_DOMAIN_CALLS: tuple[tuple[str, str, dict[str, Any], dict[str, Any]], ...] = (
    (
        "FMEA",
        "lookup_fmea_ap",
        {"severity": 10, "occurrence": 10, "detection": 10},
        {"rpn": 1000, "action_priority": "High"},
    ),
    (
        "SPC",
        "render_spc_canvas",
        {},
        {"chart_type": "Xbar-R", "in_control": True},
    ),
    (
        "MSA",
        "render_msa_canvas",
        {},
        {"method": "anova", "verdict": "Reject"},
    ),
    (
        "ControlPlan",
        "validate_control_plan",
        {
            "plan": [
                {
                    "characteristic": "Bore Diameter",
                    "measurement_method": "Bore gauge",
                    "sample_size": 5,
                    "frequency": "per shift",
                    "reaction_plan": "Stop line.",
                }
            ]
        },
        {"valid": True, "schema_valid": True},
    ),
    (
        "RCA",
        "scope_is_is_not",
        {},
        {"valid": True, "verdict": "ACCEPT", "total_rows": 4},
    ),
    (
        "NCR",
        "write_ncr",
        {
            "raw_defect_note": "Found 10 bad parts at incoming inspection.",
            "requirement_violated": "Spec-100",
            "measured_evidence": "Measured out of spec",
            "what_deviated": "Bore diameter out of spec",
            "quantity_affected": 10,
            "detection_point": "Receiving Inspection",
        },
        {"valid": True},
    ),
    (
        "COPQ",
        "estimate_copq",
        {
            "scrap_qty": 20,
            "unit_cost": 50.0,
            "rework_hours": 10.0,
            "labor_rate": 50.0,
            "revenue_base": 100000.0,
        },
        {"total_copq": 1500.0, "copq_percentage_of_revenue": 1.5},
    ),
    (
        "PPAP",
        "validate_psw",
        {},
        {"verdict": "COMPLETE"},
    ),
)


# ---------------------------------------------------------------------------
# Invariant phrase lists (§5)
#
# Intentionally the same three lists test_sqe_tools.py declares. They are duplicated rather
# than imported because the quality-mcp test package has no conftest.py to factor them into
# and one test module may not import another by path. test_sqe_tools.py applies them to the
# Python docstrings and Field descriptions; this module applies them to what actually crosses
# the wire — the list_tools() descriptions and the serialized call_tool payloads.
# ---------------------------------------------------------------------------

_NO_STANDARD_ATTRIBUTION = re.compile(r"\bper\s+(ISO|IATF|AIAG)\b", re.IGNORECASE)
_ROOT_CAUSE_OFFER_PHRASES = (
    "produces a root cause",
    "provides the root cause",
    "invents a root cause",
    "assigns a root cause",
    "determines the root cause",
    "determine the root cause",
)
_COMMERCIAL_ACTION_PHRASES = (
    "recommends a hold",
    "recommend a hold",
    "recommends de-sourcing",
    "recommend de-sourcing",
    "recommends removal",
    "recommend removal",
    "recommends a charge-back",
    "recommend a charge-back",
    "authorizes a hold",
    "authorizes de-sourcing",
)

# The verbatim heuristic-disclosure phrase _HEURISTIC_NOTE ends on; an MCP host shows this to
# the agent, so its presence in the wire description is the invariant, not its presence in
# the Python source.
_HEURISTIC_DISCLOSURE_PHRASE = "caller-configurable engineering default labelled is_heuristic=True"


def _assert_no_invariant_leak(text: str) -> None:
    """Assert one wire string attributes no standard, offers no root cause, orders no action."""
    assert not _NO_STANDARD_ATTRIBUTION.search(text), f"standard-attribution leak: {text!r}"
    lowered = text.lower()
    for phrase in _ROOT_CAUSE_OFFER_PHRASES:
        assert phrase not in lowered, f"root-cause-authorship leak: {text!r}"
    for phrase in _COMMERCIAL_ACTION_PHRASES:
        assert phrase not in lowered, f"commercial-authority leak: {text!r}"


def _walk_items(obj: Any) -> Iterator[tuple[str, Any]]:
    """Yield every (key, value) pair anywhere in a nested JSON-shaped payload."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
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


def _with_basis_echo(engine_payload: dict[str, Any]) -> dict[str, Any]:
    """Add the ``basis`` echo the tool layer appends to a raw engine ``to_dict()``.

    The engine result carries ``standards_basis``; the tool copies it to ``basis`` and changes
    nothing else. Building the expected dict this way means a mutated echo (``basis`` set to
    anything other than the engine's own ``standards_basis``) fails the parity assertion.
    """
    return {**engine_payload, "basis": engine_payload["standards_basis"]}


# ==============================================================================
# 1. FastMCP Client Handshake & Tool Discovery
# ==============================================================================


def test_client_handshake_discovers_all_sqe_tools() -> None:
    """In-process client handshake discovers and validates schemas for all 6 SQE tools."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools_result = await client.list_tools()
            tools_by_name = {t.name: t for t in tools_result.tools}

            for name in _SQE_TOOL_NAMES:
                assert name in tools_by_name

            # 1. calculate_supplier_ppm
            ppm_props = tools_by_name["calculate_supplier_ppm"].inputSchema.get("properties", {})
            assert "period" in ppm_props
            assert "lots" in ppm_props
            assert "sample_adequacy_minimum" in ppm_props

            # 2. calculate_otif
            otif_props = tools_by_name["calculate_otif"].inputSchema.get("properties", {})
            assert "period" in otif_props
            assert "deliveries" in otif_props
            assert "late_tolerance_days" in otif_props
            assert "in_full_tolerance_pct" in otif_props

            # 3. calculate_vendor_scorecard
            scorecard_props = tools_by_name["calculate_vendor_scorecard"].inputSchema.get(
                "properties", {}
            )
            assert "period" in scorecard_props
            assert "lots" in scorecard_props
            assert "deliveries" in scorecard_props
            assert "quality_weight" in scorecard_props
            assert "delivery_weight" in scorecard_props

            # 4. evaluate_escalation
            escalation_props = tools_by_name["evaluate_escalation"].inputSchema.get(
                "properties", {}
            )
            assert "scorecard" in escalation_props
            assert "recurrence_count" in escalation_props
            assert "scar_score_maximum" in escalation_props

            # 5. generate_scar — the cross-engine evidence slots this issue chains through
            scar_props = tools_by_name["generate_scar"].inputSchema.get("properties", {})
            assert "request" in scar_props
            assert "linked_ncr_evidence" in scar_props
            assert "supplier_root_cause_evidence" in scar_props
            assert "cost_impact_evidence" in scar_props
            assert "verification_of_effectiveness" in scar_props

            # 6. render_sqe_canvas
            canvas_props = tools_by_name["render_sqe_canvas"].inputSchema.get("properties", {})
            assert "rows" in canvas_props
            assert "title" in canvas_props
            assert "theme" in canvas_props
            assert "standalone" in canvas_props

    asyncio.run(_run())


# ==============================================================================
# 2. Individual Tool Round-Trip & Three-Way Parity (wire == text == direct ENGINE call)
# ==============================================================================


def test_calculate_supplier_ppm_roundtrip_parity() -> None:
    """calculate_supplier_ppm's wire payload equals a direct quality_core.sqe.ppm engine call."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res = await client.call_tool(
                "calculate_supplier_ppm",
                {"period": _SUP_3001_PERIOD, "lots": _SUP_3001_LOTS},
            )
            parsed = _parsed_payload(res)

            direct_engine = core_calculate_supplier_ppm(
                SupplierPeriod(**_SUP_3001_PERIOD),
                validate_sqe_receipt([dict(row) for row in _SUP_3001_LOTS]),
            ).to_dict()
            assert parsed == _with_basis_echo(direct_engine)
            assert parsed["basis"] == parsed["standards_basis"]
            assert parsed["verdict"] == "MEASURED"

    asyncio.run(_run())


def test_calculate_otif_roundtrip_parity() -> None:
    """calculate_otif's wire payload equals a direct quality_core.sqe.otif engine call."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res = await client.call_tool(
                "calculate_otif",
                {"period": _SUP_3001_PERIOD, "deliveries": _SUP_3001_DELIVERIES},
            )
            parsed = _parsed_payload(res)

            direct_engine = core_calculate_otif(
                SupplierPeriod(**_SUP_3001_PERIOD),
                validate_sqe_delivery([dict(row) for row in _SUP_3001_DELIVERIES]),
            ).to_dict()
            assert parsed == _with_basis_echo(direct_engine)
            assert parsed["basis"] == parsed["standards_basis"]
            assert parsed["delivery_count"] == 3

    asyncio.run(_run())


def test_calculate_vendor_scorecard_roundtrip_parity() -> None:
    """calculate_vendor_scorecard's wire payload equals a direct quality_core.sqe engine call."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res = await client.call_tool(
                "calculate_vendor_scorecard",
                {
                    "period": _SUP_3001_PERIOD,
                    "lots": _SUP_3001_LOTS,
                    "deliveries": _SUP_3001_DELIVERIES,
                },
            )
            parsed = _parsed_payload(res)

            direct_engine = core_calculate_vendor_scorecard(
                SupplierPeriod(**_SUP_3001_PERIOD),
                validate_sqe_receipt([dict(row) for row in _SUP_3001_LOTS]),
                validate_sqe_delivery([dict(row) for row in _SUP_3001_DELIVERIES]),
            ).to_dict()
            assert parsed == _with_basis_echo(direct_engine)
            assert parsed["basis"] == parsed["standards_basis"]
            assert parsed["verdict"] == "RATED"

    asyncio.run(_run())


def test_evaluate_escalation_roundtrip_parity() -> None:
    """evaluate_escalation consumes a wire-obtained scorecard and matches the direct engine.

    A two-tool chain inside one test, and the way evaluate_escalation is meant to be driven: the
    scorecard payload calculate_vendor_scorecard returned over the wire is passed straight back
    in unmodified. The comparison target is the raw escalation engine fed the equivalent
    reconstructed ScorecardResult.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res_scorecard = await client.call_tool(
                "calculate_vendor_scorecard",
                {
                    "period": _SUP_3001_PERIOD,
                    "lots": _SUP_3001_LOTS,
                    "deliveries": _SUP_3001_DELIVERIES,
                },
            )
            scorecard_payload = _parsed_payload(res_scorecard)

            res = await client.call_tool(
                "evaluate_escalation",
                {"scorecard": scorecard_payload, "recurrence_count": 2},
            )
            parsed = _parsed_payload(res)

            direct_engine = core_evaluate_escalation(
                _scorecard_result_from_payload(scorecard_payload),
                recurrence_count=2,
            ).to_dict()
            assert parsed == _with_basis_echo(direct_engine)
            assert parsed["basis"] == parsed["standards_basis"]
            assert parsed["scorecard_verdict"] == scorecard_payload["verdict"]

    asyncio.run(_run())


def test_generate_scar_roundtrip_parity() -> None:
    """generate_scar's wire payload equals a direct quality_core.sqe.scar engine call.

    Uses an ISSUED request (date_issued set), so this call resolves AWAITING_SUPPLIER_RESPONSE —
    a different status branch from the §6 chain's ISSUABLE / DRAFT pair.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res = await client.call_tool(
                "generate_scar",
                {
                    "request": _ISSUED_SCAR_REQUEST,
                    "linked_ncr_evidence": _VALID_NCR_EVIDENCE,
                },
            )
            parsed = _parsed_payload(res)

            direct_engine = core_generate_scar(
                SCARRequest(**_ISSUED_SCAR_REQUEST),
                linked_ncr_evidence=_VALID_NCR_EVIDENCE,
            ).to_dict()
            assert parsed == _with_basis_echo(direct_engine)
            assert parsed["basis"] == parsed["standards_basis"]
            assert parsed["status"] == "AWAITING_SUPPLIER_RESPONSE"
            assert parsed["linkage"]["linked_ncr"]["verdict"] == "EVIDENCE_VALID"

    asyncio.run(_run())


def test_render_sqe_canvas_roundtrip_parity() -> None:
    """render_sqe_canvas's wire HTML equals a direct quality_core.canvas.sqe render.

    SQECanvas exposes no get_summary(); the summary dict is composed by the tool layer. So the
    core-level parity surface here is the rendered HTML string itself, compared under exactly
    the same title/theme/standalone arguments — any of the three differing makes the comparison
    spuriously fail rather than meaningfully pass.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res = await client.call_tool(
                "render_sqe_canvas",
                {"title": _CANVAS_TITLE, "theme": "dark", "standalone": True},
            )
            parsed = _parsed_payload(res)

            direct_html = render_sqe(
                SQECanvas(title=_CANVAS_TITLE).load_sample(),
                theme="dark",
                standalone=True,
            )
            assert parsed["html"] == direct_html
            assert parsed["title"] == _CANVAS_TITLE
            assert parsed["verdict"] == "RENDERED"
            assert parsed["reason"] is None

            # Fixed benchmark-canvas constants (already verified in test_sqe_tools.py).
            assert parsed["rows_count"] == 6
            assert parsed["summary"]["rated_count"] == 5
            assert parsed["summary"]["indeterminate_count"] == 1
            assert parsed["summary"]["band_counts"] == {"A": 1, "B": 1, "C": 3}
            assert parsed["summary"]["tier_counts"] == {
                "NONE": 1,
                "MONITOR": 1,
                "SCAR_REQUIRED": 1,
                "CONTAINMENT_REQUIRED": 1,
                "EXECUTIVE_REVIEW": 1,
                "INDETERMINATE": 1,
            }

    asyncio.run(_run())


# ==============================================================================
# 3. Session Error Isolation & Protocol Negative Controls
# ==============================================================================


def test_session_error_isolation_does_not_corrupt_subsequent_calls() -> None:
    """A failing SQE call returns an error without poisoning later calls in the same session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Malformed: linked_ncr_evidence is a bare int, which no evidence guard accepts.
            res_bad = await client.call_tool("generate_scar", {"linked_ncr_evidence": 1})
            assert res_bad.isError

            # 2. The very next call in the SAME session is unaffected.
            res_ppm = await client.call_tool(
                "calculate_supplier_ppm",
                {"period": _SUP_3001_PERIOD, "lots": _SUP_3001_LOTS},
            )
            ppm_payload = _parsed_payload(res_ppm)
            assert ppm_payload["verdict"] == "MEASURED"

            # 3. A second failure, on a different tool and for a different reason.
            res_bad2 = await client.call_tool("render_sqe_canvas", {"theme": "neon"})
            assert res_bad2.isError

            # 4. And a valid call after it still returns the same result as step 2.
            res_ppm_again = await client.call_tool(
                "calculate_supplier_ppm",
                {"period": _SUP_3001_PERIOD, "lots": _SUP_3001_LOTS},
            )
            assert _parsed_payload(res_ppm_again) == ppm_payload

    asyncio.run(_run())


def test_protocol_negative_controls_unknown_tool_and_invalid_arguments() -> None:
    """Unknown tools, type mismatches, and invalid values surface as isError, never as a crash."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            # 1. Unknown tool name.
            assert (await client.call_tool("no_such_sqe_tool_12345", {})).isError

            # 2. Type mismatch: a string where a row list belongs.
            assert (await client.call_tool("calculate_supplier_ppm", {"lots": "not-a-list"})).isError

            # 3. Type mismatch: a string where an int config override belongs.
            assert (await client.call_tool("calculate_otif", {"late_tolerance_days": "two"})).isError

            # 4. Invalid bound: an inverted evaluation window.
            assert (
                await client.call_tool(
                    "calculate_supplier_ppm",
                    {
                        "period": {
                            "supplier_id": "SUP-3001",
                            "period_start": "2026-03-31",
                            "period_end": "2026-03-01",
                        }
                    },
                )
            ).isError

            # 5. Invalid enum value on the canvas theme.
            assert (await client.call_tool("render_sqe_canvas", {"theme": "neon"})).isError

            # 6. Supplied-but-invalid VALUE: a scorecard that reconstructs cleanly but carries a
            #    verdict outside {RATED, INDETERMINATE} is an error, deliberately NOT an
            #    INDETERMINATE tier — "neither cleared nor escalated" would imply the scorecard
            #    was read and found inconclusive when it was in fact rejected.
            good_scorecard = _parsed_payload(
                await client.call_tool("calculate_vendor_scorecard", {})
            )
            assert (
                await client.call_tool(
                    "evaluate_escalation",
                    {"scorecard": {**good_scorecard, "verdict": "BROKEN"}},
                )
            ).isError

            # 7. An EMPTY request is absent input, not a caller error: it must return a
            #    fully-shaped INDETERMINATE SCAR rather than an isError response.
            res_empty = await client.call_tool("generate_scar", {"request": {}})
            empty_payload = _parsed_payload(res_empty)
            assert empty_payload["status"] == "INDETERMINATE"
            assert empty_payload["reason"]
            assert empty_payload["root_cause"] is None

    asyncio.run(_run())


# ==============================================================================
# 4. Cross-Domain Non-Contamination (SQE interleaved with all eight prior domains)
# ==============================================================================


def test_cross_domain_calls_do_not_contaminate_sqe_results() -> None:
    """SQE results are byte-identical before and after every other domain's tool runs.

    One session: a baseline calculate_supplier_ppm and generate_scar pair, then each of the
    eight previously-shipped domains' tools in turn, re-running and re-comparing both SQE calls
    after every one. Each interleaved call is also asserted against its own known-good value, so
    a domain that silently returned garbage would not pass as "non-contaminating".
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            ppm_args = {"period": _SUP_3001_PERIOD, "lots": _SUP_3001_LOTS}
            scar_args = {
                "request": _ISSUED_SCAR_REQUEST,
                "linked_ncr_evidence": _VALID_NCR_EVIDENCE,
            }

            baseline_ppm = _parsed_payload(await client.call_tool("calculate_supplier_ppm", ppm_args))
            baseline_scar = _parsed_payload(await client.call_tool("generate_scar", scar_args))
            assert baseline_ppm["verdict"] == "MEASURED"
            assert baseline_scar["status"] == "AWAITING_SUPPLIER_RESPONSE"

            for domain, tool_name, tool_args, expected in _CROSS_DOMAIN_CALLS:
                res_other = await client.call_tool(tool_name, tool_args)
                other_payload = _parsed_payload(res_other)
                for key, value in expected.items():
                    assert other_payload[key] == value, f"{domain}/{tool_name}: {key}"

                repeat_ppm = _parsed_payload(
                    await client.call_tool("calculate_supplier_ppm", ppm_args)
                )
                repeat_scar = _parsed_payload(await client.call_tool("generate_scar", scar_args))
                assert repeat_ppm == baseline_ppm, f"PPM drifted after {domain}/{tool_name}"
                assert repeat_scar == baseline_scar, f"SCAR drifted after {domain}/{tool_name}"

    asyncio.run(_run())


# ==============================================================================
# 5. The Three SQE Invariants, Asserted at the Wire
# ==============================================================================


def test_heuristic_labelling_present_at_the_wire() -> None:
    """Every computing tool discloses its heuristics in its description AND labels them in payloads.

    Two surfaces, both of which an MCP host actually consumes: the list_tools() description text
    shown to the agent, and the serialized call_tool payload. #122 asserts the Python __doc__;
    this asserts what crosses the wire.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools_by_name = {t.name: t for t in (await client.list_tools()).tools}

            for name in _QUALITY_COMPUTING_TOOL_NAMES:
                description = tools_by_name[name].description or ""
                assert _HEURISTIC_DISCLOSURE_PHRASE in description, name

                payload = _parsed_payload(await client.call_tool(name, {}))
                heuristic_flags = [
                    value for key, value in _walk_items(payload) if key == "is_heuristic"
                ]
                assert heuristic_flags, f"{name}: no is_heuristic label anywhere in payload"
                assert all(flag is True for flag in heuristic_flags), name

    asyncio.run(_run())


def test_no_commercial_action_or_root_cause_authorship_at_the_wire() -> None:
    """No SQE description or payload string offers a commercial action or authors a root cause."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools_by_name = {t.name: t for t in (await client.list_tools()).tools}

            for name in _SQE_TOOL_NAMES:
                _assert_no_invariant_leak(tools_by_name[name].description or "")

                payload = _parsed_payload(await client.call_tool(name, {}))
                for text in _walk_strings(payload):
                    _assert_no_invariant_leak(text)

    asyncio.run(_run())


def test_generate_scar_authors_no_root_cause_without_supplier_evidence() -> None:
    """root_cause stays None over the wire whenever no supplier root-cause evidence was supplied.

    The sharpest form of the root-cause-authorship invariant: the tool is handed a fully-formed
    SCAR request and valid NCR evidence, and still declines to state a cause.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res = await client.call_tool(
                "generate_scar",
                {
                    "request": _ISSUED_SCAR_REQUEST,
                    "linked_ncr_evidence": _VALID_NCR_EVIDENCE,
                },
            )
            payload = _parsed_payload(res)
            assert payload["root_cause"] is None
            assert (
                payload["linkage"]["supplier_root_cause"]["verdict"] == "EVIDENCE_NOT_SUPPLIED"
            )

    asyncio.run(_run())


# ==============================================================================
# 6. Chained NCR -> SCAR Workflow, Both Halves in One Session
# ==============================================================================


def test_chained_ncr_to_scar_workflow_valid_and_invalid_halves() -> None:
    """generate_scar dispatches linked NCR evidence to quality_core.ncr, both halves, one session.

    Valid half: a nonconformity that passes quality_core.ncr.schema.validate_ncr resolves
    EVIDENCE_VALID and, because the request was never issued, the SCAR resolves ISSUABLE.

    Invalid half: the SAME nonconformity with quantity_affected=0 injected fails validation,
    resolves EVIDENCE_INVALID, and holds the SCAR out of ISSUABLE at DRAFT — with the NCR
    engine's own findings surfaced verbatim rather than re-authored by the SCAR engine.

    The verbatim proof compares the wire findings to a direct core call rather than to a
    hardcoded string: pydantic's exact wording is an implementation detail, but wire == engine
    is the actual invariant, and it survives a pydantic message-text change.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            valid_request = {**_CHAIN_REQUEST_BASE, "scar_id": "SCAR-2026-CHAIN-VALID"}
            invalid_request = {**_CHAIN_REQUEST_BASE, "scar_id": "SCAR-2026-CHAIN-INVALID"}

            # --- Valid half -------------------------------------------------------------
            res_valid = await client.call_tool(
                "generate_scar",
                {"request": valid_request, "linked_ncr_evidence": _VALID_NCR_EVIDENCE},
            )
            valid_data = _parsed_payload(res_valid)

            # Guard the ISSUABLE construction trap: a request carrying a date_issued would
            # resolve AWAITING_SUPPLIER_RESPONSE and never reach Rule 5 at all.
            assert valid_data["date_issued"] is None
            assert valid_data["status"] != "AWAITING_SUPPLIER_RESPONSE"
            assert valid_data["status"] == "ISSUABLE"
            assert valid_data["reason"] is None
            assert valid_data["linkage"]["linked_ncr"]["verdict"] == "EVIDENCE_VALID"
            assert valid_data["linkage"]["linked_ncr"]["findings"] == []
            assert valid_data["linkage"]["linked_ncr"]["engine"] == "quality_core.ncr"
            assert valid_data["root_cause"] is None

            # The NCR engine's own model_dump() came through the wire unmodified.
            raw_records = valid_data["linkage"]["linked_ncr"]["raw_result"]["records"]
            assert len(raw_records) == 1
            for field, expected in _VALID_NCR_EVIDENCE[0].items():
                assert raw_records[0][field] == expected

            # --- Invalid half, same session ---------------------------------------------
            res_invalid = await client.call_tool(
                "generate_scar",
                {"request": invalid_request, "linked_ncr_evidence": _INVALID_NCR_EVIDENCE},
            )
            invalid_data = _parsed_payload(res_invalid)

            assert invalid_data["status"] != "ISSUABLE"
            assert invalid_data["status"] == "DRAFT"
            assert invalid_data["linkage"]["linked_ncr"]["verdict"] == "EVIDENCE_INVALID"
            assert invalid_data["linkage"]["linked_ncr"]["findings"]
            assert invalid_data["linkage"]["linked_ncr"]["raw_result"] is None
            assert invalid_data["root_cause"] is None

            # --- Verbatim proof: wire findings == the NCR engine's own findings ----------
            direct_invalid = core_generate_scar(
                SCARRequest(**invalid_request),
                linked_ncr_evidence=_INVALID_NCR_EVIDENCE,
            ).to_dict()
            assert (
                invalid_data["linkage"]["linked_ncr"]["findings"]
                == direct_invalid["linkage"]["linked_ncr"]["findings"]
            )
            assert invalid_data["status"] == direct_invalid["status"] == "DRAFT"

            direct_valid = core_generate_scar(
                SCARRequest(**valid_request),
                linked_ncr_evidence=_VALID_NCR_EVIDENCE,
            ).to_dict()
            assert valid_data == _with_basis_echo(direct_valid)

    asyncio.run(_run())

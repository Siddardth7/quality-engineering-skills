"""
Chained in-process FastMCP client round-trip across the 8D problem-solving workflow (E13, #216).

Drives NCR containment -> 8D D3 -> RCA D4 -> FMEA/Control-Plan D7 -> D8 -> CLOSED over real MCP
tool calls (write_ncr, advance_8d, validate_5why, validate_control_plan, lookup_fmea_ap) in one
memory-transport session, proving:
1. The state machine advances through every gate the chain touches (D3->D4 linked-NCR gate,
   D7->D8 prevention gate, D8->CLOSED closure gate) and the report reaches status CLOSED.
2. Two invalid halves are BLOCKED at their correct gate with the correct code / rule_id: an
   rca-rejected D4 at D8->CLOSED (ROOT_CAUSE_REJECTED / RULE-8D-GATE-CLOSURE) and a missing D7 at
   D7->D8 (PREVENTION_UPDATE_MISSING / RULE-8D-GATE-PREVENTION).
3. Payload parity at every call in the chain: structuredContent == json.loads(content[0].text) ==
   the tool function called directly == the wrapped quality_core engine's own return, plus a
   fourth leg — each touched domain's SKILL.md names the tool this suite calls live.
4. Protocol-level error isolation: a malformed call mid-chain returns isError without poisoning
   the session.

The server persists no 8D report between calls (see ``advance_8d``'s docstring), so every hop
threads the previous hop's ``result["report"]`` forward explicitly.
"""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any, cast

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.canvas.eight_d import SAMPLE_EIGHT_D_REPORT
from quality_core.canvas.rca import SAMPLE_FIVE_WHY_STEPS
from quality_core.controlplan import validate_control_plan as validate_control_plan_core
from quality_core.ncr.nonconformance import write_nonconformance as core_write_nonconformance
from quality_core.rca.eight_d import EightDState
from quality_core.rca.eight_d import transition_eight_d as core_transition_8d
from quality_core.rca.eight_d_schema import validate_eight_d
from quality_core.rca.five_why import validate_five_why_chain
from quality_core.scoring import action_priority, rpn
from quality_mcp.server import mcp
from quality_mcp.tools.controlplan import validate_control_plan
from quality_mcp.tools.eight_d import advance_8d
from quality_mcp.tools.fmea import lookup_fmea_ap
from quality_mcp.tools.ncr import write_ncr
from quality_mcp.tools.rca import validate_5why

_REPO_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# 1. Fixtures / helpers
# ---------------------------------------------------------------------------

#: Step 1 — the nonconformance the 8D report's own D2 problem statement describes.
_NCR_ARGS: dict[str, Any] = {
    "what_deviated": "Bore diameter undersized",
    "requirement_violated": "44.00 +0.05/-0.00 mm bore print requirement",
    "measured_evidence": "12 of 480 housings measured 0.03 mm below the lower limit",
    "quantity_affected": 12,
    "detection_point": "Customer incoming inspection",
    "part_lot_id": "HSG-44821-LOT9",
}

#: Step 4 — the corrective control-plan check the D7 documentation update references.
_CONTROL_PLAN_ROWS: list[dict[str, Any]] = [
    {
        "characteristic": "Housing 44821 finish bore diameter",
        "measurement_method": "CMM bore gauge",
        "sample_size": 5,
        "frequency": "Every setup + hourly",
        "reaction_plan": (
            "Stop production, re-verify offset per CP-44821 rev C control-plan review step"
        ),
        "lsl": 43.95,
        "usl": 44.05,
        "target": 44.0,
    }
]

#: Step 4 — post-fix FMEA ratings: residual risk after the control-plan review step exists.
_FMEA_RATINGS: dict[str, int] = {"severity": 7, "occurrence": 2, "detection": 2}

#: Step 4 — the D7 record, naming the control-plan check validated live in the same session.
_D7_RECORD: dict[str, Any] = {
    "systemic_changes_description": (
        "Setup approval now requires a control-plan review before release to production."
    ),
    "documentation_updates": [
        {
            "artifact_type": "CONTROL_PLAN",
            "artifact_reference": "CP-44821 rev C (validate_control_plan: schema_valid=True)",
            "updated_date": "2026-02-10",
            "updated_by": "S. Patel",
            "target": "ROOT_CAUSE",
        }
    ],
}

#: Negative control (a) — a blame-terminal one-step chain the 5-Why engine rejects outright.
_REJECTED_FIVE_WHY_ARGS: dict[str, Any] = {
    "steps": [
        {
            "step_number": 1,
            "why": "Why did the bore fail?",
            "because": "Operator error caused the mis-drill.",
        }
    ],
    "problem_statement": "Bore diameter undersized on Housing 44821",
    "root_cause": "Operator error caused the mis-drill.",
    "leg_type": "occurrence",
}

#: Leg-4 parity — the SKILL.md a host reads while driving this exact chain, per domain.
_SKILL_TOOL_NAMES: dict[str, tuple[str, ...]] = {
    "8d-problem-solving": ("validate_8d", "advance_8d"),
    "ncr-writing": ("write_ncr",),
    "5why-root-cause": ("validate_5why",),
    "control-plan": ("validate_control_plan",),
    "fmea-reviewer": ("lookup_fmea_ap",),
}


def _parsed(result: Any) -> dict[str, Any]:
    """structuredContent, asserted equal to the deserialized text payload."""
    assert not result.isError
    text = next(c for c in result.content if isinstance(c, TextContent))
    parsed = json.loads(text.text)
    assert result.structuredContent == parsed
    assert isinstance(parsed, dict)
    return parsed


def _report_at(discipline: str) -> dict[str, Any]:
    """The benchmark report rewound to one discipline; only the field under test is overwritten.

    ``EightDReport`` enforces neither fill order nor that later disciplines stay empty, so the
    sample's fully populated D0-D8 blocks are legitimate at any ``current_discipline``: each gate
    reads only the fields it checks for the ``previous`` state in question.
    """
    report = copy.deepcopy(SAMPLE_EIGHT_D_REPORT)
    report["current_discipline"] = discipline
    return report


def _expected_control_plan_payload(dataset_row_count: int) -> dict[str, Any]:
    """The payload ``validate_control_plan`` composes for a schema-clean plan with no FMEA.

    ``validate_control_plan`` is not a bare ``to_dict()`` passthrough — it composes the core
    ``validate_control_plan`` dataset result with the (here skipped) PFMEA linkage block — so the
    core leg of the parity chain re-assembles it the same way the tool does.
    """
    return {
        "basis": "AIAG Control Plan",
        "valid": True,
        "total_rows": dataset_row_count,
        "schema_valid": True,
        "schema_findings": [],
        "linkage_checked": False,
        "linkage_valid": None,
        "linked_rows": None,
        "orphan_characteristics": [],
        "uncovered_failure_modes": [],
        "linkage_findings": [],
    }


def _advance(parsed: dict[str, Any], report: dict[str, Any], target: str) -> dict[str, Any]:
    """Assert the direct-tool and core-engine legs of an ``advance_8d`` payload, and return it."""
    assert parsed == advance_8d(report=report, target=target)
    core = core_transition_8d(validate_eight_d(report), cast(EightDState, target))
    assert parsed == core.to_dict()
    return parsed


# ---------------------------------------------------------------------------
# 2. Valid chain: NCR -> D3 -> D4 -> D7 -> D8 -> CLOSED
# ---------------------------------------------------------------------------


def test_valid_chain_ncr_to_d3_to_d4_to_d7_to_closed() -> None:
    """One session drives the whole 8D chain to CLOSED, with payload parity at every hop."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # Step 1 — NCR containment: the nonconformance evidence D3 records validating.
            ncr = _parsed(await session.call_tool("write_ncr", arguments=dict(_NCR_ARGS)))
            assert ncr == write_ncr(**_NCR_ARGS)
            assert ncr == core_write_nonconformance(**_NCR_ARGS).to_dict()
            assert ncr["valid"] is True
            assert ncr["quantity_affected"] == 12
            assert ncr["part_lot_id"] == "HSG-44821-LOT9"

            # Step 2 — D3 -> D4 through the containment + linked-NCR gate (PDD-8D-008).
            d3_report = _report_at("D3")
            d3_report["d3"]["linked_ncr_validation"] = {
                "is_valid": True,
                "record_count": 1,
                "findings": [],
            }
            to_d4 = _advance(
                _parsed(
                    await session.call_tool(
                        "advance_8d", arguments={"report": d3_report, "target": "D4"}
                    )
                ),
                d3_report,
                "D4",
            )
            assert to_d4["verdict"] == "ADVANCED"
            assert to_d4["previous_state"] == "D3"
            assert to_d4["state"] == "D4"
            assert to_d4["reasons"] == []
            carried = to_d4["report"]

            # Step 3 — RCA D4: validate the root-cause chain, then carry the verdict forward.
            five_why = _parsed(await session.call_tool("validate_5why", arguments={}))
            assert five_why == validate_5why()
            assert five_why == validate_five_why_chain(
                data=SAMPLE_FIVE_WHY_STEPS,
                problem_statement="Hole positions outside of tolerance on CNC drilling station",
                root_cause="The induction plan was not signed by Engineering",
                leg_type="occurrence",
            ).to_dict()
            assert five_why["verdict"] == "ACCEPT"
            assert five_why["valid"] is True
            assert five_why["root_cause"] == "The induction plan was not signed by Engineering"

            # D4 -> D5 -> D6 -> D7 carry no gate: each is a straight ADVANCED on the sample's own
            # D5 / D6 data, with the previous hop's returned report threaded forward.
            for target in ("D5", "D6", "D7"):
                hop = _advance(
                    _parsed(
                        await session.call_tool(
                            "advance_8d", arguments={"report": carried, "target": target}
                        )
                    ),
                    carried,
                    target,
                )
                assert hop["verdict"] == "ADVANCED"
                assert hop["state"] == target
                assert hop["reasons"] == []
                carried = hop["report"]

            # Step 4 — FMEA / Control Plan prevention evidence for D7.
            control_plan = _parsed(
                await session.call_tool(
                    "validate_control_plan", arguments={"plan": _CONTROL_PLAN_ROWS}
                )
            )
            assert control_plan == validate_control_plan(_CONTROL_PLAN_ROWS)
            assert control_plan == _expected_control_plan_payload(
                len(validate_control_plan_core(_CONTROL_PLAN_ROWS).rows)
            )
            assert control_plan["valid"] is True
            assert control_plan["schema_valid"] is True

            fmea_ap = _parsed(
                await session.call_tool("lookup_fmea_ap", arguments=dict(_FMEA_RATINGS))
            )
            assert fmea_ap == lookup_fmea_ap(**_FMEA_RATINGS)
            assert fmea_ap == {
                **_FMEA_RATINGS,
                "rpn": rpn(**_FMEA_RATINGS),
                "action_priority": action_priority(**_FMEA_RATINGS),
            }
            assert fmea_ap["action_priority"] == "Low"
            assert fmea_ap["rpn"] == 28

            # D7 -> D8 through the prevention gate, with the validated control plan as the
            # qualifying documentation update.
            carried["d7"] = copy.deepcopy(_D7_RECORD)
            to_d8 = _advance(
                _parsed(
                    await session.call_tool(
                        "advance_8d", arguments={"report": carried, "target": "D8"}
                    )
                ),
                carried,
                "D8",
            )
            assert to_d8["verdict"] == "ADVANCED"
            assert to_d8["previous_state"] == "D7"
            assert to_d8["state"] == "D8"
            assert to_d8["reasons"] == []
            carried = to_d8["report"]

            # Step 5 — D8 -> CLOSED through the closure-evidence gate, carrying Step 3's verdict.
            carried["root_cause_validation"] = five_why
            carried["d8"]["linked_five_why_verdict"] = five_why["verdict"]
            closed = _advance(
                _parsed(
                    await session.call_tool(
                        "advance_8d", arguments={"report": carried, "target": "CLOSED"}
                    )
                ),
                carried,
                "CLOSED",
            )
            assert closed["verdict"] == "ADVANCED"
            assert closed["previous_state"] == "D8"
            assert closed["state"] == "CLOSED"
            assert closed["reasons"] == []
            assert closed["report"]["status"] == "CLOSED"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 3. Negative control (a): an rca-rejected D4 blocks at D8 -> CLOSED, not earlier
# ---------------------------------------------------------------------------


def test_invalid_chain_rca_rejected_d4_blocked_at_closure_gate() -> None:
    """A REJECT root-cause validation passes D4 -> D5 and is blocked only at the closure gate."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            rejected = _parsed(
                await session.call_tool("validate_5why", arguments=dict(_REJECTED_FIVE_WHY_ARGS))
            )
            assert rejected == validate_5why(**_REJECTED_FIVE_WHY_ARGS)
            assert rejected == validate_five_why_chain(
                data=_REJECTED_FIVE_WHY_ARGS["steps"],
                problem_statement=_REJECTED_FIVE_WHY_ARGS["problem_statement"],
                root_cause=_REJECTED_FIVE_WHY_ARGS["root_cause"],
                leg_type=_REJECTED_FIVE_WHY_ARGS["leg_type"],
            ).to_dict()
            assert rejected["verdict"] == "REJECT"
            assert rejected["valid"] is False
            assert "BLAME_TERMINAL_OPERATOR_ERROR" in {
                finding["code"] for finding in rejected["anti_patterns"]
            }

            # D4 has no transition gate: the same rejected validation still advances D4 -> D5.
            at_d4 = _report_at("D4")
            at_d4["root_cause_validation"] = rejected
            at_d4["d8"]["linked_five_why_verdict"] = "REJECT"
            past_d4 = _advance(
                _parsed(
                    await session.call_tool(
                        "advance_8d", arguments={"report": at_d4, "target": "D5"}
                    )
                ),
                at_d4,
                "D5",
            )
            assert past_d4["verdict"] == "ADVANCED"
            assert past_d4["state"] == "D5"
            assert past_d4["reasons"] == []

            # The closure gate is where it blocks. d8.linked_five_why_verdict matches the REJECT
            # verdict, so ROOT_CAUSE_VERDICT_MISMATCH cannot fire alongside it — exactly one
            # reason is expected.
            at_d8 = _report_at("D8")
            at_d8["root_cause_validation"] = rejected
            at_d8["d8"]["linked_five_why_verdict"] = "REJECT"
            blocked = _advance(
                _parsed(
                    await session.call_tool(
                        "advance_8d", arguments={"report": at_d8, "target": "CLOSED"}
                    )
                ),
                at_d8,
                "CLOSED",
            )
            assert blocked["verdict"] == "BLOCKED"
            assert blocked["previous_state"] == "D8"
            assert blocked["state"] == "D8"
            assert blocked["report"]["status"] == "OPEN"
            assert len(blocked["reasons"]) == 1
            assert blocked["reasons"][0]["code"] == "ROOT_CAUSE_REJECTED"
            assert blocked["reasons"][0]["rule_id"] == "RULE-8D-GATE-CLOSURE"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4. Negative control (b): a missing D7 blocks at the D7 -> D8 prevention gate
# ---------------------------------------------------------------------------


def test_invalid_chain_missing_d7_blocked_at_prevention_gate() -> None:
    """No D7 record, and a D7 record carrying no qualifying update, both block D7 -> D8."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # No D7 record at all.
            no_d7 = _report_at("D7")
            no_d7["d7"] = None
            blocked = _advance(
                _parsed(
                    await session.call_tool(
                        "advance_8d", arguments={"report": no_d7, "target": "D8"}
                    )
                ),
                no_d7,
                "D8",
            )
            assert blocked["verdict"] == "BLOCKED"
            assert blocked["previous_state"] == "D7"
            assert blocked["state"] == "D7"
            assert len(blocked["reasons"]) == 1
            assert blocked["reasons"][0]["code"] == "PREVENTION_UPDATE_MISSING"
            assert blocked["reasons"][0]["rule_id"] == "RULE-8D-GATE-PREVENTION"

            # A D7 record that exists but names no FMEA / Control Plan update: a different
            # in-progress state reaching the same gate reason.
            empty_d7 = _report_at("D7")
            empty_d7["d7"] = {
                "systemic_changes_description": (
                    "Systemic prevention changes are drafted but not yet documented."
                ),
                "documentation_updates": [],
            }
            unqualified = _advance(
                _parsed(
                    await session.call_tool(
                        "advance_8d", arguments={"report": empty_d7, "target": "D8"}
                    )
                ),
                empty_d7,
                "D8",
            )
            assert unqualified["verdict"] == "BLOCKED"
            assert unqualified["previous_state"] == "D7"
            assert unqualified["state"] == "D7"
            assert len(unqualified["reasons"]) == 1
            assert unqualified["reasons"][0]["code"] == "PREVENTION_UPDATE_MISSING"
            assert unqualified["reasons"][0]["rule_id"] == "RULE-8D-GATE-PREVENTION"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 5. Skill-doc parity (leg 4), once per domain touched by the chain
# ---------------------------------------------------------------------------


def test_chain_tools_documented_in_their_domain_skills() -> None:
    """Each domain's SKILL.md names the tool this chain calls live.

    A thin, chain-scoped check: a renamed tool whose skill doc was not updated fails here, at the
    integration layer. The deep per-skill governance (frontmatter, required sections, citation
    fidelity, no inline math) stays in ``tests/test_skills_conventions.py`` and is not duplicated.
    """
    for skill_name, tool_names in _SKILL_TOOL_NAMES.items():
        skill_md = (_REPO_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for tool_name in tool_names:
            assert tool_name in skill_md, f"{skill_name}/SKILL.md does not name {tool_name}"


# ---------------------------------------------------------------------------
# 6. Error isolation across the chained session
# ---------------------------------------------------------------------------


def test_chained_session_error_isolation() -> None:
    """A malformed call mid-chain returns isError and leaves the session's payloads unchanged."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            d3_report = _report_at("D3")
            baseline = _parsed(
                await session.call_tool(
                    "advance_8d", arguments={"report": d3_report, "target": "D4"}
                )
            )
            assert baseline["verdict"] == "ADVANCED"

            assert (await session.call_tool("advance_8d", arguments={"target": ""})).isError
            assert (
                await session.call_tool(
                    "advance_8d", arguments={"report": "not-a-dict", "target": "D4"}
                )
            ).isError
            assert (
                await session.call_tool("validate_5why", arguments={"steps": "not-a-list"})
            ).isError

            after = _parsed(
                await session.call_tool(
                    "advance_8d", arguments={"report": d3_report, "target": "D4"}
                )
            )
            assert after == baseline

    asyncio.run(_run())

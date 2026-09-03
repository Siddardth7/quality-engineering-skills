"""Pure 8D discipline state machine and cross-discipline acceptance gates.

Prerequisite evidence is grounded in the Ford Global 8D Manual and AIAG CQI-20 through
``rca/CITATIONS.tsv``. The adjacency graph and structured blocking behavior are platform design
decisions; no published source mandates this software state machine.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Literal

from quality_core.rca.eight_d_schema import EightDReport

__all__ = [
    "EightDState",
    "EightDTransitionResult",
    "GateCode",
    "TransitionReason",
    "TransitionVerdict",
    "transition_eight_d",
]

EightDState = Literal["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "CLOSED"]
TransitionVerdict = Literal["ADVANCED", "BLOCKED"]
GateCode = Literal[
    "ILLEGAL_TRANSITION",
    "CONTAINMENT_NOT_VERIFIED",
    "PREVENTION_UPDATE_MISSING",
    "ROOT_CAUSE_REJECTED",
    "ROOT_CAUSE_EVIDENCE_MISSING",
]

_NEXT: dict[EightDState, EightDState] = {
    "D0": "D1",
    "D1": "D2",
    "D2": "D3",
    "D3": "D4",
    "D4": "D5",
    "D5": "D6",
    "D6": "D7",
    "D7": "D8",
    "D8": "CLOSED",
}


@dataclass(frozen=True)
class TransitionReason:
    code: GateCode
    message: str
    rule_id: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {"code": self.code, "message": self.message, "rule_id": self.rule_id}


@dataclass(frozen=True)
class EightDTransitionResult:
    verdict: TransitionVerdict
    previous_state: EightDState
    state: EightDState
    reasons: tuple[TransitionReason, ...]
    report: EightDReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "previous_state": self.previous_state,
            "state": self.state,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "report": copy.deepcopy(self.report.model_dump(mode="json")),
        }


def _state(report: EightDReport) -> EightDState:
    return "CLOSED" if report.status == "CLOSED" else report.current_discipline


def _prevention_reason(report: EightDReport) -> TransitionReason | None:
    qualified = report.d7 is not None and any(
        update.artifact_type in {"FMEA", "CONTROL_PLAN"}
        for update in report.d7.documentation_updates
    )
    if qualified:
        return None
    return TransitionReason(
        "PREVENTION_UPDATE_MISSING",
        "D7 has no recorded FMEA or Control Plan update; record the applicable prevention documentation update before advancing.",
        "RULE-8D-GATE-PREVENTION",
    )


def _closure_reason(report: EightDReport) -> TransitionReason | None:
    discipline = report.d8
    validation = report.root_cause_validation
    if discipline is None or validation is None:
        return TransitionReason(
            "ROOT_CAUSE_EVIDENCE_MISSING",
            "D8 has no linked 5-Why validation evidence; validate and link the causal chain before closure.",
            "RULE-8D-GATE-CLOSURE",
        )
    if validation.verdict != discipline.linked_five_why_verdict:
        return TransitionReason(
            "ROOT_CAUSE_EVIDENCE_MISSING",
            "The linked D8 verdict does not match the supplied 5-Why validation result; reconcile the evidence before closure.",
            "RULE-8D-GATE-CLOSURE",
        )
    if validation.verdict == "REJECT" or not validation.valid:
        return TransitionReason(
            "ROOT_CAUSE_REJECTED",
            f"The linked 5-Why validation result is {validation.verdict} and invalid; resolve its findings before closure.",
            "RULE-8D-GATE-CLOSURE",
        )
    if validation.verdict == "WARNING" and discipline.warning_override is None:
        return TransitionReason(
            "ROOT_CAUSE_EVIDENCE_MISSING",
            "The linked 5-Why validation verdict is WARNING but has no recorded warning override; record the approval evidence before closure.",
            "RULE-8D-GATE-CLOSURE",
        )
    return None


def transition_eight_d(report: EightDReport, target: EightDState) -> EightDTransitionResult:
    """Attempt one adjacent 8D transition without mutating ``report``."""
    previous = _state(report)
    if report.status != "OPEN" or _NEXT.get(previous) != target:
        reason = TransitionReason(
            "ILLEGAL_TRANSITION",
            f"Transition from {previous} to {target} is not an allowed adjacent 8D step.",
            None,
        )
        return EightDTransitionResult("BLOCKED", previous, previous, (reason,), report)

    reasons: list[TransitionReason] = []
    if previous == "D3" and (report.d3 is None or not report.d3.is_verified):
        reasons.append(
            TransitionReason(
                "CONTAINMENT_NOT_VERIFIED",
                "D3 containment is not verified effective; record successful verification evidence for every containment action before advancing.",
                "RULE-8D-GATE-CONTAINMENT",
            )
        )
    if previous == "D7":
        gate_reason = _prevention_reason(report)
        if gate_reason is not None:
            reasons.append(gate_reason)
    if previous == "D8":
        closure_reason = _closure_reason(report)
        if closure_reason is not None:
            reasons.append(closure_reason)
        prevention_reason = _prevention_reason(report)
        if prevention_reason is not None:
            reasons.append(prevention_reason)
    if reasons:
        return EightDTransitionResult("BLOCKED", previous, previous, tuple(reasons), report)

    update = {"status": "CLOSED"} if target == "CLOSED" else {"current_discipline": target}
    candidate = report.model_copy(update=update, deep=True)
    advanced = EightDReport.model_validate(candidate.model_dump())
    return EightDTransitionResult("ADVANCED", previous, target, (), advanced)

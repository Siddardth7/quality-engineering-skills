"""Pure 8D discipline state machine and cross-discipline acceptance gates.

Prerequisite evidence is grounded in the Ford Global 8D Manual and AIAG CQI-20 through
``rca/CITATIONS.tsv``. The adjacency graph and structured blocking behavior are platform design
decisions; no published source mandates this software state machine.

The D3 to D4 gate reads two pieces of D3 evidence: containment verification
(``report.d3.is_verified``, ``RULE-8D-GATE-CONTAINMENT``) and the recorded outcome of validating
the linked nonconformity evidence (``report.d3.linked_ncr_validation``). The second is evaluated
by ``eight_d_schema._linked_ncr_deficiency`` — the same evaluator ``validate_d3_containment``
calls, so the advisory engine and this gate cannot answer "is the linked NCR acceptable"
differently — and blocking on it is a platform decision carrying no manual clause, declared as
``PDD-8D-008`` (Process Design Decision #8 in ``rca/ASSUMPTIONS_LOG.md``).

The D8 to CLOSED closure boundary reads one further piece of evidence, added by E7 (#210): D6's
permanent corrective actions must be verified effective (``report.d6.is_verified``,
``PCA_NOT_VERIFIED``). ``RULE-8D-D6`` backs the *substance* — "Validate actions and monitor
long-term results" — but no manual clause requires refusing a state transition or a CLOSED-report
construction over it, so that refusal is declared as ``PDD-8D-010`` (Process Design Decision #10
in ``rca/ASSUMPTIONS_LOG.md``), the same ``PDD-, not RULE-`` reasoning as ``PDD-8D-008``. The
deficiency itself is evaluated once, in ``eight_d_schema._closure_evidence_deficiencies``, which
the CLOSED-report model validator and this gate both consume.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Literal

from quality_core.rca.eight_d_schema import (
    EightDReport,
    _closure_evidence_deficiencies,
    _linked_ncr_deficiency,
)

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
    "LINKED_NCR_INVALID",
    "PCA_NOT_VERIFIED",
    "PREVENTION_UPDATE_MISSING",
    "ROOT_CAUSE_REJECTED",
    "ROOT_CAUSE_EVIDENCE_MISSING",
]

#: Rule identifier for the linked-NCR block. The ``PDD-`` prefix is deliberately not ``RULE-``:
#: every ``RULE-8D-*`` id names a ``rca/CITATIONS.tsv`` row backed by an on-box manual quote, and
#: no manual clause requires a transition to be refused over nonconformity-record validity. This
#: one names Process Design Decision #8 in ``rca/ASSUMPTIONS_LOG.md`` instead.
_LINKED_NCR_RULE_ID = "PDD-8D-008"

#: Rule identifier for the D6 closure-evidence block. Same "PDD-, not RULE-" reasoning as
#: _LINKED_NCR_RULE_ID: RULE-8D-D6 backs the *substance* (the PCAs must be validated), but no
#: manual clause requires refusing CLOSED-report construction / the D8 to CLOSED transition
#: specifically over it — that refusal mechanism is this platform's own, Process Design Decision
#: #10 in rca/ASSUMPTIONS_LOG.md.
_PCA_VALIDATION_RULE_ID = "PDD-8D-010"

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


def _linked_ncr_reason(report: EightDReport) -> TransitionReason | None:
    """Block D3 to D4 when D3 records that its linked nonconformity evidence was rejected.

    Delegates the verdict to ``eight_d_schema._linked_ncr_deficiency``, the single shared
    evaluator ``validate_d3_containment`` also consults, and never re-derives NCR validity here.
    An absent ``linked_ncr_validation`` is not a block: unlinked evidence is a normal in-progress
    state, which the advisory engine reports as a warning.
    """
    recorded = None if report.d3 is None else report.d3.linked_ncr_validation
    deficiency = _linked_ncr_deficiency(recorded)
    if deficiency is None:
        return None
    return TransitionReason(
        deficiency.code,
        f"{deficiency.message} Correct the linked Nonconformance Record evidence and re-record "
        "its validation outcome before advancing.",
        _LINKED_NCR_RULE_ID,
    )


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


def _closure_reasons(report: EightDReport) -> tuple[TransitionReason, ...]:
    """Map shared closure deficiencies to the engine's stable public reason vocabulary."""
    reasons: list[TransitionReason] = []
    for deficiency in _closure_evidence_deficiencies(report):
        if deficiency.code == "CONTAINMENT_NOT_VERIFIED":
            reasons.append(
                TransitionReason(deficiency.code, deficiency.message, "RULE-8D-GATE-CONTAINMENT")
            )
        elif deficiency.code == "PCA_NOT_VERIFIED":
            reasons.append(
                TransitionReason(deficiency.code, deficiency.message, _PCA_VALIDATION_RULE_ID)
            )
        elif deficiency.code == "PREVENTION_UPDATE_MISSING":
            reasons.append(
                TransitionReason(deficiency.code, deficiency.message, "RULE-8D-GATE-PREVENTION")
            )
        else:
            code: GateCode = (
                "ROOT_CAUSE_REJECTED"
                if deficiency.code == "ROOT_CAUSE_REJECTED"
                else "ROOT_CAUSE_EVIDENCE_MISSING"
            )
            reasons.append(TransitionReason(code, deficiency.message, "RULE-8D-GATE-CLOSURE"))
    return tuple(reasons)


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
    if previous == "D3":
        if report.d3 is None or not report.d3.is_verified:
            reasons.append(
                TransitionReason(
                    "CONTAINMENT_NOT_VERIFIED",
                    "D3 containment is not verified effective; record successful verification evidence for every containment action before advancing.",
                    "RULE-8D-GATE-CONTAINMENT",
                )
            )
        ncr_reason = _linked_ncr_reason(report)
        if ncr_reason is not None:
            reasons.append(ncr_reason)
    if previous == "D7":
        gate_reason = _prevention_reason(report)
        if gate_reason is not None:
            reasons.append(gate_reason)
    if previous == "D8":
        reasons.extend(_closure_reasons(report))
    if reasons:
        return EightDTransitionResult("BLOCKED", previous, previous, tuple(reasons), report)

    update = {"status": "CLOSED"} if target == "CLOSED" else {"current_discipline": target}
    candidate = report.model_copy(update=update, deep=True)
    advanced = EightDReport.model_validate(candidate.model_dump())
    return EightDTransitionResult("ADVANCED", previous, target, (), advanced)

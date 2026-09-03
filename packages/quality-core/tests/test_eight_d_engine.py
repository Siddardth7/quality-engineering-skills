"""Exhaustive contract tests for the pure 8D transition and gate engine."""

from __future__ import annotations

import datetime
import json
from itertools import product

import pydantic
import pytest
import quality_core.rca as rca
from quality_core.rca import (
    ContainmentAction,
    D3Discipline,
    D7Discipline,
    D8Discipline,
    DocumentationUpdate,
    EffectivenessVerification,
    EightDReport,
    WarningOverride,
    transition_eight_d,
    validate_five_why_chain,
)
from quality_core.rca.five_why import FiveWhyValidationResult

DAY = datetime.date(2026, 1, 2)
STATES = ("D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "CLOSED")
LEGAL = {
    ("D0", "D1"), ("D1", "D2"), ("D2", "D3"), ("D3", "D4"), ("D4", "D5"),
    ("D5", "D6"), ("D6", "D7"), ("D7", "D8"), ("D8", "CLOSED"),
}


def _verification(effective: bool) -> EffectivenessVerification:
    return EffectivenessVerification(
        verified_by="Verifier", verified_date=DAY, evidence="Measured evidence", is_effective=effective
    )


def _d3(*effective: bool | None) -> D3Discipline:
    return D3Discipline(actions=[
        ContainmentAction(
            description=f"Containment {index}", implemented_date=DAY,
            verification=None if value is None else _verification(value),
        )
        for index, value in enumerate(effective)
    ])


def _d7(artifact: str | None = "FMEA") -> D7Discipline:
    updates = [] if artifact is None else [DocumentationUpdate(
        artifact_type=artifact, artifact_reference="DOC-1", updated_date=DAY, updated_by="Owner"
    )]
    return D7Discipline(systemic_changes_description="System changed", documentation_updates=updates)


def _validation(verdict: str = "ACCEPT") -> FiveWhyValidationResult:
    chains = {
        "ACCEPT": [
            {"step_number": 1, "why": "Why did bearing seize?", "because": "Lubricant dried up."},
            {"step_number": 2, "why": "Why did it dry up?", "because": "Maintenance routine was omitted."},
            {"step_number": 3, "why": "Why was routine omitted?", "because": "Training procedure lacked a checklist."},
        ],
        "WARNING": [
            {"step_number": 1, "why": "Why did the bearing overheat?", "because": "The grease dried up completely."},
            {"step_number": 2, "why": "Why did warehouse inventory mismatch yesterday?", "because": "Barcode scanner battery voltage dropped."},
            {"step_number": 3, "why": "Why did scanner battery drop?", "because": "Charging dock maintenance procedure was missing."},
        ],
        "REJECT": [
            {"step_number": 1, "why": "Why did the engine stall?", "because": "The engine stalled unexpectedly."},
            {"step_number": 2, "why": "Why did it stall unexpectedly?", "because": "Fuel stopped due to a clogged filter."},
            {"step_number": 3, "why": "Why was filter clogged?", "because": "Maintenance procedure lacked an interval."},
        ],
    }
    result = validate_five_why_chain(chains[verdict], problem_statement={
        "ACCEPT": "Bearing seized", "WARNING": "Bearing overheated", "REJECT": "Engine stalled unexpectedly",
    }[verdict])
    assert result.verdict == verdict
    return result


def _d8(verdict: str = "ACCEPT", *, override: bool = False) -> D8Discipline:
    evidence = WarningOverride(
        approved_by="Approver", justification="Reviewed warning", override_date=DAY
    ) if override else None
    return D8Discipline(
        team_recognition_notes="Team thanked", linked_five_why_verdict=verdict,
        warning_override=evidence,
    )


def _report(state: str, **updates: object) -> EightDReport:
    values: dict[str, object] = {
        "report_id": "8D-205", "initiated_date": DAY,
        "status": "CLOSED" if state == "CLOSED" else "OPEN",
        "current_discipline": "D8" if state == "CLOSED" else state,
    }
    if state == "CLOSED":
        values.update(d3=_d3(True), d7=_d7(), d8=_d8(), root_cause_validation=_validation())
    values.update(updates)
    return EightDReport(**values)


@pytest.mark.parametrize("current,target", sorted(LEGAL))
def test_every_adjacent_transition_advances_with_gate_evidence(current: str, target: str) -> None:
    report = _report(
        current, d3=_d3(True), d7=_d7(), d8=_d8(), root_cause_validation=_validation()
    )
    before = report.model_dump()
    result = transition_eight_d(report, target)
    assert (result.verdict, result.previous_state, result.state, result.reasons) == (
        "ADVANCED", current, target, (),
    )
    assert report.model_dump() == before
    assert result.report is not report
    if target == "CLOSED":
        assert result.report.status == "CLOSED"
        assert result.report.current_discipline == "D8"
    else:
        assert result.report.status == "OPEN"
        assert result.report.current_discipline == target


@pytest.mark.parametrize("current,target", sorted(set(product(STATES, STATES)) - LEGAL))
def test_all_non_adjacent_state_pairs_are_illegal(current: str, target: str) -> None:
    report = _report(
        current, d3=_d3(True), d7=_d7(), d8=_d8(), root_cause_validation=_validation()
    )
    result = transition_eight_d(report, target)
    assert (result.verdict, result.previous_state, result.state) == ("BLOCKED", current, current)
    assert result.report is report
    assert [reason.to_dict() for reason in result.reasons] == [{
        "code": "ILLEGAL_TRANSITION",
        "message": f"Transition from {current} to {target} is not an allowed adjacent 8D step.",
        "rule_id": None,
    }]


@pytest.mark.parametrize("discipline", ["D0", "D3", "D8"])
def test_cancelled_lifecycle_is_terminal_and_retains_prior_discipline(discipline: str) -> None:
    report = EightDReport(
        report_id="8D-205", initiated_date=DAY, status="CANCELLED", current_discipline=discipline
    )
    result = transition_eight_d(report, "D1")
    assert (result.verdict, result.previous_state, result.state) == (
        "BLOCKED", discipline, discipline,
    )


def test_valid_direct_closed_reconstruction_is_terminal() -> None:
    report = _report("CLOSED")
    result = transition_eight_d(report, "D8")
    assert (result.verdict, result.previous_state, result.state) == ("BLOCKED", "CLOSED", "CLOSED")


@pytest.mark.parametrize(
    "updates,match",
    [
        ({"current_discipline": "D0"}, "must have current_discipline D8"),
        ({"d3": None}, "requires verified-effective D3 containment"),
        ({"d3": _d3(False)}, "requires verified-effective D3 containment"),
        ({"d3": _d3(None)}, "requires verified-effective D3 containment"),
        ({"d8": None}, "requires D8"),
        ({"root_cause_validation": None}, "requires provenance-bearing"),
        ({"d7": None}, "requires a D7 FMEA or Control Plan update"),
    ],
)
def test_direct_closed_reconstruction_rejects_contradictions(
    updates: dict[str, object], match: str
) -> None:
    values = _report("CLOSED").model_dump()
    values.update(updates)
    with pytest.raises(pydantic.ValidationError, match=match):
        EightDReport.model_validate(values)


@pytest.mark.parametrize("evidence", [(None,), (False,), (True, False), (True, None)])
def test_d3_requires_every_typed_verification_to_be_effective(evidence: tuple[bool | None, ...]) -> None:
    report = _report("D3", d3=_d3(*evidence))
    result = transition_eight_d(report, "D4")
    assert result.report is report
    assert [r.code for r in result.reasons] == ["CONTAINMENT_NOT_VERIFIED"]
    assert result.reasons[0].rule_id == "RULE-8D-GATE-CONTAINMENT"
    assert "every containment action" in result.reasons[0].message


def test_d3_missing_discipline_blocks() -> None:
    result = transition_eight_d(_report("D3"), "D4")
    assert [r.code for r in result.reasons] == ["CONTAINMENT_NOT_VERIFIED"]


@pytest.mark.parametrize("artifact", ["FMEA", "CONTROL_PLAN"])
def test_d7_accepts_each_qualifying_document_update(artifact: str) -> None:
    assert transition_eight_d(_report("D7", d7=_d7(artifact)), "D8").verdict == "ADVANCED"


@pytest.mark.parametrize("artifact", [None, "PROCESS_FLOW", "WORK_INSTRUCTION", "OTHER"])
def test_d7_rejects_missing_or_nonqualifying_updates(artifact: str | None) -> None:
    result = transition_eight_d(_report("D7", d7=_d7(artifact)), "D8")
    assert [r.code for r in result.reasons] == ["PREVENTION_UPDATE_MISSING"]
    assert result.reasons[0].rule_id == "RULE-8D-GATE-PREVENTION"


def test_d7_missing_discipline_blocks() -> None:
    assert transition_eight_d(_report("D7"), "D8").reasons[0].code == "PREVENTION_UPDATE_MISSING"


@pytest.mark.parametrize("verdict,override", [("ACCEPT", False), ("WARNING", True)])
def test_d8_accepts_eligible_root_cause_evidence(verdict: str, override: bool) -> None:
    validation = _validation(verdict)
    result = transition_eight_d(_report(
        "D8", d3=_d3(True), d7=_d7(), d8=_d8(verdict, override=override),
        root_cause_validation=validation,
    ), "CLOSED")
    assert result.verdict == "ADVANCED"
    assert result.report.status == "CLOSED"


@pytest.mark.parametrize(
    "d8,code,fragment",
    [(None, "ROOT_CAUSE_EVIDENCE_MISSING", "requires D8"),
     (_d8("REJECT"), "ROOT_CAUSE_REJECTED", "valid, non-REJECT"),
     (_d8("WARNING"), "ROOT_CAUSE_EVIDENCE_MISSING", "requires warning_override")],
)
def test_d8_rejects_missing_rejected_or_unapproved_warning_evidence(
    d8: D8Discipline | None, code: str, fragment: str
) -> None:
    validation = None if d8 is None else _validation(d8.linked_five_why_verdict)
    result = transition_eight_d(_report(
        "D8", d3=_d3(True), d7=_d7(), d8=d8, root_cause_validation=validation,
    ), "CLOSED")
    assert code in [r.code for r in result.reasons]
    assert result.reasons[0].rule_id == "RULE-8D-GATE-CLOSURE"
    assert any(fragment in reason.message for reason in result.reasons)


def test_d8_rejects_missing_typed_root_cause_validation() -> None:
    result = transition_eight_d(
        _report("D8", d3=_d3(True), d7=_d7(), d8=_d8("ACCEPT")), "CLOSED"
    )
    assert [reason.code for reason in result.reasons] == ["ROOT_CAUSE_EVIDENCE_MISSING"]
    assert "provenance-bearing root_cause_validation" in result.reasons[0].message


def test_d8_defense_in_depth_collects_root_cause_then_prevention_reasons() -> None:
    report = _report(
        "D8", d3=_d3(True), d8=_d8("REJECT"), d7=_d7("OTHER"),
        root_cause_validation=_validation("REJECT")
    )
    result = transition_eight_d(report, "CLOSED")
    assert [r.code for r in result.reasons] == ["ROOT_CAUSE_REJECTED", "PREVENTION_UPDATE_MISSING"]
    assert result.report is report


def test_d8_requires_verdict_to_match_typed_validation() -> None:
    values = _report("CLOSED").model_dump()
    values.update(d8=_d8("ACCEPT").model_dump(), root_cause_validation=_validation("WARNING"))
    with pytest.raises(pydantic.ValidationError, match="verdict must match"):
        EightDReport.model_validate(values)


def test_engine_defensively_rejects_constructed_verdict_mismatch() -> None:
    report = EightDReport.model_construct(
        report_id="8D-205", initiated_date=DAY, status="OPEN", current_discipline="D8",
        d3=_d3(True), d7=_d7(), d8=_d8("ACCEPT"), root_cause_validation=_validation("WARNING"),
    )
    result = transition_eight_d(report, "CLOSED")
    assert result.reasons[0].code == "ROOT_CAUSE_EVIDENCE_MISSING"
    assert "must match" in result.reasons[0].message


def test_d8_invalid_validation_blocks_even_when_verdict_is_not_reject() -> None:
    invalid = _validation("REJECT")
    invalid.verdict = "ACCEPT"
    report = _report(
        "D8", d3=_d3(True), d7=_d7(), d8=_d8("ACCEPT"), root_cause_validation=invalid
    )
    result = transition_eight_d(report, "CLOSED")
    assert [reason.code for reason in result.reasons] == ["ROOT_CAUSE_REJECTED"]


def test_direct_closed_rejects_invalid_nonreject_and_warning_without_override() -> None:
    invalid = _validation("REJECT")
    invalid.verdict = "ACCEPT"
    base = _report("CLOSED").model_dump()
    base["root_cause_validation"] = invalid
    with pytest.raises(pydantic.ValidationError, match="requires a valid, non-REJECT"):
        EightDReport.model_validate(base)

    warning = _validation("WARNING")
    base.update(root_cause_validation=warning, d8=_d8("WARNING").model_dump())
    with pytest.raises(pydantic.ValidationError, match="WARNING verdict requires warning_override"):
        EightDReport.model_validate(base)


@pytest.mark.parametrize(
    "case,engine_code",
    [
        ("d3_missing", "CONTAINMENT_NOT_VERIFIED"),
        ("d3_unverified", "CONTAINMENT_NOT_VERIFIED"),
        ("d7_missing", "PREVENTION_UPDATE_MISSING"),
        ("d8_missing", "ROOT_CAUSE_EVIDENCE_MISSING"),
        ("validation_missing", "ROOT_CAUSE_EVIDENCE_MISSING"),
        ("validation_invalid", "ROOT_CAUSE_REJECTED"),
        ("validation_reject", "ROOT_CAUSE_REJECTED"),
        ("verdict_mismatch", "ROOT_CAUSE_EVIDENCE_MISSING"),
        ("warning_override_missing", "ROOT_CAUSE_EVIDENCE_MISSING"),
    ],
)
def test_direct_and_transition_closure_paths_reject_same_evidence_deficiencies(
    case: str, engine_code: str
) -> None:
    values = _report("CLOSED").model_dump()
    if case == "d3_missing":
        values["d3"] = None
    elif case == "d3_unverified":
        values["d3"] = _d3(None).model_dump()
    elif case == "d7_missing":
        values["d7"] = None
    elif case == "d8_missing":
        values["d8"] = None
    elif case == "validation_missing":
        values["root_cause_validation"] = None
    elif case == "validation_invalid":
        validation = _validation("REJECT")
        validation.verdict = "ACCEPT"
        values["root_cause_validation"] = validation
    elif case == "validation_reject":
        values.update(
            d8=_d8("REJECT").model_dump(), root_cause_validation=_validation("REJECT")
        )
    elif case == "verdict_mismatch":
        values["root_cause_validation"] = _validation("WARNING")
    else:
        values.update(
            d8=_d8("WARNING").model_dump(), root_cause_validation=_validation("WARNING")
        )

    with pytest.raises(pydantic.ValidationError):
        EightDReport.model_validate(values)

    values["status"] = "OPEN"
    transition_report = EightDReport.model_validate(values)
    result = transition_eight_d(transition_report, "CLOSED")
    assert result.verdict == "BLOCKED"
    assert engine_code in [reason.code for reason in result.reasons]


@pytest.mark.parametrize("verdict,override", [("ACCEPT", False), ("WARNING", True)])
def test_direct_and_transition_closure_paths_accept_same_complete_evidence(
    verdict: str, override: bool
) -> None:
    values = _report("CLOSED").model_dump()
    values.update(
        d8=_d8(verdict, override=override).model_dump(),
        root_cause_validation=_validation(verdict),
    )
    direct = EightDReport.model_validate(values)
    assert direct.status == "CLOSED"

    values["status"] = "OPEN"
    result = transition_eight_d(EightDReport.model_validate(values), "CLOSED")
    assert result.verdict == "ADVANCED"
    assert result.report.status == "CLOSED"


def test_shared_closure_evaluator_rejects_missing_d3_on_direct_path() -> None:
    values = _report("CLOSED").model_dump()
    values["d3"] = None
    with pytest.raises(pydantic.ValidationError, match="verified-effective D3"):
        EightDReport.model_validate(values)


def test_shared_closure_evaluator_rejects_missing_d3_on_transition_path() -> None:
    report = _report(
        "D8", d3=None, d7=_d7(), d8=_d8(), root_cause_validation=_validation()
    )
    result = transition_eight_d(report, "CLOSED")
    assert "CONTAINMENT_NOT_VERIFIED" in [reason.code for reason in result.reasons]


def test_result_equality_determinism_json_serialization_and_copy_isolation() -> None:
    report = _report("D0")
    first = transition_eight_d(report, "D1")
    second = transition_eight_d(report, "D1")
    assert first == second
    payload = first.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    payload["report"]["report_id"] = "tampered"
    payload["reasons"].append({"code": "tampered"})
    assert first.report.report_id == "8D-205"
    assert first.reasons == ()


def test_schema_default_ingest_and_engine_public_exports() -> None:
    report = EightDReport.model_validate({"report_id": "8D-205", "initiated_date": "2026-01-02"})
    assert report.current_discipline == "D0"
    expected = {
        "EightDDiscipline", "EightDState", "EightDTransitionResult", "GateCode",
        "TransitionReason", "TransitionVerdict", "transition_eight_d",
    }
    assert expected <= set(rca.__all__)
    assert all(hasattr(rca, name) for name in expected)

"""Contract tests for the D8 closure engine and the ``validate_8d`` whole-report orchestrator.

Issue #212 (E9). These cover:

* ``validate_d8_closure`` — the advisory pre-flight over the shared closure-evidence boundary
  plus the D8-record's own findings.
* ``validate_8d`` — the read-only orchestrator that dispatches every D0-D8 advisory engine
  (D4 deliberately excluded) and every closure gate, then combines them.

Kept separate from ``test_eight_d_engine.py`` (the pure gate) on purpose: this suite tests the
*advisory* layer, never ``transition_eight_d`` — except for the single "orchestrator and gate
agree" test, which asserts exactly that they never disagree on the same complete report.
"""

from __future__ import annotations

import dataclasses
import datetime
import json

import pytest
from quality_core.rca import (
    ContainmentAction,
    D3Discipline,
    D6Discipline,
    D7Discipline,
    D8Discipline,
    D8Finding,
    D8ValidationResult,
    DocumentationUpdate,
    EffectivenessVerification,
    EightDReport,
    EightDValidationResult,
    ImplementedAction,
    LinkedNCRValidation,
    WarningOverride,
    transition_eight_d,
    validate_8d,
    validate_d8_closure,
    validate_five_why_chain,
)
from quality_core.rca.eight_d_schema import (
    CandidateCauseTest,
    CorrectiveActionCandidate,
    D0Discipline,
    D1Discipline,
    D2Discipline,
    D4Discipline,
    D5Discipline,
    EscapePointFinding,
    RootCauseFinding,
    TeamMember,
)
from quality_core.rca.five_why import FiveWhyValidationResult

DAY = datetime.date(2026, 1, 2)


# --------------------------------------------------------------------------------------
# Builders (mirroring test_eight_d_engine.py so the two suites stay comparable)
# --------------------------------------------------------------------------------------


def _verification(effective: bool) -> EffectivenessVerification:
    return EffectivenessVerification(
        verified_by="Verifier",
        verified_date=DAY,
        evidence="Measured evidence",
        is_effective=effective,
    )


def _d3(*effective: bool | None) -> D3Discipline:
    return D3Discipline(
        actions=[
            ContainmentAction(
                description=f"Containment {index}",
                implemented_date=DAY,
                verification=None if value is None else _verification(value),
            )
            for index, value in enumerate(effective)
        ]
    )


def _d3_with_ncr(validation: LinkedNCRValidation | None) -> D3Discipline:
    """A verified-effective D3 that additionally carries a recorded linked-NCR outcome."""
    return D3Discipline(
        actions=[
            ContainmentAction(
                description="Containment 0",
                implemented_date=DAY,
                verification=_verification(True),
            )
        ],
        linked_ncr_validation=validation,
    )


def _d6(*effective: bool | None) -> D6Discipline:
    return D6Discipline(
        implemented_actions=[
            ImplementedAction(
                corrective_action_id=f"PCA-{index}",
                implemented_date=DAY,
                verification=None if value is None else _verification(value),
            )
            for index, value in enumerate(effective)
        ]
    )


def _d7(artifact: str | None = "FMEA", target: str | None = "ROOT_CAUSE") -> D7Discipline:
    updates = (
        []
        if artifact is None
        else [
            DocumentationUpdate(
                artifact_type=artifact,
                artifact_reference="DOC-1",
                updated_date=DAY,
                updated_by="Owner",
                target=target,
            )
        ]
    )
    return D7Discipline(
        systemic_changes_description="System changed", documentation_updates=updates
    )


def _validation(verdict: str = "ACCEPT") -> FiveWhyValidationResult:
    chains = {
        "ACCEPT": [
            {"step_number": 1, "why": "Why did bearing seize?", "because": "Lubricant dried up."},
            {
                "step_number": 2,
                "why": "Why did it dry up?",
                "because": "Maintenance routine was omitted.",
            },
            {
                "step_number": 3,
                "why": "Why was routine omitted?",
                "because": "Training procedure lacked a checklist.",
            },
        ],
        "WARNING": [
            {
                "step_number": 1,
                "why": "Why did the bearing overheat?",
                "because": "The grease dried up completely.",
            },
            {
                "step_number": 2,
                "why": "Why did warehouse inventory mismatch yesterday?",
                "because": "Barcode scanner battery voltage dropped.",
            },
            {
                "step_number": 3,
                "why": "Why did scanner battery drop?",
                "because": "Charging dock maintenance procedure was missing.",
            },
        ],
        "REJECT": [
            {
                "step_number": 1,
                "why": "Why did the engine stall?",
                "because": "The engine stalled unexpectedly.",
            },
            {
                "step_number": 2,
                "why": "Why did it stall unexpectedly?",
                "because": "Fuel stopped due to a clogged filter.",
            },
            {
                "step_number": 3,
                "why": "Why was filter clogged?",
                "because": "Maintenance procedure lacked an interval.",
            },
        ],
    }
    result = validate_five_why_chain(
        chains[verdict],
        problem_statement={
            "ACCEPT": "Bearing seized",
            "WARNING": "Bearing overheated",
            "REJECT": "Engine stalled unexpectedly",
        }[verdict],
    )
    assert result.verdict == verdict
    return result


def _d8(verdict: str = "ACCEPT", *, override: bool = False, reviewed: bool = True) -> D8Discipline:
    evidence = (
        WarningOverride(approved_by="Approver", justification="Reviewed warning", override_date=DAY)
        if override
        else None
    )
    return D8Discipline(
        team_recognition_notes="Team thanked",
        documentation_reviewed=reviewed,
        documentation_review_date=DAY if reviewed else None,
        documentation_reviewed_by="Reviewer" if reviewed else None,
        linked_five_why_verdict=verdict,
        warning_override=evidence,
    )


def _d8_unattributed(
    *, by: str | None = None, date: datetime.date | None = None
) -> D8Discipline:
    """A D8 whose documentation IS reviewed but whose review provenance is incomplete.

    documentation_reviewed=True (so the D8_DOCUMENTATION_NOT_REVIEWED error does NOT fire),
    but at least one of documentation_reviewed_by / documentation_review_date is None, which
    is what the D8_REVIEW_PROVENANCE_INCOMPLETE warning arm checks.
    """
    return D8Discipline(
        team_recognition_notes="Team thanked",
        documentation_reviewed=True,
        documentation_review_date=date,
        documentation_reviewed_by=by,
        linked_five_why_verdict="ACCEPT",
    )


def _closeable_updates() -> dict[str, object]:
    """Every field a report needs to be fully closeable AND advisory-clean (ACCEPT)."""
    return dict(
        d3=_d3(True),
        d6=_d6(True),
        d7=_d7(),
        d8=_d8("ACCEPT", reviewed=True),
        root_cause_validation=_validation("ACCEPT"),
    )


def _report(state: str = "D8", **updates: object) -> EightDReport:
    values: dict[str, object] = {
        "report_id": "8D-212",
        "initiated_date": DAY,
        "status": "CLOSED" if state == "CLOSED" else "OPEN",
        "current_discipline": "D8" if state == "CLOSED" else state,
    }
    values.update(updates)
    return EightDReport(**values)


def _closeable_report(state: str = "D8", **overrides: object) -> EightDReport:
    updates = _closeable_updates()
    updates.update(overrides)
    return _report(state, **updates)


def _full_d5() -> D5Discipline:
    return D5Discipline(
        candidates=[
            CorrectiveActionCandidate(
                action_id="PCA-RC",
                target="ROOT_CAUSE",
                description="Corrective action for the root cause",
                selection_criteria="Lowest residual risk.",
                verified_no_undesirable_effects=True,
                verification_notes="FMEA re-run recorded.",
            ),
            CorrectiveActionCandidate(
                action_id="PCA-EP",
                target="ESCAPE_POINT",
                description="Corrective action for the escape point",
                selection_criteria="Lowest residual risk.",
                verified_no_undesirable_effects=True,
                verification_notes="FMEA re-run recorded.",
            ),
        ]
    )


def _full_d6() -> D6Discipline:
    return D6Discipline(
        implemented_actions=[
            ImplementedAction(
                corrective_action_id="PCA-RC", implemented_date=DAY, verification=_verification(True)
            ),
            ImplementedAction(
                corrective_action_id="PCA-EP", implemented_date=DAY, verification=_verification(True)
            ),
        ],
        interim_containment_removed_date=DAY,
    )


def _clean_updates() -> dict[str, object]:
    """A report that is closeable AND every computed discipline is ACCEPT (overall ACCEPT)."""
    return dict(
        d3=_d3_with_ncr(LinkedNCRValidation(is_valid=True)),
        d4=_d4(),
        d5=_full_d5(),
        d6=_full_d6(),
        d7=_d7(),
        d8=_d8("ACCEPT", reviewed=True),
        root_cause_validation=_validation("ACCEPT"),
    )


def _clean_report(state: str = "D8", **overrides: object) -> EightDReport:
    updates = _clean_updates()
    updates.update(overrides)
    return _report(state, **updates)


def _d4() -> D4Discipline:
    return D4Discipline(
        candidate_causes_tested=[
            CandidateCauseTest(
                description="Missing approval control",
                test_data="Revision history shows no approval step.",
                result="CONFIRMED",
            )
        ],
        root_cause=RootCauseFinding(
            statement="Approval control was never added to the routing.",
            verification_evidence="Revision history confirms the missing approval control.",
            five_why_leg_type="occurrence",
            five_why_verdict="ACCEPT",
        ),
        escape_point=EscapePointFinding(
            statement="Final review step never checked the routing.",
            verification_evidence="Control-plan revision history confirms the missing review.",
            five_why_leg_type="escape",
            five_why_verdict="ACCEPT",
        ),
    )


def _codes(result: D8ValidationResult) -> list[str]:
    return [f.code for f in result.findings]


def _gate_codes(result: EightDValidationResult) -> list[str]:
    return [reason.code for reason in result.gate_reasons]


# --------------------------------------------------------------------------------------
# validate_d8_closure — to_dict shapes
# --------------------------------------------------------------------------------------


def test_d8_finding_to_dict_shape() -> None:
    finding = D8Finding(code="CODE", severity="info", message="msg", recommendation="rec")
    assert finding.to_dict() == {
        "code": "CODE",
        "severity": "info",
        "message": "msg",
        "recommendation": "rec",
    }


def test_d8_validation_result_to_dict_nests_findings_and_is_json_serializable() -> None:
    result = validate_d8_closure(_closeable_report())
    payload = result.to_dict()
    assert payload["basis"] == "Ford Global 8D / AIAG CQI-20"
    assert payload["valid"] is True
    assert payload["verdict"] == "ACCEPT"
    assert payload["d8_recorded"] is True
    assert payload["documentation_reviewed"] is True
    assert payload["linked_five_why_verdict"] == "ACCEPT"
    assert payload["closeable"] is True
    assert payload["findings"] == [f.to_dict() for f in result.findings]
    assert payload["recommendations"] is not result.recommendations
    json.dumps(payload)  # must be JSON-serializable


# --------------------------------------------------------------------------------------
# validate_d8_closure — verdict derivation and per-record findings
# --------------------------------------------------------------------------------------


def test_d8_clean_pass_emits_only_d8_ready_and_accepts() -> None:
    result = validate_d8_closure(_closeable_report())
    assert (result.verdict, result.valid) == ("ACCEPT", True)
    assert _codes(result) == ["D8_READY"]
    assert result.findings[0].severity == "info"
    assert result.closeable is True
    assert result.d8_recorded is True
    assert result.documentation_reviewed is True
    assert result.linked_five_why_verdict == "ACCEPT"


def test_d8_not_started_is_warning_finding_but_verdict_is_reject_via_d8_missing() -> None:
    """d8 is None: D8_NOT_STARTED (warning) always coexists with D8_MISSING (error).

    Pins the coder's reachability caveat: the WARNING branch of the verdict derivation is
    NOT reachable through a d8-None report, because _closure_evidence_deficiencies always adds
    the D8_MISSING error alongside it, so the verdict is REJECT.
    """
    result = validate_d8_closure(_report("D8", root_cause_validation=_validation("ACCEPT")))
    codes = _codes(result)
    assert "D8_NOT_STARTED" in codes
    assert "D8_MISSING" in codes
    not_started = next(f for f in result.findings if f.code == "D8_NOT_STARTED")
    assert not_started.severity == "warning"
    assert (result.verdict, result.valid) == ("REJECT", False)
    assert result.d8_recorded is False
    assert result.documentation_reviewed is False
    assert result.linked_five_why_verdict is None
    assert result.closeable is False


def test_d8_documentation_not_reviewed_rejects_while_still_closeable() -> None:
    """The disagreement case: closure evidence complete (closeable) but doc review missing.

    _closure_evidence_deficiencies never reads documentation_reviewed, so `closeable` is True
    while the advisory verdict is REJECT. The two are distinct facts by design.
    """
    result = validate_d8_closure(_closeable_report(d8=_d8("ACCEPT", reviewed=False)))
    assert result.closeable is True
    assert (result.verdict, result.valid) == ("REJECT", False)
    assert "D8_DOCUMENTATION_NOT_REVIEWED" in _codes(result)
    doc = next(f for f in result.findings if f.code == "D8_DOCUMENTATION_NOT_REVIEWED")
    assert doc.severity == "error"


def test_d8_root_cause_rejected_record_finding_fires_on_reject_verdict() -> None:
    result = validate_d8_closure(
        _closeable_report(d8=_d8("REJECT", reviewed=True), root_cause_validation=_validation("REJECT"))
    )
    codes = _codes(result)
    assert "D8_ROOT_CAUSE_REJECTED" in codes
    # elif is mutually exclusive: the WARNING-override finding must not also fire.
    assert "D8_WARNING_OVERRIDE_MISSING" not in codes
    assert result.verdict == "REJECT"


def test_d8_warning_without_override_raises_override_missing_record_finding() -> None:
    result = validate_d8_closure(
        _closeable_report(
            d8=_d8("WARNING", override=False, reviewed=True),
            root_cause_validation=_validation("WARNING"),
        )
    )
    codes = _codes(result)
    assert "D8_WARNING_OVERRIDE_MISSING" in codes
    assert "D8_ROOT_CAUSE_REJECTED" not in codes
    override = next(f for f in result.findings if f.code == "D8_WARNING_OVERRIDE_MISSING")
    assert override.severity == "error"
    assert result.verdict == "REJECT"


def test_d8_warning_with_override_passes_through_clean() -> None:
    """WARNING verdict + recorded override + reviewed docs -> no record finding, ACCEPT.

    Exercises the elif-False path (neither D8_ROOT_CAUSE_REJECTED nor D8_WARNING_OVERRIDE_MISSING).
    """
    result = validate_d8_closure(
        _closeable_report(
            d8=_d8("WARNING", override=True, reviewed=True),
            root_cause_validation=_validation("WARNING"),
        )
    )
    codes = _codes(result)
    assert "D8_ROOT_CAUSE_REJECTED" not in codes
    assert "D8_WARNING_OVERRIDE_MISSING" not in codes
    assert codes == ["D8_READY"]
    assert (result.verdict, result.closeable) == ("ACCEPT", True)
    assert result.linked_five_why_verdict == "WARNING"


# --------------------------------------------------------------------------------------
# validate_d8_closure — D8_REVIEW_PROVENANCE_INCOMPLETE warning arm (#212 round 2)
#
# documentation_reviewed=True but the review is unattributable (no reviewer and/or no date).
# Advisory only: NOT a closure deficiency, so closeable stays True while the verdict is WARNING.
# This is the genuinely-reachable WARNING branch of the verdict derivation.
# --------------------------------------------------------------------------------------


def test_d8_review_provenance_incomplete_missing_reviewer_is_warning_and_closeable() -> None:
    """reviewer name missing (date present) -> WARNING + finding, still closeable."""
    result = validate_d8_closure(_closeable_report(d8=_d8_unattributed(by=None, date=DAY)))
    codes = _codes(result)
    assert "D8_REVIEW_PROVENANCE_INCOMPLETE" in codes
    assert "D8_DOCUMENTATION_NOT_REVIEWED" not in codes
    assert "D8_READY" not in codes
    finding = next(f for f in result.findings if f.code == "D8_REVIEW_PROVENANCE_INCOMPLETE")
    assert finding.severity == "warning"
    assert (result.verdict, result.valid) == ("WARNING", True)
    assert result.closeable is True
    assert result.documentation_reviewed is True
    assert result.d8_recorded is True


def test_d8_review_provenance_incomplete_missing_date_is_warning_and_closeable() -> None:
    """review date missing (reviewer present) -> WARNING + finding, still closeable.

    Second leg of the `or`: proves the date check is load-bearing on its own, not only the
    reviewer check.
    """
    result = validate_d8_closure(_closeable_report(d8=_d8_unattributed(by="Reviewer", date=None)))
    codes = _codes(result)
    assert "D8_REVIEW_PROVENANCE_INCOMPLETE" in codes
    assert (result.verdict, result.valid) == ("WARNING", True)
    assert result.closeable is True


def test_d8_review_provenance_incomplete_both_missing_is_warning_and_closeable() -> None:
    """both reviewer and date missing -> single WARNING finding, still closeable."""
    result = validate_d8_closure(_closeable_report(d8=_d8_unattributed(by=None, date=None)))
    codes = _codes(result)
    assert codes == ["D8_REVIEW_PROVENANCE_INCOMPLETE"]
    assert (result.verdict, result.valid) == ("WARNING", True)
    assert result.closeable is True


def test_d8_review_provenance_complete_does_not_raise_the_warning() -> None:
    """both reviewer and date present -> no provenance finding, clean ACCEPT.

    Negative control for the elif condition: with full provenance, neither leg of the `or`
    is True, so the warning must NOT fire and the clean pass yields D8_READY / ACCEPT.
    """
    result = validate_d8_closure(_closeable_report(d8=_d8_unattributed(by="Reviewer", date=DAY)))
    codes = _codes(result)
    assert "D8_REVIEW_PROVENANCE_INCOMPLETE" not in codes
    assert codes == ["D8_READY"]
    assert (result.verdict, result.valid) == ("ACCEPT", True)


def test_d8_documentation_not_reviewed_short_circuits_the_provenance_elif() -> None:
    """documentation_reviewed=False -> the elif is never evaluated even when provenance is absent.

    Proves the provenance warning is guarded behind the `if not documentation_reviewed` error
    arm: with docs unreviewed AND provenance missing, only the ERROR fires (REJECT), never the
    WARNING. Pins the choice between the two rules, not just the boundary.
    """
    result = validate_d8_closure(_closeable_report(d8=_d8("ACCEPT", reviewed=False)))
    codes = _codes(result)
    assert "D8_DOCUMENTATION_NOT_REVIEWED" in codes
    assert "D8_REVIEW_PROVENANCE_INCOMPLETE" not in codes
    assert (result.verdict, result.valid) == ("REJECT", False)


def test_validate_8d_folds_review_provenance_warning_into_overall_verdict() -> None:
    """The provenance WARNING propagates: closeable report, gate clean, overall verdict WARNING.

    gate_reasons is empty (provenance is not a closure deficiency), no discipline is REJECT,
    and d8 is WARNING -> validate_8d's WARNING arm fires with closeable=True.
    """
    result = validate_8d(_closeable_report(d8=_d8_unattributed(by=None, date=None)))
    assert result.d8.verdict == "WARNING"
    assert "D8_REVIEW_PROVENANCE_INCOMPLETE" in [f.code for f in result.d8.findings]
    assert result.gate_reasons == ()
    assert result.closeable is True
    assert (result.verdict, result.valid) == ("WARNING", True)


# --------------------------------------------------------------------------------------
# Each closure-deficiency code -> D8Finding + mapped GateCode  (spec §5 case 5)
# --------------------------------------------------------------------------------------

# (label, overrides, deficiency_code_on_d8_findings, gate_code, gate_rule_id)
_DEFICIENCY_CASES: tuple[tuple[str, dict[str, object], str, str, str], ...] = (
    ("D8_MISSING", {"d8": None}, "D8_MISSING", "ROOT_CAUSE_EVIDENCE_MISSING", "RULE-8D-GATE-CLOSURE"),
    (
        "ROOT_CAUSE_VALIDATION_MISSING",
        {"root_cause_validation": None},
        "ROOT_CAUSE_VALIDATION_MISSING",
        "ROOT_CAUSE_EVIDENCE_MISSING",
        "RULE-8D-GATE-CLOSURE",
    ),
    (
        "ROOT_CAUSE_VERDICT_MISMATCH",
        {"d8": _d8("WARNING", override=True, reviewed=True), "root_cause_validation": _validation("ACCEPT")},
        "ROOT_CAUSE_VERDICT_MISMATCH",
        "ROOT_CAUSE_EVIDENCE_MISSING",
        "RULE-8D-GATE-CLOSURE",
    ),
    (
        "ROOT_CAUSE_REJECTED",
        {"d8": _d8("REJECT", reviewed=True), "root_cause_validation": _validation("REJECT")},
        "ROOT_CAUSE_REJECTED",
        "ROOT_CAUSE_REJECTED",
        "RULE-8D-GATE-CLOSURE",
    ),
    (
        "WARNING_OVERRIDE_MISSING",
        {"d8": _d8("WARNING", override=False, reviewed=True), "root_cause_validation": _validation("WARNING")},
        "WARNING_OVERRIDE_MISSING",
        "ROOT_CAUSE_EVIDENCE_MISSING",
        "RULE-8D-GATE-CLOSURE",
    ),
    (
        "CONTAINMENT_NOT_VERIFIED",
        {"d3": _d3(False)},
        "CONTAINMENT_NOT_VERIFIED",
        "CONTAINMENT_NOT_VERIFIED",
        "RULE-8D-GATE-CONTAINMENT",
    ),
    (
        "PCA_NOT_VERIFIED",
        {"d6": _d6(False)},
        "PCA_NOT_VERIFIED",
        "PCA_NOT_VERIFIED",
        "PDD-8D-010",
    ),
    (
        "PREVENTION_UPDATE_MISSING",
        {"d7": _d7(artifact="OTHER")},
        "PREVENTION_UPDATE_MISSING",
        "PREVENTION_UPDATE_MISSING",
        "RULE-8D-GATE-PREVENTION",
    ),
    (
        "PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE",
        {"d7": _d7(artifact="FMEA", target=None)},
        "PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE",
        "PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE",
        "PDD-8D-013",
    ),
)


@pytest.mark.parametrize(
    "label,overrides,deficiency_code,gate_code,gate_rule_id",
    _DEFICIENCY_CASES,
    ids=[case[0] for case in _DEFICIENCY_CASES],
)
def test_each_closure_deficiency_surfaces_on_findings_and_gate_reasons(
    label: str,
    overrides: dict[str, object],
    deficiency_code: str,
    gate_code: str,
    gate_rule_id: str,
) -> None:
    report = _closeable_report(**overrides)

    d8_result = validate_d8_closure(report)
    assert deficiency_code in _codes(d8_result)
    assert d8_result.closeable is False

    overall = validate_8d(report)
    matching = [r for r in overall.gate_reasons if r.code == gate_code]
    assert matching, f"{gate_code} missing from {[r.code for r in overall.gate_reasons]}"
    assert matching[0].rule_id == gate_rule_id
    assert overall.verdict == "REJECT"
    assert overall.closeable is False


@pytest.mark.parametrize(
    "label,overrides,deficiency_code,gate_code,gate_rule_id",
    _DEFICIENCY_CASES,
    ids=[case[0] for case in _DEFICIENCY_CASES],
)
def test_negative_control_each_deficiency_absent_on_complete_report(
    label: str,
    overrides: dict[str, object],
    deficiency_code: str,
    gate_code: str,
    gate_rule_id: str,
) -> None:
    """Negative control: the fully complete report shows none of these codes and is closeable."""
    report = _closeable_report()
    d8_result = validate_d8_closure(report)
    assert deficiency_code not in _codes(d8_result)
    overall = validate_8d(report)
    assert gate_code not in _gate_codes(overall)
    assert overall.closeable is True


# --------------------------------------------------------------------------------------
# Acceptance criterion 1: block closure on rca-rejected D4 (via root_cause_validation)
# --------------------------------------------------------------------------------------


def test_rca_rejected_d4_blocks_closure_through_root_cause_validation() -> None:
    report = _closeable_report(
        d8=_d8("REJECT", reviewed=True), root_cause_validation=_validation("REJECT")
    )
    result = validate_8d(report)
    rejected = [r for r in result.gate_reasons if r.code == "ROOT_CAUSE_REJECTED"]
    assert rejected, _gate_codes(result)
    assert rejected[0].rule_id == "RULE-8D-GATE-CLOSURE"
    assert result.verdict == "REJECT"
    assert result.closeable is False


def test_rca_rejected_d4_negative_control_valid_evidence_closes() -> None:
    report = _clean_report()
    result = validate_8d(report)
    assert "ROOT_CAUSE_REJECTED" not in _gate_codes(result)
    assert result.closeable is True
    assert result.verdict == "ACCEPT"


def test_d4_is_excluded_from_the_sweep_but_rejection_still_caught() -> None:
    """A rich D4 present must not make validate_8d try to call validate_d4_root_cause (crash).

    Rejection is still caught end-to-end purely through root_cause_validation, and there is no
    d4-specific advisory result anywhere on the dataclass.
    """
    report = _closeable_report(
        d4=_d4(), d8=_d8("REJECT", reviewed=True), root_cause_validation=_validation("REJECT")
    )
    result = validate_8d(report)  # must not raise
    assert "ROOT_CAUSE_REJECTED" in _gate_codes(result)


def test_eight_d_validation_result_has_no_d4_field() -> None:
    names = {f.name for f in dataclasses.fields(EightDValidationResult)}
    assert "d4" not in names
    assert {"d0", "d1", "d2", "d3", "d5", "d6", "d7", "d8"} <= names


# --------------------------------------------------------------------------------------
# Acceptance criterion 1: missing D3 containment
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("d3", [None, _d3(False), _d3(None), _d3(True, False)])
def test_missing_or_unverified_d3_blocks_closure(d3: D3Discipline | None) -> None:
    report = _closeable_report(d3=d3)
    result = validate_8d(report)
    containment = [r for r in result.gate_reasons if r.code == "CONTAINMENT_NOT_VERIFIED"]
    assert containment, _gate_codes(result)
    assert containment[0].rule_id == "RULE-8D-GATE-CONTAINMENT"
    assert result.verdict == "REJECT"
    if d3 is not None:
        # The advisory D3 engine independently reflects REJECT for a present-but-unverified D3.
        assert result.d3 is not None
        assert result.d3.verdict == "REJECT"


def test_missing_d3_negative_control_verified_d3_absent() -> None:
    result = validate_8d(_closeable_report())
    assert "CONTAINMENT_NOT_VERIFIED" not in _gate_codes(result)


# --------------------------------------------------------------------------------------
# Acceptance criterion 1: missing D7 update
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "d7,expected",
    [
        (None, "PREVENTION_UPDATE_MISSING"),
        (_d7(artifact="OTHER"), "PREVENTION_UPDATE_MISSING"),
        (_d7(artifact=None), "PREVENTION_UPDATE_MISSING"),
        (_d7(artifact="FMEA", target=None), "PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE"),
        (_d7(artifact="FMEA", target="ESCAPE_POINT"), "PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE"),
    ],
)
def test_missing_or_unlinked_d7_blocks_closure(d7: D7Discipline | None, expected: str) -> None:
    report = _closeable_report(d7=d7)
    result = validate_8d(report)
    codes = _gate_codes(result)
    assert expected in codes
    # The two prevention codes are never reported together.
    other = (
        "PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE"
        if expected == "PREVENTION_UPDATE_MISSING"
        else "PREVENTION_UPDATE_MISSING"
    )
    assert other not in codes
    assert result.verdict == "REJECT"


def test_missing_d7_negative_control_qualifying_root_cause_update_absent() -> None:
    result = validate_8d(_closeable_report())
    assert "PREVENTION_UPDATE_MISSING" not in _gate_codes(result)
    assert "PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE" not in _gate_codes(result)


# --------------------------------------------------------------------------------------
# The LINKED_NCR_INVALID gate — the load-bearing "all gates" completeness case (spec §6)
# --------------------------------------------------------------------------------------


def _invalid_ncr() -> LinkedNCRValidation:
    return LinkedNCRValidation(
        is_valid=False, findings=["part_lot_id: must not be blank or whitespace-only"]
    )


def test_linked_ncr_invalid_appears_in_gate_reasons_even_though_closure_evidence_is_complete() -> None:
    """Verified D3 containment + invalid linked NCR: LINKED_NCR_INVALID must still gate.

    _closure_evidence_deficiencies reports nothing for this D3 (containment IS verified), so this
    gate reaches validate_8d only through the explicit _linked_ncr_reason call. Deleting that call
    makes this test fail (proven by mutation).
    """
    report = _closeable_report(d3=_d3_with_ncr(_invalid_ncr()))
    result = validate_8d(report)
    ncr = [r for r in result.gate_reasons if r.code == "LINKED_NCR_INVALID"]
    assert ncr, _gate_codes(result)
    assert ncr[0].rule_id == "PDD-8D-008"
    # The D8 closure engine, which reads only _closure_evidence_deficiencies, sees it as closeable.
    assert validate_d8_closure(report).closeable is True
    # But the whole-report orchestrator does not close.
    assert result.closeable is False
    assert result.verdict == "REJECT"


@pytest.mark.parametrize("validation", [None, LinkedNCRValidation(is_valid=True)])
def test_linked_ncr_valid_or_absent_negative_control(validation: LinkedNCRValidation | None) -> None:
    report = _closeable_report(d3=_d3_with_ncr(validation))
    result = validate_8d(report)
    assert "LINKED_NCR_INVALID" not in _gate_codes(result)
    assert result.closeable is True


# --------------------------------------------------------------------------------------
# Acceptance criterion 2 + orchestrator/gate agreement (spec §5 case 4)
# --------------------------------------------------------------------------------------


def test_fully_valid_report_closes_and_agrees_with_the_transition_gate() -> None:
    report = _clean_report("D8")
    result = validate_8d(report)
    assert result.verdict == "ACCEPT"
    assert result.valid is True
    assert result.closeable is True
    assert result.gate_reasons == ()
    assert result.state == "D8"
    assert result.d8.verdict == "ACCEPT"

    # The independent gate must reach the same conclusion on the same evidence.
    transition = transition_eight_d(report, "CLOSED")
    assert transition.verdict == "ADVANCED"
    assert transition.reasons == ()


# --------------------------------------------------------------------------------------
# Verdict-combination precedence (spec §5 case 9): one test per if/elif/else branch
# --------------------------------------------------------------------------------------


def test_verdict_reject_from_gate_reasons_even_when_disciplines_accept() -> None:
    """gate_reasons non-empty + every computed discipline ACCEPT -> REJECT.

    Uses the linked-NCR gate: it is the one gate that does NOT create a d8 error finding, so the
    d8 advisory verdict stays ACCEPT while gate_reasons is non-empty. This isolates the first
    if-branch's `gate_reasons or ...` left operand.
    """
    report = _clean_report(d3=_d3_with_ncr(_invalid_ncr()))
    result = validate_8d(report)
    assert result.gate_reasons != ()
    # d8 (which reads only the closure-evidence boundary) still says ACCEPT: the LINKED_NCR gate
    # is what drives the whole-report REJECT via the `gate_reasons` operand of the first branch.
    assert result.d8.verdict == "ACCEPT"
    assert result.verdict == "REJECT"
    assert result.valid is False


def test_verdict_reject_from_a_discipline_when_gate_reasons_empty() -> None:
    """gate_reasons empty (closeable) + one discipline REJECT -> REJECT.

    The documentation-not-reviewed d8 is closeable but REJECT; nothing else blocks the gate.
    Isolates the first if-branch's `any(r.verdict == "REJECT")` right operand.
    """
    report = _clean_report(d8=_d8("ACCEPT", reviewed=False))
    result = validate_8d(report)
    assert result.gate_reasons == ()
    assert result.closeable is True
    assert result.d8.verdict == "REJECT"
    assert result.verdict == "REJECT"
    assert result.valid is False


def test_verdict_warning_when_gate_empty_no_reject_and_one_warning() -> None:
    """gate_reasons empty + no REJECT + a WARNING discipline -> WARNING.

    A clean report but with D3 carrying no linked-NCR outcome: D3's advisory verdict is WARNING
    (LINKED_NCR_NOT_PROVIDED) while containment is still verified, so the report stays closeable.
    """
    report = _clean_report(d3=_d3(True))
    result = validate_8d(report)
    assert result.gate_reasons == ()
    assert result.d3 is not None and result.d3.verdict == "WARNING"
    assert result.d8.verdict == "ACCEPT"
    assert result.verdict == "WARNING"
    assert result.valid is True


def test_verdict_accept_when_everything_clean() -> None:
    result = validate_8d(_clean_report())
    assert result.verdict == "ACCEPT"
    assert result.valid is True


# --------------------------------------------------------------------------------------
# report.d8 is None type contract, CANCELLED / CLOSED lifecycle, to_dict both branches
# --------------------------------------------------------------------------------------


def test_validate_8d_d8_field_is_never_none_even_when_report_d8_is_none() -> None:
    report = _report("D2", root_cause_validation=_validation("ACCEPT"))
    result = validate_8d(report)
    assert result.d8 is not None
    assert isinstance(result.d8, D8ValidationResult)
    assert result.d8.d8_recorded is False
    assert "ROOT_CAUSE_EVIDENCE_MISSING" in _gate_codes(result)


def test_bare_report_collapses_missing_evidence_onto_the_public_gate_vocabulary() -> None:
    """A bare D2 report yields the collapsed many-to-one GateCode mapping (spec §1.1 note)."""
    report = _report("D2")
    result = validate_8d(report)
    codes = _gate_codes(result)
    # D8_MISSING + ROOT_CAUSE_VALIDATION_MISSING both collapse -> two ROOT_CAUSE_EVIDENCE_MISSING.
    assert codes.count("ROOT_CAUSE_EVIDENCE_MISSING") == 2
    assert "CONTAINMENT_NOT_VERIFIED" in codes
    assert "PCA_NOT_VERIFIED" in codes
    assert "PREVENTION_UPDATE_MISSING" in codes
    # Uncollapsed per-deficiency codes remain on the D8 advisory result.
    d8_codes = _codes(result.d8)
    assert "D8_MISSING" in d8_codes
    assert "ROOT_CAUSE_VALIDATION_MISSING" in d8_codes


def test_cancelled_report_is_not_special_cased() -> None:
    """CANCELLED behaves exactly like an OPEN report at the same discipline with the same slots."""
    updates = _closeable_updates()
    cancelled = EightDReport(
        report_id="8D-212",
        initiated_date=DAY,
        status="CANCELLED",
        current_discipline="D8",
        **updates,
    )
    open_report = _report("D8", **_closeable_updates())
    cancelled_result = validate_8d(cancelled)
    open_result = validate_8d(open_report)
    assert cancelled_result.state == "D8"
    assert cancelled_result.verdict == open_result.verdict
    assert cancelled_result.closeable == open_result.closeable
    assert _gate_codes(cancelled_result) == _gate_codes(open_result)


def test_directly_closed_report_runs_clean_with_closed_state() -> None:
    report = _report("CLOSED", **_clean_updates())
    result = validate_8d(report)
    assert result.state == "CLOSED"
    assert result.closeable is True
    assert result.gate_reasons == ()
    assert result.verdict == "ACCEPT"


def test_to_dict_round_trips_with_every_discipline_present() -> None:
    """else-branch of all seven optional-discipline ternaries in EightDValidationResult.to_dict."""
    report = _report(
        "D8",
        d0=D0Discipline(era_required=False),
        d1=D1Discipline(
            champion="C. Hampion",
            team_leader="L. Eader",
            members=[TeamMember(name="A. Smith", role="Process Engineer")],
        ),
        d2=D2Discipline(
            what_is_wrong="Bore diameter undersized",
            with_what="Housing P/N 44821",
            quantification="14 of 500 parts",
        ),
        d3=_d3(True),
        d5=_full_d5(),
        d6=_full_d6(),
        d7=_d7(),
        d8=_d8("ACCEPT", reviewed=True),
        root_cause_validation=_validation("ACCEPT"),
    )
    result = validate_8d(report)
    payload = result.to_dict()
    for key in ("d0", "d1", "d2", "d3", "d5", "d6", "d7"):
        assert payload[key] is not None
    assert payload["d8"] is not None
    assert payload["report"]["report_id"] == "8D-212"
    json.dumps(payload)


def test_to_dict_round_trips_with_every_optional_discipline_absent() -> None:
    """None-branch of all seven optional-discipline ternaries."""
    report = _report("D2")
    result = validate_8d(report)
    payload = result.to_dict()
    for key in ("d0", "d1", "d2", "d3", "d5", "d6", "d7"):
        assert payload[key] is None
    assert payload["d8"] is not None
    assert payload["gate_reasons"] == [r.to_dict() for r in result.gate_reasons]
    json.dumps(payload)


# --------------------------------------------------------------------------------------
# Re-export contract (mirrors every test_d<n>_engine_symbols_are_re_exported_from_quality_core_rca)
# --------------------------------------------------------------------------------------


def test_d8_engine_symbols_are_re_exported_from_quality_core_rca() -> None:
    import quality_core.rca as rca

    assert rca.D8Finding is D8Finding
    assert rca.D8ValidationResult is D8ValidationResult
    assert rca.validate_d8_closure is validate_d8_closure
    assert rca.EightDValidationResult is EightDValidationResult
    assert rca.validate_8d is validate_8d
    for name in (
        "D8Finding",
        "D8ValidationResult",
        "EightDValidationResult",
        "validate_8d",
        "validate_d8_closure",
    ):
        assert name in rca.__all__

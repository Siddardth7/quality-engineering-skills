"""
Tests for quality_core.rca.eight_d_schema — the 8D report envelope, its nine discipline
models, the JSON trust boundary, and the four CSV sub-table schemas.

Covers:
- Shared helpers (blank rejection, optional-string normalization, lenient date parsing)
- D0..D8 discipline models: happy paths, blank rejection, and every validator rejection branch
- Finding 1: D8 closure policy against the linked 5-Why verdict (REJECT blocks, ACCEPT closes,
  WARNING closes only with a recorded WarningOverride)
- Finding 2: EffectivenessVerification-backed containment/corrective-action verification
- EightDReport envelope: date ordering, the `team` alias, empty-report construction
- validate_eight_d / load_eight_d_json / load_eight_d_json_from_path trust boundary
- The four CSV sub-tables and their validate_* batteries
- rca package re-export smoke test
"""

from __future__ import annotations

import dataclasses
import datetime
import io
import json
from pathlib import Path
from typing import Any, get_args, get_type_hints

import pandas as pd
import pydantic
import pytest
import quality_core.rca as rca
from quality_core.rca import (
    CONTAINMENT_ACTION_SCHEMA,
    CORRECTIVE_ACTION_CANDIDATE_SCHEMA,
    DOCUMENTATION_UPDATE_SCHEMA,
    TEAM_MEMBER_SCHEMA,
    CandidateCauseTest,
    ContainmentAction,
    ContainmentActionList,
    CorrectiveActionCandidate,
    CorrectiveActionCandidateList,
    D0Discipline,
    D1Discipline,
    D2Discipline,
    D3Discipline,
    D4Discipline,
    D5Discipline,
    D6Discipline,
    D7Discipline,
    D8Discipline,
    DocumentationUpdate,
    DocumentationUpdateList,
    EffectivenessVerification,
    EightDReport,
    EscapePointFinding,
    ImplementedAction,
    IngestError,
    RootCauseFinding,
    TeamMember,
    TeamMemberList,
    WarningOverride,
    load_containment_actions_csv,
    load_corrective_action_candidates_csv,
    load_documentation_updates_csv,
    load_eight_d_json,
    load_eight_d_json_from_path,
    load_team_members_csv,
    validate_containment_actions,
    validate_corrective_action_candidates,
    validate_documentation_updates,
    validate_eight_d,
    validate_team_members,
)
from quality_core.rca import eight_d_schema as m
from quality_core.rca.five_why import FiveWhyValidationResult, validate_five_why_chain

DAY_1 = datetime.date(2026, 1, 1)
DAY_2 = datetime.date(2026, 1, 2)
DAY_3 = datetime.date(2026, 1, 3)

# ==============================================================================
# Helper functions / fixtures
# ==============================================================================


def _csv_buf(rows: list[dict[str, Any]], name: str = "upload.csv") -> io.BytesIO:
    buf = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode("utf-8"))
    buf.name = name
    return buf


def _verification(*, effective: bool = True, on: datetime.date = DAY_2) -> EffectivenessVerification:
    return EffectivenessVerification(
        verified_by="Q. Engineer",
        verified_date=on,
        evidence="200 consecutive parts inspected, zero escapes.",
        is_effective=effective,
    )


def _containment(*, effective: bool | None = True) -> ContainmentAction:
    return ContainmentAction(
        description="100% sort at the shipping dock.",
        implemented_date=DAY_1,
        verification=None if effective is None else _verification(effective=effective),
    )


def _d5_candidates() -> list[CorrectiveActionCandidate]:
    return [
        CorrectiveActionCandidate(
            action_id="PCA-1",
            target="ROOT_CAUSE",
            description="Replace the worn forming die.",
            selection_criteria="Lowest residual risk at acceptable cost.",
        ),
        CorrectiveActionCandidate(
            action_id="PCA-2",
            target="ESCAPE_POINT",
            description="Add an in-line vision check at station 40.",
            selection_criteria="Detects the defect before the escape point.",
        ),
    ]


def _full_report() -> EightDReport:
    validation = validate_five_why_chain(
        [
            {"step_number": 1, "why": "Why did bearing seize?", "because": "Lubricant dried up."},
            {"step_number": 2, "why": "Why did it dry up?", "because": "Maintenance routine was omitted."},
            {"step_number": 3, "why": "Why was routine omitted?", "because": "Training procedure lacked a checklist."},
        ],
        problem_statement="Bearing seized",
    )
    return EightDReport(
        report_id="8D-2026-001",
        initiated_date=DAY_1,
        target_completion_date=DAY_3,
        closed_date=DAY_3,
        status="CLOSED",
        current_discipline="D8",
        root_cause_validation=validation,
        d0=D0Discipline(era_required=True, era_description="Quarantine all suspect stock."),
        d1=D1Discipline(
            champion="P. Champion",
            team_leader="T. Leader",
            members=[TeamMember(name="A. Member", role="Process Engineer")],
        ),
        d2=D2Discipline(
            what_is_wrong="Bore diameter is undersized",
            with_what="Housing P/N 12345",
            quantification="14 of 500 parts, 2.8%",
            method_used="IS_IS_NOT",
        ),
        d3=D3Discipline(actions=[_containment()]),
        d4=D4Discipline(
            candidate_causes_tested=[
                CandidateCauseTest(
                    description="Worn forming die",
                    test_data="Die wear measured 0.12 mm over tolerance",
                    result="CONFIRMED",
                )
            ],
            root_cause=RootCauseFinding(
                statement="Die maintenance interval was never added to the PM schedule.",
                verification_evidence="PM schedule revision history shows no entry.",
                five_why_leg_type="occurrence",
                five_why_verdict="ACCEPT",
            ),
            escape_point=EscapePointFinding(
                statement="Final inspection samples only 1 in 50 parts.",
                verification_evidence="Control plan sampling frequency record.",
                five_why_leg_type="escape",
                five_why_verdict="ACCEPT",
            ),
        ),
        d5=D5Discipline(candidates=_d5_candidates()),
        d6=D6Discipline(
            implemented_actions=[
                ImplementedAction(
                    corrective_action_id="PCA-1",
                    implemented_date=DAY_2,
                    verification=_verification(on=DAY_3),
                    monitoring_notes="30-day run at zero defects.",
                )
            ],
            interim_containment_removed_date=DAY_3,
        ),
        d7=D7Discipline(
            systemic_changes_description="PM schedule now owns every forming die.",
            documentation_updates=[
                DocumentationUpdate(
                    artifact_type="CONTROL_PLAN",
                    artifact_reference="CP-12345 rev C",
                    updated_date=DAY_3,
                    updated_by="D. Documenter",
                )
            ],
        ),
        d8=D8Discipline(
            team_recognition_notes="Team recognized at the plant quality review.",
            documentation_reviewed=True,
            documentation_review_date=DAY_3,
            documentation_reviewed_by="R. Reviewer",
            linked_five_why_verdict="ACCEPT",
            closure_approved=True,
            closure_approved_by="P. Champion",
            closure_approved_date=DAY_3,
        ),
    )


# ==============================================================================
# 0. Module exports
# ==============================================================================

EIGHT_D_EXPORTS = (
    "CONTAINMENT_ACTION_SCHEMA",
    "CORRECTIVE_ACTION_CANDIDATE_SCHEMA",
    "CandidateCauseTest",
    "ContainmentAction",
    "ContainmentActionList",
    "CorrectiveActionCandidate",
    "CorrectiveActionCandidateList",
    "D0Discipline",
    "D1Discipline",
    "D2Discipline",
    "D3Discipline",
    "D4Discipline",
    "D5Discipline",
    "D6Discipline",
    "D7Discipline",
    "D8Discipline",
    "DOCUMENTATION_UPDATE_SCHEMA",
    "DocumentationUpdate",
    "DocumentationUpdateList",
    "EffectivenessVerification",
    "EightDDiscipline",
    "EightDReport",
    "EightDStatus",
    "EscapePointFinding",
    "FiveWhyLegType",
    "FiveWhyVerdict",
    "ImplementedAction",
    "LinkedNCRValidation",
    "RootCauseFinding",
    "TEAM_MEMBER_SCHEMA",
    "TeamMember",
    "TeamMemberList",
    "WarningOverride",
    "load_containment_actions_csv",
    "load_corrective_action_candidates_csv",
    "load_documentation_updates_csv",
    "load_eight_d_json",
    "load_eight_d_json_from_path",
    "load_team_members_csv",
    "validate_containment_actions",
    "validate_corrective_action_candidates",
    "validate_documentation_updates",
    "validate_eight_d",
    "validate_team_members",
)


def test_every_eight_d_name_is_reexported_from_rca_package() -> None:
    missing_from_all = [n for n in EIGHT_D_EXPORTS if n not in rca.__all__]
    missing_attrs = [n for n in EIGHT_D_EXPORTS if not hasattr(rca, n)]
    assert not missing_from_all, missing_from_all
    assert not missing_attrs, missing_attrs


def test_eight_d_schema_module_all_matches_package_exports() -> None:
    assert set(m.__all__) == set(EIGHT_D_EXPORTS)


# ==============================================================================
# 1. Shared helpers
# ==============================================================================


def test_reject_blank_strips_and_rejects_and_passes_non_strings() -> None:
    assert m._reject_blank("  padded  ") == "padded"
    assert m._reject_blank(7) == 7
    with pytest.raises(ValueError, match="must not be blank"):
        m._reject_blank("   ")


def test_blank_to_none_normalizes_optional_strings() -> None:
    assert m._blank_to_none(None) is None
    assert m._blank_to_none("   ") is None
    assert m._blank_to_none("  role  ") == "role"
    assert m._blank_to_none(9) == 9


def test_na_to_none_normalizes_missing_and_tolerates_array_likes() -> None:
    assert m._na_to_none(float("nan")) is None
    assert m._na_to_none("present") == "present"
    # A bare pd.isna on a multi-element list raises; the guarded helper keeps the value.
    assert m._na_to_none([1, 2, 3]) == [1, 2, 3]


def test_clean_record_applies_na_to_none_across_a_mapping() -> None:
    assert m._clean_record({"a": float("nan"), "b": 1}) == {"a": None, "b": 1}


def test_parse_date_lenient_covers_every_branch() -> None:
    assert m._parse_date_lenient(None) is None
    assert m._parse_date_lenient("  ") is None
    assert m._parse_date_lenient(DAY_1) == DAY_1
    assert m._parse_date_lenient("2026-01-05") == datetime.date(2026, 1, 5)
    assert m._parse_date_lenient("not-a-date-at-all") is None


def test_effectiveness_verification_rejects_blank_fields() -> None:
    with pytest.raises(pydantic.ValidationError):
        EffectivenessVerification(
            verified_by="   ", verified_date=DAY_1, evidence="e", is_effective=True
        )
    with pytest.raises(pydantic.ValidationError):
        EffectivenessVerification(
            verified_by="Q", verified_date=DAY_1, evidence="  ", is_effective=True
        )


def test_effectiveness_verification_passes_non_string_through_to_pydantic() -> None:
    with pytest.raises(pydantic.ValidationError):
        EffectivenessVerification(
            verified_by=123,  # type: ignore[arg-type]
            verified_date=DAY_1,
            evidence="e",
            is_effective=True,
        )


# ==============================================================================
# 2. D0 — Emergency Response Action readiness
# ==============================================================================


def test_d0_happy_path_with_era_required() -> None:
    d0 = D0Discipline(
        era_required=True,
        era_description="  Quarantine suspect stock.  ",
        era_implemented_date="2026-01-02",  # type: ignore[arg-type]
        era_verification=_verification(),
    )
    assert d0.era_description == "Quarantine suspect stock."
    assert d0.era_implemented_date == DAY_2
    assert d0.era_verification is not None


def test_d0_no_era_required_needs_no_description() -> None:
    d0 = D0Discipline(era_required=False)
    assert d0.era_description is None
    assert d0.era_implemented_date is None


def test_d0_blank_description_normalizes_to_none_and_then_raises_when_required() -> None:
    with pytest.raises(pydantic.ValidationError, match="era_description is required"):
        D0Discipline(era_required=True, era_description="   ")


def test_d0_missing_description_when_required_raises() -> None:
    with pytest.raises(pydantic.ValidationError, match="era_description is required"):
        D0Discipline(era_required=True)


def test_d0_unparseable_date_resolves_to_none() -> None:
    d0 = D0Discipline(era_required=False, era_implemented_date="wobble")  # type: ignore[arg-type]
    assert d0.era_implemented_date is None


def test_d0_non_string_description_passes_through_to_pydantic() -> None:
    with pytest.raises(pydantic.ValidationError):
        D0Discipline(era_required=False, era_description=5)  # type: ignore[arg-type]


# ==============================================================================
# 3. D1 — Team formation
# ==============================================================================


def test_team_member_strips_and_normalizes() -> None:
    member = TeamMember(name="  A. Member  ", role="   ")
    assert member.name == "A. Member"
    assert member.role is None


def test_team_member_rejects_blank_name() -> None:
    with pytest.raises(pydantic.ValidationError):
        TeamMember(name="   ")


def test_team_member_passes_non_strings_through_to_pydantic() -> None:
    with pytest.raises(pydantic.ValidationError):
        TeamMember(name=3)  # type: ignore[arg-type]
    with pytest.raises(pydantic.ValidationError):
        TeamMember(name="ok", role=3)  # type: ignore[arg-type]


def test_d1_happy_path_and_default_empty_members() -> None:
    d1 = D1Discipline(champion="  P. Champion ", team_leader="T. Leader")
    assert d1.champion == "P. Champion"
    assert d1.members == []


@pytest.mark.parametrize("field", ["champion", "team_leader"])
def test_d1_rejects_blank_required_fields(field: str) -> None:
    kwargs: dict[str, Any] = {"champion": "P", "team_leader": "T"}
    kwargs[field] = "   "
    with pytest.raises(pydantic.ValidationError):
        D1Discipline(**kwargs)


# ==============================================================================
# 4. D2 — Problem description
# ==============================================================================


def test_d2_happy_path() -> None:
    d2 = D2Discipline(
        what_is_wrong="  Bore undersized ",
        with_what="Housing P/N 12345",
        quantification="14 of 500",
    )
    assert d2.what_is_wrong == "Bore undersized"
    assert d2.method_used is None
    assert d2.w2h_who is None
    assert d2.w2h_how_many is None


W2H_FIELDS = [
    "w2h_who",
    "w2h_what",
    "w2h_when",
    "w2h_where",
    "w2h_why",
    "w2h_how",
    "w2h_how_many",
]


@pytest.mark.parametrize("field", W2H_FIELDS)
def test_d2_w2h_answers_default_to_none_and_strip(field: str) -> None:
    """Assert each Figure 12 answer field is optional and stripped when supplied."""
    d2 = D2Discipline(
        what_is_wrong="w",
        with_what="x",
        quantification="q",
        **{field: "  an answer  "},
    )
    assert getattr(d2, field) == "an answer"
    assert [f for f in W2H_FIELDS if getattr(d2, f) is None] == [
        f for f in W2H_FIELDS if f != field
    ]


@pytest.mark.parametrize("field", W2H_FIELDS)
@pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "whitespace"])
def test_d2_blank_w2h_answer_normalises_to_none(field: str, blank: str) -> None:
    """Assert a blank Figure 12 answer becomes None rather than raising — completeness is the
    engine's judgment, so an unanswered question must stay representable."""
    d2 = D2Discipline(
        what_is_wrong="w",
        with_what="x",
        quantification="q",
        **{field: blank},
    )
    assert getattr(d2, field) is None


@pytest.mark.parametrize("field", W2H_FIELDS)
def test_d2_rejects_overlong_w2h_answer(field: str) -> None:
    """Assert each Figure 12 answer carries the same 2000-character bound as the text fields."""
    with pytest.raises(pydantic.ValidationError):
        D2Discipline(
            what_is_wrong="w",
            with_what="x",
            quantification="q",
            **{field: "z" * 2001},
        )


@pytest.mark.parametrize("field", ["what_is_wrong", "with_what", "quantification"])
def test_d2_rejects_blank_required_fields(field: str) -> None:
    kwargs: dict[str, Any] = {
        "what_is_wrong": "w",
        "with_what": "x",
        "quantification": "q",
    }
    kwargs[field] = "  "
    with pytest.raises(pydantic.ValidationError):
        D2Discipline(**kwargs)


def test_d2_rejects_unknown_method() -> None:
    with pytest.raises(pydantic.ValidationError):
        D2Discipline(
            what_is_wrong="w",
            with_what="x",
            quantification="q",
            method_used="TAROT",  # type: ignore[arg-type]
        )


# ==============================================================================
# 5. D3 — Interim containment (Finding 2)
# ==============================================================================


def test_containment_action_without_verification_is_not_verified() -> None:
    action = _containment(effective=None)
    assert action.verification is None
    assert action.is_verified is False


def test_containment_action_with_ineffective_verification_is_not_verified() -> None:
    action = _containment(effective=False)
    assert action.verification is not None
    assert action.verification.is_effective is False
    assert action.is_verified is False


def test_containment_action_with_effective_verification_is_verified() -> None:
    assert _containment(effective=True).is_verified is True


def test_containment_action_rejects_blank_description() -> None:
    with pytest.raises(pydantic.ValidationError):
        ContainmentAction(description="   ", implemented_date=DAY_1)


def test_containment_verified_date_before_implemented_date_raises() -> None:
    with pytest.raises(pydantic.ValidationError, match="cannot be before implemented_date"):
        ContainmentAction(
            description="Sort at dock",
            implemented_date=DAY_2,
            verification=_verification(on=DAY_1),
        )


def test_containment_verified_on_the_implementation_date_is_allowed() -> None:
    action = ContainmentAction(
        description="Sort at dock",
        implemented_date=DAY_2,
        verification=_verification(on=DAY_2),
    )
    assert action.is_verified is True


def test_containment_is_verified_cannot_be_faked_by_a_kwarg() -> None:
    """is_verified is a computed property, not a settable field: passing is_verified=True with
    no EffectivenessVerification is silently ignored and the property still reports False. E2's
    D3->D4 gate reads this property, so there must be no bare boolean a caller can set to satisfy
    it."""
    action = ContainmentAction(
        description="Sort at dock",
        implemented_date=DAY_1,
        is_verified=True,  # type: ignore[call-arg]
    )
    assert action.verification is None
    assert action.is_verified is False
    assert D3Discipline(actions=[action]).is_verified is False


def test_d3_requires_at_least_one_action() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one containment action"):
        D3Discipline(actions=[])
    with pytest.raises(pydantic.ValidationError, match="at least one containment action"):
        D3Discipline()


def test_d3_is_verified_only_when_every_action_is_verified() -> None:
    all_good = D3Discipline(actions=[_containment(), _containment()])
    assert all_good.is_verified is True

    mixed = D3Discipline(actions=[_containment(effective=True), _containment(effective=False)])
    assert mixed.is_verified is False

    none_verified = D3Discipline(actions=[_containment(effective=None)])
    assert none_verified.is_verified is False


# ---- Linked-NCR validation outcome and its shared evaluator (#208) -------------------


def test_linked_ncr_validation_defaults_and_invalid_outcome_requires_findings() -> None:
    """A valid outcome needs nothing extra; an invalid one must say why it is invalid."""
    accepted = m.LinkedNCRValidation(is_valid=True)
    assert (accepted.record_count, accepted.findings) == (0, [])
    rejected = m.LinkedNCRValidation(is_valid=False, findings=["part_lot_id: must not be blank"])
    assert rejected.findings == ["part_lot_id: must not be blank"]
    with pytest.raises(pydantic.ValidationError, match="at least one finding message"):
        m.LinkedNCRValidation(is_valid=False)


def test_linked_ncr_validation_rejects_a_negative_record_count() -> None:
    with pytest.raises(pydantic.ValidationError, match="greater than or equal to 0"):
        m.LinkedNCRValidation(is_valid=True, record_count=-1)


def test_d3_linked_ncr_validation_defaults_to_none_and_round_trips() -> None:
    """The recorded outcome is optional, so an in-progress D3 record stays representable."""
    assert D3Discipline(actions=[_containment()]).linked_ncr_validation is None
    discipline = D3Discipline(
        actions=[_containment()],
        linked_ncr_validation=m.LinkedNCRValidation(is_valid=True, record_count=3),
    )
    restored = D3Discipline.model_validate(json.loads(discipline.model_dump_json()))
    assert restored.linked_ncr_validation == discipline.linked_ncr_validation


@pytest.mark.parametrize(
    "validation",
    [None, m.LinkedNCRValidation(is_valid=True, record_count=1)],
    ids=["not-recorded", "recorded-valid"],
)
def test_linked_ncr_deficiency_accepts_absent_and_valid_outcomes(
    validation: m.LinkedNCRValidation | None,
) -> None:
    """Nothing recorded and a recorded pass are both acceptable — neither blocks anything."""
    assert m._linked_ncr_deficiency(validation) is None


def test_linked_ncr_deficiency_reports_a_recorded_rejection_with_its_own_findings() -> None:
    """The one shared evaluator both the D3 engine and the D3->D4 gate read."""
    deficiency = m._linked_ncr_deficiency(
        m.LinkedNCRValidation(is_valid=False, findings=["first problem", "second problem"])
    )
    assert deficiency is not None
    assert deficiency.code == "LINKED_NCR_INVALID"
    assert deficiency.message == (
        "The linked Nonconformance Record evidence is invalid: first problem; second problem."
    )


# ==============================================================================
# 6. D4 — Root cause and escape point
# ==============================================================================


def test_candidate_cause_test_happy_path_and_blank_rejection() -> None:
    tested = CandidateCauseTest(
        description="  Worn die ", test_data="0.12 mm over", result="ELIMINATED"
    )
    assert tested.description == "Worn die"
    with pytest.raises(pydantic.ValidationError):
        CandidateCauseTest(description="  ", test_data="d", result="CONFIRMED")
    with pytest.raises(pydantic.ValidationError):
        CandidateCauseTest(description="d", test_data="  ", result="CONFIRMED")


def test_root_cause_and_escape_point_findings() -> None:
    rc = RootCauseFinding(
        statement="  Missing PM entry ",
        verification_evidence="Revision history",
        five_why_leg_type="occurrence",
        five_why_verdict="WARNING",
    )
    assert rc.statement == "Missing PM entry"
    ep = EscapePointFinding(statement="Sampling gap", verification_evidence="Control plan")
    assert ep.five_why_leg_type is None
    assert ep.five_why_verdict is None


@pytest.mark.parametrize("field", ["statement", "verification_evidence"])
@pytest.mark.parametrize("model", [RootCauseFinding, EscapePointFinding])
def test_d4_findings_reject_blank_fields(model: Any, field: str) -> None:
    kwargs: dict[str, Any] = {"statement": "s", "verification_evidence": "e"}
    kwargs[field] = "  "
    with pytest.raises(pydantic.ValidationError):
        model(**kwargs)


def test_d4_discipline_defaults_to_empty_candidate_list() -> None:
    d4 = D4Discipline(
        root_cause=RootCauseFinding(statement="s", verification_evidence="e"),
        escape_point=EscapePointFinding(statement="s", verification_evidence="e"),
    )
    assert d4.candidate_causes_tested == []


def test_d4_requires_both_root_cause_and_escape_point() -> None:
    with pytest.raises(pydantic.ValidationError):
        D4Discipline(root_cause=RootCauseFinding(statement="s", verification_evidence="e"))


# ==============================================================================
# 7. D5 — Permanent corrective action selection
# ==============================================================================


def test_d5_happy_path_with_both_targets() -> None:
    d5 = D5Discipline(candidates=_d5_candidates())
    assert {c.target for c in d5.candidates} == {"ROOT_CAUSE", "ESCAPE_POINT"}
    assert d5.candidates[0].verified_no_undesirable_effects is False
    assert d5.candidates[0].verification_notes is None


def test_corrective_action_candidate_normalizes_fields() -> None:
    candidate = CorrectiveActionCandidate(
        action_id="  PCA-1 ",
        target="ROOT_CAUSE",
        description="d",
        selection_criteria="c",
        verification_notes="   ",
    )
    assert candidate.action_id == "PCA-1"
    assert candidate.verification_notes is None


@pytest.mark.parametrize("field", ["action_id", "description", "selection_criteria"])
def test_corrective_action_candidate_rejects_blank_fields(field: str) -> None:
    kwargs: dict[str, Any] = {
        "action_id": "PCA-1",
        "target": "ROOT_CAUSE",
        "description": "d",
        "selection_criteria": "c",
    }
    kwargs[field] = "  "
    with pytest.raises(pydantic.ValidationError):
        CorrectiveActionCandidate(**kwargs)


def test_d5_requires_at_least_one_candidate() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one corrective action candidate"):
        D5Discipline(candidates=[])


def test_d5_missing_escape_point_candidate_names_it() -> None:
    with pytest.raises(pydantic.ValidationError, match="ESCAPE_POINT"):
        D5Discipline(candidates=[_d5_candidates()[0]])


def test_d5_missing_root_cause_candidate_names_it() -> None:
    with pytest.raises(pydantic.ValidationError, match="ROOT_CAUSE"):
        D5Discipline(candidates=[_d5_candidates()[1]])


def test_d5_rejects_duplicate_action_ids() -> None:
    root, escape = _d5_candidates()
    escape = escape.model_copy(update={"action_id": root.action_id})
    with pytest.raises(pydantic.ValidationError, match="duplicate action_id"):
        D5Discipline(candidates=[root, escape])


# ==============================================================================
# 8. D6 — Implement the PCAs, remove the ICA
# ==============================================================================


def _implemented(*, effective: bool | None = True, action_id: str = "PCA-1") -> ImplementedAction:
    return ImplementedAction(
        corrective_action_id=action_id,
        implemented_date=DAY_2,
        verification=None if effective is None else _verification(effective=effective, on=DAY_3),
    )


def test_implemented_action_normalizes_fields() -> None:
    action = ImplementedAction(
        corrective_action_id="  PCA-1 ", implemented_date=DAY_2, monitoring_notes="  "
    )
    assert action.corrective_action_id == "PCA-1"
    assert action.monitoring_notes is None
    assert action.is_verified is False


def test_implemented_action_rejects_blank_id() -> None:
    with pytest.raises(pydantic.ValidationError):
        ImplementedAction(corrective_action_id="  ", implemented_date=DAY_2)


def test_implemented_action_is_verified_reflects_effectiveness() -> None:
    assert _implemented(effective=True).is_verified is True
    assert _implemented(effective=False).is_verified is False
    assert _implemented(effective=None).is_verified is False


def test_d6_is_verified_only_when_every_action_is_verified() -> None:
    """D6Discipline.is_verified mirrors D3Discipline.is_verified: all-or-nothing over actions.

    This is the exact predicate the D8->CLOSED closure boundary reads for PCA_NOT_VERIFIED, so a
    single unverified or ineffective action must flip it to False.
    """
    all_good = D6Discipline(
        implemented_actions=[_implemented(), _implemented(action_id="PCA-2")]
    )
    assert all_good.is_verified is True

    mixed = D6Discipline(
        implemented_actions=[
            _implemented(effective=True),
            _implemented(effective=False, action_id="PCA-2"),
        ]
    )
    assert mixed.is_verified is False

    none_verified = D6Discipline(implemented_actions=[_implemented(effective=None)])
    assert none_verified.is_verified is False


def test_d6_requires_at_least_one_implemented_action() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one implemented action"):
        D6Discipline(implemented_actions=[])


def test_d6_without_removal_date_allows_unverified_actions() -> None:
    d6 = D6Discipline(implemented_actions=[_implemented(effective=None)])
    assert d6.interim_containment_removed_date is None


def test_d6_removal_allowed_when_every_action_is_verified() -> None:
    d6 = D6Discipline(
        implemented_actions=[_implemented(), _implemented(action_id="PCA-2")],
        interim_containment_removed_date=DAY_3,
    )
    assert d6.interim_containment_removed_date == DAY_3


def test_d6_removal_blocked_when_any_action_is_unverified() -> None:
    with pytest.raises(
        pydantic.ValidationError, match="interim_containment_removed_date cannot be set"
    ):
        D6Discipline(
            implemented_actions=[
                _implemented(effective=True),
                _implemented(effective=False, action_id="PCA-2"),
            ],
            interim_containment_removed_date=DAY_3,
        )


def test_d6_removal_blocked_when_no_action_is_verified_at_all() -> None:
    with pytest.raises(
        pydantic.ValidationError, match="interim_containment_removed_date cannot be set"
    ):
        D6Discipline(
            implemented_actions=[_implemented(effective=None)],
            interim_containment_removed_date=DAY_3,
        )


# ==============================================================================
# 9. D7 — Prevent recurrence
# ==============================================================================


def test_documentation_update_normalizes_fields() -> None:
    update = DocumentationUpdate(
        artifact_type="FMEA",
        artifact_reference="  PFMEA-77 ",
        updated_date=DAY_2,
        updated_by="   ",
    )
    assert update.artifact_reference == "PFMEA-77"
    assert update.updated_by is None


def test_documentation_update_rejects_blank_reference_and_bad_type() -> None:
    with pytest.raises(pydantic.ValidationError):
        DocumentationUpdate(artifact_type="FMEA", artifact_reference="  ", updated_date=DAY_2)
    with pytest.raises(pydantic.ValidationError):
        DocumentationUpdate(
            artifact_type="SPREADSHEET",  # type: ignore[arg-type]
            artifact_reference="X",
            updated_date=DAY_2,
        )


def test_d7_is_documented_reflects_presence_of_updates() -> None:
    empty = D7Discipline(systemic_changes_description="  PM schedule updated ")
    assert empty.systemic_changes_description == "PM schedule updated"
    assert empty.is_documented is False

    documented = D7Discipline(
        systemic_changes_description="PM schedule updated",
        documentation_updates=[
            DocumentationUpdate(
                artifact_type="OTHER", artifact_reference="WI-9", updated_date=DAY_2
            )
        ],
    )
    assert documented.is_documented is True


def _d7_with(*artifact_types: str) -> D7Discipline:
    """A D7 record carrying one DocumentationUpdate per given artifact_type."""
    return D7Discipline(
        systemic_changes_description="PM schedule updated",
        documentation_updates=[
            DocumentationUpdate(
                artifact_type=at,  # type: ignore[arg-type]
                artifact_reference=f"DOC-{i}",
                updated_date=DAY_2,
            )
            for i, at in enumerate(artifact_types)
        ],
    )


def test_d7_has_qualifying_update_is_false_when_no_updates() -> None:
    assert _d7_with().has_qualifying_update is False


@pytest.mark.parametrize("artifact_type", ["PROCESS_FLOW", "WORK_INSTRUCTION", "OTHER"])
def test_d7_has_qualifying_update_false_for_non_named_artifacts(artifact_type: str) -> None:
    """Non-qualifying updates leave has_qualifying_update False even though is_documented is True —
    this is the exact difference between the two properties."""
    discipline = _d7_with(artifact_type)
    assert discipline.is_documented is True
    assert discipline.has_qualifying_update is False


@pytest.mark.parametrize("artifact_type", ["FMEA", "CONTROL_PLAN"])
def test_d7_has_qualifying_update_true_for_named_artifact(artifact_type: str) -> None:
    assert _d7_with(artifact_type).has_qualifying_update is True


def test_d7_has_qualifying_update_true_when_qualifying_mixed_with_non_qualifying() -> None:
    discipline = _d7_with("OTHER", "FMEA")
    assert discipline.has_qualifying_update is True


def test_d7_rejects_blank_description() -> None:
    with pytest.raises(pydantic.ValidationError):
        D7Discipline(systemic_changes_description="   ")


# ==============================================================================
# 10. D8 — Recognize and close (Finding 1)
# ==============================================================================


def _override() -> WarningOverride:
    return WarningOverride(
        approved_by="P. Champion",
        justification="Chain is marginal but the containment data is conclusive.",
        override_date=DAY_3,
    )


def _d8(**overrides: Any) -> D8Discipline:
    kwargs: dict[str, Any] = {
        "team_recognition_notes": "Team recognized.",
        "linked_five_why_verdict": "ACCEPT",
    }
    kwargs.update(overrides)
    return D8Discipline(**kwargs)


def test_warning_override_normalizes_and_rejects_blanks() -> None:
    assert _override().approved_by == "P. Champion"
    with pytest.raises(pydantic.ValidationError):
        WarningOverride(approved_by="  ", justification="j", override_date=DAY_3)
    with pytest.raises(pydantic.ValidationError):
        WarningOverride(approved_by="a", justification="  ", override_date=DAY_3)


def test_d8_defaults_and_blank_normalization() -> None:
    d8 = _d8(documentation_reviewed_by="  ", closure_approved_by="  ")
    assert d8.closure_approved is False
    assert d8.documentation_reviewed_by is None
    assert d8.closure_approved_by is None


def test_d8_rejects_blank_recognition_notes() -> None:
    with pytest.raises(pydantic.ValidationError):
        _d8(team_recognition_notes="   ")


def test_d8_draft_state_accepts_a_rejected_chain() -> None:
    """A report may sit open with a REJECT verdict; the hard block fires only on closure."""
    d8 = _d8(linked_five_why_verdict="REJECT")
    assert d8.closure_approved is False
    assert d8.linked_five_why_verdict == "REJECT"


def test_d8_closure_requires_an_approver() -> None:
    with pytest.raises(pydantic.ValidationError, match="closure_approved_by is required"):
        _d8(closure_approved=True, closure_approved_date=DAY_3)


def test_d8_closure_requires_an_approval_date() -> None:
    with pytest.raises(pydantic.ValidationError, match="closure_approved_date is required"):
        _d8(closure_approved=True, closure_approved_by="P. Champion")


def test_d8_closure_blocked_on_reject_verdict() -> None:
    """NEGATIVE CONTROL TARGET: the REJECT hard block in _enforce_closure_rules."""
    with pytest.raises(pydantic.ValidationError, match="linked_five_why_verdict is REJECT"):
        _d8(
            linked_five_why_verdict="REJECT",
            closure_approved=True,
            closure_approved_by="P. Champion",
            closure_approved_date=DAY_3,
        )


def test_d8_closure_on_accept_needs_no_override() -> None:
    d8 = _d8(
        linked_five_why_verdict="ACCEPT",
        closure_approved=True,
        closure_approved_by="P. Champion",
        closure_approved_date=DAY_3,
    )
    assert d8.warning_override is None
    assert d8.closure_approved is True


def test_d8_closure_blocked_on_warning_without_override() -> None:
    """NEGATIVE CONTROL TARGET: the WARNING-override requirement in _enforce_closure_rules."""
    with pytest.raises(pydantic.ValidationError, match="requires a recorded"):
        _d8(
            linked_five_why_verdict="WARNING",
            closure_approved=True,
            closure_approved_by="P. Champion",
            closure_approved_date=DAY_3,
        )


def test_d8_closure_allowed_on_warning_with_override() -> None:
    d8 = _d8(
        linked_five_why_verdict="WARNING",
        warning_override=_override(),
        closure_approved=True,
        closure_approved_by="P. Champion",
        closure_approved_date=DAY_3,
    )
    assert d8.warning_override is not None


def test_d8_stray_override_on_an_accept_chain_is_not_rejected() -> None:
    d8 = _d8(
        linked_five_why_verdict="ACCEPT",
        warning_override=_override(),
        closure_approved=True,
        closure_approved_by="P. Champion",
        closure_approved_date=DAY_3,
    )
    assert d8.warning_override is not None


def test_five_why_verdict_stays_in_sync_with_five_why_module() -> None:
    """If five_why.py's verdict literal ever changes, this must fail loudly."""
    assert dataclasses.is_dataclass(FiveWhyValidationResult)
    hints = get_type_hints(FiveWhyValidationResult)
    assert get_args(hints["verdict"]) == get_args(m.FiveWhyVerdict)


# ==============================================================================
# 11. EightDReport envelope
# ==============================================================================


def test_minimal_report_constructs_with_every_discipline_empty() -> None:
    report = EightDReport(report_id="  8D-1 ", initiated_date=DAY_1)
    assert report.report_id == "8D-1"
    assert report.status == "OPEN"
    assert report.target_completion_date is None
    assert report.closed_date is None
    assert all(
        getattr(report, f"d{n}") is None for n in range(9)
    ), "a brand-new report must have no discipline populated"


def test_report_rejects_blank_report_id() -> None:
    with pytest.raises(pydantic.ValidationError):
        EightDReport(report_id="   ", initiated_date=DAY_1)


def test_report_team_property_aliases_d1() -> None:
    report = _full_report()
    assert report.team is report.d1


def test_report_team_is_none_without_d1() -> None:
    report = EightDReport(report_id="8D-1", initiated_date=DAY_1)
    assert report.team is None


def test_report_rejects_target_completion_before_initiation() -> None:
    with pytest.raises(pydantic.ValidationError, match="target_completion_date cannot be before"):
        EightDReport(
            report_id="8D-1", initiated_date=DAY_2, target_completion_date=DAY_1
        )


def test_report_rejects_closed_before_initiation() -> None:
    with pytest.raises(pydantic.ValidationError, match="closed_date cannot be before"):
        EightDReport(report_id="8D-1", initiated_date=DAY_2, closed_date=DAY_1)


def test_report_allows_dates_on_the_initiation_date() -> None:
    report = EightDReport(
        report_id="8D-1",
        initiated_date=DAY_1,
        target_completion_date=DAY_1,
        closed_date=DAY_1,
    )
    assert report.closed_date == DAY_1


def test_report_rejects_unknown_status() -> None:
    with pytest.raises(pydantic.ValidationError):
        EightDReport(
            report_id="8D-1",
            initiated_date=DAY_1,
            status="ARCHIVED",  # type: ignore[arg-type]
        )


def test_full_report_populates_all_nine_disciplines() -> None:
    report = _full_report()
    assert report.d0 is not None and report.d0.era_required is True
    assert report.d1 is not None and report.d1.members[0].role == "Process Engineer"
    assert report.d2 is not None and report.d2.method_used == "IS_IS_NOT"
    assert report.d3 is not None and report.d3.is_verified is True
    assert report.d4 is not None and report.d4.root_cause.five_why_verdict == "ACCEPT"
    assert report.d5 is not None and len(report.d5.candidates) == 2
    assert report.d6 is not None and report.d6.interim_containment_removed_date == DAY_3
    assert report.d7 is not None and report.d7.is_documented is True
    assert report.d8 is not None and report.d8.closure_approved is True


# ==============================================================================
# 12. validate_eight_d
# ==============================================================================


def test_validate_eight_d_passes_through_a_model() -> None:
    report = _full_report()
    assert validate_eight_d(report) is report


def test_validate_eight_d_builds_from_a_dict() -> None:
    report = validate_eight_d({"report_id": "8D-9", "initiated_date": "2026-01-01"})
    assert isinstance(report, EightDReport)
    assert report.initiated_date == DAY_1


def test_validate_eight_d_propagates_validation_errors() -> None:
    with pytest.raises(pydantic.ValidationError):
        validate_eight_d({"report_id": "", "initiated_date": "2026-01-01"})


@pytest.mark.parametrize("bad", [1, 1.5, None, ["a"], "text", (1, 2)])
def test_validate_eight_d_rejects_unsupported_types(bad: Any) -> None:
    with pytest.raises(TypeError, match="Expected EightDReport or dict"):
        validate_eight_d(bad)


# ==============================================================================
# 13. load_eight_d_json / load_eight_d_json_from_path
# ==============================================================================

MINIMAL_JSON = json.dumps({"report_id": "8D-1", "initiated_date": "2026-01-01"}).encode("utf-8")


def test_load_eight_d_json_from_bytes() -> None:
    report = load_eight_d_json(MINIMAL_JSON)
    assert report.report_id == "8D-1"


def test_load_eight_d_json_from_bytearray() -> None:
    assert load_eight_d_json(bytearray(MINIMAL_JSON)).report_id == "8D-1"


def test_load_eight_d_json_from_binary_stream() -> None:
    assert load_eight_d_json(io.BytesIO(MINIMAL_JSON)).report_id == "8D-1"


def test_load_eight_d_json_round_trips_a_full_report() -> None:
    payload = _full_report().model_dump_json().encode("utf-8")
    report = load_eight_d_json(payload)
    assert report.d8 is not None and report.d8.closure_approved is True
    assert report.team is report.d1


def test_load_eight_d_json_rejects_a_str_source() -> None:
    with pytest.raises(IngestError, match="A file path is not accepted here"):
        load_eight_d_json("some/path.json")  # type: ignore[arg-type]


def test_load_eight_d_json_rejects_a_pathlike_source(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="A file path is not accepted here"):
        load_eight_d_json(tmp_path / "report.json")  # type: ignore[arg-type]


def test_load_eight_d_json_at_exactly_max_bytes_succeeds() -> None:
    assert load_eight_d_json(MINIMAL_JSON, max_bytes=len(MINIMAL_JSON)).report_id == "8D-1"


def test_load_eight_d_json_one_byte_over_max_bytes_fails() -> None:
    with pytest.raises(IngestError, match="exceeds the"):
        load_eight_d_json(MINIMAL_JSON, max_bytes=len(MINIMAL_JSON) - 1)


def test_load_eight_d_json_stream_over_max_bytes_fails() -> None:
    with pytest.raises(IngestError, match="exceeds the"):
        load_eight_d_json(io.BytesIO(MINIMAL_JSON), max_bytes=10)


def test_load_eight_d_json_with_no_ceiling_reads_everything() -> None:
    padded = MINIMAL_JSON + b" " * 4096
    assert load_eight_d_json(io.BytesIO(padded), max_bytes=None).report_id == "8D-1"


def test_load_eight_d_json_unreadable_stream_raises_ingest_error() -> None:
    class _Broken:
        def read(self, *_args: Any) -> bytes:
            raise OSError("device on fire")

    with pytest.raises(IngestError, match="Could not read the 8D report source"):
        load_eight_d_json(_Broken())  # type: ignore[arg-type]


def test_load_eight_d_json_source_without_read_raises_ingest_error() -> None:
    with pytest.raises(IngestError, match="Could not read the 8D report source"):
        load_eight_d_json(object())  # type: ignore[arg-type]


def test_load_eight_d_json_rejects_non_utf8_bytes() -> None:
    with pytest.raises(IngestError, match="not valid UTF-8 text"):
        load_eight_d_json(b"\xff\xfe{}")


def test_load_eight_d_json_rejects_malformed_json() -> None:
    with pytest.raises(IngestError, match="Could not parse the 8D report as JSON"):
        load_eight_d_json(b"{not json")


def test_load_eight_d_json_rejects_a_json_array() -> None:
    with pytest.raises(IngestError, match="must be a single JSON object"):
        load_eight_d_json(b'[{"report_id": "8D-1"}]')


def test_load_eight_d_json_surfaces_the_pydantic_message() -> None:
    with pytest.raises(IngestError) as excinfo:
        load_eight_d_json(b'{"initiated_date": "2026-01-01"}')
    assert "8D report is invalid" in str(excinfo.value)
    assert "Field required" in str(excinfo.value)


def test_load_eight_d_json_wraps_a_type_error_from_the_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TypeError arm is unreachable through JSON alone; force it to prove it is wired."""

    def _boom(_data: Any) -> EightDReport:
        raise TypeError("synthetic validator failure")

    monkeypatch.setattr(m, "validate_eight_d", _boom)
    with pytest.raises(IngestError, match="synthetic validator failure"):
        load_eight_d_json(MINIMAL_JSON)


def test_load_eight_d_json_from_path_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_bytes(MINIMAL_JSON)
    assert load_eight_d_json_from_path(path).report_id == "8D-1"
    assert load_eight_d_json_from_path(str(path)).report_id == "8D-1"


def test_load_eight_d_json_from_path_missing_file_raises_ingest_error(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="Could not read"):
        load_eight_d_json_from_path(tmp_path / "absent.json")


def test_load_eight_d_json_from_path_propagates_ingest_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_bytes(b"{not json")
    with pytest.raises(IngestError, match="Could not parse the 8D report as JSON"):
        load_eight_d_json_from_path(path)


# ==============================================================================
# 14. CSV sub-table — D1 team roster
# ==============================================================================


def test_team_member_schema_shape() -> None:
    assert TEAM_MEMBER_SCHEMA.row_model is TeamMember
    assert TEAM_MEMBER_SCHEMA.required_columns == ("name",)
    assert TEAM_MEMBER_SCHEMA.optional_columns == ("role",)
    assert TEAM_MEMBER_SCHEMA.dataset_model is TeamMemberList


def test_load_team_members_csv_from_buffer() -> None:
    buf = _csv_buf([{"name": "A. Member", "role": "Process Engineer"}])
    df = load_team_members_csv(buf)
    assert list(df.columns) == ["name", "role"]
    assert len(df) == 1


def test_load_team_members_csv_without_optional_column() -> None:
    df = load_team_members_csv(_csv_buf([{"name": "A. Member"}]))
    assert list(df.columns) == ["name"]


def test_load_team_members_csv_from_path(tmp_path: Path) -> None:
    path = tmp_path / "roster.csv"
    path.write_text("name,role\nA. Member,Process Engineer\n", encoding="utf-8")
    df = load_team_members_csv(str(path))
    assert df.loc[0, "name"] == "A. Member"


def test_load_team_members_csv_missing_required_column_raises() -> None:
    with pytest.raises(IngestError, match="Missing required column"):
        load_team_members_csv(_csv_buf([{"role": "Process Engineer"}]))


def test_team_member_list_rejects_empty_rows() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one member"):
        TeamMemberList(rows=[])


def test_validate_team_members_battery(tmp_path: Path) -> None:
    model = TeamMemberList(rows=[TeamMember(name="A. Member")])
    assert validate_team_members(model) is model

    df = load_team_members_csv(_csv_buf([{"name": "A. Member", "role": None}]))
    assert validate_team_members(df).rows[0].role is None

    assert validate_team_members([{"name": "B. Member"}]).rows[0].name == "B. Member"
    assert validate_team_members([TeamMember(name="C. Member")]).rows[0].name == "C. Member"
    assert validate_team_members({"rows": [{"name": "D. Member"}]}).rows[0].name == "D. Member"


def test_validate_team_members_rejects_bad_list_item() -> None:
    with pytest.raises(TypeError, match="Expected TeamMember or dict in list"):
        validate_team_members(["not a member"])


def test_validate_team_members_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Expected TeamMemberList, DataFrame"):
        validate_team_members(42)


# ==============================================================================
# 15. CSV sub-table — D3 containment measures
# ==============================================================================


def test_containment_action_schema_shape() -> None:
    assert CONTAINMENT_ACTION_SCHEMA.required_columns == ("description", "implemented_date")
    assert CONTAINMENT_ACTION_SCHEMA.optional_columns == ()
    assert CONTAINMENT_ACTION_SCHEMA.dataset_model is ContainmentActionList


def test_load_containment_actions_csv_from_buffer() -> None:
    buf = _csv_buf([{"description": "Sort at dock", "implemented_date": "2026-01-01"}])
    df = load_containment_actions_csv(buf)
    assert list(df.columns) == ["description", "implemented_date"]


def test_load_containment_actions_csv_from_path(tmp_path: Path) -> None:
    path = tmp_path / "containment.csv"
    path.write_text("description,implemented_date\nSort at dock,2026-01-01\n", encoding="utf-8")
    assert len(load_containment_actions_csv(str(path))) == 1


def test_load_containment_actions_csv_missing_required_column_raises() -> None:
    with pytest.raises(IngestError, match="Missing required column"):
        load_containment_actions_csv(_csv_buf([{"description": "Sort at dock"}]))


def test_containment_action_list_rejects_empty_rows() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one containment action"):
        ContainmentActionList(rows=[])


def test_validate_containment_actions_battery() -> None:
    model = ContainmentActionList(rows=[_containment()])
    assert validate_containment_actions(model) is model

    df = load_containment_actions_csv(
        _csv_buf([{"description": "Sort at dock", "implemented_date": "2026-01-01"}])
    )
    assert validate_containment_actions(df).rows[0].implemented_date == DAY_1

    from_dicts = validate_containment_actions(
        [{"description": "Sort", "implemented_date": "2026-01-01"}]
    )
    assert from_dicts.rows[0].is_verified is False
    assert validate_containment_actions([_containment()]).rows[0].is_verified is True
    assert (
        validate_containment_actions(
            {"rows": [{"description": "Sort", "implemented_date": "2026-01-01"}]}
        ).rows[0].description
        == "Sort"
    )


def test_validate_containment_actions_rejects_bad_list_item() -> None:
    with pytest.raises(TypeError, match="Expected ContainmentAction or dict in list"):
        validate_containment_actions([3])


def test_validate_containment_actions_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Expected ContainmentActionList, DataFrame"):
        validate_containment_actions("nope")


# ==============================================================================
# 16. CSV sub-table — D5 corrective-action candidates
# ==============================================================================

_PCA_ROWS = [
    {
        "action_id": "PCA-1",
        "target": "ROOT_CAUSE",
        "description": "Replace the die",
        "selection_criteria": "Lowest residual risk",
        "verified_no_undesirable_effects": True,
        "verification_notes": "Dry run passed",
    },
    {
        "action_id": "PCA-2",
        "target": "ESCAPE_POINT",
        "description": "Add vision check",
        "selection_criteria": "Detects before escape",
        "verified_no_undesirable_effects": False,
        "verification_notes": None,
    },
]


def test_corrective_action_candidate_schema_shape() -> None:
    assert CORRECTIVE_ACTION_CANDIDATE_SCHEMA.required_columns == (
        "action_id",
        "target",
        "description",
        "selection_criteria",
    )
    assert CORRECTIVE_ACTION_CANDIDATE_SCHEMA.optional_columns == (
        "verified_no_undesirable_effects",
        "verification_notes",
    )


def test_load_corrective_action_candidates_csv_from_buffer() -> None:
    df = load_corrective_action_candidates_csv(_csv_buf(_PCA_ROWS))
    assert list(df.columns) == [
        "action_id",
        "target",
        "description",
        "selection_criteria",
        "verified_no_undesirable_effects",
        "verification_notes",
    ]


def test_load_corrective_action_candidates_csv_without_optional_columns() -> None:
    rows = [{k: v for k, v in row.items() if k in CORRECTIVE_ACTION_CANDIDATE_SCHEMA.required_columns} for row in _PCA_ROWS]
    df = load_corrective_action_candidates_csv(_csv_buf(rows))
    assert list(df.columns) == list(CORRECTIVE_ACTION_CANDIDATE_SCHEMA.required_columns)


def test_load_corrective_action_candidates_csv_from_path(tmp_path: Path) -> None:
    path = tmp_path / "pca.csv"
    path.write_bytes(pd.DataFrame(_PCA_ROWS).to_csv(index=False).encode("utf-8"))
    assert len(load_corrective_action_candidates_csv(str(path))) == 2


def test_load_corrective_action_candidates_csv_missing_required_column_raises() -> None:
    rows = [{k: v for k, v in row.items() if k != "target"} for row in _PCA_ROWS]
    with pytest.raises(IngestError, match="Missing required column"):
        load_corrective_action_candidates_csv(_csv_buf(rows))


def test_load_corrective_action_candidates_csv_missing_a_target_raises() -> None:
    with pytest.raises(IngestError, match="ESCAPE_POINT"):
        load_corrective_action_candidates_csv(_csv_buf(_PCA_ROWS[:1]))


def test_corrective_action_candidate_list_rejects_empty_rows() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one corrective action candidate"):
        CorrectiveActionCandidateList(rows=[])


def test_corrective_action_candidate_list_rejects_duplicate_ids() -> None:
    root, escape = _d5_candidates()
    escape = escape.model_copy(update={"action_id": root.action_id})
    with pytest.raises(pydantic.ValidationError, match="duplicate action_id"):
        CorrectiveActionCandidateList(rows=[root, escape])


def test_validate_corrective_action_candidates_battery() -> None:
    model = CorrectiveActionCandidateList(rows=_d5_candidates())
    assert validate_corrective_action_candidates(model) is model

    df = load_corrective_action_candidates_csv(_csv_buf(_PCA_ROWS))
    from_df = validate_corrective_action_candidates(df)
    assert from_df.rows[0].verified_no_undesirable_effects is True
    assert from_df.rows[1].verification_notes is None

    assert len(validate_corrective_action_candidates(_PCA_ROWS).rows) == 2
    assert len(validate_corrective_action_candidates(_d5_candidates()).rows) == 2
    assert len(validate_corrective_action_candidates({"rows": _d5_candidates()}).rows) == 2


def test_validate_corrective_action_candidates_rejects_bad_list_item() -> None:
    with pytest.raises(TypeError, match="Expected CorrectiveActionCandidate or dict in list"):
        validate_corrective_action_candidates([object()])


def test_validate_corrective_action_candidates_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Expected CorrectiveActionCandidateList, DataFrame"):
        validate_corrective_action_candidates(7.5)


# ==============================================================================
# 17. CSV sub-table — D7 documentation updates
# ==============================================================================

_DOC_ROWS = [
    {
        "artifact_type": "CONTROL_PLAN",
        "artifact_reference": "CP-12345 rev C",
        "updated_date": "2026-01-03",
        "updated_by": "D. Documenter",
    }
]


def test_documentation_update_schema_shape() -> None:
    assert DOCUMENTATION_UPDATE_SCHEMA.required_columns == (
        "artifact_type",
        "artifact_reference",
        "updated_date",
    )
    assert DOCUMENTATION_UPDATE_SCHEMA.optional_columns == ("updated_by",)


def test_load_documentation_updates_csv_from_buffer() -> None:
    df = load_documentation_updates_csv(_csv_buf(_DOC_ROWS))
    assert list(df.columns) == [
        "artifact_type",
        "artifact_reference",
        "updated_date",
        "updated_by",
    ]


def test_load_documentation_updates_csv_without_optional_column() -> None:
    rows = [{k: v for k, v in row.items() if k != "updated_by"} for row in _DOC_ROWS]
    df = load_documentation_updates_csv(_csv_buf(rows))
    assert list(df.columns) == ["artifact_type", "artifact_reference", "updated_date"]


def test_load_documentation_updates_csv_from_path(tmp_path: Path) -> None:
    path = tmp_path / "docs.csv"
    path.write_bytes(pd.DataFrame(_DOC_ROWS).to_csv(index=False).encode("utf-8"))
    assert len(load_documentation_updates_csv(str(path))) == 1


def test_load_documentation_updates_csv_missing_required_column_raises() -> None:
    rows = [{k: v for k, v in row.items() if k != "updated_date"} for row in _DOC_ROWS]
    with pytest.raises(IngestError, match="Missing required column"):
        load_documentation_updates_csv(_csv_buf(rows))


def test_documentation_update_list_rejects_empty_rows() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one update"):
        DocumentationUpdateList(rows=[])


def test_validate_documentation_updates_battery() -> None:
    row = DocumentationUpdate(
        artifact_type="FMEA", artifact_reference="PFMEA-77", updated_date=DAY_2
    )
    model = DocumentationUpdateList(rows=[row])
    assert validate_documentation_updates(model) is model

    df = load_documentation_updates_csv(_csv_buf(_DOC_ROWS))
    assert validate_documentation_updates(df).rows[0].updated_date == DAY_3

    assert validate_documentation_updates(_DOC_ROWS).rows[0].updated_by == "D. Documenter"
    assert validate_documentation_updates([row]).rows[0].artifact_type == "FMEA"
    assert validate_documentation_updates({"rows": [row]}).rows[0].artifact_reference == "PFMEA-77"


def test_validate_documentation_updates_rejects_bad_list_item() -> None:
    with pytest.raises(TypeError, match="Expected DocumentationUpdate or dict in list"):
        validate_documentation_updates([None])


def test_validate_documentation_updates_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Expected DocumentationUpdateList, DataFrame"):
        validate_documentation_updates(object())

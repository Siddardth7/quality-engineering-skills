"""
Unit tests for the 8D D0/D1/D2/D3 discipline engines (quality_core.rca.eight_d_disciplines).

Tests:
1. Dataclass serialization: D0Finding, D0ValidationResult, D1Finding, D1ValidationResult.
2. Helpers: _is_verified_effective (absent / ineffective / effective), _dedupe (repeat skipping).
3. D0 positive controls — one per reachable branch:
   - era_required=False (ACCEPT, short-circuits even with a fully populated ERA).
   - era_required=True, no implementation date (REJECT, ERA_NOT_IMPLEMENTED).
   - era_required=True, no implementation date but a stray verification record (REJECT, both
     ERA_NOT_IMPLEMENTED and ERA_VERIFIED_WITHOUT_IMPLEMENTATION).
   - implemented, unverified (REJECT, ERA_NOT_VERIFIED).
   - implemented, verified ineffective (REJECT, ERA_VERIFIED_INEFFECTIVE).
   - implemented, verified effective but verified_date precedes implementation (WARNING).
   - implemented and verified effective (ACCEPT, ERA_READY); same-day verification is consistent.
4. D1 positive controls — one per branch combination:
   - empty members (REJECT, NO_TEAM_MEMBERS).
   - complete roster with roles (ACCEPT, TEAM_READY).
   - duplicate member names, case/whitespace-insensitive (WARNING, one finding per distinct name).
   - roleless members (WARNING, one finding per affected member).
   - champion == team_leader, case/whitespace-insensitive (WARNING).
   - error-over-warning precedence: empty members + champion == team_leader -> REJECT.
5. D2 positive controls and negative controls — one per finding condition:
   - clean input (distinct fields, numeric quantification, complete scoping) -> ACCEPT, no
     findings.
   - the composed "<what_is_wrong> with <with_what>" statement overrides an IsIsNotMatrix's own.
   - DEGENERATE_PROBLEM_STATEMENT fires on normalised equality only; distinct, overlapping and
     substring field pairs are negative controls that must NOT fire.
   - QUANTIFICATION_NOT_NUMERIC fires when no digit is present; "14ppm" / "3 per shift" /
     "0.8 mm oversize" are negative controls that must NOT fire.
   - METHOD_5W2H_DESCRIPTION_INCOMPLETE fires when method_used="5W2H" and any of the seven
     CQI-20 Figure 12 questions is unanswered: `error` severity, REJECT verdict, the missing
     questions named, and structured evidence on `five_w_two_h`. Negative controls: all seven
     answered ACCEPTs; None / GANTT / IS_IS_NOT / OTHER are never judged, answered or not.
   - a citation control binds the engine's seven questions to the RULE-8D-D2-003 manifest rows
     and forbids the "5 Why - 2 How" reading it replaced.
   - is_is_not=None warns (IS_IS_NOT_NOT_PROVIDED) and never reaches scope_is_is_not; explicitly
     supplied but empty scoping data REJECTs by delegation (IS_IS_NOT_SCOPING_REJECTED).
   - verdict tiering: error outranks warning; several warnings do not escalate.
   - recommendation de-duplication across a finding and the nested scoping result.
   - TypeError / pydantic.ValidationError from scope_is_is_not propagate uncaught.
6. Package re-export smoke test from quality_core.rca.
7. D3 positive/negative controls — one per reachable branch, the mandatory NCR-linkage
   negative control (#208), catch-tuple branches, union-shape pass-through, serialization,
   _ncr_linkage_findings unit cases, and the is_verified single-source-of-truth guard.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Literal

import pandas as pd
import pydantic
import pytest
from quality_core.copq.schema import COPQDataset, CostItem
from quality_core.ncr.schema import NCRDataset, validate_ncr
from quality_core.rca.eight_d_disciplines import (
    D0Finding,
    D0ValidationResult,
    D1Finding,
    D1ValidationResult,
    D2Finding,
    D2ValidationResult,
    D3Finding,
    D3ValidationResult,
    D4Finding,
    D4ValidationResult,
    D5Finding,
    D5ValidationResult,
    D6Finding,
    D6ValidationResult,
    _d5_traceability_finding,
    _dedupe,
    _five_w_two_h_answers,
    _is_verified_effective,
    _ncr_linkage_findings,
    validate_d0_readiness,
    validate_d1_team,
    validate_d2_problem_description,
    validate_d3_containment,
    validate_d4_root_cause,
    validate_d5_pca_selection,
    validate_d6_implementation_validation,
)
from quality_core.rca.eight_d_schema import (
    CandidateCauseTest,
    ContainmentAction,
    CorrectiveActionCandidate,
    D0Discipline,
    D1Discipline,
    D2Discipline,
    D3Discipline,
    D4Discipline,
    D5Discipline,
    D6Discipline,
    EffectivenessVerification,
    EscapePointFinding,
    ImplementedAction,
    LinkedNCRValidation,
    RootCauseFinding,
    TeamMember,
)
from quality_core.rca.is_is_not import scope_is_is_not
from quality_core.rca.schema import IsIsNotMatrix

IMPLEMENTED = datetime.date(2026, 3, 1)


def _verification(
    *,
    is_effective: bool = True,
    verified_date: datetime.date = IMPLEMENTED,
) -> EffectivenessVerification:
    """Build an EffectivenessVerification with the fields under test parameterized."""
    return EffectivenessVerification(
        verified_by="Q. Inspector",
        verified_date=verified_date,
        evidence="100% sort of 4 lots; zero escapes at the customer for 10 shipments.",
        is_effective=is_effective,
    )


#: The seven CQI-20 Figure 12 question labels, in the manual's order, paired with the
#: `D2Discipline` field that answers each. Written out independently of the engine so a change
#: to `_five_w_two_h_answers` has to be made twice, on purpose.
FIGURE_12_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("Who?", "w2h_who"),
    ("What?", "w2h_what"),
    ("When?", "w2h_when"),
    ("Where?", "w2h_where"),
    ("Why?", "w2h_why"),
    ("How?", "w2h_how"),
    ("How Many?", "w2h_how_many"),
)


def _full_w2h() -> dict[str, str]:
    """Every Figure 12 question answered — a complete 5W2H description."""
    return {field: f"answer to {question}" for question, field in FIGURE_12_QUESTIONS}


def _d2(
    *,
    what_is_wrong: str = "Bore diameter undersized",
    with_what: str = "Housing P/N 44821",
    quantification: str = "14 of 500 parts",
    method_used: str | None = None,
    **w2h: str | None,
) -> D2Discipline:
    """Build a D2Discipline with the fields under test parameterized.

    Extra keyword arguments are the optional `w2h_*` Figure 12 answers; omitted ones stay None.
    """
    return D2Discipline(
        what_is_wrong=what_is_wrong,
        with_what=with_what,
        quantification=quantification,
        method_used=method_used,
        **w2h,
    )


def _full_is_is_not_rows() -> list[dict[str, str]]:
    """Four KT dimensions, each with paired distinctions and changes — a scoping ACCEPT."""
    return [
        {
            "dimension": "WHAT",
            "is_data": "Housing P/N 44821 bore undersized",
            "is_not_data": "Housing P/N 44822 bore",
            "distinctions": "44821 uses the older reamer fixture",
            "changes": "Fixture rebuilt on 2026-02-14",
        },
        {
            "dimension": "WHERE",
            "is_data": "Op 30 reaming cell B",
            "is_not_data": "Op 30 reaming cell A",
            "distinctions": "Cell B coolant loop is shared",
            "changes": "Coolant concentration set point lowered in cell B",
        },
        {
            "dimension": "WHEN",
            "is_data": "Second shift since 2026-02-16",
            "is_not_data": "First shift",
            "distinctions": "Second shift runs without a setup verification",
            "changes": "Setup verification dropped from the second-shift routine",
        },
        {
            "dimension": "EXTENT",
            "is_data": "14 of 500 parts, growing per lot",
            "is_not_data": "Zero parts in lots before 2026-02-16",
            "distinctions": "Only lots run after the fixture rebuild are affected",
            "changes": "Reamer replaced at the same rebuild",
        },
    ]


def _partial_is_is_not_rows() -> list[dict[str, str | None]]:
    """Two dimensions, one of them missing its changes — a scoping WARNING with 2 warnings."""
    rows: list[dict[str, str | None]] = [dict(r) for r in _full_is_is_not_rows()[:2]]
    rows[0]["changes"] = None
    return rows


def _codes(
    result: D0ValidationResult | D1ValidationResult | D2ValidationResult | D4ValidationResult,
) -> list[str]:
    """Return the finding codes of a result, in order."""
    return [f.code for f in result.findings]


def _severities(
    result: D0ValidationResult | D1ValidationResult | D2ValidationResult,
) -> list[str]:
    """Return the finding severities of a result, in order.

    D0's verdict is assigned explicitly per branch rather than derived from finding
    severity (unlike D1), so severities on D0 findings are load-bearing only if a test
    pins them directly.
    """
    return [f.severity for f in result.findings]


# ==============================================================================
# 1. Dataclass serialization
# ==============================================================================


def test_d0_finding_to_dict_shape() -> None:
    """Assert D0Finding.to_dict returns every field."""
    finding = D0Finding(
        code="ERA_READY", severity="info", message="msg", recommendation="rec"
    )
    assert finding.to_dict() == {
        "code": "ERA_READY",
        "severity": "info",
        "message": "msg",
        "recommendation": "rec",
    }


def test_d0_validation_result_to_dict_nests_findings() -> None:
    """Assert D0ValidationResult.to_dict recurses into child finding dicts."""
    finding = D0Finding(
        code="ERA_NOT_VERIFIED", severity="error", message="msg", recommendation="rec"
    )
    result = D0ValidationResult(
        basis="Ford Global 8D / AIAG CQI-20",
        valid=False,
        verdict="REJECT",
        era_required=True,
        era_implemented=True,
        era_verified=False,
        findings=[finding],
        recommendations=["rec"],
    )
    payload = result.to_dict()
    assert payload == {
        "basis": "Ford Global 8D / AIAG CQI-20",
        "valid": False,
        "verdict": "REJECT",
        "era_required": True,
        "era_implemented": True,
        "era_verified": False,
        "findings": [finding.to_dict()],
        "recommendations": ["rec"],
    }
    assert isinstance(payload["findings"][0], dict)
    assert payload["recommendations"] is not result.recommendations


def test_d1_finding_to_dict_shape() -> None:
    """Assert D1Finding.to_dict returns every field including member_name."""
    finding = D1Finding(
        code="TEAM_MEMBER_ROLE_UNDEFINED",
        severity="warning",
        member_name="A. Smith",
        message="msg",
        recommendation="rec",
    )
    assert finding.to_dict() == {
        "code": "TEAM_MEMBER_ROLE_UNDEFINED",
        "severity": "warning",
        "member_name": "A. Smith",
        "message": "msg",
        "recommendation": "rec",
    }


def test_d1_validation_result_to_dict_nests_findings() -> None:
    """Assert D1ValidationResult.to_dict recurses into child finding dicts."""
    finding = D1Finding(
        code="NO_TEAM_MEMBERS",
        severity="error",
        member_name=None,
        message="msg",
        recommendation="rec",
    )
    result = D1ValidationResult(
        basis="Ford Global 8D / AIAG CQI-20",
        valid=False,
        verdict="REJECT",
        champion="C. Hampion",
        team_leader="L. Eader",
        member_count=0,
        findings=[finding],
        recommendations=["rec"],
    )
    payload = result.to_dict()
    assert payload == {
        "basis": "Ford Global 8D / AIAG CQI-20",
        "valid": False,
        "verdict": "REJECT",
        "champion": "C. Hampion",
        "team_leader": "L. Eader",
        "member_count": 0,
        "findings": [finding.to_dict()],
        "recommendations": ["rec"],
    }
    assert isinstance(payload["findings"][0], dict)
    assert payload["recommendations"] is not result.recommendations


# ==============================================================================
# 2. Helpers
# ==============================================================================


@pytest.mark.parametrize(
    ("verification", "expected"),
    [
        (None, False),
        (_verification(is_effective=False), False),
        (_verification(is_effective=True), True),
    ],
    ids=["absent", "ineffective", "effective"],
)
def test_is_verified_effective(
    verification: EffectivenessVerification | None, expected: bool
) -> None:
    """Assert the shared predicate requires a record that concluded 'effective'."""
    assert _is_verified_effective(verification) is expected


def test_dedupe_preserves_first_seen_order_and_skips_repeats() -> None:
    """Assert _dedupe keeps the first occurrence of each value and drops later repeats."""
    assert _dedupe(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]
    assert _dedupe([]) == []


# ==============================================================================
# 3. D0 — one positive control per branch
# ==============================================================================


def test_d0_not_required_accepts() -> None:
    """Assert era_required=False yields ACCEPT with an ERA_NOT_REQUIRED info finding."""
    result = validate_d0_readiness(D0Discipline(era_required=False))
    assert result.verdict == "ACCEPT"
    assert result.valid is True
    assert result.basis == "Ford Global 8D / AIAG CQI-20"
    assert _codes(result) == ["ERA_NOT_REQUIRED"]
    assert _severities(result) == ["info"]
    assert result.era_required is False
    assert result.era_implemented is False
    assert result.era_verified is False
    assert result.recommendations == [result.findings[0].recommendation]


def test_d0_not_required_short_circuits_a_populated_era() -> None:
    """Assert a fully populated ERA is still ACCEPT/ERA_NOT_REQUIRED when era_required=False."""
    result = validate_d0_readiness(
        D0Discipline(
            era_required=False,
            era_description="Certified stock sort at the customer's dock.",
            era_implemented_date=IMPLEMENTED,
            era_verification=_verification(),
        )
    )
    assert result.verdict == "ACCEPT"
    assert _codes(result) == ["ERA_NOT_REQUIRED"]
    # Readiness flags still report the underlying record faithfully.
    assert result.era_implemented is True
    assert result.era_verified is True


def test_d0_required_but_not_implemented_rejects() -> None:
    """Assert a required, unimplemented ERA rejects with ERA_NOT_IMPLEMENTED alone."""
    result = validate_d0_readiness(
        D0Discipline(era_required=True, era_description="Contain suspect stock at the dock.")
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["ERA_NOT_IMPLEMENTED"]
    assert _severities(result) == ["error"]
    assert result.era_implemented is False
    assert result.era_verified is False


def test_d0_verification_without_implementation_raises_both_findings() -> None:
    """Assert a verification with no implementation date raises both error findings."""
    result = validate_d0_readiness(
        D0Discipline(
            era_required=True,
            era_description="Contain suspect stock at the dock.",
            era_verification=_verification(),
        )
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["ERA_NOT_IMPLEMENTED", "ERA_VERIFIED_WITHOUT_IMPLEMENTATION"]
    assert _severities(result) == ["error", "error"]
    assert "Q. Inspector" in result.findings[1].message
    assert result.era_implemented is False
    assert result.era_verified is True
    assert len(result.recommendations) == 2


def test_d0_implemented_but_unverified_rejects() -> None:
    """Assert an implemented ERA with no verification record rejects."""
    result = validate_d0_readiness(
        D0Discipline(
            era_required=True,
            era_description="Contain suspect stock at the dock.",
            era_implemented_date=IMPLEMENTED,
        )
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["ERA_NOT_VERIFIED"]
    assert _severities(result) == ["error"]
    assert str(IMPLEMENTED) in result.findings[0].message
    assert result.era_implemented is True
    assert result.era_verified is False


def test_d0_verified_ineffective_rejects() -> None:
    """Assert a verification concluding 'not effective' rejects rather than passing."""
    result = validate_d0_readiness(
        D0Discipline(
            era_required=True,
            era_description="Contain suspect stock at the dock.",
            era_implemented_date=IMPLEMENTED,
            era_verification=_verification(is_effective=False),
        )
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["ERA_VERIFIED_INEFFECTIVE"]
    assert _severities(result) == ["error"]
    assert result.era_implemented is True
    assert result.era_verified is False


def test_d0_verification_date_before_implementation_warns() -> None:
    """Assert a verification dated before implementation warns but stays valid."""
    result = validate_d0_readiness(
        D0Discipline(
            era_required=True,
            era_description="Contain suspect stock at the dock.",
            era_implemented_date=IMPLEMENTED,
            era_verification=_verification(verified_date=datetime.date(2026, 2, 27)),
        )
    )
    assert result.verdict == "WARNING"
    assert result.valid is True
    assert _codes(result) == ["ERA_VERIFICATION_DATE_INCONSISTENT"]
    assert _severities(result) == ["warning"]
    assert result.era_implemented is True
    assert result.era_verified is True


def test_d0_fully_ready_accepts_with_same_day_verification() -> None:
    """Assert same-day verification is consistent and a complete ERA is ACCEPT."""
    result = validate_d0_readiness(
        D0Discipline(
            era_required=True,
            era_description="Contain suspect stock at the dock.",
            era_implemented_date=IMPLEMENTED,
            era_verification=_verification(verified_date=IMPLEMENTED),
        )
    )
    assert result.verdict == "ACCEPT"
    assert result.valid is True
    assert _codes(result) == ["ERA_READY"]
    assert _severities(result) == ["info"]
    assert result.era_implemented is True
    assert result.era_verified is True


def test_d0_fully_ready_accepts_with_later_verification() -> None:
    """Assert a verification dated after implementation is ACCEPT, with no upper bound."""
    result = validate_d0_readiness(
        D0Discipline(
            era_required=True,
            era_description="Contain suspect stock at the dock.",
            era_implemented_date=IMPLEMENTED,
            era_verification=_verification(verified_date=datetime.date(2027, 9, 30)),
        )
    )
    assert result.verdict == "ACCEPT"
    assert _codes(result) == ["ERA_READY"]


# ==============================================================================
# 4. D1 — one positive control per branch combination
# ==============================================================================


def test_d1_empty_members_rejects() -> None:
    """Assert a Champion and Team Leader with no members is an incomplete team (REJECT)."""
    result = validate_d1_team(D1Discipline(champion="C. Hampion", team_leader="L. Eader"))
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["NO_TEAM_MEMBERS"]
    assert result.findings[0].severity == "error"
    assert result.findings[0].member_name is None
    assert result.champion == "C. Hampion"
    assert result.team_leader == "L. Eader"
    assert result.member_count == 0


def test_d1_complete_team_accepts() -> None:
    """Assert a roster with distinct, roled members accepts."""
    result = validate_d1_team(
        D1Discipline(
            champion="C. Hampion",
            team_leader="L. Eader",
            members=[
                TeamMember(name="A. Smith", role="Process Engineer"),
                TeamMember(name="B. Jones", role="Quality Engineer"),
            ],
        )
    )
    assert result.verdict == "ACCEPT"
    assert result.valid is True
    assert result.basis == "Ford Global 8D / AIAG CQI-20"
    assert _codes(result) == ["TEAM_READY"]
    assert result.member_count == 2
    assert result.recommendations == [result.findings[0].recommendation]


def test_d1_member_name_matching_a_named_role_is_not_a_finding() -> None:
    """Assert a member who is also the Champion or Team Leader raises nothing."""
    result = validate_d1_team(
        D1Discipline(
            champion="C. Hampion",
            team_leader="L. Eader",
            members=[
                TeamMember(name="C. Hampion", role="Champion"),
                TeamMember(name="L. Eader", role="Team Leader"),
            ],
        )
    )
    assert result.verdict == "ACCEPT"
    assert _codes(result) == ["TEAM_READY"]


def test_d1_duplicate_member_names_raise_one_finding_per_distinct_name() -> None:
    """Assert duplicates are matched case/whitespace-insensitively, one finding per name."""
    result = validate_d1_team(
        D1Discipline(
            champion="C. Hampion",
            team_leader="L. Eader",
            members=[
                TeamMember(name="J. Smith", role="Process Engineer"),
                TeamMember(name="  j. smith ", role="Maintenance"),
                TeamMember(name="B. Jones", role="Quality Engineer"),
            ],
        )
    )
    assert result.verdict == "WARNING"
    assert result.valid is True
    duplicates = [f for f in result.findings if f.code == "DUPLICATE_TEAM_MEMBER"]
    assert len(duplicates) == 1
    assert duplicates[0].member_name == "J. Smith"
    assert duplicates[0].severity == "warning"
    assert "2 times" in duplicates[0].message
    assert result.member_count == 3


def test_d1_roleless_members_raise_one_finding_each() -> None:
    """Assert every member with no role raises its own warning, deduped into one recommendation."""
    result = validate_d1_team(
        D1Discipline(
            champion="C. Hampion",
            team_leader="L. Eader",
            members=[
                TeamMember(name="A. Smith"),
                TeamMember(name="B. Jones", role="Quality Engineer"),
                TeamMember(name="C. Doe"),
            ],
        )
    )
    assert result.verdict == "WARNING"
    assert result.valid is True
    roleless = [f for f in result.findings if f.code == "TEAM_MEMBER_ROLE_UNDEFINED"]
    assert len(roleless) == 2
    assert [f.member_name for f in roleless] == ["A. Smith", "C. Doe"]
    # Identical recommendation text collapses to a single entry.
    assert len(result.recommendations) == 1


def test_d1_champion_equals_team_leader_warns() -> None:
    """Assert one person in both roles warns, matched case/whitespace-insensitively."""
    result = validate_d1_team(
        D1Discipline(
            champion="P. Ayne",
            team_leader="  p. AYNE ",
            members=[TeamMember(name="A. Smith", role="Process Engineer")],
        )
    )
    assert result.verdict == "WARNING"
    assert result.valid is True
    assert _codes(result) == ["CHAMPION_TEAM_LEADER_SAME_PERSON"]
    assert result.findings[0].member_name is None
    # Neither spelling is already normalised, so dropping the casefold on either side breaks
    # the match. The schema strips surrounding whitespace before the engine sees it.
    assert result.champion == "P. Ayne"
    assert result.team_leader == "p. AYNE"


def test_d1_error_outranks_warning() -> None:
    """Assert an empty roster plus a doubled-up role is REJECT, with both findings present."""
    result = validate_d1_team(D1Discipline(champion="P. Ayne", team_leader="P. AYNE"))
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["NO_TEAM_MEMBERS", "CHAMPION_TEAM_LEADER_SAME_PERSON"]
    assert len(result.recommendations) == 2


# ==============================================================================
# 5. D2 — problem statement composition + Is/Is-Not delegation
# ==============================================================================


def test_d2_finding_to_dict_shape() -> None:
    """Assert D2Finding.to_dict returns every field."""
    finding = D2Finding(
        code="QUANTIFICATION_NOT_NUMERIC",
        severity="warning",
        message="msg",
        recommendation="rec",
    )
    assert finding.to_dict() == {
        "code": "QUANTIFICATION_NOT_NUMERIC",
        "severity": "warning",
        "message": "msg",
        "recommendation": "rec",
    }


def test_d2_validation_result_to_dict_nests_findings_and_scoping() -> None:
    """Assert D2ValidationResult.to_dict recurses into findings and carries the scoping payload."""
    finding = D2Finding(
        code="IS_IS_NOT_SCOPING_REJECTED", severity="error", message="msg", recommendation="rec"
    )
    scoping_payload = {"verdict": "REJECT", "total_rows": 0}
    w2h_payload = {"answered": ["Who?"], "missing": ["What?"], "complete": False}
    result = D2ValidationResult(
        basis="Ford Global 8D / AIAG CQI-20",
        valid=False,
        verdict="REJECT",
        problem_statement="Bore undersized with Housing 44821",
        findings=[finding],
        is_is_not=scoping_payload,
        five_w_two_h=w2h_payload,
        recommendations=["rec"],
    )
    payload = result.to_dict()
    assert payload == {
        "basis": "Ford Global 8D / AIAG CQI-20",
        "valid": False,
        "verdict": "REJECT",
        "problem_statement": "Bore undersized with Housing 44821",
        "findings": [finding.to_dict()],
        "is_is_not": scoping_payload,
        "five_w_two_h": w2h_payload,
        "recommendations": ["rec"],
    }
    assert isinstance(payload["findings"][0], dict)
    assert payload["recommendations"] is not result.recommendations


def test_d2_validation_result_to_dict_keeps_absent_payloads_none() -> None:
    """Assert a result with no scoping and no declared 5W2H serialises both payloads as None."""
    result = D2ValidationResult(
        basis="Ford Global 8D / AIAG CQI-20",
        valid=True,
        verdict="WARNING",
        problem_statement="Bore undersized with Housing 44821",
        findings=[],
        is_is_not=None,
        five_w_two_h=None,
        recommendations=[],
    )
    assert result.to_dict()["is_is_not"] is None
    assert result.to_dict()["five_w_two_h"] is None


def test_d2_clean_input_accepts_with_no_findings() -> None:
    """Assert a fully described D2 with complete Is/Is-Not scoping ACCEPTs with zero findings."""
    result = validate_d2_problem_description(_d2(), is_is_not=_full_is_is_not_rows())
    assert result.verdict == "ACCEPT"
    assert result.valid is True
    assert result.findings == []
    assert result.basis == "Ford Global 8D / AIAG CQI-20"
    assert result.problem_statement == "Bore diameter undersized with Housing P/N 44821"
    assert result.is_is_not is not None
    assert result.is_is_not["verdict"] == "ACCEPT"


def test_d2_composed_problem_statement_overrides_the_matrix_statement() -> None:
    """Assert the composed statement always wins over an IsIsNotMatrix's own statement."""
    matrix = IsIsNotMatrix(
        problem_statement="A stale statement carried on the matrix",
        rows=_full_is_is_not_rows(),
    )
    result = validate_d2_problem_description(_d2(), is_is_not=matrix)
    assert result.problem_statement == "Bore diameter undersized with Housing P/N 44821"
    assert result.is_is_not is not None
    assert result.is_is_not["problem_statement"] == "Bore diameter undersized with Housing P/N 44821"


def test_d2_degenerate_problem_statement_warns() -> None:
    """Assert identical defect/object text warns, case- and whitespace-insensitively."""
    result = validate_d2_problem_description(
        _d2(what_is_wrong="Bore undersized", with_what="  BORE UNDERSIZED  "),
        is_is_not=_full_is_is_not_rows(),
    )
    assert result.verdict == "WARNING"
    assert result.valid is True
    assert _codes(result) == ["DEGENERATE_PROBLEM_STATEMENT"]
    assert _severities(result) == ["warning"]


@pytest.mark.parametrize(
    ("what_is_wrong", "with_what"),
    [
        ("Bore undersized", "Bore housing 44821"),
        ("Undersized bore", "Bore undersized housing"),
        ("Leak", "Leaking pump body"),
    ],
    ids=["distinct", "overlapping-words", "substring"],
)
def test_d2_distinct_statement_fields_do_not_warn(what_is_wrong: str, with_what: str) -> None:
    """Negative control: only exact (normalised) equality trips the degenerate-statement check."""
    result = validate_d2_problem_description(
        _d2(what_is_wrong=what_is_wrong, with_what=with_what),
        is_is_not=_full_is_is_not_rows(),
    )
    assert "DEGENERATE_PROBLEM_STATEMENT" not in _codes(result)
    assert result.verdict == "ACCEPT"


@pytest.mark.parametrize(
    "quantification",
    ["several units", "a majority of parts", "many", "most of the lot"],
    ids=["several", "majority", "many", "most"],
)
def test_d2_non_numeric_quantification_warns(quantification: str) -> None:
    """Assert a quantification with no digit anywhere is flagged as a warning."""
    result = validate_d2_problem_description(
        _d2(quantification=quantification), is_is_not=_full_is_is_not_rows()
    )
    assert result.verdict == "WARNING"
    assert _codes(result) == ["QUANTIFICATION_NOT_NUMERIC"]
    assert _severities(result) == ["warning"]


@pytest.mark.parametrize(
    "quantification",
    ["14 of 500 parts", "14ppm", "3 per shift", "0.8 mm oversize"],
    ids=["ratio", "embedded-digit", "rate", "decimal"],
)
def test_d2_numeric_quantification_does_not_warn(quantification: str) -> None:
    """Negative control: any digit character anywhere satisfies the digit check."""
    result = validate_d2_problem_description(
        _d2(quantification=quantification), is_is_not=_full_is_is_not_rows()
    )
    assert "QUANTIFICATION_NOT_NUMERIC" not in _codes(result)
    assert result.verdict == "ACCEPT"


def test_d2_declared_5w2h_with_no_answers_is_rejected() -> None:
    """Assert a bare method_used='5W2H' declaration REJECTs, naming all seven questions."""
    result = validate_d2_problem_description(
        _d2(method_used="5W2H"), is_is_not=_full_is_is_not_rows()
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["METHOD_5W2H_DESCRIPTION_INCOMPLETE"]
    assert _severities(result) == ["error"]
    assert result.five_w_two_h == {
        "answered": [],
        "missing": [question for question, _ in FIGURE_12_QUESTIONS],
        "complete": False,
    }
    for question, _ in FIGURE_12_QUESTIONS:
        assert question in result.findings[0].message


@pytest.mark.parametrize(
    ("question", "field"),
    FIGURE_12_QUESTIONS,
    ids=[field for _, field in FIGURE_12_QUESTIONS],
)
def test_d2_declared_5w2h_missing_one_question_is_rejected(question: str, field: str) -> None:
    """Assert dropping any single Figure 12 answer flags that question as an error."""
    answers = _full_w2h()
    del answers[field]
    result = validate_d2_problem_description(
        _d2(method_used="5W2H", **answers), is_is_not=_full_is_is_not_rows()
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["METHOD_5W2H_DESCRIPTION_INCOMPLETE"]
    assert _severities(result) == ["error"]
    assert result.five_w_two_h is not None
    assert result.five_w_two_h["missing"] == [question]
    assert result.five_w_two_h["complete"] is False
    assert question in result.findings[0].message


@pytest.mark.parametrize(
    ("blank", "label"),
    [("", "empty"), ("   ", "whitespace")],
    ids=["empty", "whitespace"],
)
def test_d2_blank_5w2h_answer_counts_as_unanswered(blank: str, label: str) -> None:
    """Assert a blank answer is normalised to None by the schema and flagged as missing."""
    answers = _full_w2h()
    answers["w2h_where"] = blank
    discipline = _d2(method_used="5W2H", **answers)
    assert discipline.w2h_where is None, label
    result = validate_d2_problem_description(discipline, is_is_not=_full_is_is_not_rows())
    assert result.verdict == "REJECT"
    assert _codes(result) == ["METHOD_5W2H_DESCRIPTION_INCOMPLETE"]
    assert _severities(result) == ["error"]
    assert result.five_w_two_h is not None
    assert result.five_w_two_h["missing"] == ["Where?"]


def test_d2_complete_5w2h_accepts_with_structured_evidence() -> None:
    """Assert all seven Figure 12 answers present ACCEPTs and records complete evidence."""
    result = validate_d2_problem_description(
        _d2(method_used="5W2H", **_full_w2h()), is_is_not=_full_is_is_not_rows()
    )
    assert result.verdict == "ACCEPT"
    assert result.valid is True
    assert result.findings == []
    assert result.five_w_two_h == {
        "answered": [question for question, _ in FIGURE_12_QUESTIONS],
        "missing": [],
        "complete": True,
    }


@pytest.mark.parametrize(
    "method_used",
    [None, "GANTT", "IS_IS_NOT", "OTHER"],
    ids=["none", "gantt", "is-is-not", "other"],
)
def test_d2_undeclared_5w2h_is_never_judged(method_used: str | None) -> None:
    """Negative control: with no 5W2H claim, unanswered questions are not a finding at all."""
    result = validate_d2_problem_description(
        _d2(method_used=method_used), is_is_not=_full_is_is_not_rows()
    )
    assert "METHOD_5W2H_DESCRIPTION_INCOMPLETE" not in _codes(result)
    assert result.five_w_two_h is None
    assert result.verdict == "ACCEPT"


@pytest.mark.parametrize(
    "method_used",
    [None, "GANTT", "IS_IS_NOT", "OTHER"],
    ids=["none", "gantt", "is-is-not", "other"],
)
def test_d2_answers_without_a_5w2h_claim_record_no_evidence(method_used: str | None) -> None:
    """Negative control: answering all seven without claiming 5W2H still records no judgment."""
    result = validate_d2_problem_description(
        _d2(method_used=method_used, **_full_w2h()), is_is_not=_full_is_is_not_rows()
    )
    assert result.five_w_two_h is None
    assert result.findings == []
    assert result.verdict == "ACCEPT"


def test_d2_five_w_two_h_model_is_cqi20_figure_12_not_five_why_two_how() -> None:
    """Citation control: the engine's 5W2H questions are Figure 12's, quoted in CITATIONS.tsv.

    This test replaces an inverted one. The earlier version asserted that the D2 engine's 5W2H
    note carried the expansion "5 Why - 2 How" and that the What/Where/When/Who/Why/How question
    set must never be implemented — a reading taken from a CQI-20 aside inside a note on supplier
    SCARs. CQI-20 Figure 12, "Problem Identification Questions", enumerates and defines seven
    questions, so the old assertion defended an error and would have blocked the correct model.
    It now guards the opposite: every question the engine checks must be quoted verbatim from
    Figure 12 in the RULE-8D-D2-003 manifest rows, and the engine must not restate the
    SCAR-note expansion as its definition of 5W2H.
    """
    manifest = Path(__file__).resolve().parents[1] / "src" / "quality_core" / "rca"
    figure_12_quotes = [
        row.split("\t")[2]
        for row in manifest.joinpath("CITATIONS.tsv").read_text(encoding="utf-8").splitlines()
        if row.startswith("RULE-8D-D2-003\t")
    ]
    assert len(figure_12_quotes) == 8, "expected the Figure 12 caption plus seven question rows"

    engine_questions = [question for question, _ in _five_w_two_h_answers(_d2())]
    assert engine_questions == [question for question, _ in FIGURE_12_QUESTIONS]
    for question in engine_questions:
        assert any(question in quote for quote in figure_12_quotes), (
            f"engine 5W2H question {question!r} is not quoted in any RULE-8D-D2-003 row"
        )

    result = validate_d2_problem_description(_d2(method_used="5W2H"))
    incomplete = next(
        f for f in result.findings if f.code == "METHOD_5W2H_DESCRIPTION_INCOMPLETE"
    )
    assert "5 Why" not in incomplete.message
    assert "RULE-8D-D2-003" in incomplete.message


def test_d2_absent_scoping_warns_and_never_calls_the_scoping_engine() -> None:
    """Assert is_is_not=None warns, leaves the payload None, and does not raise TypeError."""
    result = validate_d2_problem_description(_d2())
    assert result.verdict == "WARNING"
    assert result.valid is True
    assert _codes(result) == ["IS_IS_NOT_NOT_PROVIDED"]
    assert _severities(result) == ["warning"]
    assert result.is_is_not is None
    assert result.recommendations == [result.findings[0].recommendation]


@pytest.mark.parametrize(
    "empty",
    [[], {"rows": []}, pd.DataFrame(columns=["dimension", "is_data", "is_not_data"])],
    ids=["empty-list", "empty-rows-dict", "empty-dataframe"],
)
def test_d2_empty_scoping_data_is_rejected_by_delegation(empty: object) -> None:
    """Assert explicitly-supplied-but-empty scoping data REJECTs, unlike an absent one."""
    result = validate_d2_problem_description(_d2(), is_is_not=empty)
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["IS_IS_NOT_SCOPING_REJECTED"]
    assert _severities(result) == ["error"]
    assert result.is_is_not is not None
    assert result.is_is_not["verdict"] == "REJECT"


def test_d2_incomplete_scoping_warns() -> None:
    """Assert an Is/Is-Not matrix missing KT dimensions surfaces the incomplete-scoping warning."""
    result = validate_d2_problem_description(_d2(), is_is_not=_full_is_is_not_rows()[:1])
    assert result.verdict == "WARNING"
    assert result.valid is True
    assert _codes(result) == ["IS_IS_NOT_SCOPING_INCOMPLETE"]
    assert _severities(result) == ["warning"]
    assert result.is_is_not is not None
    assert result.is_is_not["missing_dimensions"] == ["WHERE", "WHEN", "EXTENT"]
    assert "WHERE, WHEN, EXTENT" in result.findings[0].message


def test_d2_error_outranks_warning() -> None:
    """Assert a rejected scoping outranks concurrent warnings — overall verdict REJECT."""
    result = validate_d2_problem_description(
        _d2(what_is_wrong="Bore undersized", with_what="bore undersized"), is_is_not=[]
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == ["DEGENERATE_PROBLEM_STATEMENT", "IS_IS_NOT_SCOPING_REJECTED"]
    assert _severities(result) == ["warning", "error"]


def test_d2_two_concurrent_warnings_do_not_escalate() -> None:
    """Assert several warning findings still resolve to WARNING, never REJECT."""
    result = validate_d2_problem_description(
        _d2(
            what_is_wrong="Bore undersized",
            with_what="Bore Undersized",
            quantification="several units",
        )
    )
    assert result.verdict == "WARNING"
    assert result.valid is True
    assert _codes(result) == [
        "DEGENERATE_PROBLEM_STATEMENT",
        "QUANTIFICATION_NOT_NUMERIC",
        "IS_IS_NOT_NOT_PROVIDED",
    ]
    assert _severities(result) == ["warning", "warning", "warning"]


def test_d2_incomplete_5w2h_outranks_concurrent_warnings() -> None:
    """Assert an incomplete declared 5W2H REJECTs even alongside warning-tier findings."""
    result = validate_d2_problem_description(
        _d2(method_used="5W2H", quantification="several units")
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert _codes(result) == [
        "QUANTIFICATION_NOT_NUMERIC",
        "METHOD_5W2H_DESCRIPTION_INCOMPLETE",
        "IS_IS_NOT_NOT_PROVIDED",
    ]
    assert _severities(result) == ["warning", "error", "warning"]


def test_d2_recommendations_are_deduplicated_across_finding_and_scoping() -> None:
    """Assert the scoping recommendation reused as a finding recommendation appears once."""
    rows = _partial_is_is_not_rows()
    result = validate_d2_problem_description(_d2(), is_is_not=rows)
    scoping = scope_is_is_not(rows, problem_statement=result.problem_statement)
    assert result.findings[0].recommendation == scoping.recommendations[0]
    assert result.recommendations.count(scoping.recommendations[0]) == 1
    assert result.recommendations == _dedupe(
        [result.findings[0].recommendation] + scoping.recommendations
    )
    assert result.recommendations == scoping.recommendations
    assert len(scoping.recommendations) > 1
    assert len(result.recommendations) == len(set(result.recommendations))


@pytest.mark.parametrize("bad", [5, 4.2, True, "a string"], ids=["int", "float", "bool", "str"])
def test_d2_propagates_type_error_from_the_scoping_engine(bad: object) -> None:
    """Negative control: the D2 engine must NOT swallow scope_is_is_not's TypeError."""
    with pytest.raises(TypeError):
        validate_d2_problem_description(_d2(), is_is_not=bad)


def test_d2_propagates_validation_error_from_the_scoping_engine() -> None:
    """Negative control: the D2 engine must NOT swallow pydantic's ValidationError."""
    with pytest.raises(pydantic.ValidationError):
        validate_d2_problem_description(
            _d2(),
            is_is_not=[
                {"dimension": "NOT_A_KT_DIMENSION", "is_data": "x", "is_not_data": "y"}
            ],
        )


# ==============================================================================
# 5b. Cross-module drift guard — scope_is_is_not's warning/recommendation pairing
#
# validate_d2_problem_description reads scoping.recommendations[0] with no fallback,
# on the strength of an inline comment asserting scope_is_is_not always pairs every
# warning it raises with a recommendation (so a non-ACCEPT verdict always carries at
# least one recommendation). That is a claim about ANOTHER module's undocumented
# invariant — the one place D2 depends on is_is_not.py behaviour rather than its own.
# If a future warning path is ever added to is_is_not.py without a paired recommendation,
# D2 raises IndexError at runtime and nothing in either module's own tests would catch
# it. This guard pins the invariant directly: every scope_is_is_not result that carries
# warnings must carry at least one recommendation. It exercises each warning-producing
# path in is_is_not.py so that dropping any paired recommendation.append fails here.
# Same posture as test_five_why_verdict_stays_in_sync_with_five_why_module (#204).
# ==============================================================================


def _warning_path_inputs() -> dict[str, list[dict[str, str]]]:
    """One input per warning-emitting path in scope_is_is_not, keyed by the path it hits."""
    return {
        # Empty data short-circuits to REJECT with a warning + recommendation (is_is_not.py:168-183).
        "empty-data-reject": [],
        # A dimension with distinctions but no changes (is_is_not.py:230/233).
        "distinction-without-change": [
            {"dimension": "WHAT", "is_data": "x", "is_not_data": "y", "distinctions": "d"}
        ],
        # A dimension with changes but no distinctions (is_is_not.py:250/253).
        "change-without-distinction": [
            {"dimension": "WHAT", "is_data": "x", "is_not_data": "y", "changes": "c"}
        ],
        # A dimension with IS/IS-NOT data but neither distinctions nor changes (is_is_not.py:257/260).
        "neither-distinction-nor-change": [
            {"dimension": "WHAT", "is_data": "x", "is_not_data": "y"}
        ],
        # A fully paired single row leaves 3 dimensions missing (is_is_not.py:265/269).
        "missing-dimensions": [
            {
                "dimension": "WHAT",
                "is_data": "x",
                "is_not_data": "y",
                "distinctions": "d",
                "changes": "c",
            }
        ],
    }


@pytest.mark.parametrize("path", list(_warning_path_inputs()))
def test_scope_is_is_not_pairs_every_warning_with_a_recommendation(path: str) -> None:
    """DRIFT GUARD: D2 relies on scope_is_is_not never raising a warning without a recommendation.

    D2's validate_d2_problem_description indexes scoping.recommendations[0] with no fallback.
    If any warning path in is_is_not.py ever loses its paired recommendation, D2 IndexErrors at
    runtime. This exercises every warning path and pins warnings -> recommendations non-empty.
    """
    data = _warning_path_inputs()[path]
    scoping = scope_is_is_not(data, problem_statement="drift guard")
    assert scoping.warnings, f"expected the {path} input to raise a warning"
    # The exact property D2 depends on: a non-empty warnings list guarantees recommendations[0].
    assert scoping.recommendations, (
        f"scope_is_is_not raised warnings on {path} but produced no recommendation; "
        "validate_d2_problem_description's scoping.recommendations[0] would IndexError"
    )
    assert scoping.recommendations[0]


def test_d2_scoping_reject_indexes_the_first_recommendation_without_fallback() -> None:
    """Directly exercise the no-fallback recommendations[0] read in the D2 REJECT branch."""
    result = validate_d2_problem_description(_d2(), is_is_not=[])
    assert result.verdict == "REJECT"
    assert result.findings[0].recommendation
    assert (
        result.findings[0].recommendation
        == scope_is_is_not([], problem_statement=result.problem_statement).recommendations[0]
    )


# ==============================================================================
# 6. Package re-export
# ==============================================================================


def test_engine_symbols_are_re_exported_from_quality_core_rca() -> None:
    """Assert the D0/D1/D2/D4 engine surface is importable from quality_core.rca."""
    import quality_core.rca as rca

    assert rca.validate_d0_readiness is validate_d0_readiness
    assert rca.validate_d1_team is validate_d1_team
    assert rca.D0Finding is D0Finding
    assert rca.D0ValidationResult is D0ValidationResult
    assert rca.D1Finding is D1Finding
    assert rca.D1ValidationResult is D1ValidationResult
    assert rca.D2Finding is D2Finding
    assert rca.D2ValidationResult is D2ValidationResult
    assert rca.validate_d2_problem_description is validate_d2_problem_description
    assert rca.validate_d4_root_cause is validate_d4_root_cause
    assert rca.D4Finding is D4Finding
    assert rca.D4ValidationResult is D4ValidationResult
    for name in (
        "D0Finding",
        "D0ValidationResult",
        "D1Finding",
        "D1ValidationResult",
        "D2Finding",
        "D2ValidationResult",
        "validate_d0_readiness",
        "validate_d1_team",
        "validate_d2_problem_description",
        "D4Finding",
        "D4ValidationResult",
        "validate_d4_root_cause",
    ):
        assert name in rca.__all__


# ==============================================================================
# 7. D3 — Interim containment + NCR linkage
# ==============================================================================


def _containment_action(
    *,
    description: str = "Quarantine suspect WIP",
    implemented_date: datetime.date = IMPLEMENTED,
    is_effective: bool | None = True,
) -> ContainmentAction:
    """Build a ContainmentAction. is_effective=None means no verification record at all."""
    verification = (
        None if is_effective is None else _verification(is_effective=is_effective)
    )
    return ContainmentAction(
        description=description,
        implemented_date=implemented_date,
        verification=verification,
    )


def _d3(
    *,
    actions: list[ContainmentAction] | None = None,
    recorded_ncr: LinkedNCRValidation | None = None,
) -> D3Discipline:
    """Build a D3Discipline; defaults to a single verified-effective action, no recorded NCR."""
    return D3Discipline(
        actions=actions or [_containment_action()], linked_ncr_validation=recorded_ncr
    )


def _ncr_row(**over: object) -> dict[str, object]:
    """A single structurally valid Nonconformance Record row."""
    row: dict[str, object] = {
        "part_lot_id": "LOT-44821-A",
        "defect_description": "Bore diameter undersized",
        "requirement_violated": "Drawing 44821 rev C, bore 12.00 +0.02/-0.00",
        "quantity_affected": 14,
        "detection_point": "Final inspection",
    }
    row.update(over)
    return row


def _d3_codes(result: D3ValidationResult) -> list[str]:
    """Finding codes of a D3 result, in order."""
    return [f.code for f in result.findings]


def _finding(result: D3ValidationResult, code: str) -> D3Finding:
    """Return the single finding with the given code (fails if absent/duplicated)."""
    matches = [f for f in result.findings if f.code == code]
    assert len(matches) == 1, f"expected exactly one {code}, got {[f.code for f in result.findings]}"
    return matches[0]


# ---- 7.1 Serialization round-trips --------------------------------------------------


def test_d3_finding_to_dict_shape_with_action_description() -> None:
    """D3Finding.to_dict returns every field including a populated action_description."""
    finding = D3Finding(
        code="CONTAINMENT_ACTION_NOT_VERIFIED",
        severity="error",
        action_description="Quarantine suspect WIP",
        message="msg",
        recommendation="rec",
    )
    assert finding.to_dict() == {
        "code": "CONTAINMENT_ACTION_NOT_VERIFIED",
        "severity": "error",
        "action_description": "Quarantine suspect WIP",
        "message": "msg",
        "recommendation": "rec",
    }


def test_d3_finding_to_dict_shape_with_none_action_description() -> None:
    """D3Finding.to_dict keeps action_description=None for report-level / NCR findings."""
    finding = D3Finding(
        code="LINKED_NCR_NOT_PROVIDED",
        severity="warning",
        action_description=None,
        message="msg",
        recommendation="rec",
    )
    assert finding.to_dict()["action_description"] is None


def test_d3_validation_result_to_dict_nests_findings() -> None:
    """D3ValidationResult.to_dict recurses into child finding dicts and copies lists."""
    finding = D3Finding(
        code="LINKED_NCR_INVALID",
        severity="error",
        action_description=None,
        message="msg",
        recommendation="rec",
    )
    result = D3ValidationResult(
        basis="Ford Global 8D / AIAG CQI-20",
        valid=False,
        verdict="REJECT",
        containment_verified=True,
        action_count=1,
        linked_ncr=None,
        linked_ncr_validation=LinkedNCRValidation(is_valid=False, findings=["bad row"]),
        findings=[finding],
        recommendations=["rec"],
    )
    payload = result.to_dict()
    assert payload == {
        "basis": "Ford Global 8D / AIAG CQI-20",
        "valid": False,
        "verdict": "REJECT",
        "containment_verified": True,
        "action_count": 1,
        "linked_ncr": None,
        "linked_ncr_validation": {
            "is_valid": False,
            "record_count": 0,
            "findings": ["bad row"],
        },
        "findings": [finding.to_dict()],
        "recommendations": ["rec"],
    }
    assert isinstance(payload["findings"][0], dict)
    assert payload["recommendations"] is not result.recommendations


def test_d3_validation_result_to_dict_keeps_an_absent_ncr_outcome_none() -> None:
    """No recorded outcome serializes as None rather than an empty object."""
    result = D3ValidationResult(
        basis="Ford Global 8D / AIAG CQI-20",
        valid=True,
        verdict="WARNING",
        containment_verified=True,
        action_count=1,
        linked_ncr=None,
        linked_ncr_validation=None,
        findings=[],
        recommendations=[],
    )
    assert result.to_dict()["linked_ncr_validation"] is None


# ---- 7.2 Positive controls (one per reachable branch) -------------------------------


def test_d3_all_verified_no_ncr_is_warning() -> None:
    """All actions verified effective + linked_ncr=None -> WARNING, LINKED_NCR_NOT_PROVIDED."""
    result = validate_d3_containment(_d3(), linked_ncr=None)
    assert result.verdict == "WARNING"
    assert result.valid is True
    assert result.containment_verified is True
    assert result.action_count == 1
    assert result.linked_ncr is None
    assert _d3_codes(result) == ["LINKED_NCR_NOT_PROVIDED"]
    finding = _finding(result, "LINKED_NCR_NOT_PROVIDED")
    assert finding.severity == "warning"
    assert finding.action_description is None


def test_d3_all_verified_valid_ncr_is_accept() -> None:
    """All actions verified effective + valid linked_ncr -> ACCEPT, D3_READY + LINKED_NCR_VALID."""
    result = validate_d3_containment(_d3(), linked_ncr=[_ncr_row()])
    assert result.verdict == "ACCEPT"
    assert result.valid is True
    assert result.containment_verified is True
    assert _d3_codes(result) == ["LINKED_NCR_VALID", "D3_READY"]
    assert _finding(result, "LINKED_NCR_VALID").severity == "info"
    assert _finding(result, "D3_READY").severity == "info"
    # Payload populated from the validated dataset, not None.
    assert result.linked_ncr is not None
    assert len(result.linked_ncr["records"]) == 1
    assert result.linked_ncr["records"][0]["part_lot_id"] == "LOT-44821-A"


def test_d3_action_without_verification_is_reject() -> None:
    """One action with verification=None -> REJECT, CONTAINMENT_ACTION_NOT_VERIFIED/error."""
    result = validate_d3_containment(
        _d3(actions=[_containment_action(is_effective=None)]), linked_ncr=[_ncr_row()]
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert result.containment_verified is False
    finding = _finding(result, "CONTAINMENT_ACTION_NOT_VERIFIED")
    assert finding.severity == "error"
    assert finding.action_description == "Quarantine suspect WIP"
    assert "no effectiveness verification" in finding.message


def test_d3_action_verified_ineffective_is_reject() -> None:
    """One action verified but is_effective=False -> REJECT, CONTAINMENT_ACTION_VERIFIED_INEFFECTIVE."""
    result = validate_d3_containment(
        _d3(actions=[_containment_action(is_effective=False)]), linked_ncr=[_ncr_row()]
    )
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert result.containment_verified is False
    finding = _finding(result, "CONTAINMENT_ACTION_VERIFIED_INEFFECTIVE")
    assert finding.severity == "error"
    assert finding.action_description == "Quarantine suspect WIP"
    # The message must name the verifier from the *present* verification record.
    assert "Q. Inspector" in finding.message
    assert "not effective" in finding.message


def test_d3_mixed_actions_one_finding_per_problem_action() -> None:
    """Several actions, mixed states -> one finding per problem action, each with its own description."""
    actions = [
        _containment_action(description="Quarantine", is_effective=None),
        _containment_action(description="Rework", is_effective=False),
        _containment_action(description="100% sort", is_effective=True),
    ]
    result = validate_d3_containment(_d3(actions=actions), linked_ncr=[_ncr_row()])
    assert result.verdict == "REJECT"
    assert result.containment_verified is False
    assert result.action_count == 3
    not_verified = _finding(result, "CONTAINMENT_ACTION_NOT_VERIFIED")
    ineffective = _finding(result, "CONTAINMENT_ACTION_VERIFIED_INEFFECTIVE")
    assert not_verified.action_description == "Quarantine"
    assert ineffective.action_description == "Rework"
    # The verified-effective "100% sort" action raises no per-action finding.
    assert all(
        f.action_description != "100% sort" for f in result.findings
    )


def test_d3_single_verified_action_valid_ncr_is_accept() -> None:
    """Edge: exactly one action, verified effective, valid linked_ncr -> ACCEPT (spec §8)."""
    result = validate_d3_containment(
        _d3(actions=[_containment_action()]), linked_ncr=[_ncr_row()]
    )
    assert result.verdict == "ACCEPT"
    assert result.action_count == 1


def test_d3_all_actions_unverified_gives_one_finding_each() -> None:
    """Several unverified actions -> one CONTAINMENT_ACTION_NOT_VERIFIED each, not one aggregate."""
    actions = [
        _containment_action(description="A", is_effective=None),
        _containment_action(description="B", is_effective=None),
    ]
    result = validate_d3_containment(_d3(actions=actions), linked_ncr=[_ncr_row()])
    not_verified = [f for f in result.findings if f.code == "CONTAINMENT_ACTION_NOT_VERIFIED"]
    assert len(not_verified) == 2
    assert {f.action_description for f in not_verified} == {"A", "B"}
    assert all(f.severity == "error" for f in not_verified)


# ---- 7.3 The single-source-of-truth guard (never drifts from the gate predicate) ----


def test_d3_containment_verified_mirrors_discipline_is_verified_when_true() -> None:
    """containment_verified reads discipline.is_verified for a fully-verified fixture."""
    discipline = _d3(actions=[_containment_action(), _containment_action(description="B")])
    result = validate_d3_containment(discipline, linked_ncr=[_ncr_row()])
    assert discipline.is_verified is True
    assert result.containment_verified == discipline.is_verified


def test_d3_containment_verified_mirrors_discipline_is_verified_when_false() -> None:
    """containment_verified reads discipline.is_verified for a not-fully-verified fixture."""
    discipline = _d3(
        actions=[_containment_action(), _containment_action(description="B", is_effective=None)]
    )
    result = validate_d3_containment(discipline, linked_ncr=[_ncr_row()])
    assert discipline.is_verified is False
    assert result.containment_verified == discipline.is_verified


def test_containment_action_is_verified_is_a_computed_property_no_forged_override() -> None:
    """A forged is_verified=True kwarg is silently dropped; the property still reads the record.

    Guards the task's named attack: the engine must never be able to read 'verified' without a
    genuine EffectivenessVerification(is_effective=True). is_verified has no settable backing field.
    """
    forged = ContainmentAction(
        description="Q", implemented_date=IMPLEMENTED, is_verified=True  # type: ignore[call-arg]
    )
    assert forged.verification is None
    assert forged.is_verified is False
    discipline = D3Discipline(actions=[forged], is_verified=True)  # type: ignore[call-arg]
    assert discipline.is_verified is False
    result = validate_d3_containment(discipline, linked_ncr=[_ncr_row()])
    assert result.containment_verified is False
    assert result.verdict == "REJECT"


# ---- 7.4 The mandatory NCR-linkage negative control (#208) ---------------------------


def test_d3_invalid_linked_ncr_rejects_despite_verified_containment() -> None:
    """THE required #208 negative control: verified containment + invalid NCR -> REJECT.

    containment_verified is True on its own, yet the invalid linked NCR independently forces
    REJECT. Asserts code AND severity (E3 shipped a mutable, unasserted severity at 100% branch).
    """
    result = validate_d3_containment(
        _d3(),
        linked_ncr=[_ncr_row(part_lot_id="   ", quantity_affected=0)],
    )
    assert result.containment_verified is True
    assert result.verdict == "REJECT"
    assert result.valid is False
    finding = _finding(result, "LINKED_NCR_INVALID")
    assert finding.severity == "error"
    assert finding.action_description is None
    assert result.linked_ncr is None
    # The sub-engine's own text is surfaced.
    assert "part_lot_id" in finding.message


def test_d3_invalid_ncr_two_violations_both_surface_joined() -> None:
    """Two independent structural violations both surface, joined by '; '."""
    result = validate_d3_containment(
        _d3(), linked_ncr=[_ncr_row(part_lot_id="   ", quantity_affected=0)]
    )
    finding = _finding(result, "LINKED_NCR_INVALID")
    assert "part_lot_id: must not be blank or whitespace-only" in finding.message
    assert "quantity_affected: Input should be greater than or equal to 1" in finding.message
    assert "; " in finding.message


def test_d3_linked_ncr_type_error_branch_rejects() -> None:
    """TypeError from validate_ncr (linked_ncr=42) -> LINKED_NCR_INVALID/error/REJECT."""
    result = validate_d3_containment(_d3(), linked_ncr=42)  # type: ignore[arg-type]
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert result.containment_verified is True
    finding = _finding(result, "LINKED_NCR_INVALID")
    assert finding.severity == "error"
    assert "got int" in finding.message


def test_d3_linked_ncr_empty_list_goes_through_validate_ncr_not_none_branch() -> None:
    """linked_ncr=[] is not None: it reaches validate_ncr and fails there, not LINKED_NCR_NOT_PROVIDED."""
    result = validate_d3_containment(_d3(), linked_ncr=[])
    assert result.verdict == "REJECT"
    assert result.valid is False
    codes = _d3_codes(result)
    assert "LINKED_NCR_INVALID" in codes
    assert "LINKED_NCR_NOT_PROVIDED" not in codes
    finding = _finding(result, "LINKED_NCR_INVALID")
    assert finding.severity == "error"
    assert "at least one record" in finding.message


def test_d3_linked_ncr_bare_value_error_branch_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare (non-pydantic) ValueError from validate_ncr hits the ValueError arm of the catch tuple.

    validate_ncr does not raise a plain ValueError in practice, so the ValueError member of
    (pydantic.ValidationError, TypeError, ValueError) is only proven load-bearing by injecting one.
    It must still produce LINKED_NCR_INVALID/error/REJECT and surface str(exc) via the non-pydantic
    branch of _ncr_linkage_findings.
    """
    import quality_core.rca.eight_d_disciplines as engine

    def _boom(_data: object) -> NCRDataset:
        raise ValueError("bespoke dataset failure")

    monkeypatch.setattr(engine, "validate_ncr", _boom)
    result = validate_d3_containment(_d3(), linked_ncr=[_ncr_row()])
    assert result.verdict == "REJECT"
    assert result.valid is False
    finding = _finding(result, "LINKED_NCR_INVALID")
    assert finding.severity == "error"
    assert "bespoke dataset failure" in finding.message


# ---- 7.4a The recorded outcome carried to the gate (#208) ---------------------------


def test_d3_valid_linked_ncr_emits_a_recorded_outcome_for_the_report() -> None:
    """The engine returns the LinkedNCRValidation a caller stores on D3Discipline."""
    result = validate_d3_containment(_d3(), linked_ncr=[_ncr_row(), _ncr_row(record_id="R2")])
    recorded = result.linked_ncr_validation
    assert recorded is not None
    assert recorded.is_valid is True
    assert recorded.record_count == 2
    assert recorded.findings == []


def test_d3_invalid_linked_ncr_emits_a_recorded_outcome_carrying_the_findings() -> None:
    """A rejected outcome carries validate_ncr's own message text into the recorded artifact."""
    result = validate_d3_containment(_d3(), linked_ncr=[_ncr_row(part_lot_id="   ")])
    recorded = result.linked_ncr_validation
    assert recorded is not None
    assert recorded.is_valid is False
    assert recorded.record_count == 0
    assert "part_lot_id: must not be blank or whitespace-only" in recorded.findings


def test_d3_no_evidence_and_no_record_emits_no_outcome() -> None:
    """Nothing supplied and nothing recorded: there is no outcome to carry to the report."""
    result = validate_d3_containment(_d3(), linked_ncr=None)
    assert result.linked_ncr_validation is None


def test_d3_reports_a_recorded_invalid_outcome_when_no_evidence_is_supplied() -> None:
    """A D3 record the gate would block must not read as merely a WARNING here.

    The engine reads discipline.linked_ncr_validation through the same shared evaluator the gate
    uses, so an advisory run over a report carrying a rejected outcome REJECTs rather than
    reporting LINKED_NCR_NOT_PROVIDED.
    """
    recorded = LinkedNCRValidation(is_valid=False, findings=["quantity_affected: too small"])
    result = validate_d3_containment(_d3(recorded_ncr=recorded), linked_ncr=None)
    assert result.verdict == "REJECT"
    assert result.valid is False
    assert result.containment_verified is True
    finding = _finding(result, "LINKED_NCR_INVALID")
    assert finding.severity == "error"
    assert "quantity_affected: too small" in finding.message
    assert "LINKED_NCR_NOT_PROVIDED" not in _d3_codes(result)
    assert result.linked_ncr_validation == recorded


def test_d3_reports_a_recorded_valid_outcome_when_no_evidence_is_supplied() -> None:
    """A recorded pass is reported as LINKED_NCR_VALID, with the recorded record count."""
    recorded = LinkedNCRValidation(is_valid=True, record_count=4)
    result = validate_d3_containment(_d3(recorded_ncr=recorded), linked_ncr=None)
    assert result.verdict == "ACCEPT"
    finding = _finding(result, "LINKED_NCR_VALID")
    assert finding.severity == "info"
    assert "(4 record(s))" in finding.message
    # No live dataset was validated on this call, so there is no payload to publish.
    assert result.linked_ncr is None


def test_d3_supplied_evidence_supersedes_a_recorded_outcome() -> None:
    """Live evidence is authoritative for this call: a stale rejection does not survive it."""
    stale = LinkedNCRValidation(is_valid=False, findings=["stale rejection"])
    result = validate_d3_containment(_d3(recorded_ncr=stale), linked_ncr=[_ncr_row()])
    assert result.verdict == "ACCEPT"
    assert result.linked_ncr_validation is not None
    assert result.linked_ncr_validation.is_valid is True
    assert "stale rejection" not in " ".join(f.message for f in result.findings)


# ---- 7.5 Union-shape pass-through to validate_ncr ------------------------------------


def test_d3_linked_ncr_accepts_ncrdataset_instance() -> None:
    """An NCRDataset instance passes straight through to validate_ncr and is accepted."""
    dataset = NCRDataset(records=[_ncr_row()])  # type: ignore[list-item]
    result = validate_d3_containment(_d3(), linked_ncr=dataset)
    assert result.verdict == "ACCEPT"
    assert _finding(result, "LINKED_NCR_VALID").severity == "info"


def test_d3_linked_ncr_accepts_dataframe_with_nan_cells() -> None:
    """A DataFrame (with a NaN optional cell) passes through; validate_ncr normalizes NaN->None."""
    frame = pd.DataFrame([{**_ncr_row(), "record_id": float("nan")}])
    result = validate_d3_containment(_d3(), linked_ncr=frame)
    assert result.verdict == "ACCEPT"
    assert result.linked_ncr is not None
    assert result.linked_ncr["records"][0]["record_id"] is None


def test_d3_linked_ncr_accepts_list_of_dicts() -> None:
    """A list[dict] passes through to validate_ncr."""
    result = validate_d3_containment(_d3(), linked_ncr=[_ncr_row(), _ncr_row(record_id="R2")])
    assert result.verdict == "ACCEPT"
    assert result.linked_ncr is not None
    assert len(result.linked_ncr["records"]) == 2


def test_d3_linked_ncr_accepts_bare_dict() -> None:
    """A bare dict (single-record 'rows'/'records' payload) passes through to validate_ncr."""
    result = validate_d3_containment(_d3(), linked_ncr={"records": [_ncr_row()]})
    assert result.verdict == "ACCEPT"
    assert result.linked_ncr is not None
    assert len(result.linked_ncr["records"]) == 1


# ---- 7.6 _ncr_linkage_findings unit cases -------------------------------------------


def test_ncr_linkage_findings_pydantic_error_uses_location_message_format() -> None:
    """pydantic.ValidationError -> '{location}: {message}', with the 'Value error, ' prefix stripped."""
    with pytest.raises(pydantic.ValidationError) as excinfo:
        validate_ncr([_ncr_row(part_lot_id="   ")])
    messages = _ncr_linkage_findings(excinfo.value)
    assert "part_lot_id: must not be blank or whitespace-only" in messages
    # The pydantic 'Value error, ' prefix must not leak through.
    assert all(not m.startswith("Value error,") for m in messages)


def test_ncr_linkage_findings_empty_location_yields_bare_message() -> None:
    """A root-level (empty loc) error yields the message alone, with no leading ': '."""
    with pytest.raises(pydantic.ValidationError) as excinfo:
        validate_ncr([])
    messages = _ncr_linkage_findings(excinfo.value)
    assert messages == ("NCRDataset must contain at least one record",)


def test_ncr_linkage_findings_non_pydantic_exception_returns_str() -> None:
    """A non-pydantic exception falls back to (str(exc),)."""
    assert _ncr_linkage_findings(TypeError("bad type")) == ("bad type",)
    assert _ncr_linkage_findings(ValueError("plain value error")) == ("plain value error",)


# ---- 7.7 Package re-export smoke test ------------------------------------------------


def test_d3_engine_symbols_are_re_exported_from_quality_core_rca() -> None:
    """Assert the D3 engine surface is importable from the quality_core.rca package."""
    import quality_core.rca as rca

    assert rca.D3Finding is D3Finding
    assert rca.D3ValidationResult is D3ValidationResult
    assert rca.validate_d3_containment is validate_d3_containment
    for name in ("D3Finding", "D3ValidationResult", "validate_d3_containment"):
        assert name in rca.__all__
# ==============================================================================
# 8. D4 — root cause and escape point
# ==============================================================================
ROOT_CAUSE = "The engineering work instruction approval process did not require maintenance interval review."
ESCAPE_POINT = "The document control process did not require cross-functional review."

_OCCURRENCE_CHAIN = [
    {"step_number": 1, "why": "Why did the fixture fail?", "because": "The fixture maintenance interval was omitted."},
    {"step_number": 2, "why": "Why was the fixture maintenance interval omitted?", "because": "The maintenance procedure lacked an interval requirement."},
    {"step_number": 3, "why": "Why did the procedure lack an interval requirement?", "because": ROOT_CAUSE},
]
_ESCAPE_CHAIN = [
    {"step_number": 1, "why": "Why did inspection miss the defect?", "because": "The inspection checklist did not include the fixture dimension."},
    {"step_number": 2, "why": "Why did the checklist lack the fixture dimension?", "because": "The quality procedure omitted fixture verification."},
    {"step_number": 3, "why": "Why did the quality procedure omit fixture verification?", "because": ESCAPE_POINT},
]
_WARNING_CHAIN = [
    {"step_number": 1, "why": "Why did the bearing overheat?", "because": "The grease dried up completely."},
    {"step_number": 2, "why": "Why did warehouse inventory mismatch yesterday?", "because": "Barcode scanner battery voltage dropped."},
    {"step_number": 3, "why": "Why did scanner battery drop?", "because": "Charging dock maintenance procedure was missing."},
]
_CIRCULAR_CHAIN = [
    {"step_number": 1, "why": "Why did conveyor stop?", "because": "The drive belt jammed in the pulley."},
    {"step_number": 2, "why": "Why did drive belt jam?", "because": "The motor shaft stopped turning."},
    {"step_number": 3, "why": "Why did motor shaft stop turning?", "because": "The drive belt jammed in the pulley."},
]
_TERMINAL_BLAME_CHAIN = [
    {"step_number": 1, "why": "Why was hole off-center?", "because": "The drill fixture was misaligned."},
    {"step_number": 2, "why": "Why was drill fixture misaligned?", "because": "The operator forgot to tighten clamp bolts."},
]


def _candidate(result: Literal["CONFIRMED", "ELIMINATED"] = "CONFIRMED") -> CandidateCauseTest:
    return CandidateCauseTest(
        description="Fixture maintenance interval missing",
        test_data="Released maintenance schedule has no interval requirement.",
        result=result,
    )


def _d4(
    *,
    candidates: list[CandidateCauseTest] | None = None,
    root_statement: str = ROOT_CAUSE,
    escape_statement: str = ESCAPE_POINT,
    root_leg: Literal["occurrence", "escape", "systemic"] | None = None,
    root_verdict: Literal["ACCEPT", "WARNING", "REJECT"] | None = None,
    escape_leg: Literal["occurrence", "escape", "systemic"] | None = None,
    escape_verdict: Literal["ACCEPT", "WARNING", "REJECT"] | None = None,
) -> D4Discipline:
    return D4Discipline(
        candidate_causes_tested=[_candidate()] if candidates is None else candidates,
        root_cause=RootCauseFinding(
            statement=root_statement,
            verification_evidence="Revision history confirms the missing approval control.",
            five_why_leg_type=root_leg,
            five_why_verdict=root_verdict,
        ),
        escape_point=EscapePointFinding(
            statement=escape_statement,
            verification_evidence="Control-plan revision history confirms the missing review.",
            five_why_leg_type=escape_leg,
            five_why_verdict=escape_verdict,
        ),
    )


def test_d4_finding_and_accepted_result_serialize_without_authoring_a_cause() -> None:
    finding = D4Finding("CODE", "info", None, "msg", "rec")
    assert finding.to_dict() == {
        "code": "CODE", "severity": "info", "leg_type": None,
        "message": "msg", "recommendation": "rec",
    }

    result = validate_d4_root_cause(_d4(candidates=[_candidate(), _candidate("ELIMINATED")]), _OCCURRENCE_CHAIN, _ESCAPE_CHAIN)
    payload = result.to_dict()
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.root_cause_statement == ROOT_CAUSE
    assert result.escape_point_statement == ESCAPE_POINT
    assert result.occurrence_validation.leg_type == "occurrence"
    assert result.escape_validation.leg_type == "escape"
    assert result.candidate_causes_tested == 2
    assert (result.confirmed_candidates, result.eliminated_candidates) == (1, 1)
    assert _codes(result) == ["OCCURRENCE_CHAIN_ACCEPTED", "ESCAPE_CHAIN_ACCEPTED"]
    assert payload["occurrence_validation"]["root_cause"] == ROOT_CAUSE
    assert payload["findings"] == [finding.to_dict() for finding in result.findings]
    assert payload["recommendations"] is not result.recommendations
    assert payload["fishbone_validation"] is None


def test_d4_same_chain_is_validated_independently_for_each_leg() -> None:
    result = validate_d4_root_cause(_d4(), _OCCURRENCE_CHAIN, _OCCURRENCE_CHAIN)
    assert result.occurrence_validation.leg_type == "occurrence"
    assert result.escape_validation.leg_type == "escape"
    assert result.occurrence_validation.root_cause == ROOT_CAUSE
    assert result.escape_validation.root_cause == ESCAPE_POINT


def test_d4_rejects_circular_occurrence_but_retains_accepted_escape_result() -> None:
    result = validate_d4_root_cause(
        _d4(root_statement="The drive belt jammed in the pulley."),
        _CIRCULAR_CHAIN,
        _ESCAPE_CHAIN,
    )
    assert (result.verdict, result.valid) == ("REJECT", False)
    assert result.occurrence_validation.verdict == "REJECT"
    assert result.escape_validation.verdict == "ACCEPT"
    assert _codes(result) == ["OCCURRENCE_CHAIN_REJECTED", "ESCAPE_CHAIN_ACCEPTED"]


def test_d4_rejects_circular_escape_but_retains_accepted_occurrence_result() -> None:
    result = validate_d4_root_cause(
        _d4(escape_statement="The drive belt jammed in the pulley."),
        _OCCURRENCE_CHAIN,
        _CIRCULAR_CHAIN,
    )
    assert (result.verdict, result.valid) == ("REJECT", False)
    assert result.occurrence_validation.verdict == "ACCEPT"
    assert result.escape_validation.verdict == "REJECT"
    assert _codes(result) == ["OCCURRENCE_CHAIN_ACCEPTED", "ESCAPE_CHAIN_REJECTED"]


def test_d4_rejects_terminal_operator_blame_in_occurrence_but_retains_escape() -> None:
    result = validate_d4_root_cause(
        _d4(root_statement="The operator forgot to tighten clamp bolts."),
        _TERMINAL_BLAME_CHAIN,
        _ESCAPE_CHAIN,
    )
    assert (result.verdict, result.valid) == ("REJECT", False)
    assert result.occurrence_validation.verdict == "REJECT"
    assert result.escape_validation.verdict == "ACCEPT"
    assert _codes(result) == ["OCCURRENCE_CHAIN_REJECTED", "ESCAPE_CHAIN_ACCEPTED"]


def test_d4_rejects_terminal_operator_blame_in_escape_but_retains_occurrence() -> None:
    result = validate_d4_root_cause(
        _d4(escape_statement="The operator forgot to tighten clamp bolts."),
        _OCCURRENCE_CHAIN,
        _TERMINAL_BLAME_CHAIN,
    )
    assert (result.verdict, result.valid) == ("REJECT", False)
    assert result.occurrence_validation.verdict == "ACCEPT"
    assert result.escape_validation.verdict == "REJECT"
    assert _codes(result) == ["OCCURRENCE_CHAIN_ACCEPTED", "ESCAPE_CHAIN_REJECTED"]


def test_d4_rejects_chain_terminal_that_disagrees_with_supplied_statement() -> None:
    result = validate_d4_root_cause(_d4(), _TERMINAL_BLAME_CHAIN, _ESCAPE_CHAIN)
    assert (result.verdict, result.valid) == ("REJECT", False)
    assert result.occurrence_validation.root_cause == ROOT_CAUSE
    assert "OCCURRENCE_TERMINAL_CAUSE_MISMATCH" in _codes(result)


def test_d4_propagates_warning_from_both_legs() -> None:
    warning_terminal = "Charging dock maintenance procedure was missing."
    result = validate_d4_root_cause(
        _d4(root_statement=warning_terminal, escape_statement=warning_terminal),
        _WARNING_CHAIN,
        _WARNING_CHAIN,
    )
    assert (result.verdict, result.valid) == ("WARNING", True)
    assert _codes(result) == ["OCCURRENCE_CHAIN_WARNING", "ESCAPE_CHAIN_WARNING"]


def test_d4_empty_candidate_evidence_blocks_an_otherwise_accepted_result() -> None:
    result = validate_d4_root_cause(_d4(candidates=[]), _OCCURRENCE_CHAIN, _ESCAPE_CHAIN)
    assert (result.verdict, result.valid) == ("REJECT", False)
    assert result.candidate_causes_tested == 0
    assert _codes(result)[-1] == "NO_CANDIDATE_CAUSE_TESTS"


def test_d4_reports_stale_leg_and_verdict_metadata_without_bypassing_validation() -> None:
    result = validate_d4_root_cause(
        _d4(root_leg="escape", root_verdict="WARNING", escape_leg="occurrence", escape_verdict="WARNING"),
        _OCCURRENCE_CHAIN,
        _ESCAPE_CHAIN,
    )
    assert (result.verdict, result.valid) == ("WARNING", True)
    assert _codes(result) == [
        "OCCURRENCE_CHAIN_ACCEPTED", "ESCAPE_CHAIN_ACCEPTED",
        "OCCURRENCE_LEG_TYPE_MISMATCH", "OCCURRENCE_VERDICT_MISMATCH",
        "ESCAPE_LEG_TYPE_MISMATCH", "ESCAPE_VERDICT_MISMATCH",
    ]


def test_d4_reports_fishbone_context_without_using_it_as_verdict_authority() -> None:
    result = validate_d4_root_cause(
        _d4(),
        _OCCURRENCE_CHAIN,
        _ESCAPE_CHAIN,
        fishbone_evidence=[{"category": "Machine", "cause": "Fixture wear"}],
    )
    assert result.verdict == "ACCEPT"
    assert result.fishbone_validation is not None
    assert result.fishbone_validation.verdict == "WARNING"


# ==============================================================================
# 7. D5 — Permanent corrective action selection
# ==============================================================================


def _cs(
    result: D5ValidationResult | D6ValidationResult,
) -> list[tuple[str, str]]:
    """Return (code, severity) pairs for every finding, in order.

    Both fields are asserted together everywhere below: the milestone's standing lesson is that a
    silently mutable `severity` survives a code-only assertion even at 100% branch coverage.
    """
    return [(f.code, f.severity) for f in result.findings]


def _pca(
    *,
    action_id: str,
    target: Literal["ROOT_CAUSE", "ESCAPE_POINT"],
    verified: bool = True,
    notes: str | None = "FMEA re-run recorded; no new risk introduced.",
) -> CorrectiveActionCandidate:
    return CorrectiveActionCandidate(
        action_id=action_id,
        target=target,
        description=f"Corrective action for the {target.lower()}",
        selection_criteria="Lowest residual risk, fastest to implement.",
        verified_no_undesirable_effects=verified,
        verification_notes=notes,
    )


def _d5(*candidates: CorrectiveActionCandidate) -> D5Discipline:
    """A D5 record; defaults to one clean candidate per target (the schema minimum)."""
    if not candidates:
        candidates = (
            _pca(action_id="PCA-RC", target="ROOT_CAUSE"),
            _pca(action_id="PCA-EP", target="ESCAPE_POINT"),
        )
    return D5Discipline(candidates=list(candidates))


def _clean_d4() -> D4Discipline:
    """A D4 with a CONFIRMED test and both legs accepted — a traceable D4."""
    return _d4(root_verdict="ACCEPT", escape_verdict="ACCEPT")


def test_d5_finding_and_result_to_dict_round_trip() -> None:
    finding = D5Finding("CODE", "info", "PCA-RC", "msg", "rec")
    assert finding.to_dict() == {
        "code": "CODE", "severity": "info", "action_id": "PCA-RC",
        "message": "msg", "recommendation": "rec",
    }

    result = validate_d5_pca_selection(_d5(), _clean_d4())
    payload = result.to_dict()
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.candidate_count == 2
    assert (result.root_cause_traceable, result.escape_point_traceable) == (True, True)
    assert payload["basis"] == "Ford Global 8D / AIAG CQI-20"
    assert payload["findings"] == [f.to_dict() for f in result.findings]
    assert payload["recommendations"] is not result.recommendations
    assert payload["root_cause_traceable"] is True


def test_d5_clean_pass_emits_only_d5_ready_and_traces_both_targets() -> None:
    result = validate_d5_pca_selection(_d5(), _clean_d4())
    assert _cs(result) == [("D5_READY", "info")]
    assert (result.root_cause_traceable, result.escape_point_traceable) == (True, True)


def test_d5_no_d4_supplied_is_a_warning_and_leaves_traceability_unasked() -> None:
    result = validate_d5_pca_selection(_d5())
    assert _cs(result) == [("D4_NOT_SUPPLIED", "warning")]
    assert (result.verdict, result.valid) == ("WARNING", True)
    # `None` is "not asked", distinct from `False` ("asked, answer is no").
    assert result.root_cause_traceable is None
    assert result.escape_point_traceable is None


def test_d5_unverified_undesirable_effects_is_an_error() -> None:
    d5 = _d5(
        _pca(action_id="PCA-RC", target="ROOT_CAUSE", verified=False),
        _pca(action_id="PCA-EP", target="ESCAPE_POINT"),
    )
    result = validate_d5_pca_selection(d5, _clean_d4())
    assert ("PCA_UNDESIRABLE_EFFECTS_NOT_VERIFIED", "error") in _cs(result)
    assert result.findings[0].action_id == "PCA-RC"
    assert (result.verdict, result.valid) == ("REJECT", False)


def test_d5_verified_but_no_notes_is_a_warning_not_an_error() -> None:
    d5 = _d5(
        _pca(action_id="PCA-RC", target="ROOT_CAUSE", verified=True, notes=None),
        _pca(action_id="PCA-EP", target="ESCAPE_POINT"),
    )
    result = validate_d5_pca_selection(d5, _clean_d4())
    assert ("PCA_VERIFICATION_EVIDENCE_MISSING", "warning") in _cs(result)
    # error must not be raised for a missing-notes-only candidate: the discipline is a WARNING.
    assert (result.verdict, result.valid) == ("WARNING", True)


def test_d5_undesirable_effects_error_suppresses_the_notes_warning_for_same_candidate() -> None:
    """The notes check is an `elif`: an unverified candidate never also raises the notes warning."""
    d5 = _d5(
        _pca(action_id="PCA-RC", target="ROOT_CAUSE", verified=False, notes=None),
        _pca(action_id="PCA-EP", target="ESCAPE_POINT"),
    )
    codes = [c for c, _ in _cs(validate_d5_pca_selection(d5, _clean_d4()))]
    assert "PCA_UNDESIRABLE_EFFECTS_NOT_VERIFIED" in codes
    assert "PCA_VERIFICATION_EVIDENCE_MISSING" not in codes


# ---- D5 traceability: the AC1 negative controls -------------------------------------


def test_d5_root_cause_pca_with_rejected_five_why_is_flagged_and_positive_control_is_not() -> None:
    """AC1: a PCA not traceable to the D4 root cause (verdict REJECT) is flagged `error`.

    The positive control (an accepted verdict) does NOT fire the code, so the test distinguishes
    the two states rather than passing vacuously.
    """
    rejected = validate_d5_pca_selection(
        _d5(), _d4(root_verdict="REJECT", escape_verdict="ACCEPT")
    )
    assert ("PCA_NOT_TRACEABLE_ROOT_CAUSE", "error") in _cs(rejected)
    assert rejected.root_cause_traceable is False
    assert rejected.escape_point_traceable is True
    assert (rejected.verdict, rejected.valid) == ("REJECT", False)

    accepted = validate_d5_pca_selection(_d5(), _clean_d4())
    accepted_codes = [c for c, _ in _cs(accepted)]
    assert "PCA_NOT_TRACEABLE_ROOT_CAUSE" not in accepted_codes
    assert accepted.root_cause_traceable is True


def test_d5_root_cause_pca_without_any_confirmed_test_is_flagged() -> None:
    """AC1: D4 that did no proving work (zero CONFIRMED tests) cannot back a traceable RC PCA.

    Even with an ACCEPT five-why verdict, the absence of a CONFIRMED candidate cause fires the
    error — the `has_confirmed_test=False` branch, reachable only through a ROOT_CAUSE candidate.
    """
    no_confirmed = _d4(
        candidates=[_candidate("ELIMINATED")], root_verdict="ACCEPT", escape_verdict="ACCEPT"
    )
    result = validate_d5_pca_selection(_d5(), no_confirmed)
    assert ("PCA_NOT_TRACEABLE_ROOT_CAUSE", "error") in _cs(result)
    assert result.root_cause_traceable is False
    # The escape point is unaffected: its check never consults candidate_causes_tested.
    assert result.escape_point_traceable is True


def test_d5_root_cause_validation_not_run_is_a_warning() -> None:
    result = validate_d5_pca_selection(_d5(), _d4(root_verdict=None, escape_verdict="ACCEPT"))
    assert ("PCA_ROOT_CAUSE_VALIDATION_NOT_RUN", "warning") in _cs(result)
    assert result.root_cause_traceable is False
    assert (result.verdict, result.valid) == ("WARNING", True)


def test_d5_escape_point_rejected_five_why_is_flagged() -> None:
    result = validate_d5_pca_selection(_d5(), _d4(root_verdict="ACCEPT", escape_verdict="REJECT"))
    assert ("PCA_NOT_TRACEABLE_ESCAPE_POINT", "error") in _cs(result)
    assert result.escape_point_traceable is False
    assert result.root_cause_traceable is True
    assert (result.verdict, result.valid) == ("REJECT", False)


def test_d5_escape_point_validation_not_run_is_a_warning() -> None:
    result = validate_d5_pca_selection(_d5(), _d4(root_verdict="ACCEPT", escape_verdict=None))
    assert ("PCA_ESCAPE_POINT_VALIDATION_NOT_RUN", "warning") in _cs(result)
    assert result.escape_point_traceable is False


def test_d5_warning_verdict_is_traceable_no_finding() -> None:
    """A WARNING five-why verdict (neither None nor REJECT) is still traceable — no finding."""
    result = validate_d5_pca_selection(
        _d5(), _d4(root_verdict="WARNING", escape_verdict="WARNING")
    )
    assert _cs(result) == [("D5_READY", "info")]
    assert (result.root_cause_traceable, result.escape_point_traceable) == (True, True)


def test_d5_multiple_candidates_per_target_are_each_checked() -> None:
    """The per-candidate loop must not assume exactly one candidate per target."""
    d5 = _d5(
        _pca(action_id="PCA-RC-1", target="ROOT_CAUSE"),
        _pca(action_id="PCA-RC-2", target="ROOT_CAUSE", verified=False),
        _pca(action_id="PCA-EP-1", target="ESCAPE_POINT"),
    )
    result = validate_d5_pca_selection(d5, _clean_d4())
    assert result.candidate_count == 3
    # The second RC candidate's error is raised without masking the first's traceability pass.
    undesirable = [f for f in result.findings if f.code == "PCA_UNDESIRABLE_EFFECTS_NOT_VERIFIED"]
    assert [f.action_id for f in undesirable] == ["PCA-RC-2"]
    assert (result.verdict, result.valid) == ("REJECT", False)


def test_d5_error_outranks_concurrent_warning() -> None:
    result = validate_d5_pca_selection(
        _d5(), _d4(root_verdict="REJECT", escape_verdict=None)
    )
    codes = [c for c, _ in _cs(result)]
    assert "PCA_NOT_TRACEABLE_ROOT_CAUSE" in codes  # error
    assert "PCA_ESCAPE_POINT_VALIDATION_NOT_RUN" in codes  # warning
    assert result.verdict == "REJECT"


def test_d5_traceability_helper_confirmed_and_accepted_returns_none() -> None:
    """The private helper returns None (traceable) when the confirmed test and verdict both pass."""
    assert (
        _d5_traceability_finding(
            "PCA-RC", "ROOT_CAUSE", has_confirmed_test=True, verdict="ACCEPT"
        )
        is None
    )


def test_d5_recommendations_are_deduplicated() -> None:
    """Two RC candidates that both fail traceability collapse to one recommendation string."""
    d5 = _d5(
        _pca(action_id="PCA-RC-1", target="ROOT_CAUSE"),
        _pca(action_id="PCA-RC-2", target="ROOT_CAUSE"),
        _pca(action_id="PCA-EP-1", target="ESCAPE_POINT"),
    )
    result = validate_d5_pca_selection(d5, _d4(root_verdict="REJECT", escape_verdict="ACCEPT"))
    assert len(result.recommendations) == len(set(result.recommendations))


# ==============================================================================
# 8. D6 — Implement and validate the permanent corrective actions
# ==============================================================================


def _impl(
    *,
    action_id: str = "PCA-RC",
    effective: bool | None = True,
) -> ImplementedAction:
    """One implemented PCA; `None` = no verification record, else verified effective/ineffective."""
    return ImplementedAction(
        corrective_action_id=action_id,
        implemented_date=IMPLEMENTED,
        verification=None if effective is None else _verification(is_effective=effective),
    )


def _d6(
    *actions: ImplementedAction,
    removed: datetime.date | None = None,
) -> D6Discipline:
    """A D6 record; defaults to one verified action covering the root cause."""
    if not actions:
        actions = (_impl(),)
    return D6Discipline(
        implemented_actions=list(actions), interim_containment_removed_date=removed
    )


def _d5_both_targets() -> D5Discipline:
    """A D5 whose two candidates carry the ids `PCA-RC` (ROOT_CAUSE) / `PCA-EP` (ESCAPE_POINT)."""
    return _d5(
        _pca(action_id="PCA-RC", target="ROOT_CAUSE"),
        _pca(action_id="PCA-EP", target="ESCAPE_POINT"),
    )


def _clean_d6_both() -> D6Discipline:
    """Both targets implemented and verified, ICA removed — the D6_READY shape."""
    return _d6(
        _impl(action_id="PCA-RC"),
        _impl(action_id="PCA-EP"),
        removed=IMPLEMENTED,
    )


def test_d6_finding_and_result_to_dict_round_trip() -> None:
    finding = D6Finding("CODE", "info", "PCA-RC", "msg", "rec")
    assert finding.to_dict() == {
        "code": "CODE", "severity": "info", "action_id": "PCA-RC",
        "message": "msg", "recommendation": "rec",
    }

    result = validate_d6_implementation_validation(_clean_d6_both(), _d5_both_targets())
    payload = result.to_dict()
    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.implementation_verified is True
    assert result.action_count == 2
    assert result.copq_impact is None
    assert payload["basis"] == "Ford Global 8D / AIAG CQI-20"
    assert payload["findings"] == [f.to_dict() for f in result.findings]
    assert payload["recommendations"] is not result.recommendations
    assert payload["copq_impact"] is None


def test_d6_clean_pass_emits_only_d6_ready() -> None:
    result = validate_d6_implementation_validation(_clean_d6_both(), _d5_both_targets())
    assert _cs(result) == [("D6_READY", "info")]
    assert result.implementation_verified is True


def test_d6_no_d5_supplied_is_a_warning() -> None:
    result = validate_d6_implementation_validation(_clean_d6_both())
    assert _cs(result) == [("D5_NOT_SUPPLIED", "warning")]
    assert (result.verdict, result.valid) == ("WARNING", True)


def test_d6_action_without_verification_is_an_error() -> None:
    result = validate_d6_implementation_validation(
        _d6(_impl(action_id="PCA-RC", effective=None)), _d5_both_targets()
    )
    assert ("IMPLEMENTED_ACTION_NOT_VERIFIED", "error") in _cs(result)
    assert result.findings[0].action_id == "PCA-RC"
    assert result.implementation_verified is False
    assert (result.verdict, result.valid) == ("REJECT", False)


def test_d6_action_verified_ineffective_is_an_error() -> None:
    result = validate_d6_implementation_validation(
        _d6(_impl(action_id="PCA-RC", effective=False)), _d5_both_targets()
    )
    assert ("IMPLEMENTED_ACTION_VERIFIED_INEFFECTIVE", "error") in _cs(result)
    assert result.implementation_verified is False
    assert (result.verdict, result.valid) == ("REJECT", False)


def test_d6_unknown_corrective_action_id_is_an_error_case_sensitive() -> None:
    """AC-adjacent negative control: the D5 cross-reference is exact and case-sensitive.

    `pca-1` is NOT `PCA-RC`; a differently-cased or unknown id fires the unknown-id error rather
    than silently matching. No fuzzy matching is permitted anywhere.
    """
    result = validate_d6_implementation_validation(
        _d6(_impl(action_id="pca-rc")), _d5_both_targets()
    )
    codes = [c for c, _ in _cs(result)]
    assert ("IMPLEMENTED_ACTION_UNKNOWN_CORRECTIVE_ACTION_ID", "error") in _cs(result)
    # coverage is also incomplete because the unknown-id action is never counted as covering RC.
    assert "IMPLEMENTED_ACTION_TARGET_COVERAGE_INCOMPLETE" in codes
    assert result.verdict == "REJECT"


def test_d6_case_sensitive_positive_control_matches_exactly() -> None:
    """The exact-cased id matches and is counted as covering its target — the positive control."""
    result = validate_d6_implementation_validation(
        _clean_d6_both(), _d5_both_targets()
    )
    assert "IMPLEMENTED_ACTION_UNKNOWN_CORRECTIVE_ACTION_ID" not in [c for c, _ in _cs(result)]


def test_d6_target_coverage_incomplete_is_a_warning() -> None:
    """Only the root cause is implemented and verified — the escape point is uncovered."""
    result = validate_d6_implementation_validation(
        _d6(_impl(action_id="PCA-RC")), _d5_both_targets()
    )
    coverage = [f for f in result.findings if f.code == "IMPLEMENTED_ACTION_TARGET_COVERAGE_INCOMPLETE"]
    assert len(coverage) == 1
    assert coverage[0].severity == "warning"
    assert "ESCAPE_POINT" in coverage[0].message
    assert "ROOT_CAUSE" not in coverage[0].message
    assert (result.verdict, result.valid) == ("WARNING", True)


def test_d6_matched_but_unverified_action_does_not_cover_its_target() -> None:
    """The `elif action.is_verified` false side: an ID-matched but ineffective action.

    It matches a D5 candidate (so no unknown-id error), but being ineffective it is not added to
    covered_targets, so both the ineffective error and the incomplete-coverage warning surface.
    """
    result = validate_d6_implementation_validation(
        _d6(
            _impl(action_id="PCA-RC", effective=False),
            _impl(action_id="PCA-EP", effective=True),
        ),
        _d5_both_targets(),
    )
    codes = [c for c, _ in _cs(result)]
    assert "IMPLEMENTED_ACTION_VERIFIED_INEFFECTIVE" in codes
    assert "IMPLEMENTED_ACTION_TARGET_COVERAGE_INCOMPLETE" in codes
    assert "ROOT_CAUSE" in next(
        f.message for f in result.findings if f.code == "IMPLEMENTED_ACTION_TARGET_COVERAGE_INCOMPLETE"
    )


def test_d6_ica_not_removed_is_a_warning() -> None:
    """Every action verified but no removal date recorded — the ICA_NOT_REMOVED warning fires."""
    result = validate_d6_implementation_validation(
        _d6(_impl(action_id="PCA-RC"), _impl(action_id="PCA-EP"), removed=None),
        _d5_both_targets(),
    )
    assert ("ICA_NOT_REMOVED", "warning") in _cs(result)
    assert result.implementation_verified is True
    assert (result.verdict, result.valid) == ("WARNING", True)


def test_d6_unverified_actions_do_not_raise_ica_not_removed() -> None:
    """The ICA check is gated on is_verified: an unverified record never raises it."""
    result = validate_d6_implementation_validation(
        _d6(_impl(action_id="PCA-RC", effective=None), _impl(action_id="PCA-EP")),
        _d5_both_targets(),
    )
    assert "ICA_NOT_REMOVED" not in [c for c, _ in _cs(result)]
    assert result.implementation_verified is False


def test_d6_error_outranks_concurrent_warning() -> None:
    result = validate_d6_implementation_validation(
        _d6(_impl(action_id="PCA-RC", effective=None)), _d5_both_targets()
    )
    codes = [c for c, _ in _cs(result)]
    assert "IMPLEMENTED_ACTION_NOT_VERIFIED" in codes  # error
    assert "IMPLEMENTED_ACTION_TARGET_COVERAGE_INCOMPLETE" in codes  # warning
    assert result.verdict == "REJECT"


# ---- D6 COPQ delegation ------------------------------------------------------------


def _copq_items_as(shape: str) -> object:
    """One InternalFailure cost of $500 in each shape estimate_copq accepts."""
    row = {"category": "InternalFailure", "description": "scrap", "direct_cost": 500.0}
    if shape == "dataset":
        return COPQDataset(items=[CostItem(**row)])
    if shape == "dataframe":
        return pd.DataFrame([row])
    if shape == "list-of-dicts":
        return [row]
    if shape == "list-of-items":
        return [CostItem(**row)]
    if shape == "dict":
        return {"items": [row]}
    raise AssertionError(shape)


@pytest.mark.parametrize(
    "shape", ["dataset", "dataframe", "list-of-dicts", "list-of-items", "dict"]
)
def test_d6_copq_impact_is_populated_for_every_accepted_shape(shape: str) -> None:
    result = validate_d6_implementation_validation(
        _clean_d6_both(), _d5_both_targets(), copq_data=_copq_items_as(shape)
    )
    assert result.copq_impact is not None
    # Non-vacuous: a $500 InternalFailure driver must actually roll up to total_copq.
    assert result.copq_impact["total_copq"] == 500.0
    assert result.to_dict()["copq_impact"]["total_copq"] == 500.0


def test_d6_absent_copq_data_is_not_an_error() -> None:
    result = validate_d6_implementation_validation(_clean_d6_both(), _d5_both_targets())
    assert result.copq_impact is None
    assert result.verdict == "ACCEPT"


def test_d6_malformed_copq_data_propagates_uncaught_type_error() -> None:
    """Per OPEN QUESTION 3: COPQ exceptions propagate; they are NOT converted into a verdict."""
    with pytest.raises(TypeError):
        validate_d6_implementation_validation(
            _clean_d6_both(), _d5_both_targets(), copq_data=42
        )


def test_d6_structurally_invalid_copq_row_propagates_validation_error() -> None:
    """A negative cost in a COPQ row raises pydantic.ValidationError, uncaught by the engine."""
    with pytest.raises(pydantic.ValidationError):
        validate_d6_implementation_validation(
            _clean_d6_both(),
            _d5_both_targets(),
            copq_data=[
                {"category": "InternalFailure", "description": "scrap", "direct_cost": -5.0}
            ],
        )


def test_d6_engine_symbols_are_re_exported_from_quality_core_rca() -> None:
    """Assert the six new D5/D6 engine symbols are importable from quality_core.rca."""
    import quality_core.rca as rca

    assert rca.validate_d5_pca_selection is validate_d5_pca_selection
    assert rca.validate_d6_implementation_validation is validate_d6_implementation_validation
    assert rca.D5Finding is D5Finding
    assert rca.D5ValidationResult is D5ValidationResult
    assert rca.D6Finding is D6Finding
    assert rca.D6ValidationResult is D6ValidationResult

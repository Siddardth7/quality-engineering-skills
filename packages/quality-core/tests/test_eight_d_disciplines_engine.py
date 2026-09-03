"""
Unit tests for the 8D D0/D1 discipline engines (quality_core.rca.eight_d_disciplines).

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
5. Package re-export smoke test from quality_core.rca.
"""

from __future__ import annotations

import datetime

import pytest
from quality_core.rca.eight_d_disciplines import (
    D0Finding,
    D0ValidationResult,
    D1Finding,
    D1ValidationResult,
    _dedupe,
    _is_verified_effective,
    validate_d0_readiness,
    validate_d1_team,
)
from quality_core.rca.eight_d_schema import (
    D0Discipline,
    D1Discipline,
    EffectivenessVerification,
    TeamMember,
)

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


def _codes(result: D0ValidationResult | D1ValidationResult) -> list[str]:
    """Return the finding codes of a result, in order."""
    return [f.code for f in result.findings]


def _severities(result: D0ValidationResult | D1ValidationResult) -> list[str]:
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
# 5. Package re-export
# ==============================================================================


def test_engine_symbols_are_re_exported_from_quality_core_rca() -> None:
    """Assert the D0/D1 engine surface is importable from the quality_core.rca package."""
    import quality_core.rca as rca

    assert rca.validate_d0_readiness is validate_d0_readiness
    assert rca.validate_d1_team is validate_d1_team
    assert rca.D0Finding is D0Finding
    assert rca.D0ValidationResult is D0ValidationResult
    assert rca.D1Finding is D1Finding
    assert rca.D1ValidationResult is D1ValidationResult
    for name in (
        "D0Finding",
        "D0ValidationResult",
        "D1Finding",
        "D1ValidationResult",
        "validate_d0_readiness",
        "validate_d1_team",
    ):
        assert name in rca.__all__

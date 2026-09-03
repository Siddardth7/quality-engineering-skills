"""
eight_d_disciplines.py
Deterministic 8D discipline engines for D0 (Emergency Response Action readiness) and D1
(team completeness).

Pure, post-validation checks over already-typed :mod:`quality_core.rca.eight_d_schema` models:
``validate_d0_readiness`` reads a ``D0Discipline`` and reports whether the Emergency Response
Action (ERA) is required, implemented, and verified *effective*; ``validate_d1_team`` reads a
``D1Discipline`` and reports whether the team is complete enough to proceed. Both return a
verdict on the same three-value ``ACCEPT`` / ``WARNING`` / ``REJECT`` scale the other RCA
engines use.

**Scope.** D0 and D1 only. There is no state machine, no discipline-advancement API, and no
cross-discipline gate enforcement here — those live in ``rca/eight_d.py``. These functions take
typed discipline instances only; the untrusted-data trust boundary is ``validate_eight_d`` in
``rca/eight_d_schema.py``, which validates D0/D1 as part of a whole ``EightDReport``.

**No competency or team-size model is implemented for D1.** ``TeamMember`` carries no skill or
competency field to check one against, and neither manual quantifies a team size or a skill
level: CQI-20 describes "too few"/"too many" members and appropriate skill level qualitatively,
with no number. Inventing a minimum member count, a maximum roster size, or a competency matrix
would assert a threshold no source states, so none is implemented.

Standards References:
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Sections D0 and D1.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), team-definition step.

Rules applied: RULE-8D-D0, RULE-8D-D0-001..003, RULE-8D-D1, RULE-8D-D1-001..003 in
``rca/CITATIONS.tsv`` / ``rca/ASSUMPTIONS_LOG.md``. The heuristics that no manual backs
(``ERA_VERIFICATION_DATE_INCONSISTENT``, ``CHAMPION_TEAM_LEADER_SAME_PERSON``,
``DUPLICATE_TEAM_MEMBER``, and the field-presence reading of "roles ... clear") are declared as
Process Design Decision #6 in ``rca/ASSUMPTIONS_LOG.md`` and carry no citation row.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Literal

from quality_core.rca.eight_d_schema import (
    D0Discipline,
    D1Discipline,
    EffectivenessVerification,
)

__all__ = [
    "D0Finding",
    "D0ValidationResult",
    "D1Finding",
    "D1ValidationResult",
    "validate_d0_readiness",
    "validate_d1_team",
]

_STANDARDS_BASIS = "Ford Global 8D / AIAG CQI-20"


def _is_verified_effective(verification: EffectivenessVerification | None) -> bool:
    """True only when a verification record exists *and* concluded the action is effective.

    This predicate duplicates ``ContainmentAction.is_verified`` (``eight_d_schema.py:304``) and
    ``ImplementedAction.is_verified`` (``eight_d_schema.py:483``) **by necessity, not by
    preference**: ``EffectivenessVerification`` exposes no ``is_verified`` of its own, and
    ``D0Discipline.era_verification`` is a bare optional record with no property to read. Adding
    that property to ``EffectivenessVerification`` is the correct consolidation and is a
    deliberate follow-up once #224 (which owns ``eight_d_schema.py``) lands; until then the
    predicate is written exactly once *here* rather than inlined per call site, so the three
    copies cannot drift apart silently.
    """
    return verification is not None and verification.is_effective


def _dedupe(values: Iterable[str]) -> list[str]:
    """Collect values in first-seen order, skipping repeats."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


# ==============================================================================
# 1. D0 — Emergency Response Action readiness
# ==============================================================================


@dataclass
class D0Finding:
    """Finding raised against the D0 Emergency Response Action record."""

    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D0 finding."""
        return asdict(self)


@dataclass
class D0ValidationResult:
    """Complete D0 (ERA readiness) validation result."""

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    era_required: bool
    era_implemented: bool
    era_verified: bool
    findings: list[D0Finding]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D0 result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "era_required": self.era_required,
            "era_implemented": self.era_implemented,
            "era_verified": self.era_verified,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": list(self.recommendations),
        }


def validate_d0_readiness(discipline: D0Discipline) -> D0ValidationResult:
    """Validate D0 Emergency Response Action (ERA) readiness.

    Ford Global 8D requires an ERA to protect the customer where one is necessary, and requires
    that ERA to be *checked effective* before its full implementation (RULE-8D-D0,
    RULE-8D-D0-001..003). This function reports on that chain — required, implemented,
    verified effective — and rejects when it is broken.

    ``era_description`` presence is guaranteed by ``D0Discipline``'s own model validator whenever
    ``era_required`` is True and is deliberately not re-checked here.

    Parameters
    ----------
    discipline : D0Discipline
        A validated D0 discipline record.

    Returns
    -------
    D0ValidationResult
        Verdict, readiness flags, findings, and de-duplicated recommendations.
    """
    implemented_date = discipline.era_implemented_date
    verification = discipline.era_verification

    era_implemented = implemented_date is not None
    era_verified = _is_verified_effective(verification)

    findings: list[D0Finding] = []
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]

    if not discipline.era_required:
        findings.append(
            D0Finding(
                code="ERA_NOT_REQUIRED",
                severity="info",
                message=(
                    "D0 records no Emergency Response Action requirement "
                    "(era_required is False); no ERA readiness evidence is expected."
                ),
                recommendation=(
                    "Confirm the assessment that no Emergency Response Action is necessary is "
                    "documented, then proceed to D1."
                ),
            )
        )
        verdict, valid = "ACCEPT", True

    elif implemented_date is None:
        findings.append(
            D0Finding(
                code="ERA_NOT_IMPLEMENTED",
                severity="error",
                message=(
                    "D0 requires an Emergency Response Action but no implementation date is "
                    "recorded (era_implemented_date is unset)."
                ),
                recommendation=(
                    "Implement the Emergency Response Action to protect the customer and record "
                    "its implementation date before proceeding past D0."
                ),
            )
        )
        if verification is not None:
            findings.append(
                D0Finding(
                    code="ERA_VERIFIED_WITHOUT_IMPLEMENTATION",
                    severity="error",
                    message=(
                        f"An ERA effectiveness verification is recorded "
                        f"(by {verification.verified_by} on {verification.verified_date}) while "
                        "the ERA itself is not marked implemented."
                    ),
                    recommendation=(
                        "Record the ERA implementation date, or withdraw the verification "
                        "record — an ERA cannot be verified before it is implemented."
                    ),
                )
            )
        verdict, valid = "REJECT", False

    elif verification is None:
        findings.append(
            D0Finding(
                code="ERA_NOT_VERIFIED",
                severity="error",
                message=(
                    f"The ERA implemented on {implemented_date} carries no effectiveness "
                    "verification record."
                ),
                recommendation=(
                    "Verify the Emergency Response Action is effective before its full "
                    "implementation and record who verified it, when, and on what evidence."
                ),
            )
        )
        verdict, valid = "REJECT", False

    elif not verification.is_effective:
        findings.append(
            D0Finding(
                code="ERA_VERIFIED_INEFFECTIVE",
                severity="error",
                message=(
                    f"The ERA verification recorded by {verification.verified_by} on "
                    f"{verification.verified_date} concluded the action is not effective."
                ),
                recommendation=(
                    "Replace or strengthen the Emergency Response Action and re-verify it: the "
                    "verification must demonstrate the effects of the problem are eliminated."
                ),
            )
        )
        verdict, valid = "REJECT", False

    elif verification.verified_date < implemented_date:
        findings.append(
            D0Finding(
                code="ERA_VERIFICATION_DATE_INCONSISTENT",
                severity="warning",
                message=(
                    f"The ERA verification date {verification.verified_date} precedes the ERA "
                    f"implementation date {implemented_date}."
                ),
                recommendation=(
                    "Correct the ERA verification or implementation date so the verification "
                    "does not predate the action it verifies."
                ),
            )
        )
        verdict, valid = "WARNING", True

    else:
        findings.append(
            D0Finding(
                code="ERA_READY",
                severity="info",
                message=(
                    f"The ERA implemented on {implemented_date} was verified effective by "
                    f"{verification.verified_by} on {verification.verified_date}."
                ),
                recommendation=(
                    "Emergency Response Action is implemented and verified effective; proceed "
                    "to D1 team formation."
                ),
            )
        )
        verdict, valid = "ACCEPT", True

    return D0ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        era_required=discipline.era_required,
        era_implemented=era_implemented,
        era_verified=era_verified,
        findings=findings,
        recommendations=_dedupe(f.recommendation for f in findings),
    )


# ==============================================================================
# 2. D1 — Team completeness
# ==============================================================================


@dataclass
class D1Finding:
    """Finding raised against the D1 team roster."""

    code: str
    severity: Literal["error", "warning", "info"]
    member_name: str | None
    message: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D1 finding."""
        return asdict(self)


@dataclass
class D1ValidationResult:
    """Complete D1 (team completeness) validation result."""

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    champion: str
    team_leader: str
    member_count: int
    findings: list[D1Finding]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D1 result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "champion": self.champion,
            "team_leader": self.team_leader,
            "member_count": self.member_count,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": list(self.recommendations),
        }


def validate_d1_team(discipline: D1Discipline) -> D1ValidationResult:
    """Validate D1 team completeness.

    ``D1Discipline`` already guarantees a non-blank Champion and Team Leader (RULE-8D-D1), but
    nothing in the schema requires the team itself to have members — an empty ``members`` list is
    the real gap this engine catches (RULE-8D-D1-001, RULE-8D-D1-002) and is rejected. Undefined
    member roles are warned on (RULE-8D-D1-003); duplicate member names and a Champion who is
    also the Team Leader are warned on as declared heuristics with no standards backing (see
    Process Design Decision #6 in ``ASSUMPTIONS_LOG.md``).

    No team-size bound and no competency check are applied — see the module docstring.

    Parameters
    ----------
    discipline : D1Discipline
        A validated D1 discipline record.

    Returns
    -------
    D1ValidationResult
        Verdict, roster summary, findings, and de-duplicated recommendations.
    """
    findings: list[D1Finding] = []
    champion_norm = discipline.champion.strip().casefold()
    leader_norm = discipline.team_leader.strip().casefold()

    if not discipline.members:
        findings.append(
            D1Finding(
                code="NO_TEAM_MEMBERS",
                severity="error",
                member_name=None,
                message=(
                    "D1 names a Champion and a Team Leader but no team members — the team is "
                    "incomplete."
                ),
                recommendation=(
                    "Define the team members: establish a small group with the process and/or "
                    "product knowledge required to solve the problem."
                ),
            )
        )
    else:
        seen: dict[str, int] = {}
        for member in discipline.members:
            key = member.name.strip().casefold()
            seen[key] = seen.get(key, 0) + 1
            if member.role is None:
                findings.append(
                    D1Finding(
                        code="TEAM_MEMBER_ROLE_UNDEFINED",
                        severity="warning",
                        member_name=member.name,
                        message=f"Team member '{member.name}' has no role recorded.",
                        recommendation=(
                            "Record a role for every team member so roles and responsibilities "
                            "are clear."
                        ),
                    )
                )
        for key, count in seen.items():
            if count > 1:
                original_name = next(
                    m.name for m in discipline.members if m.name.strip().casefold() == key
                )
                findings.append(
                    D1Finding(
                        code="DUPLICATE_TEAM_MEMBER",
                        severity="warning",
                        member_name=original_name,
                        message=(
                            f"Team member '{original_name}' appears {count} times in the roster."
                        ),
                        recommendation=(
                            "Remove duplicate roster entries so each team member is listed once."
                        ),
                    )
                )

    if champion_norm == leader_norm:
        findings.append(
            D1Finding(
                code="CHAMPION_TEAM_LEADER_SAME_PERSON",
                severity="warning",
                member_name=None,
                message=(
                    f"'{discipline.champion}' is recorded as both Champion and Team Leader."
                ),
                recommendation=(
                    "Confirm one person holding both the Champion and Team Leader roles is "
                    "intended; the two roles carry distinct responsibilities."
                ),
            )
        )

    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    if any(f.severity == "error" for f in findings):
        verdict, valid = "REJECT", False
    elif any(f.severity == "warning" for f in findings):
        verdict, valid = "WARNING", True
    else:
        findings.append(
            D1Finding(
                code="TEAM_READY",
                severity="info",
                member_name=None,
                message=(
                    f"Team is complete: Champion, Team Leader, and "
                    f"{len(discipline.members)} member(s) with roles recorded."
                ),
                recommendation=(
                    "Team composition is complete; proceed to D2 problem description."
                ),
            )
        )
        verdict, valid = "ACCEPT", True

    return D1ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        champion=discipline.champion,
        team_leader=discipline.team_leader,
        member_count=len(discipline.members),
        findings=findings,
        recommendations=_dedupe(f.recommendation for f in findings),
    )

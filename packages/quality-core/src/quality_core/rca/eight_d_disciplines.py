"""
eight_d_disciplines.py
Deterministic 8D discipline engines for D0 (Emergency Response Action readiness), D1
(team completeness), and D2 (problem description).

Pure, post-validation checks over already-typed :mod:`quality_core.rca.eight_d_schema` models:
``validate_d0_readiness`` reads a ``D0Discipline`` and reports whether the Emergency Response
Action (ERA) is required, implemented, and verified *effective*; ``validate_d1_team`` reads a
``D1Discipline`` and reports whether the team is complete enough to proceed;
``validate_d2_problem_description`` reads a ``D2Discipline`` plus optional Is/Is-Not scoping data
and reports whether both stages of Ford 8D's D2 are covered. All three return a verdict on the
same three-value ``ACCEPT`` / ``WARNING`` / ``REJECT`` scale the other RCA engines use.

**Scope.** D0, D1 and D2 only. There is no state machine, no discipline-advancement API, and no
cross-discipline gate enforcement here — those live in ``rca/eight_d.py``. These functions take
typed discipline instances only; the untrusted-data trust boundary is ``validate_eight_d`` in
``rca/eight_d_schema.py``, which validates D0/D1/D2 as part of a whole ``EightDReport``. The one
exception is ``validate_d2_problem_description``'s optional ``is_is_not`` argument: untrusted
scoping data handed straight to ``quality_core.rca.is_is_not.scope_is_is_not``, the module that
owns that trust boundary, with no independent type check here.

**No competency or team-size model is implemented for D1.** ``TeamMember`` carries no skill or
competency field to check one against, and neither manual quantifies a team size or a skill
level: CQI-20 describes "too few"/"too many" members and appropriate skill level qualitatively,
with no number. Inventing a minimum member count, a maximum roster size, or a competency matrix
would assert a threshold no source states, so none is implemented.

**The D2 5W2H model is CQI-20 Figure 12, read from the manual.** Figure 12, "Problem
Identification Questions", enumerates and defines seven questions — Who?, What?, When?, Where?,
Why?, How?, How Many? — five W-questions and two How-questions (``RULE-8D-D2-003``). Those seven
are the checkable sub-fields, held on ``D2Discipline`` as the optional ``w2h_*`` answers, and a
declared-but-incomplete 5W2H is an ``error`` here. The looser expansion "5 Why-2 How" appears
once in CQI-20, in an aside inside a note on supplier SCARs (``RULE-8D-D2``); Figure 12 is the
normative enumeration and this engine follows Figure 12. No free-text token parsing is done —
completeness is judged over the typed answer fields only.

Standards References:
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Sections D0, D1 and D2.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), team-definition step,
  problem-description step, and Figure 12 "Problem Identification Questions".

Rules applied: RULE-8D-D0, RULE-8D-D0-001..003, RULE-8D-D1, RULE-8D-D1-001..003, RULE-8D-D2,
RULE-8D-D2-001..003 in ``rca/CITATIONS.tsv`` / ``rca/ASSUMPTIONS_LOG.md``. The heuristics that no
manual backs (``ERA_VERIFICATION_DATE_INCONSISTENT``, ``CHAMPION_TEAM_LEADER_SAME_PERSON``,
``DUPLICATE_TEAM_MEMBER``, the field-presence reading of "roles ... clear",
``DEGENERATE_PROBLEM_STATEMENT`` and ``QUANTIFICATION_NOT_NUMERIC``) are declared as Process
Design Decisions #6 and #7 in ``rca/ASSUMPTIONS_LOG.md`` and carry no citation row.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Literal

import pandas as pd

from quality_core.rca.eight_d_schema import (
    D0Discipline,
    D1Discipline,
    D2Discipline,
    EffectivenessVerification,
)
from quality_core.rca.is_is_not import scope_is_is_not
from quality_core.rca.schema import IsIsNotMatrix

__all__ = [
    "D0Finding",
    "D0ValidationResult",
    "D1Finding",
    "D1ValidationResult",
    "D2Finding",
    "D2ValidationResult",
    "validate_d0_readiness",
    "validate_d1_team",
    "validate_d2_problem_description",
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


# ==============================================================================
# 3. D2 — Problem description
# ==============================================================================


def _five_w_two_h_answers(discipline: D2Discipline) -> tuple[tuple[str, str | None], ...]:
    """Pair each CQI-20 Figure 12 question with the ``D2Discipline`` field that answers it.

    The questions and their order are the manual's own (``RULE-8D-D2-003``): five W-questions
    (Who, What, When, Where, Why) and two How-questions (How, How Many), which is what CQI-20's
    "5W2H" names. Written as an explicit tuple rather than a ``getattr`` loop so that a renamed
    or dropped ``w2h_*`` field fails type-checking here instead of silently reading ``None``.
    """
    return (
        ("Who?", discipline.w2h_who),
        ("What?", discipline.w2h_what),
        ("When?", discipline.w2h_when),
        ("Where?", discipline.w2h_where),
        ("Why?", discipline.w2h_why),
        ("How?", discipline.w2h_how),
        ("How Many?", discipline.w2h_how_many),
    )


@dataclass
class D2Finding:
    """Finding raised against the D2 problem description — structural or declared heuristic."""

    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D2 finding."""
        return asdict(self)


@dataclass
class D2ValidationResult:
    """Complete D2 (problem description) validation result.

    ``is_is_not`` is the nested ``IsIsNotScopingResult.to_dict()`` payload when scoping data was
    supplied, and ``None`` when it was not — this engine never authors scoping data of its own.

    ``five_w_two_h`` is the structured completeness evidence behind
    ``METHOD_5W2H_DESCRIPTION_INCOMPLETE``: ``{"answered": [...], "missing": [...], "complete":
    bool}``, the question labels being CQI-20 Figure 12's own (``RULE-8D-D2-003``). It is
    ``None`` when 5W2H was not the declared method, so the engine never records a completeness
    judgment about a method the team did not claim.
    """

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    problem_statement: str
    findings: list[D2Finding]
    is_is_not: dict[str, Any] | None
    five_w_two_h: dict[str, Any] | None
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D2 result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "problem_statement": self.problem_statement,
            "findings": [f.to_dict() for f in self.findings],
            "is_is_not": self.is_is_not,
            "five_w_two_h": self.five_w_two_h,
            "recommendations": list(self.recommendations),
        }


def validate_d2_problem_description(
    discipline: D2Discipline,
    is_is_not: IsIsNotMatrix | pd.DataFrame | list[Any] | dict[str, Any] | None = None,
) -> D2ValidationResult:
    """Validate D2: problem-statement structure plus Is/Is-Not problem-description scoping.

    Ford Global 8D splits D2 into two stages (RULE-8D-D2-001, RULE-8D-D2-002): a problem
    *statement* — what is bad (the symptom) with what (the object) — and a problem *description*
    established by determining what, where, when and how big using the Is / Is Not form.
    ``D2Discipline`` captures the first stage as three required, already-non-blank text fields;
    this engine folds in the second stage by delegating to
    ``quality_core.rca.is_is_not.scope_is_is_not``, whose four Kepner-Tregoe dimensions
    (``WHAT`` / ``WHERE`` / ``WHEN`` / ``EXTENT``) are the same four Ford names. Is/Is-Not scoping
    is never reimplemented here.

    Two of the findings are **declared heuristics, not standards claims**:
    ``DEGENERATE_PROBLEM_STATEMENT`` (``what_is_wrong`` and ``with_what`` are the same text) and
    ``QUANTIFICATION_NOT_NUMERIC`` (no digit anywhere in ``quantification``). No manual defines
    either check — a digit test cannot tell "3 per shift" from "a majority of parts" — so both are
    warnings, never errors, and neither carries a ``CITATIONS.tsv`` row. See Process Design
    Decision #7 in ``rca/ASSUMPTIONS_LOG.md``.

    ``method_used == "5W2H"`` is a **checked claim, not a label**. AIAG CQI-20 Figure 12,
    "Problem Identification Questions" (RULE-8D-D2-003), enumerates and defines the seven
    questions a 5W2H description answers — Who?, What?, When?, Where?, Why?, How?, How Many? —
    so a record that declares the method and leaves any of the seven ``w2h_*`` answers empty is
    an incomplete 5W2H. That is reported as ``METHOD_5W2H_DESCRIPTION_INCOMPLETE`` at
    ``severity="error"``, naming the unanswered questions, and the verdict is never ``ACCEPT``.
    The structured evidence is returned on ``D2ValidationResult.five_w_two_h``. When 5W2H is not
    the declared method, nothing here is checked and ``five_w_two_h`` stays ``None``: the seven
    answers are optional data, and only the declaration makes them a promise.

    The composed statement **always overrides** any ``problem_statement`` ``scope_is_is_not``
    would otherwise use (its ``"Problem Statement"`` default, or the one carried on a supplied
    ``IsIsNotMatrix``), so the nested scoping result reflects D2's authoritative statement. That
    override is a platform judgment call, not a standards requirement.

    Parameters
    ----------
    discipline : D2Discipline
        A validated D2 discipline record. Its three text fields are guaranteed non-blank and
        stripped by ``D2Discipline`` itself and are deliberately not re-checked for presence.
    is_is_not : IsIsNotMatrix | pd.DataFrame | list | dict | None, optional
        Untrusted Is/Is-Not scoping data in any shape ``scope_is_is_not`` accepts. ``None`` means
        no scoping data has been supplied yet: flagged as a warning and never passed through to
        ``scope_is_is_not``, which raises ``TypeError`` on ``None``.

    Returns
    -------
    D2ValidationResult
        Verdict, composed problem statement, findings, nested Is/Is-Not scoping payload, 5W2H
        completeness evidence, and de-duplicated recommendations.

    Raises
    ------
    TypeError
        Propagated unmodified from ``scope_is_is_not`` when ``is_is_not`` is a type it rejects
        (an int, a bool, ...). This engine performs no independent type check of its own.
    pydantic.ValidationError
        Propagated unmodified from ``scope_is_is_not`` / ``validate_is_is_not`` when ``is_is_not``
        contains structurally invalid rows.
    """
    problem_statement = f"{discipline.what_is_wrong} with {discipline.with_what}"

    findings: list[D2Finding] = []
    recommendations: list[str] = []

    if discipline.what_is_wrong.strip().casefold() == discipline.with_what.strip().casefold():
        findings.append(
            D2Finding(
                code="DEGENERATE_PROBLEM_STATEMENT",
                severity="warning",
                message=(
                    f"The problem statement does not distinguish the defect from the object: "
                    f"what_is_wrong and with_what both read '{discipline.what_is_wrong}'."
                ),
                recommendation=(
                    "Restate what_is_wrong as the defect or symptom and with_what as the object "
                    "experiencing it, so the two fields name different things."
                ),
            )
        )

    if not any(ch.isdigit() for ch in discipline.quantification):
        findings.append(
            D2Finding(
                code="QUANTIFICATION_NOT_NUMERIC",
                severity="warning",
                message=(
                    f"The D2 quantification '{discipline.quantification}' carries no numeric "
                    "magnitude, so the problem is not detailed in quantifiable terms."
                ),
                recommendation=(
                    "Add a numeric magnitude — a count, rate, or ratio — to quantification, for "
                    "example the number of affected parts out of the number inspected."
                ),
            )
        )

    five_w_two_h_payload: dict[str, Any] | None = None
    if discipline.method_used == "5W2H":
        answers = _five_w_two_h_answers(discipline)
        missing = [question for question, answer in answers if answer is None]
        five_w_two_h_payload = {
            "answered": [question for question, answer in answers if answer is not None],
            "missing": missing,
            "complete": not missing,
        }
        if missing:
            findings.append(
                D2Finding(
                    code="METHOD_5W2H_DESCRIPTION_INCOMPLETE",
                    severity="error",
                    message=(
                        "method_used declares 5W2H, but the problem description leaves "
                        f"{len(missing)} of the seven AIAG CQI-20 Figure 12 problem "
                        "identification questions unanswered: " + ", ".join(missing) + " "
                        "(RULE-8D-D2-003)."
                    ),
                    recommendation=(
                        "Answer the outstanding Figure 12 question(s) in the matching w2h_* "
                        "field(s) before claiming a 5W2H problem description, or set "
                        "method_used to the method actually used."
                    ),
                )
            )

    scoping_payload: dict[str, Any] | None = None
    if is_is_not is None:
        findings.append(
            D2Finding(
                code="IS_IS_NOT_NOT_PROVIDED",
                severity="warning",
                message=(
                    "No Is/Is-Not scoping data was supplied, so only the problem-statement stage "
                    "of D2 could be assessed; the problem-description stage is established by "
                    "determining what, where, when and how big using the Is / Is Not form "
                    "(RULE-8D-D2-002)."
                ),
                recommendation=(
                    "Supply an Is/Is-Not matrix scoping the problem across the four "
                    "Kepner-Tregoe dimensions (WHAT, WHERE, WHEN, EXTENT)."
                ),
            )
        )
    else:
        scoping = scope_is_is_not(is_is_not, problem_statement=problem_statement)
        scoping_payload = scoping.to_dict()
        # `scope_is_is_not` pairs every warning it raises with a recommendation, so a non-ACCEPT
        # verdict always carries at least one recommendation; no fallback branch is reachable.
        if scoping.verdict == "REJECT":
            findings.append(
                D2Finding(
                    code="IS_IS_NOT_SCOPING_REJECTED",
                    severity="error",
                    message=(
                        "Is/Is-Not scoping was rejected: " + "; ".join(scoping.warnings)
                    ),
                    recommendation=scoping.recommendations[0],
                )
            )
        elif scoping.verdict == "WARNING":
            findings.append(
                D2Finding(
                    code="IS_IS_NOT_SCOPING_INCOMPLETE",
                    severity="warning",
                    message=(
                        "Is/Is-Not scoping is incomplete: " + "; ".join(scoping.warnings)
                    ),
                    recommendation=scoping.recommendations[0],
                )
            )
        recommendations.extend(scoping.recommendations)

    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    if any(f.severity == "error" for f in findings):
        verdict, valid = "REJECT", False
    elif any(f.severity == "warning" for f in findings):
        verdict, valid = "WARNING", True
    else:
        verdict, valid = "ACCEPT", True

    return D2ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        problem_statement=problem_statement,
        findings=findings,
        is_is_not=scoping_payload,
        five_w_two_h=five_w_two_h_payload,
        recommendations=_dedupe([f.recommendation for f in findings] + recommendations),
    )

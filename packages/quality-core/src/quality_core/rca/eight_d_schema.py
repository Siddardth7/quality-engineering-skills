"""
eight_d_schema.py
8D Problem Solving — report envelope, the nine discipline models, and ingest validators.

Extends :mod:`quality_core.rca` with the 8D report (``EightDReport``) and its nine discipline
slots (``D0Discipline`` .. ``D8Discipline``), plus the JSON trust boundary
(``validate_eight_d`` / ``load_eight_d_json`` / ``load_eight_d_json_from_path``) and four CSV
``TableSchema`` sub-tables for the naturally tabular sub-structures: the D1 team roster, D3
containment measures, D5 corrective-action candidates, and D7 documentation updates.

**Data shape and ingest only.** There is no state machine here, no discipline-advancement API,
and no cross-discipline gate enforcement — those live in the future ``rca/eight_d.py`` (E2,
#205) and onward. The ``is_verified`` / ``is_documented`` properties defined below exist so that
engine has something to *read*; they never block anything themselves. ``D3Discipline``'s
recorded ``linked_ncr_validation`` outcome and its shared evaluator ``_linked_ncr_deficiency``
follow the same split: this module records and evaluates the outcome, ``rca/eight_d.py`` decides
what to refuse on the strength of it.

Standards basis: the Ford Motor Company *Global 8D (G8D) Problem Solving Manual* and AIAG CQI-20
*Effective Problem Solving Practitioner Guide* (2nd Edition, 2018). Every citation this module
relies on was landed in ``rca/CITATIONS.tsv`` and ``rca/ASSUMPTIONS_LOG.md`` by E0 (#218) and,
for the ``D2Discipline`` 5W2H answer fields, by E4 (#207, ``RULE-8D-D2-003``); this module
authors **no** citation rows of its own. Two data-shape judgment calls — the D8
``WARNING`` closure policy and the ``EffectivenessVerification`` field set — are this platform's
own and are recorded as Process Design Decisions #4 and #5 in ``rca/ASSUMPTIONS_LOG.md``, not as
standards requirements.
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass
from typing import Annotated, Any, BinaryIO, Literal, cast

import pandas as pd
import pydantic

from quality_core.io import IngestError, TableSchema, load_table, load_table_from_path
from quality_core.io.validate import DEFAULT_MAX_UPLOAD_BYTES, clean_pydantic_message
from quality_core.rca.five_why import FiveWhyValidationResult
from quality_core.schema._base import find_duplicates

__all__ = [
    "CONTAINMENT_ACTION_SCHEMA",
    "CORRECTIVE_ACTION_CANDIDATE_SCHEMA",
    "DOCUMENTATION_UPDATE_SCHEMA",
    "TEAM_MEMBER_SCHEMA",
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
    "DocumentationUpdate",
    "DocumentationUpdateList",
    "EffectivenessVerification",
    "EightDReport",
    "EightDDiscipline",
    "EightDStatus",
    "EscapePointFinding",
    "FiveWhyLegType",
    "FiveWhyVerdict",
    "ImplementedAction",
    "LinkedNCRValidation",
    "RootCauseFinding",
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
]

# ==============================================================================
# 1. Shared types and helpers
# ==============================================================================

#: Mirrors ``quality_core.rca.five_why.FiveWhyValidationResult.verdict`` exactly. Kept as a local
#: alias rather than an import because ``five_why.py`` exposes no standalone type for it; a
#: regression test pins the two definitions together so a change there fails loudly here.
FiveWhyVerdict = Literal["ACCEPT", "WARNING", "REJECT"]

#: Mirrors the three leg values named — but never formalized as a ``Literal`` — in
#: ``five_why.validate_five_why_chain``'s docstring. Formalized here for this module's own use
#: only; ``five_why.py`` is untouched.
FiveWhyLegType = Literal["occurrence", "escape", "systemic"]

#: No published standard defines a status vocabulary for an 8D report; this small set is this
#: platform's own, mirroring the ``sqe/scar.py`` ``ScarStatus`` precedent (which declares the same
#: "no published standard" position).
EightDStatus = Literal["OPEN", "CLOSED", "CANCELLED"]

#: Active problem-solving discipline, kept separate from the report lifecycle status.
EightDDiscipline = Literal["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

_ClosureDeficiencyCode = Literal[
    "D8_MISSING",
    "ROOT_CAUSE_VALIDATION_MISSING",
    "ROOT_CAUSE_VERDICT_MISMATCH",
    "ROOT_CAUSE_REJECTED",
    "WARNING_OVERRIDE_MISSING",
    "CONTAINMENT_NOT_VERIFIED",
    "PCA_NOT_VERIFIED",
    "PREVENTION_UPDATE_MISSING",
]


@dataclass(frozen=True)
class _ClosureDeficiency:
    """One machine-readable failure from the shared closure evidence boundary."""

    code: _ClosureDeficiencyCode
    message: str


def _na_to_none(value: Any) -> Any:
    """Normalize a missing cell to ``None``, tolerating array-like values.

    Mirrors ``io.validate._na_to_none`` (private there, hence copied rather than imported).
    ``rca/schema.py`` inlines a bare ``pd.isna(v)`` in its ``validate_*`` comprehensions, which
    raises "truth value of an array is ambiguous" whenever a value is a multi-element list. The
    8D dict entry paths pass exactly that — a list-valued ``rows`` key — so the guarded form is
    required here, not optional.
    """
    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        # pd.isna on an array-like cell returns an array; treat the value as present.
        return value


def _clean_record(mapping: dict[str, Any]) -> dict[str, Any]:
    """Apply :func:`_na_to_none` across one record before handing it to a row model."""
    return {key: _na_to_none(value) for key, value in mapping.items()}


def _reject_blank(v: object) -> object:
    """Strip a required string field and reject a blank/whitespace-only one; pass non-strings."""
    if isinstance(v, str) and not v.strip():
        raise ValueError("must not be blank or whitespace-only")
    return v.strip() if isinstance(v, str) else v


def _blank_to_none(v: object) -> object:
    """Normalize an optional string field: blank/whitespace-only becomes ``None``, else strip."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return v.strip() if isinstance(v, str) else v


def _parse_date_lenient(v: object) -> object:
    """Parse an optional date leniently: unparseable or absent resolves to ``None``, never raises.

    Local copy of the ``sqe/schema.py`` helper of the same name — ``rca`` must not import from
    ``sqe`` (imports go downward only, and ``sqe`` already imports from ``rca``).
    """
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, datetime.date):
        return v
    try:
        return pd.to_datetime(cast("Any", v)).date()
    except (ValueError, TypeError):
        return None


class EffectivenessVerification(pydantic.BaseModel):
    """A recorded, evidence-based effectiveness determination.

    Deliberately not a bare boolean: Ford Global 8D (D3, D6) and AIAG CQI-20 describe
    containment and corrective actions as *verified effective*, not merely marked done, so the
    record carries who verified it, when, the evidence behind the determination, and the
    determination itself. ``is_effective`` may be ``False`` — a verification event whose
    conclusion was "this does not work" is a real result and must not collapse to "verified".

    Reused by both ``ContainmentAction`` (D3) and ``ImplementedAction`` (D6): the same underlying
    act applied to two different subjects. The specific four-field shape is this platform's
    engineering translation, recorded as Process Design Decision #5 in ``ASSUMPTIONS_LOG.md``;
    no manual mandates these fields by name.
    """

    verified_by: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    verified_date: datetime.date
    evidence: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    is_effective: bool

    @pydantic.field_validator("verified_by", "evidence", mode="before")
    @classmethod
    def _reject_blank_fields(cls, v: object) -> object:
        return _reject_blank(v)


# ==============================================================================
# 2. D0 — Emergency Response Action readiness
# ==============================================================================


class D0Discipline(pydantic.BaseModel):
    """Emergency Response Action (ERA) readiness precondition (Ford Global 8D, D0)."""

    era_required: bool
    era_description: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    era_implemented_date: datetime.date | None = None
    era_verification: EffectivenessVerification | None = None

    @pydantic.field_validator("era_description", mode="before")
    @classmethod
    def _normalize_era_description(cls, v: object) -> object:
        return _blank_to_none(v)

    @pydantic.field_validator("era_implemented_date", mode="before")
    @classmethod
    def _parse_era_date(cls, v: object) -> object:
        return _parse_date_lenient(v)

    @pydantic.model_validator(mode="after")
    def _require_description_when_required(self) -> "D0Discipline":
        if self.era_required and not self.era_description:
            raise ValueError("era_description is required when era_required is True")
        return self


# ==============================================================================
# 3. D1 — Team formation
# ==============================================================================


class TeamMember(pydantic.BaseModel):
    """One 8D team roster row. CSV-loadable via :data:`TEAM_MEMBER_SCHEMA`."""

    name: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    role: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None

    @pydantic.field_validator("name", mode="before")
    @classmethod
    def _reject_blank_name(cls, v: object) -> object:
        return _reject_blank(v)

    @pydantic.field_validator("role", mode="before")
    @classmethod
    def _normalize_role(cls, v: object) -> object:
        return _blank_to_none(v)


class D1Discipline(pydantic.BaseModel):
    """Team completeness — a Champion and a Designated Team Leader (Ford Global 8D, D1)."""

    champion: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    team_leader: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    members: list[TeamMember] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("champion", "team_leader", mode="before")
    @classmethod
    def _reject_blank_fields(cls, v: object) -> object:
        return _reject_blank(v)


# ==============================================================================
# 4. D2 — Problem description
# ==============================================================================


class D2Discipline(pydantic.BaseModel):
    """Problem description — "what is wrong with what", in quantifiable terms (Ford 8D, D2).

    ``method_used`` is informational metadata only: it names the scoping technique used and
    deliberately does not embed an ``IsIsNotMatrix`` or ``FiveWhyChain`` object, so this module
    never becomes a second source of truth for data ``quality_core.rca`` already owns.

    The seven ``w2h_*`` fields hold the answers to CQI-20 Figure 12's "Problem Identification
    Questions" — Who?, What?, When?, Where?, Why?, How?, How Many? — the enumeration behind the
    5W2H tool name (``RULE-8D-D2-003``). They carry a prefix because a Python identifier cannot
    begin with the ``5`` of "5W2H", and because ``w2h_what`` must not be read as the required
    ``what_is_wrong`` / ``with_what`` statement fields. **All seven are optional here**: a
    partially answered 5W2H is a normal intermediate state and must stay representable. Judging
    completeness belongs to ``eight_d_disciplines.validate_d2_problem_description``, not to this
    model.
    """

    what_is_wrong: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    with_what: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    quantification: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    method_used: Literal["5W2H", "GANTT", "IS_IS_NOT", "OTHER"] | None = None
    w2h_who: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    w2h_what: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    w2h_when: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    w2h_where: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    w2h_why: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    w2h_how: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    w2h_how_many: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None

    @pydantic.field_validator("what_is_wrong", "with_what", "quantification", mode="before")
    @classmethod
    def _reject_blank_fields(cls, v: object) -> object:
        return _reject_blank(v)

    @pydantic.field_validator(
        "w2h_who",
        "w2h_what",
        "w2h_when",
        "w2h_where",
        "w2h_why",
        "w2h_how",
        "w2h_how_many",
        mode="before",
    )
    @classmethod
    def _normalize_w2h_answers(cls, v: object) -> object:
        return _blank_to_none(v)


# ==============================================================================
# 5. D3 — Interim containment
# ==============================================================================


class ContainmentAction(pydantic.BaseModel):
    """One interim containment measure (Ford Global 8D, D3).

    CSV-loadable via :data:`CONTAINMENT_ACTION_SCHEMA` for its ``description`` and
    ``implemented_date`` only — ``verification`` is a later, single event recorded through JSON
    or direct construction, never through the bulk-upload CSV.
    """

    description: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    implemented_date: datetime.date
    verification: EffectivenessVerification | None = None

    @pydantic.field_validator("description", mode="before")
    @classmethod
    def _reject_blank_description(cls, v: object) -> object:
        return _reject_blank(v)

    @pydantic.model_validator(mode="after")
    def _verified_not_before_implemented(self) -> "ContainmentAction":
        if (
            self.verification is not None
            and self.verification.verified_date < self.implemented_date
        ):
            raise ValueError("verification.verified_date cannot be before implemented_date")
        return self

    @property
    def is_verified(self) -> bool:
        """True only when a verification record exists *and* concluded the action is effective."""
        return self.verification is not None and self.verification.is_effective


class LinkedNCRValidation(pydantic.BaseModel):
    """The recorded outcome of validating the nonconformity evidence linked to D3.

    Not the evidence itself, and not a second NCR validator: this is the *result* of handing
    linked Nonconformance Record evidence to ``quality_core.ncr.schema.validate_ncr``, recorded
    on the report so the D3 to D4 gate can read a verdict it never has to re-derive. ``findings``
    carries that sub-engine's own message text verbatim; an invalid outcome must carry at least
    one, so a recorded rejection can never block a transition without saying why.

    ``validate_d3_containment`` (``rca/eight_d_disciplines.py``) produces this record from live
    evidence; a caller stores it on ``D3Discipline.linked_ncr_validation``. Recording
    nonconformity evidence alongside interim containment is this platform's traceability
    convention, not a manual requirement — Process Design Decision #8 in ``ASSUMPTIONS_LOG.md``.
    """

    is_valid: bool
    record_count: Annotated[int, pydantic.Field(ge=0)] = 0
    findings: list[str] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _require_findings_when_invalid(self) -> "LinkedNCRValidation":
        if not self.is_valid and not self.findings:
            raise ValueError(
                "an invalid linked NCR validation must carry at least one finding message"
            )
        return self


class D3Discipline(pydantic.BaseModel):
    """Interim Containment Action(s), defined, verified, and implemented (Ford 8D, D3).

    ``linked_ncr_validation`` is optional so a D3 record whose nonconformity evidence has not
    been validated yet stays representable; an absent outcome blocks nothing. A *recorded
    invalid* outcome does block the D3 to D4 transition, through :func:`_linked_ncr_deficiency`.
    """

    actions: list[ContainmentAction] = pydantic.Field(default_factory=list)
    linked_ncr_validation: LinkedNCRValidation | None = None

    @pydantic.model_validator(mode="after")
    def _require_at_least_one_action(self) -> "D3Discipline":
        if not self.actions:
            raise ValueError("D3Discipline must contain at least one containment action")
        return self

    @property
    def is_verified(self) -> bool:
        """True only when EVERY containment action is verified effective.

        One of the two things the D3 to D4 gate reads (the other being
        ``linked_ncr_validation``, through :func:`_linked_ncr_deficiency`); the gate itself —
        refusing the transition — is E2's job (#205), not this module's.
        """
        return all(a.is_verified for a in self.actions)


@dataclass(frozen=True)
class _LinkedNCRDeficiency:
    """One machine-readable failure from the shared D3 linked-NCR evidence boundary."""

    code: Literal["LINKED_NCR_INVALID"]
    message: str


def _linked_ncr_deficiency(
    validation: LinkedNCRValidation | None,
) -> _LinkedNCRDeficiency | None:
    """Answer, in one place, whether D3's linked nonconformity evidence is acceptable.

    Both consumers of that question — the advisory ``validate_d3_containment`` engine and
    ``transition_eight_d``'s D3 to D4 gate — call this evaluator instead of each keeping their
    own copy, mirroring how ``_closure_evidence_deficiencies`` serves both the CLOSED-report
    model validator and the D8 gate. Two copies could drift; one cannot.

    Returns ``None`` (acceptable) both when no outcome has been recorded — not-yet-linked
    evidence is a normal in-progress state that blocks nothing — and when the recorded outcome
    is valid.
    """
    if validation is None or validation.is_valid:
        return None
    return _LinkedNCRDeficiency(
        "LINKED_NCR_INVALID",
        "The linked Nonconformance Record evidence is invalid: "
        + "; ".join(validation.findings)
        + ".",
    )


# ==============================================================================
# 6. D4 — Root cause and escape point
# ==============================================================================


class CandidateCauseTest(pydantic.BaseModel):
    """One tested candidate cause, with the test data behind the verdict (Ford 8D, D4)."""

    description: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    test_data: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    result: Literal["CONFIRMED", "ELIMINATED"]

    @pydantic.field_validator("description", "test_data", mode="before")
    @classmethod
    def _reject_blank_fields(cls, v: object) -> object:
        return _reject_blank(v)


class RootCauseFinding(pydantic.BaseModel):
    """The proven root cause (Ford Global 8D, D4).

    ``five_why_verdict`` is populated by the *caller* (the future D4 engine, E6/#209) after it
    calls ``quality_core.rca.five_why.validate_five_why_chain``. This model never calls that
    validator itself and never authors a root cause — the root-cause-authorship invariant already
    recorded as Process Design Decision #1 in ``ASSUMPTIONS_LOG.md``.
    """

    statement: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    verification_evidence: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    five_why_leg_type: FiveWhyLegType | None = None
    five_why_verdict: FiveWhyVerdict | None = None

    @pydantic.field_validator("statement", "verification_evidence", mode="before")
    @classmethod
    def _reject_blank_fields(cls, v: object) -> object:
        return _reject_blank(v)


class EscapePointFinding(pydantic.BaseModel):
    """Where in the process the root cause's effects should have been caught (Ford 8D, D4)."""

    statement: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    verification_evidence: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    five_why_leg_type: FiveWhyLegType | None = None
    five_why_verdict: FiveWhyVerdict | None = None

    @pydantic.field_validator("statement", "verification_evidence", mode="before")
    @classmethod
    def _reject_blank_fields(cls, v: object) -> object:
        return _reject_blank(v)


class D4Discipline(pydantic.BaseModel):
    """Root cause AND escape point, both isolated and verified (Ford Global 8D, D4).

    No cross-check ties ``root_cause.statement`` to a ``CONFIRMED`` entry in
    ``candidate_causes_tested``: that would require fuzzy string matching with no standards
    basis behind the matching rule.
    """

    candidate_causes_tested: list[CandidateCauseTest] = pydantic.Field(default_factory=list)
    root_cause: RootCauseFinding
    escape_point: EscapePointFinding


# ==============================================================================
# 7. D5 — Permanent corrective action selection
# ==============================================================================


class CorrectiveActionCandidate(pydantic.BaseModel):
    """One permanent corrective action candidate (Ford Global 8D, D5).

    Targets either the root cause or the escape point; the manual requires a selected PCA for
    each. CSV-loadable via :data:`CORRECTIVE_ACTION_CANDIDATE_SCHEMA`.
    """

    action_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    target: Literal["ROOT_CAUSE", "ESCAPE_POINT"]
    description: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    selection_criteria: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    verified_no_undesirable_effects: bool = False
    verification_notes: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None

    @pydantic.field_validator("action_id", "description", "selection_criteria", mode="before")
    @classmethod
    def _reject_blank_fields(cls, v: object) -> object:
        return _reject_blank(v)

    @pydantic.field_validator("verification_notes", mode="before")
    @classmethod
    def _normalize_notes(cls, v: object) -> object:
        return _blank_to_none(v)


def _check_candidate_coverage(label: str, candidates: list[CorrectiveActionCandidate]) -> None:
    """Enforce the D5 invariant: both targets covered, no duplicate ``action_id``.

    Shared by ``D5Discipline`` and ``CorrectiveActionCandidateList`` so the two entry paths
    (direct/JSON construction and CSV upload) enforce one identical rule rather than two copies
    of it that can drift apart. ``label`` names the model in the message.
    """
    targets = {c.target for c in candidates}
    missing = {"ROOT_CAUSE", "ESCAPE_POINT"} - targets
    if missing:
        raise ValueError(f"{label} must include a candidate for each of: {sorted(missing)}")
    dupes = find_duplicates(c.action_id for c in candidates)
    if dupes:
        raise ValueError(f"duplicate action_id values found: {dupes}")


class D5Discipline(pydantic.BaseModel):
    """PCA selection for both the root cause and the escape point (Ford Global 8D, D5)."""

    candidates: list[CorrectiveActionCandidate] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _require_both_targets_and_unique_ids(self) -> "D5Discipline":
        if not self.candidates:
            raise ValueError("D5Discipline must contain at least one corrective action candidate")
        _check_candidate_coverage("D5Discipline", self.candidates)
        return self


# ==============================================================================
# 8. D6 — Implement the PCAs, remove the ICA
# ==============================================================================


class ImplementedAction(pydantic.BaseModel):
    """One PCA as implemented and validated (Ford Global 8D, D6).

    ``corrective_action_id`` is expected to reference a ``D5Discipline.candidates[].action_id``,
    but that cross-discipline reference is not enforced here — E1 is schema-only and E2 (#205)
    owns cross-discipline consistency.
    """

    corrective_action_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    implemented_date: datetime.date
    verification: EffectivenessVerification | None = None
    monitoring_notes: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None

    @pydantic.field_validator("corrective_action_id", mode="before")
    @classmethod
    def _reject_blank_id(cls, v: object) -> object:
        return _reject_blank(v)

    @pydantic.field_validator("monitoring_notes", mode="before")
    @classmethod
    def _normalize_notes(cls, v: object) -> object:
        return _blank_to_none(v)

    @property
    def is_verified(self) -> bool:
        """True only when a verification record exists *and* concluded the action is effective."""
        return self.verification is not None and self.verification.is_effective


class D6Discipline(pydantic.BaseModel):
    """PCAs implemented and validated; the ICA removed once effectiveness is verified (D6).

    ``_removal_requires_verified_actions`` reads only this model's own fields — it never reaches
    into ``D3Discipline``. It is the structural encoding of CQI-20's "provisions for containment
    should stay in place until effectiveness of the corrective actions are verified"
    (``RULE-8D-GATE-CONTAINMENT``), expressed as a single-model invariant rather than a
    cross-discipline gate.
    """

    implemented_actions: list[ImplementedAction] = pydantic.Field(default_factory=list)
    interim_containment_removed_date: datetime.date | None = None

    @property
    def is_verified(self) -> bool:
        """True only when EVERY implemented action is verified effective.

        Read directly by ``eight_d_disciplines.validate_d6_implementation_validation`` and by the
        D8 to CLOSED closure boundary (:func:`_closure_evidence_deficiencies`) — never recomputed
        independently by either consumer, mirroring ``D3Discipline.is_verified``.
        ``implemented_actions`` is guaranteed non-empty by
        ``_removal_requires_verified_actions``, so the vacuous-truth case cannot arise on a
        validated instance.
        """
        return all(a.is_verified for a in self.implemented_actions)

    @pydantic.model_validator(mode="after")
    def _removal_requires_verified_actions(self) -> "D6Discipline":
        if not self.implemented_actions:
            raise ValueError("D6Discipline must contain at least one implemented action")
        if self.interim_containment_removed_date is not None and not all(
            a.is_verified for a in self.implemented_actions
        ):
            raise ValueError(
                "interim_containment_removed_date cannot be set until every implemented_action "
                "is verified effective (CQI-20: containment stays in place until corrective-"
                "action effectiveness is verified; RULE-8D-GATE-CONTAINMENT)."
            )
        return self


# ==============================================================================
# 9. D7 — Prevent recurrence
# ==============================================================================


class DocumentationUpdate(pydantic.BaseModel):
    """One artifact updated as part of D7 prevention. CSV-loadable via
    :data:`DOCUMENTATION_UPDATE_SCHEMA`."""

    artifact_type: Literal["FMEA", "CONTROL_PLAN", "PROCESS_FLOW", "WORK_INSTRUCTION", "OTHER"]
    artifact_reference: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    updated_date: datetime.date
    updated_by: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None

    @pydantic.field_validator("artifact_reference", mode="before")
    @classmethod
    def _reject_blank_reference(cls, v: object) -> object:
        return _reject_blank(v)

    @pydantic.field_validator("updated_by", mode="before")
    @classmethod
    def _normalize_updated_by(cls, v: object) -> object:
        return _blank_to_none(v)


class D7Discipline(pydantic.BaseModel):
    """Modify the systems, policies, and procedures that permitted the problem (Ford 8D, D7)."""

    systemic_changes_description: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    documentation_updates: list[DocumentationUpdate] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("systemic_changes_description", mode="before")
    @classmethod
    def _reject_blank_description(cls, v: object) -> object:
        return _reject_blank(v)

    @property
    def is_documented(self) -> bool:
        """True iff at least one documentation update is recorded.

        This is the data the D7 prevention gate reads. An empty list (``False``) is a legitimate
        in-progress state, not an error — no non-empty requirement is placed on
        ``documentation_updates`` itself.
        """
        return bool(self.documentation_updates)


# ==============================================================================
# 10. D8 — Recognize the team and close
# ==============================================================================


class WarningOverride(pydantic.BaseModel):
    """Recorded human override permitting D8 closure on a ``WARNING``-verdict 5-Why chain.

    A Process Design Decision, not a standards clause — see ``ASSUMPTIONS_LOG.md`` Process
    Design Decision #4. No manual defines closure eligibility for a marginal (non-``REJECT``,
    non-``ACCEPT``) causal chain, so this platform requires the judgment call to be explicit,
    attributable, and justified rather than silently defaulting either way.
    """

    approved_by: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    justification: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    override_date: datetime.date

    @pydantic.field_validator("approved_by", "justification", mode="before")
    @classmethod
    def _reject_blank_fields(cls, v: object) -> object:
        return _reject_blank(v)


class D8Discipline(pydantic.BaseModel):
    """Recognize the team's contributions and close out the documentation (Ford 8D, D8).

    Closure rules, enforced within this single model (the cross-report gate stays E2's job):

    - ``REJECT`` linked 5-Why verdict hard-blocks closure (``RULE-8D-GATE-CLOSURE``).
    - ``ACCEPT`` closes without additional evidence.
    - ``WARNING`` closes only with a recorded ``warning_override`` — a platform heuristic
      (Process Design Decision #4), not a standards requirement.
    """

    team_recognition_notes: Annotated[str, pydantic.Field(min_length=1, max_length=2000)]
    documentation_reviewed: bool = False
    documentation_review_date: datetime.date | None = None
    documentation_reviewed_by: Annotated[
        str | None, pydantic.Field(default=None, max_length=200)
    ] = None
    linked_five_why_verdict: FiveWhyVerdict
    warning_override: WarningOverride | None = None
    closure_approved: bool = False
    closure_approved_by: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None
    closure_approved_date: datetime.date | None = None

    @pydantic.field_validator("team_recognition_notes", mode="before")
    @classmethod
    def _reject_blank_notes(cls, v: object) -> object:
        return _reject_blank(v)

    @pydantic.field_validator("documentation_reviewed_by", "closure_approved_by", mode="before")
    @classmethod
    def _normalize_optional_names(cls, v: object) -> object:
        return _blank_to_none(v)

    @pydantic.model_validator(mode="after")
    def _enforce_closure_rules(self) -> "D8Discipline":
        if not self.closure_approved:
            return self
        if not self.closure_approved_by:
            raise ValueError("closure_approved_by is required when closure_approved is True")
        if self.closure_approved_date is None:
            raise ValueError("closure_approved_date is required when closure_approved is True")
        if self.linked_five_why_verdict == "REJECT":
            raise ValueError(
                "D8 closure cannot be approved while linked_five_why_verdict is REJECT "
                "(RULE-8D-GATE-CLOSURE); resolve the causal chain before closing."
            )
        if self.linked_five_why_verdict == "WARNING" and self.warning_override is None:
            raise ValueError(
                "D8 closure on a WARNING-verdict 5-Why chain requires a recorded "
                "warning_override (approved_by, justification, override_date) — see "
                "ASSUMPTIONS_LOG.md Process Design Decision #4. This is a platform heuristic, "
                "not a standards requirement."
            )
        return self


# ==============================================================================
# 11. Report envelope
# ==============================================================================


class EightDReport(pydantic.BaseModel):
    """The 8D report envelope: identity, dates, status, and the nine discipline slots.

    Every ``d0``..``d8`` slot is optional: a report is built up progressively, and E1 does not
    enforce fill order, nor that a later discipline stays empty until an earlier one is done.
    ``status`` records the lifecycle while ``current_discipline`` records D0-D8 progress. OPEN
    and CANCELLED reports retain their current discipline. A directly constructed CLOSED report
    must satisfy the same provenance-bearing closure evidence boundaries as the E2 engine.
    """

    report_id: Annotated[str, pydantic.Field(min_length=1, max_length=200)]
    initiated_date: datetime.date
    target_completion_date: datetime.date | None = None
    closed_date: datetime.date | None = None
    status: EightDStatus = "OPEN"
    current_discipline: EightDDiscipline = "D0"
    root_cause_validation: FiveWhyValidationResult | None = None

    d0: D0Discipline | None = None
    d1: D1Discipline | None = None
    d2: D2Discipline | None = None
    d3: D3Discipline | None = None
    d4: D4Discipline | None = None
    d5: D5Discipline | None = None
    d6: D6Discipline | None = None
    d7: D7Discipline | None = None
    d8: D8Discipline | None = None

    @pydantic.field_validator("report_id", mode="before")
    @classmethod
    def _reject_blank_report_id(cls, v: object) -> object:
        return _reject_blank(v)

    @property
    def team(self) -> D1Discipline | None:
        """Read-only view of the report's team: D1 *is* the team-formation discipline.

        An alias, not a second copy of the data.
        """
        return self.d1

    @pydantic.model_validator(mode="after")
    def _check_date_ordering(self) -> "EightDReport":
        if (
            self.target_completion_date is not None
            and self.target_completion_date < self.initiated_date
        ):
            raise ValueError("target_completion_date cannot be before initiated_date")
        if self.closed_date is not None and self.closed_date < self.initiated_date:
            raise ValueError("closed_date cannot be before initiated_date")
        if self.status == "CLOSED":
            if self.current_discipline != "D8":
                raise ValueError("a CLOSED report must have current_discipline D8")
            deficiencies = _closure_evidence_deficiencies(self)
            if deficiencies:
                raise ValueError(deficiencies[0].message)
        return self


def _closure_evidence_deficiencies(report: EightDReport) -> tuple[_ClosureDeficiency, ...]:
    """Evaluate the complete closure evidence contract for every closure entry path."""
    deficiencies: list[_ClosureDeficiency] = []
    discipline = report.d8
    validation = report.root_cause_validation
    if discipline is None:
        deficiencies.append(_ClosureDeficiency("D8_MISSING", "a CLOSED report requires D8"))
    if validation is None:
        deficiencies.append(
            _ClosureDeficiency(
                "ROOT_CAUSE_VALIDATION_MISSING",
                "a CLOSED report requires provenance-bearing root_cause_validation",
            )
        )
    if discipline is not None and validation is not None:
        if validation.verdict != discipline.linked_five_why_verdict:
            deficiencies.append(
                _ClosureDeficiency(
                    "ROOT_CAUSE_VERDICT_MISMATCH",
                    "root_cause_validation.verdict must match d8.linked_five_why_verdict",
                )
            )
        if validation.verdict == "REJECT" or not validation.valid:
            deficiencies.append(
                _ClosureDeficiency(
                    "ROOT_CAUSE_REJECTED",
                    "a CLOSED report requires a valid, non-REJECT root_cause_validation",
                )
            )
        if validation.verdict == "WARNING" and discipline.warning_override is None:
            deficiencies.append(
                _ClosureDeficiency(
                    "WARNING_OVERRIDE_MISSING",
                    "a CLOSED report with a WARNING verdict requires warning_override",
                )
            )
    if report.d3 is None or not report.d3.is_verified:
        deficiencies.append(
            _ClosureDeficiency(
                "CONTAINMENT_NOT_VERIFIED",
                "a CLOSED report requires verified-effective D3 containment",
            )
        )
    if report.d6 is None or not report.d6.is_verified:
        deficiencies.append(
            _ClosureDeficiency(
                "PCA_NOT_VERIFIED",
                "a CLOSED report requires verified-effective D6 permanent corrective actions",
            )
        )
    if report.d7 is None or not any(
        update.artifact_type in {"FMEA", "CONTROL_PLAN"}
        for update in report.d7.documentation_updates
    ):
        deficiencies.append(
            _ClosureDeficiency(
                "PREVENTION_UPDATE_MISSING",
                "a CLOSED report requires a D7 FMEA or Control Plan update",
            )
        )
    return tuple(deficiencies)


# ==============================================================================
# 12. JSON trust boundary
# ==============================================================================


def validate_eight_d(data: Any) -> EightDReport:
    """Validate untrusted 8D report input (``EightDReport`` or ``dict``) at the trust boundary.

    Unlike the flat RCA tools, an 8D report is one nested object rather than a table of repeated
    rows, so there is deliberately no DataFrame / list-of-dicts branch here.

    Raises
    ------
    pydantic.ValidationError
        On any constraint violation.
    TypeError
        If ``data`` is not an ``EightDReport`` or a ``dict``.
    """
    if isinstance(data, EightDReport):
        return data
    if isinstance(data, dict):
        return EightDReport(**cast("dict[str, Any]", data))
    raise TypeError(f"Expected EightDReport or dict, got {type(data).__name__}")


def _format_eight_d_error(exc: pydantic.ValidationError) -> str:
    """Turn the first pydantic error into a clear, user-safe message."""
    msg = clean_pydantic_message(str(exc.errors()[0].get("msg", "invalid report")))
    return f"8D report is invalid: {msg}."


def load_eight_d_json(
    source: bytes | bytearray | BinaryIO,
    *,
    max_bytes: int | None = DEFAULT_MAX_UPLOAD_BYTES,
) -> EightDReport:
    """Read a JSON 8D report from raw bytes or a binary file-like, and validate it.

    Fail-closed, mirroring ``io.validate.read_table``'s ``Source`` contract: never a
    ``str``/``os.PathLike``, because a bare ``str`` is ambiguous between "JSON text" and "a
    path" — use :func:`load_eight_d_json_from_path` for a trusted local path. Reads at most
    ``max_bytes + 1`` bytes, so the size ceiling is enforced before the full document is parsed
    even against an unbounded stream.

    Raises
    ------
    IngestError
        On a ``str``/``os.PathLike`` source, an oversized source, undecodable bytes, malformed
        JSON, a JSON top level that is not an object, or a :func:`validate_eight_d` failure. All
        collapse to this single user-safe error type, exactly like ``load_five_why_csv``.
    """
    if isinstance(source, (str, os.PathLike)):
        raise IngestError(
            "A file path is not accepted here. Pass raw bytes/a binary file-like, or use "
            "load_eight_d_json_from_path() for a trusted local path."
        )
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    else:
        try:
            data = source.read(max_bytes + 1) if max_bytes is not None else source.read()
        except (OSError, AttributeError) as exc:
            raise IngestError("Could not read the 8D report source.") from exc
    if max_bytes is not None and len(data) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise IngestError(f"8D report JSON exceeds the {mb} MB limit.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestError("8D report JSON is not valid UTF-8 text.") from exc
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError(f"Could not parse the 8D report as JSON: {exc}.") from exc
    if not isinstance(parsed, dict):
        raise IngestError(
            "8D report JSON must be a single JSON object (got "
            f"{type(parsed).__name__}); this loader does not accept a list of multiple reports."
        )
    try:
        return validate_eight_d(parsed)
    except pydantic.ValidationError as exc:
        raise IngestError(_format_eight_d_error(exc)) from exc
    except TypeError as exc:
        raise IngestError(f"8D report is invalid: {exc}.") from exc


def load_eight_d_json_from_path(
    path: str | os.PathLike[str],
    *,
    max_bytes: int | None = DEFAULT_MAX_UPLOAD_BYTES,
) -> EightDReport:
    """Read a JSON 8D report file from a trusted filesystem path.

    Opens ``path`` directly in binary mode — never handed to a URL-resolving reader — then
    delegates to :func:`load_eight_d_json`.
    """
    name = os.fspath(path)
    try:
        with open(name, "rb") as fh:
            return load_eight_d_json(fh, max_bytes=max_bytes)
    except OSError as exc:
        raise IngestError(
            f"Could not read '{name}'. The file may be corrupt, empty, missing, or not a valid "
            "JSON file."
        ) from exc


# ==============================================================================
# 13. CSV sub-tables — D1 team roster
# ==============================================================================


class TeamMemberList(pydantic.BaseModel):
    """Dataset wrapper for a bulk-uploaded 8D team roster."""

    rows: list[TeamMember] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _check_non_empty(self) -> "TeamMemberList":
        if not self.rows:
            raise ValueError("TeamMemberList must contain at least one member")
        return self


TEAM_MEMBER_SCHEMA = TableSchema(
    name="8D Team Roster",
    row_model=TeamMember,
    required_columns=("name",),
    optional_columns=("role",),
    dataset_model=TeamMemberList,
    template_hint="data/eight_d_team_template.csv",
)


def load_team_members_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded team-roster ``.csv`` against :data:`TEAM_MEMBER_SCHEMA`."""
    if isinstance(source, str):
        return load_table_from_path(source, TEAM_MEMBER_SCHEMA)
    return load_table(source, TEAM_MEMBER_SCHEMA)


def validate_team_members(data: Any) -> TeamMemberList:
    """Validate untrusted team-roster input at the trust boundary.

    Accepts a ``TeamMemberList``, a DataFrame, a list of dicts/``TeamMember``s, or a dict.
    Raises :class:`pydantic.ValidationError` on a constraint violation, :class:`TypeError` on an
    unsupported type.
    """
    if isinstance(data, TeamMemberList):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            _clean_record(cast("dict[str, Any]", row)) for row in data.to_dict("records")
        ]
        return TeamMemberList(rows=[TeamMember(**rec) for rec in records])
    if isinstance(data, list):
        rows: list[TeamMember] = []
        for item in data:
            if isinstance(item, TeamMember):
                rows.append(item)
            elif isinstance(item, dict):
                clean_rec = _clean_record(cast("dict[str, Any]", item))
                rows.append(TeamMember(**clean_rec))
            else:
                raise TypeError(f"Expected TeamMember or dict in list, got {type(item).__name__}")
        return TeamMemberList(rows=rows)
    if isinstance(data, dict):
        clean_dict = _clean_record(cast("dict[str, Any]", data))
        return TeamMemberList(**clean_dict)
    raise TypeError(
        "Expected TeamMemberList, DataFrame, list of dicts/rows, or dict, got "
        f"{type(data).__name__}"
    )


# ==============================================================================
# 14. CSV sub-tables — D3 containment measures
# ==============================================================================


class ContainmentActionList(pydantic.BaseModel):
    """Dataset wrapper for bulk-uploaded interim containment measures."""

    rows: list[ContainmentAction] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _check_non_empty(self) -> "ContainmentActionList":
        if not self.rows:
            raise ValueError("ContainmentActionList must contain at least one containment action")
        return self


CONTAINMENT_ACTION_SCHEMA = TableSchema(
    name="8D Containment Actions",
    row_model=ContainmentAction,
    required_columns=("description", "implemented_date"),
    optional_columns=(),
    dataset_model=ContainmentActionList,
    template_hint="data/eight_d_containment_template.csv",
)


def load_containment_actions_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded containment ``.csv`` against
    :data:`CONTAINMENT_ACTION_SCHEMA`."""
    if isinstance(source, str):
        return load_table_from_path(source, CONTAINMENT_ACTION_SCHEMA)
    return load_table(source, CONTAINMENT_ACTION_SCHEMA)


def validate_containment_actions(data: Any) -> ContainmentActionList:
    """Validate untrusted containment-action input at the trust boundary.

    Accepts a ``ContainmentActionList``, a DataFrame, a list of dicts/``ContainmentAction``s, or
    a dict. Raises :class:`pydantic.ValidationError` on a constraint violation,
    :class:`TypeError` on an unsupported type.
    """
    if isinstance(data, ContainmentActionList):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            _clean_record(cast("dict[str, Any]", row)) for row in data.to_dict("records")
        ]
        return ContainmentActionList(rows=[ContainmentAction(**rec) for rec in records])
    if isinstance(data, list):
        rows: list[ContainmentAction] = []
        for item in data:
            if isinstance(item, ContainmentAction):
                rows.append(item)
            elif isinstance(item, dict):
                clean_rec = _clean_record(cast("dict[str, Any]", item))
                rows.append(ContainmentAction(**clean_rec))
            else:
                raise TypeError(
                    f"Expected ContainmentAction or dict in list, got {type(item).__name__}"
                )
        return ContainmentActionList(rows=rows)
    if isinstance(data, dict):
        clean_dict = _clean_record(cast("dict[str, Any]", data))
        return ContainmentActionList(**clean_dict)
    raise TypeError(
        "Expected ContainmentActionList, DataFrame, list of dicts/rows, or dict, got "
        f"{type(data).__name__}"
    )


# ==============================================================================
# 15. CSV sub-tables — D5 corrective-action candidates
# ==============================================================================


class CorrectiveActionCandidateList(pydantic.BaseModel):
    """Dataset wrapper for bulk-uploaded PCA candidates.

    Re-applies the same both-targets/unique-id invariant as ``D5Discipline`` — deliberate,
    harmless duplication so the CSV entry path and the direct/JSON entry path cannot diverge.
    """

    rows: list[CorrectiveActionCandidate] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _check_rows(self) -> "CorrectiveActionCandidateList":
        if not self.rows:
            raise ValueError(
                "CorrectiveActionCandidateList must contain at least one corrective action "
                "candidate"
            )
        _check_candidate_coverage("CorrectiveActionCandidateList", self.rows)
        return self


CORRECTIVE_ACTION_CANDIDATE_SCHEMA = TableSchema(
    name="8D Corrective Action Candidates",
    row_model=CorrectiveActionCandidate,
    required_columns=("action_id", "target", "description", "selection_criteria"),
    optional_columns=("verified_no_undesirable_effects", "verification_notes"),
    dataset_model=CorrectiveActionCandidateList,
    template_hint="data/eight_d_corrective_action_template.csv",
)


def load_corrective_action_candidates_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded PCA-candidate ``.csv`` against
    :data:`CORRECTIVE_ACTION_CANDIDATE_SCHEMA`."""
    if isinstance(source, str):
        return load_table_from_path(source, CORRECTIVE_ACTION_CANDIDATE_SCHEMA)
    return load_table(source, CORRECTIVE_ACTION_CANDIDATE_SCHEMA)


def validate_corrective_action_candidates(data: Any) -> CorrectiveActionCandidateList:
    """Validate untrusted PCA-candidate input at the trust boundary.

    Accepts a ``CorrectiveActionCandidateList``, a DataFrame, a list of
    dicts/``CorrectiveActionCandidate``s, or a dict. Raises
    :class:`pydantic.ValidationError` on a constraint violation, :class:`TypeError` on an
    unsupported type.
    """
    if isinstance(data, CorrectiveActionCandidateList):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            _clean_record(cast("dict[str, Any]", row)) for row in data.to_dict("records")
        ]
        return CorrectiveActionCandidateList(
            rows=[CorrectiveActionCandidate(**rec) for rec in records]
        )
    if isinstance(data, list):
        rows: list[CorrectiveActionCandidate] = []
        for item in data:
            if isinstance(item, CorrectiveActionCandidate):
                rows.append(item)
            elif isinstance(item, dict):
                clean_rec = _clean_record(cast("dict[str, Any]", item))
                rows.append(CorrectiveActionCandidate(**clean_rec))
            else:
                raise TypeError(
                    "Expected CorrectiveActionCandidate or dict in list, got "
                    f"{type(item).__name__}"
                )
        return CorrectiveActionCandidateList(rows=rows)
    if isinstance(data, dict):
        clean_dict = _clean_record(cast("dict[str, Any]", data))
        return CorrectiveActionCandidateList(**clean_dict)
    raise TypeError(
        "Expected CorrectiveActionCandidateList, DataFrame, list of dicts/rows, or dict, got "
        f"{type(data).__name__}"
    )


# ==============================================================================
# 16. CSV sub-tables — D7 documentation updates
# ==============================================================================


class DocumentationUpdateList(pydantic.BaseModel):
    """Dataset wrapper for bulk-uploaded D7 documentation updates.

    The non-empty check applies to the *CSV upload* path only; ``D7Discipline`` still allows an
    empty ``documentation_updates`` list via direct/JSON construction, which is the legitimate
    "D7 work has not started yet" state.
    """

    rows: list[DocumentationUpdate] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _check_non_empty(self) -> "DocumentationUpdateList":
        if not self.rows:
            raise ValueError("DocumentationUpdateList must contain at least one update")
        return self


DOCUMENTATION_UPDATE_SCHEMA = TableSchema(
    name="8D Documentation Updates",
    row_model=DocumentationUpdate,
    required_columns=("artifact_type", "artifact_reference", "updated_date"),
    optional_columns=("updated_by",),
    dataset_model=DocumentationUpdateList,
    template_hint="data/eight_d_documentation_template.csv",
)


def load_documentation_updates_csv(source: str | BinaryIO) -> pd.DataFrame:
    """Read + validate an uploaded documentation-update ``.csv`` against
    :data:`DOCUMENTATION_UPDATE_SCHEMA`."""
    if isinstance(source, str):
        return load_table_from_path(source, DOCUMENTATION_UPDATE_SCHEMA)
    return load_table(source, DOCUMENTATION_UPDATE_SCHEMA)


def validate_documentation_updates(data: Any) -> DocumentationUpdateList:
    """Validate untrusted documentation-update input at the trust boundary.

    Accepts a ``DocumentationUpdateList``, a DataFrame, a list of dicts/``DocumentationUpdate``s,
    or a dict. Raises :class:`pydantic.ValidationError` on a constraint violation,
    :class:`TypeError` on an unsupported type.
    """
    if isinstance(data, DocumentationUpdateList):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            _clean_record(cast("dict[str, Any]", row)) for row in data.to_dict("records")
        ]
        return DocumentationUpdateList(rows=[DocumentationUpdate(**rec) for rec in records])
    if isinstance(data, list):
        rows: list[DocumentationUpdate] = []
        for item in data:
            if isinstance(item, DocumentationUpdate):
                rows.append(item)
            elif isinstance(item, dict):
                clean_rec = _clean_record(cast("dict[str, Any]", item))
                rows.append(DocumentationUpdate(**clean_rec))
            else:
                raise TypeError(
                    f"Expected DocumentationUpdate or dict in list, got {type(item).__name__}"
                )
        return DocumentationUpdateList(rows=rows)
    if isinstance(data, dict):
        clean_dict = _clean_record(cast("dict[str, Any]", data))
        return DocumentationUpdateList(**clean_dict)
    raise TypeError(
        "Expected DocumentationUpdateList, DataFrame, list of dicts/rows, or dict, got "
        f"{type(data).__name__}"
    )

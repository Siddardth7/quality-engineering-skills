"""
eight_d_disciplines.py
Deterministic 8D discipline engines for D0 (Emergency Response Action readiness), D1
(team completeness), D2 (problem description), D3 (interim containment), D4 (root cause
and escape point), D5 (permanent corrective action selection), D6 (implementation and
validation), D7 (prevent recurrence) and D8 (recognize the team and close), plus
``validate_8d``, the read-only whole-report orchestrator over all of them.

Pure, post-validation checks over already-typed :mod:`quality_core.rca.eight_d_schema` models:
``validate_d0_readiness`` reads a ``D0Discipline`` and reports whether the Emergency Response
Action (ERA) is required, implemented, and verified *effective*; ``validate_d1_team`` reads a
``D1Discipline`` and reports whether the team is complete enough to proceed;
``validate_d2_problem_description`` reads a ``D2Discipline`` plus optional Is/Is-Not scoping data
and reports whether both stages of Ford 8D's D2 are covered; ``validate_d3_containment`` reads a
``D3Discipline`` plus optional linked Nonconformance Record evidence and reports whether every
interim containment action is verified effective; ``validate_d4_root_cause`` validates the
occurrence and escape 5-Why legs independently; ``validate_d5_pca_selection`` reads a
``D5Discipline`` plus the optional same-report ``D4Discipline`` and reports whether each selected
permanent corrective action is verified free of undesirable effects and traceable to a D4 finding
that was actually proven; ``validate_d6_implementation_validation`` reads a ``D6Discipline`` plus
the optional same-report ``D5Discipline`` and optional COPQ cost data and reports whether every
implemented PCA is verified effective; ``validate_d7_prevention`` reads a ``D7Discipline`` plus
the optional same-report ``D4Discipline``, optional Control Plan evidence and optional FMEA
residual-risk evidence, and reports whether the prevention change is documented in an artifact the
manual names; ``validate_d8_closure`` reads a whole ``EightDReport`` and reports whether the D8
closure record is complete *and* whether the shared closure-evidence boundary would let the report
close. All nine return a verdict on the same three-value ``ACCEPT`` / ``WARNING`` / ``REJECT``
scale the other RCA engines use, and ``validate_8d`` combines those nine verdicts with every
transition gate into one whole-report closure-readiness verdict on the same scale.

**Scope.** D0 through D8, advisory only. There is no state machine and no discipline-advancement
API here — those live in ``rca/eight_d.py``, and nothing in this module calls
``transition_eight_d`` or mutates a report. These functions take typed discipline instances only
(``validate_d8_closure`` and ``validate_8d`` take an already-typed ``EightDReport``; see the
whole-report paragraph below); the untrusted-data trust boundary is ``validate_eight_d`` in
``rca/eight_d_schema.py``, which validates D0-D8 as part of a whole ``EightDReport``. The
exceptions are the optional
untrusted-evidence arguments: ``validate_d2_problem_description``'s ``is_is_not``, handed straight
to ``quality_core.rca.is_is_not.scope_is_is_not``; ``validate_d3_containment``'s ``linked_ncr``,
handed straight to ``quality_core.ncr.schema.validate_ncr``;
``validate_d6_implementation_validation``'s ``copq_data``, handed straight to
``quality_core.copq.estimator.estimate_copq``; and ``validate_d7_prevention``'s
``control_plan_evidence`` / ``fmea_action``, handed straight to
``quality_core.controlplan.schema.validate_control_plan`` and
``quality_core.schema.action.Action`` — the modules that own those trust boundaries — with no
independent type check here.

**The optional cross-discipline arguments (D5's ``d4``, D6's ``d5``, D7's ``d4``) are a
documented, narrow exception to "one typed discipline argument per engine", and are still advisory.** #210's
acceptance criteria are explicitly cross-discipline (a D5 PCA must be traceable to D4; a D6
implemented action must name a D5 candidate), and no single-discipline argument can satisfy them.
Both arguments are same-report, already-typed models, both default to ``None``, and neither engine
calls, wraps, or duplicates ``transition_eight_d``. Neither adds a D4 to D5 or D5 to D6 gate:
"cross-discipline gate enforcement" in the sense used elsewhere in this docstring means *refusing
a state transition*, and that still happens only in ``rca/eight_d.py``. The one place E7 does
touch enforcement is the D8 to CLOSED closure boundary, where verified-effective D6 actions became
a shared ``_closure_evidence_deficiencies`` requirement (``PCA_NOT_VERIFIED``, ``PDD-8D-010``) —
one rule read by both the CLOSED-report model validator and the closure gate, never a second copy.

**D8 and ``validate_8d`` take a whole ``EightDReport``, a fourth and different exception to "one
typed discipline argument per engine" (Process Design Decision #14).** D8's substantive question —
"is this report's closure evidence complete" — is answered by the shared
``eight_d_schema._closure_evidence_deficiencies`` evaluator, which needs ``report.d8``,
``report.root_cause_validation``, ``report.d3``, ``report.d6`` and ``report.d7`` together. Taking a
bare ``D8Discipline`` plus four narrow optional arguments and rebuilding a throwaway
``EightDReport`` internally, purely to satisfy that evaluator's signature, would mean maintaining a
synthetic report that has to stay behaviourally identical to a real one — reimplementation risk for
no benefit. The report is therefore accepted directly, and the shared evaluator is *reused*, never
re-derived. ``validate_8d`` takes the report for the same reason: it is a dispatcher over every
per-discipline engine plus the gate evaluators, and every one of its inputs is a field of the
report.

**``validate_8d`` lives here, not in ``rca/eight_d.py``, and that is deliberate.** It is an
advisory, read-only orchestrator over the D0-D8 advisory engines this module already owns: it never
calls ``transition_eight_d``, never mutates a report, and returns findings rather than a new state.
``rca/eight_d.py`` frames itself as the *pure* state machine, and pulling this module's downstream
dependencies (``pandas``, ``ncr.schema``, ``controlplan.schema``, ``copq.estimator``, ``fishbone``,
``five_why``, ``is_is_not``) into it to host one advisory function would destroy that purity for no
gain. The direction of the dependency is therefore this module → ``eight_d.py``, from which
``validate_8d`` imports three private helpers (``_state``, ``_linked_ncr_reason``,
``_closure_reasons``) — the same kind of cross-module private reuse ``eight_d.py`` itself already
practises against ``eight_d_schema``'s ``_closure_evidence_deficiencies`` /
``_linked_ncr_deficiency``, and for the same reason: one definition of each rule, never two.

**D3 is an advisory pre-flight check that shares its rules with the gate.**
``validate_d3_containment`` *reads* ``D3Discipline.is_verified``, the same predicate
``rca/eight_d.py``'s D3→D4 gate reads, and never recomputes, overrides, or re-derives it. The
real state transition remains ``transition_eight_d``, which this module does not call. Linked
Nonconformance Record *evidence* stays a parameter of this function and is never a schema field,
but the *outcome* of validating it is one: this engine returns a ``LinkedNCRValidation`` record
for the caller to store on ``D3Discipline.linked_ncr_validation``, and the D3→D4 gate blocks on a
recorded invalid outcome with a ``LINKED_NCR_INVALID`` reason. Both sides ask the one shared
evaluator ``eight_d_schema._linked_ncr_deficiency`` — never two copies of the rule — so this
engine's ``REJECT`` and the gate's block cannot disagree about the same evidence. Only
``quality_core.ncr.schema.validate_ncr`` is called for that check; ``recommend_disposition`` and
``write_nonconformance`` are deliberately not invoked here.

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

**Every ``DNFinding`` carries ``citation_basis``, the finding's own answer to "what backs this
check" (E10, #213).** ``"RULE"`` means a ``RULE-8D-*`` row in ``rca/CITATIONS.tsv``, quoting an
on-box manual, backs the check; ``"PDD"`` means a numbered Process Design Decision in
``rca/ASSUMPTIONS_LOG.md`` backs it; ``"PLATFORM_UNCITED"`` means neither does. The field defaults
to ``"PLATFORM_UNCITED"`` so a forgotten value under-claims (heuristic) rather than over-claims
(standard) — every construction site in this module nevertheless sets it explicitly. The
three-value vocabulary is itself a platform presentation decision backed by no manual clause and
adds no ``CITATIONS.tsv`` row and no new ``RULE-8D-*`` id; see Process Design Decision #16 in
``rca/ASSUMPTIONS_LOG.md``, which also records the classification policy (a finding takes the
basis of the *check* that produced it; whole-discipline ``*_READY`` summaries, which aggregate
checks of mixed basis, take ``"PLATFORM_UNCITED"``). Presentation layers must read this field —
never scrape a finding's message prose for a rule id, which fails silently by omission on the
findings that name none.

Standards References:
- Ford Motor Company, Global 8D (G8D) Problem Solving Manual, Sections D0 through D4.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), team-definition step,
  problem-description step, and Figure 12 "Problem Identification Questions".

Rules applied: RULE-8D-D0, RULE-8D-D0-001..003, RULE-8D-D1, RULE-8D-D1-001..003, RULE-8D-D2,
RULE-8D-D2-001..003, RULE-8D-D3, RULE-8D-D4, RULE-8D-D5, RULE-8D-D5-001, RULE-8D-D6,
RULE-8D-D6-001, RULE-8D-D7 and RULE-8D-D8 in ``rca/CITATIONS.tsv`` / ``rca/ASSUMPTIONS_LOG.md``.
``RULE-8D-GATE-CONTAINMENT`` is *mirrored* by ``validate_d3_containment``,
``RULE-8D-GATE-PREVENTION`` by ``validate_d7_prevention``, and ``RULE-8D-GATE-CLOSURE`` by
``validate_d8_closure`` / ``validate_8d`` (which *compose* the already-shared
``_closure_evidence_deficiencies`` and ``_closure_reasons`` rather than re-deriving them), none
re-cited as a new claim: the gates those rules back stay in ``rca/eight_d.py``. The heuristics that no manual backs
(``ERA_VERIFICATION_DATE_INCONSISTENT``, ``CHAMPION_TEAM_LEADER_SAME_PERSON``,
``DUPLICATE_TEAM_MEMBER``, the field-presence reading of "roles ... clear",
``DEGENERATE_PROBLEM_STATEMENT``, ``QUANTIFICATION_NOT_NUMERIC``, and the three NCR-linkage
findings ``LINKED_NCR_NOT_PROVIDED`` / ``LINKED_NCR_INVALID`` / ``LINKED_NCR_VALID``) are declared
as Process Design Decisions #6, #7 and #8 in ``rca/ASSUMPTIONS_LOG.md`` and carry no citation row.
The D5/D6 heuristics with no manual behind them — ``PCA_VERIFICATION_EVIDENCE_MISSING``,
``D4_NOT_SUPPLIED``, ``D5_NOT_SUPPLIED``, ``IMPLEMENTED_ACTION_UNKNOWN_CORRECTIVE_ACTION_ID``,
``IMPLEMENTED_ACTION_TARGET_COVERAGE_INCOMPLETE`` and ``ICA_NOT_REMOVED`` — are declared the same
way, as Process Design Decision #11, and carry no citation row either. The D7 heuristics with no
manual behind them — the structural D4→D7 traceability reading
(``PREVENTION_NOT_TRACEABLE_ROOT_CAUSE`` / ``PREVENTION_ROOT_CAUSE_VALIDATION_NOT_RUN`` /
``PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE``, the last of these also identified as
``PDD-8D-013`` where the gate reports it), the
Control-Plan-evidence optionality findings (``CONTROL_PLAN_EVIDENCE_NOT_PROVIDED`` /
``CONTROL_PLAN_EVIDENCE_INVALID`` / ``CONTROL_PLAN_EVIDENCE_VALID``) and the informational
``FMEA_RESIDUAL_RISK`` / ``FMEA_RESIDUAL_RISK_EVIDENCE_INCOMPLETE`` framing — are declared as
Process Design Decision #12 and carry no citation row either. **No manual states an
Action-Priority-must-improve threshold for D7**, so ``ap_reduced=False`` never raises severity
above ``info``; inventing such a threshold would assert a rule no source states. The D8 /
``validate_8d`` decisions with no manual behind them — the whole-report signatures, the deliberate
exclusion of D4 from ``validate_8d``'s per-discipline sweep, the REJECT > WARNING > ACCEPT verdict
combination, and the explicit ``_linked_ncr_reason`` call that keeps the D3→D4-only
``LINKED_NCR_INVALID`` gate visible in a whole-report read — are declared as Process Design
Decision #14 and carry no citation row either; ``D8_WARNING_OVERRIDE_MISSING`` restates Process
Design Decision #4, which ``D8Discipline`` already enforces at construction time.

**D7 is an advisory pre-flight check that shares its rule with the gate.**
``validate_d7_prevention`` *reads* ``D7Discipline.has_qualifying_update``, extracted in E8/#211 as
the single definition of "this D7 record names an FMEA or Control Plan artifact" and now read by
all three consumers — ``eight_d.py``'s D7→D8 ``_prevention_reason`` gate,
``eight_d_schema._closure_evidence_deficiencies``' ``PREVENTION_UPDATE_MISSING`` closure
deficiency, and this engine. Before E8 the predicate was hand-written twice, identically, in the
two gates; it is now written once, so this engine's ``REJECT`` and the gates' block cannot
disagree about the same record. ``D7Discipline.has_root_cause_linked_update`` is the second such
shared predicate, written once for the same three consumers: it answers "and does that update say
which proven D4 finding it prevents the recurrence of", the question ``DocumentationUpdate.target``
was added to make answerable structurally (``PDD-8D-013``, Process Design Decision #13).

**PROCUREMENT-GAP (ISO 9001:2015 §8.7 / IATF 16949:2016 §8.7).** The licensed excerpts for the
nonconforming-output clauses that stand behind ``quality_core.ncr`` are not on this machine, so no
ISO/IATF quotation or paraphrase appears anywhere in ``rca/``: this engine only *calls* the
already-implemented ``validate_ncr`` and asserts nothing of its own about §8.7. The gap is
declared under Process Design Decision #8 in ``rca/ASSUMPTIONS_LOG.md``.

**PROCUREMENT-GAP (Cost of Poor Quality).** The same applies to
``validate_d6_implementation_validation``'s optional ``copq_data``: it only *calls* the
already-implemented ``quality_core.copq.estimator.estimate_copq`` and authors no PAF/COPQ
arithmetic, taxonomy, or methodology claim of its own; the COPQ reference manuals are not on this
machine, so ``rca/`` cannot re-verify ``quality_core.copq``'s own citation base. Declared in full
under Process Design Decision #11 in ``rca/ASSUMPTIONS_LOG.md`` — not duplicated here.

**PROCUREMENT-GAP (AIAG-VDA FMEA Handbook / AIAG APQP and Control Plan manual).**
``validate_d7_prevention`` only *calls* the already-implemented
``quality_core.controlplan.schema.validate_control_plan`` and
``quality_core.schema.action.Action.effectiveness`` (which reuses
``quality_core.scoring.action_priority`` / ``rpn``), and authors **no** AIAG-VDA FMEA or AIAG
APQP/Control-Plan standards claim of its own: no quotation or paraphrase of either manual appears
anywhere in ``rca/``. Those two callees own their own, pre-existing, independently gated citation
manifests (``controlplan/CITATIONS.tsv``, ``scoring_CITATIONS.tsv``), untouched by this epic; what
this epic cannot do is *re-verify* them, because neither manual is on this machine. Declared in
full under Process Design Decision #12 in ``rca/ASSUMPTIONS_LOG.md`` — not duplicated here.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

import pandas as pd
import pydantic

from quality_core.controlplan.schema import ControlPlanDataset, validate_control_plan
from quality_core.copq.estimator import estimate_copq
from quality_core.copq.schema import COPQDataset, CostItem
from quality_core.io.validate import clean_pydantic_message
from quality_core.ncr.schema import NCRDataset, validate_ncr
from quality_core.rca.eight_d import (
    EightDState,
    TransitionReason,
    _closure_reasons,
    _linked_ncr_reason,
    _state,
)
from quality_core.rca.eight_d_schema import (
    _QUALIFYING_ARTIFACT_TYPES,
    D0Discipline,
    D1Discipline,
    D2Discipline,
    D3Discipline,
    D4Discipline,
    D5Discipline,
    D6Discipline,
    D7Discipline,
    D8Discipline,
    EffectivenessVerification,
    EightDReport,
    FiveWhyVerdict,
    LinkedNCRValidation,
    _closure_evidence_deficiencies,
    _linked_ncr_deficiency,
)
from quality_core.rca.fishbone import FishboneCategorizationResult, categorize_fishbone
from quality_core.rca.five_why import FiveWhyValidationResult, validate_five_why_chain
from quality_core.rca.is_is_not import scope_is_is_not
from quality_core.rca.schema import IsIsNotMatrix
from quality_core.schema.action import Action, Effectiveness

__all__ = [
    "D0Finding",
    "D0ValidationResult",
    "D1Finding",
    "D1ValidationResult",
    "D2Finding",
    "D2ValidationResult",
    "D3Finding",
    "D3ValidationResult",
    "D4Finding",
    "D4ValidationResult",
    "D5Finding",
    "D5ValidationResult",
    "D6Finding",
    "D6ValidationResult",
    "D7Finding",
    "D7ValidationResult",
    "D8Finding",
    "D8ValidationResult",
    "EightDValidationResult",
    "validate_8d",
    "validate_d0_readiness",
    "validate_d1_team",
    "validate_d2_problem_description",
    "validate_d3_containment",
    "validate_d4_root_cause",
    "validate_d5_pca_selection",
    "validate_d6_implementation_validation",
    "validate_d7_prevention",
    "validate_d8_closure",
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
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

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
                citation_basis="RULE",
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
                citation_basis="RULE",
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
                    citation_basis="PLATFORM_UNCITED",
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
                citation_basis="RULE",
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
                citation_basis="RULE",
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
                citation_basis="PDD",
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
                citation_basis="PLATFORM_UNCITED",
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
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

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
                citation_basis="RULE",
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
                        citation_basis="PDD",
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
                        citation_basis="PDD",
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
                citation_basis="PDD",
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
                citation_basis="PLATFORM_UNCITED",
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
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

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
                citation_basis="PDD",
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
                citation_basis="PDD",
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
                    citation_basis="RULE",
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
                citation_basis="RULE",
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
                    citation_basis="RULE",
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
                    citation_basis="RULE",
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


# ==============================================================================
# 4. D3 — Interim containment
# ==============================================================================


def _ncr_linkage_findings(exc: Exception) -> tuple[str, ...]:
    """Turn a ``validate_ncr`` failure into finding text carrying the sub-engine's own words.

    Re-declares the identical logic of ``sqe/scar.py``'s ``_findings_from_exception`` **by
    necessity, not by preference**: that helper is ``sqe``-private and ``rca`` cannot import it,
    because imports run downward only (``sqe -> ncr/rca/copq``; none of those packages imports
    ``sqe``). Kept in exact behavioural lockstep with it — same catch shape, same
    ``"{location}: {message}"`` format — so the two copies cannot drift into different
    user-facing text for the identical failure.
    """
    if isinstance(exc, pydantic.ValidationError):
        messages: list[str] = []
        for error in exc.errors():
            message = clean_pydantic_message(str(error["msg"]))
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {message}" if location else message)
        return tuple(messages)
    return (str(exc),)


@dataclass
class D3Finding:
    """Finding raised against a D3 containment action or the linked nonconformity evidence."""

    code: str
    severity: Literal["error", "warning", "info"]
    action_description: str | None
    message: str
    recommendation: str
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D3 finding."""
        return asdict(self)


@dataclass
class D3ValidationResult:
    """Complete D3 (interim containment + NCR linkage) validation result.

    ``containment_verified`` is read directly from ``D3Discipline.is_verified`` — never
    recomputed by counting findings — so it cannot drift from the same predicate the D3→D4 gate
    in ``rca/eight_d.py`` reads. ``linked_ncr`` carries the validated
    ``NCRDataset.model_dump(mode="json")`` payload when linked evidence was supplied *and*
    accepted by ``quality_core.ncr.schema.validate_ncr``, and is ``None`` both when no evidence
    was supplied and when the supplied evidence was rejected; the ``findings`` codes
    (``LINKED_NCR_NOT_PROVIDED`` vs ``LINKED_NCR_INVALID``) disambiguate those two cases.

    ``linked_ncr_validation`` is the recorded outcome of that check, ``None`` when there is
    nothing to record. It is the artifact a caller stores on ``D3Discipline.linked_ncr_validation``
    so the D3→D4 gate can read the same verdict this engine reached, rather than re-deriving one.
    """

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    containment_verified: bool
    action_count: int
    linked_ncr: dict[str, Any] | None
    linked_ncr_validation: LinkedNCRValidation | None
    findings: list[D3Finding]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D3 result."""
        validation = self.linked_ncr_validation
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "containment_verified": self.containment_verified,
            "action_count": self.action_count,
            "linked_ncr": self.linked_ncr,
            "linked_ncr_validation": (
                None if validation is None else validation.model_dump(mode="json")
            ),
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": list(self.recommendations),
        }


def validate_d3_containment(
    discipline: D3Discipline,
    linked_ncr: NCRDataset | pd.DataFrame | list[Any] | dict[str, Any] | None = None,
) -> D3ValidationResult:
    """Validate D3 interim containment and its linked nonconformity evidence.

    Ford Global 8D requires the Interim Containment Action to be defined, verified and
    implemented, and the effectiveness of the measures of containment validated (RULE-8D-D3);
    AIAG CQI-20 adds that containment stays in place until corrective-action effectiveness is
    verified (RULE-8D-GATE-CONTAINMENT). This function reports one finding per containment action
    that is unverified or was verified ineffective, and rejects when any is found.

    **Advisory pre-flight check that shares both of the gate's rules.** ``containment_verified``
    *mirrors* — and never redefines — ``discipline.is_verified``, the same predicate
    ``rca/eight_d.py``'s D3→D4 gate reads at ``transition_eight_d``. The linked-NCR verdict is
    shared the same way: this function and that gate both call
    ``eight_d_schema._linked_ncr_deficiency``, so an invalid linked NCR is a hard stop in both
    places — here as this function's own ``REJECT``, there as a ``LINKED_NCR_INVALID`` transition
    reason, once the outcome is recorded on ``discipline.linked_ncr_validation``. That record is
    what this function returns in ``D3ValidationResult.linked_ncr_validation``, for the caller to
    store on the report. The state machine itself is still neither called nor duplicated here.
    See Process Design Decision #8 in ``rca/ASSUMPTIONS_LOG.md``.

    ``ContainmentAction`` already rejects a verification dated before the action it verifies, and
    ``D3Discipline`` already requires at least one action, so neither is re-checked here.

    Only ``quality_core.ncr.schema.validate_ncr`` is invoked for the linkage check.
    ``recommend_disposition`` and ``write_nonconformance`` remain available to a caller's
    downstream disposition workflow and are deliberately not called from this engine.

    Parameters
    ----------
    discipline : D3Discipline
        A validated D3 discipline record; guaranteed by its own model validator to carry at
        least one containment action. Any outcome already recorded on its
        ``linked_ncr_validation`` is reported when no ``linked_ncr`` evidence is supplied on this
        call, so this engine and the gate never disagree about a report they both can see.
    linked_ncr : NCRDataset | pd.DataFrame | list | dict | None, optional
        Untrusted Nonconformance Record evidence in any shape ``validate_ncr`` accepts, passed
        through unchanged with no pre-parsing or pre-validation here. Supplied evidence is
        validated live and its outcome supersedes any outcome recorded on the discipline.
        ``None`` means none was supplied on this call — a warning when the discipline records no
        outcome either, since not-yet-linked evidence is a normal in-progress state. Anything
        else, including an empty list, goes to ``validate_ncr`` and fails there if it is invalid.

    Returns
    -------
    D3ValidationResult
        Verdict, containment summary, findings, validated NCR payload, and de-duplicated
        recommendations.

    Notes
    -----
    Unlike ``validate_d2_problem_description``, which lets ``scope_is_is_not``'s exceptions
    propagate unmodified, this function **never raises from the** ``linked_ncr`` **path**:
    ``validate_ncr``'s ``pydantic.ValidationError`` / ``TypeError`` / ``ValueError`` are caught
    and surfaced as a ``LINKED_NCR_INVALID`` finding carrying the sub-engine's own message text,
    following the shipped ``sqe/scar.py`` (``_evaluate_ncr_linkage``) precedent, so a caller
    asking "does an invalid linked NCR block D3?" gets a verdict to read rather than an
    exception to catch.
    """
    findings: list[D3Finding] = []

    for action in discipline.actions:
        verification = action.verification
        if verification is None:
            findings.append(
                D3Finding(
                    code="CONTAINMENT_ACTION_NOT_VERIFIED",
                    severity="error",
                    citation_basis="RULE",
                    action_description=action.description,
                    message=(
                        f"The containment action implemented on {action.implemented_date} "
                        "carries no effectiveness verification record."
                    ),
                    recommendation=(
                        "Verify the Interim Containment Action and validate the effectiveness of "
                        "the measures of containment, recording who verified it, when, and on "
                        "what evidence."
                    ),
                )
            )
        elif not action.is_verified:
            findings.append(
                D3Finding(
                    code="CONTAINMENT_ACTION_VERIFIED_INEFFECTIVE",
                    severity="error",
                    citation_basis="RULE",
                    action_description=action.description,
                    message=(
                        f"The containment verification recorded by {verification.verified_by} on "
                        f"{verification.verified_date} concluded the action is not effective."
                    ),
                    recommendation=(
                        "Replace or strengthen the Interim Containment Action and re-verify it: "
                        "the containment must isolate the client from the effects of the problem "
                        "until permanent corrective actions are implemented."
                    ),
                )
            )

    containment_verified = discipline.is_verified

    linked_ncr_payload: dict[str, Any] | None = None
    ncr_validation: LinkedNCRValidation | None = discipline.linked_ncr_validation
    if linked_ncr is not None:
        try:
            ncr_dataset = validate_ncr(linked_ncr)
        except (pydantic.ValidationError, TypeError, ValueError) as exc:
            ncr_validation = LinkedNCRValidation(
                is_valid=False, findings=list(_ncr_linkage_findings(exc))
            )
        else:
            linked_ncr_payload = ncr_dataset.model_dump(mode="json")
            ncr_validation = LinkedNCRValidation(
                is_valid=True, record_count=len(ncr_dataset.records)
            )

    deficiency = _linked_ncr_deficiency(ncr_validation)
    if deficiency is not None:
        findings.append(
            D3Finding(
                code=deficiency.code,
                severity="error",
                citation_basis="PDD",
                action_description=None,
                message=deficiency.message,
                recommendation=(
                    "Correct the linked Nonconformance Record(s) so they satisfy "
                    "quality_core.ncr.schema.validate_ncr before this containment record can "
                    "be accepted."
                ),
            )
        )
    elif ncr_validation is None:
        findings.append(
            D3Finding(
                code="LINKED_NCR_NOT_PROVIDED",
                severity="warning",
                citation_basis="PDD",
                action_description=None,
                message=(
                    "No linked Nonconformance Record evidence was supplied, so the nonconformity "
                    "this containment isolates is not evidenced alongside the D3 record."
                ),
                recommendation=(
                    "Link the Nonconformance Record(s) covering the contained nonconformity so "
                    "the containment can be traced to the recorded nonconformity."
                ),
            )
        )
    else:
        findings.append(
            D3Finding(
                code="LINKED_NCR_VALID",
                severity="info",
                citation_basis="PDD",
                action_description=None,
                message=(
                    f"Linked Nonconformance Record evidence is structurally valid "
                    f"({ncr_validation.record_count} record(s))."
                ),
                recommendation=(
                    "No action required; the linked nonconformity evidence is valid."
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
            D3Finding(
                code="D3_READY",
                severity="info",
                citation_basis="PLATFORM_UNCITED",
                action_description=None,
                message=(
                    f"All {len(discipline.actions)} containment action(s) are verified effective "
                    "and the linked nonconformity evidence is valid."
                ),
                recommendation=(
                    "Interim containment is verified and NCR-linked; proceed to D4 root-cause "
                    "work."
                ),
            )
        )
        verdict, valid = "ACCEPT", True

    return D3ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        containment_verified=containment_verified,
        action_count=len(discipline.actions),
        linked_ncr=linked_ncr_payload,
        linked_ncr_validation=ncr_validation,
        findings=findings,
        recommendations=_dedupe(f.recommendation for f in findings),
    )
# ==============================================================================
# 5. D4 — Root cause and escape point
# ==============================================================================


@dataclass
class D4Finding:
    """Finding raised while validating supplied D4 evidence."""

    code: str
    severity: Literal["error", "warning", "info"]
    leg_type: Literal["occurrence", "escape"] | None
    message: str
    recommendation: str
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D4 finding."""
        return asdict(self)


@dataclass
class D4ValidationResult:
    """Complete D4 validation result without authored causal claims."""

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    root_cause_statement: str
    escape_point_statement: str
    occurrence_validation: FiveWhyValidationResult
    escape_validation: FiveWhyValidationResult
    candidate_causes_tested: int
    confirmed_candidates: int
    eliminated_candidates: int
    fishbone_validation: FishboneCategorizationResult | None
    findings: list[D4Finding]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a nested serializable representation using defensive list copies."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "root_cause_statement": self.root_cause_statement,
            "escape_point_statement": self.escape_point_statement,
            "occurrence_validation": self.occurrence_validation.to_dict(),
            "escape_validation": self.escape_validation.to_dict(),
            "candidate_causes_tested": self.candidate_causes_tested,
            "confirmed_candidates": self.confirmed_candidates,
            "eliminated_candidates": self.eliminated_candidates,
            "fishbone_validation": (
                self.fishbone_validation.to_dict()
                if self.fishbone_validation is not None
                else None
            ),
            "findings": [finding.to_dict() for finding in self.findings],
            "recommendations": list(self.recommendations),
        }


def _d4_leg_finding(
    leg_type: Literal["occurrence", "escape"],
    result: FiveWhyValidationResult,
) -> D4Finding:
    """Translate one 5-Why verdict without changing its meaning or causal text."""
    label = "Occurrence/root-cause" if leg_type == "occurrence" else "Escape-point"
    if result.verdict == "REJECT":
        return D4Finding(
            code=f"{leg_type.upper()}_CHAIN_REJECTED",
            severity="error",
            citation_basis="RULE",
            leg_type=leg_type,
            message=f"{label} 5-Why evidence was rejected by the RCA validator.",
            recommendation=f"Resolve the reported {leg_type} 5-Why findings and revalidate the supplied evidence.",
        )
    if result.verdict == "WARNING":
        return D4Finding(
            code=f"{leg_type.upper()}_CHAIN_WARNING",
            severity="warning",
            citation_basis="RULE",
            leg_type=leg_type,
            message=f"{label} 5-Why evidence passed with warnings.",
            recommendation=f"Review the reported {leg_type} 5-Why warnings before closing D4.",
        )
    return D4Finding(
        code=f"{leg_type.upper()}_CHAIN_ACCEPTED",
        severity="info",
        citation_basis="RULE",
        leg_type=leg_type,
        message=f"{label} 5-Why evidence was accepted.",
        recommendation=f"Retain the validated {leg_type} evidence with the 8D record.",
    )


def validate_d4_root_cause(
    discipline: D4Discipline,
    occurrence_chain: Any,
    escape_chain: Any,
    fishbone_evidence: Any | None = None,
) -> D4ValidationResult:
    """Validate caller-supplied D4 occurrence and escape evidence independently.

    The supplied D4 statements are passed unchanged as explicit terminal causes. This function
    does not infer, rank, rewrite, or generate a root cause from candidate or fishbone evidence.
    Empty candidate-test evidence blocks acceptance as an internal platform decision.
    """
    occurrence = validate_five_why_chain(
        occurrence_chain,
        root_cause=discipline.root_cause.statement,
        leg_type="occurrence",
    )
    escape = validate_five_why_chain(
        escape_chain,
        root_cause=discipline.escape_point.statement,
        leg_type="escape",
    )

    fishbone = categorize_fishbone(fishbone_evidence) if fishbone_evidence is not None else None

    confirmed = sum(cause.result == "CONFIRMED" for cause in discipline.candidate_causes_tested)
    eliminated = sum(cause.result == "ELIMINATED" for cause in discipline.candidate_causes_tested)
    findings = [
        _d4_leg_finding("occurrence", occurrence),
        _d4_leg_finding("escape", escape),
    ]

    submitted_terminals: tuple[
        tuple[Literal["occurrence", "escape"], str, str], ...
    ] = (
        ("occurrence", occurrence.link_evaluations[-1].because, discipline.root_cause.statement),
        ("escape", escape.link_evaluations[-1].because, discipline.escape_point.statement),
    )
    for leg_type, submitted_terminal, supplied_statement in submitted_terminals:
        if submitted_terminal != supplied_statement:
            findings.append(
                D4Finding(
                    code=f"{leg_type.upper()}_TERMINAL_CAUSE_MISMATCH",
                    severity="error",
                    citation_basis="PDD",
                    leg_type=leg_type,
                    message=(
                        f"The submitted {leg_type} chain terminal evidence does not match the "
                        "caller-supplied D4 statement."
                    ),
                    recommendation=(
                        "Reconcile the submitted chain and D4 statement; the validator will not "
                        "infer or author a replacement cause."
                    ),
                )
            )

    if not discipline.candidate_causes_tested:
        findings.append(
            D4Finding(
                code="NO_CANDIDATE_CAUSE_TESTS",
                severity="error",
                citation_basis="PDD",
                leg_type=None,
                message="D4 records no tested candidate causes to support the supplied root cause.",
                recommendation="Record at least one tested candidate cause and its caller-supplied evidence and result.",
            )
        )

    metadata: tuple[
        tuple[
            Literal["occurrence", "escape"],
            str | None,
            str | None,
            str,
        ],
        ...,
    ] = (
        ("occurrence", discipline.root_cause.five_why_leg_type, discipline.root_cause.five_why_verdict, occurrence.verdict),
        ("escape", discipline.escape_point.five_why_leg_type, discipline.escape_point.five_why_verdict, escape.verdict),
    )
    for leg_type, supplied_leg, supplied_verdict, validated_verdict in metadata:
        if supplied_leg is not None and supplied_leg != leg_type:
            findings.append(
                D4Finding(
                    code=f"{leg_type.upper()}_LEG_TYPE_MISMATCH",
                    severity="warning",
                    citation_basis="PDD",
                    leg_type=leg_type,
                    message=f"Caller-supplied leg type '{supplied_leg}' does not match the validated '{leg_type}' leg.",
                    recommendation="Correct the supplied leg metadata; it does not override fresh validation.",
                )
            )
        if supplied_verdict is not None and supplied_verdict != validated_verdict:
            findings.append(
                D4Finding(
                    code=f"{leg_type.upper()}_VERDICT_MISMATCH",
                    severity="warning",
                    citation_basis="PDD",
                    leg_type=leg_type,
                    message=f"Caller-supplied verdict '{supplied_verdict}' differs from fresh validation verdict '{validated_verdict}'.",
                    recommendation="Update the supplied verdict metadata to reflect the fresh validation result.",
                )
            )

    if any(finding.severity == "error" for finding in findings):
        verdict: Literal["ACCEPT", "WARNING", "REJECT"] = "REJECT"
        valid = False
    elif any(finding.severity == "warning" for finding in findings):
        verdict = "WARNING"
        valid = True
    else:
        verdict = "ACCEPT"
        valid = True

    return D4ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        root_cause_statement=discipline.root_cause.statement,
        escape_point_statement=discipline.escape_point.statement,
        occurrence_validation=occurrence,
        escape_validation=escape,
        candidate_causes_tested=len(discipline.candidate_causes_tested),
        confirmed_candidates=confirmed,
        eliminated_candidates=eliminated,
        fishbone_validation=fishbone,
        findings=findings,
        recommendations=_dedupe(finding.recommendation for finding in findings),
    )


# ==============================================================================
# 6. D5 — Permanent corrective action selection
# ==============================================================================


@dataclass
class D5Finding:
    """Finding raised against one D5 corrective-action candidate, or against the record."""

    code: str
    severity: Literal["error", "warning", "info"]
    action_id: str | None
    message: str
    recommendation: str
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D5 finding."""
        return asdict(self)


@dataclass
class D5ValidationResult:
    """Complete D5 (permanent corrective action selection) validation result.

    ``root_cause_traceable`` / ``escape_point_traceable`` are ``None`` when no ``D4Discipline``
    was supplied — the question was not asked, which is not the same answer as "no". When D4 *was*
    supplied, each is ``True`` only if every candidate carrying that ``target`` cleared the
    structural traceability check described on :func:`validate_d5_pca_selection`.
    """

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    candidate_count: int
    root_cause_traceable: bool | None
    escape_point_traceable: bool | None
    findings: list[D5Finding]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D5 result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "candidate_count": self.candidate_count,
            "root_cause_traceable": self.root_cause_traceable,
            "escape_point_traceable": self.escape_point_traceable,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": list(self.recommendations),
        }


def _d5_traceability_finding(
    candidate_id: str,
    target: Literal["ROOT_CAUSE", "ESCAPE_POINT"],
    *,
    has_confirmed_test: bool,
    verdict: str | None,
) -> D5Finding | None:
    """Answer the structural traceability question for one candidate; ``None`` means traceable.

    ``has_confirmed_test`` is only meaningful for a ``ROOT_CAUSE`` candidate — callers pass
    ``True`` for an ``ESCAPE_POINT`` candidate, because ``D4Discipline.candidate_causes_tested``
    is a single flat list scoped to root-cause testing by ``RULE-8D-D4``'s own text ("testing each
    possible cause against the description of the Problem with the test data") and the schema
    carries no escape-point analogue to read.
    """
    label = "root cause" if target == "ROOT_CAUSE" else "escape point"
    if not has_confirmed_test:
        return D5Finding(
            code=f"PCA_NOT_TRACEABLE_{target}",
            severity="error",
            citation_basis="PDD",
            action_id=candidate_id,
            message=(
                f"Corrective action candidate '{candidate_id}' targets the {label}, but D4 "
                "records no candidate cause with result CONFIRMED, so no root cause has been "
                "proven against test data for the candidate to be traceable to (RULE-8D-D4)."
            ),
            recommendation=(
                "Record the candidate cause test that confirms the root cause in D4 before "
                "claiming a permanent corrective action for it (RULE-8D-D5-001)."
            ),
        )
    if verdict == "REJECT":
        return D5Finding(
            code=f"PCA_NOT_TRACEABLE_{target}",
            severity="error",
            citation_basis="PDD",
            action_id=candidate_id,
            message=(
                f"Corrective action candidate '{candidate_id}' targets the {label}, but D4's "
                f"recorded five_why_verdict for that finding is REJECT, so the causal chain "
                "behind it was not accepted."
            ),
            recommendation=(
                f"Resolve the rejected {label} 5-Why chain in D4 and re-record its verdict "
                "before selecting a permanent corrective action against it."
            ),
        )
    if verdict is None:
        return D5Finding(
            code=f"PCA_{target}_VALIDATION_NOT_RUN",
            severity="warning",
            citation_basis="PDD",
            action_id=candidate_id,
            message=(
                f"Corrective action candidate '{candidate_id}' targets the {label}, but D4 "
                "records no five_why_verdict for that finding, so its causal chain has not been "
                "validated yet."
            ),
            recommendation=(
                f"Run the {label} 5-Why validation in D4 and record its verdict, so the "
                "selected permanent corrective action rests on a validated finding."
            ),
        )
    return None


def validate_d5_pca_selection(
    discipline: D5Discipline,
    d4: D4Discipline | None = None,
) -> D5ValidationResult:
    """Validate D5 permanent corrective action (PCA) selection and its traceability to D4.

    Ford Global 8D requires a PCA for the root cause *and* one for the escape point, and requires
    both decisions verified as successful "without causing undesirable effects" before
    implementation (RULE-8D-D5). Its own D5 evaluation questions frame that justification as an
    evidence question — "What evidence (proof) do you have that this will solve the problem at the
    root level?" (RULE-8D-D5-001). This engine reports one finding per candidate that fails either
    the verification precondition or the structural traceability check below, and rejects when any
    error is found.

    **This traceability check is structural, not semantic.** It proves that D4, as a whole, did
    the proving work RULE-8D-D4 requires before a PCA can legitimately target its finding: at
    least one candidate cause was tested and confirmed (for ``ROOT_CAUSE``-targeted candidates),
    and the D4 engine's own five-why validation of that finding did not conclude REJECT. It does
    **not** prove that this specific PCA's ``description`` actually addresses the *content* of the
    CONFIRMED test or of ``root_cause.statement`` — establishing that would require fuzzy string
    matching between ``CorrectiveActionCandidate.description`` and ``RootCauseFinding.statement``
    / ``CandidateCauseTest.description``, which ``D4Discipline``'s own docstring already disclaims
    for carrying no standards basis, and this engine does not reintroduce it under a different
    name. Whether the *specific* PCA under review really eliminates the specific finding it claims
    to target remains a human judgment call this tool does not automate. The structural
    composition itself — treating "D4 proved nothing" as "this PCA is not traceable" — is this
    platform's translation, Process Design Decision #11 in ``rca/ASSUMPTIONS_LOG.md``; neither
    quoted passage states a checkable rule of that shape.

    ``five_why_verdict`` is *read* exactly as the E6 D4 engine populated it and is never
    recomputed here, mirroring how this module never re-derives ``is_verified`` /
    ``is_effective`` predicates elsewhere. ``D5Discipline``'s own model validator already
    guarantees both targets are covered and every ``action_id`` is unique
    (``_check_candidate_coverage``), so neither is re-checked.

    Parameters
    ----------
    discipline : D5Discipline
        A validated D5 discipline record; guaranteed to carry at least one ``ROOT_CAUSE`` and one
        ``ESCAPE_POINT`` candidate.
    d4 : D4Discipline | None, optional
        The same report's already-typed D4 record. ``None`` means D4 evidence has not been
        supplied on this call — a warning, never a rejection, because absent cross-discipline
        evidence is a normal in-progress state (mirroring ``IS_IS_NOT_NOT_PROVIDED`` at D2 and
        ``LINKED_NCR_NOT_PROVIDED`` at D3).

    Returns
    -------
    D5ValidationResult
        Verdict, candidate count, per-target traceability flags, findings, and de-duplicated
        recommendations.
    """
    findings: list[D5Finding] = []
    root_cause_traceable: bool | None = None
    escape_point_traceable: bool | None = None

    if d4 is None:
        findings.append(
            D5Finding(
                code="D4_NOT_SUPPLIED",
                severity="warning",
                citation_basis="PDD",
                action_id=None,
                message=(
                    "No D4 record was supplied, so no corrective action candidate could be "
                    "traced to a proven root cause or escape point."
                ),
                recommendation=(
                    "Supply the report's D4 record so each permanent corrective action can be "
                    "traced to the finding it claims to address."
                ),
            )
        )
    else:
        root_cause_traceable = True
        escape_point_traceable = True

    has_confirmed_test = d4 is not None and any(
        cause.result == "CONFIRMED" for cause in d4.candidate_causes_tested
    )

    for candidate in discipline.candidates:
        if not candidate.verified_no_undesirable_effects:
            findings.append(
                D5Finding(
                    code="PCA_UNDESIRABLE_EFFECTS_NOT_VERIFIED",
                    severity="error",
                    citation_basis="RULE",
                    action_id=candidate.action_id,
                    message=(
                        f"Corrective action candidate '{candidate.action_id}' is not recorded as "
                        "verified free of undesirable effects; D5 requires verifying that the "
                        "decision will be successful when implemented without causing "
                        "undesirable effects (RULE-8D-D5)."
                    ),
                    recommendation=(
                        "Verify the selected permanent corrective action will succeed without "
                        "causing undesirable effects, then record that verification before "
                        "implementing it at D6."
                    ),
                )
            )
        elif candidate.verification_notes is None:
            findings.append(
                D5Finding(
                    code="PCA_VERIFICATION_EVIDENCE_MISSING",
                    severity="warning",
                    citation_basis="PDD",
                    action_id=candidate.action_id,
                    message=(
                        f"Corrective action candidate '{candidate.action_id}' is marked verified "
                        "free of undesirable effects but records no verification_notes, so the "
                        "evidence behind that verification is not written down."
                    ),
                    recommendation=(
                        "Record verification_notes describing the evidence behind the "
                        "no-undesirable-effects verification."
                    ),
                )
            )

        if d4 is None:
            continue

        if candidate.target == "ROOT_CAUSE":
            finding = _d5_traceability_finding(
                candidate.action_id,
                "ROOT_CAUSE",
                has_confirmed_test=has_confirmed_test,
                verdict=d4.root_cause.five_why_verdict,
            )
            if finding is not None:
                findings.append(finding)
                root_cause_traceable = False
        else:
            finding = _d5_traceability_finding(
                candidate.action_id,
                "ESCAPE_POINT",
                has_confirmed_test=True,
                verdict=d4.escape_point.five_why_verdict,
            )
            if finding is not None:
                findings.append(finding)
                escape_point_traceable = False

    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    if any(f.severity == "error" for f in findings):
        verdict, valid = "REJECT", False
    elif any(f.severity == "warning" for f in findings):
        verdict, valid = "WARNING", True
    else:
        findings.append(
            D5Finding(
                code="D5_READY",
                severity="info",
                citation_basis="PLATFORM_UNCITED",
                action_id=None,
                message=(
                    f"All {len(discipline.candidates)} corrective action candidate(s) are "
                    "verified free of undesirable effects and traceable to a proven D4 finding."
                ),
                recommendation=(
                    "Permanent corrective action selection is complete; proceed to D6 "
                    "implementation and validation."
                ),
            )
        )
        verdict, valid = "ACCEPT", True

    return D5ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        candidate_count=len(discipline.candidates),
        root_cause_traceable=root_cause_traceable,
        escape_point_traceable=escape_point_traceable,
        findings=findings,
        recommendations=_dedupe(f.recommendation for f in findings),
    )


# ==============================================================================
# 7. D6 — Implement and validate the permanent corrective actions
# ==============================================================================


@dataclass
class D6Finding:
    """Finding raised against one D6 implemented action, or against the record."""

    code: str
    severity: Literal["error", "warning", "info"]
    action_id: str | None
    message: str
    recommendation: str
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D6 finding."""
        return asdict(self)


@dataclass
class D6ValidationResult:
    """Complete D6 (implementation and validation) validation result.

    ``implementation_verified`` is read directly from ``D6Discipline.is_verified`` — never
    recomputed by counting findings — so it cannot drift from the same predicate the D8 to CLOSED
    closure boundary reads through ``eight_d_schema._closure_evidence_deficiencies``.

    ``copq_impact`` carries ``quality_core.copq.estimator.estimate_copq``'s own
    ``COPQEstimationResult.to_dict()`` payload when cost data was supplied, and ``None`` when it
    was not. No PAF/COPQ arithmetic or methodology claim is authored here.
    """

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    implementation_verified: bool
    action_count: int
    copq_impact: dict[str, Any] | None
    findings: list[D6Finding]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D6 result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "implementation_verified": self.implementation_verified,
            "action_count": self.action_count,
            "copq_impact": self.copq_impact,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": list(self.recommendations),
        }


def validate_d6_implementation_validation(
    discipline: D6Discipline,
    d5: D5Discipline | None = None,
    copq_data: (
        Sequence[CostItem | dict[str, Any]]
        | COPQDataset
        | pd.DataFrame
        | dict[str, Any]
        | None
    ) = None,
) -> D6ValidationResult:
    """Validate D6: the selected PCAs as implemented, validated, and cross-referenced to D5.

    Ford Global 8D requires the selected permanent corrective actions to be planned and
    implemented, the interim containment action removed, and the actions validated with long-term
    results monitored (RULE-8D-D6); its CHECK step names both targets explicitly — "Validate the
    ACPs both for the root cause and for the escape points" (RULE-8D-D6-001). This engine reports
    one finding per implemented action that is unverified, verified ineffective, or names a
    ``corrective_action_id`` no D5 candidate carries, and rejects when any error is found.

    **Advisory pre-flight check that shares the closure rule with the gate.**
    ``implementation_verified`` *mirrors* — and never redefines — ``discipline.is_verified``, the
    same predicate ``eight_d_schema._closure_evidence_deficiencies`` reads for the
    ``PCA_NOT_VERIFIED`` closure deficiency that blocks both direct CLOSED-report construction and
    the D8 to CLOSED transition (``PDD-8D-010``). One rule, one definition: this engine does not
    keep a second copy of it, and does not call ``transition_eight_d``.

    **The D5 cross-reference is an exact string match, not fuzzy matching.**
    ``corrective_action_id`` and ``action_id`` are assigned identifiers, not free-text statements,
    so equality is the whole rule — the same equality ``D5Discipline`` already uses to enforce
    ``action_id`` uniqueness. This is explicitly *not* the statement-to-statement matching
    ``D4Discipline``'s docstring disclaims, and it resolves the cross-discipline reference
    ``ImplementedAction``'s own docstring records as unenforced at the schema layer. The match is
    case-sensitive by design: ``"pca-1"`` and ``"PCA-1"`` are different identifiers, and silently
    equating them would let a typo pass as a reference.

    ``D6Discipline._removal_requires_verified_actions`` already makes an
    ``interim_containment_removed_date`` on an unverified record impossible to construct, so that
    direction is not re-checked here; only the inverse (verified actions, containment still not
    recorded as removed) is reported, as a warning.

    Parameters
    ----------
    discipline : D6Discipline
        A validated D6 discipline record; guaranteed by its own model validator to carry at least
        one implemented action.
    d5 : D5Discipline | None, optional
        The same report's already-typed D5 record. ``None`` means it was not supplied on this
        call: a warning, and both the ID cross-reference and the target-coverage check are
        skipped rather than guessed at.
    copq_data : Sequence[CostItem | dict] | COPQDataset | DataFrame | dict | None, optional
        Untrusted cost-of-quality data in any shape ``estimate_copq`` accepts, passed through
        unchanged with no pre-parsing or pre-validation here. ``None`` means none was supplied,
        which is not an error and produces ``copq_impact=None``.

    Returns
    -------
    D6ValidationResult
        Verdict, implementation summary, findings, optional COPQ payload, and de-duplicated
        recommendations.

    Raises
    ------
    TypeError
        Propagated unmodified from ``estimate_copq`` / ``validate_copq`` when ``copq_data`` is a
        type they reject. Unlike ``validate_d3_containment``'s ``linked_ncr`` path, this one is
        deliberately *not* caught: COPQ impact is optional financial context that gates nothing,
        so there is no gate-safety reason to convert the error into a verdict. This follows
        ``validate_d2_problem_description``'s ``is_is_not`` precedent.
    ValueError
        Propagated unmodified from ``estimate_copq`` on a negative, infinite, or NaN cost value.
    pydantic.ValidationError
        Propagated unmodified from ``validate_copq`` when ``copq_data`` contains structurally
        invalid rows.
    """
    findings: list[D6Finding] = []

    candidate_targets: dict[str, str] = (
        {} if d5 is None else {c.action_id: c.target for c in d5.candidates}
    )
    covered_targets: set[str] = set()

    for action in discipline.implemented_actions:
        verification = action.verification
        if verification is None:
            findings.append(
                D6Finding(
                    code="IMPLEMENTED_ACTION_NOT_VERIFIED",
                    severity="error",
                    citation_basis="RULE",
                    action_id=action.corrective_action_id,
                    message=(
                        f"The permanent corrective action '{action.corrective_action_id}' "
                        f"implemented on {action.implemented_date} carries no effectiveness "
                        "verification record."
                    ),
                    recommendation=(
                        "Validate the implemented permanent corrective action and record who "
                        "verified it, when, and on what evidence, before removing the interim "
                        "containment action."
                    ),
                )
            )
        elif not action.is_verified:
            findings.append(
                D6Finding(
                    code="IMPLEMENTED_ACTION_VERIFIED_INEFFECTIVE",
                    severity="error",
                    citation_basis="RULE",
                    action_id=action.corrective_action_id,
                    message=(
                        f"The validation of permanent corrective action "
                        f"'{action.corrective_action_id}' recorded by "
                        f"{verification.verified_by} on {verification.verified_date} concluded "
                        "the action is not effective."
                    ),
                    recommendation=(
                        "Replace or strengthen the permanent corrective action and re-validate "
                        "it: the validation must compare like-for-like data before and after "
                        "implementation."
                    ),
                )
            )

        if d5 is None:
            continue
        if action.corrective_action_id not in candidate_targets:
            findings.append(
                D6Finding(
                    code="IMPLEMENTED_ACTION_UNKNOWN_CORRECTIVE_ACTION_ID",
                    severity="error",
                    citation_basis="PDD",
                    action_id=action.corrective_action_id,
                    message=(
                        f"Implemented action names corrective_action_id "
                        f"'{action.corrective_action_id}', which matches no D5 candidate "
                        "action_id (the comparison is an exact, case-sensitive match on the "
                        "assigned identifier)."
                    ),
                    recommendation=(
                        "Correct corrective_action_id so it names one of the D5 candidates "
                        "exactly, or add the missing candidate to D5."
                    ),
                )
            )
        elif action.is_verified:
            covered_targets.add(candidate_targets[action.corrective_action_id])

    if d5 is None:
        findings.append(
            D6Finding(
                code="D5_NOT_SUPPLIED",
                severity="warning",
                citation_basis="PDD",
                action_id=None,
                message=(
                    "No D5 record was supplied, so no implemented action could be cross-"
                    "referenced to a selected corrective action candidate and target coverage "
                    "could not be assessed."
                ),
                recommendation=(
                    "Supply the report's D5 record so every implemented action can be matched to "
                    "the corrective action candidate it implements."
                ),
            )
        )
    elif not {"ROOT_CAUSE", "ESCAPE_POINT"} <= covered_targets:
        missing = sorted({"ROOT_CAUSE", "ESCAPE_POINT"} - covered_targets)
        findings.append(
            D6Finding(
                code="IMPLEMENTED_ACTION_TARGET_COVERAGE_INCOMPLETE",
                severity="warning",
                citation_basis="PDD",
                action_id=None,
                message=(
                    "No verified, D5-matched implemented action covers: "
                    + ", ".join(missing)
                    + ". D6 validates the corrective actions both for the root cause and for the "
                    "escape point (RULE-8D-D6-001)."
                ),
                recommendation=(
                    "Implement and validate a permanent corrective action for each outstanding "
                    "target so both the root cause and the escape point are covered."
                ),
            )
        )

    if discipline.is_verified and discipline.interim_containment_removed_date is None:
        findings.append(
            D6Finding(
                code="ICA_NOT_REMOVED",
                severity="warning",
                citation_basis="PDD",
                action_id=None,
                message=(
                    "Every implemented action is verified effective but no "
                    "interim_containment_removed_date is recorded; D6 removes the interim "
                    "containment action once the permanent corrective actions are validated "
                    "(RULE-8D-D6)."
                ),
                recommendation=(
                    "Remove the interim containment action and record the date, or state why it "
                    "must remain in place."
                ),
            )
        )

    copq_impact: dict[str, Any] | None = None
    if copq_data is not None:
        # estimate_copq's own `items` annotation is narrower than the shapes it accepts at
        # runtime: anything that is not a COPQDataset or a list is forwarded to
        # copq.schema.validate_copq, which additionally accepts a DataFrame and a plain dict.
        # The cast records that, and keeps every COPQ rule inside quality_core.copq.
        copq_impact = estimate_copq(
            items=cast("Sequence[CostItem | dict[str, Any]] | COPQDataset", copq_data)
        ).to_dict()

    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    if any(f.severity == "error" for f in findings):
        verdict, valid = "REJECT", False
    elif any(f.severity == "warning" for f in findings):
        verdict, valid = "WARNING", True
    else:
        findings.append(
            D6Finding(
                code="D6_READY",
                severity="info",
                citation_basis="PLATFORM_UNCITED",
                action_id=None,
                message=(
                    f"All {len(discipline.implemented_actions)} implemented action(s) are "
                    "verified effective, matched to a D5 candidate, and cover both the root "
                    "cause and the escape point."
                ),
                recommendation=(
                    "Permanent corrective actions are implemented and validated; proceed to D7 "
                    "prevention."
                ),
            )
        )
        verdict, valid = "ACCEPT", True

    return D6ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        implementation_verified=discipline.is_verified,
        action_count=len(discipline.implemented_actions),
        copq_impact=copq_impact,
        findings=findings,
        recommendations=_dedupe(f.recommendation for f in findings),
    )


# ==============================================================================
# 8. D7 — Prevent recurrence
# ==============================================================================


def _control_plan_findings(exc: Exception) -> tuple[str, ...]:
    """Turn a ``validate_control_plan`` failure into text carrying the sub-engine's own words.

    A deliberate second copy of ``_ncr_linkage_findings``' formatting, **by necessity, not by
    preference**: the two callees raise from different packages and there is no shared home both
    call sites could import a single helper from without either violating the downward-only import
    direction or adding a new shared module outside this epic's scope. Named distinctly so it is
    never mistaken for the NCR one, and kept in exact behavioural lockstep with it — same catch
    shape, same ``"{location}: {message}"`` format, same ``str(exc)`` fallback for a non-pydantic
    exception (``validate_control_plan`` raises a bare ``TypeError`` for an unsupported input
    type).
    """
    if isinstance(exc, pydantic.ValidationError):
        messages: list[str] = []
        for error in exc.errors():
            message = clean_pydantic_message(str(error["msg"]))
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {message}" if location else message)
        return tuple(messages)
    return (str(exc),)


@dataclass
class D7Finding:
    """Finding raised against the D7 prevention record or its supplied linkage evidence."""

    code: str
    severity: Literal["error", "warning", "info"]
    artifact_type: (
        Literal["FMEA", "CONTROL_PLAN", "PROCESS_FLOW", "WORK_INSTRUCTION", "OTHER"] | None
    )
    message: str
    recommendation: str
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D7 finding."""
        return asdict(self)


@dataclass
class D7ValidationResult:
    """Complete D7 (prevent recurrence) validation result.

    ``has_qualifying_update`` is read directly from ``D7Discipline.has_qualifying_update`` — never
    recomputed by counting findings or re-testing ``artifact_type`` — so it cannot drift from the
    same predicate the D7→D8 transition gate and the D8→CLOSED closure boundary both block on.
    ``prevention_documented`` is the separate, broader ``D7Discipline.is_documented``: any update
    at all, including a ``WORK_INSTRUCTION``- or ``OTHER``-typed one.

    ``root_cause_linked_update`` is read the same way from
    ``D7Discipline.has_root_cause_linked_update`` (E8/#211), the narrower predicate the same two
    checkpoints block on. The three booleans nest strictly:
    ``root_cause_linked_update`` implies ``has_qualifying_update`` implies
    ``prevention_documented``.
    """

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    prevention_documented: bool
    has_qualifying_update: bool
    root_cause_linked_update: bool
    root_cause_traceable: bool | None
    control_plan_evidence: dict[str, Any] | None
    fmea_effectiveness: dict[str, Any] | None
    findings: list[D7Finding]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D7 result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "prevention_documented": self.prevention_documented,
            "has_qualifying_update": self.has_qualifying_update,
            "root_cause_linked_update": self.root_cause_linked_update,
            "root_cause_traceable": self.root_cause_traceable,
            "control_plan_evidence": self.control_plan_evidence,
            "fmea_effectiveness": self.fmea_effectiveness,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": list(self.recommendations),
        }


def validate_d7_prevention(
    discipline: D7Discipline,
    d4: D4Discipline | None = None,
    control_plan_evidence: ControlPlanDataset | pd.DataFrame | list[Any] | None = None,
    fmea_action: Action | dict[str, Any] | None = None,
    fmea_before: tuple[int, int, int] | None = None,
) -> D7ValidationResult:
    """Validate D7: the prevention documentation update, its D4 traceability, and its evidence.

    Ford Global 8D's D7 requires modifying the systems, policies, practices and procedures that
    permitted the problem, and its evaluation question asks "Have all changes been documented
    (for example, FMEA, control plan, flow of process)?" (``RULE-8D-D7``, repeated at five
    checkpoints and cited for the gate as ``RULE-8D-GATE-PREVENTION``). **What that passage
    establishes** is that the FMEA and the control plan are the artifacts a D7 change is recorded
    in. **What this engine does** with it is narrower and is this platform's translation: it
    reports whether the record names at least one such artifact, and — when the caller supplies
    them — validates the linked Control Plan and reports FMEA residual risk. The manual states no
    threshold, no evidence format, and no completeness algorithm; none is invented here.

    **Advisory pre-flight check that shares its rule with the gate.** ``has_qualifying_update``
    *reads* — and never redefines — ``D7Discipline.has_qualifying_update``, the one predicate
    ``eight_d.py``'s D7→D8 ``_prevention_reason`` gate and
    ``eight_d_schema._closure_evidence_deficiencies``' ``PREVENTION_UPDATE_MISSING`` closure
    deficiency both block on. One rule, one definition: this engine keeps no second copy of it and
    does not call ``transition_eight_d``. ``PREVENTION_ARTIFACT_UPDATE_MISSING`` is reported at
    ``severity="error"`` for the same reason ``ERA_NOT_IMPLEMENTED`` (D0),
    ``CONTAINMENT_ACTION_NOT_VERIFIED`` (D3) and ``IMPLEMENTED_ACTION_NOT_VERIFIED`` (D6) are —
    the advisory engine reports as an error the exact fact the gate blocks on, even where the
    schema itself permits the underlying state to be constructed.

    **D4→D7 traceability is structural, not semantic — and it has two legs.** The check proves
    (a) that D4 as a whole did the proving work — a non-``REJECT`` ``five_why_verdict`` on the
    root-cause finding — and (b) that a qualifying D7 artifact update declares
    ``target="ROOT_CAUSE"``, the structural back-reference added in E8/#211 and read here through
    ``D7Discipline.has_root_cause_linked_update``. Leg (b) is what makes ``root_cause_traceable``
    a statement about *this* update rather than about the report at large: a qualifying FMEA or
    Control Plan update that names no target, or names only ``ESCAPE_POINT``, is reported
    ``PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE`` at ``severity="error"`` and is not traceable,
    exactly as the D7→D8 gate and the D8→CLOSED boundary now block it. Both legs must hold on the
    same record; the two conditions of leg (b) must hold on the same ``DocumentationUpdate``.

    What is still **not** attempted is comparing ``DocumentationUpdate.artifact_reference`` with
    ``RootCauseFinding.statement``: that would be the fuzzy string matching ``D4Discipline``'s own
    docstring disclaims for having no standards basis, and this epic does not reintroduce it under
    another name. ``target`` sidesteps it because ``D4Discipline`` carries exactly one
    ``root_cause`` and one ``escape_point``, so the two-value vocabulary is a complete structural
    reference, not an approximation — the same reason ``CorrectiveActionCandidate.target`` works
    at D5. **Whether the artifact behind ``artifact_reference`` genuinely implements the fix for
    the declared target remains a human judgment call this tool does not automate**, precisely as
    it does at D5; what the tool now refuses to do is call an update traceable that never made the
    claim.

    **Bidirectional PFMEA linkage is deliberately not checked here.**
    ``quality_core.controlplan.validate_pfmea_linkage`` exists and is importable downward, but it
    takes a ``ControlPlanDataset`` *and* a ``RelationalFMEA``, and ``D7Discipline`` carries no
    FMEA payload to build one from — ``DocumentationUpdate.artifact_reference`` is a bare string,
    not a linkable dataset. There is therefore nothing on this record for it to check. Linkage
    checking stays at the MCP tool layer, where the caller holds both documents.

    Parameters
    ----------
    discipline : D7Discipline
        A validated D7 discipline record. The untrusted-data trust boundary is
        ``validate_eight_d``, as for every other discipline engine here.
    d4 : D4Discipline | None, optional
        The same report's already-typed D4 record. ``None`` means it was not supplied on this
        call: a warning, and the traceability check is skipped rather than guessed at
        (``root_cause_traceable=None``).
    control_plan_evidence : ControlPlanDataset | DataFrame | list | None, optional
        Untrusted Control Plan evidence in any shape
        ``quality_core.controlplan.schema.validate_control_plan`` accepts, passed through
        unchanged with no pre-parsing or pre-validation here. ``None`` means none was supplied,
        which warns only when the record itself declares a ``CONTROL_PLAN`` update.
    fmea_action : Action | dict | None, optional
        The re-rated ``quality_core.schema.action.Action`` recording the post-update FMEA
        ratings, or a dict ``Action`` accepts. Required together with ``fmea_before``.
    fmea_before : tuple[int, int, int] | None, optional
        The pre-update ``(severity, occurrence, detection)`` triple the D7 change is measured
        against. Required together with ``fmea_action``.

    Returns
    -------
    D7ValidationResult
        Verdict, prevention summary, findings, optional Control Plan and FMEA residual-risk
        payloads, and de-duplicated recommendations.

    Raises
    ------
    pydantic.ValidationError
        Propagated unmodified from ``Action(**fmea_action)`` when the supplied dict is not a valid
        ``Action``. Unlike the ``control_plan_evidence`` path, this one is deliberately *not*
        caught: FMEA residual risk is optional, informational context that gates nothing, so there
        is no gate-safety reason to convert the error into a verdict. Mirrors
        ``validate_d6_implementation_validation``'s ``copq_data`` path.
    ValueError
        Propagated unmodified from ``Action.effectiveness`` (via
        ``quality_core.scoring.action_priority`` / ``rpn``) when any supplied rating is outside
        the 1..10 scale.
    """
    findings: list[D7Finding] = []

    if not discipline.has_qualifying_update:
        findings.append(
            D7Finding(
                code="PREVENTION_ARTIFACT_UPDATE_MISSING",
                severity="error",
                citation_basis="RULE",
                artifact_type=None,
                message=(
                    "D7 records no FMEA or Control Plan documentation update; Ford Global 8D asks "
                    "whether all changes have been documented (for example, FMEA, control plan, "
                    "flow of process) at this checkpoint (RULE-8D-D7, RULE-8D-GATE-PREVENTION), "
                    "and this is the same evidence the D7 to D8 and D8 to CLOSED gates require."
                ),
                recommendation=(
                    "Record a documentation_updates entry with artifact_type FMEA or "
                    "CONTROL_PLAN before advancing past D7."
                ),
            )
        )
    else:
        qualifying_types = sorted(
            {
                update.artifact_type
                for update in discipline.documentation_updates
                if update.artifact_type in _QUALIFYING_ARTIFACT_TYPES
            }
        )
        findings.append(
            D7Finding(
                code="PREVENTION_ARTIFACT_UPDATE_RECORDED",
                severity="info",
                citation_basis="RULE",
                artifact_type=None,
                message=(
                    "D7 records a qualifying documentation update: "
                    f"{', '.join(qualifying_types)}."
                ),
                recommendation=(
                    "No action required for the prevention-documentation precondition."
                ),
            )
        )
        if not discipline.has_root_cause_linked_update:
            findings.append(
                D7Finding(
                    code="PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE",
                    severity="error",
                    citation_basis="PDD",
                    artifact_type=None,
                    message=(
                        "No qualifying D7 documentation update declares target=ROOT_CAUSE, so "
                        "the record does not say which proven D4 finding the prevention update "
                        "prevents the recurrence of. An FMEA or Control Plan update that names "
                        "no target is not evidence of prevention for this problem's root cause "
                        "(PDD-8D-013); this is the same fact the D7 to D8 gate and the D8 to "
                        "CLOSED closure boundary both block on."
                    ),
                    recommendation=(
                        "Set target=ROOT_CAUSE on the FMEA or Control Plan documentation update "
                        "that implements the systemic change for the D4 root cause."
                    ),
                )
            )

    root_cause_traceable: bool | None
    if d4 is None:
        findings.append(
            D7Finding(
                code="D4_NOT_SUPPLIED",
                severity="warning",
                citation_basis="PDD",
                artifact_type=None,
                message=(
                    "No D4 record was supplied, so the D7 prevention update could not be checked "
                    "for traceability to a proven root cause."
                ),
                recommendation=(
                    "Supply the report's D4 record so the D7 update can be checked against it."
                ),
            )
        )
        root_cause_traceable = None
    elif not discipline.has_qualifying_update:
        # Already reported as PREVENTION_ARTIFACT_UPDATE_MISSING above; do not double-report.
        root_cause_traceable = False
    elif not discipline.has_root_cause_linked_update:
        # Already reported as PREVENTION_UPDATE_NOT_LINKED_TO_ROOT_CAUSE above; report once.
        root_cause_traceable = False
    elif d4.root_cause.five_why_verdict == "REJECT":
        findings.append(
            D7Finding(
                code="PREVENTION_NOT_TRACEABLE_ROOT_CAUSE",
                severity="error",
                citation_basis="PDD",
                artifact_type=None,
                message=(
                    "D4's recorded five_why_verdict for the root cause is REJECT, so the causal "
                    "chain the D7 update is supposed to prevent recurrence of was not accepted."
                ),
                recommendation=(
                    "Resolve the rejected root-cause 5-Why chain in D4 before relying on it to "
                    "justify a D7 update."
                ),
            )
        )
        root_cause_traceable = False
    elif d4.root_cause.five_why_verdict is None:
        findings.append(
            D7Finding(
                code="PREVENTION_ROOT_CAUSE_VALIDATION_NOT_RUN",
                severity="warning",
                citation_basis="PDD",
                artifact_type=None,
                message=(
                    "D4 records no five_why_verdict for the root cause, so its causal chain has "
                    "not been validated yet."
                ),
                recommendation=(
                    "Run the root-cause 5-Why validation in D4 and record its verdict."
                ),
            )
        )
        root_cause_traceable = False
    else:
        root_cause_traceable = True

    control_plan_payload: dict[str, Any] | None = None
    if control_plan_evidence is not None:
        try:
            cp_dataset = validate_control_plan(control_plan_evidence)
        except (pydantic.ValidationError, TypeError, ValueError) as exc:
            findings.append(
                D7Finding(
                    code="CONTROL_PLAN_EVIDENCE_INVALID",
                    severity="error",
                    citation_basis="PDD",
                    artifact_type="CONTROL_PLAN",
                    message=(
                        "Linked Control Plan evidence is invalid: "
                        + "; ".join(_control_plan_findings(exc))
                        + "."
                    ),
                    recommendation=(
                        "Correct the linked Control Plan data so it satisfies "
                        "quality_core.controlplan.schema.validate_control_plan."
                    ),
                )
            )
        else:
            control_plan_payload = cp_dataset.model_dump(mode="json")
            findings.append(
                D7Finding(
                    code="CONTROL_PLAN_EVIDENCE_VALID",
                    severity="info",
                    citation_basis="PDD",
                    artifact_type="CONTROL_PLAN",
                    message=(
                        "Linked Control Plan evidence is structurally valid "
                        f"({len(cp_dataset.rows)} characteristic row(s))."
                    ),
                    recommendation=(
                        "No action required; the linked Control Plan evidence is valid."
                    ),
                )
            )
    elif any(update.artifact_type == "CONTROL_PLAN" for update in discipline.documentation_updates):
        findings.append(
            D7Finding(
                code="CONTROL_PLAN_EVIDENCE_NOT_PROVIDED",
                severity="warning",
                citation_basis="PDD",
                artifact_type="CONTROL_PLAN",
                message=(
                    "D7 declares a CONTROL_PLAN update but no Control Plan evidence was supplied "
                    "to independently verify it."
                ),
                recommendation=(
                    "Supply the updated Control Plan data so it can be validated against "
                    "quality_core.controlplan.schema.validate_control_plan."
                ),
            )
        )

    fmea_payload: dict[str, Any] | None = None
    if fmea_action is not None and fmea_before is not None:
        action = fmea_action if isinstance(fmea_action, Action) else Action(**fmea_action)
        effectiveness: Effectiveness = action.effectiveness(*fmea_before)
        fmea_payload = asdict(effectiveness)
        findings.append(
            D7Finding(
                code="FMEA_RESIDUAL_RISK",
                severity="info",
                citation_basis="PDD",
                artifact_type="FMEA",
                message=(
                    f"FMEA residual risk after the D7 update: RPN "
                    f"{effectiveness.initial_rpn} to {effectiveness.revised_rpn} "
                    f"(delta {effectiveness.rpn_delta}), Action Priority "
                    f"{effectiveness.initial_ap} to {effectiveness.revised_ap} "
                    f"({'reduced' if effectiveness.ap_reduced else 'not reduced'})."
                ),
                recommendation=(
                    "No action required; this is informational residual-risk context, not a "
                    "pass/fail check."
                ),
            )
        )
    elif fmea_action is not None or fmea_before is not None:
        findings.append(
            D7Finding(
                code="FMEA_RESIDUAL_RISK_EVIDENCE_INCOMPLETE",
                severity="warning",
                citation_basis="PDD",
                artifact_type="FMEA",
                message=(
                    "Both fmea_action and fmea_before are required to compute FMEA residual "
                    "risk; only one was supplied."
                ),
                recommendation=(
                    "Supply both the pre-update (severity, occurrence, detection) rating and the "
                    "re-rated Action to compute residual risk."
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
            D7Finding(
                code="D7_READY",
                severity="info",
                citation_basis="PLATFORM_UNCITED",
                artifact_type=None,
                message=(
                    "D7 prevention documentation is recorded, qualifying, and traceable to a "
                    "proven D4 root cause."
                ),
                recommendation="Prevention documentation is complete; proceed to D8.",
            )
        )
        verdict, valid = "ACCEPT", True

    return D7ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        prevention_documented=discipline.is_documented,
        has_qualifying_update=discipline.has_qualifying_update,
        root_cause_linked_update=discipline.has_root_cause_linked_update,
        root_cause_traceable=root_cause_traceable,
        control_plan_evidence=control_plan_payload,
        fmea_effectiveness=fmea_payload,
        findings=findings,
        recommendations=_dedupe(f.recommendation for f in findings),
    )


# ==============================================================================
# 9. D8 — Recognize the team and close
# ==============================================================================


@dataclass
class D8Finding:
    """Finding raised against the D8 closure record or the closure evidence it is judged against.

    ``code`` is either one of the nine ``eight_d_schema._ClosureDeficiencyCode`` values, reused
    **verbatim** from the shared ``_closure_evidence_deficiencies`` evaluator so this advisory
    engine and the D8→CLOSED gate can never name the same deficiency differently, or one of the
    codes this engine owns outright: ``D8_NOT_STARTED``, ``D8_DOCUMENTATION_NOT_REVIEWED``,
    ``D8_REVIEW_PROVENANCE_INCOMPLETE``, ``D8_ROOT_CAUSE_REJECTED``,
    ``D8_WARNING_OVERRIDE_MISSING`` and the clean-pass ``D8_READY``.
    """

    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    recommendation: str
    citation_basis: Literal["RULE", "PDD", "PLATFORM_UNCITED"] = "PLATFORM_UNCITED"

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D8 finding."""
        return asdict(self)


@dataclass
class D8ValidationResult:
    """Complete D8 (recognize the team and close out) validation result.

    ``closeable`` is ``_closure_evidence_deficiencies(report) == ()`` — the one shared
    closure-evidence evaluator that the ``CLOSED``-report model validator and
    ``transition_eight_d``'s D8→CLOSED gate both consume — read directly and never recomputed by
    counting findings, so it cannot drift from what those two checkpoints will decide about the
    same report.

    ``closeable`` and ``verdict`` are deliberately kept as two distinct facts. ``verdict`` is the
    advisory three-value read every engine in this module returns, and it also reflects
    D8-record-level findings that the closure boundary does not itself evaluate — notably
    ``D8_DOCUMENTATION_NOT_REVIEWED``, since ``_closure_evidence_deficiencies`` never reads
    ``documentation_reviewed``. A report can therefore be ``closeable=True`` while this engine
    still returns ``REJECT``, and the two are not in conflict: they answer different questions.

    ``d8_recorded``, ``documentation_reviewed`` and ``linked_five_why_verdict`` describe the D8
    record itself and degrade to ``False`` / ``False`` / ``None`` when ``report.d8`` is ``None``,
    which is a legitimate in-progress state rather than a malformed report.
    """

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    d8_recorded: bool
    documentation_reviewed: bool
    linked_five_why_verdict: FiveWhyVerdict | None
    closeable: bool
    findings: list[D8Finding]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the D8 result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "d8_recorded": self.d8_recorded,
            "documentation_reviewed": self.documentation_reviewed,
            "linked_five_why_verdict": self.linked_five_why_verdict,
            "closeable": self.closeable,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": list(self.recommendations),
        }


def validate_d8_closure(report: EightDReport) -> D8ValidationResult:
    """Validate D8: the closing documentation review and the whole-report closure evidence.

    Ford Global 8D's D8 completes the team's experience by recognizing individual and team
    contributions, and its closing checklist asks to "ensure that all related documentation is
    reviewed and updated" (``RULE-8D-D8``). **What that passage establishes** is that a
    documentation review is part of closing out an 8D. **What this engine does** with it is
    narrower and is this platform's translation: it reports whether ``documentation_reviewed`` was
    set. The manual states no review checklist, no reviewer competence rule and no completeness
    algorithm, and none is invented here. Team recognition itself carries no checkable predicate —
    ``team_recognition_notes`` is required non-blank text at the schema level, and judging its
    adequacy would be a claim no source supports — so this engine asserts nothing about it.

    **Advisory pre-flight check that shares its rules with the gate.** The closure-evidence half of
    this engine is ``eight_d_schema._closure_evidence_deficiencies(report)``, called once and
    reported verbatim: each returned deficiency becomes one ``error`` finding carrying the
    evaluator's own ``code`` and ``message``. That is the same evaluator the ``CLOSED``-report
    model validator and ``transition_eight_d``'s D8→CLOSED gate consume (the latter through
    ``_closure_reasons``, ``RULE-8D-GATE-CLOSURE`` / ``PDD-8D-010`` / ``PDD-8D-013``), so this
    engine's ``REJECT`` and the gate's block cannot disagree about the same report. No closure rule
    is re-derived here, and this engine never calls ``transition_eight_d``.

    **The whole-report signature is a documented deviation** from this module's "one typed
    discipline argument per engine" norm, recorded as Process Design Decision #14: the shared
    closure evaluator needs ``report.d8``, ``report.root_cause_validation``, ``report.d3``,
    ``report.d6`` and ``report.d7`` together, and reconstructing a throwaway report internally to
    satisfy its signature would be reimplementation risk for no benefit. See the module docstring.

    **``closure_approved`` is deliberately not read.** Whether closure has been *approved* is
    orthogonal to whether the evidence supporting it is complete; ``D8Discipline`` already refuses
    at construction time to record ``closure_approved=True`` on a ``REJECT`` verdict or on an
    unoverridden ``WARNING``, and ``EightDReport``'s ``CLOSED``-state validator is the actual gate.
    Re-checking either here would be a second copy of a rule the schema already owns.

    The two D8-record findings that mirror those model rules —
    ``D8_ROOT_CAUSE_REJECTED`` (``RULE-8D-GATE-CLOSURE``: the systemic root cause of the root cause
    must be established and resolved) and ``D8_WARNING_OVERRIDE_MISSING`` (Process Design Decision
    #4: closing on a marginal causal chain requires an explicit, attributable override) — are
    reported as *advisory* ``error`` findings against the record's own
    ``linked_five_why_verdict``, and are never reported together: a ``REJECT`` verdict cannot also
    be a ``WARNING`` missing its override.

    Args:
        report: An already-validated ``EightDReport``. The untrusted-data trust boundary is
            ``validate_eight_d``; this engine performs no schema validation of its own.

    Returns:
        ``D8ValidationResult`` — ``REJECT`` when any closure deficiency or D8-record error is
        present, ``WARNING`` when D8 has simply not been recorded yet, ``ACCEPT`` otherwise.
    """
    discipline: D8Discipline | None = report.d8
    deficiencies = _closure_evidence_deficiencies(report)
    findings: list[D8Finding] = [
        D8Finding(
            code=deficiency.code,
            severity="error",
            citation_basis="PDD",
            message=deficiency.message,
            recommendation=(
                "Complete the closure evidence this deficiency names before closing the report; "
                "the D8 to CLOSED gate blocks on the same shared evaluator."
            ),
        )
        for deficiency in deficiencies
    ]

    if discipline is None:
        findings.append(
            D8Finding(
                code="D8_NOT_STARTED",
                severity="warning",
                citation_basis="PLATFORM_UNCITED",
                message=(
                    "D8 has not been recorded on this report yet; team recognition and the "
                    "closure documentation review have not started."
                ),
                recommendation=(
                    "Record a D8Discipline once the team recognition and documentation review "
                    "are ready to be captured."
                ),
            )
        )
    else:
        if not discipline.documentation_reviewed:
            findings.append(
                D8Finding(
                    code="D8_DOCUMENTATION_NOT_REVIEWED",
                    severity="error",
                    citation_basis="RULE",
                    message=(
                        "D8's documentation has not been marked reviewed; Ford Global 8D's D8 "
                        "checklist asks to ensure that all related documentation is reviewed and "
                        "updated (RULE-8D-D8)."
                    ),
                    recommendation=(
                        "Set documentation_reviewed=True once the closing documentation review is "
                        "complete, and record documentation_review_date/documentation_reviewed_by."
                    ),
                )
            )
        elif (
            discipline.documentation_reviewed_by is None
            or discipline.documentation_review_date is None
        ):
            findings.append(
                D8Finding(
                    code="D8_REVIEW_PROVENANCE_INCOMPLETE",
                    severity="warning",
                    citation_basis="PDD",
                    message=(
                        "D8 records the closing documentation review as complete but does not say "
                        "who performed it or when; the review is therefore unattributable. "
                        "RULE-8D-D8 requires the review itself; requiring it to be attributable "
                        "is this platform's heuristic (Process Design Decision #15)."
                    ),
                    recommendation=(
                        "Record documentation_reviewed_by and documentation_review_date alongside "
                        "documentation_reviewed=True."
                    ),
                )
            )
        if discipline.linked_five_why_verdict == "REJECT":
            findings.append(
                D8Finding(
                    code="D8_ROOT_CAUSE_REJECTED",
                    severity="error",
                    citation_basis="RULE",
                    message=(
                        "D8's linked 5-Why verdict is REJECT; Ford Global 8D requires the systemic "
                        "root cause of the root cause to be established and resolved before "
                        "closure (RULE-8D-GATE-CLOSURE)."
                    ),
                    recommendation=(
                        "Resolve the causal chain (or replace it with one that is not REJECT) "
                        "before closure."
                    ),
                )
            )
        elif (
            discipline.linked_five_why_verdict == "WARNING" and discipline.warning_override is None
        ):
            findings.append(
                D8Finding(
                    code="D8_WARNING_OVERRIDE_MISSING",
                    severity="error",
                    citation_basis="PDD",
                    message=(
                        "D8's linked 5-Why verdict is WARNING with no recorded warning_override; "
                        "this platform requires an explicit, attributable override to close on a "
                        "marginal causal chain (Process Design Decision #4)."
                    ),
                    recommendation=(
                        "Record a WarningOverride (approved_by, justification, override_date) "
                        "before closure."
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
            D8Finding(
                code="D8_READY",
                severity="info",
                citation_basis="PLATFORM_UNCITED",
                message=(
                    "D8 is recorded, its documentation is reviewed, and the whole-report closure "
                    "evidence is complete."
                ),
                recommendation="D8 is complete; the report may be closed.",
            )
        )
        verdict, valid = "ACCEPT", True

    return D8ValidationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        d8_recorded=discipline is not None,
        documentation_reviewed=False if discipline is None else discipline.documentation_reviewed,
        linked_five_why_verdict=(
            None if discipline is None else discipline.linked_five_why_verdict
        ),
        closeable=not deficiencies,
        findings=findings,
        recommendations=_dedupe(f.recommendation for f in findings),
    )


# ==============================================================================
# 10. validate_8d — full-report orchestrator
# ==============================================================================


@dataclass(frozen=True)
class EightDValidationResult:
    """One whole-report 8D verdict: state, every gate, and every per-discipline advisory result.

    ``verdict`` answers **"is this report closure-ready right now"**, not "is this report
    internally valid". ``EightDReport`` already refuses to construct an internally inconsistent
    report, so any report reaching ``validate_8d`` is schema-valid by definition. A report still at
    D2 with D3-D8 legitimately absent is correctly reported ``REJECT`` / ``closeable=False``: it is
    not yet closeable. That is the intended reading, not a false positive.

    ``gate_reasons`` is every blocking gate reason the state machine would raise on the closure
    path, in ``eight_d.py``'s stable ``GateCode`` vocabulary, and ``closeable`` is exactly
    ``gate_reasons == ()``. There is no ``d4`` field, deliberately — see ``validate_8d``.
    """

    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    valid: bool
    state: EightDState
    closeable: bool
    gate_reasons: tuple[TransitionReason, ...]
    d0: D0ValidationResult | None
    d1: D1ValidationResult | None
    d2: D2ValidationResult | None
    d3: D3ValidationResult | None
    d5: D5ValidationResult | None
    d6: D6ValidationResult | None
    d7: D7ValidationResult | None
    d8: D8ValidationResult
    report: EightDReport

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of the whole-report result."""
        return {
            "verdict": self.verdict,
            "valid": self.valid,
            "state": self.state,
            "closeable": self.closeable,
            "gate_reasons": [reason.to_dict() for reason in self.gate_reasons],
            "d0": None if self.d0 is None else self.d0.to_dict(),
            "d1": None if self.d1 is None else self.d1.to_dict(),
            "d2": None if self.d2 is None else self.d2.to_dict(),
            "d3": None if self.d3 is None else self.d3.to_dict(),
            "d5": None if self.d5 is None else self.d5.to_dict(),
            "d6": None if self.d6 is None else self.d6.to_dict(),
            "d7": None if self.d7 is None else self.d7.to_dict(),
            "d8": self.d8.to_dict(),
            "report": copy.deepcopy(self.report.model_dump(mode="json")),
        }


def validate_8d(report: EightDReport) -> EightDValidationResult:
    """Run every 8D discipline engine and every closure gate over one report, read-only.

    This function implements no rule of its own: it dispatches to the already-tested engines and
    evaluators and combines their answers. Each discipline engine is called only when its record
    exists (``None`` in, ``None`` out — no placeholder discipline is ever constructed), with only
    the cross-discipline arguments the report actually carries (``d5``'s ``d4``, ``d6``'s ``d5``,
    ``d7``'s ``d4``); every optional *untrusted evidence* argument is left at its ``None`` default,
    because none of that evidence (Is/Is-Not data, a linked NCR dataset, COPQ costs, Control Plan
    or FMEA payloads) is persisted on an ``EightDReport``. ``validate_d8_closure`` is always
    called, since it handles ``report.d8 is None`` internally, so ``d8`` is never ``None``.

    **D4 is deliberately excluded from the sweep, and that is not an oversight.**
    ``validate_d4_root_cause`` requires the raw occurrence and escape 5-Why chains as arguments,
    and those chains are not persisted anywhere on ``EightDReport`` — only the terminal
    ``RootCauseFinding.five_why_verdict`` metadata is. There is no report-resident data to supply,
    so calling it here would be impossible, not merely unhelpful, and ``EightDValidationResult``
    carries no ``d4`` field at all rather than a half-wired one. The question the acceptance
    criteria actually ask of D4 — "is the RCA rejected" — is answered end-to-end through
    ``report.root_cause_validation``, which ``_closure_evidence_deficiencies`` already reads and
    which surfaces here as a ``ROOT_CAUSE_REJECTED`` gate reason.

    **Gates.** ``gate_reasons`` is ``_closure_reasons(report)`` — every closure-boundary deficiency
    mapped onto the public ``GateCode`` vocabulary — **plus** ``_linked_ncr_reason(report)`` when
    it fires. The extra call is required for completeness, not duplication: linked-NCR validity
    gates the D3→D4 step only (``PDD-8D-008``) and is not part of the closure-evidence contract, so
    ``_closure_reasons`` alone would let a genuinely blocking ``LINKED_NCR_INVALID`` vanish from a
    whole-report read. ``_prevention_reason`` is *not* called for the mirror-image reason: both of
    its codes are already produced by ``_closure_reasons``, so calling it too would report the same
    fact twice. Note that ``_closure_reasons`` collapses ``D8_MISSING``,
    ``ROOT_CAUSE_VALIDATION_MISSING``, ``ROOT_CAUSE_VERDICT_MISMATCH`` and
    ``WARNING_OVERRIDE_MISSING`` onto the single ``ROOT_CAUSE_EVIDENCE_MISSING`` gate code; that is
    the state machine's existing public vocabulary and is passed through unchanged. The
    uncollapsed, per-deficiency codes remain available on ``result.d8.findings``.

    **Verdict combination** is REJECT > WARNING > ACCEPT over ``gate_reasons`` together with every
    computed discipline verdict — this platform's own aggregation policy (Process Design Decision
    #14); no manual defines a multi-discipline orchestrator algorithm. Any gate reason, or any
    discipline's ``REJECT``, makes the whole report ``REJECT``.

    ``validate_8d`` never calls ``transition_eight_d`` and never mutates ``report``; advancing or
    closing a report remains the state machine's job alone.

    Args:
        report: An already-validated ``EightDReport``. The untrusted-data trust boundary is
            ``validate_eight_d``; this orchestrator performs no schema validation of its own.

    Returns:
        ``EightDValidationResult`` carrying the report's state, its closure readiness, every gate
        reason, and each computed discipline result.
    """
    state = _state(report)

    d0 = validate_d0_readiness(report.d0) if report.d0 is not None else None
    d1 = validate_d1_team(report.d1) if report.d1 is not None else None
    d2 = validate_d2_problem_description(report.d2) if report.d2 is not None else None
    d3 = validate_d3_containment(report.d3) if report.d3 is not None else None
    d5 = validate_d5_pca_selection(report.d5, d4=report.d4) if report.d5 is not None else None
    d6 = (
        validate_d6_implementation_validation(report.d6, d5=report.d5)
        if report.d6 is not None
        else None
    )
    d7 = validate_d7_prevention(report.d7, d4=report.d4) if report.d7 is not None else None
    d8 = validate_d8_closure(report)

    reasons: list[TransitionReason] = list(_closure_reasons(report))
    ncr_reason = _linked_ncr_reason(report)
    if ncr_reason is not None:
        reasons.append(ncr_reason)
    gate_reasons = tuple(reasons)

    results: list[
        D0ValidationResult
        | D1ValidationResult
        | D2ValidationResult
        | D3ValidationResult
        | D5ValidationResult
        | D6ValidationResult
        | D7ValidationResult
        | D8ValidationResult
    ] = [r for r in (d0, d1, d2, d3, d5, d6, d7, d8) if r is not None]

    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    if gate_reasons or any(r.verdict == "REJECT" for r in results):
        verdict, valid = "REJECT", False
    elif any(r.verdict == "WARNING" for r in results):
        verdict, valid = "WARNING", True
    else:
        verdict, valid = "ACCEPT", True

    return EightDValidationResult(
        verdict=verdict,
        valid=valid,
        state=state,
        closeable=not gate_reasons,
        gate_reasons=gate_reasons,
        d0=d0,
        d1=d1,
        d2=d2,
        d3=d3,
        d5=d5,
        d6=d6,
        d7=d7,
        d8=d8,
        report=report,
    )

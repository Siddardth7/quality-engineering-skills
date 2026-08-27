"""
scar.py
Deterministic Supplier Corrective Action Request (SCAR) generator for the SQE suite.

The one invariant this module exists to hold
--------------------------------------------
**This generator never authors, infers, or synthesizes a root cause.** It *requests* one from the
supplier and *validates* the one the supplier returns, by dispatching that response to
``quality_core.rca``'s reversible 5-Why validator. ``SCARResult.root_cause`` is only ever copied
verbatim out of the sub-engine's own payload; it is never assigned a string literal, an f-string, a
template, or a placeholder default anywhere in this file. A SCAR with no supplier response carries
``root_cause=None`` and can never reach ``CLOSABLE``.

Cross-engine evidence linkage
-----------------------------
Three evidence slots are dispatched to their owning engines and their findings are surfaced
verbatim — no rule belonging to a sub-engine is re-encoded here:

- ``linked_ncr`` -> :func:`quality_core.ncr.schema.validate_ncr`
- ``supplier_root_cause`` -> :func:`quality_core.rca.five_why.validate_five_why_chain`
- ``cost_impact`` -> :func:`quality_core.copq.estimator.estimate_copq`

A fourth slot, ``vendor_scorecard``, always resolves ``LINKAGE_NOT_AVAILABLE``: the
``quality_core.sqe.scorecard`` engine (#118) does not exist yet. It is never verdict-affecting.

Imports run downward only (``sqe`` -> ``ncr``/``rca``/``copq``); none of those packages imports
``sqe``.

Standards basis
---------------
Only the three rendered section headings trace to a published source, each through its own
``ASSUMPTIONS_LOG.md`` entry and ``CITATIONS.tsv`` row: **Root-Cause Requirement**
(RULE-SQE-011), **Corrective-Action Requirement** (RULE-SQE-012), and **Prevention /
Read-Across** (RULE-SQE-013), reusing sources already verified for the RCA milestone.

Headings for problem definition (Ford 8D D2), containment (D3), and verification of effectiveness
(D6) are **deliberately withheld**: no verified quotation for them exists in this repository, and
writing heading text ahead of its citation is the fabrication the citation gate exists to prevent.
Their *mechanisms* are fully wired regardless — ``SCARRequest.due_date`` is carried and its absence
is warned about, and ``verification_of_effectiveness`` gates ``CLOSABLE``.

The status state machine, the linkage dispatch, and ``SCARConfig`` assert **no** published
standard; ISO 9001:2015 §8.4/§10.2 and IATF 16949:2016 §8.4 require that nonconformity drive
corrective action but supply no status vocabulary and no closure criteria. See
``ASSUMPTIONS_LOG.md`` ("Process Design Decisions").
"""

from __future__ import annotations

import copy
import datetime
from dataclasses import dataclass, field
from typing import Any, Literal

import pydantic

from quality_core.copq.estimator import estimate_copq
from quality_core.io.validate import clean_pydantic_message
from quality_core.ncr.schema import validate_ncr
from quality_core.rca.five_why import validate_five_why_chain
from quality_core.sqe.schema import SCARRequest

__all__ = [
    "LINKAGE_KEYS",
    "LinkageKey",
    "LinkageVerdict",
    "SCARConfig",
    "SCARLinkageResult",
    "SCARResult",
    "SCARSection",
    "ScarStatus",
    "generate_scar",
]

LinkageVerdict = Literal[
    "EVIDENCE_VALID",
    "EVIDENCE_INVALID",
    "EVIDENCE_NOT_SUPPLIED",
    "LINKAGE_NOT_AVAILABLE",
]

ScarStatus = Literal[
    "DRAFT",
    "ISSUABLE",
    "AWAITING_SUPPLIER_RESPONSE",
    "RESPONSE_REJECTED",
    "CLOSABLE",
    "INDETERMINATE",
]

LinkageKey = Literal[
    "linked_ncr",
    "supplier_root_cause",
    "cost_impact",
    "vendor_scorecard",
]

#: Every linkage slot this engine knows about, in evaluation order.
LINKAGE_KEYS: tuple[LinkageKey, ...] = (
    "linked_ncr",
    "supplier_root_cause",
    "cost_impact",
    "vendor_scorecard",
)

#: The linkage slots that can move the status. ``vendor_scorecard`` is deliberately absent.
_VERDICT_AFFECTING_KEYS: tuple[LinkageKey, ...] = (
    "linked_ncr",
    "supplier_root_cause",
    "cost_impact",
)

_ENGINE_NCR: str = "quality_core.ncr"
_ENGINE_RCA: str = "quality_core.rca"
_ENGINE_COPQ: str = "quality_core.copq"

_STANDARDS_BASIS: str = (
    "AIAG CQI-20 Effective Problem Solving (2nd Edition, 2018) and the Ford Global 8D Manual back "
    "the three rendered section headings only (ASSUMPTIONS_LOG.md RULE-SQE-011/008/009). The "
    "status state machine, the linkage dispatch, and SCARConfig assert no published standard: "
    "ISO 9001:2015 §8.4/§10.2 and IATF 16949:2016 §8.4 require corrective action but supply no "
    "status vocabulary and no closure criteria."
)

_ROOT_CAUSE_AUTHORITY: str = (
    "The root cause is stated by the supplier and validated here; this generator never authors, "
    "infers, or substitutes one."
)


@dataclass(frozen=True)
class SCARConfig:
    """Caller-overridable SCAR generator configuration.

    No field here traces to a published standard. The hard invariants — that a root cause is
    only ever supplier-authored, and that ``CLOSABLE`` requires a stated verification of
    effectiveness — are **not** configurable: they are process-authority rules, not caller-tunable
    thresholds, and are hardcoded in :func:`generate_scar`'s state machine.

    Attributes
    ----------
    evaluate_vendor_scorecard_linkage : bool
        Whether to include the ``"vendor_scorecard"`` key in ``SCARResult.linkage`` at all. It
        always resolves ``LINKAGE_NOT_AVAILABLE`` this release (``quality_core.sqe.scorecard``,
        #118, does not exist yet) and is never verdict-affecting either way; this flag exists only
        so a caller who does not want the placeholder key can omit it.
    """

    evaluate_vendor_scorecard_linkage: bool = True

    def __post_init__(self) -> None:
        """Reject a non-bool flag; ``bool`` is checked explicitly, never truthiness."""
        if not isinstance(self.evaluate_vendor_scorecard_linkage, bool):
            raise TypeError(
                "evaluate_vendor_scorecard_linkage must be a bool, got "
                f"{type(self.evaluate_vendor_scorecard_linkage).__name__}: "
                f"{self.evaluate_vendor_scorecard_linkage!r}"
            )


@dataclass(frozen=True)
class SCARLinkageResult:
    """Outcome of dispatching one evidence slot to its owning engine.

    ``findings`` is always the sub-engine's own text, surfaced verbatim — this module authors
    none of it. ``raw_result`` is the sub-engine's own serialized payload, or ``None`` when the
    sub-engine produced none (evidence absent, or the call raised).
    """

    linkage_key: LinkageKey
    verdict: LinkageVerdict
    engine: str | None
    findings: tuple[str, ...]
    rationale: str
    raw_result: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary, deep-copying the sub-engine payload."""
        return {
            "linkage_key": self.linkage_key,
            "verdict": self.verdict,
            "engine": self.engine,
            "findings": list(self.findings),
            "rationale": self.rationale,
            "raw_result": None if self.raw_result is None else copy.deepcopy(self.raw_result),
        }


@dataclass(frozen=True)
class SCARSection:
    """One rendered SCAR section, traced to the ``ASSUMPTIONS_LOG.md`` rule that authorizes it."""

    heading: str
    rule_id: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "heading": self.heading,
            "rule_id": self.rule_id,
            "content": self.content,
        }


@dataclass
class SCARResult:
    """Structured result of generating one Supplier Corrective Action Request.

    ``root_cause`` is ``None`` until the supplier returns a chain this engine's RCA linkage can
    parse, and is then a verbatim copy of that chain's own terminal cause. ``due_date`` and
    ``date_issued`` are ISO-8601 strings built once at construction from the request; they are
    never re-derived inside :meth:`to_dict`.
    """

    supplier_id: str
    scar_id: str | None
    issue_description: str
    status: ScarStatus
    sections: list[SCARSection]
    linkage: dict[str, SCARLinkageResult]
    root_cause: str | None
    verification_of_effectiveness: str | None
    due_date: str | None
    date_issued: str | None
    reason: str | None
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    standards_basis: str = _STANDARDS_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary.

        Every nested list and dict is copied, so a caller mutating the returned structure cannot
        corrupt this result's state.
        """
        return {
            "supplier_id": self.supplier_id,
            "scar_id": self.scar_id,
            "issue_description": self.issue_description,
            "status": self.status,
            "sections": [section.to_dict() for section in self.sections],
            "linkage": {key: value.to_dict() for key, value in self.linkage.items()},
            "root_cause": self.root_cause,
            "verification_of_effectiveness": self.verification_of_effectiveness,
            "due_date": self.due_date,
            "date_issued": self.date_issued,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "standards_basis": self.standards_basis,
        }


# ===========================================================================
# Helpers
# ===========================================================================


def _normalise_optional_text(value: str | None) -> str | None:
    """Strip a caller-supplied statement; a blank or whitespace-only one normalises to ``None``.

    Matches ``schema.py``'s ``_blank_string_to_none`` convention, so a whitespace-only
    verification-of-effectiveness statement can never satisfy the ``CLOSABLE`` gate.
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _iso_or_none(value: datetime.date | None) -> str | None:
    """Render a date as ISO-8601, passing ``None`` through untouched (never imputed)."""
    return None if value is None else value.isoformat()


def _findings_from_exception(exc: Exception) -> tuple[str, ...]:
    """Turn a sub-engine exception into findings carrying the sub-engine's own message text."""
    if isinstance(exc, pydantic.ValidationError):
        findings: list[str] = []
        for error in exc.errors():
            message = clean_pydantic_message(str(error["msg"]))
            location = ".".join(str(part) for part in error["loc"])
            findings.append(f"{location}: {message}" if location else message)
        return tuple(findings)
    return (str(exc),)


# ===========================================================================
# Linkage evaluation — one function per evidence slot
# ===========================================================================


def _evaluate_ncr_linkage(evidence: Any) -> SCARLinkageResult:
    """Validate linked nonconformance evidence through ``quality_core.ncr.validate_ncr``."""
    if evidence is None:
        return SCARLinkageResult(
            linkage_key="linked_ncr",
            verdict="EVIDENCE_NOT_SUPPLIED",
            engine=_ENGINE_NCR,
            findings=(),
            rationale=(
                "No nonconformance evidence was supplied for this SCAR; a linked_ncr_id on the "
                "request is metadata about intent, not proof, and is not validated in its place."
            ),
            raw_result=None,
        )
    try:
        dataset = validate_ncr(evidence)
    except (pydantic.ValidationError, TypeError) as exc:
        return SCARLinkageResult(
            linkage_key="linked_ncr",
            verdict="EVIDENCE_INVALID",
            engine=_ENGINE_NCR,
            findings=_findings_from_exception(exc),
            rationale="quality_core.ncr rejected the supplied nonconformance evidence.",
            raw_result=None,
        )
    return SCARLinkageResult(
        linkage_key="linked_ncr",
        verdict="EVIDENCE_VALID",
        engine=_ENGINE_NCR,
        findings=(),
        rationale="quality_core.ncr accepted the supplied nonconformance evidence.",
        raw_result=dataset.model_dump(),
    )


def _evaluate_root_cause_linkage(evidence: Any, problem_statement: str) -> SCARLinkageResult:
    """Validate the supplier-returned root cause through ``quality_core.rca``'s 5-Why validator.

    Per the E6 scope decision recorded in ``ASSUMPTIONS_LOG.md``, only the 5-Why validator is
    consulted: Kepner-Tregoe Is/Is-Not is a scoping tool and returns no accept/reject verdict to
    gate on.

    A structurally malformed chain (the validator raises) and a logically rejected chain (the
    validator returns ``valid=False``) both collapse to ``EVIDENCE_INVALID``; the parsed chain is
    surfaced in ``raw_result`` whenever one exists, so a reviewer can see exactly what the supplier
    submitted even when it was rejected.
    """
    if evidence is None:
        return SCARLinkageResult(
            linkage_key="supplier_root_cause",
            verdict="EVIDENCE_NOT_SUPPLIED",
            engine=_ENGINE_RCA,
            findings=(),
            rationale=(
                "No supplier root-cause response has been received. " + _ROOT_CAUSE_AUTHORITY
            ),
            raw_result=None,
        )
    try:
        result = validate_five_why_chain(data=evidence, problem_statement=problem_statement)
    except (pydantic.ValidationError, TypeError) as exc:
        return SCARLinkageResult(
            linkage_key="supplier_root_cause",
            verdict="EVIDENCE_INVALID",
            engine=_ENGINE_RCA,
            findings=_findings_from_exception(exc),
            rationale=(
                "quality_core.rca could not parse the supplier-returned causal chain. "
                + _ROOT_CAUSE_AUTHORITY
            ),
            raw_result=None,
        )

    raw_result = result.to_dict()
    if not result.valid:
        findings = tuple(f"{finding.code}: {finding.message}" for finding in result.anti_patterns)
        if not findings:
            findings = (
                f"quality_core.rca returned verdict {result.verdict!r} with reversibility_score "
                f"{result.reversibility_score}.",
            )
        return SCARLinkageResult(
            linkage_key="supplier_root_cause",
            verdict="EVIDENCE_INVALID",
            engine=_ENGINE_RCA,
            findings=findings,
            rationale=(
                "quality_core.rca rejected the supplier-returned root cause. "
                + _ROOT_CAUSE_AUTHORITY
            ),
            raw_result=raw_result,
        )
    return SCARLinkageResult(
        linkage_key="supplier_root_cause",
        verdict="EVIDENCE_VALID",
        engine=_ENGINE_RCA,
        findings=(),
        rationale=(
            "quality_core.rca accepted the supplier-returned root cause. " + _ROOT_CAUSE_AUTHORITY
        ),
        raw_result=raw_result,
    )


def _evaluate_cost_impact_linkage(evidence: Any) -> SCARLinkageResult:
    """Quantify the cost impact through ``quality_core.copq.estimate_copq``.

    A valid but zero-total estimate stays ``EVIDENCE_VALID``: ``estimate_copq`` warns rather than
    raises on an all-zero rollup, and "$0 impact" is a result, not an invalid input.
    """
    if evidence is None:
        return SCARLinkageResult(
            linkage_key="cost_impact",
            verdict="EVIDENCE_NOT_SUPPLIED",
            engine=_ENGINE_COPQ,
            findings=(),
            rationale="No cost-of-poor-quality evidence was supplied for this SCAR.",
            raw_result=None,
        )
    try:
        result = estimate_copq(items=evidence)
    except (pydantic.ValidationError, TypeError, ValueError) as exc:
        return SCARLinkageResult(
            linkage_key="cost_impact",
            verdict="EVIDENCE_INVALID",
            engine=_ENGINE_COPQ,
            findings=_findings_from_exception(exc),
            rationale="quality_core.copq rejected the supplied cost-impact evidence.",
            raw_result=None,
        )
    return SCARLinkageResult(
        linkage_key="cost_impact",
        verdict="EVIDENCE_VALID",
        engine=_ENGINE_COPQ,
        findings=(),
        rationale="quality_core.copq accepted and costed the supplied cost-impact evidence.",
        raw_result=result.to_dict(),
    )


def _evaluate_vendor_scorecard_linkage() -> SCARLinkageResult:
    """Placeholder slot for vendor-scorecard linkage — always ``LINKAGE_NOT_AVAILABLE``.

    ``quality_core.sqe.scorecard`` (#118) is not implemented yet. This slot takes no input, has no
    branches, and is never verdict-affecting.
    """
    return SCARLinkageResult(
        linkage_key="vendor_scorecard",
        verdict="LINKAGE_NOT_AVAILABLE",
        engine=None,
        findings=(),
        rationale=(
            "Vendor scorecard linkage is not available in this release: the vendor scorecard "
            "engine (#118) has not shipped. This slot never affects the SCAR status."
        ),
        raw_result=None,
    )


def _root_cause_from_linkage(linkage_result: SCARLinkageResult) -> str | None:
    """Copy the supplier's own root cause out of the RCA payload, or return ``None``.

    This is the only assignment path to ``SCARResult.root_cause``. Nothing in this module ever
    supplies a literal, a template, or a fallback here: no supplier chain means no root cause.
    """
    if linkage_result.raw_result is None:
        return None
    root_cause: str | None = linkage_result.raw_result["root_cause"]
    return root_cause


# ===========================================================================
# Section rendering
# ===========================================================================


def _build_sections(request: SCARRequest) -> list[SCARSection]:
    """Render the SCAR sections that currently carry a verified citation.

    Only three sections ship: each is authorized by a ``RULE-SQE-0NN`` entry in
    ``ASSUMPTIONS_LOG.md`` with matching ``CITATIONS.tsv`` rows. Their text is a standing
    requirement on the supplier and does not vary with the request payload, so nothing from
    ``request`` is interpolated — the withheld Containment section is the one that would carry
    ``request.due_date``, and until it has a citation that date is surfaced through
    ``SCARResult.due_date`` and its absence through a warning instead.

    Problem-definition (Ford 8D D2), containment (D3), and verification-of-effectiveness (D6)
    headings are withheld pending verified quotations; adding one means adding its
    ``RULE-SQE-0NN`` row first, then one entry to this list.
    """
    return [
        SCARSection(
            heading="Root-Cause Requirement",
            rule_id="RULE-SQE-011",
            content=(
                "State the systemic root cause of this nonconformity. Keep asking why past any "
                "individual- or task-level explanation until the procedure, policy, or practice "
                "that allowed the problem to occur and to escape is established, and state that "
                "cause explicitly (AIAG CQI-20 / Ford Global 8D — ASSUMPTIONS_LOG.md "
                "RULE-SQE-011). " + _ROOT_CAUSE_AUTHORITY
            ),
        ),
        SCARSection(
            heading="Corrective-Action Requirement",
            rule_id="RULE-SQE-012",
            content=(
                "Define and implement the permanent corrective action(s) that resolve the "
                "established systemic root cause. Changing only the affected product is not a "
                "corrective action: the system that allowed the problem must itself be changed "
                "(Ford Global 8D — ASSUMPTIONS_LOG.md RULE-SQE-012)."
            ),
        ),
        SCARSection(
            heading="Prevention / Read-Across",
            rule_id="RULE-SQE-013",
            content=(
                "Identify every other part, product, line, and process to which the same systemic "
                "root cause applies, and extend the corrective action to them so a similar "
                "problem cannot arise there (Ford Global 8D — ASSUMPTIONS_LOG.md RULE-SQE-013)."
            ),
        ),
    ]


# ===========================================================================
# Status resolution
# ===========================================================================


def _resolve_status(
    *,
    issued: bool,
    ncr_verdict: LinkageVerdict,
    root_cause_verdict: LinkageVerdict,
    cost_verdict: LinkageVerdict,
    voe: str | None,
) -> tuple[ScarStatus, str | None]:
    """Resolve the SCAR status and its reason, first matching rule winning.

    ``vendor_scorecard`` never participates. ``reason`` is populated for every status except
    ``ISSUABLE`` and ``CLOSABLE``, which need no explanation.
    """
    response_present = root_cause_verdict != "EVIDENCE_NOT_SUPPLIED"
    other_evidence_invalid = "EVIDENCE_INVALID" in (ncr_verdict, cost_verdict)

    # Rule 0 — temporal contradiction. A response and/or a closure statement exists on a SCAR
    # that was never recorded as issued. Which of the two records is wrong is not guessed.
    if not issued and (response_present or voe is not None):
        return (
            "INDETERMINATE",
            "date_issued is absent, yet a supplier response and/or a "
            "verification-of-effectiveness statement is present; the SCAR timeline is "
            "contradictory and is reported as undecided rather than resolved by guessing.",
        )

    # Rule 1 — a rejected root cause is always the most specific finding, so it outranks an
    # also-invalid NCR or cost linkage rather than being masked by one.
    if root_cause_verdict == "EVIDENCE_INVALID":
        return (
            "RESPONSE_REJECTED",
            "quality_core.rca rejected the supplier-returned root cause; see "
            "linkage['supplier_root_cause'].findings for the validator's own findings.",
        )

    # Rule 2 — the only path to CLOSABLE.
    if root_cause_verdict == "EVIDENCE_VALID" and voe is not None and not other_evidence_invalid:
        return ("CLOSABLE", None)

    # Rule 3 — issued and still open. Deliberately overloaded: it also covers "root cause
    # accepted, closure not yet possible" (see ASSUMPTIONS_LOG.md, Process Design Decisions).
    if issued:
        if root_cause_verdict == "EVIDENCE_VALID":
            return (
                "AWAITING_SUPPLIER_RESPONSE",
                "the supplier root cause was accepted, but this SCAR is not closable: a "
                "verification-of-effectiveness statement is missing, or other linked evidence is "
                "currently invalid.",
            )
        return (
            "AWAITING_SUPPLIER_RESPONSE",
            "this SCAR has been issued and no supplier root-cause response has been received.",
        )

    # Rule 4 — not yet issued, and something already linked is already wrong.
    if other_evidence_invalid:
        return (
            "DRAFT",
            "this SCAR has not been issued and linked evidence already fails validation; see the "
            "EVIDENCE_INVALID entries in linkage.",
        )

    # Rule 5 — not issued, nothing invalid, no response applicable yet.
    return ("ISSUABLE", None)


# ===========================================================================
# Warnings and recommendations
# ===========================================================================


def _build_warnings(
    request: SCARRequest, linkage: dict[str, SCARLinkageResult]
) -> list[str]:
    """Build operator-facing warnings; every finding quoted here is a sub-engine's own text."""
    warnings: list[str] = []
    if request.due_date is None:
        warnings.append(
            "No due_date is recorded on this SCAR request; the supplier response due date is "
            "undecided and is not invented by this generator."
        )
    ncr_result = linkage["linked_ncr"]
    if request.linked_ncr_id is not None and ncr_result.verdict == "EVIDENCE_NOT_SUPPLIED":
        warnings.append(
            f"linked_ncr_id {request.linked_ncr_id!r} is referenced but no nonconformance "
            "evidence was supplied to validate against it."
        )
    for key in _VERDICT_AFFECTING_KEYS:
        result = linkage[key]
        if result.verdict == "EVIDENCE_INVALID":
            warnings.append(
                f"{key} evidence was rejected by {result.engine}: {'; '.join(result.findings)}"
            )
    return warnings


def _build_recommendations(linkage: dict[str, SCARLinkageResult], voe: str | None) -> list[str]:
    """Build operator-facing next steps, none of which ever proposes a root cause."""
    recommendations: list[str] = []
    root_cause_verdict = linkage["supplier_root_cause"].verdict
    if root_cause_verdict == "EVIDENCE_NOT_SUPPLIED":
        recommendations.append(
            "Request the supplier's 5-Why root-cause response. " + _ROOT_CAUSE_AUTHORITY
        )
    elif root_cause_verdict == "EVIDENCE_INVALID":
        recommendations.append(
            "Return the rejected response to the supplier with the quality_core.rca findings "
            "attached; do not close this SCAR by authoring a root cause internally."
        )
    if voe is None:
        recommendations.append(
            "Obtain a written verification-of-effectiveness statement from the supplier: no SCAR "
            "closes without one."
        )
    if linkage["cost_impact"].verdict == "EVIDENCE_NOT_SUPPLIED":
        recommendations.append(
            "Attach itemized cost-of-poor-quality evidence so the financial impact is quantified "
            "by quality_core.copq rather than estimated by hand."
        )
    return recommendations


# ===========================================================================
# Public entry point
# ===========================================================================


def generate_scar(
    request: SCARRequest,
    *,
    config: SCARConfig | None = None,
    linked_ncr_evidence: Any = None,
    supplier_root_cause_evidence: Any = None,
    cost_impact_evidence: Any = None,
    verification_of_effectiveness: str | None = None,
) -> SCARResult:
    """Generate a Supplier Corrective Action Request from a request record and linked evidence.

    Parameters
    ----------
    request : SCARRequest
        The SCAR request record (``quality_core.sqe.schema``), consumed as-is.
    config : SCARConfig, optional
        Engine configuration. ``None`` uses :class:`SCARConfig` defaults.
    linked_ncr_evidence : Any, optional
        Raw nonconformance evidence forwarded verbatim to ``quality_core.ncr.validate_ncr``
        (``NCRDataset``, ``DataFrame``, list of dicts/records, or dict). ``None`` resolves
        ``EVIDENCE_NOT_SUPPLIED`` regardless of ``request.linked_ncr_id``: an id with no evidence
        behind it is still nothing to check.
    supplier_root_cause_evidence : Any, optional
        The supplier's returned 5-Why chain, forwarded verbatim to
        ``quality_core.rca.validate_five_why_chain`` with ``request.issue_description`` as the
        problem statement. ``None`` resolves ``EVIDENCE_NOT_SUPPLIED`` — no response yet.
    cost_impact_evidence : Any, optional
        Itemized cost evidence forwarded verbatim to ``quality_core.copq.estimate_copq`` as
        ``items``. ``None`` resolves ``EVIDENCE_NOT_SUPPLIED``.
    verification_of_effectiveness : str, optional
        The caller's verification-of-effectiveness statement, stripped; a blank or
        whitespace-only value normalises to ``None``. Never authored or inferred here.

    Returns
    -------
    SCARResult
        The generated SCAR: cited sections, per-slot linkage results carrying each sub-engine's
        own findings, the status, and — only when the supplier supplied a parseable chain — that
        chain's own root cause, copied verbatim.
    """
    active_config = SCARConfig() if config is None else config
    voe = _normalise_optional_text(verification_of_effectiveness)

    linkage: dict[str, SCARLinkageResult] = {
        "linked_ncr": _evaluate_ncr_linkage(linked_ncr_evidence),
        "supplier_root_cause": _evaluate_root_cause_linkage(
            supplier_root_cause_evidence, request.issue_description
        ),
        "cost_impact": _evaluate_cost_impact_linkage(cost_impact_evidence),
    }
    if active_config.evaluate_vendor_scorecard_linkage:
        linkage["vendor_scorecard"] = _evaluate_vendor_scorecard_linkage()

    status, reason = _resolve_status(
        issued=request.date_issued is not None,
        ncr_verdict=linkage["linked_ncr"].verdict,
        root_cause_verdict=linkage["supplier_root_cause"].verdict,
        cost_verdict=linkage["cost_impact"].verdict,
        voe=voe,
    )

    return SCARResult(
        supplier_id=request.supplier_id,
        scar_id=request.scar_id,
        issue_description=request.issue_description,
        status=status,
        sections=_build_sections(request),
        linkage=linkage,
        root_cause=_root_cause_from_linkage(linkage["supplier_root_cause"]),
        verification_of_effectiveness=voe,
        due_date=_iso_or_none(request.due_date),
        date_issued=_iso_or_none(request.date_issued),
        reason=reason,
        warnings=_build_warnings(request, linkage),
        recommendations=_build_recommendations(linkage, voe),
    )

"""
auditor.py
Production Part Approval Process (PPAP) — 18-element completeness auditor core.

Performs a deterministic audit of a PPAP submission package against the 18 AIAG elements
(§2.2.1–§2.2.18) at a requested Submission Level (1–5) and Reason for Submission.

🔒 THE AUTHORITY INVARIANT:
Per Section 5 (Part Submission Status), the dispositions Approved, Interim Approval,
and Rejected are assigned exclusively by the customer's authorized representative.
This module evaluates and reports supplier-side submission readiness (SUBMISSION_READY,
NOT_READY, INDETERMINATE) and never emits, returns, or embeds customer approval verdicts.

COMPOSITION DISCIPLINE:
This module contains no standards data of its own. Requirement codes are looked up from
`quality_core.ppap.table_4_1.lookup_requirement`; applicability decisions are evaluated
via `quality_core.ppap.applicability.assess_applicability`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from quality_core.ppap.applicability import (
    ApplicabilityResult,
    ApplicabilityVerdict,
    assess_applicability,
)
from quality_core.ppap.schema import (
    PPAP_ELEMENT_ALIASES,
    PPAP_ELEMENT_IDS,
    PPAP_ELEMENT_NAMES,
    PPAP_ELEMENT_NUMBERS,
    REASON_FOR_SUBMISSION_ALIASES,
    REASON_FOR_SUBMISSION_VALUES,
    SUBMISSION_LEVEL_ALIASES,
    SUBMISSION_LEVELS,
    EvidenceItem,
    EvidenceStatus,
    PPAPElementId,
    PPAPPackage,
    ReasonForSubmission,
    SubmissionLevel,
)
from quality_core.ppap.table_4_1 import (
    RequirementCode,
    lookup_requirement,
)

__all__ = [
    "AUDIT_ELEMENT_VERDICTS",
    "AUDIT_PACKAGE_VERDICTS",
    "ElementAuditResult",
    "ElementAuditVerdict",
    "PPAPAuditResult",
    "PackageAuditVerdict",
    "audit_ppap_package",
]

ElementAuditVerdict = Literal[
    "SUBMITTED",
    "RETAINED_ON_FILE",
    "MISSING",
    "NOT_APPLICABLE",
    "INDETERMINATE",
    "EVIDENCE_INVALID",
]

AUDIT_ELEMENT_VERDICTS: tuple[ElementAuditVerdict, ...] = (
    "SUBMITTED",
    "RETAINED_ON_FILE",
    "MISSING",
    "NOT_APPLICABLE",
    "INDETERMINATE",
    "EVIDENCE_INVALID",
)

PackageAuditVerdict = Literal[
    "SUBMISSION_READY",
    "NOT_READY",
    "INDETERMINATE",
]

AUDIT_PACKAGE_VERDICTS: tuple[PackageAuditVerdict, ...] = (
    "SUBMISSION_READY",
    "NOT_READY",
    "INDETERMINATE",
)


@dataclass(frozen=True)
class ElementAuditResult:
    """Audit evaluation result for an individual PPAP element requirement."""

    element_id: PPAPElementId
    element_name: str
    verdict: ElementAuditVerdict
    requirement_code: RequirementCode
    applicability_verdict: ApplicabilityVerdict
    rationale: str
    is_blocking: bool
    evidence_status: EvidenceStatus | str | None = None
    evidence_present: bool | None = None
    artifact_ref: str | None = None
    document_reference: str | None = None
    evidence_valid: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard serializable dictionary."""
        return {
            "element_id": self.element_id,
            "element_name": self.element_name,
            "verdict": self.verdict,
            "requirement_code": self.requirement_code,
            "applicability_verdict": self.applicability_verdict,
            "rationale": self.rationale,
            "is_blocking": self.is_blocking,
            "evidence_status": self.evidence_status,
            "evidence_present": self.evidence_present,
            "artifact_ref": self.artifact_ref,
            "document_reference": self.document_reference,
            "evidence_valid": self.evidence_valid,
        }


@dataclass
class PPAPAuditResult:
    """Consolidated 18-element completeness audit result for a PPAP submission package."""

    package_verdict: PackageAuditVerdict
    submission_level: SubmissionLevel
    reason_for_submission: ReasonForSubmission
    elements: dict[PPAPElementId, ElementAuditResult]
    verdict_counts: dict[ElementAuditVerdict, int]
    blocking_elements: list[PPAPElementId]
    blocking_element_names: list[str]
    submitted_elements: list[PPAPElementId]
    retained_elements: list[PPAPElementId]
    missing_elements: list[PPAPElementId]
    not_applicable_elements: list[PPAPElementId]
    indeterminate_elements: list[PPAPElementId]
    invalid_elements: list[PPAPElementId]
    standards_basis: str = "AIAG PPAP 4th Edition (June 2006)"
    applicability_result: ApplicabilityResult | None = None

    def is_ready(self) -> bool:
        """Return True iff the entire PPAP package is SUBMISSION_READY."""
        return self.package_verdict == "SUBMISSION_READY"

    def get_element(self, element_id: str | int) -> ElementAuditResult | None:
        """Lookup an element audit result by canonical ID, number (1–18), or alias."""
        target_id: PPAPElementId | None = None
        if isinstance(element_id, int) and element_id in PPAP_ELEMENT_NUMBERS:
            target_id = PPAP_ELEMENT_NUMBERS[element_id]
        elif isinstance(element_id, str):
            clean = element_id.strip().lower()
            if clean in PPAP_ELEMENT_ALIASES:
                target_id = PPAP_ELEMENT_ALIASES[clean]
        if target_id is None:
            return None
        return self.elements.get(target_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard serializable dictionary."""
        return {
            "package_verdict": self.package_verdict,
            "submission_level": self.submission_level,
            "reason_for_submission": self.reason_for_submission,
            "elements": {k: v.to_dict() for k, v in self.elements.items()},
            "verdict_counts": dict(self.verdict_counts),
            "blocking_elements": list(self.blocking_elements),
            "blocking_element_names": list(self.blocking_element_names),
            "submitted_elements": list(self.submitted_elements),
            "retained_elements": list(self.retained_elements),
            "missing_elements": list(self.missing_elements),
            "not_applicable_elements": list(self.not_applicable_elements),
            "indeterminate_elements": list(self.indeterminate_elements),
            "invalid_elements": list(self.invalid_elements),
            "standards_basis": self.standards_basis,
            "applicability_result": (
                self.applicability_result.to_dict()
                if self.applicability_result is not None
                else None
            ),
        }


def _normalize_level(raw_level: Any) -> SubmissionLevel:
    if isinstance(raw_level, int) and not isinstance(raw_level, bool):
        if raw_level in SUBMISSION_LEVELS:
            return cast(SubmissionLevel, raw_level)
        raise ValueError(
            f"Invalid submission_level: {raw_level}. Must be an integer 1–5 or recognized alias."
        )
    if isinstance(raw_level, str):
        clean = raw_level.strip().lower()
        if clean in SUBMISSION_LEVEL_ALIASES:
            return SUBMISSION_LEVEL_ALIASES[clean]
        raise ValueError(
            f"Invalid submission_level: '{raw_level}'. Must be an integer 1–5 or recognized alias ('Level 1'–'Level 5')."
        )
    raise TypeError(
        f"submission_level must be an int (1–5) or str, got {type(raw_level).__name__}"
    )


def _normalize_reason(raw_reason: Any) -> ReasonForSubmission:
    if isinstance(raw_reason, str):
        clean = raw_reason.strip()
        if clean in REASON_FOR_SUBMISSION_VALUES:
            return cast(ReasonForSubmission, clean)
        clean_lower = clean.lower()
        if clean_lower in REASON_FOR_SUBMISSION_ALIASES:
            return REASON_FOR_SUBMISSION_ALIASES[clean_lower]
        raise ValueError(
            f"Invalid reason_for_submission: '{raw_reason}'. Must be one of {list(REASON_FOR_SUBMISSION_VALUES)} or recognized alias."
        )
    raise TypeError(
        f"reason_for_submission must be a str, got {type(raw_reason).__name__}"
    )


_ASSESS_APPLICABILITY_PARAMS: frozenset[str] = frozenset({
    "has_design_responsibility",
    "appearance_item",
    "has_checking_aid",
    "customer_engineering_approval_required",
    "master_sample_waived",
    "customer_level_4_requirements",
    "is_bulk_material",
    "is_tire",
    "is_truck_industry",
    "commodity_type",
})

_PPAP_PACKAGE_FIELDS: frozenset[str] = frozenset({
    "part_name",
    "part_number",
    "organization",
    "supplier_name",
    "supplier_code",
    "customer",
    "customer_name",
    "submission_level",
    "reason_for_submission",
    "application",
    "designated_appearance_item",
    "appearance_item",
    "bulk_material",
    "catalog_part",
    "black_box_part",
    "safety_critical",
    "has_checking_aid",
    "has_design_responsibility",
    "customer_requirement_set",
    "elements",
    "evidence",
})


def audit_ppap_package(
    package_or_data: PPAPPackage | dict[str, Any] | None = None,
    *,
    submission_level: SubmissionLevel | int | str | None = None,
    reason_for_submission: ReasonForSubmission | str | None = None,
    applicability: ApplicabilityResult | None = None,
    **kwargs: Any,
) -> PPAPAuditResult:
    """Audit a PPAP submission package for 18-element completeness and submission readiness.

    Joins package evidence against AIAG Table 4.1 requirement codes and applicability rules.

    Parameters:
        package_or_data: PPAPPackage instance, raw dictionary, or None.
        submission_level: Optional override for submission level (1–5).
        reason_for_submission: Optional override for reason for submission.
        applicability: Optional pre-computed ApplicabilityResult; if None, evaluated automatically.
        **kwargs: Additional parameters passed to assess_applicability.

    Returns:
        PPAPAuditResult with 18-element breakdown and package-level readiness verdict.
    """
    # 1. Resolve PPAPPackage instance
    package: PPAPPackage
    if isinstance(package_or_data, PPAPPackage):
        package = package_or_data
    elif isinstance(package_or_data, dict):
        pkg_kwargs = {k: v for k, v in package_or_data.items() if k in _PPAP_PACKAGE_FIELDS}
        package = PPAPPackage(**pkg_kwargs)
    elif package_or_data is None:
        pkg_kwargs = {k: v for k, v in kwargs.items() if k in _PPAP_PACKAGE_FIELDS}
        if submission_level is not None:
            pkg_kwargs["submission_level"] = submission_level
        if reason_for_submission is not None:
            pkg_kwargs["reason_for_submission"] = reason_for_submission
        package = PPAPPackage(**pkg_kwargs)
    else:
        raise TypeError(
            f"package_or_data must be a PPAPPackage, dict, or None, got {type(package_or_data).__name__}"
        )

    # 2. Determine effective submission level & reason
    eff_level: SubmissionLevel = (
        _normalize_level(submission_level)
        if submission_level is not None
        else package.submission_level
    )
    eff_reason: ReasonForSubmission = (
        _normalize_reason(reason_for_submission)
        if reason_for_submission is not None
        else package.reason_for_submission
    )

    # 3. Assess or inherit element applicability
    app_result: ApplicabilityResult
    if applicability is not None:
        app_result = applicability
    else:
        app_kwargs = {k: v for k, v in kwargs.items() if k in _ASSESS_APPLICABILITY_PARAMS}
        if isinstance(package_or_data, dict):
            for k in _ASSESS_APPLICABILITY_PARAMS:
                if k in package_or_data and k not in app_kwargs:
                    app_kwargs[k] = package_or_data[k]
        app_result = assess_applicability(
            package,
            submission_level=eff_level,
            reason_for_submission=eff_reason,
            **app_kwargs,
        )

    # 4. Map package evidence by canonical element ID
    evidence_map = package.element_map

    elements: dict[PPAPElementId, ElementAuditResult] = {}
    counts: dict[ElementAuditVerdict, int] = {
        "SUBMITTED": 0,
        "RETAINED_ON_FILE": 0,
        "MISSING": 0,
        "NOT_APPLICABLE": 0,
        "INDETERMINATE": 0,
        "EVIDENCE_INVALID": 0,
    }
    blocking_elements: list[PPAPElementId] = []
    blocking_element_names: list[str] = []
    submitted_elements: list[PPAPElementId] = []
    retained_elements: list[PPAPElementId] = []
    missing_elements: list[PPAPElementId] = []
    not_applicable_elements: list[PPAPElementId] = []
    indeterminate_elements: list[PPAPElementId] = []
    invalid_elements: list[PPAPElementId] = []

    # 5. Evaluate all 18 canonical elements (§2.2.1–§2.2.18)
    for elem_id in PPAP_ELEMENT_IDS:
        elem_name = PPAP_ELEMENT_NAMES[elem_id]
        req_code = lookup_requirement(elem_id, eff_level)
        elem_app = app_result.get_element(elem_id)
        app_verdict: ApplicabilityVerdict = (
            elem_app.verdict if elem_app is not None else "INDETERMINATE"
        )

        ev_item: EvidenceItem | None = evidence_map.get(elem_id)
        ev_status: EvidenceStatus | str | None = ev_item.status if ev_item else None
        ev_present: bool | None = ev_item.present if ev_item else None
        artifact_ref: str | None = ev_item.artifact_ref if ev_item else None
        doc_ref: str | None = ev_item.document_reference if ev_item else None
        ev_valid: bool | None = ev_item.evidence_valid if ev_item else None

        elem_verdict: ElementAuditVerdict
        rationale: str
        is_blocking: bool

        if app_verdict == "INDETERMINATE":
            elem_verdict = "INDETERMINATE"
            rationale = (
                f"Applicability is indeterminate: {elem_app.rationale}"
                if elem_app
                else "Un-surveyed: element applicability requirement is indeterminate."
            )
            is_blocking = True

        elif app_verdict == "NOT_APPLICABLE":
            elem_verdict = "NOT_APPLICABLE"
            rationale = (
                elem_app.rationale
                if elem_app
                else "Element is not applicable for this part and submission context."
            )
            is_blocking = False

        else:
            # Element is APPLICABLE
            # Check validation failure first
            if ev_valid is False:
                elem_verdict = "EVIDENCE_INVALID"
                rationale = (
                    f"Element is applicable and evidence is present, but failed validation: "
                    f"{ev_item.notes or 'Evidence does not meet acceptance criteria'}."
                    if ev_item
                    else "Element is applicable, but evidence failed validation."
                )
                is_blocking = True

            # Undecided sentinel: un-surveyed presence
            elif ev_item is None or (
                ev_present is None
                and ev_status == "undecided"
                and ev_item.retained_at_organization is None
                and ev_item.submitted_to_customer is None
            ):
                elem_verdict = "INDETERMINATE"
                rationale = (
                    "Un-surveyed: element evidence presence/status is undecided "
                    "(surveyed-unknown, not confirmed-absent)."
                )
                is_blocking = True

            # Confirmed absent evidence
            elif (
                ev_present is False
                or ev_status == "missing"
                or (
                    ev_item.submitted_to_customer is False
                    and ev_item.retained_at_organization is False
                )
            ):
                elem_verdict = "MISSING"
                is_blocking = True
                if req_code == "S":
                    rationale = (
                        "Element is applicable and required to be submitted to customer "
                        "(Table 4.1 coded 'S'), but evidence is missing."
                    )
                elif req_code == "R":
                    rationale = (
                        "Element is applicable and required to be retained at organization "
                        "and made available upon request (Table 4.1 coded 'R'), but evidence is missing."
                    )
                else:  # code '*' or CUSTOMER_DEFINED
                    rationale = (
                        "Element is applicable and required to be retained at organization "
                        "and submitted upon request (Table 4.1 coded '*'), but evidence is missing."
                    )

            # Present evidence
            else:
                if req_code == "S":
                    if (
                        (ev_item.submitted_to_customer is False or ev_item.status == "retained")
                        and not (ev_item.submitted_to_customer is True or ev_item.status == "submitted")
                    ):
                        elem_verdict = "MISSING"
                        rationale = (
                            "Element is applicable and required to be submitted to customer "
                            "(Table 4.1 coded 'S'), but evidence is only retained on file, not submitted."
                        )
                        is_blocking = True
                    else:
                        elem_verdict = "SUBMITTED"
                        rationale = (
                            "The organization shall submit to the customer and retain a copy of "
                            "records or documentation items at appropriate locations "
                            "(Table 4.1 coded 'S'); evidence present and submitted."
                        )
                        is_blocking = False

                elif req_code == "R":
                    elem_verdict = "RETAINED_ON_FILE"
                    rationale = (
                        "The organization shall retain at appropriate locations and make available "
                        "to the customer upon request (Table 4.1 coded 'R'); evidence present on file."
                    )
                    is_blocking = False

                else:  # code '*' or CUSTOMER_DEFINED
                    if (
                        ev_item.status == "submitted"
                        or ev_item.submitted_to_customer is True
                    ):
                        elem_verdict = "SUBMITTED"
                        rationale = (
                            "The organization shall retain at appropriate locations and submit "
                            "to the customer upon request (Table 4.1 coded '*'); evidence submitted to customer."
                        )
                    else:
                        elem_verdict = "RETAINED_ON_FILE"
                        rationale = (
                            "The organization shall retain at appropriate locations and submit "
                            "to the customer upon request (Table 4.1 coded '*'); evidence retained on file."
                        )
                    is_blocking = False

        counts[elem_verdict] += 1

        if is_blocking:
            blocking_elements.append(elem_id)
            blocking_element_names.append(elem_name)

        if elem_verdict == "SUBMITTED":
            submitted_elements.append(elem_id)
        elif elem_verdict == "RETAINED_ON_FILE":
            retained_elements.append(elem_id)
        elif elem_verdict == "MISSING":
            missing_elements.append(elem_id)
        elif elem_verdict == "NOT_APPLICABLE":
            not_applicable_elements.append(elem_id)
        elif elem_verdict == "INDETERMINATE":
            indeterminate_elements.append(elem_id)
        else:  # EVIDENCE_INVALID
            invalid_elements.append(elem_id)

        elements[elem_id] = ElementAuditResult(
            element_id=elem_id,
            element_name=elem_name,
            verdict=elem_verdict,
            requirement_code=req_code,
            applicability_verdict=app_verdict,
            rationale=rationale,
            is_blocking=is_blocking,
            evidence_status=ev_status,
            evidence_present=ev_present,
            artifact_ref=artifact_ref,
            document_reference=doc_ref,
            evidence_valid=ev_valid,
        )

    # 6. Resolve package-level readiness verdict
    package_verdict: PackageAuditVerdict
    if (
        app_result.package_verdict == "INDETERMINATE"
        or counts["INDETERMINATE"] > 0
    ):
        package_verdict = "INDETERMINATE"
    elif counts["MISSING"] > 0 or counts["EVIDENCE_INVALID"] > 0 or len(blocking_elements) > 0:
        package_verdict = "NOT_READY"
    else:
        package_verdict = "SUBMISSION_READY"

    return PPAPAuditResult(
        package_verdict=package_verdict,
        submission_level=eff_level,
        reason_for_submission=eff_reason,
        elements=elements,
        verdict_counts=counts,
        blocking_elements=blocking_elements,
        blocking_element_names=blocking_element_names,
        submitted_elements=submitted_elements,
        retained_elements=retained_elements,
        missing_elements=missing_elements,
        not_applicable_elements=not_applicable_elements,
        indeterminate_elements=indeterminate_elements,
        invalid_elements=invalid_elements,
        standards_basis="AIAG PPAP 4th Edition (June 2006)",
        applicability_result=app_result,
    )

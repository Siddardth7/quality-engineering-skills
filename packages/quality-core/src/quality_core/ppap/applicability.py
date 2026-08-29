"""
applicability.py
Production Part Approval Process (PPAP) — element applicability and submission-reason rules.

Evaluates applicability (APPLICABLE / NOT_APPLICABLE / INDETERMINATE) for all 18 AIAG PPAP
elements (§2.2.1–§2.2.18) based on part characteristics, design responsibility, customer
engineering approval requirements, appearance requirements, checking aids, master sample
waivers, Submission Level 4 customer-defined gates, and commodity scope boundaries
(Appendices F, G, H).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

from quality_core.ppap.schema import (
    PPAP_ELEMENT_ALIASES,
    PPAP_ELEMENT_IDS,
    PPAP_ELEMENT_NAMES,
    PPAP_ELEMENT_NUMBERS,
    REASON_FOR_SUBMISSION_ALIASES,
    REASON_FOR_SUBMISSION_VALUES,
    SUBMISSION_LEVEL_ALIASES,
    SUBMISSION_LEVELS,
    PPAPElementId,
    PPAPPackage,
    ReasonForSubmission,
    SubmissionLevel,
)

__all__ = [
    "APPLICABILITY_VERDICTS",
    "ApplicabilityResult",
    "ApplicabilityVerdict",
    "CONDITIONAL_ELEMENTS",
    "ElementApplicability",
    "assess_applicability",
]

# ---------------------------------------------------------------------------
# 1. Applicability Verdicts & Conditional Elements Taxonomy
# ---------------------------------------------------------------------------

ApplicabilityVerdict = Literal["APPLICABLE", "NOT_APPLICABLE", "INDETERMINATE"]

APPLICABILITY_VERDICTS: tuple[ApplicabilityVerdict, ...] = (
    "APPLICABLE",
    "NOT_APPLICABLE",
    "INDETERMINATE",
)

CONDITIONAL_ELEMENTS: tuple[PPAPElementId, ...] = (
    "2.2.3",   # Customer Engineering Approval
    "2.2.4",   # Design FMEA
    "2.2.13",  # Appearance Approval Report (AAR)
    "2.2.15",  # Master Sample
    "2.2.16",  # Checking Aids
)


# ---------------------------------------------------------------------------
# 2. Dataclasses: ElementApplicability & ApplicabilityResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ElementApplicability:
    """Applicability verdict and cited justification for a single PPAP element."""

    element_id: PPAPElementId
    element_name: str
    verdict: ApplicabilityVerdict
    rationale: str
    standard_reference: str
    is_conditional: bool
    condition_met: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize element applicability to a JSON-compatible dictionary."""
        return {
            "element_id": self.element_id,
            "element_name": self.element_name,
            "verdict": self.verdict,
            "rationale": self.rationale,
            "standard_reference": self.standard_reference,
            "is_conditional": self.is_conditional,
            "condition_met": self.condition_met,
        }


@dataclass
class ApplicabilityResult:
    """Complete 18-element applicability assessment for a PPAP submission package."""

    package_verdict: ApplicabilityVerdict
    submission_level: SubmissionLevel
    reason_for_submission: ReasonForSubmission
    elements: dict[PPAPElementId, ElementApplicability]
    applicable_elements: list[PPAPElementId]
    not_applicable_elements: list[PPAPElementId]
    indeterminate_elements: list[PPAPElementId]
    scope_boundary_notes: list[str] = field(default_factory=list)
    standards_basis: str = "AIAG PPAP 4th Edition (June 2006)"

    def get_element(self, element_id: str | int) -> ElementApplicability | None:
        """Lookup an element applicability by canonical element ID ('2.2.1'), number (1–18), or alias."""
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

    def is_applicable(self, element_id: str | int) -> bool:
        """Return True iff the specified element is APPLICABLE."""
        elem = self.get_element(element_id)
        return elem is not None and elem.verdict == "APPLICABLE"

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a JSON-compatible dictionary."""
        return {
            "package_verdict": self.package_verdict,
            "submission_level": self.submission_level,
            "reason_for_submission": self.reason_for_submission,
            "elements": {k: v.to_dict() for k, v in self.elements.items()},
            "applicable_elements": list(self.applicable_elements),
            "not_applicable_elements": list(self.not_applicable_elements),
            "indeterminate_elements": list(self.indeterminate_elements),
            "scope_boundary_notes": list(self.scope_boundary_notes),
            "standards_basis": self.standards_basis,
        }


# ---------------------------------------------------------------------------
# 3. Helper Functions & Engine Implementation
# ---------------------------------------------------------------------------

_BULK_COMMODITY_ALIASES: frozenset[str] = frozenset({
    "bulk",
    "bulk_material",
    "bulk material",
    "bulk materials",
    "chemicals",
    "chemical",
    "resin",
    "resins",
    "polymer",
    "polymers",
    "lubricant",
    "lubricants",
    "coating",
    "coatings",
    "paint",
    "fluid",
    "fluids",
})

_TIRE_COMMODITY_ALIASES: frozenset[str] = frozenset({
    "tire",
    "tires",
    "tyre",
    "tyres",
})

_TRUCK_COMMODITY_ALIASES: frozenset[str] = frozenset({
    "truck",
    "trucks",
    "heavy truck",
    "heavy trucks",
    "truck_industry",
    "truck industry",
    "commercial vehicle",
    "commercial vehicles",
})


def _to_element_id(v: Any) -> PPAPElementId | None:
    if isinstance(v, int) and v in PPAP_ELEMENT_NUMBERS:
        return PPAP_ELEMENT_NUMBERS[v]
    if isinstance(v, str):
        clean = v.strip().lower()
        if clean in PPAP_ELEMENT_ALIASES:
            return PPAP_ELEMENT_ALIASES[clean]
    return None


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


def _validate_bool_or_none(name: str, val: Any) -> bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    raise TypeError(f"{name} must be a bool or None, got {type(val).__name__}")


def assess_applicability(
    package_or_data: PPAPPackage | dict[str, Any] | None = None,
    *,
    submission_level: SubmissionLevel | int | str | None = None,
    reason_for_submission: ReasonForSubmission | str | None = None,
    has_design_responsibility: bool | None = None,
    appearance_item: bool | None = None,
    has_checking_aid: bool | None = None,
    customer_engineering_approval_required: bool | None = None,
    master_sample_waived: bool | None = None,
    customer_level_4_requirements: set[PPAPElementId] | list[str] | dict[str, Any] | None = None,
    is_bulk_material: bool = False,
    is_tire: bool = False,
    is_truck_industry: bool = False,
    commodity_type: str | None = None,
) -> ApplicabilityResult:
    """Assess element-by-element applicability under AIAG PPAP 4th Edition rules.

    Evaluates applicability for all 18 canonical elements (§2.2.1–§2.2.18) based on
    design responsibility, appearance requirements, checking aids, master sample waivers,
    customer engineering approvals, Submission Level 4 requirements, and commodity scope boundaries.

    Parameters:
        package_or_data: Optional PPAPPackage instance or raw dictionary of package attributes.
        submission_level: Submission Level 1–5 (defaults to package level or Level 3).
        reason_for_submission: PSW Field 18 Reason for Submission (defaults to "Initial Submission").
        has_design_responsibility: Whether organization is design-responsible (governs §2.2.4 DFMEA).
        appearance_item: Whether part has appearance requirements on design record (governs §2.2.13 AAR).
        has_checking_aid: Whether part-specific checking aid exists (governs §2.2.16 Checking Aids).
        customer_engineering_approval_required: Whether customer requires engineering approval (governs §2.2.3).
        master_sample_waived: Whether customer granted documented master sample waiver (governs §2.2.15).
        customer_level_4_requirements: Specific required elements under Submission Level 4.
        is_bulk_material: Out-of-scope flag for bulk materials per Appendix F.
        is_tire: Out-of-scope flag for tires per Appendix G.
        is_truck_industry: Out-of-scope flag for truck industry per Appendix H.
        commodity_type: Optional commodity string to detect scope boundaries.

    Returns:
        ApplicabilityResult with 18-element verdicts and package applicability verdict.
    """
    # 1. Extract base values from package_or_data if supplied
    p_level: Any = None
    p_reason: Any = None
    p_design_resp: Any = None
    p_appearance: Any = None
    p_checking_aid: Any = None
    p_eng_approval: Any = None
    p_master_waived: Any = None
    p_l4_reqs: Any = None
    p_bulk: bool = False
    p_tire: bool = False
    p_truck: bool = False
    p_commodity: str | None = None

    if package_or_data is not None:
        if isinstance(package_or_data, PPAPPackage):
            p_level = package_or_data.submission_level
            p_reason = package_or_data.reason_for_submission
            p_design_resp = package_or_data.has_design_responsibility
            p_appearance = package_or_data.appearance_item
            p_checking_aid = package_or_data.has_checking_aid
            p_l4_reqs = package_or_data.customer_requirement_set
            p_bulk = package_or_data.bulk_material
        elif isinstance(package_or_data, dict):
            p_level = package_or_data.get("submission_level")
            p_reason = package_or_data.get("reason_for_submission")
            p_design_resp = package_or_data.get("has_design_responsibility")
            p_appearance = package_or_data.get("appearance_item")
            p_checking_aid = package_or_data.get("has_checking_aid")
            p_eng_approval = package_or_data.get("customer_engineering_approval_required")
            p_master_waived = package_or_data.get("master_sample_waived")
            p_l4_reqs = package_or_data.get("customer_level_4_requirements") or package_or_data.get(
                "customer_requirement_set"
            )
            p_bulk = bool(package_or_data.get("is_bulk_material", False) or package_or_data.get("bulk_material", False))
            p_tire = bool(package_or_data.get("is_tire", False))
            p_truck = bool(package_or_data.get("is_truck_industry", False))
            p_commodity = package_or_data.get("commodity_type")
        else:
            raise TypeError(
                f"package_or_data must be a PPAPPackage, dict, or None, got {type(package_or_data).__name__}"
            )

    # 2. Resolve keyword parameter overrides and defaults
    raw_level = submission_level if submission_level is not None else (p_level if p_level is not None else 3)
    norm_level = _normalize_level(raw_level)

    raw_reason = (
        reason_for_submission
        if reason_for_submission is not None
        else (p_reason if p_reason is not None else "Initial Submission")
    )
    norm_reason = _normalize_reason(raw_reason)

    raw_design_resp = has_design_responsibility if has_design_responsibility is not None else p_design_resp
    val_design_resp = _validate_bool_or_none("has_design_responsibility", raw_design_resp)

    raw_appearance = appearance_item if appearance_item is not None else p_appearance
    val_appearance = _validate_bool_or_none("appearance_item", raw_appearance)

    raw_checking_aid = has_checking_aid if has_checking_aid is not None else p_checking_aid
    val_checking_aid = _validate_bool_or_none("has_checking_aid", raw_checking_aid)

    raw_eng_approval = (
        customer_engineering_approval_required
        if customer_engineering_approval_required is not None
        else p_eng_approval
    )
    val_eng_approval = _validate_bool_or_none(
        "customer_engineering_approval_required", raw_eng_approval
    )

    raw_master_waived = (
        master_sample_waived
        if master_sample_waived is not None
        else p_master_waived
    )
    val_master_waived = _validate_bool_or_none("master_sample_waived", raw_master_waived)

    eff_l4_reqs = (
        customer_level_4_requirements
        if customer_level_4_requirements is not None
        else p_l4_reqs
    )

    eff_bulk = is_bulk_material or p_bulk
    eff_tire = is_tire or p_tire
    eff_truck = is_truck_industry or p_truck
    eff_commodity = commodity_type if commodity_type is not None else p_commodity

    if eff_commodity is not None:
        if not isinstance(eff_commodity, str):
            raise TypeError(f"commodity_type must be a str, got {type(eff_commodity).__name__}")
        comm_clean = eff_commodity.strip().lower()
        if comm_clean in _BULK_COMMODITY_ALIASES:
            eff_bulk = True
        elif comm_clean in _TIRE_COMMODITY_ALIASES:
            eff_tire = True
        elif comm_clean in _TRUCK_COMMODITY_ALIASES:
            eff_truck = True

    # 3. Scope Boundaries Check (Appendices F, G, H)
    scope_notes: list[str] = []
    if eff_bulk:
        scope_notes.append(
            "Bulk materials per AIAG PPAP 4th Edition Appendix F are out of scope for standard discrete-part PPAP Core."
        )
    if eff_tire:
        scope_notes.append(
            "Tire industry submissions per AIAG PPAP 4th Edition Appendix G are out of scope for standard discrete-part PPAP Core."
        )
    if eff_truck:
        scope_notes.append(
            "Truck industry submissions per AIAG PPAP 4th Edition Appendix H are out of scope for standard discrete-part PPAP Core."
        )

    if scope_notes:
        out_of_scope_rationale = (
            f"Commodity/industry is out of scope for standard discrete-part PPAP Core ({'; '.join(scope_notes)})."
        )
        elements_map: dict[PPAPElementId, ElementApplicability] = {}
        for elem_id in PPAP_ELEMENT_IDS:
            elements_map[elem_id] = ElementApplicability(
                element_id=elem_id,
                element_name=PPAP_ELEMENT_NAMES[elem_id],
                verdict="INDETERMINATE",
                rationale=out_of_scope_rationale,
                standard_reference="AIAG PPAP 4th Edition Appendices F/G/H",
                is_conditional=elem_id in CONDITIONAL_ELEMENTS,
                condition_met=None,
            )
        return ApplicabilityResult(
            package_verdict="INDETERMINATE",
            submission_level=norm_level,
            reason_for_submission=norm_reason,
            elements=elements_map,
            applicable_elements=[],
            not_applicable_elements=[],
            indeterminate_elements=list(PPAP_ELEMENT_IDS),
            scope_boundary_notes=scope_notes,
            standards_basis="AIAG PPAP 4th Edition (June 2006)",
        )

    # 4. Submission Level 4 Evaluation Gate
    if norm_level == 4:
        if eff_l4_reqs is None:
            l4_indeterminate_map: dict[PPAPElementId, ElementApplicability] = {}
            for elem_id in PPAP_ELEMENT_IDS:
                l4_indeterminate_map[elem_id] = ElementApplicability(
                    element_id=elem_id,
                    element_name=PPAP_ELEMENT_NAMES[elem_id],
                    verdict="INDETERMINATE",
                    rationale=(
                        "Submission Level 4 requires customer-defined requirements "
                        "(AIAG PPAP 4th Edition Section 4 & Table 4.1). No customer requirements provided."
                    ),
                    standard_reference="AIAG PPAP 4th Edition Section 4 & Table 4.1",
                    is_conditional=elem_id in CONDITIONAL_ELEMENTS,
                    condition_met=None,
                )
            return ApplicabilityResult(
                package_verdict="INDETERMINATE",
                submission_level=norm_level,
                reason_for_submission=norm_reason,
                elements=l4_indeterminate_map,
                applicable_elements=[],
                not_applicable_elements=[],
                indeterminate_elements=list(PPAP_ELEMENT_IDS),
                scope_boundary_notes=scope_notes,
                standards_basis="AIAG PPAP 4th Edition (June 2006)",
            )

        # Level 4 with explicit customer requirements provided
        elements_map = {}
        applicable_list: list[PPAPElementId] = []
        not_applicable_list: list[PPAPElementId] = []
        indeterminate_list: list[PPAPElementId] = []

        if isinstance(eff_l4_reqs, dict):
            normalized_dict: dict[PPAPElementId, Any] = {}
            for k, v in eff_l4_reqs.items():
                norm_k = _to_element_id(k)
                if norm_k is not None:
                    normalized_dict[norm_k] = v

            for elem_id in PPAP_ELEMENT_IDS:
                is_cond = elem_id in CONDITIONAL_ELEMENTS
                if elem_id in normalized_dict:
                    val = normalized_dict[elem_id]
                    if val is True or (
                        isinstance(val, str)
                        and val.upper() in ("APPLICABLE", "S", "R", "*", "SUBMIT", "RETAIN", "TRUE", "Y", "YES")
                    ):
                        verdict: ApplicabilityVerdict = "APPLICABLE"
                        rationale = "Element required by customer under Submission Level 4 specification."
                        cond_met = True if is_cond else None
                        applicable_list.append(elem_id)
                    elif val is False or (
                        isinstance(val, str)
                        and val.upper() in ("NOT_APPLICABLE", "NA", "N/A", "WAIVED", "EXEMPT", "FALSE", "N", "NO")
                    ):
                        verdict = "NOT_APPLICABLE"
                        rationale = "Element not required by customer under Submission Level 4 specification."
                        cond_met = False if is_cond else None
                        not_applicable_list.append(elem_id)
                    elif val is None or (
                        isinstance(val, str)
                        and val.upper() in ("INDETERMINATE", "UNDECIDED", "?", "UNKNOWN")
                    ):
                        verdict = "INDETERMINATE"
                        rationale = "Customer requirement for this element is indeterminate."
                        cond_met = None
                        indeterminate_list.append(elem_id)
                    else:
                        verdict = "APPLICABLE"
                        rationale = "Element required by customer under Submission Level 4 specification."
                        cond_met = True if is_cond else None
                        applicable_list.append(elem_id)
                else:
                    verdict = "NOT_APPLICABLE"
                    rationale = "Element not specified in customer Level 4 requirements."
                    cond_met = False if is_cond else None
                    not_applicable_list.append(elem_id)

                elements_map[elem_id] = ElementApplicability(
                    element_id=elem_id,
                    element_name=PPAP_ELEMENT_NAMES[elem_id],
                    verdict=verdict,
                    rationale=rationale,
                    standard_reference="AIAG PPAP 4th Edition Section 4 & Table 4.1",
                    is_conditional=is_cond,
                    condition_met=cond_met,
                )
        elif isinstance(eff_l4_reqs, (set, list, tuple)):
            specified_ids: set[PPAPElementId] = set()
            for item in eff_l4_reqs:
                norm_item = _to_element_id(item)
                if norm_item is not None:
                    specified_ids.add(norm_item)

            for elem_id in PPAP_ELEMENT_IDS:
                is_cond = elem_id in CONDITIONAL_ELEMENTS
                if elem_id in specified_ids:
                    verdict = "APPLICABLE"
                    rationale = "Element required by customer under Submission Level 4 specification."
                    cond_met = True if is_cond else None
                    applicable_list.append(elem_id)
                else:
                    verdict = "NOT_APPLICABLE"
                    rationale = "Element not specified in customer Level 4 requirements."
                    cond_met = False if is_cond else None
                    not_applicable_list.append(elem_id)

                elements_map[elem_id] = ElementApplicability(
                    element_id=elem_id,
                    element_name=PPAP_ELEMENT_NAMES[elem_id],
                    verdict=verdict,
                    rationale=rationale,
                    standard_reference="AIAG PPAP 4th Edition Section 4 & Table 4.1",
                    is_conditional=is_cond,
                    condition_met=cond_met,
                )
        else:
            raise TypeError(
                f"customer_level_4_requirements must be a set, list, dict, or None, got {type(eff_l4_reqs).__name__}"
            )

        package_verdict: ApplicabilityVerdict = (
            "INDETERMINATE" if indeterminate_list else "APPLICABLE"
        )
        return ApplicabilityResult(
            package_verdict=package_verdict,
            submission_level=norm_level,
            reason_for_submission=norm_reason,
            elements=elements_map,
            applicable_elements=applicable_list,
            not_applicable_elements=not_applicable_list,
            indeterminate_elements=indeterminate_list,
            scope_boundary_notes=scope_notes,
            standards_basis="AIAG PPAP 4th Edition (June 2006)",
        )

    # 5. Standard Discrete-Part Applicability Evaluation (Levels 1, 2, 3, 5)
    elements_map = {}
    applicable_list = []
    not_applicable_list = []
    indeterminate_list = []

    for elem_id in PPAP_ELEMENT_IDS:
        name = PPAP_ELEMENT_NAMES[elem_id]

        if elem_id == "2.2.1":
            verdict = "APPLICABLE"
            rationale = "Design records are mandatory for all production parts (§2.2.1)."
            standard_ref = "AIAG PPAP 4th Edition §2.2.1"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.2":
            verdict = "APPLICABLE"
            rationale = (
                "Authorized engineering change documents for changes not yet recorded in design records (§2.2.2)."
            )
            standard_ref = "AIAG PPAP 4th Edition §2.2.2"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.3":
            is_cond = True
            standard_ref = "AIAG PPAP 4th Edition §2.2.3"
            if val_eng_approval is True:
                verdict = "APPLICABLE"
                rationale = "Customer engineering approval is required per customer specification/contract (§2.2.3)."
                cond_met = True
            elif val_eng_approval is False:
                verdict = "NOT_APPLICABLE"
                rationale = "Customer engineering approval is not required / specified by customer (§2.2.3)."
                cond_met = False
            else:
                verdict = "INDETERMINATE"
                rationale = "Un-surveyed: customer engineering approval requirement not specified (§2.2.3)."
                cond_met = None

        elif elem_id == "2.2.4":
            is_cond = True
            standard_ref = "AIAG PPAP 4th Edition §2.2.4"
            if val_design_resp is True:
                verdict = "APPLICABLE"
                rationale = "Organization is design-responsible; Design FMEA is required (§2.2.4)."
                cond_met = True
            elif val_design_resp is False:
                verdict = "NOT_APPLICABLE"
                rationale = (
                    "Organization is not design-responsible (customer is design-responsible); "
                    "Design FMEA is not applicable (§2.2.4)."
                )
                cond_met = False
            else:
                verdict = "INDETERMINATE"
                rationale = "Un-surveyed: design responsibility not specified (§2.2.4)."
                cond_met = None

        elif elem_id == "2.2.5":
            verdict = "APPLICABLE"
            rationale = "Process flow diagrams depicting manufacturing process steps are mandatory (§2.2.5)."
            standard_ref = "AIAG PPAP 4th Edition §2.2.5"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.6":
            verdict = "APPLICABLE"
            rationale = "Process FMEA is mandatory for all manufacturing processes (§2.2.6)."
            standard_ref = "AIAG PPAP 4th Edition §2.2.6"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.7":
            verdict = "APPLICABLE"
            rationale = "Control Plan defining process control methods is mandatory (§2.2.7)."
            standard_ref = "AIAG PPAP 4th Edition §2.2.7"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.8":
            verdict = "APPLICABLE"
            rationale = "Measurement System Analysis (MSA / Gage R&R) studies are mandatory (§2.2.8)."
            standard_ref = "AIAG PPAP 4th Edition §2.2.8"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.9":
            verdict = "APPLICABLE"
            rationale = (
                "Dimensional verification results showing conformance to design records are mandatory (§2.2.9)."
            )
            standard_ref = "AIAG PPAP 4th Edition §2.2.9"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.10":
            verdict = "APPLICABLE"
            rationale = (
                "Material and performance test results demonstrating conformance to specifications are mandatory (§2.2.10)."
            )
            standard_ref = "AIAG PPAP 4th Edition §2.2.10"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.11":
            verdict = "APPLICABLE"
            rationale = (
                "Initial process capability studies (Cpk / Ppk) are mandatory for special characteristics (§2.2.11)."
            )
            standard_ref = "AIAG PPAP 4th Edition §2.2.11"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.12":
            verdict = "APPLICABLE"
            rationale = "Qualified laboratory documentation and scope accreditation are mandatory (§2.2.12)."
            standard_ref = "AIAG PPAP 4th Edition §2.2.12"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.13":
            is_cond = True
            standard_ref = "AIAG PPAP 4th Edition §2.2.13"
            if val_appearance is True:
                verdict = "APPLICABLE"
                rationale = (
                    "Part has appearance requirements on the design record; "
                    "Appearance Approval Report (AAR) is required (§2.2.13)."
                )
                cond_met = True
            elif val_appearance is False:
                verdict = "NOT_APPLICABLE"
                rationale = (
                    "Part does not have appearance requirements on design record; "
                    "Appearance Approval Report (AAR) is not applicable (§2.2.13)."
                )
                cond_met = False
            else:
                verdict = "INDETERMINATE"
                rationale = "Un-surveyed: appearance requirement designation on design record not specified (§2.2.13)."
                cond_met = None

        elif elem_id == "2.2.14":
            verdict = "APPLICABLE"
            rationale = "Sample production parts from a significant production run are mandatory (§2.2.14)."
            standard_ref = "AIAG PPAP 4th Edition §2.2.14"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.15":
            is_cond = True
            standard_ref = "AIAG PPAP 4th Edition §2.2.15"
            if val_master_waived is True:
                verdict = "NOT_APPLICABLE"
                rationale = "Master sample is waived by documented customer agreement (§2.2.15)."
                cond_met = False
            elif val_master_waived is False:
                verdict = "APPLICABLE"
                rationale = "Master sample retention is required by default (§2.2.15); no customer waiver documented."
                cond_met = True
            else:
                verdict = "INDETERMINATE"
                rationale = "Un-surveyed: master sample customer waiver status not specified (§2.2.15)."
                cond_met = None

        elif elem_id == "2.2.16":
            is_cond = True
            standard_ref = "AIAG PPAP 4th Edition §2.2.16"
            if val_checking_aid is True:
                verdict = "APPLICABLE"
                rationale = (
                    "Part-specific assembly or component checking aid exists; "
                    "Checking Aids documentation is required (§2.2.16)."
                )
                cond_met = True
            elif val_checking_aid is False:
                verdict = "NOT_APPLICABLE"
                rationale = "No part-specific checking aid exists; Checking Aids element is not applicable (§2.2.16)."
                cond_met = False
            else:
                verdict = "INDETERMINATE"
                rationale = "Un-surveyed: checking aid existence not specified (§2.2.16)."
                cond_met = None

        elif elem_id == "2.2.17":
            verdict = "APPLICABLE"
            rationale = (
                "Records of compliance with applicable customer-specific requirements are mandatory (§2.2.17)."
            )
            standard_ref = "AIAG PPAP 4th Edition §2.2.17"
            is_cond = False
            cond_met = None

        elif elem_id == "2.2.18":
            verdict = "APPLICABLE"
            rationale = "Part Submission Warrant (PSW) is mandatory for all PPAP submissions (§2.2.18)."
            standard_ref = "AIAG PPAP 4th Edition §2.2.18"
            is_cond = False
            cond_met = None

        else:
            verdict = "INDETERMINATE"
            rationale = f"Unknown element: {elem_id}"
            standard_ref = "AIAG PPAP 4th Edition"
            is_cond = False
            cond_met = None

        if verdict == "APPLICABLE":
            applicable_list.append(elem_id)
        elif verdict == "NOT_APPLICABLE":
            not_applicable_list.append(elem_id)
        else:
            indeterminate_list.append(elem_id)

        elements_map[elem_id] = ElementApplicability(
            element_id=elem_id,
            element_name=name,
            verdict=verdict,
            rationale=rationale,
            standard_reference=standard_ref,
            is_conditional=is_cond,
            condition_met=cond_met,
        )

    package_verdict = "INDETERMINATE" if indeterminate_list else "APPLICABLE"

    return ApplicabilityResult(
        package_verdict=package_verdict,
        submission_level=norm_level,
        reason_for_submission=norm_reason,
        elements=elements_map,
        applicable_elements=applicable_list,
        not_applicable_elements=not_applicable_list,
        indeterminate_elements=indeterminate_list,
        scope_boundary_notes=scope_notes,
        standards_basis="AIAG PPAP 4th Edition (June 2006)",
    )

"""
psw.py
Production Part Approval Process (PPAP) — Part Submission Warrant (PSW) 27-field validator.

Validates Part Submission Warrant form fields against AIAG PPAP 4th Edition Appendix A
completion instructions, conditional field rules, prohibited blanket statements of conformance,
package/warrant cross-consistency checks, and the mandatory customer authority invariant.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, cast

import pydantic

from quality_core.ppap.schema import (
    REASON_FOR_SUBMISSION_ALIASES,
    REASON_FOR_SUBMISSION_VALUES,
    SUBMISSION_LEVEL_ALIASES,
    SUBMISSION_LEVELS,
    PPAPPackage,
    ReasonForSubmission,
    SubmissionLevel,
)

__all__ = [
    "BLANKET_STATEMENT_PATTERNS",
    "PSWFieldStatus",
    "PSWFieldVerdict",
    "PSWValidationResult",
    "PSWValidationVerdict",
    "PSW_FIELD_NAMES",
    "PartSubmissionWarrant",
    "find_blanket_statements",
    "validate_psw",
]

_STANDARDS_BASIS: str = (
    "AIAG Production Part Approval Process (PPAP) Reference Manual, 4th Edition "
    "(June 2006), Appendix A — Part Submission Warrant (PSW) Completion Instructions "
    "and Section 5 — Part Submission Status."
)

# ---------------------------------------------------------------------------
# 1. Verdict Literals and Constants
# ---------------------------------------------------------------------------

PSWValidationVerdict = Literal["COMPLETE", "INCOMPLETE", "INDETERMINATE"]

PSWFieldVerdict = Literal["VALID", "MISSING", "INVALID", "NOT_APPLICABLE", "INDETERMINATE"]

PSW_FIELD_NAMES: dict[int, str] = {
    1: "Part Name",
    2: "Customer Part Number",
    3: "Part Drawing Number / Org Part Number",
    4: "Engineering Change Level",
    5: "Engineering Change Date",
    6: "Additional Engineering Changes",
    7: "Purchase Order Number",
    8: "Part Weight (kg)",
    9: "Checking Aid Number",
    10: "Checking Aid Engineering Change Level & Date",
    11: "Organization Name & Code",
    12: "Organization Manufacturing Address",
    13: "Customer Name & Division",
    14: "Customer Contact / Buyer",
    15: "Application",
    16: "Materials Reporting (IMDS)",
    17: "Polymeric Parts Marking",
    18: "Reason for Submission",
    19: "Submission Level",
    20: "Submission Results",
    21: "Declaration of Conformance",
    22: "Customer Tool Tagging / Identification",
    23: "Production Rate (Pieces)",
    24: "Production Run Duration (Hours)",
    25: "Explanation / Comments",
    26: "Organization Authorized Signature",
    27: "Customer Disposition (FOR CUSTOMER USE ONLY)",
}

BLANKET_STATEMENT_PATTERNS: tuple[str, ...] = (
    "meets all specs",
    "meets all specifications",
    "all dimensions conform",
    "all dimensions conforming",
    "all specs met",
    "conforming to drawing",
    "all parts conforming",
    "100% conforming",
    "fully conforming",
    "all requirements met",
    "meets specifications",
    "conforming",
)


# ---------------------------------------------------------------------------
# 2. Blanket Statement Detection Helper
# ---------------------------------------------------------------------------

def find_blanket_statements(text: str | None) -> list[str]:
    """Detect prohibited blanket statements of conformance in text.

    Per AIAG PPAP 4th Edition Appendix A & §2.2.9/§2.2.10, actual test data is required;
    blanket statements of conformance are unacceptable.
    """
    if not text or not isinstance(text, str):
        return []
    clean = " ".join(text.strip().lower().split())
    found: list[str] = []
    for pattern in BLANKET_STATEMENT_PATTERNS:
        pattern_clean = " ".join(pattern.strip().lower().split())
        escaped = re.escape(pattern_clean)
        if re.search(rf"(?:^|\b){escaped}(?:\b|$)", clean, re.IGNORECASE):
            found.append(pattern)
    return found


# ---------------------------------------------------------------------------
# 3. Pydantic Domain Model: PartSubmissionWarrant
# ---------------------------------------------------------------------------

class PartSubmissionWarrant(pydantic.BaseModel):
    """Part Submission Warrant (PSW) 27-field form model per AIAG PPAP 4th Edition Appendix A.

    Captures all 27 numbered Appendix A fields with support for aliases, partial data entry,
    and flexible ingestion.
    """

    model_config = pydantic.ConfigDict(extra="allow")

    # Fields 1-10: Part Information
    part_name: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    customer_part_number: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    part_drawing_number: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    org_part_number: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    engineering_change_level: Annotated[str | None, pydantic.Field(default=None, max_length=100)] = None
    engineering_change_date: Annotated[str | datetime.date | None, pydantic.Field(default=None)] = None
    additional_engineering_changes: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    purchase_order_number: Annotated[str | None, pydantic.Field(default=None, max_length=100)] = None
    part_weight_kg: Annotated[float | int | None, pydantic.Field(default=None)] = None
    checking_aid_number: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None
    checking_aid_change_level_date: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None

    # Fields 11-12: Organization Information
    organization_name: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    organization_code: Annotated[str | None, pydantic.Field(default=None, max_length=100)] = None
    organization_address: Annotated[str | None, pydantic.Field(default=None, max_length=1000)] = None

    # Fields 13-15: Customer Information
    customer_name: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    customer_division: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    customer_contact: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    application: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None

    # Fields 16-17: Materials Reporting
    materials_reporting: Annotated[str | bool | None, pydantic.Field(default=None)] = None
    polymeric_parts_marking: Annotated[str | bool | None, pydantic.Field(default=None)] = None

    # Field 18: Reason for Submission
    reason_for_submission: Annotated[ReasonForSubmission | str | None, pydantic.Field(default=None)] = None

    # Field 19: Submission Level
    submission_level: Annotated[SubmissionLevel | int | str | None, pydantic.Field(default=None)] = None

    # Field 20: Submission Results
    submission_results: Annotated[str | dict[str, Any] | bool | None, pydantic.Field(default=None)] = None
    results_dimensional: bool | None = None
    results_material_functional: bool | None = None
    results_appearance: bool | None = None
    results_process_capability: bool | None = None

    # Field 21: Declaration of Conformance
    declaration_of_conformance: Annotated[bool | str | None, pydantic.Field(default=None)] = None

    # Field 22: Customer Tool Tagging / Identification
    customer_tool_tagging: Annotated[str | bool | None, pydantic.Field(default=None)] = None

    # Fields 23-24: Production Run Details
    production_rate: Annotated[float | int | None, pydantic.Field(default=None)] = None
    production_duration_hours: Annotated[float | int | None, pydantic.Field(default=None)] = None

    # Field 25: Explanation / Comments
    explanation_comments: Annotated[str | None, pydantic.Field(default=None, max_length=5000)] = None

    # Field 26: Authorized Organization Signature
    authorized_signature: Annotated[str | bool | None, pydantic.Field(default=None)] = None
    authorized_signature_name: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    authorized_signature_title: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    authorized_signature_date: Annotated[str | datetime.date | None, pydantic.Field(default=None)] = None
    authorized_signature_phone: Annotated[str | None, pydantic.Field(default=None, max_length=100)] = None
    authorized_signature_email: Annotated[str | None, pydantic.Field(default=None, max_length=200)] = None

    # Field 27: Customer Disposition (FOR CUSTOMER USE ONLY)
    customer_disposition: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def _sync_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            # Aliases for part information
            if "part_number" in d and d.get("customer_part_number") is None:
                d["customer_part_number"] = d["part_number"]
            if "drawing_number" in d and d.get("part_drawing_number") is None:
                d["part_drawing_number"] = d["drawing_number"]
            if "po_number" in d and d.get("purchase_order_number") is None:
                d["purchase_order_number"] = d["po_number"]
            if "weight" in d and d.get("part_weight_kg") is None:
                d["part_weight_kg"] = d["weight"]
            elif "weight_kg" in d and d.get("part_weight_kg") is None:
                d["part_weight_kg"] = d["weight_kg"]

            # Aliases for organization
            if "supplier_name" in d and d.get("organization_name") is None:
                d["organization_name"] = d["supplier_name"]
            elif "organization" in d and d.get("organization_name") is None:
                d["organization_name"] = d["organization"]
            if "supplier_code" in d and d.get("organization_code") is None:
                d["organization_code"] = d["supplier_code"]
            if "manufacturing_address" in d and d.get("organization_address") is None:
                d["organization_address"] = d["manufacturing_address"]

            # Aliases for customer
            if "customer" in d and d.get("customer_name") is None:
                d["customer_name"] = d["customer"]
            if "buyer" in d and d.get("customer_contact") is None:
                d["customer_contact"] = d["buyer"]

            # Aliases for materials/polymeric
            if "imds_reported" in d and d.get("materials_reporting") is None:
                d["materials_reporting"] = d["imds_reported"]
            elif "imds_id" in d and d.get("materials_reporting") is None:
                d["materials_reporting"] = d["imds_id"]
            if "polymeric_marked" in d and d.get("polymeric_parts_marking") is None:
                d["polymeric_parts_marking"] = d["polymeric_marked"]

            # Aliases for tooling / production
            if "tooling_tagged" in d and d.get("customer_tool_tagging") is None:
                d["customer_tool_tagging"] = d["tooling_tagged"]
            if "production_rate_pieces" in d and d.get("production_rate") is None:
                d["production_rate"] = d["production_rate_pieces"]
            if "run_duration_hours" in d and d.get("production_duration_hours") is None:
                d["production_duration_hours"] = d["run_duration_hours"]

            # Aliases for comments / explanation
            if "comments" in d and d.get("explanation_comments") is None:
                d["explanation_comments"] = d["comments"]
            elif "explanation" in d and d.get("explanation_comments") is None:
                d["explanation_comments"] = d["explanation"]

            # Aliases for signature
            if "signature" in d and d.get("authorized_signature") is None:
                d["authorized_signature"] = d["signature"]
            if "signee_name" in d and d.get("authorized_signature_name") is None:
                d["authorized_signature_name"] = d["signee_name"]

            return d
        return data

    @pydantic.field_validator("submission_level", mode="before")
    @classmethod
    def normalize_submission_level(cls, v: object) -> object:
        if isinstance(v, int) and v in SUBMISSION_LEVELS:
            return v
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in SUBMISSION_LEVEL_ALIASES:
                return SUBMISSION_LEVEL_ALIASES[clean]
        return v

    @pydantic.field_validator("reason_for_submission", mode="before")
    @classmethod
    def normalize_reason_for_submission(cls, v: object) -> object:
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in REASON_FOR_SUBMISSION_ALIASES:
                return REASON_FOR_SUBMISSION_ALIASES[clean]
        return v

    def to_dict(self) -> dict[str, Any]:
        """Serialize warrant model to a dictionary."""
        return self.model_dump()


# ---------------------------------------------------------------------------
# 4. Dataclasses: PSWFieldStatus & PSWValidationResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PSWFieldStatus:
    """Validation status for a single Part Submission Warrant field (1–27)."""

    field_number: int
    field_name: str
    verdict: PSWFieldVerdict
    value: Any = None
    details: str = ""
    is_required: bool = True
    standard_reference: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize field status to a JSON-compatible dictionary."""
        return {
            "field_number": self.field_number,
            "field_name": self.field_name,
            "verdict": self.verdict,
            "value": self.value,
            "details": self.details,
            "is_required": self.is_required,
            "standard_reference": self.standard_reference,
        }


@dataclass
class PSWValidationResult:
    """Complete validation result for a Part Submission Warrant (27 fields)."""

    verdict: PSWValidationVerdict
    fields: dict[int, PSWFieldStatus]
    missing_fields: list[int]
    invalid_fields: list[int]
    indeterminate_fields: list[int]
    blanket_statement_detected: bool = False
    blanket_statement_findings: list[str] = field(default_factory=list)
    cross_consistency_findings: list[str] = field(default_factory=list)
    customer_disposition_present: bool = False
    customer_disposition_warning: str | None = None
    warnings: list[str] = field(default_factory=list)
    standards_basis: str = _STANDARDS_BASIS

    def get_field(self, field_number: int) -> PSWFieldStatus | None:
        """Lookup a field status by its 1-indexed field number (1–27)."""
        return self.fields.get(field_number)

    def is_valid(self, field_number: int) -> bool:
        """Return True iff the specified field is VALID or NOT_APPLICABLE."""
        f = self.fields.get(field_number)
        return f is not None and f.verdict in ("VALID", "NOT_APPLICABLE")

    def to_dict(self) -> dict[str, Any]:
        """Serialize validation result to a JSON-compatible dictionary."""
        return {
            "verdict": self.verdict,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "missing_fields": list(self.missing_fields),
            "invalid_fields": list(self.invalid_fields),
            "indeterminate_fields": list(self.indeterminate_fields),
            "blanket_statement_detected": self.blanket_statement_detected,
            "blanket_statement_findings": list(self.blanket_statement_findings),
            "cross_consistency_findings": list(self.cross_consistency_findings),
            "customer_disposition_present": self.customer_disposition_present,
            "customer_disposition_warning": self.customer_disposition_warning,
            "warnings": list(self.warnings),
            "standards_basis": self.standards_basis,
        }


# ---------------------------------------------------------------------------
# 5. Core Engine: validate_psw
# ---------------------------------------------------------------------------

def validate_psw(
    psw: PartSubmissionWarrant | dict[str, Any],
    package: PPAPPackage | None = None,
    *,
    has_checking_aid: bool | None = None,
) -> PSWValidationResult:
    """Validate a Part Submission Warrant (PSW) across all 27 Appendix A fields.

    Parameters
    ----------
    psw : PartSubmissionWarrant | dict[str, Any]
        The Part Submission Warrant instance or raw dictionary payload to validate.
    package : PPAPPackage | None, optional
        PPAP package submission metadata for cross-consistency verification.
    has_checking_aid : bool | None, optional
        Whether a checking aid is applicable. If None, inferred from `package.has_checking_aid`
        or `psw.checking_aid_number`.

    Returns
    -------
    PSWValidationResult
        Complete validation result containing per-field verdicts, blanket statement findings,
        cross-consistency findings, and overall completeness verdict.
    """
    if isinstance(psw, dict):
        warrant = PartSubmissionWarrant(**psw)
    elif isinstance(psw, PartSubmissionWarrant):
        warrant = psw
    else:
        raise TypeError(f"psw must be PartSubmissionWarrant or dict, got {type(psw).__name__}")

    fields_dict: dict[int, PSWFieldStatus] = {}
    blanket_statement_findings: list[str] = []
    cross_consistency_findings: list[str] = []
    warnings: list[str] = []

    # Resolve checking aid requirement
    effective_has_checking_aid = has_checking_aid
    if effective_has_checking_aid is None and package is not None:
        effective_has_checking_aid = package.has_checking_aid

    # -----------------------------------------------------------------------
    # Field 1: Part Name
    # -----------------------------------------------------------------------
    p_name = warrant.part_name
    if p_name is not None and str(p_name).strip():
        fields_dict[1] = PSWFieldStatus(
            field_number=1,
            field_name=PSW_FIELD_NAMES[1],
            verdict="VALID",
            value=str(p_name).strip(),
            details="Part Name provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 1",
        )
    else:
        fields_dict[1] = PSWFieldStatus(
            field_number=1,
            field_name=PSW_FIELD_NAMES[1],
            verdict="MISSING",
            value=None,
            details="Part Name is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 1",
        )

    # -----------------------------------------------------------------------
    # Field 2: Customer Part Number
    # -----------------------------------------------------------------------
    cust_part_num = warrant.customer_part_number
    if cust_part_num is not None and str(cust_part_num).strip():
        fields_dict[2] = PSWFieldStatus(
            field_number=2,
            field_name=PSW_FIELD_NAMES[2],
            verdict="VALID",
            value=str(cust_part_num).strip(),
            details="Customer Part Number provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 2",
        )
    else:
        fields_dict[2] = PSWFieldStatus(
            field_number=2,
            field_name=PSW_FIELD_NAMES[2],
            verdict="MISSING",
            value=None,
            details="Customer Part Number is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 2",
        )

    # -----------------------------------------------------------------------
    # Field 3: Part Drawing Number / Org Part Number
    # -----------------------------------------------------------------------
    drawing_num = warrant.part_drawing_number or warrant.org_part_number
    if drawing_num is not None and str(drawing_num).strip():
        fields_dict[3] = PSWFieldStatus(
            field_number=3,
            field_name=PSW_FIELD_NAMES[3],
            verdict="VALID",
            value=str(drawing_num).strip(),
            details="Part Drawing Number / Organization Part Number provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 3",
        )
    else:
        fields_dict[3] = PSWFieldStatus(
            field_number=3,
            field_name=PSW_FIELD_NAMES[3],
            verdict="MISSING",
            value=None,
            details="Part Drawing Number / Organization Part Number is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 3",
        )

    # -----------------------------------------------------------------------
    # Field 4: Engineering Change Level
    # -----------------------------------------------------------------------
    ec_level = warrant.engineering_change_level
    if ec_level is not None and str(ec_level).strip():
        fields_dict[4] = PSWFieldStatus(
            field_number=4,
            field_name=PSW_FIELD_NAMES[4],
            verdict="VALID",
            value=str(ec_level).strip(),
            details="Engineering Change Level provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 4",
        )
    else:
        fields_dict[4] = PSWFieldStatus(
            field_number=4,
            field_name=PSW_FIELD_NAMES[4],
            verdict="MISSING",
            value=None,
            details="Engineering Change Level is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 4",
        )

    # -----------------------------------------------------------------------
    # Field 5: Engineering Change Date
    # -----------------------------------------------------------------------
    ec_date = warrant.engineering_change_date
    if ec_date is not None and str(ec_date).strip():
        fields_dict[5] = PSWFieldStatus(
            field_number=5,
            field_name=PSW_FIELD_NAMES[5],
            verdict="VALID",
            value=str(ec_date).strip(),
            details="Engineering Change Date provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 5",
        )
    else:
        fields_dict[5] = PSWFieldStatus(
            field_number=5,
            field_name=PSW_FIELD_NAMES[5],
            verdict="MISSING",
            value=None,
            details="Engineering Change Date is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 5",
        )

    # -----------------------------------------------------------------------
    # Field 6: Additional Engineering Changes
    # -----------------------------------------------------------------------
    add_ec = warrant.additional_engineering_changes
    fields_dict[6] = PSWFieldStatus(
        field_number=6,
        field_name=PSW_FIELD_NAMES[6],
        verdict="VALID",
        value=str(add_ec).strip() if add_ec is not None else None,
        details="Additional Engineering Changes documented." if add_ec else "No additional engineering changes recorded.",
        is_required=False,
        standard_reference="AIAG PPAP 4th Edition Appendix A Field 6",
    )

    # -----------------------------------------------------------------------
    # Field 7: Purchase Order Number
    # -----------------------------------------------------------------------
    po_num = warrant.purchase_order_number
    if po_num is not None and str(po_num).strip():
        fields_dict[7] = PSWFieldStatus(
            field_number=7,
            field_name=PSW_FIELD_NAMES[7],
            verdict="VALID",
            value=str(po_num).strip(),
            details="Purchase Order Number provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 7",
        )
    else:
        fields_dict[7] = PSWFieldStatus(
            field_number=7,
            field_name=PSW_FIELD_NAMES[7],
            verdict="MISSING",
            value=None,
            details="Purchase Order Number is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 7",
        )

    # -----------------------------------------------------------------------
    # Field 8: Part Weight (kg)
    # -----------------------------------------------------------------------
    p_weight = warrant.part_weight_kg
    if p_weight is not None:
        try:
            wt_float = float(p_weight)
            if wt_float > 0:
                fields_dict[8] = PSWFieldStatus(
                    field_number=8,
                    field_name=PSW_FIELD_NAMES[8],
                    verdict="VALID",
                    value=wt_float,
                    details=f"Part weight declared ({wt_float:.4f} kg).",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 8",
                )
            else:
                fields_dict[8] = PSWFieldStatus(
                    field_number=8,
                    field_name=PSW_FIELD_NAMES[8],
                    verdict="INVALID",
                    value=wt_float,
                    details="Part weight must be greater than 0 kg.",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 8",
                )
        except (ValueError, TypeError):
            fields_dict[8] = PSWFieldStatus(
                field_number=8,
                field_name=PSW_FIELD_NAMES[8],
                verdict="INVALID",
                value=p_weight,
                details="Part weight must be a valid positive number in kilograms.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 8",
            )
    else:
        fields_dict[8] = PSWFieldStatus(
            field_number=8,
            field_name=PSW_FIELD_NAMES[8],
            verdict="MISSING",
            value=None,
            details="Part Weight (kg) is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 8",
        )

    # -----------------------------------------------------------------------
    # Field 9: Checking Aid Number (Conditional)
    # -----------------------------------------------------------------------
    chk_aid = warrant.checking_aid_number
    chk_aid_clean = str(chk_aid).strip() if chk_aid is not None else None
    chk_aid_is_na = chk_aid_clean is not None and chk_aid_clean.lower() in ("n/a", "na", "none", "not applicable", "no")

    if effective_has_checking_aid is True:
        if chk_aid_clean and not chk_aid_is_na:
            fields_dict[9] = PSWFieldStatus(
                field_number=9,
                field_name=PSW_FIELD_NAMES[9],
                verdict="VALID",
                value=chk_aid_clean,
                details="Checking Aid Number provided.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 9 & §2.2.16",
            )
        else:
            fields_dict[9] = PSWFieldStatus(
                field_number=9,
                field_name=PSW_FIELD_NAMES[9],
                verdict="MISSING",
                value=chk_aid_clean,
                details="Checking Aid Number is required when checking aid is applicable.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 9 & §2.2.16",
            )
    elif effective_has_checking_aid is False:
        fields_dict[9] = PSWFieldStatus(
            field_number=9,
            field_name=PSW_FIELD_NAMES[9],
            verdict="NOT_APPLICABLE",
            value=chk_aid_clean,
            details="Checking aid not required / not applicable.",
            is_required=False,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 9 & §2.2.16",
        )
    else:
        # Un-surveyed checking aid status
        if chk_aid_clean and not chk_aid_is_na:
            fields_dict[9] = PSWFieldStatus(
                field_number=9,
                field_name=PSW_FIELD_NAMES[9],
                verdict="VALID",
                value=chk_aid_clean,
                details="Checking Aid Number provided.",
                is_required=False,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 9 & §2.2.16",
            )
        else:
            fields_dict[9] = PSWFieldStatus(
                field_number=9,
                field_name=PSW_FIELD_NAMES[9],
                verdict="NOT_APPLICABLE",
                value=chk_aid_clean,
                details="Checking aid not specified / not applicable.",
                is_required=False,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 9 & §2.2.16",
            )

    # -----------------------------------------------------------------------
    # Field 10: Checking Aid Change Level & Date (Conditional)
    # -----------------------------------------------------------------------
    chk_aid_date = warrant.checking_aid_change_level_date
    chk_aid_date_clean = str(chk_aid_date).strip() if chk_aid_date is not None else None
    chk_aid_date_is_na = chk_aid_date_clean is not None and chk_aid_date_clean.lower() in ("n/a", "na", "none", "not applicable")

    if fields_dict[9].verdict == "VALID":
        if chk_aid_date_clean and not chk_aid_date_is_na:
            fields_dict[10] = PSWFieldStatus(
                field_number=10,
                field_name=PSW_FIELD_NAMES[10],
                verdict="VALID",
                value=chk_aid_date_clean,
                details="Checking Aid Engineering Change Level & Date provided.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 10 & §2.2.16",
            )
        else:
            fields_dict[10] = PSWFieldStatus(
                field_number=10,
                field_name=PSW_FIELD_NAMES[10],
                verdict="MISSING",
                value=chk_aid_date_clean,
                details="Checking Aid Change Level & Date is required when checking aid is present.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 10 & §2.2.16",
            )
    else:
        fields_dict[10] = PSWFieldStatus(
            field_number=10,
            field_name=PSW_FIELD_NAMES[10],
            verdict="NOT_APPLICABLE",
            value=chk_aid_date_clean,
            details="Checking aid change level & date not applicable.",
            is_required=False,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 10 & §2.2.16",
        )

    # -----------------------------------------------------------------------
    # Field 11: Organization Name & Code
    # -----------------------------------------------------------------------
    org_name = warrant.organization_name
    org_code = warrant.organization_code
    if org_name is not None and str(org_name).strip():
        display_org = f"{str(org_name).strip()}" + (f" (Code: {str(org_code).strip()})" if org_code else "")
        fields_dict[11] = PSWFieldStatus(
            field_number=11,
            field_name=PSW_FIELD_NAMES[11],
            verdict="VALID",
            value=display_org,
            details="Organization Name & Code provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 11",
        )
    else:
        fields_dict[11] = PSWFieldStatus(
            field_number=11,
            field_name=PSW_FIELD_NAMES[11],
            verdict="MISSING",
            value=None,
            details="Organization Name & Code is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 11",
        )

    # -----------------------------------------------------------------------
    # Field 12: Organization Manufacturing Address
    # -----------------------------------------------------------------------
    org_addr = warrant.organization_address
    if org_addr is not None and str(org_addr).strip():
        fields_dict[12] = PSWFieldStatus(
            field_number=12,
            field_name=PSW_FIELD_NAMES[12],
            verdict="VALID",
            value=str(org_addr).strip(),
            details="Organization Manufacturing Address provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 12",
        )
    else:
        fields_dict[12] = PSWFieldStatus(
            field_number=12,
            field_name=PSW_FIELD_NAMES[12],
            verdict="MISSING",
            value=None,
            details="Organization Manufacturing Address is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 12",
        )

    # -----------------------------------------------------------------------
    # Field 13: Customer Name & Division
    # -----------------------------------------------------------------------
    cust_name = warrant.customer_name
    cust_div = warrant.customer_division
    if cust_name is not None and str(cust_name).strip():
        display_cust = f"{str(cust_name).strip()}" + (f" / {str(cust_div).strip()}" if cust_div else "")
        fields_dict[13] = PSWFieldStatus(
            field_number=13,
            field_name=PSW_FIELD_NAMES[13],
            verdict="VALID",
            value=display_cust,
            details="Customer Name & Division provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 13",
        )
    else:
        fields_dict[13] = PSWFieldStatus(
            field_number=13,
            field_name=PSW_FIELD_NAMES[13],
            verdict="MISSING",
            value=None,
            details="Customer Name & Division is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 13",
        )

    # -----------------------------------------------------------------------
    # Field 14: Customer Contact / Buyer
    # -----------------------------------------------------------------------
    cust_contact = warrant.customer_contact
    if cust_contact is not None and str(cust_contact).strip():
        fields_dict[14] = PSWFieldStatus(
            field_number=14,
            field_name=PSW_FIELD_NAMES[14],
            verdict="VALID",
            value=str(cust_contact).strip(),
            details="Customer Contact / Buyer provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 14",
        )
    else:
        fields_dict[14] = PSWFieldStatus(
            field_number=14,
            field_name=PSW_FIELD_NAMES[14],
            verdict="MISSING",
            value=None,
            details="Customer Contact / Buyer is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 14",
        )

    # -----------------------------------------------------------------------
    # Field 15: Application
    # -----------------------------------------------------------------------
    app = warrant.application
    if app is not None and str(app).strip():
        fields_dict[15] = PSWFieldStatus(
            field_number=15,
            field_name=PSW_FIELD_NAMES[15],
            verdict="VALID",
            value=str(app).strip(),
            details="Application (model year / vehicle program) provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 15",
        )
    else:
        fields_dict[15] = PSWFieldStatus(
            field_number=15,
            field_name=PSW_FIELD_NAMES[15],
            verdict="MISSING",
            value=None,
            details="Application is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 15",
        )

    # -----------------------------------------------------------------------
    # Field 16: Materials Reporting (IMDS)
    # -----------------------------------------------------------------------
    mat_rep = warrant.materials_reporting
    if mat_rep is not None:
        mat_str = str(mat_rep).strip()
        if mat_str.lower() in ("n/a", "na", "not applicable"):
            fields_dict[16] = PSWFieldStatus(
                field_number=16,
                field_name=PSW_FIELD_NAMES[16],
                verdict="NOT_APPLICABLE",
                value=mat_str,
                details="Materials reporting declared not applicable.",
                is_required=False,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 16",
            )
        elif mat_str:
            fields_dict[16] = PSWFieldStatus(
                field_number=16,
                field_name=PSW_FIELD_NAMES[16],
                verdict="VALID",
                value=mat_rep,
                details="Materials reporting (IMDS) declared.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 16",
            )
        else:
            fields_dict[16] = PSWFieldStatus(
                field_number=16,
                field_name=PSW_FIELD_NAMES[16],
                verdict="MISSING",
                value=None,
                details="Materials Reporting (IMDS) declaration is required.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 16",
            )
    else:
        fields_dict[16] = PSWFieldStatus(
            field_number=16,
            field_name=PSW_FIELD_NAMES[16],
            verdict="MISSING",
            value=None,
            details="Materials Reporting (IMDS) declaration is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 16",
        )

    # -----------------------------------------------------------------------
    # Field 17: Polymeric Parts Marking
    # -----------------------------------------------------------------------
    poly_mark = warrant.polymeric_parts_marking
    if poly_mark is not None:
        poly_str = str(poly_mark).strip()
        if poly_str.lower() in ("n/a", "na", "not applicable"):
            fields_dict[17] = PSWFieldStatus(
                field_number=17,
                field_name=PSW_FIELD_NAMES[17],
                verdict="NOT_APPLICABLE",
                value=poly_str,
                details="Polymeric parts marking declared not applicable.",
                is_required=False,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 17",
            )
        elif poly_str:
            fields_dict[17] = PSWFieldStatus(
                field_number=17,
                field_name=PSW_FIELD_NAMES[17],
                verdict="VALID",
                value=poly_mark,
                details="Polymeric parts marking declared.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 17",
            )
        else:
            fields_dict[17] = PSWFieldStatus(
                field_number=17,
                field_name=PSW_FIELD_NAMES[17],
                verdict="MISSING",
                value=None,
                details="Polymeric Parts Marking declaration is required.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 17",
            )
    else:
        fields_dict[17] = PSWFieldStatus(
            field_number=17,
            field_name=PSW_FIELD_NAMES[17],
            verdict="MISSING",
            value=None,
            details="Polymeric Parts Marking declaration is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 17",
        )

    # -----------------------------------------------------------------------
    # Field 18: Reason for Submission
    # -----------------------------------------------------------------------
    reason = warrant.reason_for_submission
    if reason is not None:
        clean_reason_str = str(reason).strip()
        canonical_reason: ReasonForSubmission | None = None
        if clean_reason_str in REASON_FOR_SUBMISSION_VALUES:
            canonical_reason = cast(ReasonForSubmission, clean_reason_str)
        elif clean_reason_str.lower() in REASON_FOR_SUBMISSION_ALIASES:
            canonical_reason = REASON_FOR_SUBMISSION_ALIASES[clean_reason_str.lower()]

        if canonical_reason is not None:
            if canonical_reason == "Other":
                # Explanation in Field 25 is required
                exp_text = warrant.explanation_comments
                if exp_text is not None and str(exp_text).strip():
                    fields_dict[18] = PSWFieldStatus(
                        field_number=18,
                        field_name=PSW_FIELD_NAMES[18],
                        verdict="VALID",
                        value=canonical_reason,
                        details="Reason for Submission is 'Other' with supporting explanation.",
                        is_required=True,
                        standard_reference="AIAG PPAP 4th Edition Appendix A Field 18",
                    )
                else:
                    fields_dict[18] = PSWFieldStatus(
                        field_number=18,
                        field_name=PSW_FIELD_NAMES[18],
                        verdict="INVALID",
                        value=canonical_reason,
                        details="Reason for Submission 'Other' requires explanation in Field 25.",
                        is_required=True,
                        standard_reference="AIAG PPAP 4th Edition Appendix A Field 18",
                    )
            else:
                fields_dict[18] = PSWFieldStatus(
                    field_number=18,
                    field_name=PSW_FIELD_NAMES[18],
                    verdict="VALID",
                    value=canonical_reason,
                    details=f"Valid Reason for Submission: '{canonical_reason}'.",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 18",
                )
        else:
            fields_dict[18] = PSWFieldStatus(
                field_number=18,
                field_name=PSW_FIELD_NAMES[18],
                verdict="INVALID",
                value=reason,
                details=f"Invalid Reason for Submission: '{reason}'. Must match one of {list(REASON_FOR_SUBMISSION_VALUES)}.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 18",
            )
    else:
        fields_dict[18] = PSWFieldStatus(
            field_number=18,
            field_name=PSW_FIELD_NAMES[18],
            verdict="MISSING",
            value=None,
            details="Reason for Submission is required (at least one trigger).",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 18",
        )

    # -----------------------------------------------------------------------
    # Field 19: Submission Level
    # -----------------------------------------------------------------------
    lvl = warrant.submission_level
    if lvl is not None:
        clean_lvl_str = str(lvl).strip().lower()
        canonical_lvl: SubmissionLevel | None = None
        if isinstance(lvl, int) and lvl in SUBMISSION_LEVELS:
            canonical_lvl = cast(SubmissionLevel, lvl)
        elif clean_lvl_str in SUBMISSION_LEVEL_ALIASES:
            canonical_lvl = SUBMISSION_LEVEL_ALIASES[clean_lvl_str]

        if canonical_lvl is not None:
            fields_dict[19] = PSWFieldStatus(
                field_number=19,
                field_name=PSW_FIELD_NAMES[19],
                verdict="VALID",
                value=canonical_lvl,
                details=f"Submission Level {canonical_lvl} specified.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 19 & Section 4",
            )
        else:
            fields_dict[19] = PSWFieldStatus(
                field_number=19,
                field_name=PSW_FIELD_NAMES[19],
                verdict="INVALID",
                value=lvl,
                details=f"Invalid Submission Level: '{lvl}'. Must be 1, 2, 3, 4, or 5.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 19 & Section 4",
            )
    else:
        fields_dict[19] = PSWFieldStatus(
            field_number=19,
            field_name=PSW_FIELD_NAMES[19],
            verdict="MISSING",
            value=None,
            details="Submission Level is required (exactly one level 1–5).",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 19 & Section 4",
        )

    # -----------------------------------------------------------------------
    # Field 20: Submission Results
    # -----------------------------------------------------------------------
    results = warrant.submission_results
    has_explicit_results_flags = any(
        x is not None
        for x in (
            warrant.results_dimensional,
            warrant.results_material_functional,
            warrant.results_appearance,
            warrant.results_process_capability,
        )
    )

    if results is not None or has_explicit_results_flags:
        # Check for blanket statement
        bs_found = find_blanket_statements(str(results)) if isinstance(results, str) else []
        if bs_found:
            for b in bs_found:
                finding = f"Blanket statement of conformance detected in Field 20 (Submission Results): '{b}'."
                blanket_statement_findings.append(finding)
            fields_dict[20] = PSWFieldStatus(
                field_number=20,
                field_name=PSW_FIELD_NAMES[20],
                verdict="INVALID",
                value=results,
                details="Prohibited blanket statement of conformance detected in Submission Results. Actual test data is required.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 20 & §2.2.9/§2.2.10",
            )
        else:
            fields_dict[20] = PSWFieldStatus(
                field_number=20,
                field_name=PSW_FIELD_NAMES[20],
                verdict="VALID",
                value=results if results is not None else {
                    "dimensional": warrant.results_dimensional,
                    "material_functional": warrant.results_material_functional,
                    "appearance": warrant.results_appearance,
                    "process_capability": warrant.results_process_capability,
                },
                details="Submission Results declared.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 20",
            )
    else:
        fields_dict[20] = PSWFieldStatus(
            field_number=20,
            field_name=PSW_FIELD_NAMES[20],
            verdict="MISSING",
            value=None,
            details="Submission Results declaration is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 20",
        )

    # -----------------------------------------------------------------------
    # Field 21: Declaration of Conformance
    # -----------------------------------------------------------------------
    decl = warrant.declaration_of_conformance
    if decl is not None:
        decl_clean = str(decl).strip().lower()
        if decl is True or decl_clean in ("true", "yes", "y", "conforming", "conforms"):
            fields_dict[21] = PSWFieldStatus(
                field_number=21,
                field_name=PSW_FIELD_NAMES[21],
                verdict="VALID",
                value=True,
                details="Declaration of Conformance is Yes (conforming).",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 21",
            )
        elif decl is False or decl_clean in ("false", "no", "n", "nonconforming"):
            # Requires explanation in Field 25
            exp_text = warrant.explanation_comments
            if exp_text is not None and str(exp_text).strip():
                fields_dict[21] = PSWFieldStatus(
                    field_number=21,
                    field_name=PSW_FIELD_NAMES[21],
                    verdict="VALID",
                    value=False,
                    details="Declaration of Conformance is No (non-conforming) with explanation provided in Field 25.",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 21",
                )
            else:
                fields_dict[21] = PSWFieldStatus(
                    field_number=21,
                    field_name=PSW_FIELD_NAMES[21],
                    verdict="INVALID",
                    value=False,
                    details="Declaration of Conformance is No, which requires an explanation in Field 25 (Explanation/Comments).",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 21",
                )
        else:
            fields_dict[21] = PSWFieldStatus(
                field_number=21,
                field_name=PSW_FIELD_NAMES[21],
                verdict="INVALID",
                value=decl,
                details=f"Invalid Declaration of Conformance value: '{decl}'. Must be boolean or Yes/No.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 21",
            )
    else:
        fields_dict[21] = PSWFieldStatus(
            field_number=21,
            field_name=PSW_FIELD_NAMES[21],
            verdict="MISSING",
            value=None,
            details="Declaration of Conformance is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 21",
        )

    # -----------------------------------------------------------------------
    # Field 22: Customer Tool Tagging / Identification
    # -----------------------------------------------------------------------
    tool_tag = warrant.customer_tool_tagging
    if tool_tag is not None:
        tt_clean = str(tool_tag).strip().lower()
        if tt_clean in ("n/a", "na", "not applicable"):
            fields_dict[22] = PSWFieldStatus(
                field_number=22,
                field_name=PSW_FIELD_NAMES[22],
                verdict="NOT_APPLICABLE",
                value=str(tool_tag).strip(),
                details="Customer Tool Tagging declared not applicable.",
                is_required=False,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 22",
            )
        elif tt_clean:
            fields_dict[22] = PSWFieldStatus(
                field_number=22,
                field_name=PSW_FIELD_NAMES[22],
                verdict="VALID",
                value=tool_tag,
                details="Customer Tool Tagging declaration provided.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 22",
            )
        else:
            fields_dict[22] = PSWFieldStatus(
                field_number=22,
                field_name=PSW_FIELD_NAMES[22],
                verdict="MISSING",
                value=None,
                details="Customer Tool Tagging declaration is required.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 22",
            )
    else:
        fields_dict[22] = PSWFieldStatus(
            field_number=22,
            field_name=PSW_FIELD_NAMES[22],
            verdict="MISSING",
            value=None,
            details="Customer Tool Tagging declaration is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 22",
        )

    # -----------------------------------------------------------------------
    # Field 23: Production Rate (Pieces)
    # -----------------------------------------------------------------------
    prod_rate = warrant.production_rate
    if prod_rate is not None:
        try:
            rate_val = float(prod_rate)
            if rate_val > 0:
                fields_dict[23] = PSWFieldStatus(
                    field_number=23,
                    field_name=PSW_FIELD_NAMES[23],
                    verdict="VALID",
                    value=rate_val,
                    details=f"Production Rate declared ({rate_val} pieces).",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 23",
                )
            else:
                fields_dict[23] = PSWFieldStatus(
                    field_number=23,
                    field_name=PSW_FIELD_NAMES[23],
                    verdict="INVALID",
                    value=rate_val,
                    details="Production Rate (Pieces) must be greater than 0.",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 23",
                )
        except (ValueError, TypeError):
            fields_dict[23] = PSWFieldStatus(
                field_number=23,
                field_name=PSW_FIELD_NAMES[23],
                verdict="INVALID",
                value=prod_rate,
                details="Production Rate must be a valid positive number.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 23",
            )
    else:
        fields_dict[23] = PSWFieldStatus(
            field_number=23,
            field_name=PSW_FIELD_NAMES[23],
            verdict="MISSING",
            value=None,
            details="Production Rate (Pieces) is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 23",
        )

    # -----------------------------------------------------------------------
    # Field 24: Production Run Duration (Hours)
    # -----------------------------------------------------------------------
    prod_dur = warrant.production_duration_hours
    if prod_dur is not None:
        try:
            dur_val = float(prod_dur)
            if dur_val > 0:
                fields_dict[24] = PSWFieldStatus(
                    field_number=24,
                    field_name=PSW_FIELD_NAMES[24],
                    verdict="VALID",
                    value=dur_val,
                    details=f"Production Run Duration declared ({dur_val} hours).",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 24",
                )
            else:
                fields_dict[24] = PSWFieldStatus(
                    field_number=24,
                    field_name=PSW_FIELD_NAMES[24],
                    verdict="INVALID",
                    value=dur_val,
                    details="Production Run Duration (Hours) must be greater than 0.",
                    is_required=True,
                    standard_reference="AIAG PPAP 4th Edition Appendix A Field 24",
                )
        except (ValueError, TypeError):
            fields_dict[24] = PSWFieldStatus(
                field_number=24,
                field_name=PSW_FIELD_NAMES[24],
                verdict="INVALID",
                value=prod_dur,
                details="Production Run Duration must be a valid positive number.",
                is_required=True,
                standard_reference="AIAG PPAP 4th Edition Appendix A Field 24",
            )
    else:
        fields_dict[24] = PSWFieldStatus(
            field_number=24,
            field_name=PSW_FIELD_NAMES[24],
            verdict="MISSING",
            value=None,
            details="Production Run Duration (Hours) is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 24",
        )

    # -----------------------------------------------------------------------
    # Field 25: Explanation / Comments
    # -----------------------------------------------------------------------
    exp_comments = warrant.explanation_comments
    exp_bs_found = find_blanket_statements(exp_comments)
    if exp_bs_found:
        for b in exp_bs_found:
            finding = f"Blanket statement of conformance detected in Field 25 (Explanation/Comments): '{b}'."
            blanket_statement_findings.append(finding)
        fields_dict[25] = PSWFieldStatus(
            field_number=25,
            field_name=PSW_FIELD_NAMES[25],
            verdict="INVALID",
            value=exp_comments,
            details="Prohibited blanket statement of conformance detected in Explanation/Comments.",
            is_required=False,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 25 & §2.2.9/§2.2.10",
        )
    elif exp_comments is not None and str(exp_comments).strip():
        fields_dict[25] = PSWFieldStatus(
            field_number=25,
            field_name=PSW_FIELD_NAMES[25],
            verdict="VALID",
            value=str(exp_comments).strip(),
            details="Explanation / Comments provided.",
            is_required=False,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 25",
        )
    else:
        fields_dict[25] = PSWFieldStatus(
            field_number=25,
            field_name=PSW_FIELD_NAMES[25],
            verdict="VALID",
            value=None,
            details="No explanation/comments recorded.",
            is_required=False,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 25",
        )

    # -----------------------------------------------------------------------
    # Field 26: Organization Authorized Signature
    # -----------------------------------------------------------------------
    sig = warrant.authorized_signature
    sig_name = warrant.authorized_signature_name
    sig_provided = (
        (isinstance(sig, bool) and sig is True)
        or (isinstance(sig, str) and bool(sig.strip()))
        or (isinstance(sig_name, str) and bool(sig_name.strip()))
    )

    if sig_provided:
        sig_display = sig_name or (str(sig) if isinstance(sig, str) else "Authorized Signature on file")
        fields_dict[26] = PSWFieldStatus(
            field_number=26,
            field_name=PSW_FIELD_NAMES[26],
            verdict="VALID",
            value=sig_display,
            details="Organization Authorized Signature provided.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 26",
        )
    else:
        fields_dict[26] = PSWFieldStatus(
            field_number=26,
            field_name=PSW_FIELD_NAMES[26],
            verdict="MISSING",
            value=None,
            details="Organization Authorized Signature is required.",
            is_required=True,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 26",
        )

    # -----------------------------------------------------------------------
    # Field 27: Customer Disposition (FOR CUSTOMER USE ONLY - Invariant)
    # -----------------------------------------------------------------------
    cust_disp = warrant.customer_disposition
    cust_disp_present = cust_disp is not None and bool(str(cust_disp).strip())
    cust_disp_warning: str | None = None

    if cust_disp_present:
        cust_disp_warning = (
            "Field 27 (Customer Disposition) is populated but is FOR CUSTOMER USE ONLY per AIAG PPAP "
            "4th Edition Section 5 & Appendix A. The validation engine evaluates supplier submission "
            "completeness only and never emits or approves customer dispositions."
        )
        warnings.append(cust_disp_warning)
        fields_dict[27] = PSWFieldStatus(
            field_number=27,
            field_name=PSW_FIELD_NAMES[27],
            verdict="NOT_APPLICABLE",
            value=str(cust_disp).strip(),
            details="Field 27 is FOR CUSTOMER USE ONLY; excluded from supplier completeness evaluation.",
            is_required=False,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 27 & Section 5",
        )
    else:
        fields_dict[27] = PSWFieldStatus(
            field_number=27,
            field_name=PSW_FIELD_NAMES[27],
            verdict="NOT_APPLICABLE",
            value=None,
            details="FOR CUSTOMER USE ONLY (reserved for customer authorized representative).",
            is_required=False,
            standard_reference="AIAG PPAP 4th Edition Appendix A Field 27 & Section 5",
        )

    # -----------------------------------------------------------------------
    # Cross-Consistency Checks with PPAPPackage (if supplied)
    # -----------------------------------------------------------------------
    if package is not None:
        # 1. Part Number Check
        if warrant.customer_part_number and package.part_number:
            if warrant.customer_part_number.strip().lower() != package.part_number.strip().lower():
                finding = (
                    f"Cross-consistency mismatch on Part Number: PSW '{warrant.customer_part_number}' "
                    f"!= Package '{package.part_number}'."
                )
                cross_consistency_findings.append(finding)

        # 2. Part Name Check
        if warrant.part_name and package.part_name:
            if warrant.part_name.strip().lower() != package.part_name.strip().lower():
                finding = (
                    f"Cross-consistency mismatch on Part Name: PSW '{warrant.part_name}' "
                    f"!= Package '{package.part_name}'."
                )
                cross_consistency_findings.append(finding)

        # 3. Submission Level Check
        if fields_dict[19].verdict == "VALID" and fields_dict[19].value is not None:
            if fields_dict[19].value != package.submission_level:
                finding = (
                    f"Cross-consistency mismatch on Submission Level: PSW Level {fields_dict[19].value} "
                    f"!= Package Level {package.submission_level}."
                )
                cross_consistency_findings.append(finding)

        # 4. Reason for Submission Check
        if fields_dict[18].verdict == "VALID" and fields_dict[18].value is not None:
            psw_reason = str(fields_dict[18].value).strip().lower()
            pkg_reason = str(package.reason_for_submission).strip().lower()
            if psw_reason != pkg_reason:
                finding = (
                    f"Cross-consistency mismatch on Reason for Submission: PSW '{fields_dict[18].value}' "
                    f"!= Package '{package.reason_for_submission}'."
                )
                cross_consistency_findings.append(finding)

        # 5. Supplier / Organization Name Check
        pkg_org = package.supplier_name or package.organization
        if warrant.organization_name and pkg_org:
            if warrant.organization_name.strip().lower() != pkg_org.strip().lower():
                finding = (
                    f"Cross-consistency mismatch on Organization/Supplier Name: PSW '{warrant.organization_name}' "
                    f"!= Package '{pkg_org}'."
                )
                cross_consistency_findings.append(finding)

        # 6. Customer Name Check
        pkg_cust = package.customer_name or package.customer
        if warrant.customer_name and pkg_cust:
            if warrant.customer_name.strip().lower() != pkg_cust.strip().lower():
                finding = (
                    f"Cross-consistency mismatch on Customer Name: PSW '{warrant.customer_name}' "
                    f"!= Package '{pkg_cust}'."
                )
                cross_consistency_findings.append(finding)

        # 7. Checking Aid Check
        if package.has_checking_aid is True and fields_dict[9].verdict in ("MISSING", "NOT_APPLICABLE"):
            finding = "Cross-consistency mismatch: Package has_checking_aid=True but PSW Checking Aid Number is missing."
            cross_consistency_findings.append(finding)

    # -----------------------------------------------------------------------
    # Aggregate Verdict Calculation
    # -----------------------------------------------------------------------
    missing_fields: list[int] = []
    invalid_fields: list[int] = []
    indeterminate_fields: list[int] = []

    for num in range(1, 28):
        status = fields_dict[num]
        if status.verdict == "MISSING":
            missing_fields.append(num)
        elif status.verdict == "INVALID":
            invalid_fields.append(num)
        elif status.verdict == "INDETERMINATE":
            indeterminate_fields.append(num)

    blanket_detected = len(blanket_statement_findings) > 0

    if indeterminate_fields:
        overall_verdict: PSWValidationVerdict = "INDETERMINATE"
    elif missing_fields or invalid_fields or blanket_detected or cross_consistency_findings:
        overall_verdict = "INCOMPLETE"
    else:
        overall_verdict = "COMPLETE"

    return PSWValidationResult(
        verdict=overall_verdict,
        fields=fields_dict,
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
        indeterminate_fields=indeterminate_fields,
        blanket_statement_detected=blanket_detected,
        blanket_statement_findings=blanket_statement_findings,
        cross_consistency_findings=cross_consistency_findings,
        customer_disposition_present=cust_disp_present,
        customer_disposition_warning=cust_disp_warning,
        warnings=warnings,
        standards_basis=_STANDARDS_BASIS,
    )

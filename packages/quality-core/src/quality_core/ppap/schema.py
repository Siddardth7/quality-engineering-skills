"""
schema.py
Production Part Approval Process (PPAP) — shared domain models, schemas, and ingest validators.

Defines Pydantic models, enums/literals, and TableSchema descriptors for:
- The 18 canonical AIAG PPAP 4th Edition element requirements (§2.2.1–§2.2.18)
- Submission Levels 1–5 with verbatim definitions (Section 4)
- Part Submission Warrant (PSW) Field 18 Reason for Submission vocabulary (Appendix A)
- Element evidence items and PPAP submission packages (EvidenceItem, PPAPPackage)
- Undecided sentinel (present=None / status="undecided") preventing un-surveyed elements from being coerced to absent
- TableSchema descriptor for CSV ingestion and trust-boundary validation helpers
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Annotated, Any, BinaryIO, Literal, cast

import pandas as pd
import pydantic

from quality_core.io import (
    IngestError,
    TableSchema,
    read_table,
    read_table_from_path,
    validate_table,
)
from quality_core.schema._base import find_duplicates

__all__ = [
    "EVIDENCE_STATUS_ALIASES",
    "EVIDENCE_STATUS_VALUES",
    "EvidenceItem",
    "EvidenceStatus",
    "IngestError",
    "PPAPElementId",
    "PPAPPackage",
    "PPAP_ELEMENT_ALIASES",
    "PPAP_ELEMENT_IDS",
    "PPAP_ELEMENT_NAMES",
    "PPAP_ELEMENT_NUMBERS",
    "PPAP_PACKAGE_SCHEMA",
    "REASON_FOR_SUBMISSION_ALIASES",
    "REASON_FOR_SUBMISSION_VALUES",
    "ReasonForSubmission",
    "SUBMISSION_LEVELS",
    "SUBMISSION_LEVEL_ALIASES",
    "SUBMISSION_LEVEL_DESCRIPTIONS",
    "SubmissionLevel",
    "load_ppap_csv",
    "validate_ppap",
]

# ---------------------------------------------------------------------------
# 1. Canonical 18 PPAP Element IDs & Names (AIAG PPAP 4th Edition §2.2)
# ---------------------------------------------------------------------------

PPAPElementId = Literal[
    "2.2.1",
    "2.2.2",
    "2.2.3",
    "2.2.4",
    "2.2.5",
    "2.2.6",
    "2.2.7",
    "2.2.8",
    "2.2.9",
    "2.2.10",
    "2.2.11",
    "2.2.12",
    "2.2.13",
    "2.2.14",
    "2.2.15",
    "2.2.16",
    "2.2.17",
    "2.2.18",
]

PPAP_ELEMENT_IDS: tuple[PPAPElementId, ...] = (
    "2.2.1",
    "2.2.2",
    "2.2.3",
    "2.2.4",
    "2.2.5",
    "2.2.6",
    "2.2.7",
    "2.2.8",
    "2.2.9",
    "2.2.10",
    "2.2.11",
    "2.2.12",
    "2.2.13",
    "2.2.14",
    "2.2.15",
    "2.2.16",
    "2.2.17",
    "2.2.18",
)

PPAP_ELEMENT_NAMES: MappingProxyType[PPAPElementId, str] = MappingProxyType({
    "2.2.1": "Design Records",
    "2.2.2": "Authorized Engineering Change Documents",
    "2.2.3": "Customer Engineering Approval",
    "2.2.4": "Design Failure Mode and Effects Analysis (Design FMEA)",
    "2.2.5": "Process Flow Diagrams",
    "2.2.6": "Process Failure Mode and Effects Analysis (Process FMEA)",
    "2.2.7": "Control Plan",
    "2.2.8": "Measurement System Analysis Studies",
    "2.2.9": "Dimensional Results",
    "2.2.10": "Records of Material / Performance Test Results",
    "2.2.11": "Initial Process Studies",
    "2.2.12": "Qualified Laboratory Documentation",
    "2.2.13": "Appearance Approval Report (AAR)",
    "2.2.14": "Sample Production Parts",
    "2.2.15": "Master Sample",
    "2.2.16": "Checking Aids",
    "2.2.17": "Customer-Specific Requirements",
    "2.2.18": "Part Submission Warrant (PSW)",
})

PPAP_ELEMENT_NUMBERS: MappingProxyType[int, PPAPElementId] = MappingProxyType({
    i + 1: elem_id for i, elem_id in enumerate(PPAP_ELEMENT_IDS)
})

PPAP_ELEMENT_ALIASES: MappingProxyType[str, PPAPElementId] = MappingProxyType({
    # 2.2.1
    "1": "2.2.1",
    "2.2.1": "2.2.1",
    "design records": "2.2.1",
    "design_records": "2.2.1",
    "design record": "2.2.1",
    "drawings": "2.2.1",
    "drawing": "2.2.1",
    "cad": "2.2.1",
    # 2.2.2
    "2": "2.2.2",
    "2.2.2": "2.2.2",
    "authorized engineering change documents": "2.2.2",
    "authorized_engineering_change_documents": "2.2.2",
    "engineering change documents": "2.2.2",
    "engineering change document": "2.2.2",
    "engineering changes": "2.2.2",
    "engineering change": "2.2.2",
    "ecn": "2.2.2",
    "eco": "2.2.2",
    # 2.2.3
    "3": "2.2.3",
    "2.2.3": "2.2.3",
    "customer engineering approval": "2.2.3",
    "customer_engineering_approval": "2.2.3",
    "customer approval": "2.2.3",
    "engineering approval": "2.2.3",
    # 2.2.4
    "4": "2.2.4",
    "2.2.4": "2.2.4",
    "design failure mode and effects analysis (design fmea)": "2.2.4",
    "design failure mode and effects analysis": "2.2.4",
    "design fmea": "2.2.4",
    "design_fmea": "2.2.4",
    "dfmea": "2.2.4",
    # 2.2.5
    "5": "2.2.5",
    "2.2.5": "2.2.5",
    "process flow diagrams": "2.2.5",
    "process_flow_diagrams": "2.2.5",
    "process flow diagram": "2.2.5",
    "process flow": "2.2.5",
    "process_flow": "2.2.5",
    "pfd": "2.2.5",
    # 2.2.6
    "6": "2.2.6",
    "2.2.6": "2.2.6",
    "process failure mode and effects analysis (process fmea)": "2.2.6",
    "process failure mode and effects analysis": "2.2.6",
    "process fmea": "2.2.6",
    "process_fmea": "2.2.6",
    "pfmea": "2.2.6",
    # 2.2.7
    "7": "2.2.7",
    "2.2.7": "2.2.7",
    "control plan": "2.2.7",
    "control_plan": "2.2.7",
    "cp": "2.2.7",
    # 2.2.8
    "8": "2.2.8",
    "2.2.8": "2.2.8",
    "measurement system analysis studies": "2.2.8",
    "measurement system analysis": "2.2.8",
    "measurement_system_analysis_studies": "2.2.8",
    "msa": "2.2.8",
    "gage r&r": "2.2.8",
    "gage rr": "2.2.8",
    # 2.2.9
    "9": "2.2.9",
    "2.2.9": "2.2.9",
    "dimensional results": "2.2.9",
    "dimensional_results": "2.2.9",
    "dimensional report": "2.2.9",
    "dimensions": "2.2.9",
    # 2.2.10
    "10": "2.2.10",
    "2.2.10": "2.2.10",
    "records of material / performance test results": "2.2.10",
    "records of material/performance test results": "2.2.10",
    "material / performance test results": "2.2.10",
    "material/performance test results": "2.2.10",
    "material test results": "2.2.10",
    "performance test results": "2.2.10",
    "material and performance test results": "2.2.10",
    "material & performance test results": "2.2.10",
    # 2.2.11
    "11": "2.2.11",
    "2.2.11": "2.2.11",
    "initial process studies": "2.2.11",
    "initial_process_studies": "2.2.11",
    "initial process study": "2.2.11",
    "process capability": "2.2.11",
    "capability studies": "2.2.11",
    "spc": "2.2.11",
    "cpk": "2.2.11",
    "ppk": "2.2.11",
    # 2.2.12
    "12": "2.2.12",
    "2.2.12": "2.2.12",
    "qualified laboratory documentation": "2.2.12",
    "qualified_laboratory_documentation": "2.2.12",
    "laboratory documentation": "2.2.12",
    "lab documentation": "2.2.12",
    "lab certs": "2.2.12",
    "lab certification": "2.2.12",
    # 2.2.13
    "13": "2.2.13",
    "2.2.13": "2.2.13",
    "appearance approval report (aar)": "2.2.13",
    "appearance approval report": "2.2.13",
    "appearance_approval_report": "2.2.13",
    "aar": "2.2.13",
    # 2.2.14
    "14": "2.2.14",
    "2.2.14": "2.2.14",
    "sample production parts": "2.2.14",
    "sample_production_parts": "2.2.14",
    "production samples": "2.2.14",
    "sample parts": "2.2.14",
    "samples": "2.2.14",
    # 2.2.15
    "15": "2.2.15",
    "2.2.15": "2.2.15",
    "master sample": "2.2.15",
    "master_sample": "2.2.15",
    "master samples": "2.2.15",
    # 2.2.16
    "16": "2.2.16",
    "2.2.16": "2.2.16",
    "checking aids": "2.2.16",
    "checking_aids": "2.2.16",
    "checking aid": "2.2.16",
    "fixtures": "2.2.16",
    "fixture": "2.2.16",
    # 2.2.17
    "17": "2.2.17",
    "2.2.17": "2.2.17",
    "customer-specific requirements": "2.2.17",
    "customer specific requirements": "2.2.17",
    "customer_specific_requirements": "2.2.17",
    "records of compliance with customer-specific requirements": "2.2.17",
    "csr": "2.2.17",
    # 2.2.18
    "18": "2.2.18",
    "2.2.18": "2.2.18",
    "part submission warrant (psw)": "2.2.18",
    "part submission warrant": "2.2.18",
    "part_submission_warrant": "2.2.18",
    "psw": "2.2.18",
    "warrant": "2.2.18",
})


# ---------------------------------------------------------------------------
# 2. Submission Levels 1–5 (AIAG PPAP 4th Edition Section 4)
# ---------------------------------------------------------------------------

SubmissionLevel = Literal[1, 2, 3, 4, 5]

SUBMISSION_LEVELS: tuple[SubmissionLevel, ...] = (1, 2, 3, 4, 5)

SUBMISSION_LEVEL_DESCRIPTIONS: MappingProxyType[SubmissionLevel, str] = MappingProxyType({
    1: "Warrant only (and for designated appearance items, an Appearance Approval Report) submitted to customer.",
    2: "Warrant with product samples and limited supporting data submitted to customer.",
    3: "Warrant with product samples and complete supporting data submitted to customer.",
    4: "Warrant and other requirements as defined by customer.",
    5: "Warrant with product samples and complete supporting data reviewed at supplier's manufacturing location.",
})

SUBMISSION_LEVEL_ALIASES: MappingProxyType[str, SubmissionLevel] = MappingProxyType({
    "1": 1,
    "level 1": 1,
    "level_1": 1,
    "level1": 1,
    "l1": 1,
    "2": 2,
    "level 2": 2,
    "level_2": 2,
    "level2": 2,
    "l2": 2,
    "3": 3,
    "level 3": 3,
    "level_3": 3,
    "level3": 3,
    "l3": 3,
    "4": 4,
    "level 4": 4,
    "level_4": 4,
    "level4": 4,
    "l4": 4,
    "5": 5,
    "level 5": 5,
    "level_5": 5,
    "level5": 5,
    "l5": 5,
})


# ---------------------------------------------------------------------------
# 3. Reason for Submission Vocabulary (PSW Field 18, Appendix A)
# ---------------------------------------------------------------------------

ReasonForSubmission = Literal[
    "Initial Submission",
    "Engineering Change(s)",
    "Tooling: Transfer, Replacement, Refurbishment, or additional",
    "Correction of Discrepancy",
    "Tooling Inactive > than 1 year",
    "Change to Optional Construction or Material",
    "Sub-Supplier or Material Source Change",
    "Change in Part Processing",
    "Parts Produced at Additional Location",
    "Other",
]

REASON_FOR_SUBMISSION_VALUES: tuple[ReasonForSubmission, ...] = (
    "Initial Submission",
    "Engineering Change(s)",
    "Tooling: Transfer, Replacement, Refurbishment, or additional",
    "Correction of Discrepancy",
    "Tooling Inactive > than 1 year",
    "Change to Optional Construction or Material",
    "Sub-Supplier or Material Source Change",
    "Change in Part Processing",
    "Parts Produced at Additional Location",
    "Other",
)

REASON_FOR_SUBMISSION_ALIASES: MappingProxyType[str, ReasonForSubmission] = MappingProxyType({
    "initial submission": "Initial Submission",
    "initial": "Initial Submission",
    "new part": "Initial Submission",
    "engineering change(s)": "Engineering Change(s)",
    "engineering change": "Engineering Change(s)",
    "engineering changes": "Engineering Change(s)",
    "ecn": "Engineering Change(s)",
    "eco": "Engineering Change(s)",
    "tooling: transfer, replacement, refurbishment, or additional": (
        "Tooling: Transfer, Replacement, Refurbishment, or additional"
    ),
    "tooling transfer, replacement, refurbishment, or additional": (
        "Tooling: Transfer, Replacement, Refurbishment, or additional"
    ),
    "tooling change": "Tooling: Transfer, Replacement, Refurbishment, or additional",
    "tooling transfer": "Tooling: Transfer, Replacement, Refurbishment, or additional",
    "tooling replacement": "Tooling: Transfer, Replacement, Refurbishment, or additional",
    "correction of discrepancy": "Correction of Discrepancy",
    "discrepancy correction": "Correction of Discrepancy",
    "discrepancy": "Correction of Discrepancy",
    "tooling inactive > than 1 year": "Tooling Inactive > than 1 year",
    "tooling inactive > 1 year": "Tooling Inactive > than 1 year",
    "tooling inactive": "Tooling Inactive > than 1 year",
    "inactive tooling": "Tooling Inactive > than 1 year",
    "change to optional construction or material": "Change to Optional Construction or Material",
    "optional construction or material": "Change to Optional Construction or Material",
    "material change": "Change to Optional Construction or Material",
    "sub-supplier or material source change": "Sub-Supplier or Material Source Change",
    "sub supplier or material source change": "Sub-Supplier or Material Source Change",
    "supplier change": "Sub-Supplier or Material Source Change",
    "source change": "Sub-Supplier or Material Source Change",
    "change in part processing": "Change in Part Processing",
    "process change": "Change in Part Processing",
    "processing change": "Change in Part Processing",
    "parts produced at additional location": "Parts Produced at Additional Location",
    "additional location": "Parts Produced at Additional Location",
    "new location": "Parts Produced at Additional Location",
    "other": "Other",
    "other - please specify": "Other",
    "other (specify)": "Other",
})


# ---------------------------------------------------------------------------
# 4. Evidence Status Vocabulary & Undecided Sentinel
# ---------------------------------------------------------------------------

EvidenceStatus = Literal[
    "submitted",
    "retained",
    "not_applicable",
    "missing",
    "undecided",
]

EVIDENCE_STATUS_VALUES: tuple[EvidenceStatus, ...] = (
    "submitted",
    "retained",
    "not_applicable",
    "missing",
    "undecided",
)

EVIDENCE_STATUS_ALIASES: MappingProxyType[str, EvidenceStatus] = MappingProxyType({
    # submitted (S)
    "s": "submitted",
    "submitted": "submitted",
    "submit": "submitted",
    "present": "submitted",
    "provided": "submitted",
    "yes": "submitted",
    "y": "submitted",
    "complete": "submitted",
    "done": "submitted",
    "pass": "submitted",
    "attached": "submitted",
    # retained (R / *)
    "r": "retained",
    "retained": "retained",
    "retain": "retained",
    "on file": "retained",
    "on_file": "retained",
    "at supplier": "retained",
    "at_supplier": "retained",
    "available": "retained",
    "*": "retained",
    # not applicable
    "na": "not_applicable",
    "n/a": "not_applicable",
    "not applicable": "not_applicable",
    "not_applicable": "not_applicable",
    "exempt": "not_applicable",
    "waived": "not_applicable",
    # missing
    "m": "missing",
    "missing": "missing",
    "absent": "missing",
    "no": "missing",
    "n": "missing",
    "none": "missing",
    "fail": "missing",
    # undecided sentinel
    "u": "undecided",
    "undecided": "undecided",
    "unknown": "undecided",
    "unsurveyed": "undecided",
    "pending": "undecided",
    "tbd": "undecided",
    "?": "undecided",
    "": "undecided",
    "unspecified": "undecided",
})


# ---------------------------------------------------------------------------
# 5. Pydantic Domain Models: EvidenceItem & PPAPPackage
# ---------------------------------------------------------------------------

class EvidenceItem(pydantic.BaseModel):
    """One element of evidence in a PPAP submission package.

    Captures the element's canonical ID (§2.2.1–§2.2.18), descriptive name,
    supplier-side evidence availability status, boolean presence flag (with None as undecided sentinel),
    document references, and optional cross-engine payload.
    """

    element_id: PPAPElementId
    element_name: Annotated[str, pydantic.Field(default="", max_length=500)] = ""
    present: bool | None = None
    status: EvidenceStatus = "undecided"
    artifact_ref: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    retained_at_organization: bool | None = None
    submitted_to_customer: bool | None = None
    dated: Annotated[str | None, pydantic.Field(default=None, max_length=100)] = None
    notes: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    document_reference: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    comments: Annotated[str | None, pydantic.Field(default=None, max_length=2000)] = None
    linked_data: dict[str, Any] | None = None
    evidence_valid: bool | None = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def _populate_and_sync_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            elem_id = d.get("element_id")
            canonical_id: PPAPElementId | None = None
            if isinstance(elem_id, int) and elem_id in PPAP_ELEMENT_NUMBERS:
                canonical_id = PPAP_ELEMENT_NUMBERS[elem_id]
            elif isinstance(elem_id, str):
                clean = elem_id.strip().lower()
                if clean in PPAP_ELEMENT_ALIASES:
                    canonical_id = PPAP_ELEMENT_ALIASES[clean]

            name = d.get("element_name")
            if (name is None or (isinstance(name, str) and not name.strip())) and canonical_id:
                d["element_name"] = PPAP_ELEMENT_NAMES[canonical_id]

            # Sync document_reference <-> artifact_ref
            if d.get("document_reference") and not d.get("artifact_ref"):
                d["artifact_ref"] = d["document_reference"]
            elif d.get("artifact_ref") and not d.get("document_reference"):
                d["document_reference"] = d["artifact_ref"]

            # Sync comments <-> notes
            if d.get("comments") and not d.get("notes"):
                d["notes"] = d["comments"]
            elif d.get("notes") and not d.get("comments"):
                d["comments"] = d["notes"]

            return d
        return data

    @pydantic.field_validator("element_id", mode="before")
    @classmethod
    def normalize_element_id(cls, v: object) -> str:
        if isinstance(v, int) and v in PPAP_ELEMENT_NUMBERS:
            return PPAP_ELEMENT_NUMBERS[v]
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in PPAP_ELEMENT_ALIASES:
                return PPAP_ELEMENT_ALIASES[clean]
        raise ValueError(
            f"Invalid element_id: '{v}'. Must be a canonical AIAG PPAP element ID ('2.2.1'–'2.2.18') or recognized number (1–18)."
        )

    @pydantic.field_validator("element_name", mode="before")
    @classmethod
    def validate_element_name(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError("element_name must not be blank or whitespace-only")
        return str(v).strip()

    @pydantic.field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "undecided"
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in EVIDENCE_STATUS_ALIASES:
                return EVIDENCE_STATUS_ALIASES[clean]
        raise ValueError(
            f"Invalid evidence status: '{v}'. Must be one of {list(EVIDENCE_STATUS_VALUES)} or recognized alias."
        )

    @pydantic.field_validator(
        "document_reference",
        "comments",
        "artifact_ref",
        "notes",
        "dated",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, v: object) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()


class PPAPPackage(pydantic.BaseModel):
    """Production Part Approval Process (PPAP) submission package metadata & evidence set.

    Represents a full 18-element PPAP package at a specified Submission Level (1–5)
    and Reason for Submission.
    """

    part_name: Annotated[str, pydantic.Field(default="Sample Part", min_length=1, max_length=500)]
    part_number: Annotated[str, pydantic.Field(default="PART-001", min_length=1, max_length=500)]
    organization: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    supplier_name: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    supplier_code: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    customer: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    customer_name: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    submission_level: SubmissionLevel = 3
    reason_for_submission: ReasonForSubmission = "Initial Submission"
    application: Annotated[str | None, pydantic.Field(default=None, max_length=500)] = None
    designated_appearance_item: bool = False
    appearance_item: bool = False
    bulk_material: bool = False
    catalog_part: bool = False
    black_box_part: bool = False
    safety_critical: bool = False
    has_checking_aid: bool = False
    has_design_responsibility: bool = True
    customer_requirement_set: set[PPAPElementId] | list[PPAPElementId] | None = None
    elements: list[EvidenceItem] = pydantic.Field(default_factory=list)
    evidence: list[EvidenceItem] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="before")
    @classmethod
    def _sync_package_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            # Sync organization <-> supplier_name
            if "organization" in d and d.get("supplier_name") is None:
                d["supplier_name"] = d["organization"]
            elif "supplier_name" in d and d.get("organization") is None:
                d["organization"] = d["supplier_name"]
            # Sync customer <-> customer_name
            if "customer" in d and d.get("customer_name") is None:
                d["customer_name"] = d["customer"]
            elif "customer_name" in d and d.get("customer") is None:
                d["customer"] = d["customer_name"]
            # Sync designated_appearance_item <-> appearance_item
            if "designated_appearance_item" in d and not d.get("appearance_item"):
                d["appearance_item"] = d["designated_appearance_item"]
            elif "appearance_item" in d and not d.get("designated_appearance_item"):
                d["designated_appearance_item"] = d["appearance_item"]
            # Sync evidence <-> elements
            if "evidence" in d and not d.get("elements"):
                d["elements"] = d["evidence"]
            elif "elements" in d and not d.get("evidence"):
                d["evidence"] = d["elements"]
            return d
        return data

    @pydantic.field_validator("part_name", "part_number", mode="before")
    @classmethod
    def reject_blank_required(cls, v: object) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("must not be blank or whitespace-only")
        if v is None:
            raise ValueError("must not be None")
        return str(v).strip()

    @pydantic.field_validator("submission_level", mode="before")
    @classmethod
    def normalize_submission_level(cls, v: object) -> int:
        if isinstance(v, int) and v in SUBMISSION_LEVELS:
            return v
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in SUBMISSION_LEVEL_ALIASES:
                return SUBMISSION_LEVEL_ALIASES[clean]
        raise ValueError(
            f"Invalid submission_level: '{v}'. Must be an integer 1–5 or recognized alias ('Level 1'–'Level 5')."
        )

    @pydantic.field_validator("reason_for_submission", mode="before")
    @classmethod
    def normalize_reason_for_submission(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "Initial Submission"
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in REASON_FOR_SUBMISSION_ALIASES:
                return REASON_FOR_SUBMISSION_ALIASES[clean]
        raise ValueError(
            f"Invalid reason_for_submission: '{v}'. Must be one of {list(REASON_FOR_SUBMISSION_VALUES)} or recognized alias."
        )

    @pydantic.field_validator(
        "supplier_name",
        "supplier_code",
        "customer_name",
        "organization",
        "customer",
        "application",
        mode="before",
    )
    @classmethod
    def normalize_optional_metadata(cls, v: object) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    @pydantic.model_validator(mode="after")
    def validate_package_invariants(self) -> "PPAPPackage":
        # Unique element IDs check
        element_ids = [e.element_id for e in self.elements]
        dupes = find_duplicates(element_ids)
        if dupes:
            raise ValueError(f"duplicate element_id values found in PPAP package: {dupes}")

        # Level 4 customer requirement set check
        if self.customer_requirement_set is not None and self.submission_level != 4:
            raise ValueError(
                f"customer_requirement_set is only valid for Submission Level 4 (got Level {self.submission_level})"
            )
        return self

    @property
    def element_map(self) -> dict[PPAPElementId, EvidenceItem]:
        """Map of element_id to EvidenceItem for fast lookup."""
        return {e.element_id: e for e in self.elements}

    def get_element(self, element_id: str | int) -> EvidenceItem | None:
        """Lookup an evidence item by canonical element ID or number."""
        target_id: PPAPElementId | None = None
        if isinstance(element_id, int) and element_id in PPAP_ELEMENT_NUMBERS:
            target_id = PPAP_ELEMENT_NUMBERS[element_id]
        elif isinstance(element_id, str):
            clean = element_id.strip().lower()
            if clean in PPAP_ELEMENT_ALIASES:
                target_id = PPAP_ELEMENT_ALIASES[clean]
        if target_id is None:
            return None
        return self.element_map.get(target_id)

    def full_elements(self) -> list[EvidenceItem]:
        """Return a full 18-element list in canonical order (§2.2.1–§2.2.18),

        auto-filling any unsupplied element with the 'undecided' sentinel.
        """
        existing = self.element_map
        full: list[EvidenceItem] = []
        for elem_id in PPAP_ELEMENT_IDS:
            if elem_id in existing:
                full.append(existing[elem_id])
            else:
                full.append(
                    EvidenceItem(
                        element_id=elem_id,
                        element_name=PPAP_ELEMENT_NAMES[elem_id],
                        status="undecided",
                        present=None,
                    )
                )
        return full

    def to_dict(self) -> dict[str, Any]:
        """Export PPAP package to JSON-serializable dictionary representation."""
        return {
            "part_name": self.part_name,
            "part_number": self.part_number,
            "organization": self.organization,
            "supplier_name": self.supplier_name,
            "supplier_code": self.supplier_code,
            "customer": self.customer,
            "customer_name": self.customer_name,
            "submission_level": self.submission_level,
            "reason_for_submission": self.reason_for_submission,
            "application": self.application,
            "designated_appearance_item": self.designated_appearance_item,
            "appearance_item": self.appearance_item,
            "bulk_material": self.bulk_material,
            "catalog_part": self.catalog_part,
            "black_box_part": self.black_box_part,
            "safety_critical": self.safety_critical,
            "has_checking_aid": self.has_checking_aid,
            "has_design_responsibility": self.has_design_responsibility,
            "customer_requirement_set": (
                list(self.customer_requirement_set)
                if self.customer_requirement_set is not None
                else None
            ),
            "elements": [
                {
                    "element_id": e.element_id,
                    "element_name": e.element_name,
                    "present": e.present,
                    "status": e.status,
                    "artifact_ref": e.artifact_ref,
                    "retained_at_organization": e.retained_at_organization,
                    "submitted_to_customer": e.submitted_to_customer,
                    "dated": e.dated,
                    "notes": e.notes,
                    "document_reference": e.document_reference,
                    "comments": e.comments,
                    "linked_data": e.linked_data,
                    "evidence_valid": e.evidence_valid,
                }
                for e in self.elements
            ],
        }


# ---------------------------------------------------------------------------
# 6. TableSchema Ingest Contract & CSV Loader
# ---------------------------------------------------------------------------

PPAP_PACKAGE_SCHEMA = TableSchema(
    name="PPAP Evidence Item",
    row_model=EvidenceItem,
    required_columns=(
        "element_id",
    ),
    optional_columns=(
        "element_name",
        "present",
        "status",
        "document_reference",
        "artifact_ref",
        "comments",
        "notes",
        "dated",
        "retained_at_organization",
        "submitted_to_customer",
    ),
    dataset_model=None,
    template_hint="data/ppap_template.csv",
)

_CSV_COLUMN_ALIASES: dict[str, str] = {
    "element": "element_id",
    "element_id": "element_id",
    "element_number": "element_id",
    "element_no": "element_id",
    "item": "element_id",
    "id": "element_id",
    "section": "element_id",
    "element_name": "element_name",
    "name": "element_name",
    "description": "element_name",
    "title": "element_name",
    "present": "present",
    "is_present": "present",
    "available": "present",
    "status": "status",
    "evidence_status": "status",
    "submission_status": "status",
    "disposition": "status",
    "document_reference": "document_reference",
    "doc_ref": "document_reference",
    "doc_reference": "document_reference",
    "reference": "document_reference",
    "document": "document_reference",
    "filename": "document_reference",
    "file": "document_reference",
    "doc": "document_reference",
    "artifact_ref": "artifact_ref",
    "artifact": "artifact_ref",
    "comments": "comments",
    "comment": "comments",
    "notes": "comments",
    "note": "comments",
    "remarks": "comments",
    "rationale": "comments",
    "dated": "dated",
    "date": "dated",
    "retained_at_organization": "retained_at_organization",
    "retained": "retained_at_organization",
    "submitted_to_customer": "submitted_to_customer",
    "submitted": "submitted_to_customer",
}


def _normalize_csv_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Rename DataFrame columns through recognized aliases."""
    rename_map: dict[str, str] = {}
    for col in df.columns:
        norm_key = str(col).strip().lower()
        if norm_key in _CSV_COLUMN_ALIASES:
            rename_map[col] = _CSV_COLUMN_ALIASES[norm_key]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def load_ppap_csv(
    source: str | BinaryIO | bytes,
    *,
    filename: str = "upload.csv",
    part_name: str = "Sample Part",
    part_number: str = "PART-001",
    submission_level: SubmissionLevel = 3,
    reason_for_submission: ReasonForSubmission = "Initial Submission",
    **package_kwargs: Any,
) -> PPAPPackage:
    """Read and validate an uploaded PPAP checklist CSV against :data:`PPAP_PACKAGE_SCHEMA`.

    Accepts file path (str), file-like buffer, or raw bytes.
    Maps CSV columns through aliases and builds a validated :class:`PPAPPackage`.
    Raises :class:`IngestError` with a user-safe message on a malformed upload.
    """
    raw_df: pd.DataFrame
    if isinstance(source, str):
        raw_df = read_table_from_path(source)
    else:
        raw_df = read_table(source, filename=filename)

    norm_df = _normalize_csv_frame(raw_df)
    df = validate_table(norm_df, PPAP_PACKAGE_SCHEMA)

    # Convert DataFrame records into EvidenceItem instances
    evidence_items: list[EvidenceItem] = []
    for row in df.to_dict("records"):
        clean_row = cast(
            "dict[str, Any]",
            {k: (None if pd.isna(v) else v) for k, v in row.items()},
        )
        evidence_items.append(EvidenceItem(**clean_row))

    return PPAPPackage(
        part_name=part_name,
        part_number=part_number,
        submission_level=submission_level,
        reason_for_submission=reason_for_submission,
        elements=evidence_items,
        **package_kwargs,
    )


def _clean_scalar(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    return v


def validate_ppap(data: Any) -> PPAPPackage:
    """Validate untrusted PPAP input at the trust boundary.

    Accepts :class:`PPAPPackage`, a dict matching PPAPPackage structure,
    a list of :class:`EvidenceItem` / dicts (wrapped with default part metadata),
    or a :class:`pandas.DataFrame`.

    Raises :class:`pydantic.ValidationError` or :class:`IngestError` on constraint violations,
    or :class:`TypeError` on unsupported types.
    """
    if isinstance(data, PPAPPackage):
        return data
    if isinstance(data, pd.DataFrame):
        records = [
            cast("dict[str, Any]", {k: _clean_scalar(v) for k, v in row.items()})
            for row in data.to_dict("records")
        ]
        items = [EvidenceItem(**rec) for rec in records]
        return PPAPPackage(part_name="Sample Part", part_number="PART-001", elements=items)
    if isinstance(data, list):
        items_list: list[EvidenceItem] = []
        for item in data:
            if isinstance(item, EvidenceItem):
                items_list.append(item)
            elif isinstance(item, dict):
                clean_rec = cast(
                    "dict[str, Any]",
                    {ik: _clean_scalar(iv) for ik, iv in item.items()},
                )
                items_list.append(EvidenceItem(**clean_rec))
            else:
                raise TypeError(f"Expected EvidenceItem or dict in list, got {type(item).__name__}")
        return PPAPPackage(part_name="Sample Part", part_number="PART-001", elements=items_list)
    if isinstance(data, dict):
        clean_dict: dict[str, Any] = {}
        for k, v in data.items():
            if k in ("elements", "evidence") and isinstance(v, list):
                clean_elements: list[EvidenceItem] = []
                for item in v:
                    if isinstance(item, EvidenceItem):
                        clean_elements.append(item)
                    elif isinstance(item, dict):
                        clean_rec = cast(
                            "dict[str, Any]",
                            {ik: _clean_scalar(iv) for ik, iv in item.items()},
                        )
                        clean_elements.append(EvidenceItem(**clean_rec))
                    else:
                        raise TypeError(f"Expected EvidenceItem or dict in elements list, got {type(item).__name__}")
                clean_dict["elements"] = clean_elements
            else:
                clean_dict[k] = _clean_scalar(v)
        return PPAPPackage(**clean_dict)
    raise TypeError(f"Expected PPAPPackage, DataFrame, list of EvidenceItems, or dict, got {type(data).__name__}")

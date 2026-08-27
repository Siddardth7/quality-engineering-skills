"""
ppap.py
Single-writer visual PPAP Canvas controller and HTML matrix renderer for Quality Platform.

Provides `PPAPCanvasElement` and `PPAPCanvas` controller for managing an in-memory
18-element AIAG Production Part Approval Process (PPAP) 4th Edition checklist canvas,
Table 4.1 / Table 4.2 Submission and Retention Matrix (Levels 1–5), evidence status
tracking, benchmark automotive sample dataset loading, single-writer CRUD operations,
audit synchronization via `quality_core.ppap`, summary KPI rollups, responsive
dark/light themed HTML canvas generation, and strict enforcement of the Section 5
Customer Authority Invariant.

Standards References:
- AIAG Production Part Approval Process (PPAP) Reference Manual, 4th Edition (June 2006):
  - Table 4.1 & Table 4.2 Submission and Retention Matrix (pp. 17–19)
  - Section 2.2 (§2.2.1–§2.2.18) Element Requirements
  - Section 4 Submission Levels 1–5
  - Section 5 Part Submission Status (Customer Authority Invariant)
  - Appendix A Part Submission Warrant (PSW) completion rules
"""

from __future__ import annotations

import html
from dataclasses import asdict, dataclass, field
from typing import Any, cast

from quality_core.ppap.applicability import assess_applicability
from quality_core.ppap.schema import (
    EVIDENCE_STATUS_ALIASES,
    EVIDENCE_STATUS_VALUES,
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
    validate_ppap,
)
from quality_core.ppap.table_4_1 import (
    REQUIREMENT_CODES,
    TABLE_4_1_MATRIX,
    RequirementCode,
    elements_required_at_level,
    submission_level_description,
)
from quality_core.theme.palette import (
    AMBER,
    BG_CARD,
    BG_PRIMARY,
    BG_SECONDARY,
    BORDER,
    DANGER,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    VIOLET,
)

__all__ = [
    "PPAPCanvas",
    "PPAPCanvasElement",
    "SAMPLE_PPAP_ELEMENTS",
    "SAMPLE_PPAP_PACKAGE",
    "load_sample_ppap_canvas",
    "render_ppap",
]

_STANDARDS_BASIS: str = (
    "AIAG Production Part Approval Process (PPAP) Reference Manual, 4th Edition "
    "(June 2006), Table 4.1 & Table 4.2 Submission and Retention Matrix, "
    "Section 2.2 Element Requirements, and Section 5 Part Submission Status."
)

_AUTHORITY_INVARIANT_NOTICE: str = (
    "Customer approval dispositions ('Approved', 'Interim Approval', 'Rejected') "
    "are reserved exclusively for the customer's authorized representative per "
    "AIAG PPAP 4th Edition Section 5. This canvas evaluates supplier submission readiness only."
)


# ---------------------------------------------------------------------------
# 1. PPAPCanvasElement Dataclass
# ---------------------------------------------------------------------------


@dataclass
class PPAPCanvasElement:
    """Individual element within the 18-element AIAG PPAP checklist canvas.

    Captures canonical element ID (§2.2.1–§2.2.18), name, evidence status,
    Table 4.1 requirement codes across Levels 1–5, artifact/document reference,
    supplier notes, dated status, presence flag, applicability verdict, and validation findings.
    """

    element_id: PPAPElementId
    element_name: str = ""
    status: EvidenceStatus = "undecided"
    requirement_level_1: RequirementCode = "R"
    requirement_level_2: RequirementCode = "S"
    requirement_level_3: RequirementCode = "S"
    requirement_level_4: RequirementCode = "*"
    requirement_level_5: RequirementCode = "R"
    artifact_ref: str | None = None
    document_reference: str | None = None
    notes: str | None = None
    comments: str | None = None
    dated: str | None = None
    present: bool | None = None
    applicability_verdict: str | None = None
    validation_status: str = "valid"
    findings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Element ID normalization & validation
        if isinstance(self.element_id, bool):
            raise TypeError(f"element_id cannot be a boolean, got {self.element_id!r}")
        if isinstance(self.element_id, int):
            if self.element_id in PPAP_ELEMENT_NUMBERS:
                self.element_id = PPAP_ELEMENT_NUMBERS[self.element_id]
            else:
                raise ValueError(f"Invalid element_id number: {self.element_id}. Must be 1–18.")
        elif isinstance(self.element_id, str):
            clean = self.element_id.strip().lower()
            if clean in PPAP_ELEMENT_ALIASES:
                self.element_id = PPAP_ELEMENT_ALIASES[clean]
            else:
                raise ValueError(
                    f"Invalid element_id: '{self.element_id}'. Must be a canonical AIAG PPAP element ID ('2.2.1'–'2.2.18') or alias."
                )
        else:
            raise TypeError(f"element_id must be a string or integer, got {type(self.element_id).__name__}")

        # Element Name
        if not isinstance(self.element_name, str):
            raise TypeError(f"element_name must be a string, got {type(self.element_name).__name__}")
        if not self.element_name.strip():
            self.element_name = PPAP_ELEMENT_NAMES[self.element_id]
        else:
            self.element_name = self.element_name.strip()

        # Status validation & normalization
        if not isinstance(self.status, str):
            raise TypeError(f"status must be a string, got {type(self.status).__name__}")
        clean_status = self.status.strip().lower()
        if clean_status in EVIDENCE_STATUS_ALIASES:
            self.status = cast(EvidenceStatus, EVIDENCE_STATUS_ALIASES[clean_status])
        else:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of {list(EVIDENCE_STATUS_VALUES)} or recognized alias."
            )

        # Populate Table 4.1 matrix requirements if using defaults or invalid codes
        for lvl in (1, 2, 3, 4, 5):
            attr_name = f"requirement_level_{lvl}"
            cur_val = getattr(self, attr_name)
            matrix_req = TABLE_4_1_MATRIX.get((self.element_id, cast(SubmissionLevel, lvl)), "R")
            if cur_val is None or cur_val not in REQUIREMENT_CODES:
                setattr(self, attr_name, matrix_req)

        # Sync artifact_ref and document_reference
        if self.artifact_ref is not None:
            if not isinstance(self.artifact_ref, str):
                raise TypeError(f"artifact_ref must be a string or None, got {type(self.artifact_ref).__name__}")
            self.artifact_ref = self.artifact_ref.strip() or None
        if self.document_reference is not None:
            if not isinstance(self.document_reference, str):
                raise TypeError(
                    f"document_reference must be a string or None, got {type(self.document_reference).__name__}"
                )
            self.document_reference = self.document_reference.strip() or None

        if self.artifact_ref is not None and self.document_reference is None:
            self.document_reference = self.artifact_ref
        elif self.document_reference is not None and self.artifact_ref is None:
            self.artifact_ref = self.document_reference

        # Sync notes and comments
        if self.notes is not None:
            if not isinstance(self.notes, str):
                raise TypeError(f"notes must be a string or None, got {type(self.notes).__name__}")
            self.notes = self.notes.strip() or None
        if self.comments is not None:
            if not isinstance(self.comments, str):
                raise TypeError(f"comments must be a string or None, got {type(self.comments).__name__}")
            self.comments = self.comments.strip() or None

        if self.notes is not None and self.comments is None:
            self.comments = self.notes
        elif self.comments is not None and self.notes is None:
            self.notes = self.comments

        # Dated
        if self.dated is not None:
            if not isinstance(self.dated, str):
                raise TypeError(f"dated must be a string or None, got {type(self.dated).__name__}")
            self.dated = self.dated.strip() or None

        # Present flag
        if self.present is not None and not isinstance(self.present, bool):
            raise TypeError(f"present must be a boolean or None, got {type(self.present).__name__}")

        # Applicability Verdict
        if self.applicability_verdict is not None:
            if not isinstance(self.applicability_verdict, str):
                raise TypeError(
                    f"applicability_verdict must be a string or None, got {type(self.applicability_verdict).__name__}"
                )
            self.applicability_verdict = self.applicability_verdict.strip() or None

        # Validation status
        if not isinstance(self.validation_status, str):
            raise TypeError(f"validation_status must be a string, got {type(self.validation_status).__name__}")
        self.validation_status = self.validation_status.strip()

        # Findings
        if not isinstance(self.findings, list):
            raise TypeError(f"findings must be a list, got {type(self.findings).__name__}")
        self.findings = [str(f) for f in self.findings]

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable dictionary representation of the canvas element."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PPAPCanvasElement:
        """Construct a PPAPCanvasElement from a dictionary supporting snake_case or PascalCase keys."""
        if not isinstance(data, dict):
            raise TypeError(f"data must be a dictionary, got {type(data).__name__}: {data!r}")

        def get_field(snake_name: str, pascal_name: str, default: Any = None) -> Any:
            if snake_name in data:
                return data[snake_name]
            if pascal_name in data:
                return data[pascal_name]
            return default

        element_id = get_field("element_id", "Element_ID", default=get_field("id", "ID", default=None))
        if element_id is None:
            raise ValueError("Missing required field 'element_id' or 'id'")

        element_name = get_field("element_name", "Element_Name", default="")
        status = get_field("status", "Status", default="undecided")
        req1 = get_field("requirement_level_1", "Requirement_Level_1", default="R")
        req2 = get_field("requirement_level_2", "Requirement_Level_2", default="S")
        req3 = get_field("requirement_level_3", "Requirement_Level_3", default="S")
        req4 = get_field("requirement_level_4", "Requirement_Level_4", default="*")
        req5 = get_field("requirement_level_5", "Requirement_Level_5", default="R")
        artifact_ref = get_field(
            "artifact_ref",
            "Artifact_Ref",
            default=get_field("document_reference", "Document_Reference", default=None),
        )
        document_reference = get_field("document_reference", "Document_Reference", default=artifact_ref)
        notes = get_field("notes", "Notes", default=get_field("comments", "Comments", default=None))
        comments = get_field("comments", "Comments", default=notes)
        dated = get_field("dated", "Dated", default=None)
        present = get_field("present", "Present", default=None)
        applicability_verdict = get_field("applicability_verdict", "Applicability_Verdict", default=None)
        validation_status = get_field("validation_status", "Validation_Status", default="valid")
        findings = get_field("findings", "Findings", default=None)

        return cls(
            element_id=element_id,
            element_name=element_name,
            status=status,
            requirement_level_1=req1,
            requirement_level_2=req2,
            requirement_level_3=req3,
            requirement_level_4=req4,
            requirement_level_5=req5,
            artifact_ref=artifact_ref,
            document_reference=document_reference,
            notes=notes,
            comments=comments,
            dated=dated,
            present=present,
            applicability_verdict=applicability_verdict,
            validation_status=validation_status,
            findings=findings if findings is not None else [],
        )


# ---------------------------------------------------------------------------
# 2. Reference Benchmark Dataset (Level 3 Automotive Transmission Output Shaft)
# ---------------------------------------------------------------------------

SAMPLE_PPAP_ELEMENTS: list[dict[str, Any]] = [
    {
        "element_id": "2.2.1",
        "element_name": "Design Records",
        "status": "submitted",
        "artifact_ref": "DWG-SFT-4410-RevD.pdf",
        "notes": "Full 2D GD&T drawing & 3D STEP CAD model conforming to customer specs.",
        "dated": "2026-08-15",
        "present": True,
    },
    {
        "element_id": "2.2.2",
        "element_name": "Authorized Engineering Change Documents",
        "status": "submitted",
        "artifact_ref": "ECN-2026-089.pdf",
        "notes": "Approved engineering change notice for spline relief groove modification.",
        "dated": "2026-08-16",
        "present": True,
    },
    {
        "element_id": "2.2.3",
        "element_name": "Customer Engineering Approval",
        "status": "submitted",
        "artifact_ref": "CEA-OEM-7712.pdf",
        "notes": "Customer SQA & Product Engineering formal approval sign-off.",
        "dated": "2026-08-18",
        "present": True,
    },
    {
        "element_id": "2.2.4",
        "element_name": "Design Failure Mode and Effects Analysis (Design FMEA)",
        "status": "submitted",
        "artifact_ref": "DFMEA-SFT-04.xlsx",
        "notes": "Design FMEA approved and submitted with customer engineering sign-off.",
        "dated": "2026-07-20",
        "present": True,
    },
    {
        "element_id": "2.2.5",
        "element_name": "Process Flow Diagrams",
        "status": "submitted",
        "artifact_ref": "PFD-OP-010-180.pdf",
        "notes": "Complete end-to-end manufacturing process flow from forging receipt to packaging.",
        "dated": "2026-08-10",
        "present": True,
    },
    {
        "element_id": "2.2.6",
        "element_name": "Process Failure Mode and Effects Analysis (Process FMEA)",
        "status": "submitted",
        "artifact_ref": "PFMEA-SFT-2026-Rev2.xlsx",
        "notes": "AIAG-VDA 1st Edition PFMEA; all high Action Priority failure modes mitigated.",
        "dated": "2026-08-12",
        "present": True,
    },
    {
        "element_id": "2.2.7",
        "element_name": "Control Plan",
        "status": "submitted",
        "artifact_ref": "CP-SFT-2026-RevC.xlsx",
        "notes": "Pre-launch and production control plans linked to PFMEA special characteristics.",
        "dated": "2026-08-14",
        "present": True,
    },
    {
        "element_id": "2.2.8",
        "element_name": "Measurement System Analysis Studies",
        "status": "submitted",
        "artifact_ref": "MSA-GAGE-RR-2026.pdf",
        "notes": "CMM & Air Gage Gage R&R studies (%GRR = 7.8% <= 10%, ndc = 14 >= 5).",
        "dated": "2026-08-17",
        "present": True,
    },
    {
        "element_id": "2.2.9",
        "element_name": "Dimensional Results",
        "status": "submitted",
        "artifact_ref": "DIM-REPORT-30PCS.pdf",
        "notes": "100% ballooned layout inspection of 30 production sample parts across all print dimensions.",
        "dated": "2026-08-19",
        "present": True,
    },
    {
        "element_id": "2.2.10",
        "element_name": "Records of Material / Performance Test Results",
        "status": "submitted",
        "artifact_ref": "MAT-TEST-MET-4410.pdf",
        "notes": "Certified mill test certificates, case hardening depth, and core tensile test reports.",
        "dated": "2026-08-18",
        "present": True,
    },
    {
        "element_id": "2.2.11",
        "element_name": "Initial Process Studies",
        "status": "submitted",
        "artifact_ref": "SPC-CAPABILITY-Ppk.pdf",
        "notes": "Bearing journal OD statistical capability: Ppk = 1.84, Cpk = 1.76 (> 1.67 acceptance band).",
        "dated": "2026-08-19",
        "present": True,
    },
    {
        "element_id": "2.2.12",
        "element_name": "Qualified Laboratory Documentation",
        "status": "submitted",
        "artifact_ref": "ISO-IEC-17025-CERT.pdf",
        "notes": "ISO/IEC 17025 accreditation scope and internal metallurgical laboratory certifications.",
        "dated": "2026-06-30",
        "present": True,
    },
    {
        "element_id": "2.2.13",
        "element_name": "Appearance Approval Report (AAR)",
        "status": "not_applicable",
        "artifact_ref": None,
        "notes": "Not applicable — functional transmission powertrain component with no appearance designation.",
        "dated": None,
        "present": False,
    },
    {
        "element_id": "2.2.14",
        "element_name": "Sample Production Parts",
        "status": "submitted",
        "artifact_ref": "SAMPLE-TAGS-30PCS.pdf",
        "notes": "30 production parts from 300-piece production run shipped with proper identification tags.",
        "dated": "2026-08-20",
        "present": True,
    },
    {
        "element_id": "2.2.15",
        "element_name": "Master Sample",
        "status": "retained",
        "artifact_ref": "MASTER-SMPL-TAG-01.pdf",
        "notes": "Master sample part retained in organization climate-controlled quality laboratory.",
        "dated": "2026-08-20",
        "present": True,
    },
    {
        "element_id": "2.2.16",
        "element_name": "Checking Aids",
        "status": "submitted",
        "artifact_ref": "CHK-FIXTURE-CERT-09.pdf",
        "notes": "Spline contour checking fixture calibration and dimensional verification report.",
        "dated": "2026-08-15",
        "present": True,
    },
    {
        "element_id": "2.2.17",
        "element_name": "Customer-Specific Requirements",
        "status": "submitted",
        "artifact_ref": "CSR-COMPLIANCE-MATRIX.pdf",
        "notes": "Compliance matrix for customer-specific requirements (AIAG CQI-9 heat treat & CQI-15 weld).",
        "dated": "2026-08-18",
        "present": True,
    },
    {
        "element_id": "2.2.18",
        "element_name": "Part Submission Warrant (PSW)",
        "status": "submitted",
        "artifact_ref": "PSW-PART-4410-SIGNED.pdf",
        "notes": "Completed and signed 27-field Part Submission Warrant.",
        "dated": "2026-08-21",
        "present": True,
    },
]

SAMPLE_PPAP_PACKAGE: dict[str, Any] = {
    "part_name": "Transmission Output Shaft",
    "part_number": "PART-SFT-4410",
    "organization": "Acme Precision Driveline Systems",
    "supplier_name": "Acme Precision Driveline Systems",
    "supplier_code": "VND-88210",
    "customer": "Apex Automotive Group",
    "customer_name": "Apex Automotive Group",
    "submission_level": 3,
    "reason_for_submission": "Initial Submission",
    "application": "8-Speed Automatic Transmission",
    "designated_appearance_item": False,
    "appearance_item": False,
    "has_design_responsibility": True,
    "has_checking_aid": True,
    "elements": SAMPLE_PPAP_ELEMENTS,
}


# ---------------------------------------------------------------------------
# 3. PPAPCanvas Controller
# ---------------------------------------------------------------------------


class PPAPCanvas:
    """Controller for the in-memory single-writer PPAP visual checklist matrix canvas.

    Provides single-writer CRUD operations, Table 4.1 Level 1–5 requirement matrix rendering,
    applicability and audit synchronization via `quality_core.ppap`, state summarization,
    and responsive dark/light themed HTML generation adhering to the Quality Platform theme
    and the Section 5 Customer Authority Invariant.
    """

    def __init__(
        self,
        elements: list[PPAPCanvasElement | EvidenceItem | dict[str, Any]] | PPAPPackage | None = None,
        package: PPAPPackage | dict[str, Any] | None = None,
        part_name: str = "Sample Part",
        part_number: str = "PART-001",
        submission_level: int | str = 3,
        reason_for_submission: str = "Initial Submission",
        organization: str | None = None,
        supplier_name: str | None = None,
        supplier_code: str | None = None,
        customer: str | None = None,
        customer_name: str | None = None,
        application: str | None = None,
        has_design_responsibility: bool = True,
        designated_appearance_item: bool = False,
        has_checking_aid: bool = True,
        title: str = "AIAG PPAP 4th Edition Checklist Canvas",
        description: str = "Interactive single-writer visual PPAP canvas with Table 4.1 matrix and submission readiness.",
    ) -> None:
        # Title and Description validation
        if isinstance(title, bool) or not isinstance(title, str) or not title.strip():
            raise TypeError("title must be a non-empty string")
        if isinstance(description, bool) or not isinstance(description, str) or not description.strip():
            raise TypeError("description must be a non-empty string")
        self._title = title.strip()
        self._description = description.strip()

        # Part Name & Part Number validation
        if isinstance(part_name, bool) or not isinstance(part_name, str) or not part_name.strip():
            raise TypeError("part_name must be a non-empty string")
        if isinstance(part_number, bool) or not isinstance(part_number, str) or not part_number.strip():
            raise TypeError("part_number must be a non-empty string")
        self._part_name = part_name.strip()
        self._part_number = part_number.strip()

        # Submission Level validation (reject bool explicitly before int)
        if isinstance(submission_level, bool):
            raise TypeError(f"submission_level cannot be a boolean, got {submission_level!r}")
        if isinstance(submission_level, int):
            if submission_level in SUBMISSION_LEVELS:
                self._submission_level: SubmissionLevel = cast(SubmissionLevel, submission_level)
            else:
                raise ValueError(f"submission_level must be an integer 1–5, got {submission_level}")
        elif isinstance(submission_level, str):
            clean_lvl = submission_level.strip().lower()
            if clean_lvl in SUBMISSION_LEVEL_ALIASES:
                self._submission_level = SUBMISSION_LEVEL_ALIASES[clean_lvl]
            else:
                raise ValueError(f"Invalid submission_level: '{submission_level}'. Must be 1–5 or recognized alias.")
        else:
            raise TypeError(f"submission_level must be an integer or string, got {type(submission_level).__name__}")

        # Reason for Submission validation
        if isinstance(reason_for_submission, bool) or not isinstance(reason_for_submission, str):
            raise TypeError(f"reason_for_submission must be a string, got {type(reason_for_submission).__name__}")
        clean_rsn = reason_for_submission.strip().lower()
        clean_rsn_normalized = clean_rsn.replace("_", " ")
        if clean_rsn in REASON_FOR_SUBMISSION_ALIASES:
            self._reason_for_submission: ReasonForSubmission = REASON_FOR_SUBMISSION_ALIASES[clean_rsn]
        elif clean_rsn_normalized in REASON_FOR_SUBMISSION_ALIASES:
            self._reason_for_submission = REASON_FOR_SUBMISSION_ALIASES[clean_rsn_normalized]
        else:
            raise ValueError(
                f"Invalid reason_for_submission: '{reason_for_submission}'. Must be one of {list(REASON_FOR_SUBMISSION_VALUES)}."
            )

        # Organization / Supplier Name syncing
        if isinstance(organization, bool):
            raise TypeError("organization / supplier_name must be a string or None")
        if isinstance(supplier_name, bool):
            raise TypeError("organization / supplier_name must be a string or None")
        org_val = organization or supplier_name
        if org_val is not None:
            if not isinstance(org_val, str):
                raise TypeError("organization / supplier_name must be a string or None")
            self._organization: str | None = org_val.strip() or None
            self._supplier_name: str | None = self._organization
        else:
            self._organization = None
            self._supplier_name = None

        # Supplier Code
        if isinstance(supplier_code, bool):
            raise TypeError("supplier_code must be a string or None")
        if supplier_code is not None:
            if not isinstance(supplier_code, str):
                raise TypeError("supplier_code must be a string or None")
            self._supplier_code: str | None = supplier_code.strip() or None
        else:
            self._supplier_code = None

        # Customer / Customer Name syncing
        if isinstance(customer, bool):
            raise TypeError("customer / customer_name must be a string or None")
        if isinstance(customer_name, bool):
            raise TypeError("customer / customer_name must be a string or None")
        cust_val = customer or customer_name
        if cust_val is not None:
            if not isinstance(cust_val, str):
                raise TypeError("customer / customer_name must be a string or None")
            self._customer: str | None = cust_val.strip() or None
            self._customer_name: str | None = self._customer
        else:
            self._customer = None
            self._customer_name = None

        # Application
        if isinstance(application, bool):
            raise TypeError("application must be a string or None")
        if application is not None:
            if not isinstance(application, str):
                raise TypeError("application must be a string or None")
            self._application: str | None = application.strip() or None
        else:
            self._application = None

        # Boolean Flags validation
        for flag_name, flag_val in (
            ("has_design_responsibility", has_design_responsibility),
            ("designated_appearance_item", designated_appearance_item),
            ("has_checking_aid", has_checking_aid),
        ):
            if not isinstance(flag_val, bool):
                raise TypeError(f"{flag_name} must be a boolean, got {type(flag_val).__name__}")

        self._has_design_responsibility = has_design_responsibility
        self._designated_appearance_item = designated_appearance_item
        self._has_checking_aid = has_checking_aid

        self._elements: dict[PPAPElementId, PPAPCanvasElement] = {}

        # Ingest from package if provided
        pkg_target = package if package is not None else (elements if isinstance(elements, PPAPPackage) else None)
        if pkg_target is not None:
            pkg = validate_ppap(pkg_target)
            self._part_name = pkg.part_name
            self._part_number = pkg.part_number
            self._submission_level = pkg.submission_level
            self._reason_for_submission = pkg.reason_for_submission
            self._organization = pkg.organization or pkg.supplier_name
            self._supplier_name = self._organization
            self._supplier_code = pkg.supplier_code
            self._customer = pkg.customer or pkg.customer_name
            self._customer_name = self._customer
            self._application = pkg.application
            self._has_design_responsibility = pkg.has_design_responsibility
            self._designated_appearance_item = pkg.designated_appearance_item or pkg.appearance_item
            self._has_checking_aid = pkg.has_checking_aid

            for pkg_item in pkg.full_elements():
                elem = PPAPCanvasElement(
                    element_id=pkg_item.element_id,
                    element_name=pkg_item.element_name or PPAP_ELEMENT_NAMES[pkg_item.element_id],
                    status=pkg_item.status,
                    artifact_ref=pkg_item.artifact_ref or pkg_item.document_reference,
                    document_reference=pkg_item.document_reference or pkg_item.artifact_ref,
                    notes=pkg_item.notes or pkg_item.comments,
                    comments=pkg_item.comments or pkg_item.notes,
                    dated=pkg_item.dated,
                    present=pkg_item.present,
                )
                self._elements[elem.element_id] = elem

        elif elements is not None:
            if not isinstance(elements, list):
                raise TypeError(f"elements must be a list, got {type(elements).__name__}")
            for el_item in elements:
                self.add_element(el_item)

        # Ensure all 18 canonical elements are populated with undecided default if not explicitly provided
        for elem_id in PPAP_ELEMENT_IDS:
            if elem_id not in self._elements:
                self._elements[elem_id] = PPAPCanvasElement(
                    element_id=elem_id,
                    element_name=PPAP_ELEMENT_NAMES[elem_id],
                    status="undecided",
                    present=None,
                )

        # Synchronize applicability, requirements, and findings
        self.sync_audit()

    # -----------------------------------------------------------------------
    # Metadata Properties
    # -----------------------------------------------------------------------

    @property
    def title(self) -> str:
        """Canvas title."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
            raise TypeError("title must be a non-empty string")
        self._title = value.strip()

    @property
    def description(self) -> str:
        """Canvas description."""
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
            raise TypeError("description must be a non-empty string")
        self._description = value.strip()

    @property
    def part_name(self) -> str:
        """Part name."""
        return self._part_name

    @part_name.setter
    def part_name(self, value: str) -> None:
        if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
            raise TypeError("part_name must be a non-empty string")
        self._part_name = value.strip()

    @property
    def part_number(self) -> str:
        """Part number."""
        return self._part_number

    @part_number.setter
    def part_number(self, value: str) -> None:
        if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
            raise TypeError("part_number must be a non-empty string")
        self._part_number = value.strip()

    @property
    def submission_level(self) -> SubmissionLevel:
        """AIAG PPAP Submission Level (1–5)."""
        return self._submission_level

    @submission_level.setter
    def submission_level(self, value: int | str) -> None:
        if isinstance(value, bool):
            raise TypeError("submission_level cannot be a boolean")
        if isinstance(value, int):
            if value in SUBMISSION_LEVELS:
                self._submission_level = cast(SubmissionLevel, value)
            else:
                raise ValueError(f"submission_level must be an integer 1–5, got {value}")
        elif isinstance(value, str):
            clean = value.strip().lower()
            if clean in SUBMISSION_LEVEL_ALIASES:
                self._submission_level = SUBMISSION_LEVEL_ALIASES[clean]
            else:
                raise ValueError(f"Invalid submission_level: '{value}'")
        else:
            raise TypeError("submission_level must be an integer 1–5 or recognized alias")

    @property
    def reason_for_submission(self) -> ReasonForSubmission:
        """PSW Reason for Submission."""
        return self._reason_for_submission

    @reason_for_submission.setter
    def reason_for_submission(self, value: str) -> None:
        if isinstance(value, bool) or not isinstance(value, str):
            raise TypeError("reason_for_submission must be a string")
        clean = value.strip().lower()
        clean_normalized = clean.replace("_", " ")
        if clean in REASON_FOR_SUBMISSION_ALIASES:
            self._reason_for_submission = REASON_FOR_SUBMISSION_ALIASES[clean]
        elif clean_normalized in REASON_FOR_SUBMISSION_ALIASES:
            self._reason_for_submission = REASON_FOR_SUBMISSION_ALIASES[clean_normalized]
        else:
            raise ValueError(f"Invalid reason_for_submission: '{value}'")

    @property
    def organization(self) -> str | None:
        """Organization / supplier name."""
        return self._organization

    @organization.setter
    def organization(self, value: str | None) -> None:
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, str):
                raise TypeError("organization must be a string or None")
            self._organization = value.strip() or None
        else:
            self._organization = None
        self._supplier_name = self._organization

    @property
    def supplier_name(self) -> str | None:
        """Supplier name alias."""
        return self._supplier_name

    @supplier_name.setter
    def supplier_name(self, value: str | None) -> None:
        self.organization = value

    @property
    def supplier_code(self) -> str | None:
        """Supplier vendor / DUNS code."""
        return self._supplier_code

    @supplier_code.setter
    def supplier_code(self, value: str | None) -> None:
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, str):
                raise TypeError("supplier_code must be a string or None")
            self._supplier_code = value.strip() or None
        else:
            self._supplier_code = None

    @property
    def customer(self) -> str | None:
        """Customer name."""
        return self._customer

    @customer.setter
    def customer(self, value: str | None) -> None:
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, str):
                raise TypeError("customer must be a string or None")
            self._customer = value.strip() or None
        else:
            self._customer = None
        self._customer_name = self._customer

    @property
    def customer_name(self) -> str | None:
        """Customer name alias."""
        return self._customer_name

    @customer_name.setter
    def customer_name(self, value: str | None) -> None:
        self.customer = value

    @property
    def application(self) -> str | None:
        """Vehicle or equipment application."""
        return self._application

    @application.setter
    def application(self, value: str | None) -> None:
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, str):
                raise TypeError("application must be a string or None")
            self._application = value.strip() or None
        else:
            self._application = None

    @property
    def has_design_responsibility(self) -> bool:
        """Design responsibility flag."""
        return self._has_design_responsibility

    @has_design_responsibility.setter
    def has_design_responsibility(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("has_design_responsibility must be a boolean")
        self._has_design_responsibility = value

    @property
    def designated_appearance_item(self) -> bool:
        """Designated appearance item flag."""
        return self._designated_appearance_item

    @designated_appearance_item.setter
    def designated_appearance_item(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("designated_appearance_item must be a boolean")
        self._designated_appearance_item = value

    @property
    def appearance_item(self) -> bool:
        """Appearance item flag alias."""
        return self._designated_appearance_item

    @appearance_item.setter
    def appearance_item(self, value: bool) -> None:
        self.designated_appearance_item = value

    @property
    def has_checking_aid(self) -> bool:
        """Checking aid presence flag."""
        return self._has_checking_aid

    @has_checking_aid.setter
    def has_checking_aid(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("has_checking_aid must be a boolean")
        self._has_checking_aid = value

    @property
    def elements(self) -> list[PPAPCanvasElement]:
        """List of 18 PPAPCanvasElement objects in canonical order (§2.2.1–§2.2.18)."""
        return [self._elements[elem_id] for elem_id in PPAP_ELEMENT_IDS if elem_id in self._elements]

    @property
    def rows(self) -> list[PPAPCanvasElement]:
        """Alias to elements matching other visual canvas controllers."""
        return self.elements

    # -----------------------------------------------------------------------
    # Factory and Benchmark Loaders
    # -----------------------------------------------------------------------

    @classmethod
    def load_sample(
        cls,
        title: str = "AIAG PPAP 4th Edition Checklist Canvas",
        description: str = "Interactive single-writer visual PPAP canvas with Table 4.1 matrix and submission readiness.",
        **kwargs: Any,
    ) -> PPAPCanvas:
        """Create and return a PPAPCanvas loaded with the Level 3 automotive benchmark dataset."""
        sample_copy = dict(SAMPLE_PPAP_PACKAGE)
        pkg_keys = {
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
            "has_checking_aid",
            "has_design_responsibility",
            "elements",
        }
        for k in list(kwargs.keys()):
            if k in pkg_keys:
                sample_copy[k] = kwargs.pop(k)
        return cls(package=sample_copy, title=title, description=description)

    @classmethod
    def from_package(
        cls,
        package: PPAPPackage | dict[str, Any],
        title: str = "AIAG PPAP 4th Edition Checklist Canvas",
        description: str = "Interactive single-writer visual PPAP canvas with Table 4.1 matrix and submission readiness.",
    ) -> PPAPCanvas:
        """Create and return a PPAPCanvas initialized from a PPAPPackage model or dictionary."""
        return cls(package=package, title=title, description=description)

    # -----------------------------------------------------------------------
    # Single-Writer CRUD Operations
    # -----------------------------------------------------------------------

    def _resolve_element_id(self, element_id: str | int) -> PPAPElementId | None:
        """Resolve an element ID from integer (1–18), canonical ID string ('2.2.1'), or alias."""
        if isinstance(element_id, bool):
            return None
        if isinstance(element_id, int):
            return PPAP_ELEMENT_NUMBERS.get(element_id)
        if isinstance(element_id, str):
            clean = element_id.strip().lower()
            if clean in PPAP_ELEMENT_ALIASES:
                return PPAP_ELEMENT_ALIASES[clean]
            if clean.isdigit():
                num = int(clean)
                return PPAP_ELEMENT_NUMBERS.get(num)
        return None

    def get_element(self, element_id: str | int) -> PPAPCanvasElement | None:
        """Retrieve a canvas element by canonical ID, integer number (1–18), or name alias."""
        resolved = self._resolve_element_id(element_id)
        if resolved is None:
            return None
        return self._elements.get(resolved)

    def get_row(self, row_id: str | int) -> PPAPCanvasElement | None:
        """Alias to get_element."""
        return self.get_element(row_id)

    def add_element(self, element: PPAPCanvasElement | EvidenceItem | dict[str, Any]) -> PPAPCanvasElement:
        """Add an element to the canvas. Raises ValueError on duplicate element ID."""
        if isinstance(element, dict):
            canvas_elem = PPAPCanvasElement.from_dict(element)
        elif isinstance(element, EvidenceItem):
            canvas_elem = PPAPCanvasElement(
                element_id=element.element_id,
                element_name=element.element_name or PPAP_ELEMENT_NAMES[element.element_id],
                status=element.status,
                artifact_ref=element.artifact_ref or element.document_reference,
                document_reference=element.document_reference or element.artifact_ref,
                notes=element.notes or element.comments,
                comments=element.comments or element.notes,
                dated=element.dated,
                present=element.present,
            )
        elif isinstance(element, PPAPCanvasElement):
            canvas_elem = element
        else:
            raise TypeError(
                f"element must be a PPAPCanvasElement, EvidenceItem, or dict, got {type(element).__name__}: {element!r}"
            )

        if canvas_elem.element_id in self._elements:
            raise ValueError(f"Element with ID '{canvas_elem.element_id}' already exists in canvas.")

        self._elements[canvas_elem.element_id] = canvas_elem
        return canvas_elem

    def add_row(self, row: PPAPCanvasElement | dict[str, Any]) -> PPAPCanvasElement:
        """Alias to add_element."""
        return self.add_element(row)

    def update_element(self, element_id: str | int, /, **updates: Any) -> PPAPCanvasElement:
        """Update fields of an existing element and re-validate."""
        resolved = self._resolve_element_id(element_id)
        if resolved is None or resolved not in self._elements:
            raise KeyError(f"Element with identifier '{element_id}' not found in canvas.")

        existing = self._elements[resolved]
        data = existing.to_dict()

        field_mapping: dict[str, str] = {
            "element_id": "element_id",
            "Element_ID": "element_id",
            "id": "element_id",
            "ID": "element_id",
            "element_name": "element_name",
            "Element_Name": "element_name",
            "status": "status",
            "Status": "status",
            "requirement_level_1": "requirement_level_1",
            "Requirement_Level_1": "requirement_level_1",
            "requirement_level_2": "requirement_level_2",
            "Requirement_Level_2": "requirement_level_2",
            "requirement_level_3": "requirement_level_3",
            "Requirement_Level_3": "requirement_level_3",
            "requirement_level_4": "requirement_level_4",
            "Requirement_Level_4": "requirement_level_4",
            "requirement_level_5": "requirement_level_5",
            "Requirement_Level_5": "requirement_level_5",
            "artifact_ref": "artifact_ref",
            "Artifact_Ref": "artifact_ref",
            "document_reference": "document_reference",
            "Document_Reference": "document_reference",
            "notes": "notes",
            "Notes": "notes",
            "comments": "comments",
            "Comments": "comments",
            "dated": "dated",
            "Dated": "dated",
            "present": "present",
            "Present": "present",
            "applicability_verdict": "applicability_verdict",
            "Applicability_Verdict": "applicability_verdict",
            "validation_status": "validation_status",
            "Validation_Status": "validation_status",
            "findings": "findings",
            "Findings": "findings",
        }

        for k, v in updates.items():
            if k in field_mapping:
                data[field_mapping[k]] = v
            else:
                raise ValueError(f"Unknown field '{k}' in element update")

        # Keep artifact_ref and document_reference in sync if only one is updated
        if "artifact_ref" in updates and "document_reference" not in updates:
            data["document_reference"] = updates["artifact_ref"]
        elif "document_reference" in updates and "artifact_ref" not in updates:
            data["artifact_ref"] = updates["document_reference"]

        # Keep notes and comments in sync if only one is updated
        if "notes" in updates and "comments" not in updates:
            data["comments"] = updates["notes"]
        elif "comments" in updates and "notes" not in updates:
            data["notes"] = updates["comments"]

        new_element = PPAPCanvasElement.from_dict(data)

        if new_element.element_id != resolved and new_element.element_id in self._elements:
            raise ValueError(
                f"Cannot change element ID to '{new_element.element_id}': ID already exists in canvas."
            )

        if new_element.element_id != resolved:
            del self._elements[resolved]
        self._elements[new_element.element_id] = new_element
        return new_element

    def edit_row(self, row_id: str | int, /, **updates: Any) -> PPAPCanvasElement:
        """Alias to update_element."""
        return self.update_element(row_id, **updates)

    def delete_element(self, element_id: str | int) -> PPAPCanvasElement:
        """Remove an element by its ID and return the deleted element."""
        resolved = self._resolve_element_id(element_id)
        if resolved is None or resolved not in self._elements:
            raise KeyError(f"Element with identifier '{element_id}' not found in canvas.")

        return self._elements.pop(resolved)

    def delete_row(self, row_id: str | int) -> PPAPCanvasElement:
        """Alias to delete_element."""
        return self.delete_element(row_id)

    # -----------------------------------------------------------------------
    # Ingest & Domain Interoperability
    # -----------------------------------------------------------------------

    def to_package(self) -> PPAPPackage:
        """Convert the current canvas state into a validated `PPAPPackage` domain model."""
        evidence_items = [
            EvidenceItem(
                element_id=e.element_id,
                element_name=e.element_name,
                status=e.status,
                artifact_ref=e.artifact_ref,
                document_reference=e.document_reference,
                notes=e.notes,
                comments=e.comments,
                dated=e.dated,
                present=e.present,
            )
            for e in self.elements
        ]
        return PPAPPackage(
            part_name=self._part_name,
            part_number=self._part_number,
            organization=self._organization,
            supplier_name=self._supplier_name,
            supplier_code=self._supplier_code,
            customer=self._customer,
            customer_name=self._customer_name,
            submission_level=self._submission_level,
            reason_for_submission=self._reason_for_submission,
            application=self._application,
            has_design_responsibility=self._has_design_responsibility,
            designated_appearance_item=self._designated_appearance_item,
            appearance_item=self._designated_appearance_item,
            has_checking_aid=self._has_checking_aid,
            elements=evidence_items,
        )

    def sync_audit(self) -> dict[str, Any]:
        """Synchronize element applicability, Table 4.1 requirements, and audit findings."""
        pkg = self.to_package()
        app_res = assess_applicability(pkg)

        for elem in self.elements:
            elem_app = app_res.elements.get(elem.element_id)
            if elem_app is not None:
                elem.applicability_verdict = elem_app.verdict

            req_code = TABLE_4_1_MATRIX.get((elem.element_id, self._submission_level), "R")
            if req_code == "S":
                if elem.status == "submitted":
                    elem.validation_status = "valid"
                    elem.findings = []
                elif elem.status == "not_applicable" and elem.applicability_verdict == "NOT_APPLICABLE":
                    elem.validation_status = "valid"
                    elem.findings = [
                        f"Conditionally exempt per AIAG PPAP 4th Edition: {elem_app.rationale if elem_app else ''}"
                    ]
                elif elem.status == "missing":
                    elem.validation_status = "missing"
                    elem.findings = [
                        f"Element {elem.element_id} ({elem.element_name}) is required for submission at Level {self._submission_level} but is missing."
                    ]
                elif elem.status == "undecided":
                    elem.validation_status = "undecided"
                    elem.findings = [
                        f"Element {elem.element_id} ({elem.element_name}) status is undecided (unsurveyed)."
                    ]
                else:  # retained / other
                    elem.validation_status = "warning"
                    elem.findings = [
                        f"Element {elem.element_id} ({elem.element_name}) is marked retained but Submission Level {self._submission_level} requires submission ('S')."
                    ]
            elif req_code == "R":
                if elem.status in ("retained", "submitted"):
                    elem.validation_status = "valid"
                    elem.findings = []
                elif elem.status == "not_applicable" and elem.applicability_verdict == "NOT_APPLICABLE":
                    elem.validation_status = "valid"
                    elem.findings = []
                elif elem.status == "missing":
                    elem.validation_status = "missing"
                    elem.findings = [
                        f"Element {elem.element_id} ({elem.element_name}) is required for retention at Level {self._submission_level} but is missing."
                    ]
                else:  # undecided / other
                    elem.validation_status = "undecided"
                    elem.findings = [
                        f"Element {elem.element_id} ({elem.element_name}) status is undecided."
                    ]
            else:  # "*"
                if elem.status in ("retained", "submitted"):
                    elem.validation_status = "valid"
                    elem.findings = []
                elif elem.status == "not_applicable" and elem.applicability_verdict == "NOT_APPLICABLE":
                    elem.validation_status = "valid"
                    elem.findings = []
                elif elem.status == "missing":
                    elem.validation_status = "missing"
                    elem.findings = [
                        f"Element {elem.element_id} ({elem.element_name}) required per customer definition at Level 4."
                    ]
                else:  # undecided / other
                    elem.validation_status = "undecided"
                    elem.findings = [
                        f"Element {elem.element_id} ({elem.element_name}) status is undecided."
                    ]

        return self.get_summary()

    # -----------------------------------------------------------------------
    # Summary KPI Calculation
    # -----------------------------------------------------------------------

    def get_summary(self) -> dict[str, Any]:
        """Compute aggregated PPAP canvas metrics, Table 4.1 readiness, and authority invariant notice."""
        total_elements = len(self.elements)
        submitted_count = sum(1 for e in self.elements if e.status == "submitted")
        retained_count = sum(1 for e in self.elements if e.status == "retained")
        not_applicable_count = sum(1 for e in self.elements if e.status == "not_applicable")
        missing_count = sum(1 for e in self.elements if e.status == "missing")
        undecided_count = sum(1 for e in self.elements if e.status == "undecided")

        req_element_ids = list(elements_required_at_level(self._submission_level))
        required_elements_count = len(req_element_ids)

        req_submitted_count = 0
        req_missing_count = 0
        req_undecided_count = 0

        for elem_id in req_element_ids:
            elem = self.get_element(elem_id)
            if elem is None:
                req_missing_count += 1
            elif elem.status == "submitted":
                req_submitted_count += 1
            elif elem.status == "not_applicable" and elem.applicability_verdict == "NOT_APPLICABLE":
                req_submitted_count += 1
            elif elem.status == "missing":
                req_missing_count += 1
            elif elem.status == "undecided":
                req_undecided_count += 1
            else:  # retained / other
                req_missing_count += 1

        # Submission readiness verdict evaluation (Section 5 Customer Authority Invariant compliant)
        if req_missing_count > 0 or missing_count > 0:
            submission_readiness = "NOT_READY"
        elif req_undecided_count > 0 or undecided_count > 0:
            submission_readiness = "INDETERMINATE"
        else:
            submission_readiness = "SUBMISSION_READY"

        return {
            "total_elements": total_elements,
            "submission_level": self._submission_level,
            "submission_level_description": submission_level_description(self._submission_level),
            "reason_for_submission": self._reason_for_submission,
            "part_name": self._part_name,
            "part_number": self._part_number,
            "organization": self._organization,
            "customer": self._customer,
            "status_counts": {
                "submitted": submitted_count,
                "retained": retained_count,
                "not_applicable": not_applicable_count,
                "missing": missing_count,
                "undecided": undecided_count,
            },
            "required_elements_count": required_elements_count,
            "required_submitted_count": req_submitted_count,
            "required_missing_count": req_missing_count,
            "required_undecided_count": req_undecided_count,
            "submission_readiness": submission_readiness,
            "standards_basis": _STANDARDS_BASIS,
            "authority_notice": _AUTHORITY_INVARIANT_NOTICE,
        }

    # -----------------------------------------------------------------------
    # Themed HTML Matrix Rendering
    # -----------------------------------------------------------------------

    def to_html(self, theme: str = "dark", standalone: bool = True) -> str:
        """Render the PPAP canvas as a styled HTML Table 4.1 matrix checklist.

        Parameters
        ----------
        theme : {"dark", "light"}, default="dark"
            Color palette theme.
        standalone : bool, default=True
            If True, generates a full standalone HTML5 document. If False, generates
            an embeddable styled container.

        Returns
        -------
        str
            Rendered HTML string.
        """
        if not isinstance(standalone, bool):
            raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")
        if theme not in ("dark", "light"):
            raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

        summary = self.get_summary()
        is_dark = theme == "dark"

        # Theme color variables
        if is_dark:
            c_bg_page = BG_PRIMARY
            c_bg_card = BG_CARD
            c_bg_header = BG_SECONDARY
            c_border = BORDER
            c_text_main = TEXT_PRIMARY
            c_text_muted = TEXT_SECONDARY
            c_row_hover = "#242d40"
            c_active_col_bg = "rgba(245, 158, 11, 0.08)"
            c_active_header_bg = "rgba(245, 158, 11, 0.20)"
            c_legend_bg = "rgba(30, 37, 53, 0.6)"
            c_callout_bg = "rgba(245, 158, 11, 0.05)"
        else:
            c_bg_page = "#f8fafc"
            c_bg_card = "#ffffff"
            c_bg_header = "#f1f5f9"
            c_border = "#e2e8f0"
            c_text_main = "#0f172a"
            c_text_muted = "#64748b"
            c_row_hover = "#f8fafc"
            c_active_col_bg = "rgba(245, 158, 11, 0.10)"
            c_active_header_bg = "rgba(245, 158, 11, 0.22)"
            c_legend_bg = "#f1f5f9"
            c_callout_bg = "#fffbeb"

        # Submission Readiness Badge
        readiness = summary["submission_readiness"]
        if readiness == "SUBMISSION_READY":
            readiness_badge = (
                f'<span style="display:inline-block;padding:6px 14px;border-radius:6px;'
                f'font-size:13px;font-weight:700;background-color:{SUCCESS};color:#ffffff;'
                f'letter-spacing:0.5px;">SUBMISSION READY</span>'
            )
        elif readiness == "NOT_READY":
            readiness_badge = (
                f'<span style="display:inline-block;padding:6px 14px;border-radius:6px;'
                f'font-size:13px;font-weight:700;background-color:{DANGER};color:#ffffff;'
                f'letter-spacing:0.5px;">NOT READY</span>'
            )
        else:
            readiness_badge = (
                f'<span style="display:inline-block;padding:6px 14px;border-radius:6px;'
                f'font-size:13px;font-weight:700;background-color:{VIOLET};color:#ffffff;'
                f'letter-spacing:0.5px;">INDETERMINATE</span>'
            )

        # Status badge helper
        def format_status_badge(st: str) -> str:
            if st == "submitted":
                return (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(16, 185, 129, 0.2);'
                    f'color:{SUCCESS};border:1px solid {SUCCESS};">Submitted</span>'
                )
            elif st == "retained":
                return (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(245, 158, 11, 0.2);'
                    f'color:{AMBER};border:1px solid {AMBER};">Retained</span>'
                )
            elif st == "not_applicable":
                return (
                    '<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:500;background-color:rgba(148, 163, 184, 0.2);'
                    f'color:{c_text_muted};border:1px solid {c_border};">N/A</span>'
                )
            elif st == "missing":
                return (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:700;background-color:rgba(239, 68, 68, 0.2);'
                    f'color:{DANGER};border:1px solid {DANGER};">Missing</span>'
                )
            else:  # undecided
                return (
                    f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                    f'font-size:11px;font-weight:600;background-color:rgba(139, 92, 246, 0.2);'
                    f'color:{VIOLET};border:1px solid {VIOLET};">Undecided</span>'
                )

        # Requirement Code badge helper
        def format_req_badge(code: str, is_active_level: bool = False) -> str:
            extra_style = "box-shadow:0 0 0 1px #f59e0b;" if is_active_level else ""
            if code == "S":
                return (
                    f'<span style="display:inline-block;padding:2px 6px;border-radius:3px;'
                    f'font-size:11px;font-family:monospace;font-weight:700;background-color:rgba(59, 130, 246, 0.2);'
                    f'color:#60a5fa;{extra_style}">S</span>'
                )
            elif code == "R":
                return (
                    f'<span style="display:inline-block;padding:2px 6px;border-radius:3px;'
                    f'font-size:11px;font-family:monospace;font-weight:700;background-color:rgba(245, 158, 11, 0.2);'
                    f'color:{AMBER};{extra_style}">R</span>'
                )
            else:  # "*"
                return (
                    f'<span style="display:inline-block;padding:2px 6px;border-radius:3px;'
                    f'font-size:11px;font-family:monospace;font-weight:700;background-color:rgba(148, 163, 184, 0.2);'
                    f'color:{c_text_muted};{extra_style}">*</span>'
                )

        # Build table rows
        rows_html: list[str] = []
        for elem in self.elements:
            req_l1 = format_req_badge(elem.requirement_level_1, self._submission_level == 1)
            req_l2 = format_req_badge(elem.requirement_level_2, self._submission_level == 2)
            req_l3 = format_req_badge(elem.requirement_level_3, self._submission_level == 3)
            req_l4 = format_req_badge(elem.requirement_level_4, self._submission_level == 4)
            req_l5 = format_req_badge(elem.requirement_level_5, self._submission_level == 5)

            active_code = getattr(elem, f"requirement_level_{self._submission_level}", "R")
            active_req = format_req_badge(active_code, True)
            st_badge = format_status_badge(elem.status)

            doc_ref = html.escape(elem.artifact_ref or elem.document_reference or "—")
            elem_notes = html.escape(elem.notes or elem.comments or "—")

            # Column style for active level
            def col_bg(lvl: int) -> str:
                return f"background-color:{c_active_col_bg};" if self._submission_level == lvl else ""

            row_str = f"""
            <tr style="border-bottom:1px solid {c_border};transition:background-color 0.15s ease;">
                <td style="padding:10px 12px;font-family:monospace;font-weight:700;color:{AMBER};white-space:nowrap;">{html.escape(elem.element_id)}</td>
                <td style="padding:10px 12px;font-weight:600;color:{c_text_main};">{html.escape(elem.element_name)}</td>
                <td style="padding:10px 8px;text-align:center;{col_bg(1)}">{req_l1}</td>
                <td style="padding:10px 8px;text-align:center;{col_bg(2)}">{req_l2}</td>
                <td style="padding:10px 8px;text-align:center;{col_bg(3)}">{req_l3}</td>
                <td style="padding:10px 8px;text-align:center;{col_bg(4)}">{req_l4}</td>
                <td style="padding:10px 8px;text-align:center;{col_bg(5)}">{req_l5}</td>
                <td style="padding:10px 10px;text-align:center;font-weight:700;background-color:{c_active_col_bg};">{active_req}</td>
                <td style="padding:10px 12px;text-align:center;">{st_badge}</td>
                <td style="padding:10px 12px;font-family:monospace;font-size:12px;color:{c_text_muted};">{doc_ref}</td>
                <td style="padding:10px 12px;font-size:12px;color:{c_text_muted};">{elem_notes}</td>
            </tr>
            """
            rows_html.append(row_str)

        # Header active column helpers
        def th_style(lvl: int) -> str:
            if self._submission_level == lvl:
                return (
                    f"padding:10px 8px;text-align:center;font-size:11px;font-weight:700;"
                    f"color:{AMBER};background-color:{c_active_header_bg};border-bottom:2px solid {AMBER};"
                )
            return f"padding:10px 8px;text-align:center;font-size:11px;font-weight:600;color:{c_text_muted};"

        status_counts = summary["status_counts"]
        escaped_title = html.escape(self._title)
        escaped_desc = html.escape(self._description)
        escaped_part_name = html.escape(self._part_name)
        escaped_part_number = html.escape(self._part_number)
        escaped_org = html.escape(self._organization or "Not Specified")
        escaped_cust = html.escape(self._customer or "Not Specified")
        escaped_rsn = html.escape(self._reason_for_submission)
        escaped_lvl_desc = html.escape(summary["submission_level_description"])

        container_html = f"""
        <div class="ppap-canvas-container" style="font-family:Inter,system-ui,-apple-system,sans-serif;color:{c_text_main};background-color:{c_bg_page};padding:24px;border-radius:12px;">
            <!-- Header Section -->
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:20px;">
                <div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                        <h2 style="margin:0;font-size:22px;font-weight:700;color:{c_text_main};">{escaped_title}</h2>
                        <span style="display:inline-block;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:700;background-color:{AMBER};color:#1e293b;">AIAG PPAP 4th Ed.</span>
                    </div>
                    <p style="margin:0;font-size:13px;color:{c_text_muted};">{escaped_desc}</p>
                </div>
                <div style="display:flex;align-items:center;gap:12px;">
                    {readiness_badge}
                </div>
            </div>

            <!-- Metadata KPI Card -->
            <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;padding:16px;margin-bottom:20px;">
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:16px;">
                    <div>
                        <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;margin-bottom:4px;">Part Identification</div>
                        <div style="font-size:14px;font-weight:700;color:{c_text_main};">{escaped_part_name}</div>
                        <div style="font-size:12px;font-family:monospace;color:{AMBER};">{escaped_part_number}</div>
                    </div>
                    <div>
                        <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;margin-bottom:4px;">Organization & Customer</div>
                        <div style="font-size:13px;font-weight:600;color:{c_text_main};">Org: {escaped_org}</div>
                        <div style="font-size:13px;color:{c_text_muted};">Cust: {escaped_cust}</div>
                    </div>
                    <div>
                        <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;margin-bottom:4px;">Submission Parameters</div>
                        <div style="font-size:14px;font-weight:700;color:{AMBER};">Submission Level {self._submission_level}</div>
                        <div style="font-size:12px;color:{c_text_muted};">{escaped_rsn}</div>
                    </div>
                    <div>
                        <div style="font-size:11px;font-weight:600;color:{c_text_muted};text-transform:uppercase;margin-bottom:4px;">Evidence Status Rollup</div>
                        <div style="display:flex;flex-wrap:wrap;gap:6px;font-size:11px;font-weight:600;">
                            <span style="color:{SUCCESS};">Submitted: {status_counts['submitted']}</span> •
                            <span style="color:{AMBER};">Retained: {status_counts['retained']}</span> •
                            <span style="color:{c_text_muted};">N/A: {status_counts['not_applicable']}</span> •
                            <span style="color:{DANGER};">Missing: {status_counts['missing']}</span> •
                            <span style="color:{VIOLET};">Undecided: {status_counts['undecided']}</span>
                        </div>
                    </div>
                </div>
                <div style="margin-top:12px;padding-top:10px;border-top:1px dashed {c_border};font-size:12px;color:{c_text_muted};">
                    <strong>Level {self._submission_level} Definition:</strong> {escaped_lvl_desc}
                </div>
            </div>

            <!-- Table 4.1 Matrix Grid -->
            <div style="background-color:{c_bg_card};border:1px solid {c_border};border-radius:8px;overflow-x:auto;margin-bottom:20px;">
                <table style="width:100%;border-collapse:collapse;text-align:left;font-size:13px;">
                    <thead>
                        <tr style="background-color:{c_bg_header};border-bottom:1px solid {c_border};">
                            <th style="padding:12px;font-size:11px;font-weight:700;color:{c_text_muted};text-transform:uppercase;">#</th>
                            <th style="padding:12px;font-size:11px;font-weight:700;color:{c_text_muted};text-transform:uppercase;">Element Requirement (§2.2)</th>
                            <th style="{th_style(1)}">L1</th>
                            <th style="{th_style(2)}">L2</th>
                            <th style="{th_style(3)}">L3</th>
                            <th style="{th_style(4)}">L4</th>
                            <th style="{th_style(5)}">L5</th>
                            <th style="padding:12px 10px;text-align:center;font-size:11px;font-weight:700;color:{AMBER};background-color:{c_active_header_bg};text-transform:uppercase;">Active Req</th>
                            <th style="padding:12px;text-align:center;font-size:11px;font-weight:700;color:{c_text_muted};text-transform:uppercase;">Evidence Status</th>
                            <th style="padding:12px;font-size:11px;font-weight:700;color:{c_text_muted};text-transform:uppercase;">Document / Artifact Reference</th>
                            <th style="padding:12px;font-size:11px;font-weight:700;color:{c_text_muted};text-transform:uppercase;">Notes / Comments</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows_html)}
                    </tbody>
                </table>
            </div>

            <!-- Legend & Section 5 Authority Invariant Notice -->
            <div style="display:grid;grid-template-columns:1fr;gap:12px;">
                <!-- Table 4.1 Legend -->
                <div style="background-color:{c_legend_bg};border:1px solid {c_border};border-radius:8px;padding:12px 16px;font-size:12px;color:{c_text_muted};">
                    <strong style="color:{c_text_main};">Table 4.1 Requirement Legend:</strong>
                    <span style="margin-left:8px;"><strong style="color:#60a5fa;">S</strong> = Submit to customer & retain copy</span>
                    <span style="margin-left:12px;"><strong style="color:{AMBER};">R</strong> = Retain at organization and make available</span>
                    <span style="margin-left:12px;"><strong style="color:{c_text_muted};">*</strong> = Retain at organization and submit upon request</span>
                </div>

                <!-- Section 5 Customer Authority Invariant Alert Box -->
                <div style="background-color:{c_callout_bg};border:1px solid rgba(245, 158, 11, 0.4);border-left:4px solid {AMBER};border-radius:6px;padding:12px 16px;font-size:12px;color:{c_text_main};">
                    <strong style="color:{AMBER};">🔒 Section 5 Customer Authority Invariant:</strong>
                    {_AUTHORITY_INVARIANT_NOTICE}
                </div>
            </div>
        </div>
        """

        if not standalone:
            return container_html

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>{escaped_title}</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background-color: {c_bg_page};
            color: {c_text_main};
            font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        table tr:hover {{
            background-color: {c_row_hover} !important;
        }}
    </style>
</head>
<body>
    {container_html}
</body>
</html>"""


# ---------------------------------------------------------------------------
# 4. Functional Helpers
# ---------------------------------------------------------------------------


def load_sample_ppap_canvas() -> PPAPCanvas:
    """Load a `PPAPCanvas` populated with the 18-element Level 3 benchmark automotive sample dataset."""
    return PPAPCanvas.load_sample()


def render_ppap(
    elements: list[PPAPCanvasElement | EvidenceItem | dict[str, Any]] | PPAPPackage | None = None,
    package: PPAPPackage | dict[str, Any] | None = None,
    theme: str = "dark",
    standalone: bool = True,
    **kwargs: Any,
) -> str:
    """Render PPAP elements or package directly to themed HTML.

    Parameters
    ----------
    elements : list or PPAPPackage, optional
        PPAP checklist elements or full package.
    package : PPAPPackage or dict, optional
        PPAP package model or dictionary.
    theme : {"dark", "light"}, default="dark"
        Theme color palette.
    standalone : bool, default=True
        Whether to return a complete HTML5 document or embeddable container.
    **kwargs : Any
        Additional constructor arguments for PPAPCanvas.

    Returns
    -------
    str
        Rendered HTML string.
    """
    if elements is not None:
        canvas = PPAPCanvas(elements=elements, **kwargs)
    elif package is not None:
        canvas = PPAPCanvas(package=package, **kwargs)
    else:
        canvas = PPAPCanvas.load_sample(**kwargs)
    return canvas.to_html(theme=theme, standalone=standalone)

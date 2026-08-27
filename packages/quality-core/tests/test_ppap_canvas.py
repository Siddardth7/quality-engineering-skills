"""
test_ppap_canvas.py
Exhaustive unit and integration test suite for PPAP visual checklist canvas
controller and themed HTML matrix renderer in `quality_core.canvas.ppap`.

Test Coverage:
- 100% line & branch coverage on quality_core.canvas.ppap
- Dataclass validation, normalization, and serialization (PPAPCanvasElement)
- Default initialization and paranoid type guards on constructor and setters
- Benchmark sample datasets (SAMPLE_PPAP_ELEMENTS, SAMPLE_PPAP_PACKAGE)
- Single-writer CRUD lifecycle (get, add, update, delete) and row/element aliases
- AIAG PPAP 4th Edition Table 4.1 matrix lookup and Level 1–5 column highlighting
- Domain interoperability (to_package, from_package) and audit synchronization (sync_audit)
- Summary KPI metrics and readiness rollups (SUBMISSION_READY, NOT_READY, INDETERMINATE)
- Dark and light theme semantic HTML rendering (standalone HTML5 and embeddable container)
- Security and XSS prevention across all user fields
- Mandatory Section 5 Customer Authority Invariant negative controls
- Functional helpers (load_sample_ppap_canvas, render_ppap)
"""

from __future__ import annotations

import html

import pytest
from quality_core.canvas.ppap import (
    SAMPLE_PPAP_ELEMENTS,
    SAMPLE_PPAP_PACKAGE,
    PPAPCanvas,
    PPAPCanvasElement,
    load_sample_ppap_canvas,
    render_ppap,
)
from quality_core.ppap.schema import (
    PPAP_ELEMENT_IDS,
    EvidenceItem,
    PPAPPackage,
)

# ===========================================================================
# 1. PPAPCanvasElement Dataclass Tests
# ===========================================================================


class TestPPAPCanvasElement:
    """Test suite for PPAPCanvasElement dataclass initialization and methods."""

    def test_init_canonical_id_and_defaults(self) -> None:
        """Element initializes with canonical ID and default values."""
        elem = PPAPCanvasElement(element_id="2.2.1")
        assert elem.element_id == "2.2.1"
        assert elem.element_name == "Design Records"
        assert elem.status == "undecided"
        assert elem.requirement_level_1 == "R"
        assert elem.requirement_level_2 == "S"
        assert elem.requirement_level_3 == "S"
        assert elem.requirement_level_4 == "*"
        assert elem.requirement_level_5 == "R"
        assert elem.artifact_ref is None
        assert elem.document_reference is None
        assert elem.notes is None
        assert elem.comments is None
        assert elem.dated is None
        assert elem.present is None
        assert elem.applicability_verdict is None
        assert elem.validation_status == "valid"
        assert elem.findings == []

    def test_init_integer_element_id_conversion(self) -> None:
        """Integer element IDs 1–18 convert to canonical element IDs."""
        elem1 = PPAPCanvasElement(element_id=1)
        assert elem1.element_id == "2.2.1"
        elem18 = PPAPCanvasElement(element_id=18)
        assert elem18.element_id == "2.2.18"

    def test_init_integer_element_id_out_of_range(self) -> None:
        """Integer element IDs outside 1–18 raise ValueError."""
        with pytest.raises(ValueError, match="Invalid element_id number"):
            PPAPCanvasElement(element_id=0)
        with pytest.raises(ValueError, match="Invalid element_id number"):
            PPAPCanvasElement(element_id=19)

    def test_init_string_aliases_conversion(self) -> None:
        """String aliases normalize to canonical element IDs."""
        aliases = [
            ("dfmea", "2.2.4"),
            ("pfmea", "2.2.6"),
            ("control plan", "2.2.7"),
            ("msa", "2.2.8"),
            ("spc", "2.2.11"),
            ("psw", "2.2.18"),
        ]
        for alias, expected_id in aliases:
            elem = PPAPCanvasElement(element_id=alias)
            assert elem.element_id == expected_id

    def test_init_invalid_element_id_types_and_values(self) -> None:
        """Invalid element_id types and unmapped strings raise TypeError or ValueError."""
        with pytest.raises(TypeError, match="element_id cannot be a boolean"):
            PPAPCanvasElement(element_id=True)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="element_id must be a string or integer"):
            PPAPCanvasElement(element_id=3.14)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Invalid element_id: 'unknown_elem'"):
            PPAPCanvasElement(element_id="unknown_elem")

    def test_init_element_name_handling(self) -> None:
        """Explicit name is preserved; non-string raises TypeError."""
        elem = PPAPCanvasElement(element_id="2.2.1", element_name="Custom Drawing Spec")
        assert elem.element_name == "Custom Drawing Spec"
        with pytest.raises(TypeError, match="element_name must be a string"):
            PPAPCanvasElement(element_id="2.2.1", element_name=12345)  # type: ignore[arg-type]

    def test_init_status_normalization_and_validation(self) -> None:
        """Status aliases and valid values are normalized; invalid raise ValueError/TypeError."""
        elem_alias = PPAPCanvasElement(element_id="2.2.1", status="submit")
        assert elem_alias.status == "submitted"
        elem_na = PPAPCanvasElement(element_id="2.2.13", status="N/A")
        assert elem_na.status == "not_applicable"

        with pytest.raises(TypeError, match="status must be a string"):
            PPAPCanvasElement(element_id="2.2.1", status=123)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Invalid status 'invalid_status'"):
            PPAPCanvasElement(element_id="2.2.1", status="invalid_status")

    def test_init_matrix_requirements_explicit_vs_default(self) -> None:
        """Explicit requirement codes are preserved; missing/invalid are loaded from Table 4.1."""
        elem = PPAPCanvasElement(
            element_id="2.2.1",
            requirement_level_1="S",
            requirement_level_2=None,  # type: ignore[arg-type]
            requirement_level_3="INVALID",  # type: ignore[arg-type]
        )
        assert elem.requirement_level_1 == "S"
        assert elem.requirement_level_2 == "S"  # Table 4.1 matrix default for 2.2.1 Level 2
        assert elem.requirement_level_3 == "S"  # Table 4.1 matrix default for 2.2.1 Level 3

    def test_init_artifact_ref_and_document_reference_syncing(self) -> None:
        """artifact_ref and document_reference sync bi-directionally."""
        e1 = PPAPCanvasElement(element_id="2.2.1", artifact_ref="  DWG-001.pdf  ")
        assert e1.artifact_ref == "DWG-001.pdf"
        assert e1.document_reference == "DWG-001.pdf"

        e2 = PPAPCanvasElement(element_id="2.2.1", document_reference="  SPEC-002.pdf  ")
        assert e2.artifact_ref == "SPEC-002.pdf"
        assert e2.document_reference == "SPEC-002.pdf"

        e3 = PPAPCanvasElement(element_id="2.2.1", artifact_ref="A.pdf", document_reference="B.pdf")
        assert e3.artifact_ref == "A.pdf"
        assert e3.document_reference == "B.pdf"

        e4 = PPAPCanvasElement(element_id="2.2.1", artifact_ref="   ", document_reference="   ")
        assert e4.artifact_ref is None
        assert e4.document_reference is None

        with pytest.raises(TypeError, match="artifact_ref must be a string or None"):
            PPAPCanvasElement(element_id="2.2.1", artifact_ref=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="document_reference must be a string or None"):
            PPAPCanvasElement(element_id="2.2.1", document_reference=123)  # type: ignore[arg-type]

    def test_init_notes_and_comments_syncing(self) -> None:
        """notes and comments sync bi-directionally."""
        e1 = PPAPCanvasElement(element_id="2.2.1", notes="  Note text  ")
        assert e1.notes == "Note text"
        assert e1.comments == "Note text"

        e2 = PPAPCanvasElement(element_id="2.2.1", comments="  Comment text  ")
        assert e2.notes == "Comment text"
        assert e2.comments == "Comment text"

        e3 = PPAPCanvasElement(element_id="2.2.1", notes="Note", comments="Comment")
        assert e3.notes == "Note"
        assert e3.comments == "Comment"

        e4 = PPAPCanvasElement(element_id="2.2.1", notes="   ", comments="   ")
        assert e4.notes is None
        assert e4.comments is None

        with pytest.raises(TypeError, match="notes must be a string or None"):
            PPAPCanvasElement(element_id="2.2.1", notes=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="comments must be a string or None"):
            PPAPCanvasElement(element_id="2.2.1", comments=123)  # type: ignore[arg-type]

    def test_init_dated_present_verdict_validation(self) -> None:
        """Dated, present, applicability verdict, and validation status enforce types."""
        elem = PPAPCanvasElement(
            element_id="2.2.1",
            dated="  2026-08-20  ",
            present=True,
            applicability_verdict="  APPLICABLE  ",
            validation_status="  warning  ",
            findings=["Issue 1", 2],  # type: ignore[list-item]
        )
        assert elem.dated == "2026-08-20"
        assert elem.present is True
        assert elem.applicability_verdict == "APPLICABLE"
        assert elem.validation_status == "warning"
        assert elem.findings == ["Issue 1", "2"]

        with pytest.raises(TypeError, match="dated must be a string or None"):
            PPAPCanvasElement(element_id="2.2.1", dated=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="present must be a boolean or None"):
            PPAPCanvasElement(element_id="2.2.1", present="true")  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="applicability_verdict must be a string or None"):
            PPAPCanvasElement(element_id="2.2.1", applicability_verdict=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="validation_status must be a string"):
            PPAPCanvasElement(element_id="2.2.1", validation_status=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="findings must be a list"):
            PPAPCanvasElement(element_id="2.2.1", findings="finding")  # type: ignore[arg-type]

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        """to_dict and from_dict serialize and deserialize accurately."""
        elem = PPAPCanvasElement(
            element_id="2.2.6",
            element_name="Process FMEA",
            status="submitted",
            artifact_ref="PFMEA-001.xlsx",
            notes="Completed AIAG-VDA PFMEA",
            dated="2026-08-15",
            present=True,
            findings=["No issues found"],
        )
        d = elem.to_dict()
        assert d["element_id"] == "2.2.6"
        assert d["status"] == "submitted"
        assert d["findings"] == ["No issues found"]

        loaded = PPAPCanvasElement.from_dict(d)
        assert loaded.element_id == elem.element_id
        assert loaded.status == elem.status
        assert loaded.artifact_ref == elem.artifact_ref
        assert loaded.notes == elem.notes
        assert loaded.findings == elem.findings

    def test_from_dict_pascal_case_and_aliases(self) -> None:
        """from_dict supports PascalCase and alias keys."""
        data = {
            "Element_ID": "2.2.7",
            "Element_Name": "Control Plan",
            "Status": "Submitted",
            "Requirement_Level_1": "R",
            "Requirement_Level_2": "R",
            "Requirement_Level_3": "S",
            "Requirement_Level_4": "*",
            "Requirement_Level_5": "R",
            "Document_Reference": "CP-001.xlsx",
            "Comments": "Pre-launch CP",
            "Dated": "2026-08-16",
            "Present": True,
            "Applicability_Verdict": "APPLICABLE",
            "Validation_Status": "valid",
            "Findings": ["Linked to PFMEA"],
        }
        elem = PPAPCanvasElement.from_dict(data)
        assert elem.element_id == "2.2.7"
        assert elem.element_name == "Control Plan"
        assert elem.status == "submitted"
        assert elem.artifact_ref == "CP-001.xlsx"
        assert elem.comments == "Pre-launch CP"
        assert elem.findings == ["Linked to PFMEA"]

    def test_from_dict_id_aliases_and_errors(self) -> None:
        """from_dict handles 'id'/'ID' aliases and validates input."""
        elem_id = PPAPCanvasElement.from_dict({"id": "2.2.4"})
        assert elem_id.element_id == "2.2.4"

        elem_cap_id = PPAPCanvasElement.from_dict({"ID": "2.2.5"})
        assert elem_cap_id.element_id == "2.2.5"

        with pytest.raises(TypeError, match="data must be a dictionary"):
            PPAPCanvasElement.from_dict("not_a_dict")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Missing required field 'element_id' or 'id'"):
            PPAPCanvasElement.from_dict({"notes": "missing id"})

    def test_from_dict_all_statuses(self) -> None:
        """from_dict handles all valid and alias status values."""
        for st in ("submitted", "retained", "missing", "not_applicable", "undecided", "submit", "retain", "na"):
            elem = PPAPCanvasElement.from_dict({"element_id": "2.2.1", "status": st})
            assert elem.status in ("submitted", "retained", "missing", "not_applicable", "undecided")


# ===========================================================================
# 2. PPAPCanvas Instantiation & Properties Tests
# ===========================================================================


class TestPPAPCanvasInstantiationAndProperties:
    """Test suite for PPAPCanvas controller initialization and properties."""

    def test_default_instantiation(self) -> None:
        """PPAPCanvas initializes with defaults and 18 canonical elements."""
        canvas = PPAPCanvas()
        assert canvas.title == "AIAG PPAP 4th Edition Checklist Canvas"
        assert canvas.part_name == "Sample Part"
        assert canvas.part_number == "PART-001"
        assert canvas.submission_level == 3
        assert canvas.reason_for_submission == "Initial Submission"
        assert canvas.organization is None
        assert canvas.supplier_name is None
        assert canvas.supplier_code is None
        assert canvas.customer is None
        assert canvas.customer_name is None
        assert canvas.application is None
        assert canvas.has_design_responsibility is True
        assert canvas.designated_appearance_item is False
        assert canvas.appearance_item is False
        assert canvas.has_checking_aid is True
        assert len(canvas.elements) == 18
        assert len(canvas.rows) == 18

    def test_constructor_type_guards(self) -> None:
        """Paranoid type guards on PPAPCanvas constructor parameters."""
        with pytest.raises(TypeError, match="title must be a non-empty string"):
            PPAPCanvas(title=True)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="title must be a non-empty string"):
            PPAPCanvas(title="")
        with pytest.raises(TypeError, match="description must be a non-empty string"):
            PPAPCanvas(description=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="part_name must be a non-empty string"):
            PPAPCanvas(part_name="   ")
        with pytest.raises(TypeError, match="part_number must be a non-empty string"):
            PPAPCanvas(part_number=False)  # type: ignore[arg-type]

        # Submission level guards
        with pytest.raises(TypeError, match="submission_level cannot be a boolean"):
            PPAPCanvas(submission_level=True)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="submission_level must be an integer 1–5"):
            PPAPCanvas(submission_level=6)
        with pytest.raises(ValueError, match="submission_level must be an integer 1–5"):
            PPAPCanvas(submission_level=0)
        with pytest.raises(ValueError, match="Invalid submission_level"):
            PPAPCanvas(submission_level="Level 99")
        with pytest.raises(TypeError, match="submission_level must be an integer or string"):
            PPAPCanvas(submission_level=3.14)  # type: ignore[arg-type]

        # Reason for submission guards
        with pytest.raises(TypeError, match="reason_for_submission must be a string"):
            PPAPCanvas(reason_for_submission=True)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Invalid reason_for_submission"):
            PPAPCanvas(reason_for_submission="Invalid Reason")
        c_rsn1 = PPAPCanvas(reason_for_submission="Initial Submission")
        assert c_rsn1.reason_for_submission == "Initial Submission"
        c_rsn2 = PPAPCanvas(reason_for_submission="initial submission")
        assert c_rsn2.reason_for_submission == "Initial Submission"
        c_rsn3 = PPAPCanvas(reason_for_submission="INITIAL_SUBMISSION")
        assert c_rsn3.reason_for_submission == "Initial Submission"

        c_lvl_str = PPAPCanvas(submission_level="Level 3")
        assert c_lvl_str.submission_level == 3

        c_blanks = PPAPCanvas(supplier_code="   ", application="   ")
        assert c_blanks.supplier_code is None
        assert c_blanks.application is None

        # Organization & customer guards
        with pytest.raises(TypeError, match="organization / supplier_name must be a string or None"):
            PPAPCanvas(organization=True)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="organization / supplier_name must be a string or None"):
            PPAPCanvas(organization=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="organization / supplier_name must be a string or None"):
            PPAPCanvas(supplier_name=True)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="organization / supplier_name must be a string or None"):
            PPAPCanvas(supplier_name=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="supplier_code must be a string or None"):
            PPAPCanvas(supplier_code=True)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="supplier_code must be a string or None"):
            PPAPCanvas(supplier_code=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="customer / customer_name must be a string or None"):
            PPAPCanvas(customer=False)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="customer / customer_name must be a string or None"):
            PPAPCanvas(customer=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="customer / customer_name must be a string or None"):
            PPAPCanvas(customer_name=True)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="customer / customer_name must be a string or None"):
            PPAPCanvas(customer_name=123)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="application must be a string or None"):
            PPAPCanvas(application=True)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="application must be a string or None"):
            PPAPCanvas(application=123)  # type: ignore[arg-type]

        # Boolean flags guards
        with pytest.raises(TypeError, match="has_design_responsibility must be a boolean"):
            PPAPCanvas(has_design_responsibility="yes")  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="designated_appearance_item must be a boolean"):
            PPAPCanvas(designated_appearance_item="no")  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="has_checking_aid must be a boolean"):
            PPAPCanvas(has_checking_aid=1)  # type: ignore[arg-type]

    def test_property_setters_and_validation(self) -> None:
        """Property setters validate inputs and update state correctly."""
        canvas = PPAPCanvas()

        canvas.title = "Updated Title"
        assert canvas.title == "Updated Title"
        with pytest.raises(TypeError):
            canvas.title = "   "

        canvas.description = "Updated Description"
        assert canvas.description == "Updated Description"
        with pytest.raises(TypeError):
            canvas.description = True  # type: ignore[assignment]

        canvas.part_name = "Shaft"
        assert canvas.part_name == "Shaft"
        with pytest.raises(TypeError):
            canvas.part_name = ""

        canvas.part_number = "SH-100"
        assert canvas.part_number == "SH-100"
        with pytest.raises(TypeError):
            canvas.part_number = 123  # type: ignore[assignment]

        # Submission level setter
        canvas.submission_level = 2
        assert canvas.submission_level == 2
        canvas.submission_level = "Level 4"
        assert canvas.submission_level == 4
        with pytest.raises(TypeError):
            canvas.submission_level = True  # type: ignore[assignment]
        with pytest.raises(ValueError):
            canvas.submission_level = 0
        with pytest.raises(ValueError):
            canvas.submission_level = "Level 99"
        with pytest.raises(TypeError):
            canvas.submission_level = 3.5  # type: ignore[assignment]

        # Reason for submission setter
        canvas.reason_for_submission = "Engineering Change(s)"
        assert canvas.reason_for_submission == "Engineering Change(s)"
        canvas.reason_for_submission = "tooling_change"
        assert canvas.reason_for_submission == "Tooling: Transfer, Replacement, Refurbishment, or additional"
        with pytest.raises(TypeError):
            canvas.reason_for_submission = 123  # type: ignore[assignment]
        with pytest.raises(ValueError):
            canvas.reason_for_submission = "bogus_reason"

        # Organization & Supplier setter
        canvas.organization = "Acme Corp"
        assert canvas.organization == "Acme Corp"
        assert canvas.supplier_name == "Acme Corp"
        canvas.supplier_name = "Beta Corp"
        assert canvas.organization == "Beta Corp"
        assert canvas.supplier_name == "Beta Corp"
        canvas.organization = None
        assert canvas.organization is None
        assert canvas.supplier_name is None
        with pytest.raises(TypeError):
            canvas.organization = True  # type: ignore[assignment]

        # Supplier code setter
        canvas.supplier_code = "SUP-99"
        assert canvas.supplier_code == "SUP-99"
        canvas.supplier_code = None
        assert canvas.supplier_code is None
        with pytest.raises(TypeError):
            canvas.supplier_code = 123  # type: ignore[assignment]

        # Customer & Customer Name setter
        canvas.customer = "OEM Corp"
        assert canvas.customer == "OEM Corp"
        assert canvas.customer_name == "OEM Corp"
        canvas.customer_name = "Auto OEM"
        assert canvas.customer == "Auto OEM"
        assert canvas.customer_name == "Auto OEM"
        canvas.customer = None
        assert canvas.customer is None
        assert canvas.customer_name is None
        with pytest.raises(TypeError):
            canvas.customer = True  # type: ignore[assignment]

        # Application setter
        canvas.application = "Transmission Gearbox"
        assert canvas.application == "Transmission Gearbox"
        canvas.application = None
        assert canvas.application is None
        with pytest.raises(TypeError):
            canvas.application = 123  # type: ignore[assignment]

        # Boolean flags
        canvas.has_design_responsibility = False
        assert canvas.has_design_responsibility is False
        with pytest.raises(TypeError):
            canvas.has_design_responsibility = "false"  # type: ignore[assignment]

        canvas.designated_appearance_item = True
        assert canvas.designated_appearance_item is True
        assert canvas.appearance_item is True
        canvas.appearance_item = False
        assert canvas.designated_appearance_item is False
        with pytest.raises(TypeError):
            canvas.designated_appearance_item = 1  # type: ignore[assignment]
        with pytest.raises(TypeError):
            canvas.appearance_item = "no"  # type: ignore[assignment]

        canvas.has_checking_aid = False
        assert canvas.has_checking_aid is False
        with pytest.raises(TypeError):
            canvas.has_checking_aid = None  # type: ignore[assignment]


# ===========================================================================
# 3. Benchmark Datasets & Factories Tests
# ===========================================================================


class TestPPAPCanvasBenchmarkDataAndFactories:
    """Test benchmark automotive datasets and loader factory methods."""

    def test_sample_elements_dataset(self) -> None:
        """SAMPLE_PPAP_ELEMENTS contains all 18 canonical elements with metadata."""
        assert len(SAMPLE_PPAP_ELEMENTS) == 18
        elem_ids = [e["element_id"] for e in SAMPLE_PPAP_ELEMENTS]
        assert elem_ids == list(PPAP_ELEMENT_IDS)
        for elem in SAMPLE_PPAP_ELEMENTS:
            assert elem["status"] in ("submitted", "retained", "not_applicable")

    def test_sample_package_dataset(self) -> None:
        """SAMPLE_PPAP_PACKAGE conforms to PPAPPackage structure."""
        assert SAMPLE_PPAP_PACKAGE["part_name"] == "Transmission Output Shaft"
        assert SAMPLE_PPAP_PACKAGE["submission_level"] == 3
        assert len(SAMPLE_PPAP_PACKAGE["elements"]) == 18

    def test_load_sample_factory(self) -> None:
        """load_sample and load_sample_ppap_canvas instantiate Level 3 canvas."""
        c1 = PPAPCanvas.load_sample()
        assert c1.part_name == "Transmission Output Shaft"
        assert c1.submission_level == 3
        assert len(c1.elements) == 18

        c2 = load_sample_ppap_canvas()
        assert c2.part_number == "PART-SFT-4410"
        assert len(c2.rows) == 18

    def test_load_sample_extra_and_override_kwargs(self) -> None:
        """load_sample forwards package overrides and ignores non-package kwargs."""
        c = PPAPCanvas.load_sample(part_name="Custom Shaft", custom_extra_key="extra_val")
        assert c.part_name == "Custom Shaft"

    def test_from_package_factory(self) -> None:
        """from_package constructs canvas from PPAPPackage model and dictionary."""
        pkg_dict = dict(SAMPLE_PPAP_PACKAGE)
        c_dict = PPAPCanvas.from_package(pkg_dict)
        assert c_dict.part_name == "Transmission Output Shaft"

        pkg_obj = c_dict.to_package()
        assert isinstance(pkg_obj, PPAPPackage)
        c_obj = PPAPCanvas.from_package(pkg_obj)
        assert c_obj.part_number == pkg_obj.part_number
        assert len(c_obj.elements) == 18

    def test_constructor_with_invalid_elements_type(self) -> None:
        """Passing non-list, non-package to elements raises TypeError."""
        with pytest.raises(TypeError, match="elements must be a list"):
            PPAPCanvas(elements="invalid_elements")  # type: ignore[arg-type]


# ===========================================================================
# 4. Single-Writer CRUD Operations Tests
# ===========================================================================


class TestPPAPCanvasCRUD:
    """Test single-writer CRUD operations and element lookup resolution."""

    def test_resolve_element_id(self) -> None:
        """_resolve_element_id resolves ints, canonical strings, aliases, and digit strings."""
        canvas = PPAPCanvas()
        assert canvas._resolve_element_id(1) == "2.2.1"
        assert canvas._resolve_element_id(18) == "2.2.18"
        assert canvas._resolve_element_id(0) is None
        assert canvas._resolve_element_id(19) is None
        assert canvas._resolve_element_id("2.2.4") == "2.2.4"
        assert canvas._resolve_element_id("  2.2.6  ") == "2.2.6"
        assert canvas._resolve_element_id("dfmea") == "2.2.4"
        assert canvas._resolve_element_id("control plan") == "2.2.7"
        assert canvas._resolve_element_id("1") == "2.2.1"
        assert canvas._resolve_element_id("18") == "2.2.18"
        assert canvas._resolve_element_id("99") is None
        assert canvas._resolve_element_id("unknown") is None
        assert canvas._resolve_element_id(True) is None  # type: ignore[arg-type]
        assert canvas._resolve_element_id(3.14) is None  # type: ignore[arg-type]

    def test_get_element_and_get_row(self) -> None:
        """get_element and get_row retrieve elements or return None."""
        canvas = load_sample_ppap_canvas()
        assert canvas.get_element("2.2.4") is not None
        assert canvas.get_element("dfmea") is not None
        assert canvas.get_element(4) is not None
        assert canvas.get_element("4") is not None
        assert canvas.get_row("2.2.7") is not None
        assert canvas.get_element("99") is None
        assert canvas.get_element("invalid_id") is None

    def test_add_element_and_add_row(self) -> None:
        """add_element and add_row support dict, EvidenceItem, and PPAPCanvasElement."""
        canvas = PPAPCanvas(elements=[])  # Empty initially before 18-element backfill

        # Remove an element to test re-adding
        canvas.delete_element("2.2.1")
        assert canvas.get_element("2.2.1") is None

        # Add via dict
        elem_dict = {"element_id": "2.2.1", "status": "submitted", "artifact_ref": "DWG.pdf"}
        added1 = canvas.add_element(elem_dict)
        assert isinstance(added1, PPAPCanvasElement)
        assert added1.element_id == "2.2.1"
        assert added1.status == "submitted"

        # Duplicate ID raises ValueError
        with pytest.raises(ValueError, match="Element with ID '2.2.1' already exists"):
            canvas.add_element(elem_dict)

        # Add via EvidenceItem
        canvas.delete_element("2.2.2")
        ev_item = EvidenceItem(element_id="2.2.2", status="submitted", artifact_ref="ECN.pdf")
        added2 = canvas.add_element(ev_item)
        assert added2.element_id == "2.2.2"

        # Add via PPAPCanvasElement
        canvas.delete_element("2.2.3")
        c_elem = PPAPCanvasElement(element_id="2.2.3", status="submitted")
        added3 = canvas.add_row(c_elem)
        assert added3.element_id == "2.2.3"

        # Invalid type raises TypeError
        with pytest.raises(TypeError, match="element must be a PPAPCanvasElement, EvidenceItem, or dict"):
            canvas.add_element("invalid_type")  # type: ignore[arg-type]

    def test_update_element_and_edit_row(self) -> None:
        """update_element and edit_row update attributes and validate state."""
        canvas = load_sample_ppap_canvas()

        updated = canvas.update_element(
            "2.2.1",
            status="retained",
            artifact_ref="DWG-NEW.pdf",
            notes="Updated note",
        )
        assert updated.status == "retained"
        assert updated.artifact_ref == "DWG-NEW.pdf"
        assert updated.document_reference == "DWG-NEW.pdf"
        assert updated.notes == "Updated note"
        assert updated.comments == "Updated note"

        # Alias edit_row with PascalCase
        updated2 = canvas.edit_row("2.2.2", Status="retained", Comments="New comment")
        assert updated2.status == "retained"
        assert updated2.comments == "New comment"

        # Solo document_reference and comments updates keep artifact_ref and notes in sync
        u_doc = canvas.update_element("2.2.1", document_reference="SOLO_DOC.pdf")
        assert u_doc.artifact_ref == "SOLO_DOC.pdf"
        u_comm = canvas.update_element("2.2.1", comments="SOLO_COMM")
        assert u_comm.notes == "SOLO_COMM"

        # Non-existent element raises KeyError
        with pytest.raises(KeyError, match="Element with identifier '99' not found"):
            canvas.update_element(99, status="submitted")

        # Unknown field raises ValueError
        with pytest.raises(ValueError, match="Unknown field 'invalid_field'"):
            canvas.update_element("2.2.1", invalid_field="val")

    def test_update_element_id_change(self) -> None:
        """Changing element_id to an unused ID succeeds; changing to existing raises ValueError."""
        canvas = PPAPCanvas()
        canvas.delete_element("2.2.1")  # Make 2.2.1 unused

        # Change 2.2.2 to 2.2.1
        updated = canvas.update_element("2.2.2", element_id="2.2.1")
        assert updated.element_id == "2.2.1"
        assert canvas.get_element("2.2.2") is None
        assert canvas.get_element("2.2.1") is not None

        # Attempt to change 2.2.3 to 2.2.1 (which now exists)
        with pytest.raises(ValueError, match="Cannot change element ID to '2.2.1': ID already exists"):
            canvas.update_element("2.2.3", element_id="2.2.1")

    def test_delete_element_and_delete_row(self) -> None:
        """delete_element and delete_row pop element from canvas; invalid raises KeyError."""
        canvas = load_sample_ppap_canvas()
        deleted = canvas.delete_element("2.2.1")
        assert deleted.element_id == "2.2.1"
        assert canvas.get_element("2.2.1") is None

        deleted2 = canvas.delete_row("2.2.2")
        assert deleted2.element_id == "2.2.2"
        assert canvas.get_element("2.2.2") is None

        with pytest.raises(KeyError, match="Element with identifier '2.2.1' not found"):
            canvas.delete_element("2.2.1")


# ===========================================================================
# 5. Domain Interoperability & Audit Synchronization Tests
# ===========================================================================


class TestPPAPCanvasDomainInteroperabilityAndAudit:
    """Test to_package conversion and sync_audit execution."""

    def test_to_package(self) -> None:
        """to_package produces a valid PPAPPackage with all elements."""
        canvas = load_sample_ppap_canvas()
        pkg = canvas.to_package()
        assert isinstance(pkg, PPAPPackage)
        assert pkg.part_name == canvas.part_name
        assert pkg.submission_level == canvas.submission_level
        assert len(pkg.elements) == 18

    def test_sync_audit_all_verdicts(self) -> None:
        """sync_audit evaluates applicability and validates all requirement codes (S, R, *)."""
        canvas = load_sample_ppap_canvas()

        # Set diverse statuses to hit all audit rule branches
        # Requirement 'S' element (e.g. 2.2.1 Design Records at Level 3)
        canvas.update_element("2.2.1", status="submitted")
        # Conditionally exempt N/A element (2.2.13 AAR without appearance item)
        canvas.update_element("2.2.13", status="not_applicable")
        # Missing S element
        canvas.update_element("2.2.5", status="missing")
        # Undecided S element
        canvas.update_element("2.2.6", status="undecided")
        # Retained S element (warning)
        canvas.update_element("2.2.7", status="retained")

        # Requirement 'R' element (e.g. 2.2.16 Checking Aids at Level 3)
        canvas.update_element("2.2.16", status="retained")
        # Missing R element (2.2.15 Master Sample)
        canvas.update_element("2.2.15", status="missing")
        # Undecided R element (2.2.17 CSR)
        canvas.update_element("2.2.17", status="undecided")

        summary = canvas.sync_audit()
        assert isinstance(summary, dict)

        e1 = canvas.get_element("2.2.1")
        assert e1 is not None and e1.validation_status == "valid" and e1.findings == []

        e13 = canvas.get_element("2.2.13")
        assert e13 is not None and e13.validation_status == "valid"
        assert len(e13.findings) == 1 and "Conditionally exempt" in e13.findings[0]

        e5 = canvas.get_element("2.2.5")
        assert e5 is not None and e5.validation_status == "missing"
        assert len(e5.findings) == 1 and "is missing" in e5.findings[0]

        e6 = canvas.get_element("2.2.6")
        assert e6 is not None and e6.validation_status == "undecided"
        assert len(e6.findings) == 1 and "is undecided" in e6.findings[0]

        e7 = canvas.get_element("2.2.7")
        assert e7 is not None and e7.validation_status == "warning"
        assert len(e7.findings) == 1 and "requires submission ('S')" in e7.findings[0]

        e16 = canvas.get_element("2.2.16")
        assert e16 is not None and e16.validation_status == "valid"

        e15 = canvas.get_element("2.2.15")
        assert e15 is not None and e15.validation_status == "missing"

        e17 = canvas.get_element("2.2.17")
        assert e17 is not None and e17.validation_status == "undecided"

        # Test Level 4 requirement '*' paths
        canvas_l4 = load_sample_ppap_canvas()
        canvas_l4.submission_level = 4
        canvas_l4.update_element("2.2.1", status="retained")
        canvas_l4.update_element("2.2.2", status="missing")
        canvas_l4.update_element("2.2.3", status="undecided")
        canvas_l4.update_element("2.2.13", status="not_applicable")
        canvas_l4.sync_audit()

        assert canvas_l4.get_element("2.2.1").validation_status == "valid"  # type: ignore[union-attr]
        assert canvas_l4.get_element("2.2.2").validation_status == "missing"  # type: ignore[union-attr]
        assert canvas_l4.get_element("2.2.3").validation_status == "undecided"  # type: ignore[union-attr]
        assert canvas_l4.get_element("2.2.13").validation_status == "undecided"  # type: ignore[union-attr]

        # Test Level 4 with explicit customer requirements so 2.2.13 evaluates to NOT_APPLICABLE
        canvas_l4_cust = PPAPCanvas(
            submission_level=4,
            customer_level_4_requirements=["2.2.1", "2.2.2"],
            designated_appearance_item=False,
        )
        canvas_l4_cust.update_element("2.2.1", status="submitted")
        canvas_l4_cust.update_element("2.2.2", status="retained")
        canvas_l4_cust.update_element("2.2.13", status="not_applicable")
        canvas_l4_cust.sync_audit()
        assert canvas_l4_cust.get_element("2.2.13").validation_status == "valid"  # type: ignore[union-attr]

        # Test Level 5 requirement paths (all R except 2.2.18 S)
        canvas_l5 = load_sample_ppap_canvas()
        canvas_l5.submission_level = 5
        canvas_l5.update_element("2.2.1", status="submitted")
        canvas_l5.update_element("2.2.2", status="retained")
        canvas_l5.update_element("2.2.13", status="not_applicable")
        canvas_l5.update_element("2.2.14", status="missing")
        canvas_l5.update_element("2.2.15", status="undecided")
        canvas_l5.sync_audit()

        assert canvas_l5.get_element("2.2.1").validation_status == "valid"  # type: ignore[union-attr]
        assert canvas_l5.get_element("2.2.2").validation_status == "valid"  # type: ignore[union-attr]
        assert canvas_l5.get_element("2.2.13").validation_status == "valid"  # type: ignore[union-attr]
        assert canvas_l5.get_element("2.2.14").validation_status == "missing"  # type: ignore[union-attr]
        assert canvas_l5.get_element("2.2.15").validation_status == "undecided"  # type: ignore[union-attr]


# ===========================================================================
# 6. Summary KPI & Section 5 Customer Authority Invariant Tests
# ===========================================================================


class TestPPAPCanvasSummaryAndAuthorityInvariant:
    """Test get_summary KPI calculations and Section 5 Customer Authority Invariant."""

    def test_summary_readiness_submission_ready(self) -> None:
        """When all required elements are submitted/exempt and none missing/undecided -> SUBMISSION_READY."""
        canvas = load_sample_ppap_canvas()
        canvas.sync_audit()
        summary = canvas.get_summary()
        assert summary["submission_readiness"] == "SUBMISSION_READY"
        assert summary["status_counts"]["missing"] == 0
        assert summary["status_counts"]["undecided"] == 0
        assert summary["required_submitted_count"] >= summary["required_elements_count"]

    def test_summary_readiness_indeterminate_due_to_undecided(self) -> None:
        """When all elements are undecided -> INDETERMINATE."""
        canvas = PPAPCanvas()  # default elements are undecided
        canvas.sync_audit()
        summary = canvas.get_summary()
        assert summary["submission_readiness"] == "INDETERMINATE"

    def test_summary_readiness_not_ready_due_to_missing(self) -> None:
        """When any element is missing -> NOT_READY."""
        canvas = load_sample_ppap_canvas()
        canvas.update_element("2.2.1", status="missing")
        summary = canvas.get_summary()
        assert summary["submission_readiness"] == "NOT_READY"

    def test_summary_readiness_not_ready_due_to_unsubmitted_required(self) -> None:
        """When a required element is marked retained -> NOT_READY."""
        canvas = load_sample_ppap_canvas()
        canvas.update_element("2.2.1", status="retained")
        summary = canvas.get_summary()
        assert summary["submission_readiness"] == "NOT_READY"

    def test_summary_readiness_indeterminate(self) -> None:
        """When undecided elements are present and none missing -> INDETERMINATE."""
        canvas = PPAPCanvas()  # Fresh canvas has all elements undecided
        summary = canvas.get_summary()
        assert summary["submission_readiness"] == "INDETERMINATE"
        assert summary["status_counts"]["undecided"] == 18

    def test_summary_deleted_required_element(self) -> None:
        """When a required element is deleted from canvas -> missing count increments -> NOT_READY."""
        canvas = load_sample_ppap_canvas()
        canvas.delete_element("2.2.1")
        summary = canvas.get_summary()
        assert summary["required_missing_count"] >= 1
        assert summary["submission_readiness"] == "NOT_READY"

    def test_section_5_customer_authority_invariant_negative_control(self) -> None:
        """Section 5 Invariant: Supplier canvas MUST NOT emit customer approval dispositions."""
        canvas = load_sample_ppap_canvas()
        summary = canvas.get_summary()

        forbidden_customer_verdicts = ["Approved", "Interim Approval", "Rejected", "APPROVED", "INTERIM_APPROVAL", "REJECTED"]
        for forbidden in forbidden_customer_verdicts:
            assert summary["submission_readiness"] != forbidden
            assert forbidden not in summary.values()

        # Verify explicit authority notice is present
        assert "Customer approval dispositions" in summary["authority_notice"]
        assert "reserved exclusively for the customer's authorized representative" in summary["authority_notice"]
        assert "AIAG PPAP 4th Edition Section 5" in summary["authority_notice"]


# ===========================================================================
# 7. Themed HTML Matrix Rendering Tests
# ===========================================================================


class TestPPAPCanvasThemedHTMLRendering:
    """Test dark/light theme HTML rendering, column highlighting, and helper functions."""

    def test_theme_dark_standalone_html(self) -> None:
        """Dark theme standalone HTML generates full HTML5 document with dark palette."""
        canvas = load_sample_ppap_canvas()
        html_out = canvas.to_html(theme="dark", standalone=True)
        assert "<!DOCTYPE html>" in html_out
        assert '<html lang="en">' in html_out
        assert "AIAG PPAP 4th Ed." in html_out
        assert "Transmission Output Shaft" in html_out
        assert "SUBMISSION READY" in html_out
        assert "Table 4.1 Requirement Legend:" in html_out
        assert "Section 5 Customer Authority Invariant:" in html_out
        assert "background-color: #0e1117" in html_out or "#0e1117" in html_out

    def test_theme_light_embeddable_html(self) -> None:
        """Light theme embeddable snippet generates container div with light palette."""
        canvas = load_sample_ppap_canvas()
        html_out = canvas.to_html(theme="light", standalone=False)
        assert "<!DOCTYPE html>" not in html_out
        assert '<div class="ppap-canvas-container"' in html_out
        assert "#f8fafc" in html_out or "#ffffff" in html_out

    def test_active_column_highlighting_all_levels(self) -> None:
        """Active submission level column header and cells are highlighted across Levels 1–5."""
        for lvl in (1, 2, 3, 4, 5):
            canvas = load_sample_ppap_canvas()
            canvas.submission_level = lvl
            html_out = canvas.to_html()
            assert f"Submission Level {lvl}" in html_out
            assert f"L{lvl}" in html_out

    def test_readiness_badge_rendering_all_states(self) -> None:
        """HTML renderer includes appropriate badges for all readiness states."""
        # SUBMISSION_READY
        c_ready = load_sample_ppap_canvas()
        h_ready = c_ready.to_html()
        assert "SUBMISSION READY" in h_ready

        # NOT_READY
        c_not_ready = load_sample_ppap_canvas()
        c_not_ready.update_element("2.2.1", status="missing")
        h_not_ready = c_not_ready.to_html()
        assert "NOT READY" in h_not_ready

        # INDETERMINATE
        c_indet = PPAPCanvas()
        h_indet = c_indet.to_html()
        assert "INDETERMINATE" in h_indet

    def test_status_badge_rendering_all_statuses(self) -> None:
        """HTML renderer includes distinct styling for all 5 evidence statuses."""
        canvas = load_sample_ppap_canvas()
        canvas.update_element("2.2.1", status="submitted")
        canvas.update_element("2.2.4", status="retained")
        canvas.update_element("2.2.13", status="not_applicable")
        canvas.update_element("2.2.2", status="missing")
        canvas.update_element("2.2.3", status="undecided")

        html_out = canvas.to_html()
        assert "Submitted</span>" in html_out
        assert "Retained</span>" in html_out
        assert "N/A</span>" in html_out
        assert "Missing</span>" in html_out
        assert "Undecided</span>" in html_out

    def test_to_html_invalid_parameters(self) -> None:
        """to_html validates theme and standalone parameters."""
        canvas = load_sample_ppap_canvas()
        with pytest.raises(ValueError, match="theme must be 'dark' or 'light'"):
            canvas.to_html(theme="blue")  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="standalone must be a boolean"):
            canvas.to_html(standalone="true")  # type: ignore[arg-type]

    def test_render_ppap_functional_helper(self) -> None:
        """render_ppap renders HTML from elements, package, or sample dataset."""
        # From elements list
        h_elems = render_ppap(elements=SAMPLE_PPAP_ELEMENTS, theme="dark", standalone=True)
        assert "AIAG PPAP 4th Ed." in h_elems

        # From package dict
        h_pkg = render_ppap(package=SAMPLE_PPAP_PACKAGE, theme="light", standalone=False)
        assert '<div class="ppap-canvas-container"' in h_pkg

        # From default sample
        h_sample = render_ppap(theme="dark", standalone=True, part_name="Custom Part")
        assert "Custom Part" in h_sample


# ===========================================================================
# 8. Security & XSS Prevention Tests
# ===========================================================================


class TestPPAPCanvasSecurityAndXSS:
    """Test XSS entity escaping across all user-supplied metadata and element fields."""

    def test_xss_escaping_canvas_metadata(self) -> None:
        """Malicious script tags in canvas title, description, and metadata are escaped."""
        xss_payload = "<script>alert('XSS')</script>"
        xss_img = "<img src=x onerror=alert('PWN')/>"

        canvas = PPAPCanvas(
            title=f"Canvas {xss_payload}",
            description=f"Desc {xss_img}",
            part_name=f"Part {xss_payload}",
            part_number=f"PN {xss_payload}",
            organization=f"Org {xss_payload}",
            customer=f"Cust {xss_payload}",
        )
        html_out = canvas.to_html(standalone=True)

        assert "<script>" not in html_out
        assert "<img src=x" not in html_out
        assert html.escape(xss_payload) in html_out
        assert html.escape(xss_img) in html_out

    def test_xss_escaping_element_fields(self) -> None:
        """Malicious script tags in element names, artifact refs, and notes are escaped."""
        xss_payload = "<script>alert('ELEM_XSS')</script>"
        canvas = load_sample_ppap_canvas()
        canvas.update_element(
            "2.2.1",
            element_name=f"Design {xss_payload}",
            artifact_ref=f"Doc {xss_payload}",
            notes=f"Note {xss_payload}",
        )
        html_out = canvas.to_html()

        assert "<script>alert('ELEM_XSS')</script>" not in html_out
        assert html.escape(f"Design {xss_payload}") in html_out
        assert html.escape(f"Doc {xss_payload}") in html_out
        assert html.escape(f"Note {xss_payload}") in html_out

"""
test_ppap_schema.py
Unit tests for quality_core.ppap.schema (Milestone 8, Epic 1 / Issue #99).

Verifies 100% line & branch coverage on the PPAP domain schema:
- Canonical 18-element definitions, numbering (§2.2.1–§2.2.18), names, and aliases
- Submission Levels 1–5, verbatim descriptions, and level aliases
- PSW Field 18 Reason for Submission vocabulary and aliases
- Evidence availability status, boolean present flag, and the undecided sentinel
- EvidenceItem model parsing, normalization, validation, and rejection of invalid data
- PPAPPackage model parsing, duplicate element detection, element_map, get_element,
  full_elements expansion, customer_requirement_set validation, and to_dict serialization
- PPAP_PACKAGE_SCHEMA TableSchema descriptor and column aliasing
- load_ppap_csv from path, binary buffer, and raw bytes with IngestError handling
- validate_ppap trust boundary validation across all supported data shapes and types
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import numpy as np
import pandas as pd
import pydantic
import pytest
from quality_core.ppap.schema import (
    EVIDENCE_STATUS_ALIASES,
    EVIDENCE_STATUS_VALUES,
    PPAP_ELEMENT_ALIASES,
    PPAP_ELEMENT_IDS,
    PPAP_ELEMENT_NAMES,
    PPAP_ELEMENT_NUMBERS,
    PPAP_PACKAGE_SCHEMA,
    REASON_FOR_SUBMISSION_ALIASES,
    REASON_FOR_SUBMISSION_VALUES,
    SUBMISSION_LEVEL_ALIASES,
    SUBMISSION_LEVEL_DESCRIPTIONS,
    SUBMISSION_LEVELS,
    EvidenceItem,
    IngestError,
    PPAPPackage,
    _clean_scalar,
    _normalize_csv_frame,
    load_ppap_csv,
    validate_ppap,
)

# ==============================================================================
# 1. Canonical 18 Element Definitions & Mapping
# ==============================================================================

def test_canonical_18_element_ids_count_and_order() -> None:
    assert len(PPAP_ELEMENT_IDS) == 18
    assert PPAP_ELEMENT_IDS[0] == "2.2.1"
    assert PPAP_ELEMENT_IDS[-1] == "2.2.18"
    for i, elem_id in enumerate(PPAP_ELEMENT_IDS):
        assert elem_id.startswith("2.2.")
        assert int(elem_id.split(".")[-1]) == i + 1


def test_canonical_18_element_names() -> None:
    assert len(PPAP_ELEMENT_NAMES) == 18
    assert PPAP_ELEMENT_NAMES["2.2.1"] == "Design Records"
    assert PPAP_ELEMENT_NAMES["2.2.4"] == "Design Failure Mode and Effects Analysis (Design FMEA)"
    assert PPAP_ELEMENT_NAMES["2.2.6"] == "Process Failure Mode and Effects Analysis (Process FMEA)"
    assert PPAP_ELEMENT_NAMES["2.2.7"] == "Control Plan"
    assert PPAP_ELEMENT_NAMES["2.2.8"] == "Measurement System Analysis Studies"
    assert PPAP_ELEMENT_NAMES["2.2.11"] == "Initial Process Studies"
    assert PPAP_ELEMENT_NAMES["2.2.13"] == "Appearance Approval Report (AAR)"
    assert PPAP_ELEMENT_NAMES["2.2.18"] == "Part Submission Warrant (PSW)"


def test_element_number_lookup() -> None:
    assert len(PPAP_ELEMENT_NUMBERS) == 18
    assert PPAP_ELEMENT_NUMBERS[1] == "2.2.1"
    assert PPAP_ELEMENT_NUMBERS[7] == "2.2.7"
    assert PPAP_ELEMENT_NUMBERS[18] == "2.2.18"


def test_element_aliases_coverage() -> None:
    assert PPAP_ELEMENT_ALIASES["dfmea"] == "2.2.4"
    assert PPAP_ELEMENT_ALIASES["pfmea"] == "2.2.6"
    assert PPAP_ELEMENT_ALIASES["control plan"] == "2.2.7"
    assert PPAP_ELEMENT_ALIASES["msa"] == "2.2.8"
    assert PPAP_ELEMENT_ALIASES["spc"] == "2.2.11"
    assert PPAP_ELEMENT_ALIASES["psw"] == "2.2.18"
    assert PPAP_ELEMENT_ALIASES["aar"] == "2.2.13"


def test_immutable_standards_mappings_mutation_negative_control() -> None:
    """Negative Control: Public standards mappings are immutable and reject in-place mutation."""
    with pytest.raises(TypeError):
        PPAP_ELEMENT_NAMES["2.2.1"] = "Mutated Name"  # type: ignore[index]

    with pytest.raises(TypeError):
        PPAP_ELEMENT_NUMBERS[1] = "2.2.18"  # type: ignore[index]

    with pytest.raises(TypeError):
        PPAP_ELEMENT_ALIASES["custom"] = "2.2.1"  # type: ignore[index]

    with pytest.raises(TypeError):
        SUBMISSION_LEVEL_DESCRIPTIONS[1] = "Mutated Level"  # type: ignore[index]

    with pytest.raises(TypeError):
        SUBMISSION_LEVEL_ALIASES["custom_lvl"] = 1  # type: ignore[index]

    with pytest.raises(TypeError):
        REASON_FOR_SUBMISSION_ALIASES["custom_reason"] = "Initial Submission"  # type: ignore[index]

    with pytest.raises(TypeError):
        EVIDENCE_STATUS_ALIASES["custom_status"] = "submitted"  # type: ignore[index]


# ==============================================================================
# 2. Submission Levels 1–5
# ==============================================================================

def test_submission_levels_tuple() -> None:
    assert SUBMISSION_LEVELS == (1, 2, 3, 4, 5)


def test_submission_level_descriptions() -> None:
    assert len(SUBMISSION_LEVEL_DESCRIPTIONS) == 5
    assert "Warrant only" in SUBMISSION_LEVEL_DESCRIPTIONS[1]
    assert "limited supporting data" in SUBMISSION_LEVEL_DESCRIPTIONS[2]
    assert "complete supporting data" in SUBMISSION_LEVEL_DESCRIPTIONS[3]
    assert "defined by customer" in SUBMISSION_LEVEL_DESCRIPTIONS[4]
    assert "reviewed at supplier's manufacturing location" in SUBMISSION_LEVEL_DESCRIPTIONS[5]


def test_submission_level_aliases() -> None:
    assert SUBMISSION_LEVEL_ALIASES["level 1"] == 1
    assert SUBMISSION_LEVEL_ALIASES["l3"] == 3
    assert SUBMISSION_LEVEL_ALIASES["level 4"] == 4
    assert SUBMISSION_LEVEL_ALIASES["level_5"] == 5


# ==============================================================================
# 3. Reason for Submission Vocabulary
# ==============================================================================

def test_reason_for_submission_values() -> None:
    assert len(REASON_FOR_SUBMISSION_VALUES) == 10
    assert "Initial Submission" in REASON_FOR_SUBMISSION_VALUES
    assert "Engineering Change(s)" in REASON_FOR_SUBMISSION_VALUES
    assert "Tooling: Transfer, Replacement, Refurbishment, or additional" in REASON_FOR_SUBMISSION_VALUES
    assert "Correction of Discrepancy" in REASON_FOR_SUBMISSION_VALUES
    assert "Tooling Inactive > than 1 year" in REASON_FOR_SUBMISSION_VALUES
    assert "Change to Optional Construction or Material" in REASON_FOR_SUBMISSION_VALUES
    assert "Sub-Supplier or Material Source Change" in REASON_FOR_SUBMISSION_VALUES
    assert "Change in Part Processing" in REASON_FOR_SUBMISSION_VALUES
    assert "Parts Produced at Additional Location" in REASON_FOR_SUBMISSION_VALUES
    assert "Other" in REASON_FOR_SUBMISSION_VALUES


def test_reason_for_submission_aliases() -> None:
    assert REASON_FOR_SUBMISSION_ALIASES["initial"] == "Initial Submission"
    assert REASON_FOR_SUBMISSION_ALIASES["ecn"] == "Engineering Change(s)"
    assert REASON_FOR_SUBMISSION_ALIASES["material change"] == "Change to Optional Construction or Material"
    assert REASON_FOR_SUBMISSION_ALIASES["process change"] == "Change in Part Processing"
    assert REASON_FOR_SUBMISSION_ALIASES["discrepancy"] == "Correction of Discrepancy"


# ==============================================================================
# 4. Evidence Status Vocabulary & Undecided Sentinel
# ==============================================================================

def test_evidence_status_values() -> None:
    assert EVIDENCE_STATUS_VALUES == (
        "submitted",
        "retained",
        "not_applicable",
        "missing",
        "undecided",
    )


def test_evidence_status_aliases() -> None:
    assert EVIDENCE_STATUS_ALIASES["s"] == "submitted"
    assert EVIDENCE_STATUS_ALIASES["r"] == "retained"
    assert EVIDENCE_STATUS_ALIASES["*"] == "retained"
    assert EVIDENCE_STATUS_ALIASES["na"] == "not_applicable"
    assert EVIDENCE_STATUS_ALIASES["m"] == "missing"
    assert EVIDENCE_STATUS_ALIASES["u"] == "undecided"
    assert EVIDENCE_STATUS_ALIASES["?"] == "undecided"
    assert EVIDENCE_STATUS_ALIASES[""] == "undecided"
    assert EVIDENCE_STATUS_ALIASES["tbd"] == "undecided"


# ==============================================================================
# 5. EvidenceItem Pydantic Model Tests
# ==============================================================================

def test_evidence_item_canonical_creation() -> None:
    item = EvidenceItem(
        element_id="2.2.1",
        element_name="Design Records",
        present=True,
        status="submitted",
        document_reference="DWG-1001 Rev B",
        comments="Approved by engineering",
    )
    assert item.element_id == "2.2.1"
    assert item.element_name == "Design Records"
    assert item.present is True
    assert item.status == "submitted"
    assert item.document_reference == "DWG-1001 Rev B"
    assert item.comments == "Approved by engineering"
    assert item.artifact_ref == "DWG-1001 Rev B"
    assert item.notes == "Approved by engineering"
    assert item.linked_data is None
    assert item.evidence_valid is None


def test_evidence_item_number_coercion() -> None:
    item = EvidenceItem(element_id=7, element_name="Control Plan", status="retained")
    assert item.element_id == "2.2.7"
    assert item.status == "retained"


def test_evidence_item_alias_coercion() -> None:
    item = EvidenceItem(element_id="pfmea", element_name="PFMEA", status="s")
    assert item.element_id == "2.2.6"
    assert item.status == "submitted"


def test_evidence_item_auto_populates_name_if_none_or_blank() -> None:
    item1 = EvidenceItem(element_id="2.2.8", element_name=None, status="submitted")  # type: ignore[arg-type]
    assert item1.element_name == "Measurement System Analysis Studies"

    item2 = EvidenceItem(element_id="2.2.11", element_name="   ", status="submitted")
    assert item2.element_name == "Initial Process Studies"

    item3 = EvidenceItem(element_id=5, status="submitted")
    assert item3.element_name == "Process Flow Diagrams"


def test_evidence_item_default_status_is_undecided() -> None:
    item = EvidenceItem(element_id="2.2.2", element_name="Engineering Change")
    assert item.status == "undecided"
    assert item.present is None

    item_none = EvidenceItem(element_id="2.2.2", element_name="Engineering Change", status=None)  # type: ignore[arg-type]
    assert item_none.status == "undecided"

    item_blank = EvidenceItem(element_id="2.2.2", element_name="Engineering Change", status="   ")
    assert item_blank.status == "undecided"


def test_evidence_item_optional_strings_stripped_and_blank_to_none() -> None:
    item = EvidenceItem(
        element_id="2.2.3",
        element_name="Customer Approval",
        document_reference="   ",
        comments="   ",
        artifact_ref="   ",
        notes="   ",
        dated="   ",
    )
    assert item.document_reference is None
    assert item.comments is None
    assert item.artifact_ref is None
    assert item.notes is None
    assert item.dated is None

    item_with_vals = EvidenceItem(
        element_id="2.2.3",
        element_name="Customer Approval",
        document_reference="  REF-99  ",
        comments="  Note 1  ",
        dated="  2026-08-24  ",
    )
    assert item_with_vals.document_reference == "REF-99"
    assert item_with_vals.comments == "Note 1"
    assert item_with_vals.artifact_ref == "REF-99"
    assert item_with_vals.notes == "Note 1"
    assert item_with_vals.dated == "2026-08-24"


def test_evidence_item_invalid_element_id_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="Invalid element_id"):
        EvidenceItem(element_id="99.99", element_name="Invalid Element")

    with pytest.raises(pydantic.ValidationError, match="Invalid element_id"):
        EvidenceItem(element_id=99, element_name="Invalid Element")

    with pytest.raises(pydantic.ValidationError, match="Invalid element_id"):
        EvidenceItem(element_id=object(), element_name="Invalid Element")  # type: ignore[arg-type]


def test_evidence_item_invalid_status_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="Invalid evidence status"):
        EvidenceItem(element_id="2.2.1", element_name="Design Records", status="bogus_status")

    with pytest.raises(pydantic.ValidationError, match="Invalid evidence status"):
        EvidenceItem(element_id="2.2.1", element_name="Design Records", status=123)  # type: ignore[arg-type]


def test_evidence_item_blank_name_without_valid_id_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        EvidenceItem(element_id="invalid", element_name="   ")


def test_evidence_item_model_validator_non_dict_and_edge_cases() -> None:
    res = EvidenceItem._populate_and_sync_fields("not-a-dict")
    assert res == "not-a-dict"

    dict_bad_int = {"element_id": 999, "element_name": None}
    res_bad_int = EvidenceItem._populate_and_sync_fields(dict_bad_int)
    assert res_bad_int["element_name"] is None

    # Test reverse alias sync
    item_rev = EvidenceItem(
        element_id="2.2.1",
        notes="A note",
        artifact_ref="ART-1",
    )
    assert item_rev.comments == "A note"
    assert item_rev.document_reference == "ART-1"


# ==============================================================================
# 6. PPAPPackage Model Tests
# ==============================================================================

def test_ppap_package_minimal_valid() -> None:
    pkg = PPAPPackage(
        part_name="Transmission Bracket",
        part_number="TB-4400-A",
    )
    assert pkg.part_name == "Transmission Bracket"
    assert pkg.part_number == "TB-4400-A"
    assert pkg.submission_level == 3
    assert pkg.reason_for_submission == "Initial Submission"
    assert pkg.elements == []
    assert pkg.safety_critical is False
    assert pkg.appearance_item is False
    assert pkg.has_checking_aid is False
    assert pkg.has_design_responsibility is True
    assert pkg.customer_requirement_set is None


def test_ppap_package_full_valid() -> None:
    items = [
        EvidenceItem(element_id="2.2.1", element_name="Design Records", status="submitted", present=True),
        EvidenceItem(element_id="2.2.7", element_name="Control Plan", status="retained", present=True),
    ]
    pkg = PPAPPackage(
        part_name="Transmission Bracket",
        part_number="TB-4400-A",
        submission_level=2,
        reason_for_submission="Engineering Change(s)",
        supplier_name="Acme Auto Corp",
        supplier_code="ACM-01",
        customer_name="Global Motors",
        application="Model X Powertrain",
        safety_critical=True,
        appearance_item=True,
        has_checking_aid=True,
        has_design_responsibility=False,
        elements=items,
    )
    assert pkg.submission_level == 2
    assert pkg.reason_for_submission == "Engineering Change(s)"
    assert pkg.supplier_name == "Acme Auto Corp"
    assert pkg.supplier_code == "ACM-01"
    assert pkg.customer_name == "Global Motors"
    assert pkg.application == "Model X Powertrain"
    assert pkg.safety_critical is True
    assert pkg.appearance_item is True
    assert pkg.has_checking_aid is True
    assert pkg.has_design_responsibility is False
    assert len(pkg.elements) == 2


def test_ppap_package_reject_blank_part_name_or_number() -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        PPAPPackage(part_name="   ", part_number="PART-1")

    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        PPAPPackage(part_name="Part A", part_number="   ")

    with pytest.raises(pydantic.ValidationError, match="must not be None"):
        PPAPPackage(part_name=None, part_number="PART-1")  # type: ignore[arg-type]


def test_ppap_package_submission_level_normalization() -> None:
    pkg1 = PPAPPackage(part_name="P", part_number="1", submission_level="Level 1")  # type: ignore[arg-type]
    assert pkg1.submission_level == 1

    pkg4 = PPAPPackage(part_name="P", part_number="1", submission_level="4")  # type: ignore[arg-type]
    assert pkg4.submission_level == 4

    with pytest.raises(pydantic.ValidationError, match="Invalid submission_level"):
        PPAPPackage(part_name="P", part_number="1", submission_level=6)  # type: ignore[arg-type]

    with pytest.raises(pydantic.ValidationError, match="Invalid submission_level"):
        PPAPPackage(part_name="P", part_number="1", submission_level="level 10")  # type: ignore[arg-type]

    with pytest.raises(pydantic.ValidationError, match="Invalid submission_level"):
        PPAPPackage(part_name="P", part_number="1", submission_level=object())  # type: ignore[arg-type]


def test_ppap_package_reason_for_submission_normalization() -> None:
    pkg1 = PPAPPackage(part_name="P", part_number="1", reason_for_submission="ecn")  # type: ignore[arg-type]
    assert pkg1.reason_for_submission == "Engineering Change(s)"

    pkg2 = PPAPPackage(part_name="P", part_number="1", reason_for_submission=None)  # type: ignore[arg-type]
    assert pkg2.reason_for_submission == "Initial Submission"

    pkg_blank = PPAPPackage(part_name="P", part_number="1", reason_for_submission="   ")  # type: ignore[arg-type]
    assert pkg_blank.reason_for_submission == "Initial Submission"

    pkg3 = PPAPPackage(part_name="P", part_number="1", reason_for_submission="OTHER")  # type: ignore[arg-type]
    assert pkg3.reason_for_submission == "Other"

    with pytest.raises(pydantic.ValidationError, match="Invalid reason_for_submission"):
        PPAPPackage(part_name="P", part_number="1", reason_for_submission="random unknown reason")  # type: ignore[arg-type]

    with pytest.raises(pydantic.ValidationError, match="Invalid reason_for_submission"):
        PPAPPackage(part_name="P", part_number="1", reason_for_submission=123)  # type: ignore[arg-type]


def test_ppap_package_normalize_optional_metadata() -> None:
    pkg = PPAPPackage(
        part_name="P",
        part_number="1",
        supplier_name="  Acme  ",
        supplier_code="   ",
        customer_name=None,
        application="   ",
    )
    assert pkg.supplier_name == "Acme"
    assert pkg.supplier_code is None
    assert pkg.customer_name is None
    assert pkg.application is None


def test_ppap_package_reject_duplicate_elements() -> None:
    items = [
        EvidenceItem(element_id="2.2.1", element_name="Design Records"),
        EvidenceItem(element_id="2.2.1", element_name="Design Records"),
    ]
    with pytest.raises(pydantic.ValidationError, match="duplicate element_id"):
        PPAPPackage(part_name="P", part_number="1", elements=items)


def test_ppap_package_element_map_and_get_element() -> None:
    item1 = EvidenceItem(element_id="2.2.1", element_name="Design Records", status="submitted")
    item7 = EvidenceItem(element_id="2.2.7", element_name="Control Plan", status="retained")
    pkg = PPAPPackage(part_name="P", part_number="1", elements=[item1, item7])

    assert len(pkg.element_map) == 2
    assert pkg.element_map["2.2.1"] is item1

    # Lookup by string ID
    assert pkg.get_element("2.2.1") is item1
    # Lookup by int number
    assert pkg.get_element(7) is item7
    # Lookup by alias
    assert pkg.get_element("control plan") is item7
    assert pkg.get_element("cp") is item7
    # Lookup missing or invalid element
    assert pkg.get_element("2.2.2") is None
    assert pkg.get_element(99) is None
    assert pkg.get_element("nonexistent") is None
    assert pkg.get_element(object()) is None  # type: ignore[arg-type]


def test_ppap_package_full_elements_expansion() -> None:
    item1 = EvidenceItem(element_id="2.2.1", element_name="Design Records", status="submitted", present=True)
    pkg = PPAPPackage(part_name="P", part_number="1", elements=[item1])

    full = pkg.full_elements()
    assert len(full) == 18
    assert full[0].element_id == "2.2.1"
    assert full[0].status == "submitted"
    assert full[0].present is True
    assert full[1].element_id == "2.2.2"
    assert full[1].status == "undecided"
    assert full[1].present is None
    assert full[17].element_id == "2.2.18"
    assert full[17].status == "undecided"
    assert full[17].present is None


def test_ppap_package_to_dict_serialization() -> None:
    item = EvidenceItem(
        element_id="2.2.1",
        element_name="Design Records",
        present=True,
        status="submitted",
        document_reference="DOC-1",
        comments="Note A",
    )
    pkg = PPAPPackage(part_name="Part A", part_number="PA-1", elements=[item])
    d = pkg.to_dict()

    assert d["part_name"] == "Part A"
    assert d["part_number"] == "PA-1"
    assert d["submission_level"] == 3
    assert len(d["elements"]) == 1
    assert d["elements"][0]["element_id"] == "2.2.1"
    assert d["elements"][0]["present"] is True
    assert d["elements"][0]["status"] == "submitted"
    assert d["elements"][0]["document_reference"] == "DOC-1"


# ==============================================================================
# 7. TableSchema & load_ppap_csv Tests
# ==============================================================================

def test_ppap_package_schema_structure() -> None:
    assert PPAP_PACKAGE_SCHEMA.name == "PPAP Evidence Item"
    assert PPAP_PACKAGE_SCHEMA.required_columns == ("element_id",)
    assert "present" in PPAP_PACKAGE_SCHEMA.optional_columns
    assert "status" in PPAP_PACKAGE_SCHEMA.optional_columns
    assert "document_reference" in PPAP_PACKAGE_SCHEMA.optional_columns
    assert "comments" in PPAP_PACKAGE_SCHEMA.optional_columns


def test_load_ppap_csv_from_buffer() -> None:
    csv_data = (
        "element_id,present,status,document_reference,comments\n"
        "2.2.1,true,submitted,DWG-001,Final CAD\n"
        "2.2.7,true,retained,CP-2026,Shop floor copy\n"
        "2.2.18,true,s,PSW-SIGNED,Signed by director\n"
    )
    buf = io.BytesIO(csv_data.encode("utf-8"))
    buf.name = "ppap_checklist.csv"

    pkg = load_ppap_csv(
        buf,
        part_name="Brake Disc",
        part_number="BD-100",
        submission_level=3,
        reason_for_submission="Initial Submission",
    )
    assert pkg.part_name == "Brake Disc"
    assert pkg.part_number == "BD-100"
    assert len(pkg.elements) == 3
    assert pkg.get_element("2.2.1").status == "submitted"  # type: ignore[union-attr]
    assert pkg.get_element("2.2.7").status == "retained"  # type: ignore[union-attr]
    assert pkg.get_element("2.2.18").status == "submitted"  # type: ignore[union-attr]


def test_load_ppap_csv_from_bytes() -> None:
    csv_data = (
        b"element_id,status\n"
        b"2.2.1,submitted\n"
    )
    pkg = load_ppap_csv(csv_data, part_name="Gear", part_number="G-1")
    assert pkg.part_name == "Gear"
    assert len(pkg.elements) == 1
    assert pkg.get_element("2.2.1").status == "submitted"  # type: ignore[union-attr]


def test_load_ppap_csv_from_path(tmp_path: Path) -> None:
    csv_file = tmp_path / "test_ppap.csv"
    csv_file.write_text(
        "element_id,element_name,status\n"
        "2.2.4,Design FMEA,submitted\n"
        "2.2.6,Process FMEA,submitted\n"
    )
    pkg = load_ppap_csv(str(csv_file), part_name="Engine Block", part_number="EB-99")
    assert pkg.part_name == "Engine Block"
    assert len(pkg.elements) == 2
    assert pkg.get_element("2.2.4").status == "submitted"  # type: ignore[union-attr]


def test_load_ppap_csv_with_aliases_and_missing_name() -> None:
    csv_data = (
        "item,status,doc\n"
        "1,s,CAD-1\n"
        "7,r,CP-1\n"
    )
    buf = io.BytesIO(csv_data.encode("utf-8"))
    buf.name = "checklist.csv"
    pkg = load_ppap_csv(buf)
    assert len(pkg.elements) == 2
    e1 = pkg.get_element("2.2.1")
    assert e1 is not None
    assert e1.element_name == "Design Records"
    assert e1.status == "submitted"


def test_load_ppap_csv_invalid_format_raises_ingest_error() -> None:
    bad_csv = "wrong_col_a,wrong_col_b\nval1,val2\n"
    buf = io.BytesIO(bad_csv.encode("utf-8"))
    buf.name = "bad.csv"
    with pytest.raises(IngestError):
        load_ppap_csv(buf)


def test_normalize_csv_frame_no_aliases_unchanged() -> None:
    df = pd.DataFrame({"element_id": ["2.2.1"]})
    norm = _normalize_csv_frame(df)
    assert list(norm.columns) == ["element_id"]


# ==============================================================================
# 8. validate_ppap Trust Boundary Tests
# ==============================================================================

def test_clean_scalar_helper() -> None:
    assert _clean_scalar(None) is None
    assert _clean_scalar(float("nan")) is None
    assert _clean_scalar(np.nan) is None
    assert _clean_scalar(3.14) == 3.14
    assert _clean_scalar("text") == "text"


def test_validate_ppap_with_ppap_package_instance() -> None:
    pkg = PPAPPackage(part_name="Sensor", part_number="SN-01")
    res = validate_ppap(pkg)
    assert res is pkg


def test_validate_ppap_with_dataframe() -> None:
    df = pd.DataFrame([
        {"element_id": "2.2.1", "element_name": "Design Records", "status": "submitted", "document_reference": float("nan")},
        {"element_id": "2.2.7", "element_name": "Control Plan", "status": "retained", "document_reference": None},
    ])
    pkg = validate_ppap(df)
    assert isinstance(pkg, PPAPPackage)
    assert len(pkg.elements) == 2
    assert pkg.get_element("2.2.1").status == "submitted"  # type: ignore[union-attr]
    assert pkg.get_element("2.2.1").document_reference is None  # type: ignore[union-attr]


def test_validate_ppap_with_list_of_items_and_dicts() -> None:
    items = [
        EvidenceItem(element_id="2.2.1", element_name="Design Records", status="submitted"),
        {"element_id": "2.2.7", "element_name": "Control Plan", "status": "retained", "comments": float("nan")},
    ]
    pkg = validate_ppap(items)
    assert isinstance(pkg, PPAPPackage)
    assert len(pkg.elements) == 2


def test_validate_ppap_with_dict() -> None:
    data = {
        "part_name": "Hub",
        "part_number": "HB-1",
        "submission_level": 4,
        "reason_for_submission": "Tooling Change",
        "elements": [
            {"element_id": "2.2.1", "element_name": "Design Records", "status": "submitted", "comments": None},
            EvidenceItem(element_id="2.2.18", element_name="PSW", status="submitted"),
        ],
    }
    pkg = validate_ppap(data)
    assert pkg.part_name == "Hub"
    assert pkg.submission_level == 4
    assert pkg.reason_for_submission == "Tooling: Transfer, Replacement, Refurbishment, or additional"
    assert len(pkg.elements) == 2


def test_validate_ppap_invalid_types_raise_type_error() -> None:
    with pytest.raises(TypeError, match="Expected PPAPPackage"):
        validate_ppap(12345)

    with pytest.raises(TypeError, match="Expected PPAPPackage"):
        validate_ppap("invalid string")

    with pytest.raises(TypeError, match="Expected EvidenceItem or dict in list"):
        validate_ppap([123, 456])

    with pytest.raises(TypeError, match="Expected EvidenceItem or dict in elements list"):
        validate_ppap({"part_name": "A", "part_number": "1", "elements": [123]})


# ==============================================================================
# 9. Negative Controls & Edge Cases
# ==============================================================================

def test_negative_control_duplicate_element_in_dataframe_rejected() -> None:
    df = pd.DataFrame([
        {"element_id": "2.2.1", "element_name": "Design Records", "status": "submitted"},
        {"element_id": "2.2.1", "element_name": "Design Records", "status": "retained"},
    ])
    with pytest.raises(pydantic.ValidationError, match="duplicate element_id"):
        validate_ppap(df)


def test_negative_control_unsupported_status_in_dict_rejected() -> None:
    data = {
        "part_name": "Part",
        "part_number": "P1",
        "elements": [
            {"element_id": "2.2.1", "element_name": "Design Records", "status": "INVALID_STATUS"},
        ],
    }
    with pytest.raises(pydantic.ValidationError, match="Invalid evidence status"):
        validate_ppap(data)


# ==============================================================================
# 10. Present Flag, Customer Requirement Set, and Aliases
# ==============================================================================

def test_evidence_item_present_undecided_sentinel() -> None:
    # Default is None (undecided sentinel)
    item_default = EvidenceItem(element_id="2.2.1", element_name="Design Records")
    assert item_default.present is None

    # Explicit True and False
    item_true = EvidenceItem(element_id="2.2.1", element_name="Design Records", present=True)
    assert item_true.present is True

    item_false = EvidenceItem(element_id="2.2.1", element_name="Design Records", present=False)
    assert item_false.present is False

    # Synchronized artifact_ref and notes
    item_synced = EvidenceItem(
        element_id="2.2.1",
        element_name="Design Records",
        artifact_ref="ART-101",
        notes="Engineering note",
        retained_at_organization=True,
        submitted_to_customer=False,
        dated="2026-08-24",
    )
    assert item_synced.document_reference == "ART-101"
    assert item_synced.comments == "Engineering note"
    assert item_synced.retained_at_organization is True
    assert item_synced.submitted_to_customer is False
    assert item_synced.dated == "2026-08-24"


def test_ppap_package_customer_requirement_set_level_4_allowed() -> None:
    pkg = PPAPPackage(
        part_name="Bracket",
        part_number="BR-1",
        submission_level=4,
        customer_requirement_set={"2.2.1", "2.2.18"},
    )
    assert pkg.submission_level == 4
    assert pkg.customer_requirement_set == {"2.2.1", "2.2.18"}
    d = pkg.to_dict()
    assert d["customer_requirement_set"] == ["2.2.1", "2.2.18"] or set(d["customer_requirement_set"]) == {"2.2.1", "2.2.18"}


def test_negative_control_customer_requirement_set_non_level_4_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="customer_requirement_set is only valid for Submission Level 4"):
        PPAPPackage(
            part_name="Bracket",
            part_number="BR-1",
            submission_level=3,
            customer_requirement_set={"2.2.1"},
        )

    with pytest.raises(pydantic.ValidationError, match="customer_requirement_set is only valid for Submission Level 4"):
        PPAPPackage(
            part_name="Bracket",
            part_number="BR-1",
            submission_level=1,
            customer_requirement_set={"2.2.1"},
        )


def test_ppap_package_field_synchronization_and_aliases() -> None:
    pkg = PPAPPackage(
        part_name="Shaft",
        part_number="SH-10",
        organization="Tier 1 Supplier LLC",
        customer="OEM Global",
        designated_appearance_item=True,
        bulk_material=False,
        catalog_part=False,
        black_box_part=False,
        evidence=[EvidenceItem(element_id="2.2.1", element_name="Design Records")],
    )
    assert pkg.supplier_name == "Tier 1 Supplier LLC"
    assert pkg.customer_name == "OEM Global"
    assert pkg.appearance_item is True
    assert len(pkg.elements) == 1
    assert pkg.elements[0].element_id == "2.2.1"


def test_ppap_package_sync_reverse_aliases() -> None:
    pkg1 = PPAPPackage(
        supplier_name="Acme",
        customer_name="OEM",
        appearance_item=True,
        elements=[EvidenceItem(element_id="2.2.1", element_name="Design Records")],
    )
    assert pkg1.organization == "Acme"
    assert pkg1.customer == "OEM"
    assert pkg1.designated_appearance_item is True
    assert len(pkg1.evidence) == 1

    res_non_dict = PPAPPackage._sync_package_fields("non-dict")
    assert res_non_dict == "non-dict"

# ==============================================================================
# 11. Citations & Assumptions Log Integrity
# ==============================================================================

def test_ppap_e1_assumptions_log_and_citations_manifest_integrity() -> None:
    ppap_dir = Path(__file__).resolve().parents[1] / "src" / "quality_core" / "ppap"
    manifest_path = ppap_dir / "CITATIONS.tsv"
    log_path = ppap_dir / "ASSUMPTIONS_LOG.md"

    assert manifest_path.exists(), f"CITATIONS.tsv not found at {manifest_path}"
    assert log_path.exists(), f"ASSUMPTIONS_LOG.md not found at {log_path}"

    with manifest_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    assert len(rows) >= 24
    sites = {r["site"] for r in rows}
    assert "RULE 1" in sites
    assert "RULE 2" in sites
    assert "RULE 3" in sites

    log_content = log_path.read_text(encoding="utf-8")
    assert "## RULE 1: Canonical 18 PPAP Element Vocabulary" in log_content
    assert "## RULE 2: Submission Levels 1–5 Verbatim Definitions" in log_content
    assert "## RULE 3: Part Submission Warrant (PSW) Field 18 Reason for Submission Vocabulary" in log_content

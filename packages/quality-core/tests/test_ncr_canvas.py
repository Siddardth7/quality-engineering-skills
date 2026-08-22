"""
test_ncr_canvas.py
Unit tests for single-writer NCRCanvas controller and HTML renderer in quality_core.canvas.ncr.

Tests:
- Initialization with empty records, list of dicts, NonconformanceRecord instances, and NCRDataset.
- Benchmark sample dataset loading (SAMPLE_NCR_RECORDS, load_sample_ncr_canvas).
- Single-writer CRUD lifecycle: add_record, get_record, update_record, delete_record.
- Record lookup by record_id, part_lot_id, integer index, and numeric string.
- Summary KPI metrics computation (total_records, total_quantity_affected, disposition counts, MRB count).
- Theme rendering: dark theme, light theme, standalone HTML5 document vs embeddable container.
- XSS prevention / HTML entity escaping on user strings.
- Error handling: type errors on invalid constructor inputs, KeyError on non-existent update.
- render_ncr standalone functional helper.
"""

from __future__ import annotations

import pytest
from quality_core.canvas.ncr import (
    SAMPLE_NCR_RECORDS,
    NCRCanvas,
    load_sample_ncr_canvas,
    render_ncr,
)
from quality_core.ncr.schema import NCRDataset, NonconformanceRecord


def test_ncr_canvas_init_default() -> None:
    """NCRCanvas initializes with default title and empty records list."""
    canvas = NCRCanvas()
    assert canvas.title == "Nonconformance Report (NCR) Canvas"
    assert len(canvas.records) == 0
    summary = canvas.get_summary()
    assert summary["total_records"] == 0
    assert summary["total_quantity_affected"] == 0


def test_ncr_canvas_sample_dataset_loading() -> None:
    """load_sample_ncr_canvas loads the 5 benchmark automotive NCR records."""
    canvas = load_sample_ncr_canvas()
    assert len(canvas.records) == 5
    summary = canvas.get_summary()
    assert summary["total_records"] == 5
    assert summary["total_quantity_affected"] == sum(r["quantity_affected"] for r in SAMPLE_NCR_RECORDS)
    assert summary["disposition_counts"]["Scrap"] == 1
    assert summary["disposition_counts"]["Rework"] == 1
    assert summary["disposition_counts"]["UseAsIs"] == 1
    assert summary["disposition_counts"]["ReturnToVendor"] == 1
    assert summary["disposition_counts"]["Regrade"] == 1
    assert summary["mrb_required_count"] >= 2


def test_ncr_canvas_crud_operations() -> None:
    """NCRCanvas supports full add, get, update, and delete lifecycle."""
    canvas = NCRCanvas(title="Plant A NCR Log")
    rec_dict = {
        "record_id": "NCR-100",
        "part_lot_id": "LOT-A",
        "defect_description": "Machined bore undersized",
        "requirement_violated": "Spec 20.00 +/- 0.05 mm",
        "quantity_affected": 12,
        "detection_point": "Station 2",
        "disposition": "Rework",
        "severity": "Minor",
    }
    added = canvas.add_record(rec_dict)
    assert isinstance(added, NonconformanceRecord)
    assert added.record_id == "NCR-100"
    assert len(canvas.records) == 1

    # Get by ID and index
    rec_by_id = canvas.get_record("NCR-100")
    assert rec_by_id is not None and rec_by_id.part_lot_id == "LOT-A"

    rec_by_lot = canvas.get_record("LOT-A")
    assert rec_by_lot is not None and rec_by_lot.record_id == "NCR-100"

    rec_by_idx = canvas.get_record(0)
    assert rec_by_idx is not None and rec_by_idx.record_id == "NCR-100"

    rec_by_idx_str = canvas.get_record("0")
    assert rec_by_idx_str is not None and rec_by_idx_str.record_id == "NCR-100"

    assert canvas.get_record("NON-EXISTENT") is None
    assert canvas.get_record(99) is None

    # Update record
    updated = canvas.update_record("NCR-100", disposition="Scrap", quantity_affected=15)
    assert updated.disposition == "Scrap"
    assert updated.quantity_affected == 15
    assert canvas.records[0].disposition == "Scrap"

    # Delete record
    deleted = canvas.delete_record("NCR-100")
    assert deleted is True
    assert len(canvas.records) == 0
    assert canvas.delete_record("NCR-100") is False


def test_ncr_canvas_init_with_different_types() -> None:
    """NCRCanvas accepts NonconformanceRecord instances, dict schemas, and NCRDataset in constructor."""
    rec = NonconformanceRecord(
        part_lot_id="LOT-B",
        defect_description="Crack",
        requirement_violated="Zero crack",
        quantity_affected=5,
        detection_point="Gate 1",
    )
    canvas1 = NCRCanvas(records=[rec])
    assert len(canvas1.records) == 1

    dataset = NCRDataset(records=[rec])
    canvas2 = NCRCanvas(records=dataset)
    assert len(canvas2.records) == 1

    # Pass dict structure validated via validate_ncr
    canvas3 = NCRCanvas(records={"records": [rec.model_dump()]})
    assert len(canvas3.records) == 1

    # Add NonconformanceRecord directly
    added_rec = canvas1.add_record(rec)
    assert added_rec.part_lot_id == "LOT-B"
    assert len(canvas1.records) == 2

    # String index out of bounds
    assert canvas1.get_record("999") is None


def test_ncr_canvas_html_rendering_dark_and_light() -> None:
    """NCRCanvas renders valid themed HTML in both dark and light palettes."""
    canvas = load_sample_ncr_canvas()

    dark_html = canvas.to_html(theme="dark", standalone=True)
    assert "<!DOCTYPE html>" in dark_html
    assert "NCR-2026-001" in dark_html
    assert "ReturnToVendor" in dark_html
    assert "Scrap" in dark_html

    light_html = canvas.to_html(theme="light", standalone=False)
    assert "<!DOCTYPE html>" not in light_html
    assert '<div class="ncr-canvas-container"' in light_html
    assert "NCR-2026-001" in light_html


def test_ncr_canvas_empty_state_html() -> None:
    """NCRCanvas renders empty state message when no records are present."""
    canvas = NCRCanvas()
    html_out = canvas.to_html(theme="dark", standalone=False)
    assert "No nonconformance records captured" in html_out


def test_ncr_canvas_xss_escaping() -> None:
    """NCRCanvas escapes HTML tags in defect descriptions and metadata."""
    xss_text = "<script>alert('XSS')</script>"
    canvas = NCRCanvas()
    canvas.add_record(
        {
            "record_id": xss_text,
            "part_lot_id": "LOT-XSS",
            "defect_description": xss_text,
            "requirement_violated": xss_text,
            "quantity_affected": 1,
            "detection_point": xss_text,
            "rationale": xss_text,
        }
    )
    html_out = canvas.to_html()
    assert "<script>" not in html_out
    assert "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;" in html_out


def test_ncr_canvas_type_and_key_errors() -> None:
    """NCRCanvas raises TypeError and KeyError on invalid operations."""
    with pytest.raises(TypeError, match="title must be a non-empty string"):
        NCRCanvas(title="")

    with pytest.raises(TypeError, match="title must be a non-empty string"):
        NCRCanvas(title=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Expected NonconformanceRecord or dict"):
        NCRCanvas(records=[123])  # type: ignore[list-item]

    canvas = NCRCanvas()
    with pytest.raises(TypeError, match="Expected NonconformanceRecord or dict"):
        canvas.add_record(123)  # type: ignore[arg-type]

    with pytest.raises(KeyError, match="not found"):
        canvas.update_record("UNKNOWN-ID", quantity_affected=10)


def test_render_ncr_helper() -> None:
    """render_ncr helper function properly renders HTML from canvas or list of dicts."""
    canvas = load_sample_ncr_canvas()
    html_from_canvas = render_ncr(canvas, theme="dark", standalone=True)
    assert "<!DOCTYPE html>" in html_from_canvas

    html_from_list = render_ncr(SAMPLE_NCR_RECORDS, theme="light", standalone=False)
    assert '<div class="ncr-canvas-container"' in html_from_list

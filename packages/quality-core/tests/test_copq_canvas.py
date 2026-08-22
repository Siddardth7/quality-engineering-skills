"""
test_copq_canvas.py
Unit tests and visual rendering validation for COPQCanvas.
"""

from __future__ import annotations

import pandas as pd
import pytest
from quality_core.canvas.copq import (
    SAMPLE_COPQ_ITEMS,
    COPQCanvas,
    load_sample_copq_canvas,
    render_copq,
)
from quality_core.copq.schema import COPQDataset, CostItem


def test_copq_canvas_instantiation_default() -> None:
    """Test default instantiation of COPQCanvas with no items."""
    canvas = COPQCanvas()
    assert canvas.title == "Cost of Poor Quality (COPQ) Canvas"
    assert canvas.revenue_base is None
    assert len(canvas.items) == 0

    summary = canvas.get_summary()
    assert summary["total_items"] == 0
    assert summary["total_coq"] == 0.0
    assert summary["copq"] == 0.0
    assert summary["cogq"] == 0.0
    assert summary["copq_pct_revenue"] is None
    assert summary["pareto_breakdown"] == []

    html_empty = canvas.to_html(theme="dark", standalone=False)
    assert "No Cost Items captured in canvas" in html_empty


def test_copq_canvas_instantiation_with_sample_and_helpers() -> None:
    """Test sample loader and render helper."""
    canvas = load_sample_copq_canvas(revenue_base=1000000.0)
    assert len(canvas.items) == len(SAMPLE_COPQ_ITEMS)
    assert canvas.revenue_base == 1000000.0

    summary = canvas.get_summary()
    assert summary["total_items"] == len(SAMPLE_COPQ_ITEMS)
    assert summary["copq"] > 0.0
    assert summary["cogq"] > 0.0
    assert summary["total_coq"] == summary["copq"] + summary["cogq"]
    assert summary["copq_pct_revenue"] is not None

    # Verify Pareto sorting
    pareto = summary["pareto_breakdown"]
    assert len(pareto) == len(SAMPLE_COPQ_ITEMS)
    for i in range(len(pareto) - 1):
        assert pareto[i]["cost"] >= pareto[i + 1]["cost"]
    assert pareto[-1]["cumulative_percentage"] == 100.0

    # HTML rendering
    html_dark = canvas.to_html(theme="dark", standalone=True)
    assert "<!DOCTYPE html>" in html_dark
    assert "TOTAL COPQ (FAILURE)" in html_dark
    assert "PAF Cost of Quality Distribution" in html_dark
    assert "Financial Pareto Ranking" in html_dark

    html_light = canvas.to_html(theme="light", standalone=False)
    assert "<!DOCTYPE html>" not in html_light
    assert "copq-canvas-container" in html_light


def test_copq_canvas_crud_operations() -> None:
    """Test CRUD operations on COPQCanvas."""
    canvas = COPQCanvas(title="Manufacturing Quality Canvas")

    # Add items
    item1 = canvas.add_item({"category": "Prevention", "description": "DFMEA", "direct_cost": 5000.0})
    assert isinstance(item1, CostItem)
    assert len(canvas.items) == 1

    item2 = canvas.add_item(CostItem(category="InternalFailure", description="Scrap", scrap_qty=10, unit_cost=50.0))
    assert len(canvas.items) == 2

    # Get item by description and by index
    assert canvas.get_item("DFMEA") == item1
    assert canvas.get_item(1) == item2
    assert canvas.get_item("1") == item2
    assert canvas.get_item("999") is None
    assert canvas.get_item("NonExistent") is None
    assert canvas.get_item(99) is None

    # Update item
    updated = canvas.update_item("DFMEA", direct_cost=6500.0)
    assert updated.total_cost == 6500.0
    assert canvas.get_item("DFMEA") is not None
    assert canvas.get_item("DFMEA").total_cost == 6500.0  # type: ignore[union-attr]

    # Delete item
    deleted = canvas.delete_item("DFMEA")
    assert deleted is True
    assert len(canvas.items) == 1
    assert canvas.get_item("DFMEA") is None

    # Delete non-existent item
    assert canvas.delete_item("NonExistent") is False


def test_copq_canvas_instantiation_from_dataset_and_dataframe() -> None:
    """Test initializing COPQCanvas from COPQDataset and DataFrame."""
    items = [
        CostItem(category="Prevention", description="Training", direct_cost=2000.0),
        CostItem(category="Appraisal", description="Inspection", direct_cost=3000.0),
    ]
    # Instantiate with list of CostItem instances directly
    canvas_items_list = COPQCanvas(items=items)
    assert len(canvas_items_list.items) == 2

    # Dataset without revenue_base
    ds_no_rev = COPQDataset(items=items)
    canvas_no_rev = COPQCanvas(items=ds_no_rev)
    assert canvas_no_rev.revenue_base is None

    # Dataset with revenue_base
    ds = COPQDataset(items=items, revenue_base=250000.0)
    canvas_ds = COPQCanvas(items=ds)
    assert len(canvas_ds.items) == 2
    assert canvas_ds.revenue_base == 250000.0

    df = pd.DataFrame([
        {"category": "Prevention", "description": "Training", "direct_cost": 2000.0},
    ])
    canvas_df = COPQCanvas(items=df, revenue_base=100000.0)
    assert len(canvas_df.items) == 1

    # Dict input containing revenue_base
    dict_payload = {
        "items": [{"category": "Prevention", "description": "Training", "direct_cost": 2000.0}],
        "revenue_base": 500000.0,
    }
    canvas_dict = COPQCanvas(items=dict_payload)
    assert canvas_dict.revenue_base == 500000.0


def test_render_copq_functional_helper() -> None:
    """Test render_copq helper function."""
    html_from_canvas = render_copq(load_sample_copq_canvas())
    assert "PAF Cost of Quality Distribution" in html_from_canvas

    html_from_list = render_copq(SAMPLE_COPQ_ITEMS, revenue_base=500000.0, theme="light")
    assert "PAF Cost of Quality Distribution" in html_from_list


def test_copq_canvas_xss_escaping() -> None:
    """Test that special characters and scripts are safely HTML-escaped."""
    dangerous_item = {
        "category": "Prevention",
        "description": "<script>alert('xss')</script> & Danger",
        "direct_cost": 1000.0,
    }
    canvas = COPQCanvas(
        items=[dangerous_item],
        title="<script>alert('title')</script>",
    )
    html_out = canvas.to_html()
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out
    assert "&amp; Danger" in html_out


# ---------------------------------------------------------------------------
# Negative Controls and Exception Handling
# ---------------------------------------------------------------------------

def test_negative_control_canvas_invalid_title() -> None:
    """Non-string or empty title must raise TypeError."""
    with pytest.raises(TypeError, match="title must be a non-empty string"):
        COPQCanvas(title="")
    with pytest.raises(TypeError, match="title must be a non-empty string"):
        COPQCanvas(title=None)  # type: ignore[arg-type]


def test_negative_control_canvas_invalid_revenue_base() -> None:
    """Invalid revenue_base types or negative values must raise appropriate errors."""
    with pytest.raises(TypeError, match="revenue_base must be a number or None"):
        COPQCanvas(revenue_base="500000")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="revenue_base must be a number or None"):
        COPQCanvas(revenue_base=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="revenue_base must be >= 0.0"):
        COPQCanvas(revenue_base=-500.0)


def test_negative_control_canvas_invalid_items_type() -> None:
    """Invalid items element type must raise TypeError."""
    with pytest.raises(TypeError, match="Expected CostItem or dict at index 0"):
        COPQCanvas(items=["invalid"])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="Expected CostItem or dict"):
        canvas = COPQCanvas()
        canvas.add_item("invalid")  # type: ignore[arg-type]


def test_negative_control_canvas_update_nonexistent_key() -> None:
    """Updating a non-existent item must raise KeyError."""
    canvas = COPQCanvas()
    with pytest.raises(KeyError, match="not found"):
        canvas.update_item("missing_id", direct_cost=500.0)

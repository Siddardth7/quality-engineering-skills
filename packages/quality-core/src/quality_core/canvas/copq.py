"""
copq.py
Single-writer visual canvas controller and HTML renderer for the Cost of Poor Quality (COPQ) PAF model.

Provides in-memory CRUD operations over PAF cost items, financial Pareto analysis ranking,
conformance vs failure distribution rollups, and dark/light themed HTML canvas reporting.
"""

from __future__ import annotations

import html
from typing import Any

from quality_core.copq.schema import (
    COPQDataset,
    CostItem,
    PAFCategory,
    validate_copq,
)
from quality_core.theme.palette import (
    AMBER,
    BG_CARD,
    BG_PRIMARY,
    BORDER,
    DANGER,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    VIOLET,
)

__all__ = [
    "COPQCanvas",
    "SAMPLE_COPQ_ITEMS",
    "load_sample_copq_canvas",
    "render_copq",
]

_STANDARDS_BASIS: str = "ASQ Certified Six Sigma Green Belt (CSSGB) BoK / PAF Model (Feigenbaum & Juran)"

SAMPLE_COPQ_ITEMS: list[dict[str, Any]] = [
    {
        "category": "Prevention",
        "description": "APQP Quality Planning & DFM Design Review",
        "direct_cost": 4500.0,
    },
    {
        "category": "Prevention",
        "description": "Operator Error-Proofing / Poka-Yoke Assembly Training",
        "direct_cost": 2800.0,
    },
    {
        "category": "Appraisal",
        "description": "Receiving CMM Dimensional Verification & Metallurgical Testing",
        "direct_cost": 6200.0,
    },
    {
        "category": "Appraisal",
        "description": "In-Process Automated Optical Inspection (AOI) Station Audits",
        "direct_cost": 5100.0,
    },
    {
        "category": "InternalFailure",
        "description": "Machined Bore Casting Porosity Scrap (45 pcs)",
        "scrap_qty": 45,
        "unit_cost": 120.0,
    },
    {
        "category": "InternalFailure",
        "description": "Connecting Rod Undersized Journal Rework (35 hrs labor)",
        "rework_hours": 35.0,
        "labor_rate": 65.0,
        "direct_cost": 450.0,
    },
    {
        "category": "InternalFailure",
        "description": "Plant Containment Sorting & Gauge Re-inspection (40 hrs)",
        "containment_hours": 40.0,
        "labor_rate": 45.0,
    },
    {
        "category": "ExternalFailure",
        "description": "Customer Field Warranty Claims & Replacement Assembly (12 units)",
        "warranty_units": 12,
        "warranty_unit_cost": 850.0,
    },
    {
        "category": "ExternalFailure",
        "description": "Customer Returned Defective Batch Logistics & Restocking Loss",
        "direct_cost": 3600.0,
    },
]


class COPQCanvas:
    """Single-writer controller managing an in-memory collection of PAF Cost Items.

    Provides CRUD operations, summary Pareto calculations, and theme-aligned HTML canvas rendering.
    """

    def __init__(
        self,
        items: list[CostItem] | list[dict[str, Any]] | list[Any] | COPQDataset | None = None,
        revenue_base: float | None = None,
        title: str = "Cost of Poor Quality (COPQ) Canvas",
    ) -> None:
        if not isinstance(title, str) or not title.strip():
            raise TypeError("title must be a non-empty string")
        self._title = title.strip()

        if revenue_base is not None:
            if isinstance(revenue_base, bool) or not isinstance(revenue_base, (int, float)):
                raise TypeError(f"revenue_base must be a number or None, got {type(revenue_base).__name__}")
            if float(revenue_base) < 0.0:
                raise ValueError(f"revenue_base must be >= 0.0, got {revenue_base}")
            self._revenue_base: float | None = float(revenue_base)
        else:
            self._revenue_base = None

        self._items: list[CostItem] = []

        if items is not None:
            if isinstance(items, COPQDataset):
                self._items = list(items.items)
                if self._revenue_base is None and items.revenue_base is not None:
                    self._revenue_base = items.revenue_base
            elif isinstance(items, list):
                for idx, item in enumerate(items):
                    if isinstance(item, CostItem):
                        self._items.append(item)
                    elif isinstance(item, dict):
                        self._items.append(CostItem(**item))
                    else:
                        raise TypeError(f"Expected CostItem or dict at index {idx}, got {type(item).__name__}")
            else:
                validated = validate_copq(items)
                self._items = list(validated.items)
                if self._revenue_base is None and validated.revenue_base is not None:
                    self._revenue_base = validated.revenue_base

    @property
    def title(self) -> str:
        """Canvas title."""
        return self._title

    @property
    def revenue_base(self) -> float | None:
        """Revenue base for % of sales calculations."""
        return self._revenue_base

    @property
    def items(self) -> list[CostItem]:
        """List of managed CostItem items."""
        return list(self._items)

    def add_item(self, item: CostItem | dict[str, Any]) -> CostItem:
        """Add a new CostItem to the canvas."""
        if isinstance(item, CostItem):
            cost_item = item
        elif isinstance(item, dict):
            cost_item = CostItem(**item)
        else:
            raise TypeError(f"Expected CostItem or dict, got {type(item).__name__}")

        self._items.append(cost_item)
        return cost_item

    def _find_index(self, item_id: str | int) -> int | None:
        """Find the index of an item by integer position or description match."""
        if isinstance(item_id, int):
            if 0 <= item_id < len(self._items):
                return item_id
            return None

        clean_id = str(item_id).strip()
        for idx, itm in enumerate(self._items):
            if itm.description.strip() == clean_id:
                return idx

        if clean_id.isdigit():
            idx_val = int(clean_id)
            if 0 <= idx_val < len(self._items):
                return idx_val
        return None

    def get_item(self, item_id: str | int) -> CostItem | None:
        """Retrieve an item by description or integer index."""
        idx = self._find_index(item_id)
        if idx is not None:
            return self._items[idx]
        return None

    def update_item(self, item_id: str | int, **updates: Any) -> CostItem:
        """Update fields of an existing cost item."""
        idx = self._find_index(item_id)
        if idx is None:
            raise KeyError(f"CostItem with identifier '{item_id}' not found.")

        current = self._items[idx]
        data = current.model_dump()
        data.update(updates)
        updated = CostItem(**data)
        self._items[idx] = updated
        return updated

    def delete_item(self, item_id: str | int) -> bool:
        """Delete an item by description or integer index."""
        idx = self._find_index(item_id)
        if idx is not None:
            self._items.pop(idx)
            return True
        return False

    def get_summary(self) -> dict[str, Any]:
        """Compute aggregated PAF metrics, COPQ rollups, and Pareto breakdown."""
        total_items = len(self._items)
        prevention_cost = sum(i.total_cost for i in self._items if i.category == "Prevention")
        appraisal_cost = sum(i.total_cost for i in self._items if i.category == "Appraisal")
        internal_failure_cost = sum(i.total_cost for i in self._items if i.category == "InternalFailure")
        external_failure_cost = sum(i.total_cost for i in self._items if i.category == "ExternalFailure")

        total_coq = prevention_cost + appraisal_cost + internal_failure_cost + external_failure_cost
        copq = internal_failure_cost + external_failure_cost
        cogq = prevention_cost + appraisal_cost

        copq_pct_revenue = None
        if self._revenue_base is not None and self._revenue_base > 0.0:
            copq_pct_revenue = round((copq / self._revenue_base) * 100.0, 4)

        # Pareto ranking of items by cost descending
        sorted_items = sorted(self._items, key=lambda x: x.total_cost, reverse=True)
        pareto_breakdown: list[dict[str, Any]] = []
        cumulative = 0.0
        for rank, itm in enumerate(sorted_items, start=1):
            cost = itm.total_cost
            cumulative += cost
            pct = (cost / total_coq * 100.0) if total_coq > 0.0 else 0.0
            cum_pct = (cumulative / total_coq * 100.0) if total_coq > 0.0 else 0.0
            pareto_breakdown.append(
                {
                    "rank": rank,
                    "category": itm.category,
                    "description": itm.description,
                    "cost": round(cost, 2),
                    "percentage_of_coq": round(pct, 2),
                    "cumulative_percentage": round(cum_pct, 2),
                }
            )

        return {
            "total_items": total_items,
            "prevention_cost": round(prevention_cost, 2),
            "appraisal_cost": round(appraisal_cost, 2),
            "internal_failure_cost": round(internal_failure_cost, 2),
            "external_failure_cost": round(external_failure_cost, 2),
            "total_coq": round(total_coq, 2),
            "copq": round(copq, 2),
            "cogq": round(cogq, 2),
            "revenue_base": self._revenue_base,
            "copq_pct_revenue": copq_pct_revenue,
            "pareto_breakdown": pareto_breakdown,
        }

    def to_html(self, theme: str = "dark", standalone: bool = True) -> str:
        """Render themed HTML visualization of the COPQ canvas and PAF waterfall.

        Parameters
        ----------
        theme : {"dark", "light"}, default="dark"
            Visual color theme.
        standalone : bool, default=True
            If True, returns a complete HTML5 document; otherwise returns an embeddable container.
        """
        is_dark = theme.lower().strip() != "light"
        summary = self.get_summary()

        # Theme color variables
        bg_page = BG_PRIMARY if is_dark else "#f8fafc"
        bg_card = BG_CARD if is_dark else "#ffffff"
        border_col = BORDER if is_dark else "#cbd5e1"
        text_main = TEXT_PRIMARY if is_dark else "#0f172a"
        text_muted = TEXT_SECONDARY if is_dark else "#64748b"

        accent_blue = "#38bdf8" if is_dark else "#0284c7"
        accent_red = DANGER
        accent_amber = AMBER
        accent_green = SUCCESS
        accent_purple = VIOLET

        category_colors: dict[PAFCategory, str] = {
            "Prevention": accent_green,
            "Appraisal": accent_blue,
            "InternalFailure": accent_amber,
            "ExternalFailure": accent_red,
        }

        # Cards summary section
        rev_html = ""
        if summary["copq_pct_revenue"] is not None:
            rev_html = f"""
            <div class="kpi-card" style="border-top: 4px solid {accent_purple};">
                <div class="kpi-label">COPQ % OF SALES</div>
                <div class="kpi-value" style="color: {accent_purple};">{summary['copq_pct_revenue']:.2f}%</div>
                <div class="kpi-sub">Revenue: ${summary['revenue_base']:,.2f}</div>
            </div>"""

        # Proportional PAF Distribution Bar
        total_coq = summary["total_coq"]
        p_pct = (summary["prevention_cost"] / total_coq * 100.0) if total_coq > 0 else 0.0
        a_pct = (summary["appraisal_cost"] / total_coq * 100.0) if total_coq > 0 else 0.0
        if_pct = (summary["internal_failure_cost"] / total_coq * 100.0) if total_coq > 0 else 0.0
        ef_pct = (summary["external_failure_cost"] / total_coq * 100.0) if total_coq > 0 else 0.0

        paf_bar_html = f"""
        <div style="margin: 20px 0; background: {bg_card}; padding: 16px; border-radius: 8px; border: 1px solid {border_col};">
            <div style="font-weight: 600; font-size: 0.9rem; margin-bottom: 10px; color: {text_main};">
                PAF Cost of Quality Distribution (CoQ = ${total_coq:,.2f})
            </div>
            <div style="display: flex; height: 24px; border-radius: 4px; overflow: hidden; background: {border_col};">
                <div style="width: {p_pct}%; background: {accent_green};" title="Prevention: ${summary['prevention_cost']:,.2f} ({p_pct:.1f}%)"></div>
                <div style="width: {a_pct}%; background: {accent_blue};" title="Appraisal: ${summary['appraisal_cost']:,.2f} ({a_pct:.1f}%)"></div>
                <div style="width: {if_pct}%; background: {accent_amber};" title="Internal Failure: ${summary['internal_failure_cost']:,.2f} ({if_pct:.1f}%)"></div>
                <div style="width: {ef_pct}%; background: {accent_red};" title="External Failure: ${summary['external_failure_cost']:,.2f} ({ef_pct:.1f}%)"></div>
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 16px; margin-top: 10px; font-size: 0.8rem;">
                <span style="display: flex; align-items: center; gap: 6px; color: {text_main};">
                    <span style="width: 10px; height: 10px; border-radius: 2px; background: {accent_green};"></span>
                    Prevention: ${summary['prevention_cost']:,.2f} ({p_pct:.1f}%)
                </span>
                <span style="display: flex; align-items: center; gap: 6px; color: {text_main};">
                    <span style="width: 10px; height: 10px; border-radius: 2px; background: {accent_blue};"></span>
                    Appraisal: ${summary['appraisal_cost']:,.2f} ({a_pct:.1f}%)
                </span>
                <span style="display: flex; align-items: center; gap: 6px; color: {text_main};">
                    <span style="width: 10px; height: 10px; border-radius: 2px; background: {accent_amber};"></span>
                    Internal Failure: ${summary['internal_failure_cost']:,.2f} ({if_pct:.1f}%)
                </span>
                <span style="display: flex; align-items: center; gap: 6px; color: {text_main};">
                    <span style="width: 10px; height: 10px; border-radius: 2px; background: {accent_red};"></span>
                    External Failure: ${summary['external_failure_cost']:,.2f} ({ef_pct:.1f}%)
                </span>
            </div>
        </div>"""

        # Pareto Table rows
        table_rows = []
        for row in summary["pareto_breakdown"]:
            cat_col = category_colors.get(row["category"], accent_blue)
            table_rows.append(
                f"""<tr>
                    <td style="text-align: center; font-weight: bold; color: {text_muted};">{row['rank']}</td>
                    <td><span style="background: {cat_col}22; color: {cat_col}; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">{html.escape(row['category'])}</span></td>
                    <td style="color: {text_main}; font-weight: 500;">{html.escape(row['description'])}</td>
                    <td style="text-align: right; font-weight: 600; color: {text_main};">${row['cost']:,.2f}</td>
                    <td style="text-align: right; color: {text_muted};">{row['percentage_of_coq']:.1f}%</td>
                    <td style="text-align: right; font-weight: 600; color: {accent_blue};">{row['cumulative_percentage']:.1f}%</td>
                </tr>"""
            )

        if not table_rows:
            table_rows.append(f"""<tr><td colspan="6" style="text-align: center; padding: 24px; color: {text_muted};">No Cost Items captured in canvas.</td></tr>""")

        body_content = f"""
<div class="copq-canvas-container" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: {bg_page}; color: {text_main}; padding: 24px; max-width: 1200px; margin: 0 auto;">
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 20px; border-bottom: 1px solid {border_col}; padding-bottom: 12px;">
        <h1 style="margin: 0; font-size: 1.5rem; font-weight: 700; color: {text_main};">{html.escape(self._title)}</h1>
        <span style="font-size: 0.8rem; color: {text_muted}; background: {bg_card}; padding: 4px 10px; border-radius: 4px; border: 1px solid {border_col};">{_STANDARDS_BASIS}</span>
    </div>

    <!-- Financial KPI Cards -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px;">
        <div class="kpi-card" style="border-top: 4px solid {accent_red};">
            <div class="kpi-label">TOTAL COPQ (FAILURE)</div>
            <div class="kpi-value" style="color: {accent_red};">${summary['copq']:,.2f}</div>
            <div class="kpi-sub">Internal + External Failure</div>
        </div>
        <div class="kpi-card" style="border-top: 4px solid {accent_green};">
            <div class="kpi-label">CONFORMANCE COST (CoGQ)</div>
            <div class="kpi-value" style="color: {accent_green};">${summary['cogq']:,.2f}</div>
            <div class="kpi-sub">Prevention + Appraisal</div>
        </div>
        <div class="kpi-card" style="border-top: 4px solid {accent_blue};">
            <div class="kpi-label">TOTAL COST OF QUALITY (CoQ)</div>
            <div class="kpi-value" style="color: {accent_blue};">${summary['total_coq']:,.2f}</div>
            <div class="kpi-sub">{summary['total_items']} items accounted</div>
        </div>
        {rev_html}
    </div>

    <!-- PAF Proportional Bar -->
    {paf_bar_html}

    <!-- Pareto Cost Breakdown Table -->
    <div style="background: {bg_card}; border-radius: 8px; border: 1px solid {border_col}; overflow: hidden; margin-top: 20px;">
        <div style="padding: 14px 18px; border-bottom: 1px solid {border_col}; font-weight: 600; font-size: 0.95rem; color: {text_main};">
            Financial Pareto Ranking & Cost Breakdown
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
            <thead>
                <tr style="background: {bg_page}; border-bottom: 1px solid {border_col}; color: {text_muted}; text-align: left;">
                    <th style="padding: 10px 14px; width: 50px; text-align: center;">Rank</th>
                    <th style="padding: 10px 14px; width: 140px;">PAF Category</th>
                    <th style="padding: 10px 14px;">Cost Item Description</th>
                    <th style="padding: 10px 14px; text-align: right; width: 120px;">Cost</th>
                    <th style="padding: 10px 14px; text-align: right; width: 90px;">% CoQ</th>
                    <th style="padding: 10px 14px; text-align: right; width: 100px;">Cum %</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
    </div>
</div>"""

        if not standalone:
            return body_content

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(self._title)}</title>
    <style>
        body {{ margin: 0; padding: 0; background-color: {bg_page}; }}
        * {{ box-sizing: border-box; }}
        .kpi-card {{
            background: {bg_card};
            padding: 16px;
            border-radius: 8px;
            border: 1px solid {border_col};
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .kpi-label {{
            font-size: 0.75rem;
            font-weight: 700;
            color: {text_muted};
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-size: 1.5rem;
            font-weight: 800;
            line-height: 1.2;
        }}
        .kpi-sub {{
            font-size: 0.75rem;
            color: {text_muted};
            margin-top: 4px;
        }}
        table tbody tr:hover {{
            background-color: {border_col}44;
        }}
        table td {{
            padding: 10px 14px;
            border-bottom: 1px solid {border_col}66;
        }}
    </style>
</head>
<body>
{body_content}
</body>
</html>"""


def load_sample_copq_canvas(revenue_base: float | None = 500000.0) -> COPQCanvas:
    """Load benchmark sample dataset into a new COPQCanvas instance."""
    return COPQCanvas(items=SAMPLE_COPQ_ITEMS, revenue_base=revenue_base)


def render_copq(
    data: Any,
    theme: str = "dark",
    standalone: bool = True,
    revenue_base: float | None = None,
    title: str = "Cost of Poor Quality (COPQ) Canvas",
) -> str:
    """Render a COPQ canvas HTML visualization from untrusted dataset or canvas input."""
    if isinstance(data, COPQCanvas):
        return data.to_html(theme=theme, standalone=standalone)
    canvas = COPQCanvas(items=data, revenue_base=revenue_base, title=title)
    return canvas.to_html(theme=theme, standalone=standalone)

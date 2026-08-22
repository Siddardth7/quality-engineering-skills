"""
ncr.py
Single-writer visual Nonconformance Report (NCR) Canvas reference implementation for Quality Platform.

Provides `NCRCanvas` controller for managing an in-memory collection of ISO 9001:2015 §8.7
and IATF 16949:2016 §8.7 nonconformance records, CRUD operations, benchmark dataset loading,
summary metrics rollup, and theme-aligned HTML canvas rendering (dark and light palettes).

Standards References:
- ISO 9001:2015 Clause 8.7 ("Control of nonconforming outputs"): Clause 8.7.1 & Clause 8.7.2.
- IATF 16949:2016 Clause 8.7 ("Control of nonconforming outputs"): Clause 8.7.1.1, 8.7.1.3, 8.7.1.4 & 8.7.1.7.
"""

from __future__ import annotations

import html
from typing import Any

from quality_core.ncr.schema import (
    DISPOSITION_VALUES,
    NCRDataset,
    NonconformanceRecord,
    validate_ncr,
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
    "NCRCanvas",
    "SAMPLE_NCR_RECORDS",
    "load_sample_ncr_canvas",
    "render_ncr",
]

_STANDARDS_BASIS = "ISO 9001:2015 §8.7 / IATF 16949:2016 §8.7"

# ---------------------------------------------------------------------------
# Reference Benchmark Dataset (Automotive & Precision Machining NCR Records)
# ---------------------------------------------------------------------------

SAMPLE_NCR_RECORDS: list[dict[str, Any]] = [
    {
        "record_id": "NCR-2026-001",
        "part_lot_id": "LOT-BRK-8821",
        "defect_description": "Cast porosity on brake caliper mounting flange exceeding max allowable void diameter.",
        "requirement_violated": "DWG-BRK-004 Rev D: Max surface pore diameter <= 0.50 mm; zero clustering permitted.",
        "quantity_affected": 45,
        "detection_point": "Receiving Inspection / CMM Cell 1",
        "disposition": "ReturnToVendor",
        "severity": "Major",
        "rationale": "Defect originated from external foundry supplier; nonconforming casting lot rejected and segregated for return per ISO 9001:2015 Clause 8.7.1(b).",
        "approval_authority": "Supplier Quality Assurance (SQA) / Purchasing",
    },
    {
        "record_id": "NCR-2026-002",
        "part_lot_id": "LOT-SHAFT-4410",
        "defect_description": "Drive shaft bearing journal outer diameter turned oversized at +0.035 mm above tolerance.",
        "requirement_violated": "SPEC-SFT-102: Bearing journal OD = 35.000 +0.005/-0.000 mm.",
        "quantity_affected": 120,
        "detection_point": "CNC Turning Station 3 / In-Process Post-Op Gauge",
        "disposition": "Rework",
        "severity": "Moderate",
        "rationale": "Product has excess stock and can be precision skim-ground to specification per ISO 9001:2015 Clause 8.7.1(a); risk analysis required per IATF 16949:2016 Clause 8.7.1.4.",
        "approval_authority": "Manufacturing Engineering & Quality Engineering",
    },
    {
        "record_id": "NCR-2026-003",
        "part_lot_id": "LOT-HSG-9904",
        "defect_description": "Inverter housing CNC internal bore undercut wall thickness below minimum structural limit.",
        "requirement_violated": "DWG-INV-012: Minimum wall thickness >= 3.20 mm across pressure envelope.",
        "quantity_affected": 18,
        "detection_point": "Final Machining CMM Inspection",
        "disposition": "Scrap",
        "severity": "Critical",
        "rationale": "Under-thickness structural wall cannot be restored to drawing requirements; must be defaced and rendered unusable per IATF 16949:2016 Clause 8.7.1.7.",
        "approval_authority": "Quality Manager / Scrap Authority",
    },
    {
        "record_id": "NCR-2026-004",
        "part_lot_id": "LOT-BKT-1102",
        "defect_description": "Zinc phosphate bracket e-coat surface finish minor gloss variation on non-cosmetic underbody bracket.",
        "requirement_violated": "SPEC-COAT-09: Gloss reading 60° target = 70 ± 5 GU; measured 58 GU on non-critical face.",
        "quantity_affected": 250,
        "detection_point": "E-Coat Line Unload Inspection",
        "disposition": "UseAsIs",
        "severity": "Minor",
        "rationale": "Deviation does not impair corrosion resistance, fit, form, function, or vehicle safety; customer concession permit obtained per ISO 9001:2015 Clause 8.7.1(d) and IATF 16949:2016 Clause 8.7.1.1.",
        "approval_authority": "Material Review Board (MRB) & Customer Concession Permit",
    },
    {
        "record_id": "NCR-2026-005",
        "part_lot_id": "LOT-ROD-3309",
        "defect_description": "Connecting rod tensile yield strength 780 MPa vs Grade A requirement 820 MPa; conforms to Grade B requirement (>= 750 MPa).",
        "requirement_violated": "MAT-SPEC-04 Grade A: Yield strength >= 820 MPa.",
        "quantity_affected": 300,
        "detection_point": "Metallurgical Lab Tensile Test Gate",
        "disposition": "Regrade",
        "severity": "Moderate",
        "rationale": "Lot meets Grade B application specification; authorized for secondary application transfer per IATF 16949:2016 Clause 8.7.1.7.",
        "approval_authority": "Material Review Board (MRB) & Customer Approval",
    },
]


class NCRCanvas:
    """Single-writer controller managing an in-memory collection of Nonconformance Records.

    Provides CRUD operations, summary statistics, benchmark dataset support, and
    theme-aligned HTML canvas rendering per ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7.
    """

    def __init__(
        self,
        records: list[NonconformanceRecord] | list[dict[str, Any]] | list[Any] | NCRDataset | None = None,
        title: str = "Nonconformance Report (NCR) Canvas",
    ) -> None:
        if not isinstance(title, str) or not title.strip():
            raise TypeError("title must be a non-empty string")
        self._title = title.strip()
        self._records: list[NonconformanceRecord] = []

        if records is not None:
            if isinstance(records, NCRDataset):
                self._records = list(records.records)
            elif isinstance(records, list):
                for item in records:
                    if isinstance(item, NonconformanceRecord):
                        self._records.append(item)
                    elif isinstance(item, dict):
                        self._records.append(NonconformanceRecord(**item))
                    else:
                        raise TypeError(f"Expected NonconformanceRecord or dict, got {type(item).__name__}")
            else:
                validated = validate_ncr(records)
                self._records = list(validated.records)

    @property
    def title(self) -> str:
        """Canvas title."""
        return self._title

    @property
    def records(self) -> list[NonconformanceRecord]:
        """List of managed NonconformanceRecord items."""
        return list(self._records)

    def add_record(self, record: NonconformanceRecord | dict[str, Any]) -> NonconformanceRecord:
        """Add a new NonconformanceRecord to the canvas.

        Parameters
        ----------
        record : NonconformanceRecord or dict
            The record to add.

        Returns
        -------
        NonconformanceRecord
            The validated and stored record.
        """
        if isinstance(record, NonconformanceRecord):
            rec = record
        elif isinstance(record, dict):
            rec = NonconformanceRecord(**record)
        else:
            raise TypeError(f"Expected NonconformanceRecord or dict, got {type(record).__name__}")

        self._records.append(rec)
        return rec

    def _find_index(self, record_id: str | int) -> int | None:
        """Find the index of a record by record_id or integer position."""
        if isinstance(record_id, int):
            if 0 <= record_id < len(self._records):
                return record_id
            return None

        clean_id = str(record_id).strip()
        for idx, rec in enumerate(self._records):
            if rec.record_id and rec.record_id.strip() == clean_id:
                return idx
            if rec.part_lot_id and rec.part_lot_id.strip() == clean_id:
                return idx

        # Try parsing as 0-based integer index
        if clean_id.isdigit():
            idx_val = int(clean_id)
            if 0 <= idx_val < len(self._records):
                return idx_val
        return None

    def get_record(self, record_id: str | int) -> NonconformanceRecord | None:
        """Retrieve a record by record_id, part_lot_id, or integer index."""
        idx = self._find_index(record_id)
        if idx is not None:
            return self._records[idx]
        return None

    def update_record(self, record_id: str | int, **updates: Any) -> NonconformanceRecord:
        """Update fields of an existing record.

        Parameters
        ----------
        record_id : str or int
            The record_id, part_lot_id, or index of the record to update.
        **updates : Any
            Field updates to apply.

        Returns
        -------
        NonconformanceRecord
            The updated record.

        Raises
        ------
        KeyError
            If no matching record is found.
        """
        idx = self._find_index(record_id)
        if idx is None:
            raise KeyError(f"Record with ID/index '{record_id}' not found")

        current_dict = self._records[idx].model_dump()
        current_dict.update(updates)
        updated_rec = NonconformanceRecord(**current_dict)
        self._records[idx] = updated_rec
        return updated_rec

    def delete_record(self, record_id: str | int) -> bool:
        """Delete a record by record_id, part_lot_id, or integer index.

        Parameters
        ----------
        record_id : str or int
            Identifier of the record to remove.

        Returns
        -------
        bool
            True if removed, False if not found.
        """
        idx = self._find_index(record_id)
        if idx is not None:
            self._records.pop(idx)
            return True
        return False

    def get_summary(self) -> dict[str, Any]:
        """Compute aggregate summary metrics across all canvas records."""
        total_records = len(self._records)
        total_quantity = sum(r.quantity_affected for r in self._records)

        disposition_counts: dict[str, int] = {k: 0 for k in DISPOSITION_VALUES}
        disposition_counts["Unassigned"] = 0
        severity_counts: dict[str, int] = {}
        mrb_required_count = 0

        for r in self._records:
            disp = r.disposition or "Unassigned"
            disposition_counts[disp] = disposition_counts.get(disp, 0) + 1

            if disp in ("UseAsIs", "Regrade") or (r.approval_authority and "MRB" in r.approval_authority):
                mrb_required_count += 1

            sev = r.severity or "Unspecified"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "title": self._title,
            "total_records": total_records,
            "total_quantity_affected": total_quantity,
            "disposition_counts": disposition_counts,
            "severity_counts": severity_counts,
            "mrb_required_count": mrb_required_count,
            "standards_basis": _STANDARDS_BASIS,
        }

    def to_html(self, theme: str = "dark", standalone: bool = True) -> str:
        """Render the canvas as a responsive, themed HTML nonconformance report card & log.

        Parameters
        ----------
        theme : str, default "dark"
            Theme palette ('dark' or 'light').
        standalone : bool, default True
            Whether to return a complete HTML5 document or an embeddable container.

        Returns
        -------
        str
            Sanitized and rendered HTML output.
        """
        is_dark = theme.lower().strip() != "light"

        # Theme color variables
        bg_page = BG_PRIMARY if is_dark else "#f8fafc"
        bg_card = BG_CARD if is_dark else "#ffffff"
        bg_sub = BG_SECONDARY if is_dark else "#f1f5f9"
        border_col = BORDER if is_dark else "#cbd5e1"
        text_pri = TEXT_PRIMARY if is_dark else "#0f172a"
        text_sec = TEXT_SECONDARY if is_dark else "#64748b"

        summary = self.get_summary()
        disp_counts = summary["disposition_counts"]

        # Disposition badge styling map
        badge_styles: dict[str, tuple[str, str]] = {
            "Scrap": (DANGER, "#fee2e2" if not is_dark else "#450a0a"),
            "Rework": (AMBER, "#fef3c7" if not is_dark else "#451a03"),
            "UseAsIs": (SUCCESS, "#dcfce7" if not is_dark else "#052e16"),
            "ReturnToVendor": (VIOLET, "#f3e8ff" if not is_dark else "#3b0764"),
            "Regrade": (AMBER, "#e0e7ff" if not is_dark else "#1e1b4b"),
            "Unassigned": (text_sec, bg_sub),
        }

        # Build cards / rows HTML
        cards_html: list[str] = []
        if not self._records:
            cards_html.append(
                f'<div style="text-align: center; padding: 40px; color: {text_sec}; font-style: italic;">'
                "No nonconformance records captured in canvas. Add records using the NCR engine."
                "</div>"
            )
        else:
            for idx, r in enumerate(self._records, start=1):
                disp_val = r.disposition or "Unassigned"
                fg, bg = badge_styles.get(disp_val, (text_sec, bg_sub))
                rec_id_disp = r.record_id or f"NCR-{idx:03d}"
                sev_badge = f'<span style="font-size: 11px; padding: 2px 8px; border-radius: 4px; background: {bg_sub}; color: {text_sec}; border: 1px solid {border_col};">{html.escape(r.severity or "Standard")}</span>' if r.severity else ""

                cards_html.append(f"""
                <div class="ncr-card" style="background: {bg_card}; border: 1px solid {border_col}; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {border_col}; padding-bottom: 10px; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <strong style="color: {text_pri}; font-size: 15px;">{html.escape(rec_id_disp)}</strong>
                            <span style="color: {text_sec}; font-size: 13px;">| Part/Lot: <code style="color: {AMBER};">{html.escape(r.part_lot_id)}</code></span>
                            {sev_badge}
                        </div>
                        <div>
                            <span style="font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 12px; color: {fg}; background: {bg}; border: 1px solid {fg};">
                                {html.escape(disp_val)}
                            </span>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;">
                        <div>
                            <div style="font-size: 11px; text-transform: uppercase; color: {text_sec}; font-weight: 600; margin-bottom: 4px;">Defect Description</div>
                            <div style="color: {text_pri}; font-size: 13px; line-height: 1.4;">{html.escape(r.defect_description)}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; text-transform: uppercase; color: {text_sec}; font-weight: 600; margin-bottom: 4px;">Requirement Violated</div>
                            <div style="color: {text_pri}; font-size: 13px; line-height: 1.4;">{html.escape(r.requirement_violated)}</div>
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; background: {bg_sub}; padding: 10px; border-radius: 6px; margin-bottom: 10px; font-size: 12px;">
                        <div><strong style="color: {text_sec};">Quantity Affected:</strong> <span style="color: {text_pri}; font-weight: 600;">{r.quantity_affected}</span></div>
                        <div><strong style="color: {text_sec};">Detection Point:</strong> <span style="color: {text_pri};">{html.escape(r.detection_point)}</span></div>
                        <div><strong style="color: {text_sec};">Approval Authority:</strong> <span style="color: {text_pri};">{html.escape(r.approval_authority or 'Pending')}</span></div>
                    </div>
                    {f'<div style="font-size: 12px; color: {text_sec}; font-style: italic; border-left: 3px solid {fg}; padding-left: 8px;">Rationale: {html.escape(r.rationale)}</div>' if r.rationale else ''}
                </div>
                """)

        body_content = f"""
        <div class="ncr-canvas-container" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 1100px; margin: 0 auto; padding: 20px; color: {text_pri}; background: {bg_page};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 2px solid {border_col}; padding-bottom: 12px;">
                <div>
                    <h2 style="margin: 0 0 4px 0; color: {text_pri}; font-size: 20px;">{html.escape(self._title)}</h2>
                    <div style="font-size: 12px; color: {text_sec};">Standards Basis: {html.escape(_STANDARDS_BASIS)}</div>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 13px; color: {text_sec};">Total Records: <strong style="color: {text_pri};">{summary['total_records']}</strong> | Total Qty: <strong style="color: {text_pri};">{summary['total_quantity_affected']}</strong></span>
                </div>
            </div>

            <!-- Summary KPI Badges -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 24px;">
                <div style="background: {bg_card}; border: 1px solid {border_col}; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 11px; color: {text_sec};">Scrap</div>
                    <div style="font-size: 18px; font-weight: 700; color: {DANGER};">{disp_counts.get('Scrap', 0)}</div>
                </div>
                <div style="background: {bg_card}; border: 1px solid {border_col}; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 11px; color: {text_sec};">Rework</div>
                    <div style="font-size: 18px; font-weight: 700; color: {AMBER};">{disp_counts.get('Rework', 0)}</div>
                </div>
                <div style="background: {bg_card}; border: 1px solid {border_col}; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 11px; color: {text_sec};">Use As Is</div>
                    <div style="font-size: 18px; font-weight: 700; color: {SUCCESS};">{disp_counts.get('UseAsIs', 0)}</div>
                </div>
                <div style="background: {bg_card}; border: 1px solid {border_col}; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 11px; color: {text_sec};">Return To Vendor</div>
                    <div style="font-size: 18px; font-weight: 700; color: {VIOLET};">{disp_counts.get('ReturnToVendor', 0)}</div>
                </div>
                <div style="background: {bg_card}; border: 1px solid {border_col}; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 11px; color: {text_sec};">Regrade</div>
                    <div style="font-size: 18px; font-weight: 700; color: {AMBER};">{disp_counts.get('Regrade', 0)}</div>
                </div>
                <div style="background: {bg_card}; border: 1px solid {border_col}; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 11px; color: {text_sec};">MRB Gate Required</div>
                    <div style="font-size: 18px; font-weight: 700; color: {text_pri};">{summary['mrb_required_count']}</div>
                </div>
            </div>

            <!-- Nonconformance Records List -->
            <div class="ncr-records-list">
                {''.join(cards_html)}
            </div>
        </div>
        """

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
    </style>
</head>
<body>
{body_content}
</body>
</html>"""


def load_sample_ncr_canvas() -> NCRCanvas:
    """Load benchmark sample dataset into a new NCRCanvas instance."""
    return NCRCanvas(records=SAMPLE_NCR_RECORDS)


def render_ncr(
    data: Any,
    theme: str = "dark",
    standalone: bool = True,
    title: str = "Nonconformance Report (NCR) Canvas",
) -> str:
    """Render an NCR canvas HTML visualization from untrusted dataset or canvas input."""
    if isinstance(data, NCRCanvas):
        return data.to_html(theme=theme, standalone=standalone)
    canvas = NCRCanvas(records=data, title=title)
    return canvas.to_html(theme=theme, standalone=standalone)

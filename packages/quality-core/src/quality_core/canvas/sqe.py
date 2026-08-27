"""Read-only visual canvas for supplier scorecard and escalation results."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from typing import Any

from quality_core.sqe.escalation import EscalationResult, EscalationTier
from quality_core.sqe.scorecard import ScorecardBand, ScorecardDimensionResult, ScorecardResult
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

__all__ = ["SQECanvasRow", "SQECanvas", "SAMPLE_SQE_ROWS", "load_sample_sqe_canvas", "render_sqe"]

_BAND_COLOURS = {"A": SUCCESS, "B": AMBER, "C": DANGER}
_TIER_COLOURS = {
    "NONE": SUCCESS,
    "MONITOR": AMBER,
    "SCAR_REQUIRED": AMBER,
    "CONTAINMENT_REQUIRED": DANGER,
    "EXECUTIVE_REVIEW": VIOLET,
    "INDETERMINATE": TEXT_SECONDARY,
}


@dataclass
class SQECanvasRow:
    """One already-evaluated supplier scorecard and escalation recommendation."""

    supplier_id: str
    scorecard: ScorecardResult
    escalation: EscalationResult
    supplier_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.supplier_id, str) or not self.supplier_id.strip():
            raise TypeError("supplier_id must be a non-empty string")
        self.supplier_id = self.supplier_id.strip()
        if not isinstance(self.scorecard, ScorecardResult):
            raise TypeError("scorecard must be a ScorecardResult")
        if not isinstance(self.escalation, EscalationResult):
            raise TypeError("escalation must be an EscalationResult")
        if self.supplier_name is not None:
            if not isinstance(self.supplier_name, str):
                raise TypeError("supplier_name must be a string or None")
            self.supplier_name = self.supplier_name.strip() or None

    def to_dict(self) -> dict[str, Any]:
        return {
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "scorecard": self.scorecard.to_dict(),
            "escalation": self.escalation.to_dict(),
        }


class SQECanvas:
    """Single-writer collection of immutable engine results."""

    def __init__(
        self,
        rows: list[SQECanvasRow] | list[dict[str, Any]] | None = None,
        title: str = "SQE Vendor Scorecard Canvas",
    ) -> None:
        if not isinstance(title, str):
            raise TypeError("title must be a non-empty string")
        if not title.strip():
            raise ValueError("title must be a non-empty string")
        self._title = title.strip()
        self._rows: list[SQECanvasRow] = []
        if rows is not None:
            if not isinstance(rows, list):
                raise TypeError(f"rows must be a list or None, got {type(rows).__name__}")
            for row in rows:
                self._rows.append(row if isinstance(row, SQECanvasRow) else SQECanvasRow(**row) if isinstance(row, dict) else _bad_row(row))

    @property
    def title(self) -> str:
        return self._title

    @property
    def rows(self) -> list[SQECanvasRow]:
        return list(self._rows)

    def load_sample(self) -> SQECanvas:
        self._rows = [SQECanvasRow(**row) for row in SAMPLE_SQE_ROWS]
        return self

    def to_dict(self) -> dict[str, Any]:
        return {"title": self._title, "rows": [row.to_dict() for row in self._rows]}

    @staticmethod
    def _theme(theme: str, standalone: bool) -> tuple[bool, bool]:
        if not isinstance(theme, str) or theme.lower().strip() not in {"dark", "light"}:
            raise ValueError("theme must be 'dark' or 'light'")
        if not isinstance(standalone, bool):
            raise TypeError("standalone must be a boolean")
        return theme.lower().strip() == "dark", standalone

    def to_html(self, theme: str = "dark", standalone: bool = True) -> str:
        is_dark, standalone = self._theme(theme, standalone)
        page = BG_PRIMARY if is_dark else "#f8fafc"
        card = BG_CARD if is_dark else "#ffffff"
        border = BORDER if is_dark else "#cbd5e1"
        primary = TEXT_PRIMARY if is_dark else "#0f172a"
        secondary = TEXT_SECONDARY if is_dark else "#64748b"
        rows: list[str] = []
        for row in self._rows:
            score = row.scorecard
            dims = {dimension.name: dimension for dimension in score.dimensions}
            quality = dims.get("quality")
            delivery = dims.get("delivery")
            cost = dims.get("cost")
            evidence = delivery.source_evidence if delivery else {}
            on_time = evidence.get("on_time_pct", "not scored")
            in_full = evidence.get("in_full_pct", "not scored")
            ppm = quality.raw_metric if quality and quality.raw_metric is not None else "not scored"
            cost_value = cost.raw_metric if cost and cost.raw_metric is not None else "not scored/omitted"
            rated = score.verdict == "RATED"
            composite = _number(score.composite_score) if rated else "UNRATED"
            band = score.band if rated and score.band is not None else "INDETERMINATE"
            band_colour = _BAND_COLOURS.get(str(band), secondary)
            tier = row.escalation.tier
            tier_colour = _TIER_COLOURS.get(tier, secondary)
            reason = score.reason or row.escalation.reason
            reason_html = f'<div class="reason">{html.escape(reason)}</div>' if reason else ""
            period = score.period_label or f"{score.period_start.isoformat()} to {score.period_end.isoformat()}"
            rows.append(f"""
            <tr><td><strong>{html.escape(row.supplier_id)}</strong>{f'<br><small>{html.escape(row.supplier_name)}</small>' if row.supplier_name else ''}<br><small>{html.escape(period)}</small></td>
              <td>{_number(ppm)}</td><td>{_number(on_time)}<br><small>on-time</small><br>{_number(in_full)}<br><small>in-full</small></td>
              <td>{_number(cost_value)}</td><td>{composite}</td>
              <td><span class="badge" style="color:{band_colour};">{html.escape(str(band))}</span></td>
              <td><span class="badge" style="color:{tier_colour};">{html.escape(tier)}</span></td></tr>
              {f'<tr><td colspan="7">{reason_html}</td></tr>' if reason_html else ''}
            """)
        if not rows:
            rows.append('<tr><td colspan="7" class="empty">No supplier scorecard results captured in canvas.</td></tr>')
        heuristic = "All weights, thresholds, curves, bands, and escalation tiers are caller-configurable engineering heuristics with no standards citation."
        body = f"""<div class="sqe-canvas" style="font-family:Inter,Arial,sans-serif;max-width:1400px;margin:0 auto;padding:20px;background:{page};color:{primary};">
<h2>{html.escape(self._title)}</h2><div style="color:{secondary};font-size:12px;">{html.escape(heuristic)}</div>
<table style="width:100%;border-collapse:collapse;margin-top:18px;background:{card};"><thead><tr>
<th>Supplier / period</th><th>PPM</th><th>OTIF</th><th>COPQ / cost</th><th>Composite score</th><th>Band</th><th>Escalation tier</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table>
<div style="margin-top:12px;color:{secondary};font-size:12px;">Period context is taken from each scorecard result. Escalation is a quality recommendation only; commercial response remains authorized-business-person territory.</div>
<style>th,td{{padding:10px;text-align:left;border-bottom:1px solid {border};}} th{{color:{secondary};font-size:11px;text-transform:uppercase;}} .badge{{font-weight:700;}} .empty{{text-align:center;padding:36px;color:{secondary};font-style:italic;}} .reason{{color:{secondary};font-size:12px;}}</style></div>"""
        if not standalone:
            return body
        return f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{html.escape(self._title)}</title><style>body{{margin:0;background:{page};}}*{{box-sizing:border-box;}}</style></head><body>{body}</body></html>'


def _bad_row(value: object) -> SQECanvasRow:
    raise TypeError(f"Expected SQECanvasRow or dict, got {type(value).__name__}")


def _number(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:g}"
    return html.escape(str(value))


def _sample_scorecard(supplier_id: str, composite: float | None, band: ScorecardBand | None) -> ScorecardResult:
    rated = composite is not None
    dimensions = [
        ScorecardDimensionResult("quality", "ppm", 100.0, 95.0, 0.60, 57.0, "MEASURED", None, {"ppm": 100.0}),
        ScorecardDimensionResult("delivery", "otif_pct", 98.0, 98.0, 0.40, 39.2, "MEASURED", None, {"on_time_pct": 99.0, "in_full_pct": 99.0, "otif_pct": 98.0}),
    ]
    return ScorecardResult(supplier_id, date(2026, 1, 1), date(2026, 1, 31), "January 2026", "RATED" if rated else "INDETERMINATE", composite, band, dimensions, {"is_heuristic": True, "basis": "no standards citation"}, [], None if rated else "required evidence is unavailable")


def _sample_row(supplier_id: str, tier: EscalationTier, composite: float | None, band: ScorecardBand | None) -> dict[str, Any]:
    scorecard = _sample_scorecard(supplier_id, composite, band)
    return {"supplier_id": supplier_id, "supplier_name": f"Benchmark {supplier_id}", "scorecard": scorecard, "escalation": EscalationResult(supplier_id, tier, scorecard.verdict, [], [], None, None if composite is not None else scorecard.reason, {}, "AIAG CQI-20 discipline; no numeric standard")}


SAMPLE_SQE_ROWS: list[dict[str, Any]] = [
    _sample_row("SUP-A", "NONE", 95.0, "A"),
    _sample_row("SUP-B", "MONITOR", 80.0, "B"),
    _sample_row("SUP-C", "SCAR_REQUIRED", 70.0, "C"),
    _sample_row("SUP-D", "CONTAINMENT_REQUIRED", 50.0, "C"),
    _sample_row("SUP-E", "EXECUTIVE_REVIEW", 30.0, "C"),
    _sample_row("SUP-X", "INDETERMINATE", None, None),
]


def load_sample_sqe_canvas() -> SQECanvas:
    return SQECanvas(SAMPLE_SQE_ROWS)


def render_sqe(data: Any, theme: str = "dark", standalone: bool = True, title: str = "SQE Vendor Scorecard Canvas") -> str:
    if isinstance(data, SQECanvas):
        return data.to_html(theme=theme, standalone=standalone)
    return SQECanvas(rows=data, title=title).to_html(theme=theme, standalone=standalone)

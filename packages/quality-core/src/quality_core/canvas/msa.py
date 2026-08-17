"""
msa.py
Single-writer visual MSA Gage R&R Canvas reference implementation for Quality Platform.

Provides `MSACanvasMeasurement` and `MSACanvas` controller for managing in-memory
Gage R&R measurement data with deterministic AIAG MSA 4th Edition calculations via
`quality_core.msa`, sample dataset loading, single-writer measurement CRUD editing,
and theme-aligned HTML/SVG canvas rendering (Interaction Plot & Variance Components).
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from quality_core.msa.gage_rr import (
    METHOD,
    METHOD_ANOVA,
    compute_gage_rr,
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

# Standard AIAG MSA 4th Edition Table A 4 / A 5 Benchmark Dataset (10 parts x 3 appraisers x 3 trials = 90 rows)
SAMPLE_MSA_STUDY_DATA: list[dict[str, Any]] = [
    {"part": "P01", "appraiser": "A", "trial": 1, "measurement": 0.29},
    {"part": "P01", "appraiser": "A", "trial": 2, "measurement": 0.41},
    {"part": "P01", "appraiser": "A", "trial": 3, "measurement": 0.64},
    {"part": "P02", "appraiser": "A", "trial": 1, "measurement": -0.56},
    {"part": "P02", "appraiser": "A", "trial": 2, "measurement": -0.68},
    {"part": "P02", "appraiser": "A", "trial": 3, "measurement": -0.58},
    {"part": "P03", "appraiser": "A", "trial": 1, "measurement": 1.34},
    {"part": "P03", "appraiser": "A", "trial": 2, "measurement": 1.17},
    {"part": "P03", "appraiser": "A", "trial": 3, "measurement": 1.27},
    {"part": "P04", "appraiser": "A", "trial": 1, "measurement": 0.47},
    {"part": "P04", "appraiser": "A", "trial": 2, "measurement": 0.50},
    {"part": "P04", "appraiser": "A", "trial": 3, "measurement": 0.64},
    {"part": "P05", "appraiser": "A", "trial": 1, "measurement": -0.80},
    {"part": "P05", "appraiser": "A", "trial": 2, "measurement": -0.92},
    {"part": "P05", "appraiser": "A", "trial": 3, "measurement": -0.84},
    {"part": "P06", "appraiser": "A", "trial": 1, "measurement": 0.02},
    {"part": "P06", "appraiser": "A", "trial": 2, "measurement": -0.11},
    {"part": "P06", "appraiser": "A", "trial": 3, "measurement": -0.21},
    {"part": "P07", "appraiser": "A", "trial": 1, "measurement": 0.59},
    {"part": "P07", "appraiser": "A", "trial": 2, "measurement": 0.75},
    {"part": "P07", "appraiser": "A", "trial": 3, "measurement": 0.66},
    {"part": "P08", "appraiser": "A", "trial": 1, "measurement": -0.31},
    {"part": "P08", "appraiser": "A", "trial": 2, "measurement": -0.20},
    {"part": "P08", "appraiser": "A", "trial": 3, "measurement": -0.17},
    {"part": "P09", "appraiser": "A", "trial": 1, "measurement": 2.26},
    {"part": "P09", "appraiser": "A", "trial": 2, "measurement": 1.99},
    {"part": "P09", "appraiser": "A", "trial": 3, "measurement": 2.01},
    {"part": "P10", "appraiser": "A", "trial": 1, "measurement": -1.36},
    {"part": "P10", "appraiser": "A", "trial": 2, "measurement": -1.25},
    {"part": "P10", "appraiser": "A", "trial": 3, "measurement": -1.31},
    {"part": "P01", "appraiser": "B", "trial": 1, "measurement": 0.08},
    {"part": "P01", "appraiser": "B", "trial": 2, "measurement": 0.25},
    {"part": "P01", "appraiser": "B", "trial": 3, "measurement": 0.07},
    {"part": "P02", "appraiser": "B", "trial": 1, "measurement": -0.47},
    {"part": "P02", "appraiser": "B", "trial": 2, "measurement": -1.22},
    {"part": "P02", "appraiser": "B", "trial": 3, "measurement": -0.68},
    {"part": "P03", "appraiser": "B", "trial": 1, "measurement": 1.19},
    {"part": "P03", "appraiser": "B", "trial": 2, "measurement": 0.94},
    {"part": "P03", "appraiser": "B", "trial": 3, "measurement": 1.34},
    {"part": "P04", "appraiser": "B", "trial": 1, "measurement": 0.01},
    {"part": "P04", "appraiser": "B", "trial": 2, "measurement": 1.03},
    {"part": "P04", "appraiser": "B", "trial": 3, "measurement": 0.20},
    {"part": "P05", "appraiser": "B", "trial": 1, "measurement": -0.56},
    {"part": "P05", "appraiser": "B", "trial": 2, "measurement": -1.20},
    {"part": "P05", "appraiser": "B", "trial": 3, "measurement": -1.28},
    {"part": "P06", "appraiser": "B", "trial": 1, "measurement": -0.20},
    {"part": "P06", "appraiser": "B", "trial": 2, "measurement": 0.22},
    {"part": "P06", "appraiser": "B", "trial": 3, "measurement": 0.06},
    {"part": "P07", "appraiser": "B", "trial": 1, "measurement": 0.47},
    {"part": "P07", "appraiser": "B", "trial": 2, "measurement": 0.55},
    {"part": "P07", "appraiser": "B", "trial": 3, "measurement": 0.83},
    {"part": "P08", "appraiser": "B", "trial": 1, "measurement": -0.63},
    {"part": "P08", "appraiser": "B", "trial": 2, "measurement": 0.08},
    {"part": "P08", "appraiser": "B", "trial": 3, "measurement": -0.34},
    {"part": "P09", "appraiser": "B", "trial": 1, "measurement": 1.80},
    {"part": "P09", "appraiser": "B", "trial": 2, "measurement": 2.12},
    {"part": "P09", "appraiser": "B", "trial": 3, "measurement": 2.19},
    {"part": "P10", "appraiser": "B", "trial": 1, "measurement": -1.68},
    {"part": "P10", "appraiser": "B", "trial": 2, "measurement": -1.62},
    {"part": "P10", "appraiser": "B", "trial": 3, "measurement": -1.50},
    {"part": "P01", "appraiser": "C", "trial": 1, "measurement": 0.04},
    {"part": "P01", "appraiser": "C", "trial": 2, "measurement": 0.28},
    {"part": "P01", "appraiser": "C", "trial": 3, "measurement": -0.11},
    {"part": "P02", "appraiser": "C", "trial": 1, "measurement": -0.92},
    {"part": "P02", "appraiser": "C", "trial": 2, "measurement": -0.99},
    {"part": "P02", "appraiser": "C", "trial": 3, "measurement": -1.13},
    {"part": "P03", "appraiser": "C", "trial": 1, "measurement": 0.79},
    {"part": "P03", "appraiser": "C", "trial": 2, "measurement": 1.25},
    {"part": "P03", "appraiser": "C", "trial": 3, "measurement": 0.94},
    {"part": "P04", "appraiser": "C", "trial": 1, "measurement": 0.28},
    {"part": "P04", "appraiser": "C", "trial": 2, "measurement": 0.43},
    {"part": "P04", "appraiser": "C", "trial": 3, "measurement": 0.20},
    {"part": "P05", "appraiser": "C", "trial": 1, "measurement": -1.07},
    {"part": "P05", "appraiser": "C", "trial": 2, "measurement": -1.02},
    {"part": "P05", "appraiser": "C", "trial": 3, "measurement": -1.10},
    {"part": "P06", "appraiser": "C", "trial": 1, "measurement": -0.29},
    {"part": "P06", "appraiser": "C", "trial": 2, "measurement": -0.42},
    {"part": "P06", "appraiser": "C", "trial": 3, "measurement": -0.37},
    {"part": "P07", "appraiser": "C", "trial": 1, "measurement": 0.34},
    {"part": "P07", "appraiser": "C", "trial": 2, "measurement": 0.49},
    {"part": "P07", "appraiser": "C", "trial": 3, "measurement": 0.70},
    {"part": "P08", "appraiser": "C", "trial": 1, "measurement": -0.64},
    {"part": "P08", "appraiser": "C", "trial": 2, "measurement": -0.44},
    {"part": "P08", "appraiser": "C", "trial": 3, "measurement": -0.44},
    {"part": "P09", "appraiser": "C", "trial": 1, "measurement": 2.28},
    {"part": "P09", "appraiser": "C", "trial": 2, "measurement": 1.78},
    {"part": "P09", "appraiser": "C", "trial": 3, "measurement": 1.96},
    {"part": "P10", "appraiser": "C", "trial": 1, "measurement": -1.50},
    {"part": "P10", "appraiser": "C", "trial": 2, "measurement": -1.41},
    {"part": "P10", "appraiser": "C", "trial": 3, "measurement": -1.53},
]

# Color cycle for appraiser lines in the interaction plot
_APPRAISER_COLORS: list[str] = [
    "#38bdf8",  # Sky blue
    AMBER,      # Amber
    SUCCESS,    # Emerald green
    "#ec4899",  # Pink
    VIOLET,     # Violet
    "#f97316",  # Orange
]


@dataclass
class MSACanvasMeasurement:
    """Represents a single observation row in the Gage R&R study dataset."""

    id: int
    part: str
    appraiser: str
    trial: int
    measurement: float

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary of the measurement item."""
        return {
            "id": self.id,
            "part": self.part,
            "appraiser": self.appraiser,
            "trial": self.trial,
            "measurement": self.measurement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MSACanvasMeasurement:
        """Construct MSACanvasMeasurement from dictionary supporting case variations."""
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for measurement item, got {type(data).__name__}: {data!r}")

        raw_id: Any = data.get("id")
        if raw_id is None:
            raw_id = data.get("ID", 0)
        try:
            item_id = int(raw_id)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid measurement id: {raw_id!r}")

        part = str(data.get("part", data.get("Part", data.get("PART", "")))).strip()
        if not part:
            raise ValueError("Measurement missing or empty 'part' attribute.")

        appraiser = str(data.get("appraiser", data.get("Appraiser", data.get("APPRAISER", "")))).strip()
        if not appraiser:
            raise ValueError("Measurement missing or empty 'appraiser' attribute.")

        raw_trial: Any = data.get("trial")
        if raw_trial is None:
            raw_trial = data.get("Trial", data.get("TRIAL", 1))
        try:
            trial = int(raw_trial)
            if trial < 1:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError(f"Trial must be a positive integer, got: {raw_trial!r}")

        raw_measurement: Any = data.get("measurement")
        if raw_measurement is None:
            raw_measurement = data.get("Measurement", data.get("MEASUREMENT", data.get("value", 0.0)))
        try:
            val = float(raw_measurement)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid measurement numeric value: {raw_measurement!r}")

        return cls(id=item_id, part=part, appraiser=appraiser, trial=trial, measurement=val)


class MSACanvas:
    """Single-writer Gage R&R Visual Canvas controller.

    Manages crossed Gage R&R study data, recalculates variance components and ANOVA
    decompositions deterministically via `quality_core.msa`, supports single-writer
    measurement CRUD editing, and generates styled HTML5/SVG canvas artifacts
    including an Operator x Part Interaction Plot and Variance Components bar chart.
    """

    SUPPORTED_METHODS: tuple[str, ...] = (METHOD_ANOVA, METHOD)

    def __init__(
        self,
        method: str = METHOD_ANOVA,
        title: str = "AIAG MSA Gage R&R Canvas",
        tolerance: float | None = None,
        measurements: list[dict[str, Any]] | list[MSACanvasMeasurement] | None = None,
    ) -> None:
        if isinstance(title, bool) or not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string.")
        if method not in self.SUPPORTED_METHODS:
            raise ValueError(f"Unknown or unsupported method: {method!r}. Supported: {self.SUPPORTED_METHODS}")
        if tolerance is not None:
            if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance <= 0:
                raise ValueError("tolerance must be a positive finite float.")

        self.title: str = title.strip()
        self.method: str = method
        self.tolerance: float | None = float(tolerance) if tolerance is not None else None

        self.measurements: list[MSACanvasMeasurement] = []
        self._next_id: int = 1

        # Cached analysis fields
        self.basis: str = "AIAG MSA 4th Edition"
        self.ev: float = 0.0
        self.av: float = 0.0
        self.grr: float = 0.0
        self.pv: float = 0.0
        self.tv: float = 0.0
        self.mean: float = 0.0
        self.pev_study: float = 0.0
        self.pav_study: float = 0.0
        self.pgrr_study: float = 0.0
        self.ppv_study: float = 0.0
        self.pev_tolerance: float | None = None
        self.pav_tolerance: float | None = None
        self.pgrr_tolerance: float | None = None
        self.ppv_tolerance: float | None = None
        self.ndc: int = 0
        self.verdict: str = "Pending"
        self.n_parts: int = 0
        self.n_appraisers: int = 0
        self.n_trials: int = 0
        self.is_balanced: bool = True
        self.interaction: float | None = None
        self.interaction_f: float | None = None
        self.interaction_significant: bool | None = None
        self.method_note: str = ""

        if measurements is not None:
            self.set_data(measurements)

    def set_data(self, measurements: list[dict[str, Any]] | list[MSACanvasMeasurement]) -> None:
        """Replace all current measurements and recalculate the Gage R&R model."""
        if not isinstance(measurements, list):
            raise TypeError(f"measurements must be a list, got {type(measurements).__name__}: {measurements!r}")

        new_measurements: list[MSACanvasMeasurement] = []
        next_id = 1

        for item in measurements:
            if isinstance(item, MSACanvasMeasurement):
                meas = MSACanvasMeasurement(
                    id=next_id,
                    part=item.part,
                    appraiser=item.appraiser,
                    trial=item.trial,
                    measurement=item.measurement,
                )
            elif isinstance(item, dict):
                meas = MSACanvasMeasurement.from_dict(item)
                meas.id = next_id
            else:
                raise TypeError(f"Expected dict or MSACanvasMeasurement, got {type(item).__name__}")
            new_measurements.append(meas)
            next_id += 1

        self.measurements = new_measurements
        self._next_id = next_id
        self.recalculate()

    def add_measurement(self, item: dict[str, Any] | MSACanvasMeasurement) -> MSACanvasMeasurement:
        """Add a single measurement item and recalculate."""
        if isinstance(item, MSACanvasMeasurement):
            meas = MSACanvasMeasurement(
                id=self._next_id,
                part=item.part,
                appraiser=item.appraiser,
                trial=item.trial,
                measurement=item.measurement,
            )
        elif isinstance(item, dict):
            meas = MSACanvasMeasurement.from_dict(item)
            meas.id = self._next_id
        else:
            raise TypeError(f"Expected dict or MSACanvasMeasurement, got {type(item).__name__}")

        self.measurements.append(meas)
        self._next_id += 1
        self.recalculate()
        return meas

    def update_measurement(
        self,
        id: int,
        measurement: float | None = None,
        part: str | None = None,
        appraiser: str | None = None,
        trial: int | None = None,
    ) -> MSACanvasMeasurement:
        """Update fields of an existing measurement identified by ID and recalculate."""
        for item in self.measurements:
            if item.id == id:
                if measurement is not None:
                    try:
                        item.measurement = float(measurement)
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid numeric measurement: {measurement!r}")
                if part is not None:
                    p = str(part).strip()
                    if not p:
                        raise ValueError("part cannot be empty.")
                    item.part = p
                if appraiser is not None:
                    a = str(appraiser).strip()
                    if not a:
                        raise ValueError("appraiser cannot be empty.")
                    item.appraiser = a
                if trial is not None:
                    try:
                        t = int(trial)
                        if t < 1:
                            raise ValueError
                        item.trial = t
                    except (ValueError, TypeError):
                        raise ValueError(f"trial must be a positive integer, got: {trial!r}")
                self.recalculate()
                return item
        raise KeyError(f"Measurement with id={id} not found in canvas.")

    def delete_measurement(self, id: int) -> bool:
        """Delete a measurement by ID and recalculate. Returns True if deleted."""
        for idx, item in enumerate(self.measurements):
            if item.id == id:
                self.measurements.pop(idx)
                self.recalculate()
                return True
        return False

    def _reset_analysis_state(self, verdict: str = "Pending", note: str = "") -> None:
        """Reset calculated metrics to pending / empty defaults."""
        self.basis = "AIAG MSA 4th Edition"
        self.ev = 0.0
        self.av = 0.0
        self.grr = 0.0
        self.pv = 0.0
        self.tv = 0.0
        self.mean = 0.0
        self.pev_study = 0.0
        self.pav_study = 0.0
        self.pgrr_study = 0.0
        self.ppv_study = 0.0
        self.pev_tolerance = None
        self.pav_tolerance = None
        self.pgrr_tolerance = None
        self.ppv_tolerance = None
        self.ndc = 0
        self.verdict = verdict
        self.n_parts = len(set(m.part for m in self.measurements)) if self.measurements else 0
        self.n_appraisers = len(set(m.appraiser for m in self.measurements)) if self.measurements else 0
        self.n_trials = max((m.trial for m in self.measurements), default=0) if self.measurements else 0
        self.is_balanced = True
        self.interaction = None
        self.interaction_f = None
        self.interaction_significant = None
        self.method_note = note

    def recalculate(self) -> None:
        """Recalculate Gage R&R variance components using quality_core.msa."""
        if not self.measurements:
            self._reset_analysis_state()
            return

        records = [m.to_dict() for m in self.measurements]
        try:
            res = compute_gage_rr(records, method=self.method, tolerance=self.tolerance)
        except ValueError as err:
            self._reset_analysis_state(verdict="Pending", note=str(err))
            return

        self.basis = "AIAG MSA 4th Edition"
        self.ev = res["ev"]
        self.av = res["av"]
        self.grr = res["grr"]
        self.pv = res["pv"]
        self.tv = res["tv"]
        self.mean = res["mean"]
        self.pev_study = res["pev_study"]
        self.pav_study = res["pav_study"]
        self.pgrr_study = res["pgrr_study"]
        self.ppv_study = res["ppv_study"]
        self.pev_tolerance = res["pev_tolerance"]
        self.pav_tolerance = res["pav_tolerance"]
        self.pgrr_tolerance = res["pgrr_tolerance"]
        self.ppv_tolerance = res["ppv_tolerance"]
        self.ndc = res["ndc"]
        self.verdict = res["verdict"]
        self.n_parts = res["n_parts"]
        self.n_appraisers = res["n_appraisers"]
        self.n_trials = res["n_trials"]
        self.is_balanced = res["is_balanced"]
        self.interaction = res["interaction"]
        self.interaction_f = res["interaction_f"]
        self.interaction_significant = res["interaction_significant"]
        self.method_note = res["method_note"]

    def get_summary(self) -> dict[str, Any]:
        """Return high-level risk and statistical summary metrics dictionary."""
        return {
            "title": self.title,
            "method": self.method,
            "measurements_count": len(self.measurements),
            "n_parts": self.n_parts,
            "n_appraisers": self.n_appraisers,
            "n_trials": self.n_trials,
            "ev": self.ev,
            "av": self.av,
            "grr": self.grr,
            "pv": self.pv,
            "tv": self.tv,
            "pev_study": self.pev_study,
            "pav_study": self.pav_study,
            "pgrr_study": self.pgrr_study,
            "ppv_study": self.ppv_study,
            "pgrr_tolerance": self.pgrr_tolerance,
            "ndc": self.ndc,
            "verdict": self.verdict,
            "interaction_significant": self.interaction_significant,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete canvas state to dictionary."""
        return {
            "title": self.title,
            "method": self.method,
            "tolerance": self.tolerance,
            "measurements": [m.to_dict() for m in self.measurements],
            "summary": self.get_summary(),
        }

    @classmethod
    def load_sample(
        cls,
        method: str = METHOD_ANOVA,
        title: str = "AIAG MSA Gage R&R Canvas",
        tolerance: float | None = 4.42,
    ) -> MSACanvas:
        """Create and return an MSACanvas preloaded with the standard AIAG benchmark dataset."""
        return cls(
            method=method,
            title=title,
            tolerance=tolerance,
            measurements=SAMPLE_MSA_STUDY_DATA,
        )

    def _render_interaction_plot_svg(self, width: int = 700, height: int = 320) -> str:
        """Render the Operator x Part Interaction Plot SVG."""
        if not self.measurements:
            return f'<svg width="{width}" height="{height}" class="msa-svg"><text x="50%" y="50%" fill="{TEXT_SECONDARY}" text-anchor="middle">No measurement data</text></svg>'

        # Aggregate cell averages: (part, appraiser) -> average
        part_appraiser_sums: dict[tuple[str, str], list[float]] = {}
        unique_parts_set: set[str] = set()
        unique_appraisers_set: set[str] = set()

        for m in self.measurements:
            key = (m.part, m.appraiser)
            part_appraiser_sums.setdefault(key, []).append(m.measurement)
            unique_parts_set.add(m.part)
            unique_appraisers_set.add(m.appraiser)

        parts = sorted(unique_parts_set)
        appraisers = sorted(unique_appraisers_set)

        cell_means: dict[tuple[str, str], float] = {
            k: sum(vals) / len(vals) for k, vals in part_appraiser_sums.items()
        }

        all_means = list(cell_means.values())
        min_y = min(all_means) if all_means else 0.0
        max_y = max(all_means) if all_means else 1.0
        span_y = max_y - min_y
        if span_y < 1e-6:
            min_y -= 0.5
            max_y += 0.5
            span_y = 1.0
        else:
            padding = span_y * 0.15
            min_y -= padding
            max_y += padding
            span_y = max_y - min_y

        margin_left = 65
        margin_right = 140
        margin_top = 40
        margin_bottom = 50
        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        svg_parts: list[str] = []
        svg_parts.append(f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="msa-svg" xmlns="http://www.w3.org/2000/svg">')

        # Background
        svg_parts.append(f'<rect width="{width}" height="{height}" fill="{BG_SECONDARY}" rx="8" />')

        # Title
        int_status = ""
        if self.interaction_significant is not None:
            int_status = f" (Interaction: {'Significant' if self.interaction_significant else 'Not Significant'})"
        svg_parts.append(
            f'<text x="{margin_left}" y="24" fill="{TEXT_PRIMARY}" font-size="13" font-weight="600" font-family="Inter, sans-serif">'
            f'Operator × Part Interaction Plot{html.escape(int_status)}</text>'
        )

        # Axes and grid
        svg_parts.append(f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="{BORDER}" stroke-width="1" />')
        svg_parts.append(f'<line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" stroke="{BORDER}" stroke-width="1" />')

        # Y-axis ticks & grid lines (5 levels)
        for i in range(5):
            frac = i / 4.0
            val = min_y + (1.0 - frac) * span_y
            y_pos = margin_top + frac * plot_h
            svg_parts.append(f'<line x1="{margin_left}" y1="{y_pos:.1f}" x2="{margin_left + plot_w}" y2="{y_pos:.1f}" stroke="{BORDER}" stroke-dasharray="3,3" stroke-width="1" opacity="0.6" />')
            svg_parts.append(f'<text x="{margin_left - 8}" y="{y_pos + 4:.1f}" fill="{TEXT_SECONDARY}" font-size="10" text-anchor="end" font-family="Inter, sans-serif">{val:.2f}</text>')

        # X-axis part ticks
        x_step = plot_w / max(len(parts) - 1, 1) if len(parts) > 1 else plot_w / 2.0
        part_x_coords: dict[str, float] = {}

        for idx, part_name in enumerate(parts):
            x_pos = margin_left + idx * x_step if len(parts) > 1 else margin_left + plot_w / 2.0
            part_x_coords[part_name] = x_pos
            svg_parts.append(f'<line x1="{x_pos:.1f}" y1="{margin_top + plot_h}" x2="{x_pos:.1f}" y2="{margin_top + plot_h + 5}" stroke="{BORDER}" stroke-width="1" />')
            svg_parts.append(f'<text x="{x_pos:.1f}" y="{margin_top + plot_h + 20}" fill="{TEXT_SECONDARY}" font-size="10" text-anchor="middle" font-family="Inter, sans-serif">{html.escape(part_name)}</text>')

        # Appraiser lines and points
        for a_idx, appraiser_name in enumerate(appraisers):
            color = _APPRAISER_COLORS[a_idx % len(_APPRAISER_COLORS)]
            pts: list[tuple[float, float]] = []

            for part_name in parts:
                if (part_name, appraiser_name) in cell_means:
                    val = cell_means[(part_name, appraiser_name)]
                    x = part_x_coords[part_name]
                    y = margin_top + (1.0 - (val - min_y) / span_y) * plot_h
                    pts.append((x, y))

            if len(pts) > 1:
                path_d = " ".join([f"{'M' if i == 0 else 'L'} {p[0]:.1f} {p[1]:.1f}" for i, p in enumerate(pts)])
                svg_parts.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" />')

            for p in pts:
                svg_parts.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="4" fill="{color}" stroke="{BG_SECONDARY}" stroke-width="1.5" />')

            # Legend item
            leg_x = margin_left + plot_w + 16
            leg_y = margin_top + 20 + a_idx * 22
            svg_parts.append(f'<circle cx="{leg_x}" cy="{leg_y}" r="4" fill="{color}" />')
            svg_parts.append(f'<text x="{leg_x + 10}" y="{leg_y + 4}" fill="{TEXT_PRIMARY}" font-size="11" font-family="Inter, sans-serif">{html.escape(appraiser_name)}</text>')

        svg_parts.append('</svg>')
        return "\n".join(svg_parts)

    def _render_variance_breakdown_svg(self, width: int = 700, height: int = 240) -> str:
        """Render the Variance Components Breakdown horizontal bar chart SVG."""
        components: list[tuple[str, float, float | None, str]] = [
            ("Repeatability (EV)", self.pev_study, self.pev_tolerance, "#38bdf8"),
            ("Reproducibility (AV)", self.pav_study, self.pav_tolerance, AMBER),
        ]
        if self.method == METHOD_ANOVA and self.interaction is not None and self.interaction > 0:
            p_int_study = 100.0 * self.interaction / self.tv if self.tv > 0 else 0.0
            p_int_tol = 100.0 * 6.0 * self.interaction / self.tolerance if self.tolerance else None
            components.append(("Part × Appraiser (INT)", p_int_study, p_int_tol, VIOLET))

        components.append(("Total Gage R&R (GRR)", self.pgrr_study, self.pgrr_tolerance, DANGER if self.pgrr_study > 30 else (AMBER if self.pgrr_study >= 10 else SUCCESS)))
        components.append(("Part-to-Part (PV)", self.ppv_study, self.ppv_tolerance, SUCCESS))

        margin_left = 180
        margin_right = 50
        margin_top = 40
        margin_bottom = 40
        plot_w = width - margin_left - margin_right
        n_comps = len(components)
        bar_group_h = (height - margin_top - margin_bottom) / n_comps
        bar_h = min(16.0, bar_group_h * 0.35)

        svg_parts: list[str] = []
        svg_parts.append(f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" class="msa-svg" xmlns="http://www.w3.org/2000/svg">')
        svg_parts.append(f'<rect width="{width}" height="{height}" fill="{BG_SECONDARY}" rx="8" />')

        # Header Title & Legend
        has_tol = self.tolerance is not None
        svg_parts.append(
            f'<text x="{margin_left}" y="24" fill="{TEXT_PRIMARY}" font-size="13" font-weight="600" font-family="Inter, sans-serif">'
            f'Variance Component Breakdown (% Study Variation vs % Tolerance)</text>'
        )

        # Grid lines (0%, 20%, 40%, 60%, 80%, 100%)
        for pct in [0, 20, 40, 60, 80, 100]:
            x_pos = margin_left + (pct / 100.0) * plot_w
            svg_parts.append(f'<line x1="{x_pos:.1f}" y1="{margin_top}" x2="{x_pos:.1f}" y2="{height - margin_bottom}" stroke="{BORDER}" stroke-dasharray="3,3" stroke-width="1" opacity="0.6" />')
            svg_parts.append(f'<text x="{x_pos:.1f}" y="{height - margin_bottom + 15}" fill="{TEXT_SECONDARY}" font-size="10" text-anchor="middle" font-family="Inter, sans-serif">{pct}%</text>')

        # Bars
        for idx, (label, study_val, tol_val, color) in enumerate(components):
            y_base = margin_top + idx * bar_group_h + (bar_group_h - (bar_h * 2 if has_tol else bar_h)) / 2.0

            # Label
            svg_parts.append(f'<text x="{margin_left - 12}" y="{y_base + bar_h:.1f}" fill="{TEXT_PRIMARY}" font-size="11" text-anchor="end" font-family="Inter, sans-serif">{html.escape(label)}</text>')

            # Study variation bar
            w_study = max(0.0, min(plot_w, (study_val / 100.0) * plot_w))
            svg_parts.append(f'<rect x="{margin_left}" y="{y_base:.1f}" width="{w_study:.1f}" height="{bar_h:.1f}" fill="{color}" rx="3" opacity="0.9" />')
            svg_parts.append(f'<text x="{margin_left + w_study + 6:.1f}" y="{y_base + bar_h - 3:.1f}" fill="{TEXT_PRIMARY}" font-size="10" font-family="Inter, sans-serif">{study_val:.1f}% SV</text>')

            # Tolerance bar (if given)
            if has_tol and tol_val is not None:
                y_tol = y_base + bar_h + 3
                w_tol = max(0.0, min(plot_w, (tol_val / 100.0) * plot_w))
                svg_parts.append(f'<rect x="{margin_left}" y="{y_tol:.1f}" width="{w_tol:.1f}" height="{bar_h:.1f}" fill="{color}" stroke="{TEXT_PRIMARY}" stroke-width="1" stroke-dasharray="2,2" rx="3" opacity="0.55" />')
                svg_parts.append(f'<text x="{margin_left + w_tol + 6:.1f}" y="{y_tol + bar_h - 3:.1f}" fill="{TEXT_SECONDARY}" font-size="10" font-family="Inter, sans-serif">{tol_val:.1f}% Tol</text>')

        svg_parts.append('</svg>')
        return "\n".join(svg_parts)

    def to_html(self, standalone: bool = True) -> str:
        """Render complete styled HTML5 / SVG visual canvas artifact."""
        interaction_svg = self._render_interaction_plot_svg()
        variance_svg = self._render_variance_breakdown_svg()

        # Semantic styling for verdict badge
        if self.verdict == "Accept":
            badge_bg = "rgba(16, 185, 129, 0.15)"
            badge_color = SUCCESS
            badge_border = SUCCESS
            verdict_desc = "Acceptable (<10% %GRR, ndc ≥ 5)"
        elif self.verdict == "Marginal":
            badge_bg = "rgba(245, 158, 11, 0.15)"
            badge_color = AMBER
            badge_border = AMBER
            verdict_desc = "Marginal / Conditionally Acceptable (10%–30% %GRR)"
        elif self.verdict == "Reject":
            badge_bg = "rgba(239, 68, 68, 0.15)"
            badge_color = DANGER
            badge_border = DANGER
            verdict_desc = "Unacceptable / Needs Improvement (>30% %GRR or ndc < 2)"
        else:
            badge_bg = "rgba(148, 163, 184, 0.15)"
            badge_color = TEXT_SECONDARY
            badge_border = BORDER
            verdict_desc = "Pending Analysis"

        method_badge = "ANOVA (Two-Factor Crossed)" if self.method == METHOD_ANOVA else "Average & Range"

        content = f"""
<div class="msa-canvas-container" style="background-color: {BG_PRIMARY}; color: {TEXT_PRIMARY}; font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif; padding: 24px; border-radius: 12px; max-width: 900px; margin: 0 auto; box-sizing: border-box;">
  <!-- Header -->
  <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid {BORDER}; padding-bottom: 16px; margin-bottom: 20px;">
    <div>
      <h1 style="font-size: 20px; font-weight: 700; margin: 0 0 6px 0; color: {TEXT_PRIMARY};">{html.escape(self.title)}</h1>
      <div style="font-size: 12px; color: {TEXT_SECONDARY};">
        Basis: <span style="color: {TEXT_PRIMARY}; font-weight: 500;">{html.escape(self.basis)}</span> &bull;
        Method: <span style="color: {TEXT_PRIMARY}; font-weight: 500;">{html.escape(method_badge)}</span>
      </div>
    </div>
    <div style="background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_border}; padding: 6px 14px; border-radius: 9999px; font-size: 13px; font-weight: 600;">
      {html.escape(self.verdict.upper())}
    </div>
  </div>

  <!-- KPI Cards Grid -->
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-bottom: 20px;">
    <div style="background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px;">
      <div style="font-size: 11px; color: {TEXT_SECONDARY}; margin-bottom: 4px;">%GRR (Study)</div>
      <div style="font-size: 18px; font-weight: 700; color: {badge_color};">{self.pgrr_study:.2f}%</div>
    </div>
    <div style="background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px;">
      <div style="font-size: 11px; color: {TEXT_SECONDARY}; margin-bottom: 4px;">%GRR (Tolerance)</div>
      <div style="font-size: 18px; font-weight: 700; color: {TEXT_PRIMARY};">{'N/A' if self.pgrr_tolerance is None else f'{self.pgrr_tolerance:.2f}%'}</div>
    </div>
    <div style="background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px;">
      <div style="font-size: 11px; color: {TEXT_SECONDARY}; margin-bottom: 4px;">ndc (Categories)</div>
      <div style="font-size: 18px; font-weight: 700; color: {SUCCESS if self.ndc >= 5 else DANGER};">{self.ndc}</div>
    </div>
    <div style="background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 12px;">
      <div style="font-size: 11px; color: {TEXT_SECONDARY}; margin-bottom: 4px;">Study Layout</div>
      <div style="font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};">{self.n_parts}P &times; {self.n_appraisers}A &times; {self.n_trials}R</div>
    </div>
  </div>

  <!-- Charts Section -->
  <div style="display: flex; flex-direction: column; gap: 20px; margin-bottom: 20px;">
    <!-- Interaction Plot -->
    <div style="background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 16px; overflow-x: auto;">
      {interaction_svg}
    </div>

    <!-- Variance Components -->
    <div style="background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 16px; overflow-x: auto;">
      {variance_svg}
    </div>
  </div>

  <!-- Summary Description -->
  <div style="background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 14px; font-size: 12px; line-height: 1.5; color: {TEXT_SECONDARY};">
    <strong style="color: {TEXT_PRIMARY};">AIAG Evaluation:</strong> {html.escape(verdict_desc)}.<br />
    <strong style="color: {TEXT_PRIMARY};">Equipment Variation (EV):</strong> {self.ev:.4f} ({self.pev_study:.1f}% SV) &bull;
    <strong style="color: {TEXT_PRIMARY};">Appraiser Variation (AV):</strong> {self.av:.4f} ({self.pav_study:.1f}% SV) &bull;
    <strong style="color: {TEXT_PRIMARY};">Part Variation (PV):</strong> {self.pv:.4f} ({self.ppv_study:.1f}% SV).
  </div>
</div>
"""
        if not standalone:
            return content.strip()

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(self.title)}</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background-color: {BG_PRIMARY};
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    .msa-svg text {{
      user-select: none;
    }}
  </style>
</head>
<body>
  {content.strip()}
</body>
</html>"""


def load_sample_msa_canvas(
    method: str = METHOD_ANOVA,
    title: str = "AIAG MSA Gage R&R Canvas",
    tolerance: float | None = 4.42,
) -> MSACanvas:
    """Convenience helper to construct and return an MSACanvas with AIAG reference data."""
    return MSACanvas.load_sample(method=method, title=title, tolerance=tolerance)

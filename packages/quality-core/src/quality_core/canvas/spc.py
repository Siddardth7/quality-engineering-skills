"""
spc.py
Single-writer visual SPC Control Chart Canvas reference implementation for Quality Platform.

Provides `SPCCanvasSubgroup` and `SPCCanvas` controller for managing an in-memory
control chart with deterministic AIAG SPC 4th Edition calculations via `quality_core.spc`,
sample dataset loading, single-writer point/subgroup editing, and theme-aligned HTML/SVG
canvas rendering.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from typing import Any

from quality_core.spc.capability import compute_capability
from quality_core.spc.control_charts import (
    compute_c,
    compute_imr,
    compute_p,
    compute_u,
    compute_xbar_r,
    compute_xbar_s,
)
from quality_core.spc.rule_detection import detect_violations
from quality_core.spc.stability import stability_fields
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
)

# Standard AIAG SPC 4th Ed. Table II.1 benchmark dataset (20 subgroups of size 5)
SAMPLE_SPC_XBAR_R_DATA: list[list[float]] = [
    [10.1, 10.0, 9.9, 10.2, 9.8],
    [9.9, 10.1, 10.0, 10.0, 10.1],
    [10.2, 9.8, 10.1, 9.9, 10.0],
    [10.0, 10.0, 10.1, 10.2, 9.9],
    [9.8, 10.1, 10.0, 9.9, 10.2],
    [10.1, 10.2, 9.8, 10.0, 10.0],
    [10.0, 9.9, 10.1, 10.1, 10.0],
    [10.2, 10.0, 9.9, 10.1, 9.8],
    [9.9, 10.1, 10.0, 10.0, 10.2],
    [10.1, 9.8, 10.2, 10.0, 9.9],
    [10.0, 10.1, 9.9, 10.0, 10.1],
    [9.8, 10.0, 10.2, 10.1, 9.9],
    [10.1, 10.0, 10.0, 9.9, 10.2],
    [10.2, 9.9, 10.1, 10.0, 9.8],
    [9.9, 10.1, 10.0, 10.2, 10.0],
    [10.0, 9.8, 10.1, 10.0, 10.1],
    [10.1, 10.2, 9.9, 10.0, 9.9],
    [9.9, 10.0, 10.1, 10.2, 9.8],
    [10.0, 10.1, 10.0, 9.9, 10.1],
    [10.2, 9.9, 10.0, 10.1, 10.0],
]


@dataclass
class SPCCanvasSubgroup:
    """Represents an individual plotted subgroup or sample point in the SPC canvas."""

    id: int
    values: list[float]
    point_value: float = 0.0
    dispersion_value: float = 0.0
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary of the subgroup item."""
        return {
            "id": self.id,
            "values": list(self.values),
            "point_value": self.point_value,
            "dispersion_value": self.dispersion_value,
            "violations": list(self.violations),
        }


class SPCCanvas:
    """Single-writer SPC Control Chart Canvas controller.

    Manages control chart data, recalculates control limits and run rules deterministically
    via `quality_core.spc`, enforces the stability gate for process capability, supports
    single-writer point/subgroup editing, and generates styled HTML5/SVG canvas artifacts.
    """

    SUPPORTED_CHARTS: tuple[str, ...] = ("Xbar-R", "Xbar-S", "I-MR", "p", "c", "u")

    def __init__(
        self,
        chart_type: str = "Xbar-R",
        title: str = "AIAG SPC Control Chart Canvas",
        usl: float | None = None,
        lsl: float | None = None,
        rule_set: str = "Western Electric",
        sample_sizes: list[float] | None = None,
        data: list[list[float]] | list[float] | None = None,
    ) -> None:
        if isinstance(title, bool) or not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string.")
        if chart_type not in self.SUPPORTED_CHARTS:
            raise ValueError(f"Unknown or unsupported chart_type: {chart_type!r}. Supported: {self.SUPPORTED_CHARTS}")
        if usl is not None and lsl is not None and usl < lsl:
            raise ValueError("USL cannot be less than LSL.")

        self.title: str = title.strip()
        self.chart_type: str = chart_type
        self.usl: float | None = usl
        self.lsl: float | None = lsl
        self.rule_set: str = rule_set
        self.sample_sizes: list[float] | None = [float(x) for x in sample_sizes] if sample_sizes is not None else None

        self.data: list[list[float]] | list[float] = []
        self.subgroups: list[SPCCanvasSubgroup] = []
        self.center_line: float = 0.0
        self.ucl: float | list[float] = 0.0
        self.lcl: float | list[float] = 0.0
        self.dispersion_center: float = 0.0
        self.ucl_dispersion: float = 0.0
        self.lcl_dispersion: float = 0.0
        self.sigma_hat: float = 0.0
        self.points: list[float] = []
        self.dispersion_points: list[float] = []
        self.violations: list[dict[str, Any]] = []
        self.in_control: bool = True
        self.stable: bool | None = True
        self.stability_note: str | None = None
        self.capability: dict[str, Any] | None = None

        if data is not None:
            self.set_data(data, sample_sizes=sample_sizes)

    def set_data(
        self,
        data: list[list[float]] | list[float],
        sample_sizes: list[float] | None = None,
    ) -> None:
        """Load new dataset into the canvas and recalculate all metrics deterministically."""
        if sample_sizes is not None:
            self.sample_sizes = [float(x) for x in sample_sizes]

        if self.chart_type in {"Xbar-R", "Xbar-S"}:
            if not isinstance(data, list) or not data or not isinstance(data[0], list):
                raise ValueError(f"{self.chart_type} chart requires data as a list of subgroups (list[list[float]]).")
            sub_len = len(data[0])
            for sub in data:
                if not isinstance(sub, list) or len(sub) != sub_len:
                    raise ValueError(f"All subgroups in {self.chart_type} chart must have equal size.")
            if self.chart_type == "Xbar-R" and not (2 <= sub_len <= 10):
                raise ValueError("Xbar-R chart requires subgroup size between 2 and 10.")
            if self.chart_type == "Xbar-S" and not (2 <= sub_len <= 12):
                raise ValueError("Xbar-S chart requires subgroup size between 2 and 12.")

            self.data = [[float(x) for x in sub] for sub in data]
        else:
            if not isinstance(data, list) or not data or isinstance(data[0], list):
                raise ValueError(f"{self.chart_type} chart requires data as a 1D list of values (list[float]).")
            if self.chart_type in {"p", "u"} and self.sample_sizes is None:
                raise ValueError(f"{self.chart_type} chart requires sample_sizes.")
            if self.chart_type == "I-MR" and len(data) < 2:
                raise ValueError("I-MR chart requires at least two values.")

            self.data = [float(x) for x in data]

        self._recalculate()

    def _recalculate(self) -> None:
        """Recalculate control chart limits, stability, run-rule violations, and capability."""
        if not self.data:
            return

        raw_values: list[float] = []

        if self.chart_type == "Xbar-R":
            subgroups_2d: list[list[float]] = self.data  # type: ignore[assignment]
            xr = compute_xbar_r(subgroups_2d)
            self.points = xr["subgroup_means"]
            self.dispersion_points = xr["ranges"]
            self.center_line = xr["xbarbar"]
            self.ucl = xr["ucl_x"]
            self.lcl = xr["lcl_x"]
            self.dispersion_center = xr["rbar"]
            self.ucl_dispersion = xr["ucl_r"]
            self.lcl_dispersion = xr["lcl_r"]
            self.sigma_hat = xr["sigma_hat"]
            subgroup_size = len(subgroups_2d[0])
            sigma_points = self.sigma_hat / math.sqrt(subgroup_size)
            raw_values = [x for sub in subgroups_2d for x in sub]

        elif self.chart_type == "Xbar-S":
            subgroups_2d = self.data  # type: ignore[assignment]
            xs = compute_xbar_s(subgroups_2d)
            self.points = xs["subgroup_means"]
            self.dispersion_points = xs["std_devs"]
            self.center_line = xs["xbarbar"]
            self.ucl = xs["ucl_x"]
            self.lcl = xs["lcl_x"]
            self.dispersion_center = xs["sbar"]
            self.ucl_dispersion = xs["ucl_s"]
            self.lcl_dispersion = xs["lcl_s"]
            self.sigma_hat = xs["sigma_hat"]
            subgroup_size = len(subgroups_2d[0])
            sigma_points = self.sigma_hat / math.sqrt(subgroup_size)
            raw_values = [x for sub in subgroups_2d for x in sub]

        elif self.chart_type == "I-MR":
            values_1d: list[float] = self.data  # type: ignore[assignment]
            im = compute_imr(values_1d)
            self.points = im["values"]
            self.dispersion_points = im["moving_ranges"]
            self.center_line = im["xbar"]
            self.ucl = im["ucl_x"]
            self.lcl = im["lcl_x"]
            self.dispersion_center = im["mrbar"]
            self.ucl_dispersion = im["ucl_mr"]
            self.lcl_dispersion = im["lcl_mr"]
            self.sigma_hat = im["sigma_hat"]
            sigma_points = self.sigma_hat
            raw_values = values_1d

        elif self.chart_type == "p":
            counts_1d: list[float] = self.data  # type: ignore[assignment]
            assert self.sample_sizes is not None
            p_res = compute_p(counts_1d, self.sample_sizes)
            self.points = p_res["proportions"]
            self.dispersion_points = []
            self.center_line = p_res["pbar"]
            self.ucl = p_res["ucl"]
            self.lcl = p_res["lcl"]
            self.dispersion_center = 0.0
            self.ucl_dispersion = 0.0
            self.lcl_dispersion = 0.0
            self.sigma_hat = 0.0
            sigma_points = 0.0

        elif self.chart_type == "c":
            counts_1d = self.data  # type: ignore[assignment]
            c_res = compute_c(counts_1d)
            self.points = c_res["counts"]
            self.dispersion_points = []
            self.center_line = c_res["cbar"]
            self.ucl = c_res["ucl"]
            self.lcl = c_res["lcl"]
            self.dispersion_center = 0.0
            self.ucl_dispersion = 0.0
            self.lcl_dispersion = 0.0
            self.sigma_hat = 0.0
            sigma_points = 0.0

        else:
            counts_1d = self.data  # type: ignore[assignment]
            assert self.sample_sizes is not None
            u_res = compute_u(counts_1d, self.sample_sizes)
            self.points = u_res["u_values"]
            self.dispersion_points = []
            self.center_line = u_res["ubar"]
            self.ucl = u_res["ucl"]
            self.lcl = u_res["lcl"]
            self.dispersion_center = 0.0
            self.ucl_dispersion = 0.0
            self.lcl_dispersion = 0.0
            self.sigma_hat = 0.0
            sigma_points = 0.0

        # Run-rule detection
        if sigma_points > 0:
            self.violations = detect_violations(
                self.chart_type,
                self.points,
                cl=self.center_line,
                sigma=sigma_points,
                rule_set=self.rule_set,
            )
        else:
            self.violations = []

        self.in_control = len(self.violations) == 0
        stable_flag, self.stability_note = stability_fields(self.violations)
        self.stable = stable_flag is True

        # Build subgroup objects
        violation_indices: dict[int, list[str]] = {}
        for v in self.violations:
            idx = int(v.get("index", v.get("point_index", 0)))
            violation_indices.setdefault(idx, []).append(str(v["rule"]))

        self.subgroups = []
        if isinstance(self.data[0], list):
            for i, sub in enumerate(self.data):
                disp_val = self.dispersion_points[i] if i < len(self.dispersion_points) else 0.0
                self.subgroups.append(
                    SPCCanvasSubgroup(
                        id=i + 1,
                        values=list(sub),  # type: ignore[arg-type]
                        point_value=self.points[i],
                        dispersion_value=disp_val,
                        violations=violation_indices.get(i, []),
                    )
                )
        else:
            for i, val in enumerate(self.data):
                disp_val = self.dispersion_points[i] if i < len(self.dispersion_points) else 0.0
                self.subgroups.append(
                    SPCCanvasSubgroup(
                        id=i + 1,
                        values=[float(val)],  # type: ignore[list-item]
                        point_value=self.points[i],
                        dispersion_value=disp_val,
                        violations=violation_indices.get(i, []),
                    )
                )

        # Capability calculation: strictly stability-gated
        self.capability = None
        if self.chart_type in {"Xbar-R", "Xbar-S", "I-MR"}:
            if self.usl is not None or self.lsl is not None:
                if self.in_control:
                    cap_res = compute_capability(
                        data=raw_values,
                        lsl=self.lsl,
                        usl=self.usl,
                        sigma_hat=self.sigma_hat,
                    )
                    self.capability = {
                        "cp": cap_res["cp"],
                        "cpk": cap_res["cpk"],
                        "pp": cap_res["pp"],
                        "ppk": cap_res["ppk"],
                        "mean": cap_res["mean"],
                        "sigma_hat": cap_res["sigma_hat"],
                        "sigma_overall": cap_res["sigma_overall"],
                        "n": cap_res["n"],
                        "pp_ci": cap_res["pp_ci"],
                        "ppk_ci": cap_res["ppk_ci"],
                        "ppk_lower": cap_res["ppk_lower"],
                    }

    def edit_subgroup(self, index: int, new_values: list[float]) -> None:
        """Single-writer edit: update a subgroup at 0-indexed position and recalculate."""
        if not isinstance(index, int) or index < 0 or index >= len(self.data):
            raise IndexError(f"Subgroup index {index} out of range [0, {len(self.data) - 1}].")
        if not isinstance(new_values, list) or not new_values:
            raise ValueError("new_values must be a non-empty list of floats.")
        if self.chart_type in {"Xbar-R", "Xbar-S"}:
            subgroups_list: list[list[float]] = self.data  # type: ignore[assignment]
            expected_len = len(subgroups_list[0])
            if len(new_values) != expected_len:
                raise ValueError(f"Subgroup size mismatch: expected {expected_len}, got {len(new_values)}.")
            subgroups_list[index] = [float(x) for x in new_values]
        else:
            raise TypeError(f"edit_subgroup is for 2D charts (Xbar-R, Xbar-S). Use edit_point for {self.chart_type}.")

        self._recalculate()

    def edit_point(self, index: int, new_value: float) -> None:
        """Single-writer edit: update an individual point at 0-indexed position and recalculate."""
        if not isinstance(index, int) or index < 0 or index >= len(self.data):
            raise IndexError(f"Point index {index} out of range [0, {len(self.data) - 1}].")
        if self.chart_type in {"Xbar-R", "Xbar-S"}:
            raise TypeError(f"edit_point is for 1D charts (I-MR, p, c, u). Use edit_subgroup for {self.chart_type}.")

        points_list: list[float] = self.data  # type: ignore[assignment]
        points_list[index] = float(new_value)
        self._recalculate()

    def get_summary(self) -> dict[str, Any]:
        """Return summary statistics of the current control chart state."""
        return {
            "title": self.title,
            "chart_type": self.chart_type,
            "points_count": len(self.points),
            "in_control": self.in_control,
            "stable": self.stable,
            "violations_count": len(self.violations),
            "violations": list(self.violations),
            "stability_note": self.stability_note,
            "center_line": self.center_line,
            "ucl": self.ucl,
            "lcl": self.lcl,
            "sigma_hat": self.sigma_hat,
            "capability": self.capability,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return full serializable state dictionary."""
        summary = self.get_summary()
        summary["subgroups"] = [s.to_dict() for s in self.subgroups]
        summary["data"] = self.data
        return summary

    def to_html(self, standalone: bool = True) -> str:
        """Generate Quality Platform dark theme HTML5 canvas view with SVG control chart curves."""
        title_esc = html.escape(self.title)
        chart_type_esc = html.escape(self.chart_type)

        # Status badge
        if self.in_control:
            status_badge = f'<span style="background: {SUCCESS}22; color: {SUCCESS}; border: 1px solid {SUCCESS}44; padding: 4px 12px; border-radius: 9999px; font-weight: 600; font-size: 0.875rem;">IN CONTROL</span>'
        else:
            status_badge = f'<span style="background: {DANGER}22; color: {DANGER}; border: 1px solid {DANGER}44; padding: 4px 12px; border-radius: 9999px; font-weight: 600; font-size: 0.875rem;">OUT OF CONTROL</span>'

        # Capability summary card
        if self.capability:
            cp_str = f"{self.capability['cp']:.3f}" if self.capability.get("cp") is not None else "N/A"
            cpk_str = f"{self.capability['cpk']:.3f}" if self.capability.get("cpk") is not None else "N/A"
            pp_str = f"{self.capability['pp']:.3f}" if self.capability.get("pp") is not None else "N/A"
            ppk_str = f"{self.capability['ppk']:.3f}" if self.capability.get("ppk") is not None else "N/A"
            cap_card = f"""
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px;">
                <div style="background: {BG_PRIMARY}; border: 1px solid {BORDER}; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: {TEXT_SECONDARY}; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">Cp</div>
                    <div style="color: {TEXT_PRIMARY}; font-size: 1.25rem; font-weight: 700; margin-top: 4px;">{cp_str}</div>
                </div>
                <div style="background: {BG_PRIMARY}; border: 1px solid {BORDER}; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: {TEXT_SECONDARY}; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">Cpk</div>
                    <div style="color: {TEXT_PRIMARY}; font-size: 1.25rem; font-weight: 700; margin-top: 4px;">{cpk_str}</div>
                </div>
                <div style="background: {BG_PRIMARY}; border: 1px solid {BORDER}; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: {TEXT_SECONDARY}; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">Pp</div>
                    <div style="color: {TEXT_PRIMARY}; font-size: 1.25rem; font-weight: 700; margin-top: 4px;">{pp_str}</div>
                </div>
                <div style="background: {BG_PRIMARY}; border: 1px solid {BORDER}; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="color: {TEXT_SECONDARY}; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">Ppk</div>
                    <div style="color: {TEXT_PRIMARY}; font-size: 1.25rem; font-weight: 700; margin-top: 4px;">{ppk_str}</div>
                </div>
            </div>
            """
        elif not self.in_control:
            cap_card = f"""
            <div style="background: {DANGER}11; border: 1px solid {DANGER}33; border-radius: 8px; padding: 12px 16px; margin-top: 16px; color: {DANGER}; font-size: 0.875rem;">
                <strong>Stability Gate Notice:</strong> {html.escape(self.stability_note or "Process is not in statistical control. Capability metrics withheld.")}
            </div>
            """
        else:
            cap_card = ""

        # SVG Chart Generation
        svg_chart = self._generate_svg_chart()

        # Data Subgroups Table
        rows_html: list[str] = []
        for sub in self.subgroups:
            vals_str = ", ".join(f"{v:.2f}" for v in sub.values)
            violation_str = ", ".join(sub.violations) if sub.violations else '<span style="color: ' + SUCCESS + ';">In Control</span>'
            row_bg = f"{DANGER}15" if sub.violations else "transparent"
            rows_html.append(
                f'<tr style="background: {row_bg}; border-bottom: 1px solid {BORDER};">'
                f'<td style="padding: 8px 12px; text-align: center; color: {TEXT_SECONDARY};">{sub.id}</td>'
                f'<td style="padding: 8px 12px; color: {TEXT_PRIMARY}; font-family: monospace;">{vals_str}</td>'
                f'<td style="padding: 8px 12px; text-align: right; color: {TEXT_PRIMARY}; font-weight: 600;">{sub.point_value:.3f}</td>'
                f'<td style="padding: 8px 12px; text-align: right; color: {TEXT_SECONDARY};">{sub.dispersion_value:.3f}</td>'
                f'<td style="padding: 8px 12px; color: {DANGER if sub.violations else SUCCESS};">{violation_str}</td>'
                f"</tr>"
            )
        table_body = "\n".join(rows_html)

        body_content = f"""
        <div style="background: {BG_PRIMARY}; color: {TEXT_PRIMARY}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; min-height: 100vh;">
            <div style="max-width: 1100px; margin: 0 auto;">
                <!-- Header Card -->
                <div style="background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 20px 24px; margin-bottom: 24px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="color: {TEXT_SECONDARY}; font-size: 0.8125rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">AIAG SPC 4th Edition · Control Chart Canvas</div>
                            <h1 style="font-size: 1.5rem; font-weight: 700; margin: 4px 0 0 0; color: {TEXT_PRIMARY};">{title_esc}</h1>
                        </div>
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span style="background: {BG_SECONDARY}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER}; padding: 4px 10px; border-radius: 6px; font-size: 0.8125rem; font-weight: 600;">{chart_type_esc}</span>
                            {status_badge}
                        </div>
                    </div>
                    {cap_card}
                </div>

                <!-- SVG Visual Canvas Card -->
                <div style="background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 20px; margin-bottom: 24px;">
                    <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem; font-weight: 600; margin-bottom: 12px;">Primary Control Chart View</div>
                    <div style="overflow-x: auto;">
                        {svg_chart}
                    </div>
                </div>

                <!-- Data Table Card -->
                <div style="background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 20px;">
                    <div style="color: {TEXT_SECONDARY}; font-size: 0.875rem; font-weight: 600; margin-bottom: 12px;">Subgroup Observations & Run-Rule Diagnostics ({len(self.subgroups)} Points)</div>
                    <div style="overflow-x: auto;">
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
                            <thead>
                                <tr style="border-bottom: 2px solid {BORDER}; text-align: left; color: {TEXT_SECONDARY}; font-size: 0.75rem; text-transform: uppercase;">
                                    <th style="padding: 8px 12px; text-align: center; width: 60px;">#</th>
                                    <th style="padding: 8px 12px;">Observations</th>
                                    <th style="padding: 8px 12px; text-align: right;">Plotted Value</th>
                                    <th style="padding: 8px 12px; text-align: right;">Dispersion</th>
                                    <th style="padding: 8px 12px;">Stability Assessment</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table_body}
                            </tbody>
                        </table>
                    </div>
                </div>
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
    <title>{title_esc}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ background: {BG_PRIMARY}; color: {TEXT_PRIMARY}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    </style>
</head>
<body>
{body_content}
</body>
</html>"""

    def _generate_svg_chart(self) -> str:
        """Generate inline SVG chart visualizing control limits and plotted points."""
        if not self.points:
            return '<div style="color: #64748b; padding: 20px; text-align: center;">No data to display.</div>'

        width = 900
        height = 320
        margin_left = 70
        margin_right = 60
        margin_top = 30
        margin_bottom = 40
        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        # Determine y range
        ucl_val = self.ucl[0] if isinstance(self.ucl, list) else self.ucl
        lcl_val = self.lcl[0] if isinstance(self.lcl, list) else self.lcl
        y_vals = list(self.points) + [self.center_line, ucl_val, lcl_val]
        y_min = min(y_vals)
        y_max = max(y_vals)
        y_pad = (y_max - y_min) * 0.15 if y_max > y_min else 1.0
        y_min -= y_pad
        y_max += y_pad

        def to_y(val: float) -> float:
            return margin_top + (y_max - val) / (y_max - y_min) * plot_h

        n_pts = len(self.points)
        x_step = plot_w / (n_pts - 1) if n_pts > 1 else plot_w / 2

        def to_x(i: int) -> float:
            if n_pts <= 1:
                return margin_left + plot_w / 2
            return margin_left + i * x_step

        cl_y = to_y(self.center_line)
        ucl_y = to_y(ucl_val)
        lcl_y = to_y(lcl_val)

        # SVG elements
        elements: list[str] = []

        # Background grid rect
        elements.append(
            f'<rect x="{margin_left}" y="{margin_top}" width="{plot_w}" height="{plot_h}" fill="{BG_PRIMARY}" rx="6"/>'
        )

        # Control limit lines
        elements.append(
            f'<line x1="{margin_left}" y1="{ucl_y}" x2="{margin_left + plot_w}" y2="{ucl_y}" stroke="{DANGER}" stroke-dasharray="4,4" stroke-width="1.5"/>'
        )
        elements.append(
            f'<text x="{margin_left + plot_w + 8}" y="{ucl_y + 4}" fill="{DANGER}" font-size="11" font-weight="600">UCL {ucl_val:.2f}</text>'
        )

        elements.append(
            f'<line x1="{margin_left}" y1="{cl_y}" x2="{margin_left + plot_w}" y2="{cl_y}" stroke="{SUCCESS}" stroke-width="1.5"/>'
        )
        elements.append(
            f'<text x="{margin_left + plot_w + 8}" y="{cl_y + 4}" fill="{SUCCESS}" font-size="11" font-weight="600">CL {self.center_line:.2f}</text>'
        )

        elements.append(
            f'<line x1="{margin_left}" y1="{lcl_y}" x2="{margin_left + plot_w}" y2="{lcl_y}" stroke="{DANGER}" stroke-dasharray="4,4" stroke-width="1.5"/>'
        )
        elements.append(
            f'<text x="{margin_left + plot_w + 8}" y="{lcl_y + 4}" fill="{DANGER}" font-size="11" font-weight="600">LCL {lcl_val:.2f}</text>'
        )

        # Connect points with line
        pts_coords = [(to_x(i), to_y(pt)) for i, pt in enumerate(self.points)]
        poly_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_coords)
        elements.append(f'<polyline points="{poly_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

        # Plotted points & violation circles
        violation_indices = {int(v.get("index", v.get("point_index", 0))) for v in self.violations}
        for i, (px, py) in enumerate(pts_coords):
            is_ooc = i in violation_indices
            pt_color = DANGER if is_ooc else "#38bdf8"
            elements.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{pt_color}" stroke="{BG_CARD}" stroke-width="1.5"/>')
            if is_ooc:
                elements.append(
                    f'<circle cx="{px:.1f}" cy="{py:.1f}" r="8" fill="none" stroke="{AMBER}" stroke-width="1.5" stroke-dasharray="2,2"/>'
                )

            # X-axis label
            if n_pts <= 25 or i % max(1, n_pts // 15) == 0:
                elements.append(f'<text x="{px:.1f}" y="{margin_top + plot_h + 18}" fill="{TEXT_SECONDARY}" font-size="10" text-anchor="middle">{i + 1}</text>')

        return f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" style="overflow: visible;">\n' + "\n".join(elements) + "\n</svg>"

    @classmethod
    def load_sample(
        cls,
        chart_type: str = "Xbar-R",
        title: str = "AIAG SPC Control Chart Canvas",
        usl: float | None = 11.0,
        lsl: float | None = 9.0,
    ) -> SPCCanvas:
        """Load benchmark sample dataset into SPCCanvas controller."""
        return cls(
            chart_type=chart_type,
            title=title,
            usl=usl,
            lsl=lsl,
            data=SAMPLE_SPC_XBAR_R_DATA,
        )


def load_sample_spc_canvas(
    chart_type: str = "Xbar-R",
    title: str = "AIAG SPC Control Chart Canvas",
    usl: float | None = 11.0,
    lsl: float | None = 9.0,
) -> SPCCanvas:
    """Convenience helper to construct and return an SPCCanvas loaded with benchmark sample data."""
    return SPCCanvas.load_sample(chart_type=chart_type, title=title, usl=usl, lsl=lsl)


__all__ = [
    "SAMPLE_SPC_XBAR_R_DATA",
    "SPCCanvas",
    "SPCCanvasSubgroup",
    "load_sample_spc_canvas",
]

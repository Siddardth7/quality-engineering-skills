"""
spc.py
FastMCP tool for Statistical Process Control (SPC) chart calculations and stability-gated capability analysis.

Wraps deterministic engines from quality_core.spc without introducing UI or heavy dependencies.
Standards basis: AIAG Statistical Process Control (SPC) Reference Manual (4th Edition, 2005).
"""

from __future__ import annotations

import math
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


def calculate_spc_chart(
    chart_type: str,
    data: list[list[float]] | list[float],
    usl: float | None = None,
    lsl: float | None = None,
    sample_sizes: list[float] | None = None,
    rule_set: str = "Western Electric",
) -> dict[str, Any]:
    """Calculate SPC control chart limits, run-rule violations, and stability-gated capability.

    Parameters:
        chart_type: The control chart type ("Xbar-R", "Xbar-S", "I-MR", "p", "c", "u").
        data: Subgroups (list of lists of floats for Xbar-R/Xbar-S) or individual values/counts (list of floats for I-MR/p/c/u).
        usl: Optional Upper Specification Limit.
        lsl: Optional Lower Specification Limit.
        sample_sizes: Optional sample sizes per subgroup for attribute charts with varying sizes (p, u).
        rule_set: Run-rule set to evaluate ("Western Electric" or "Nelson"). Defaults to "Western Electric".

    Returns:
        Structured dictionary containing control limits, plotted points, run-rule violations,
        stability evaluation, and (when stable and spec limits provided) process capability indices.
    """
    if usl is not None and lsl is not None and usl < lsl:
        raise ValueError("USL cannot be less than LSL.")

    basis = "AIAG SPC 4th Edition"

    if chart_type == "Xbar-R":
        if not isinstance(data, list) or not data or not isinstance(data[0], list):
            raise ValueError("Xbar-R chart requires data as a list of subgroups (list[list[float]]).")
        subgroups: list[list[float]] = data  # type: ignore[assignment]
        subgroup_size = len(subgroups[0])
        if any(len(sub) != subgroup_size for sub in subgroups):
            raise ValueError("All subgroups in Xbar-R chart must have equal size.")
        if subgroup_size < 2 or subgroup_size > 10:
            raise ValueError("X-bar R chart requires subgroup size between 2 and 10.")

        xr = compute_xbar_r(subgroups)
        points = xr["subgroup_means"]
        dispersion_points = xr["ranges"]
        cl = xr["xbarbar"]
        ucl = xr["ucl_x"]
        lcl = xr["lcl_x"]
        dispersion_cl = xr["rbar"]
        ucl_disp = xr["ucl_r"]
        lcl_disp = xr["lcl_r"]
        sigma_hat = xr["sigma_hat"]
        sigma_points = sigma_hat / math.sqrt(subgroup_size)
        raw_values = [float(x) for sub in subgroups for x in sub]

    elif chart_type == "Xbar-S":
        if not isinstance(data, list) or not data or not isinstance(data[0], list):
            raise ValueError("Xbar-S chart requires data as a list of subgroups (list[list[float]]).")
        subgroups = data  # type: ignore[assignment]
        subgroup_size = len(subgroups[0])
        if any(len(sub) != subgroup_size for sub in subgroups):
            raise ValueError("All subgroups in Xbar-S chart must have equal size.")
        if subgroup_size < 2 or subgroup_size > 12:
            raise ValueError("X-bar S chart requires subgroup size between 2 and 12.")

        xs = compute_xbar_s(subgroups)
        points = xs["subgroup_means"]
        dispersion_points = xs["std_devs"]
        cl = xs["xbarbar"]
        ucl = xs["ucl_x"]
        lcl = xs["lcl_x"]
        dispersion_cl = xs["sbar"]
        ucl_disp = xs["ucl_s"]
        lcl_disp = xs["lcl_s"]
        sigma_hat = xs["sigma_hat"]
        sigma_points = sigma_hat / math.sqrt(subgroup_size)
        raw_values = [float(x) for sub in subgroups for x in sub]

    elif chart_type == "I-MR":
        if not isinstance(data, list) or not data or isinstance(data[0], list):
            raise ValueError("I-MR chart requires data as a 1D list of values (list[float]).")
        values: list[float] = [float(x) for x in data]  # type: ignore[union-attr]
        if len(values) < 2:
            raise ValueError("I-MR chart requires at least two values.")

        im = compute_imr(values)
        points = im["values"]
        dispersion_points = im["moving_ranges"]
        cl = im["xbar"]
        ucl = im["ucl_x"]
        lcl = im["lcl_x"]
        dispersion_cl = im["mrbar"]
        ucl_disp = im["ucl_mr"]
        lcl_disp = im["lcl_mr"]
        sigma_hat = im["sigma_hat"]
        sigma_points = sigma_hat
        raw_values = values

    elif chart_type == "p":
        if not isinstance(data, list) or not data or isinstance(data[0], list):
            raise ValueError("p chart requires data as a list of defective counts (list[float]).")
        if sample_sizes is None:
            raise ValueError("p chart requires sample_sizes.")
        counts = [float(x) for x in data]  # type: ignore[union-attr]
        sizes = [float(x) for x in sample_sizes]
        p_res = compute_p(counts, sizes)
        points = p_res["proportions"]
        dispersion_points = []
        cl = p_res["pbar"]
        ucl = p_res["ucl"]  # type: ignore[assignment]
        lcl = p_res["lcl"]  # type: ignore[assignment]
        dispersion_cl = 0.0
        ucl_disp = 0.0
        lcl_disp = 0.0
        sigma_hat = 0.0
        sigma_points = 0.0
        raw_values = []

    elif chart_type == "c":
        if not isinstance(data, list) or not data or isinstance(data[0], list):
            raise ValueError("c chart requires data as a list of defect counts (list[float]).")
        counts = [float(x) for x in data]  # type: ignore[union-attr]
        c_res = compute_c(counts)
        points = c_res["counts"]
        dispersion_points = []
        cl = c_res["cbar"]
        ucl = c_res["ucl"]
        lcl = c_res["lcl"]
        dispersion_cl = 0.0
        ucl_disp = 0.0
        lcl_disp = 0.0
        sigma_hat = 0.0
        sigma_points = 0.0
        raw_values = []

    elif chart_type == "u":
        if not isinstance(data, list) or not data or isinstance(data[0], list):
            raise ValueError("u chart requires data as a list of defect counts (list[float]).")
        if sample_sizes is None:
            raise ValueError("u chart requires sample_sizes.")
        counts = [float(x) for x in data]  # type: ignore[union-attr]
        sizes = [float(x) for x in sample_sizes]
        u_res = compute_u(counts, sizes)
        points = u_res["u_values"]
        dispersion_points = []
        cl = u_res["ubar"]
        ucl = u_res["ucl"]  # type: ignore[assignment]
        lcl = u_res["lcl"]  # type: ignore[assignment]
        dispersion_cl = 0.0
        ucl_disp = 0.0
        lcl_disp = 0.0
        sigma_hat = 0.0
        sigma_points = 0.0
        raw_values = []

    else:
        raise ValueError(
            f"Unknown or unsupported chart_type: {chart_type!r}. "
            "Supported: 'Xbar-R', 'Xbar-S', 'I-MR', 'p', 'c', 'u'."
        )

    # Run-rule detection for Shewhart charts
    if sigma_points > 0:
        violations = detect_violations(chart_type, points, cl=cl, sigma=sigma_points, rule_set=rule_set)
    else:
        violations = []

    in_control = len(violations) == 0
    stable, stability_note = stability_fields(violations)

    # Capability calculation: strictly stability-gated
    capability: dict[str, Any] | None = None
    if chart_type in {"Xbar-R", "Xbar-S", "I-MR"}:
        if usl is not None or lsl is not None:
            if in_control:
                cap_res = compute_capability(data=raw_values, lsl=lsl, usl=usl, sigma_hat=sigma_hat)
                capability = {
                    "cp": cap_res["cp"],
                    "cpk": cap_res["cpk"],
                    "pp": cap_res["pp"],
                    "ppk": cap_res["ppk"],
                    "mean": cap_res["mean"],
                    "sigma_hat": cap_res["sigma_hat"],
                    "sigma_overall": cap_res["sigma_overall"],
                    "n": cap_res["n"],
                    "alpha": cap_res["alpha"],
                    "pp_ci": cap_res["pp_ci"],
                    "ppk_ci": cap_res["ppk_ci"],
                    "ppk_lower": cap_res["ppk_lower"],
                    "ci_estimator": cap_res["ci_estimator"],
                    "ci_df": cap_res["ci_df"],
                }
            else:
                capability = None  # Stability gate holds!

    return {
        "chart_type": chart_type,
        "basis": basis,
        "center_line": cl,
        "ucl": ucl,
        "lcl": lcl,
        "dispersion_center": dispersion_cl,
        "ucl_dispersion": ucl_disp,
        "lcl_dispersion": lcl_disp,
        "sigma_hat": sigma_hat,
        "points": points,
        "dispersion_points": dispersion_points,
        "violations": violations,
        "in_control": in_control,
        "stable": stable,
        "stability_note": stability_note,
        "capability": capability,
    }


__all__ = ["calculate_spc_chart"]

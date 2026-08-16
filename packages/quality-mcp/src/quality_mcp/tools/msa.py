"""
msa.py
FastMCP tool for Measurement Systems Analysis (MSA) Gage R&R calculations.

Wraps deterministic engines from quality_core.msa without introducing UI or heavy dependencies.
Standards basis: AIAG Measurement Systems Analysis (MSA) Reference Manual (4th Edition).
"""

from __future__ import annotations

from typing import Any

from quality_core.msa import (
    METHOD_ANOVA,
    compute_gage_rr,
)


def calculate_gage_rr(
    measurements: list[dict[str, Any]],
    method: str = METHOD_ANOVA,
    tolerance: float | None = None,
) -> dict[str, Any]:
    """Calculate Gage R&R metrics for crossed measurement studies per AIAG MSA (4th Edition).

    Parameters:
        measurements: Crossed gage study data as a list of dicts with keys:
            - "part": str or identifier of the part/sample being measured
            - "appraiser": str or identifier of the operator/appraiser
            - "trial": int replicate number (1, 2, ...)
            - "measurement": float numeric observed value
        method: Calculation technique: "anova" (crossed two-factor with interaction, default)
            or "average_and_range" (arithmetic range method without interaction estimation).
        tolerance: Optional process tolerance width (USL - LSL). If provided, calculates
            %EV, %AV, %GRR, and %PV scaled by the AIAG 6-sigma study variation multiplier.

    Returns:
        Structured dictionary containing:
        - basis: Standards attribution string ("AIAG MSA 4th Edition")
        - ev: Equipment Variation (Repeatability, 1-sigma)
        - av: Appraiser Variation (Reproducibility, 1-sigma)
        - grr: Gage R&R standard deviation
        - pv: Part Variation (1-sigma)
        - tv: Total Variation (1-sigma)
        - mean: Overall study mean
        - pev_study: %EV vs study variation (100 * EV / TV)
        - pav_study: %AV vs study variation (100 * AV / TV)
        - pgrr_study: %GRR vs study variation (100 * GRR / TV)
        - ppv_study: %PV vs study variation (100 * PV / TV)
        - pev_tolerance: %EV vs tolerance (100 * 6 * EV / tolerance), or None if tolerance omitted
        - pav_tolerance: %AV vs tolerance (100 * 6 * AV / tolerance), or None if tolerance omitted
        - pgrr_tolerance: %GRR vs tolerance (100 * 6 * GRR / tolerance), or None if tolerance omitted
        - ppv_tolerance: %PV vs tolerance (100 * 6 * PV / tolerance), or None if tolerance omitted
        - ndc: Number of Distinct Categories (integer)
        - verdict: AIAG acceptance status ("Accept", "Marginal", "Reject")
        - n_parts: Number of unique parts
        - n_appraisers: Number of unique appraisers
        - n_trials: Number of trials per cell
        - is_balanced: True if all (part, appraiser) cells have identical trial counts
        - method: The technique used ("anova" or "average_and_range")
        - method_note: Standards context and limitations of the selected method
        - interaction: Interaction standard deviation (None for average_and_range)
        - interaction_f: ANOVA interaction F-test statistic (None for average_and_range)
        - interaction_significant: Whether interaction F exceeds critical value at alpha=0.05 (None for average_and_range)
    """
    basis = "AIAG MSA 4th Edition"

    res = compute_gage_rr(data=measurements, tolerance=tolerance, method=method)

    return {
        "basis": basis,
        "ev": res["ev"],
        "av": res["av"],
        "grr": res["grr"],
        "pv": res["pv"],
        "tv": res["tv"],
        "mean": res["mean"],
        "pev_study": res["pev_study"],
        "pav_study": res["pav_study"],
        "pgrr_study": res["pgrr_study"],
        "ppv_study": res["ppv_study"],
        "pev_tolerance": res["pev_tolerance"],
        "pav_tolerance": res["pav_tolerance"],
        "pgrr_tolerance": res["pgrr_tolerance"],
        "ppv_tolerance": res["ppv_tolerance"],
        "ndc": res["ndc"],
        "verdict": res["verdict"],
        "n_parts": res["n_parts"],
        "n_appraisers": res["n_appraisers"],
        "n_trials": res["n_trials"],
        "is_balanced": res["is_balanced"],
        "method": res["method"],
        "method_note": res["method_note"],
        "interaction": res["interaction"],
        "interaction_f": res["interaction_f"],
        "interaction_significant": res["interaction_significant"],
    }


__all__ = ["calculate_gage_rr"]

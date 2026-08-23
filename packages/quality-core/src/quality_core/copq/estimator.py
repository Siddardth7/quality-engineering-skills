"""
estimator.py
Deterministic Cost of Poor Quality (COPQ) financial estimator over the PAF (Prevention-Appraisal-Failure) model.

Implements standard Prevention-Appraisal-Failure financial rollup arithmetic per the ASQ Certified Six Sigma
Green Belt (CSSGB) Body of Knowledge and CSSC Lean Six Sigma curricula:
- Internal Failure: scrap (scrap_qty * unit_cost), rework (rework_hours * labor_rate + added_material_cost),
  containment/sorting (sort_hours * labor_rate), retest (retest_hours * labor_rate), downtime (downtime_hours * downtime_hourly_rate).
- External Failure: warranty claims (warranty_units * warranty_unit_cost), returns (returned_qty * unit_cost),
  recalls (recall_cost), concessions (concession_qty * price_reduction_per_unit).
- Prevention and Appraisal rollups, CoGQ (Prevention + Appraisal), COPQ (Internal + External Failure),
  Total Cost of Quality (CoQ = CoGQ + COPQ), %-of-revenue, and failure cost distribution ratios.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from quality_core.copq.schema import COPQDataset, CostItem, validate_copq

__all__ = [
    "COPQEstimationResult",
    "estimate_copq",
]

_STANDARDS_BASIS: str = (
    "ASQ Certified Six Sigma Green Belt (CSSGB) Body of Knowledge / "
    "PAF Model (Feigenbaum & Juran) / CSSC Lean Six Sigma Manual (2018)"
)


@dataclass
class COPQEstimationResult:
    """Structured result of Cost of Poor Quality (COPQ) PAF financial estimation."""

    title: str
    total_copq: float
    internal_failure_total: float
    external_failure_total: float
    prevention_total: float
    appraisal_total: float
    cogq_total: float
    total_coq: float
    copq_percentage_of_revenue: float | None
    revenue_base: float | None
    failure_cost_ratio: dict[str, float]
    cost_breakdown: dict[str, Any]
    item_count: int
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    standards_basis: str = _STANDARDS_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a JSON-compatible dictionary."""
        return asdict(self)


def _validate_non_negative_qty(name: str, val: Any) -> int | None:
    """Validate that quantity is a non-negative integer or None."""
    if val is None:
        return None
    if isinstance(val, bool):
        raise TypeError(f"{name} cannot be a boolean, got {val!r}")
    if isinstance(val, int):
        if val < 0:
            raise ValueError(f"{name} must be >= 0, got {val}")
        return val
    raise TypeError(f"{name} must be an integer or None, got {type(val).__name__}: {val!r}")


def _validate_non_negative_float(name: str, val: Any) -> float | None:
    """Validate that numeric value is a non-negative finite float/int or None."""
    if val is None:
        return None
    if isinstance(val, bool):
        raise TypeError(f"{name} cannot be a boolean, got {val!r}")
    if isinstance(val, (int, float)):
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            raise ValueError(f"{name} must be a finite number, got {f_val}")
        if f_val < 0.0:
            raise ValueError(f"{name} must be >= 0.0, got {f_val}")
        return f_val
    raise TypeError(f"{name} must be a number or None, got {type(val).__name__}: {val!r}")


def estimate_copq(
    *,
    items: Sequence[CostItem | dict[str, Any]] | COPQDataset | None = None,
    scrap_qty: int | None = None,
    unit_cost: float | None = None,
    rework_hours: float | None = None,
    labor_rate: float | None = None,
    added_material_cost: float | None = None,
    sort_hours: float | None = None,
    containment_hours: float | None = None,
    retest_hours: float | None = None,
    downtime_hours: float | None = None,
    downtime_hourly_rate: float | None = None,
    warranty_units: int | None = None,
    warranty_cost_per_unit: float | None = None,
    warranty_unit_cost: float | None = None,
    returned_qty: int | None = None,
    recall_cost: float | None = None,
    concession_qty: int | None = None,
    price_reduction_per_unit: float | None = None,
    prevention_cost: float | None = None,
    appraisal_cost: float | None = None,
    revenue_base: float | None = None,
    title: str = "Cost of Poor Quality (COPQ) Financial Estimate",
) -> COPQEstimationResult:
    """Perform deterministic Cost of Poor Quality (COPQ) financial calculation and PAF rollup.

    Parameters
    ----------
    items : Sequence[CostItem | dict[str, Any]] | COPQDataset | None, optional
        Pre-itemized PAF cost entries.
    scrap_qty : int, optional
        Quantity of units scrapped.
    unit_cost : float, optional
        Standard product/unit manufactured cost ($).
    rework_hours : float, optional
        Direct labor hours required for rework operations.
    labor_rate : float, optional
        Hourly labor rate ($/hr) applied to rework, sorting, and retesting.
    added_material_cost : float, optional
        Additional material or replacement components cost consumed during rework ($).
    sort_hours : float, optional
        Hours dedicated to inventory sorting and containment.
    containment_hours : float, optional
        Alias for `sort_hours`.
    retest_hours : float, optional
        Hours dedicated to re-testing or re-inspecting reworked product.
    downtime_hours : float, optional
        Hours of production downtime resulting from the nonconformance.
    downtime_hourly_rate : float, optional
        Cost rate per downtime hour ($/hr).
    warranty_units : int, optional
        Number of defective units claimed or serviced under warranty.
    warranty_cost_per_unit : float, optional
        Average cost per warranty repair or field replacement ($).
    warranty_unit_cost : float, optional
        Alias for `warranty_cost_per_unit`.
    returned_qty : int, optional
        Quantity of units returned by customer.
    recall_cost : float, optional
        Direct logistics, customer compensation, and administrative cost of product recall ($).
    concession_qty : int, optional
        Quantity of units accepted under price concession / deviation permit.
    price_reduction_per_unit : float, optional
        Price discount or concession credit per unit granted to customer ($).
    prevention_cost : float, optional
        Direct investments in quality planning, error proofing, and training ($).
    appraisal_cost : float, optional
        Direct expenses for inspection, testing, and audits ($).
    revenue_base : float, optional
        Total annual or batch product revenue base ($) used to calculate COPQ as a percentage of sales.
    title : str, default="Cost of Poor Quality (COPQ) Financial Estimate"
        Title of the financial estimate.

    Returns
    -------
    COPQEstimationResult
        Structured calculation containing PAF cost categories, aggregate COPQ, CoGQ, total CoQ,
        %-of-revenue, failure cost ratios, cost breakdown, warnings, and recommendations.

    Raises
    ------
    TypeError
        If parameter types are invalid (e.g. booleans passed for numeric values, or non-string title).
    ValueError
        If numeric values are negative, infinite, NaN, or title is empty.
    """
    if not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must be a non-empty string")
    clean_title = title.strip()

    # Validate inputs
    v_scrap_qty = _validate_non_negative_qty("scrap_qty", scrap_qty)
    v_warranty_units = _validate_non_negative_qty("warranty_units", warranty_units)
    v_returned_qty = _validate_non_negative_qty("returned_qty", returned_qty)
    v_concession_qty = _validate_non_negative_qty("concession_qty", concession_qty)

    v_unit_cost = _validate_non_negative_float("unit_cost", unit_cost)
    v_rework_hours = _validate_non_negative_float("rework_hours", rework_hours)
    v_labor_rate = _validate_non_negative_float("labor_rate", labor_rate)
    v_added_mat = _validate_non_negative_float("added_material_cost", added_material_cost)
    v_sort_hours = _validate_non_negative_float("sort_hours", sort_hours)
    v_containment_hours = _validate_non_negative_float("containment_hours", containment_hours)
    v_retest_hours = _validate_non_negative_float("retest_hours", retest_hours)
    v_downtime_hours = _validate_non_negative_float("downtime_hours", downtime_hours)
    v_downtime_rate = _validate_non_negative_float("downtime_hourly_rate", downtime_hourly_rate)

    v_w_cost1 = _validate_non_negative_float("warranty_cost_per_unit", warranty_cost_per_unit)
    v_w_cost2 = _validate_non_negative_float("warranty_unit_cost", warranty_unit_cost)
    v_warranty_unit_cost = v_w_cost1 if v_w_cost1 is not None else v_w_cost2

    v_recall_cost = _validate_non_negative_float("recall_cost", recall_cost)
    v_price_red = _validate_non_negative_float("price_reduction_per_unit", price_reduction_per_unit)
    v_prev_cost = _validate_non_negative_float("prevention_cost", prevention_cost)
    v_appr_cost = _validate_non_negative_float("appraisal_cost", appraisal_cost)
    v_revenue_base = _validate_non_negative_float("revenue_base", revenue_base)

    warnings: list[str] = []
    recommendations: list[str] = []

    if v_w_cost1 is not None and v_w_cost2 is not None and v_w_cost1 != v_w_cost2:
        warnings.append(
            f"Conflicting values provided for warranty_cost_per_unit ({v_w_cost1}) and "
            f"warranty_unit_cost ({v_w_cost2}); using warranty_cost_per_unit={v_w_cost1}."
        )

    if v_sort_hours is not None and v_containment_hours is not None and v_sort_hours != v_containment_hours:
        warnings.append(
            f"Conflicting values provided for sort_hours ({v_sort_hours}) and "
            f"containment_hours ({v_containment_hours}); using sort_hours={v_sort_hours}."
        )

    # 1. Direct Internal Failure Calculations
    calc_scrap_cost = 0.0
    if v_scrap_qty is not None:
        if v_unit_cost is not None:
            calc_scrap_cost = float(v_scrap_qty) * v_unit_cost
        else:
            warnings.append("scrap_qty was provided without unit_cost; scrap cost evaluated to $0.00.")

    calc_rework_cost = 0.0
    if v_rework_hours is not None:
        if v_labor_rate is not None:
            calc_rework_cost += float(v_rework_hours) * v_labor_rate
        else:
            warnings.append("rework_hours was provided without labor_rate; rework labor cost evaluated to $0.00.")
    if v_added_mat is not None:
        calc_rework_cost += v_added_mat

    effective_sort_hours = v_sort_hours if v_sort_hours is not None else v_containment_hours
    calc_containment_cost = 0.0
    if effective_sort_hours is not None:
        if v_labor_rate is not None:
            calc_containment_cost = float(effective_sort_hours) * v_labor_rate
        else:
            warnings.append("sort_hours / containment_hours provided without labor_rate; containment cost evaluated to $0.00.")

    calc_retest_cost = 0.0
    if v_retest_hours is not None:
        if v_labor_rate is not None:
            calc_retest_cost = float(v_retest_hours) * v_labor_rate
        else:
            warnings.append("retest_hours was provided without labor_rate; retest cost evaluated to $0.00.")

    calc_downtime_cost = 0.0
    if v_downtime_hours is not None:
        if v_downtime_rate is not None:
            calc_downtime_cost = float(v_downtime_hours) * v_downtime_rate
        else:
            warnings.append("downtime_hours was provided without downtime_hourly_rate; downtime cost evaluated to $0.00.")

    direct_internal_failure = (
        calc_scrap_cost
        + calc_rework_cost
        + calc_containment_cost
        + calc_retest_cost
        + calc_downtime_cost
    )

    # 2. Direct External Failure Calculations
    calc_warranty_cost = 0.0
    if v_warranty_units is not None:
        if v_warranty_unit_cost is not None:
            calc_warranty_cost = float(v_warranty_units) * v_warranty_unit_cost
        else:
            warnings.append("warranty_units provided without warranty_cost_per_unit; warranty cost evaluated to $0.00.")

    calc_returns_cost = 0.0
    if v_returned_qty is not None:
        if v_unit_cost is not None:
            calc_returns_cost = float(v_returned_qty) * v_unit_cost
        else:
            warnings.append("returned_qty was provided without unit_cost; customer returns cost evaluated to $0.00.")

    calc_recall_cost = v_recall_cost or 0.0

    calc_concession_cost = 0.0
    if v_concession_qty is not None:
        if v_price_red is not None:
            calc_concession_cost = float(v_concession_qty) * v_price_red
        else:
            warnings.append("concession_qty was provided without price_reduction_per_unit; concession cost evaluated to $0.00.")

    direct_external_failure = (
        calc_warranty_cost
        + calc_returns_cost
        + calc_recall_cost
        + calc_concession_cost
    )

    # 3. Direct Prevention and Appraisal
    direct_prevention = v_prev_cost or 0.0
    direct_appraisal = v_appr_cost or 0.0

    # 4. Process Itemized Ingest if provided
    item_count = 0
    items_prevention = 0.0
    items_appraisal = 0.0
    items_internal_failure = 0.0
    items_external_failure = 0.0

    if items is not None:
        if isinstance(items, COPQDataset):
            item_list = items.items
            if v_revenue_base is None and items.revenue_base is not None:
                v_revenue_base = items.revenue_base
        elif isinstance(items, list):
            item_list = []
            for idx, itm in enumerate(items):
                if isinstance(itm, CostItem):
                    item_list.append(itm)
                elif isinstance(itm, dict):
                    item_list.append(CostItem(**itm))
                else:
                    raise TypeError(f"items element at index {idx} must be CostItem or dict, got {type(itm).__name__}")
        else:
            validated_dataset = validate_copq(items)
            item_list = validated_dataset.items
            if v_revenue_base is None and validated_dataset.revenue_base is not None:
                v_revenue_base = validated_dataset.revenue_base

        item_count = len(item_list)
        for cost_item in item_list:
            cost = cost_item.total_cost
            if cost_item.category == "Prevention":
                items_prevention += cost
            elif cost_item.category == "Appraisal":
                items_appraisal += cost
            elif cost_item.category == "InternalFailure":
                items_internal_failure += cost
            else:
                items_external_failure += cost

    # 5. Consolidated PAF Model Financial Rollup
    prevention_total = round(direct_prevention + items_prevention, 2)
    appraisal_total = round(direct_appraisal + items_appraisal, 2)
    internal_failure_total = round(direct_internal_failure + items_internal_failure, 2)
    external_failure_total = round(direct_external_failure + items_external_failure, 2)

    total_copq = round(internal_failure_total + external_failure_total, 2)
    cogq_total = round(prevention_total + appraisal_total, 2)
    total_coq = round(total_copq + cogq_total, 2)

    # 6. COPQ % of Revenue
    copq_pct_revenue: float | None = None
    if v_revenue_base is not None:
        if v_revenue_base > 0.0:
            copq_pct_revenue = round((total_copq / v_revenue_base) * 100.0, 4)
        else:
            warnings.append(
                "revenue_base must be greater than 0.0 to calculate COPQ as a percentage of revenue; received 0.0."
            )
            recommendations.append(
                "Provide a positive revenue_base ($ > 0.0) to calculate COPQ as a percentage of product/organization sales."
            )
    else:
        recommendations.append("Provide revenue_base ($) to calculate COPQ as a percentage of product/organization sales.")

    # 7. Failure Cost Ratio Distribution
    if total_copq > 0.0:
        internal_pct = round((internal_failure_total / total_copq) * 100.0, 2)
        external_pct = round((external_failure_total / total_copq) * 100.0, 2)
    else:
        internal_pct = 0.0
        external_pct = 0.0

    failure_cost_ratio = {
        "internal_failure_pct": internal_pct,
        "external_failure_pct": external_pct,
    }

    # 8. Detailed Breakdown Dictionary
    cost_breakdown: dict[str, Any] = {
        "internal_failure": {
            "scrap": round(calc_scrap_cost, 2),
            "rework": round(calc_rework_cost, 2),
            "containment": round(calc_containment_cost, 2),
            "retest": round(calc_retest_cost, 2),
            "downtime": round(calc_downtime_cost, 2),
            "itemized_additional": round(items_internal_failure, 2),
            "total": internal_failure_total,
        },
        "external_failure": {
            "warranty": round(calc_warranty_cost, 2),
            "returns": round(calc_returns_cost, 2),
            "recall": round(calc_recall_cost, 2),
            "concessions": round(calc_concession_cost, 2),
            "itemized_additional": round(items_external_failure, 2),
            "total": external_failure_total,
        },
        "prevention": {
            "direct": round(direct_prevention, 2),
            "itemized": round(items_prevention, 2),
            "total": prevention_total,
        },
        "appraisal": {
            "direct": round(direct_appraisal, 2),
            "itemized": round(items_appraisal, 2),
            "total": appraisal_total,
        },
    }

    # 9. Strategic Quality Engineering Recommendations & Warnings
    if total_coq == 0.0:
        warnings.append("No cost drivers or items provided; all cost categories evaluated to $0.00.")

    if external_failure_total > internal_failure_total and total_copq > 0.0:
        warnings.append(
            f"External failure costs (${external_failure_total:,.2f}) exceed internal failure costs "
            f"(${internal_failure_total:,.2f}); indicates significant quality escape rate to customer."
        )
        recommendations.append(
            "Prioritize immediate containment and upstream Poke-Yoke / error-proofing to intercept defects before delivery."
        )

    if total_copq > (cogq_total * 3.0) and cogq_total > 0.0:
        recommendations.append(
            "Failure costs heavily dominate conformance investments. Shift budget into Prevention (FMEA, Control Plans, DFM) "
            "to optimize the total Cost of Quality curve."
        )

    return COPQEstimationResult(
        title=clean_title,
        total_copq=total_copq,
        internal_failure_total=internal_failure_total,
        external_failure_total=external_failure_total,
        prevention_total=prevention_total,
        appraisal_total=appraisal_total,
        cogq_total=cogq_total,
        total_coq=total_coq,
        copq_percentage_of_revenue=copq_pct_revenue,
        revenue_base=v_revenue_base,
        failure_cost_ratio=failure_cost_ratio,
        cost_breakdown=cost_breakdown,
        item_count=item_count,
        warnings=warnings,
        recommendations=recommendations,
        standards_basis=_STANDARDS_BASIS,
    )

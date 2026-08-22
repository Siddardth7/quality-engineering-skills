"""
copq.py
FastMCP tools for Cost of Poor Quality (COPQ) financial estimation and PAF model rollup.

Exposes deterministic PAF cost accounting from quality_core.copq to AI agents and MCP client hosts.

Standards References:
- ASQ Certified Six Sigma Green Belt (CSSGB) Body of Knowledge (2014/2022).
- The Certified Six Sigma Green Belt Handbook (2nd Edition, ASQ Quality Press).
- Council for Six Sigma Certification (CSSC) Lean Six Sigma Green Belt Training Manual (2018).
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field
from quality_core.copq.estimator import (
    estimate_copq as _estimate_copq,
)

__all__ = [
    "estimate_copq",
]


def estimate_copq(
    items: Annotated[
        list[dict[str, Any]] | None,
        Field(description="Itemized list of PAF cost dictionaries with fields: category, description, and cost drivers (scrap_qty, unit_cost, rework_hours, labor_rate, direct_cost, etc.)."),
    ] = None,
    scrap_qty: Annotated[
        int | None,
        Field(description="Total quantity of nonconforming parts scrapped."),
    ] = None,
    unit_cost: Annotated[
        float | None,
        Field(description="Standard manufactured cost per unit ($)."),
    ] = None,
    rework_hours: Annotated[
        float | None,
        Field(description="Direct labor hours spent on rework operations."),
    ] = None,
    labor_rate: Annotated[
        float | None,
        Field(description="Hourly labor rate ($/hr) applied to rework, sorting, and retesting."),
    ] = None,
    added_material_cost: Annotated[
        float | None,
        Field(description="Additional material or component replacement cost incurred during rework ($)."),
    ] = None,
    sort_hours: Annotated[
        float | None,
        Field(description="Hours dedicated to inventory containment and sorting."),
    ] = None,
    retest_hours: Annotated[
        float | None,
        Field(description="Hours dedicated to retesting and re-inspection."),
    ] = None,
    downtime_hours: Annotated[
        float | None,
        Field(description="Hours of line/cell downtime caused by the quality nonconformance."),
    ] = None,
    downtime_hourly_rate: Annotated[
        float | None,
        Field(description="Cost rate per downtime hour ($/hr)."),
    ] = None,
    warranty_units: Annotated[
        int | None,
        Field(description="Number of defective units claimed or serviced under warranty."),
    ] = None,
    warranty_cost_per_unit: Annotated[
        float | None,
        Field(description="Average cost per warranty repair or field replacement ($)."),
    ] = None,
    returned_qty: Annotated[
        int | None,
        Field(description="Quantity of defective units returned by customer."),
    ] = None,
    recall_cost: Annotated[
        float | None,
        Field(description="Direct logistics, notification, and administrative cost of product recall ($)."),
    ] = None,
    concession_qty: Annotated[
        int | None,
        Field(description="Quantity of units accepted under customer price concession / deviation permit."),
    ] = None,
    price_reduction_per_unit: Annotated[
        float | None,
        Field(description="Price discount or concession credit per unit ($)."),
    ] = None,
    prevention_cost: Annotated[
        float | None,
        Field(description="Direct investment in quality planning, poka-yoke, and training ($)."),
    ] = None,
    appraisal_cost: Annotated[
        float | None,
        Field(description="Direct expenses for inspection, testing, and audits ($)."),
    ] = None,
    revenue_base: Annotated[
        float | None,
        Field(description="Total annual or batch product revenue base ($) to compute COPQ as a percentage of sales."),
    ] = None,
    title: Annotated[
        str,
        Field(description="Title of the COPQ financial estimate report."),
    ] = "Cost of Poor Quality (COPQ) Financial Estimate",
) -> dict[str, Any]:
    """Calculate Cost of Poor Quality (COPQ) financial metrics and PAF cost rollups.

    Implements the classical Prevention-Appraisal-Failure (PAF) cost accounting model per the ASQ
    Certified Six Sigma Green Belt (CSSGB) Body of Knowledge. Computes internal failure, external failure,
    conformance costs (CoGQ), total Cost of Quality (CoQ), %-of-revenue, and failure cost distribution ratios.
    """
    res = _estimate_copq(
        items=items,
        scrap_qty=scrap_qty,
        unit_cost=unit_cost,
        rework_hours=rework_hours,
        labor_rate=labor_rate,
        added_material_cost=added_material_cost,
        sort_hours=sort_hours,
        retest_hours=retest_hours,
        downtime_hours=downtime_hours,
        downtime_hourly_rate=downtime_hourly_rate,
        warranty_units=warranty_units,
        warranty_cost_per_unit=warranty_cost_per_unit,
        returned_qty=returned_qty,
        recall_cost=recall_cost,
        concession_qty=concession_qty,
        price_reduction_per_unit=price_reduction_per_unit,
        prevention_cost=prevention_cost,
        appraisal_cost=appraisal_cost,
        revenue_base=revenue_base,
        title=title,
    )
    return res.to_dict()

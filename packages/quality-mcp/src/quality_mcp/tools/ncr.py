"""
ncr.py
FastMCP tools for Nonconformance Reporting (NCR) defect statement writing and disposition recommendation.

Exposes deterministic ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7 nonconformance statement
formulation and rule-based disposition recommendation from quality_core.ncr to AI agents and MCP client hosts.

Standards References:
- ISO 9001:2015 Clause 8.7 ("Control of nonconforming outputs"): Clause 8.7.1 & Clause 8.7.2.
- IATF 16949:2016 Clause 8.7 ("Control of nonconforming outputs"): Clause 8.7.1.1, 8.7.1.3, 8.7.1.4 & 8.7.1.7.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field
from quality_core.ncr.nonconformance import (
    DispositionRecommendation,
    NonconformanceWriteResult,
)
from quality_core.ncr.nonconformance import (
    recommend_disposition as _recommend_disposition,
)
from quality_core.ncr.nonconformance import (
    write_nonconformance as _write_nonconformance,
)

__all__ = [
    "recommend_disposition",
    "write_ncr",
]

_STANDARDS_BASIS = "ISO 9001:2015 §8.7 / IATF 16949:2016 §8.7"


def write_ncr(
    raw_defect_note: Annotated[
        str | None,
        Field(description="Unstructured defect note or shop-floor description to rewrite into objective nonconformance language."),
    ] = None,
    what_deviated: Annotated[
        str | None,
        Field(description="Specific nonconforming condition or deviation observed on the part/lot."),
    ] = None,
    requirement_violated: Annotated[
        str | None,
        Field(description="Engineering drawing specification, standard, or requirement violated."),
    ] = None,
    measured_evidence: Annotated[
        str | None,
        Field(description="Quantitative or qualitative measurement demonstrating the deviation (e.g. '12.45 mm vs 12.00 ± 0.10 mm')."),
    ] = None,
    quantity_affected: Annotated[
        int | str | None,
        Field(description="Total quantity of nonconforming or suspect parts/units."),
    ] = None,
    detection_point: Annotated[
        str | None,
        Field(description="Operation, station, cell, or inspection gate where the defect was detected."),
    ] = None,
    part_lot_id: Annotated[
        str | None,
        Field(description="Part number, lot number, serial number, or batch identifier."),
    ] = None,
    unit_of_measure: Annotated[
        str | None,
        Field(description="Unit of measure for quantity affected (e.g. 'pcs', 'units', 'kg')."),
    ] = "units",
) -> dict[str, Any]:
    """Draft an objective-evidence nonconformance statement per ISO 9001:2015 §8.7.

    Deterministic FastMCP tool wrapping `quality_core.ncr.write_nonconformance`.
    Converts raw defect notes into structured, blame-free ISO 9001 §8.7 nonconformance statements
    (what deviated, requirement violated, measured evidence, quantity affected, detection point)
    and filters operator blame phrases and premature root-cause speculation.

    Parameters
    ----------
    raw_defect_note : str | None, optional
        Unstructured text or defect notes from the shop floor.
    what_deviated : str | None, optional
        Specific description of what nonconforming condition was observed.
    requirement_violated : str | None, optional
        Engineering drawing specification or standard violated.
    measured_evidence : str | None, optional
        Measured evidence demonstrating the deviation.
    quantity_affected : int | str | None, optional
        Total quantity of nonconforming items.
    detection_point : str | None, optional
        Operation or station where the nonconformance was detected.
    part_lot_id : str | None, optional
        Part number or lot identifier.
    unit_of_measure : str | None, default "units"
        Unit of measure for quantity affected.

    Returns
    -------
    dict[str, Any]
        Structured dictionary containing statement, valid flag, populated/missing fields,
        detected blame/speculation, warnings, and recommendations.
    """
    result: NonconformanceWriteResult = _write_nonconformance(
        raw_defect_note=raw_defect_note,
        what_deviated=what_deviated,
        requirement_violated=requirement_violated,
        measured_evidence=measured_evidence,
        quantity_affected=quantity_affected,
        detection_point=detection_point,
        part_lot_id=part_lot_id,
        unit_of_measure=unit_of_measure,
    )
    return result.to_dict()


def recommend_disposition(
    is_reworkable: Annotated[
        bool | None,
        Field(description="Whether the nonconforming feature can technically be reworked to meet specification."),
    ] = None,
    defect_origin: Annotated[
        str | None,
        Field(description="Origin of the defect: 'Internal', 'Supplier', 'Customer', or 'Unknown'."),
    ] = None,
    meets_secondary_spec: Annotated[
        bool | None,
        Field(description="Whether the product conforms to an authorized secondary product grade specification for regrading."),
    ] = None,
    customer_concession_eligible: Annotated[
        bool | None,
        Field(description="Whether the deviation is minor and eligible for customer concession (Use-As-Is)."),
    ] = None,
    rework_cost: Annotated[
        float | int | None,
        Field(description="Estimated direct cost to perform rework per unit or batch."),
    ] = None,
    part_value: Annotated[
        float | int | None,
        Field(description="Standard manufactured cost or part value of the nonconforming item."),
    ] = None,
    severity: Annotated[
        str | None,
        Field(description="Defect severity rating (e.g. 'Critical', 'Major', 'Minor')."),
    ] = None,
    safety_critical: Annotated[
        bool | None,
        Field(description="Whether the defect affects a safety, regulatory, or critical characteristic."),
    ] = None,
    defect_description: Annotated[
        str | None,
        Field(description="Description of the nonconformance for audit context."),
    ] = None,
) -> dict[str, Any]:
    """Recommend a deterministic, standards-cited disposition per ISO 9001:2015 §8.7 and IATF 16949:2016 §8.7.

    Deterministic FastMCP tool wrapping `quality_core.ncr.recommend_disposition`.
    Evaluates defect origin, technical reworkability, secondary grade conformance, customer concession
    eligibility, and rework cost economics to recommend one of the 5 canonical dispositions
    (Scrap, Rework, UseAsIs, ReturnToVendor, Regrade) with cited rationale and required approval authority.
    Refuses silent disposition guessing on ambiguous/incomplete inputs (INSUFFICIENT_DATA negative control).

    Parameters
    ----------
    is_reworkable : bool | None, optional
        Whether the product can technically be reworked.
    defect_origin : str | None, optional
        Origin of the defect ('Internal', 'Supplier', 'Customer', etc.).
    meets_secondary_spec : bool | None, optional
        Whether product meets a secondary grade specification.
    customer_concession_eligible : bool | None, optional
        Whether defect is eligible for customer concession.
    rework_cost : float | int | None, optional
        Estimated rework cost.
    part_value : float | int | None, optional
        Part value / standard manufactured cost.
    severity : str | None, optional
        Defect severity rating.
    safety_critical : bool | None, optional
        Whether defect affects safety-critical characteristics.
    defect_description : str | None, optional
        Description of the defect.

    Returns
    -------
    dict[str, Any]
        Structured dictionary containing recommended disposition, cited rationale,
        approval authority, MRB/Customer authorization flags, and warnings.
    """
    result: DispositionRecommendation = _recommend_disposition(
        is_reworkable=is_reworkable,
        defect_origin=defect_origin,
        meets_secondary_spec=meets_secondary_spec,
        customer_concession_eligible=customer_concession_eligible,
        rework_cost=rework_cost,
        part_value=part_value,
        severity=severity,
        safety_critical=safety_critical,
        defect_description=defect_description,
    )
    return result.to_dict()

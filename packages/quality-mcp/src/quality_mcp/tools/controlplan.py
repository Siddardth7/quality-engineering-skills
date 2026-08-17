"""
controlplan.py
FastMCP tool for AIAG Control Plan schema validation and PFMEA linkage.

Exposes deterministic Control Plan validation and PFMEA linkage checking from
quality_core.controlplan to AI agents and MCP client hosts.
Standards basis: AIAG APQP & Control Plan (2nd Edition) and AIAG-VDA FMEA (2019).
"""

from __future__ import annotations

from typing import Any

import pydantic
from quality_core.controlplan import (
    ControlPlanDataset,
    validate_pfmea_linkage,
)
from quality_core.controlplan import (
    validate_control_plan as validate_control_plan_core,
)
from quality_core.io.validate import clean_pydantic_message
from quality_core.schema import FMEADataset, FMEARow, flat_to_relational


def validate_control_plan(
    plan: list[dict[str, Any]],
    fmea: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate a Control Plan document against the AIAG Control Plan schema and PFMEA linkage.

    Parameters:
        plan: List of Control Plan row dictionaries with schema fields:
            - "characteristic": str name of the characteristic (required, non-blank)
            - "measurement_method": str inspection / measurement method (required, non-blank)
            - "sample_size": int sample size per check (required, >= 1)
            - "frequency": str inspection frequency / cadence (required, non-blank)
            - "reaction_plan": str reaction / containment instruction (required, non-blank)
            - "lsl": optional float Lower Specification Limit
            - "usl": optional float Upper Specification Limit (must be > lsl if both provided)
            - "target": optional float nominal target (must be within [lsl, usl] if provided)
            - "recommended_chart": optional str SPC chart type ("Xbar-R", "Xbar-S", "I-MR", "p", "c", "u")
            - "source_cause_id": optional str FMEA join key ("FunctionID::FailureModeID::CauseID")
            - "sample_plan_is_placeholder": optional bool flag indicating defaulted sample plan
        fmea: Optional list of flat FMEA record dictionaries to validate bidirectional PFMEA linkage.
            If provided, verifies that all Control Plan rows resolve to valid causes in the FMEA,
            detects orphan characteristics, and identifies uncovered FMEA failure modes.

    Returns:
        Structured dictionary containing:
        - basis: Standards attribution string ("AIAG Control Plan")
        - valid: Overall boolean validity (True if schema is valid and linkage has 0 orphans)
        - total_rows: Total count of rows in the Control Plan
        - schema_valid: Boolean indicating whether all row and dataset schema rules passed
        - schema_findings: List of error messages for any schema violations
        - linkage_checked: Boolean indicating whether PFMEA linkage verification was executed
        - linkage_valid: Boolean (or None if fmea omitted) indicating whether all rows are linked
        - linked_rows: Integer (or None if fmea omitted) count of linked Control Plan rows
        - orphan_characteristics: List of characteristic names lacking valid FMEA cause linkage
        - uncovered_failure_modes: List of FMEA failure modes lacking Control Plan rows
        - linkage_findings: List of detailed findings for orphan or uncovered items
    """
    if not isinstance(plan, list):
        raise TypeError(f"plan must be a list of row dicts, got {type(plan).__name__}")
    if fmea is not None and not isinstance(fmea, list):
        raise TypeError(f"fmea must be a list of dicts or None, got {type(fmea).__name__}")

    basis = "AIAG Control Plan"
    total_rows = len(plan)
    schema_findings: list[str] = []
    dataset: ControlPlanDataset | None = None

    if total_rows == 0:
        schema_valid = False
        schema_findings.append("Control Plan dataset must contain at least one characteristic row.")
    else:
        try:
            dataset = validate_control_plan_core(plan)
            schema_valid = True
        except pydantic.ValidationError as exc:
            schema_valid = False
            for err in exc.errors():
                loc = ".".join(str(p) for p in err.get("loc", ()))
                msg = clean_pydantic_message(err.get("msg", "invalid value"))
                where = f"column '{loc}'" if loc else "dataset"
                schema_findings.append(f"{where}: {msg}")
        except (ValueError, TypeError) as exc:
            schema_valid = False
            schema_findings.append(str(exc))

    linkage_checked = fmea is not None
    linkage_valid: bool | None = None
    linked_rows: int | None = None
    orphan_characteristics: list[str] = []
    uncovered_failure_modes: list[str] = []
    linkage_findings: list[str] = []

    if linkage_checked:
        if dataset is None:
            linkage_valid = False
            linked_rows = 0
            linkage_findings.append("Cannot verify PFMEA linkage because Control Plan schema is invalid.")
        else:
            try:
                fmea_rows = [FMEARow(**r) for r in fmea]  # type: ignore[union-attr]
                fmea_dataset = FMEADataset(rows=fmea_rows)
                relational_fmea = flat_to_relational(fmea_dataset)
                linkage_res = validate_pfmea_linkage(dataset, relational_fmea)

                linkage_valid = linkage_res["valid"]
                linked_rows = linkage_res["linked_rows"]
                orphan_characteristics = linkage_res["orphan_characteristics"]
                uncovered_failure_modes = linkage_res["uncovered_failure_modes"]
                linkage_findings = linkage_res["findings"]
            except pydantic.ValidationError as exc:
                linkage_valid = False
                linked_rows = 0
                for err in exc.errors():
                    msg = clean_pydantic_message(err.get("msg", "invalid value"))
                    linkage_findings.append(f"Invalid FMEA input: {msg}")
            except Exception as exc:
                linkage_valid = False
                linked_rows = 0
                linkage_findings.append(f"FMEA processing error: {exc}")

    overall_valid = schema_valid and (linkage_valid is not False)

    return {
        "basis": basis,
        "valid": overall_valid,
        "total_rows": total_rows,
        "schema_valid": schema_valid,
        "schema_findings": schema_findings,
        "linkage_checked": linkage_checked,
        "linkage_valid": linkage_valid,
        "linked_rows": linked_rows,
        "orphan_characteristics": orphan_characteristics,
        "uncovered_failure_modes": uncovered_failure_modes,
        "linkage_findings": linkage_findings,
    }


__all__ = ["validate_control_plan"]

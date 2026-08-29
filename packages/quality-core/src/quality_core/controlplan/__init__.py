"""
quality_core.controlplan

Control Plan engine, schema validation, PFMEA-linkage engine, and Excel exporter.
"""

from __future__ import annotations

from quality_core.controlplan.connector import (
    DataType,
    build_control_plan,
    recommend_chart,
    source_index,
    validate_pfmea_linkage,
)
from quality_core.controlplan.export import (
    CONTROLPLAN_COL_WIDTHS,
    CONTROLPLAN_EXPORT_COLUMNS,
    benchmark_controlplan_dataset,
    export_controlplan_workbook,
)
from quality_core.controlplan.schema import (
    CONTROL_PLAN_SCHEMA,
    ControlPlanDataset,
    ControlPlanRow,
    IngestError,
    SPCChart,
    load_control_plan_csv,
    validate_control_plan,
)

__all__ = [
    "CONTROLPLAN_COL_WIDTHS",
    "CONTROLPLAN_EXPORT_COLUMNS",
    "CONTROL_PLAN_SCHEMA",
    "ControlPlanDataset",
    "ControlPlanRow",
    "DataType",
    "IngestError",
    "SPCChart",
    "benchmark_controlplan_dataset",
    "build_control_plan",
    "export_controlplan_workbook",
    "load_control_plan_csv",
    "recommend_chart",
    "source_index",
    "validate_control_plan",
    "validate_pfmea_linkage",
]

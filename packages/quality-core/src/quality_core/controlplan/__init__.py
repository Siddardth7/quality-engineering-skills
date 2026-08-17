"""
quality_core.controlplan

Control Plan engine, schema validation, and PFMEA-linkage engine.
"""

from __future__ import annotations

from quality_core.controlplan.connector import (
    DataType,
    build_control_plan,
    recommend_chart,
    source_index,
    validate_pfmea_linkage,
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
    "CONTROL_PLAN_SCHEMA",
    "ControlPlanDataset",
    "ControlPlanRow",
    "DataType",
    "IngestError",
    "SPCChart",
    "build_control_plan",
    "load_control_plan_csv",
    "recommend_chart",
    "source_index",
    "validate_control_plan",
    "validate_pfmea_linkage",
]

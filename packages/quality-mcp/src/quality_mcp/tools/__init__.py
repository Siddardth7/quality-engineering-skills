"""Tools package for quality-mcp exposing deterministic quality engineering engines."""

from __future__ import annotations

from quality_mcp.tools.canvas import (
    render_5why_canvas,
    render_controlplan_canvas,
    render_copq_canvas,
    render_fishbone_canvas,
    render_fmea_canvas,
    render_is_is_not_canvas,
    render_isisnot_canvas,
    render_msa_canvas,
    render_ncr_canvas,
    render_ppap_canvas,
    render_spc_canvas,
    render_sqe_canvas,
)
from quality_mcp.tools.controlplan import validate_control_plan
from quality_mcp.tools.copq import estimate_copq
from quality_mcp.tools.fmea import lookup_fmea_ap
from quality_mcp.tools.msa import calculate_gage_rr
from quality_mcp.tools.ncr import (
    recommend_disposition,
    write_ncr,
)
from quality_mcp.tools.ppap import (
    assess_ppap_capability,
    audit_ppap_package,
    lookup_ppap_requirement,
    validate_psw,
)
from quality_mcp.tools.rca import (
    categorize_fishbone,
    scope_is_is_not,
    validate_5why,
)
from quality_mcp.tools.spc import calculate_spc_chart
from quality_mcp.tools.sqe import (
    calculate_otif,
    calculate_supplier_ppm,
    calculate_vendor_scorecard,
    evaluate_escalation,
    generate_scar,
)

__all__ = [
    "assess_ppap_capability",
    "audit_ppap_package",
    "calculate_gage_rr",
    "calculate_otif",
    "calculate_spc_chart",
    "calculate_supplier_ppm",
    "calculate_vendor_scorecard",
    "categorize_fishbone",
    "estimate_copq",
    "evaluate_escalation",
    "generate_scar",
    "lookup_fmea_ap",
    "lookup_ppap_requirement",
    "recommend_disposition",
    "render_5why_canvas",
    "render_controlplan_canvas",
    "render_copq_canvas",
    "render_fishbone_canvas",
    "render_fmea_canvas",
    "render_is_is_not_canvas",
    "render_isisnot_canvas",
    "render_msa_canvas",
    "render_ncr_canvas",
    "render_ppap_canvas",
    "render_spc_canvas",
    "render_sqe_canvas",
    "scope_is_is_not",
    "validate_5why",
    "validate_control_plan",
    "validate_psw",
    "write_ncr",
]

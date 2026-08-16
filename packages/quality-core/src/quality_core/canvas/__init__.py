"""
quality_core.canvas
Interactive visual canvas models and controllers for Quality Platform.
"""

from __future__ import annotations

from quality_core.canvas.fmea import (
    SAMPLE_FMEA_ROWS,
    FMEACanvas,
    FMEACanvasRow,
    load_sample_canvas,
)
from quality_core.canvas.spc import (
    SAMPLE_SPC_XBAR_R_DATA,
    SPCCanvas,
    SPCCanvasSubgroup,
    load_sample_spc_canvas,
)

__all__ = [
    "FMEACanvas",
    "FMEACanvasRow",
    "SAMPLE_FMEA_ROWS",
    "SAMPLE_SPC_XBAR_R_DATA",
    "SPCCanvas",
    "SPCCanvasSubgroup",
    "load_sample_canvas",
    "load_sample_spc_canvas",
]

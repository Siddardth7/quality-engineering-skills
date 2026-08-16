"""Unit and integration tests for quality_mcp calculate_spc_chart FastMCP tool."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from quality_mcp.server import mcp
from quality_mcp.tools.spc import calculate_spc_chart

# ---------------------------------------------------------------------------
# Positive Control Tests - Variable Charts
# ---------------------------------------------------------------------------


def test_xbar_r_stable_with_capability() -> None:
    """Xbar-R chart with stable in-control data and bilateral spec limits calculates capability."""
    # 5 subgroups of size 4
    subgroups = [
        [10.0, 10.2, 9.8, 10.1],
        [10.1, 9.9, 10.0, 10.2],
        [9.9, 10.1, 10.0, 10.0],
        [10.2, 10.0, 9.9, 10.1],
        [10.0, 10.1, 10.2, 9.8],
    ]
    res = calculate_spc_chart("Xbar-R", subgroups, usl=11.0, lsl=9.0)

    assert res["chart_type"] == "Xbar-R"
    assert res["basis"] == "AIAG SPC 4th Edition"
    assert isinstance(res["center_line"], float)
    assert res["center_line"] == pytest.approx(10.03, abs=1e-2)
    assert res["ucl"] > res["center_line"]
    assert res["lcl"] < res["center_line"]
    assert res["dispersion_center"] > 0
    assert len(res["points"]) == 5
    assert len(res["dispersion_points"]) == 5
    assert res["violations"] == []
    assert res["in_control"] is True
    assert res["stable"] is True
    assert res["stability_note"] is None
    assert res["capability"] is not None

    cap = res["capability"]
    assert "cp" in cap and cap["cp"] is not None
    assert "cpk" in cap and cap["cpk"] is not None
    assert "pp" in cap and cap["pp"] is not None
    assert "ppk" in cap and cap["ppk"] is not None
    assert cap["mean"] == pytest.approx(10.03, abs=1e-3)
    assert cap["sigma_hat"] == res["sigma_hat"]
    assert cap["pp_ci"] is not None
    assert cap["ppk_ci"] is not None
    assert cap["ppk_lower"] is not None


def test_xbar_s_stable_with_capability() -> None:
    """Xbar-S chart with stable in-control data and specification limits."""
    # 4 subgroups of size 5
    subgroups = [
        [100.0, 102.0, 99.0, 101.0, 100.5],
        [101.0, 99.5, 100.0, 101.5, 100.0],
        [99.0, 100.5, 101.0, 99.8, 100.2],
        [100.5, 101.0, 99.5, 100.0, 100.8],
    ]
    res = calculate_spc_chart("Xbar-S", subgroups, usl=105.0, lsl=95.0, rule_set="Nelson")

    assert res["chart_type"] == "Xbar-S"
    assert res["in_control"] is True
    assert res["stable"] is True
    assert res["capability"] is not None
    assert res["capability"]["cp"] > 1.0


def test_imr_stable_with_capability() -> None:
    """I-MR chart with stable in-control data and unilateral spec limit (USL only)."""
    values = [10.1, 10.3, 9.9, 10.2, 10.0, 10.1, 9.8, 10.2, 10.0, 10.1]
    res = calculate_spc_chart("I-MR", values, usl=11.5)

    assert res["chart_type"] == "I-MR"
    assert res["in_control"] is True
    assert res["stable"] is True
    assert len(res["points"]) == 10
    assert len(res["dispersion_points"]) == 9
    assert res["capability"] is not None
    assert res["capability"]["cp"] is None  # unilateral USL only -> cp is None
    assert res["capability"]["cpk"] is not None
    assert res["capability"]["pp"] is None
    assert res["capability"]["ppk"] is not None


def test_imr_stable_lsl_only() -> None:
    """I-MR chart with unilateral LSL only."""
    values = [10.1, 10.3, 9.9, 10.2, 10.0, 10.1, 9.8, 10.2, 10.0, 10.1]
    res = calculate_spc_chart("I-MR", values, lsl=8.5)

    assert res["capability"] is not None
    assert res["capability"]["cp"] is None
    assert res["capability"]["cpk"] is not None


def test_variable_chart_without_spec_limits() -> None:
    """When no spec limits (usl=None, lsl=None) are provided, capability is None."""
    values = [10.1, 10.3, 9.9, 10.2, 10.0, 10.1, 9.8, 10.2, 10.0, 10.1]
    res = calculate_spc_chart("I-MR", values)

    assert res["in_control"] is True
    assert res["capability"] is None


# ---------------------------------------------------------------------------
# Positive Control Tests - Attribute Charts
# ---------------------------------------------------------------------------


def test_p_chart() -> None:
    """p chart calculation with constant and varying sample sizes."""
    defects = [5.0, 3.0, 7.0, 2.0, 4.0]
    sizes = [100.0, 100.0, 100.0, 100.0, 100.0]
    res = calculate_spc_chart("p", defects, sample_sizes=sizes)

    assert res["chart_type"] == "p"
    assert res["center_line"] == pytest.approx(21.0 / 500.0)
    assert res["in_control"] is True
    assert res["capability"] is None
    assert res["dispersion_points"] == []


def test_c_chart() -> None:
    """c chart calculation with defect counts."""
    counts = [2.0, 4.0, 3.0, 1.0, 5.0, 2.0]
    res = calculate_spc_chart("c", counts)

    assert res["chart_type"] == "c"
    assert res["center_line"] == pytest.approx(17.0 / 6.0)
    assert res["in_control"] is True
    assert res["capability"] is None
    assert res["dispersion_points"] == []


def test_u_chart() -> None:
    """u chart calculation with defect counts and varying inspection units."""
    defects = [10.0, 12.0, 8.0, 14.0]
    units = [5.0, 6.0, 4.0, 7.0]
    res = calculate_spc_chart("u", defects, sample_sizes=units)

    assert res["chart_type"] == "u"
    assert res["center_line"] == pytest.approx(44.0 / 22.0)
    assert res["in_control"] is True
    assert res["capability"] is None
    assert res["dispersion_points"] == []


# ---------------------------------------------------------------------------
# Stability Gate & Run Rule Violation Tests (Crucial Negative Control)
# ---------------------------------------------------------------------------


def test_stability_gate_out_of_control_suppresses_capability() -> None:
    """Out-of-control signals MUST suppress capability calculation even if spec limits are given."""
    # Create extreme outlier on point 3 to trigger Rule 1 (beyond 3-sigma limit)
    subgroups = [
        [10.0, 10.1, 9.9, 10.0],
        [10.1, 10.0, 9.9, 10.2],
        [25.0, 26.0, 24.5, 25.5],  # Out-of-control surge!
        [10.0, 9.9, 10.1, 10.0],
        [10.2, 10.0, 10.1, 9.9],
    ]
    res = calculate_spc_chart("Xbar-R", subgroups, usl=30.0, lsl=5.0)

    assert res["in_control"] is False
    assert res["stable"] is False
    assert len(res["violations"]) > 0
    assert "Process is not in statistical control" in (res["stability_note"] or "")
    # STRICT STABILITY GATE CHECK:
    assert res["capability"] is None


def test_imr_out_of_control_suppresses_capability() -> None:
    """I-MR chart with out-of-control point must yield capability=None."""
    values = [10.0, 10.1, 9.9, 10.0, 10.2, 50.0, 10.1, 9.9, 10.0]
    res = calculate_spc_chart("I-MR", values, usl=60.0, lsl=0.0)

    assert res["in_control"] is False
    assert res["stable"] is False
    assert res["capability"] is None


# ---------------------------------------------------------------------------
# Error Handling & Validation Tests
# ---------------------------------------------------------------------------


def test_invalid_spec_limits_inverted() -> None:
    """usl < lsl raises ValueError."""
    with pytest.raises(ValueError, match="USL cannot be less than LSL"):
        calculate_spc_chart("I-MR", [1.0, 2.0, 3.0], usl=10.0, lsl=20.0)


def test_invalid_chart_type() -> None:
    """Unknown chart type raises ValueError."""
    with pytest.raises(ValueError, match="Unknown or unsupported chart_type"):
        calculate_spc_chart("InvalidChart", [1.0, 2.0, 3.0])


def test_xbar_r_invalid_data_types_and_dimensions() -> None:
    """Xbar-R validation errors."""
    with pytest.raises(ValueError, match="Xbar-R chart requires data as a list of subgroups"):
        calculate_spc_chart("Xbar-R", [1.0, 2.0, 3.0])  # 1D list

    with pytest.raises(ValueError, match="Xbar-R chart requires data as a list of subgroups"):
        calculate_spc_chart("Xbar-R", [])  # empty

    with pytest.raises(ValueError, match="All subgroups in Xbar-R chart must have equal size"):
        calculate_spc_chart("Xbar-R", [[1.0, 2.0], [1.0, 2.0, 3.0]])  # unequal sizes

    with pytest.raises(ValueError, match="subgroup size between 2 and 10"):
        calculate_spc_chart("Xbar-R", [[1.0], [2.0]])  # n=1

    with pytest.raises(ValueError, match="subgroup size between 2 and 10"):
        calculate_spc_chart("Xbar-R", [[1.0] * 11, [2.0] * 11])  # n=11


def test_xbar_s_invalid_data_types_and_dimensions() -> None:
    """Xbar-S validation errors."""
    with pytest.raises(ValueError, match="Xbar-S chart requires data as a list of subgroups"):
        calculate_spc_chart("Xbar-S", [1.0, 2.0, 3.0])

    with pytest.raises(ValueError, match="Xbar-S chart requires data as a list of subgroups"):
        calculate_spc_chart("Xbar-S", [])

    with pytest.raises(ValueError, match="All subgroups in Xbar-S chart must have equal size"):
        calculate_spc_chart("Xbar-S", [[1.0, 2.0], [1.0, 2.0, 3.0]])

    with pytest.raises(ValueError, match="subgroup size between 2 and 12"):
        calculate_spc_chart("Xbar-S", [[1.0], [2.0]])

    with pytest.raises(ValueError, match="subgroup size between 2 and 12"):
        calculate_spc_chart("Xbar-S", [[1.0] * 15, [2.0] * 15])


def test_imr_invalid_data() -> None:
    """I-MR validation errors."""
    with pytest.raises(ValueError, match="I-MR chart requires data as a 1D list of values"):
        calculate_spc_chart("I-MR", [[1.0, 2.0]])  # 2D list

    with pytest.raises(ValueError, match="I-MR chart requires data as a 1D list of values"):
        calculate_spc_chart("I-MR", [])

    with pytest.raises(ValueError, match="I-MR chart requires at least two values"):
        calculate_spc_chart("I-MR", [10.0])


def test_p_invalid_data_and_sample_sizes() -> None:
    """p chart validation errors."""
    with pytest.raises(ValueError, match="p chart requires data as a list of defective counts"):
        calculate_spc_chart("p", [[1.0, 2.0]], sample_sizes=[10.0])

    with pytest.raises(ValueError, match="p chart requires data as a list of defective counts"):
        calculate_spc_chart("p", [], sample_sizes=[10.0])

    with pytest.raises(ValueError, match="p chart requires sample_sizes"):
        calculate_spc_chart("p", [1.0, 2.0], sample_sizes=None)


def test_c_invalid_data() -> None:
    """c chart validation errors."""
    with pytest.raises(ValueError, match="c chart requires data as a list of defect counts"):
        calculate_spc_chart("c", [[1.0, 2.0]])

    with pytest.raises(ValueError, match="c chart requires data as a list of defect counts"):
        calculate_spc_chart("c", [])


def test_u_invalid_data_and_sample_sizes() -> None:
    """u chart validation errors."""
    with pytest.raises(ValueError, match="u chart requires data as a list of defect counts"):
        calculate_spc_chart("u", [[1.0, 2.0]], sample_sizes=[10.0])

    with pytest.raises(ValueError, match="u chart requires data as a list of defect counts"):
        calculate_spc_chart("u", [], sample_sizes=[10.0])

    with pytest.raises(ValueError, match="u chart requires sample_sizes"):
        calculate_spc_chart("u", [1.0, 2.0], sample_sizes=None)


# ---------------------------------------------------------------------------
# FastMCP Integration & Client Roundtrip Tests
# ---------------------------------------------------------------------------


def test_spc_tool_fastmcp_call_tool_roundtrip() -> None:
    """calculate_spc_chart can be invoked through mcp.call_tool()."""
    values = [10.0, 10.2, 9.8, 10.1, 10.0, 9.9, 10.1, 10.0]
    args: dict[str, Any] = {
        "chart_type": "I-MR",
        "data": values,
        "usl": 11.0,
        "lsl": 9.0,
    }
    _, content = asyncio.run(mcp.call_tool("calculate_spc_chart", args))

    assert isinstance(content, dict)
    assert content["chart_type"] == "I-MR"
    assert content["in_control"] is True
    assert content["stable"] is True
    assert content["capability"] is not None
    assert content["capability"]["mean"] == pytest.approx(10.0125, abs=1e-3)

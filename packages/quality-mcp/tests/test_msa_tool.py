"""Tests for calculate_gage_rr MCP tool in quality_mcp.tools.msa.

Validates:
- Direct function execution with ANOVA and Average-and-Range methods.
- Tolerance-basis vs Study-basis metrics.
- FastMCP tool registration and invocation.
- Dict parity against quality_core.msa on AIAG reference benchmark and synthetic datasets.
- Structured error handling for invalid/unbalanced/malformed studies.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from quality_core.msa import (
    METHOD,
    METHOD_ANOVA,
    compute_gage_rr,
    load_gage_study_csv,
)
from quality_mcp.server import mcp
from quality_mcp.tools.msa import calculate_gage_rr

_AIAG_REFERENCE_STUDY_CSV = (
    Path(__file__).resolve().parents[2]
    / "quality-core"
    / "tests"
    / "data"
    / "aiag_reference_study.csv"
)

# Example B synthetic dataset (3 parts x 2 appraisers x 2 trials)
_EXAMPLE_B_DATA = [
    {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 2.0},
    {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 2.2},
    {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 2.5},
    {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 2.5},
    {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 4.0},
    {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 4.2},
    {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 4.5},
    {"part": "P2", "appraiser": "B", "trial": 2, "measurement": 4.5},
    {"part": "P3", "appraiser": "A", "trial": 1, "measurement": 6.0},
    {"part": "P3", "appraiser": "A", "trial": 2, "measurement": 6.2},
    {"part": "P3", "appraiser": "B", "trial": 1, "measurement": 6.5},
    {"part": "P3", "appraiser": "B", "trial": 2, "measurement": 6.5},
]


def test_calculate_gage_rr_example_b_anova() -> None:
    """Verify calculate_gage_rr defaults to ANOVA on Example B."""
    res = calculate_gage_rr(_EXAMPLE_B_DATA, tolerance=8.0)

    assert res["basis"] == "AIAG MSA 4th Edition"
    assert res["method"] == METHOD_ANOVA
    assert res["n_parts"] == 3
    assert res["n_appraisers"] == 2
    assert res["n_trials"] == 2
    assert res["is_balanced"] is True
    assert res["interaction"] is not None
    assert res["interaction_significant"] is False
    assert res["pgrr_tolerance"] is not None
    assert res["verdict"] in {"Accept", "Marginal", "Reject"}

    # Compare directly with quality_core.msa
    core_res = compute_gage_rr(_EXAMPLE_B_DATA, tolerance=8.0, method=METHOD_ANOVA)
    assert res["ev"] == pytest.approx(core_res["ev"], rel=1e-9)
    assert res["av"] == pytest.approx(core_res["av"], rel=1e-9)
    assert res["grr"] == pytest.approx(core_res["grr"], rel=1e-9)
    assert res["pv"] == pytest.approx(core_res["pv"], rel=1e-9)
    assert res["tv"] == pytest.approx(core_res["tv"], rel=1e-9)
    assert res["pgrr_study"] == pytest.approx(core_res["pgrr_study"], rel=1e-9)
    assert res["pgrr_tolerance"] == pytest.approx(core_res["pgrr_tolerance"], rel=1e-9)
    assert res["ndc"] == core_res["ndc"]
    assert res["verdict"] == core_res["verdict"]


def test_calculate_gage_rr_example_b_average_and_range() -> None:
    """Verify calculate_gage_rr supports Average-and-Range method."""
    res = calculate_gage_rr(_EXAMPLE_B_DATA, method=METHOD, tolerance=None)

    assert res["basis"] == "AIAG MSA 4th Edition"
    assert res["method"] == METHOD
    assert res["interaction"] is None
    assert res["interaction_f"] is None
    assert res["interaction_significant"] is None
    assert res["pgrr_tolerance"] is None

    core_res = compute_gage_rr(_EXAMPLE_B_DATA, tolerance=None, method=METHOD)
    assert res["grr"] == pytest.approx(core_res["grr"], rel=1e-9)
    assert res["pgrr_study"] == pytest.approx(core_res["pgrr_study"], rel=1e-9)
    assert res["ndc"] == core_res["ndc"]
    assert res["verdict"] == core_res["verdict"]


def test_calculate_gage_rr_aiag_reference_parity() -> None:
    """Verify parity on canonical AIAG reference 10x3x3 dataset."""
    df = load_gage_study_csv(str(_AIAG_REFERENCE_STUDY_CSV))
    records: list[dict[str, Any]] = df.to_dict(orient="records")

    res_anova = calculate_gage_rr(records, method=METHOD_ANOVA, tolerance=4.42)
    core_anova = compute_gage_rr(records, method=METHOD_ANOVA, tolerance=4.42)

    assert res_anova["basis"] == "AIAG MSA 4th Edition"
    assert res_anova["grr"] == pytest.approx(core_anova["grr"], rel=1e-9)
    assert res_anova["pgrr_study"] == pytest.approx(core_anova["pgrr_study"], rel=1e-9)
    assert res_anova["pgrr_tolerance"] == pytest.approx(core_anova["pgrr_tolerance"], rel=1e-9)
    assert res_anova["ndc"] == 4
    assert res_anova["verdict"] == "Reject"

    res_avg = calculate_gage_rr(records, method=METHOD, tolerance=4.42)
    core_avg = compute_gage_rr(records, method=METHOD, tolerance=4.42)
    assert res_avg["grr"] == pytest.approx(core_avg["grr"], rel=1e-9)
    assert res_avg["ndc"] == 5
    assert res_avg["verdict"] == "Reject"


def test_fastmcp_calculate_gage_rr_invocation() -> None:
    """Verify FastMCP server registers and executes calculate_gage_rr."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            assert "calculate_gage_rr" in tool_names

            tool = next(t for t in tools_result.tools if t.name == "calculate_gage_rr")
            assert tool.description is not None
            assert "Gage R&R" in tool.description or "AIAG" in tool.description
            assert tool.inputSchema is not None
            properties = tool.inputSchema.get("properties", {})
            assert "measurements" in properties
            assert "method" in properties
            assert "tolerance" in properties

            res = await session.call_tool(
                "calculate_gage_rr",
                {"measurements": _EXAMPLE_B_DATA, "tolerance": 8.0, "method": "anova"},
            )
            assert res.isError is False
            assert res.structuredContent is not None
            assert res.structuredContent["basis"] == "AIAG MSA 4th Edition"
            assert res.structuredContent["method"] == METHOD_ANOVA
            assert res.structuredContent["verdict"] in {"Accept", "Marginal", "Reject"}
            assert res.structuredContent["ndc"] >= 1
            assert len(res.content) == 1
            assert isinstance(res.content[0], TextContent)
            assert res.content[0].type == "text"

    asyncio.run(_run())


def test_invalid_study_empty_raises() -> None:
    """Verify empty study raises ValueError."""
    with pytest.raises(ValueError, match="at least one measurement"):
        calculate_gage_rr([])


def test_invalid_study_missing_columns_raises() -> None:
    """Verify missing required keys raises ValueError."""
    with pytest.raises(ValueError, match="Missing required columns"):
        calculate_gage_rr([{"part": "P1", "appraiser": "A"}])


def test_invalid_study_single_part_raises() -> None:
    """Verify study with fewer than 2 parts raises ValueError."""
    data = [
        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.1},
        {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.0},
        {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 10.1},
    ]
    with pytest.raises(ValueError, match="at least 2 parts"):
        calculate_gage_rr(data)


def test_invalid_study_single_appraiser_raises() -> None:
    """Verify study with fewer than 2 appraisers raises ValueError."""
    data = [
        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.1},
        {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 10.1},
    ]
    with pytest.raises(ValueError, match="at least 2 appraisers"):
        calculate_gage_rr(data)


def test_invalid_study_single_trial_raises() -> None:
    """Verify study with fewer than 2 trials raises ValueError."""
    data = [
        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.1},
        {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 10.1},
    ]
    with pytest.raises(ValueError, match="at least 2 trials"):
        calculate_gage_rr(data)


def test_invalid_study_unbalanced_raises() -> None:
    """Verify unbalanced study raises ValueError."""
    data = [
        {"part": "P1", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P1", "appraiser": "A", "trial": 2, "measurement": 10.1},
        {"part": "P1", "appraiser": "A", "trial": 3, "measurement": 10.2},
        {"part": "P1", "appraiser": "B", "trial": 1, "measurement": 10.0},
        {"part": "P1", "appraiser": "B", "trial": 2, "measurement": 10.1},
        {"part": "P2", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P2", "appraiser": "A", "trial": 2, "measurement": 10.1},
        {"part": "P2", "appraiser": "B", "trial": 1, "measurement": 10.0},
        {"part": "P2", "appraiser": "B", "trial": 2, "measurement": 10.1},
    ]
    with pytest.raises(ValueError, match="Data is unbalanced"):
        calculate_gage_rr(data)


def test_invalid_method_raises() -> None:
    """Verify unknown method raises ValueError."""
    with pytest.raises(ValueError, match="Unknown method"):
        calculate_gage_rr(_EXAMPLE_B_DATA, method="bogus")


def test_invalid_tolerance_negative_raises() -> None:
    """Verify negative tolerance raises ValueError."""
    with pytest.raises(ValueError, match="positive finite"):
        calculate_gage_rr(_EXAMPLE_B_DATA, tolerance=-1.0)

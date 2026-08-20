"""
Unit and integration tests for 5-Why RCA FastMCP tools in quality_mcp.tools.rca.

Tests:
1. validate_5why direct execution:
   - Default sample execution (None steps) loads reference Ford Global 8D bearing case.
   - Custom valid 5-Why steps execution.
   - Custom problem statement, root cause, and leg_type handling.
   - Empty steps list [] handling (returns PREMATURE_TERMINATION).
   - Schema validation error handling (returns SCHEMA_VALIDATION_ERROR).
   - Type errors: problem_statement, root_cause, leg_type, steps, step items.
   - Value errors: empty problem_statement.
2. render_5why_canvas direct execution:
   - Default sample execution (None steps).
   - Custom steps execution with and without step_number autoincrement.
   - Custom problem_statement, root_cause, and leg_type on sample dataset.
   - Themes: "dark" and "light".
   - Standalone: True and False.
   - Type errors: standalone (non-bool / int), title, problem_statement, steps, step items.
   - Value errors: empty title, empty problem_statement, invalid theme.
3. FastMCP in-process client-server round-trip integration tests:
   - Server initialization and tool discovery (validate_5why, render_5why_canvas).
   - Tool execution over memory transport with dual-payload verification.
   - Protocol error handling on invalid tool arguments.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from quality_mcp.server import mcp
from quality_mcp.tools.rca import (
    categorize_fishbone,
    render_5why_canvas,
    render_fishbone_canvas,
    validate_5why,
)

# ---------------------------------------------------------------------------
# 1. validate_5why Direct Function Execution Tests
# ---------------------------------------------------------------------------


def test_validate_5why_default_sample() -> None:
    """validate_5why() with no arguments evaluates reference Ford Global 8D bearing case."""
    result = validate_5why()
    assert result["basis"] == "AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox"
    assert result["valid"] is True
    assert result["verdict"] == "ACCEPT"
    assert result["reversibility_score"] == 1.0
    assert result["total_steps"] == 5
    assert result["leg_type"] == "occurrence"
    assert result["systemic_assessment"]["is_systemic"] is True
    assert len(result["link_evaluations"]) == 5


def test_validate_5why_custom_steps() -> None:
    """validate_5why() with custom valid steps returns structured results."""
    steps = [
        {"step_number": 1, "why": "Why did motor stall?", "because": "Belt jammed."},
        {"step_number": 2, "why": "Why did belt jam?", "because": "Assembly procedure omitted tension check."},
    ]
    result = validate_5why(
        steps=steps,
        problem_statement="Motor stalled",
        root_cause="Assembly procedure omitted tension check",
        leg_type="occurrence",
    )
    assert result["valid"] is True
    assert result["verdict"] == "ACCEPT"
    assert result["total_steps"] == 2
    assert result["problem_statement"] == "Motor stalled"
    assert result["root_cause"] == "Assembly procedure omitted tension check"
    assert result["leg_type"] == "occurrence"


def test_validate_5why_empty_steps() -> None:
    """validate_5why(steps=[]) returns valid=False, verdict=REJECT, and PREMATURE_TERMINATION finding."""
    result = validate_5why(steps=[], problem_statement="No steps")
    assert result["valid"] is False
    assert result["verdict"] == "REJECT"
    assert result["total_steps"] == 0
    assert any(ap["code"] == "PREMATURE_TERMINATION" for ap in result["anti_patterns"])


def test_validate_5why_schema_validation_error() -> None:
    """validate_5why() with non-consecutive steps catches ValidationError and returns SCHEMA_VALIDATION_ERROR."""
    steps = [
        {"step_number": 1, "why": "Why 1?", "because": "Because 1."},
        {"step_number": 3, "why": "Why 3?", "because": "Because 3."},  # missing step 2
    ]
    result = validate_5why(steps=steps)
    assert result["valid"] is False
    assert result["verdict"] == "REJECT"
    assert any(ap["code"] == "SCHEMA_VALIDATION_ERROR" for ap in result["anti_patterns"])
    assert any("Schema validation error" in r for r in result["recommendations"])


def test_validate_5why_type_and_value_errors() -> None:
    """validate_5why() raises TypeError and ValueError on invalid argument types."""
    # problem_statement
    with pytest.raises(TypeError, match="problem_statement must be a string"):
        validate_5why(problem_statement=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="problem_statement must be a string"):
        validate_5why(problem_statement=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="problem_statement must not be empty"):
        validate_5why(problem_statement="   ")

    # root_cause
    with pytest.raises(TypeError, match="root_cause must be a string or None"):
        validate_5why(root_cause=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="root_cause must be a string or None"):
        validate_5why(root_cause=False)  # type: ignore[arg-type]

    # leg_type
    with pytest.raises(TypeError, match="leg_type must be a string or None"):
        validate_5why(leg_type=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="leg_type must be a string or None"):
        validate_5why(leg_type=True)  # type: ignore[arg-type]

    # steps
    with pytest.raises(TypeError, match="steps must be a list of dictionaries or None"):
        validate_5why(steps="invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="steps item at index 0 must be a dict"):
        validate_5why(steps=["not-a-dict"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# 2. render_5why_canvas Direct Function Execution Tests
# ---------------------------------------------------------------------------


def test_render_5why_canvas_default_sample() -> None:
    """render_5why_canvas() with default arguments renders sample benchmark canvas."""
    result = render_5why_canvas()
    assert result["title"] == "5-Why Root Cause Analysis Canvas"
    assert result["rows_count"] == 5
    assert result["steps_count"] == 5
    assert result["valid"] is True
    assert result["verdict"] == "ACCEPT"
    assert result["reversibility_score"] == 1.0
    assert "<!DOCTYPE html>" in result["html"]
    assert "Hole positions outside of tolerance" in result["html"]


def test_render_5why_canvas_custom_dataset() -> None:
    """render_5why_canvas() with custom steps, theme, and embeddable mode."""
    custom_steps = [
        {"why": "Why did pump leak?", "because": "O-ring cracked."},  # step_number omitted, tests autoincrement
        {"why": "Why did O-ring crack?", "because": "Material specification omitted temperature limit."},
    ]
    result = render_5why_canvas(
        steps=custom_steps,
        problem_statement="Pump leaked oil",
        root_cause="Material specification omitted temperature limit",
        leg_type="occurrence",
        title="Pump Leak 5-Why",
        theme="light",
        standalone=False,
    )
    assert result["title"] == "Pump Leak 5-Why"
    assert result["rows_count"] == 2
    assert result["valid"] is True
    assert "<!DOCTYPE html>" not in result["html"]
    assert "Pump leaked oil" in result["html"]


def test_render_5why_canvas_sample_overrides() -> None:
    """render_5why_canvas(steps=None) with custom problem_statement, root_cause, leg_type."""
    result = render_5why_canvas(
        steps=None,
        problem_statement="Custom Problem",
        root_cause="Custom Root Cause",
        leg_type="systemic",
    )
    assert "Custom Problem" in result["html"]
    assert "Custom Root Cause" in result["html"]
    assert "SYSTEMIC" in result["html"]


def test_render_5why_canvas_type_and_value_errors() -> None:
    """render_5why_canvas() raises TypeError and ValueError on invalid inputs."""
    # standalone
    with pytest.raises(TypeError, match="standalone must be a boolean"):
        render_5why_canvas(standalone=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="standalone must be a boolean"):
        render_5why_canvas(standalone="true")  # type: ignore[arg-type]

    # title
    with pytest.raises(TypeError, match="title must be a string"):
        render_5why_canvas(title=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="title must not be empty"):
        render_5why_canvas(title="   ")

    # problem_statement
    with pytest.raises(TypeError, match="problem_statement must be a string"):
        render_5why_canvas(problem_statement=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="problem_statement must not be empty"):
        render_5why_canvas(problem_statement="")

    # theme
    with pytest.raises(ValueError, match="theme must be 'dark' or 'light'"):
        render_5why_canvas(theme="neon")

    # steps
    with pytest.raises(TypeError, match="steps must be a list of dictionaries or None"):
        render_5why_canvas(steps="not-a-list")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="steps item at index 0 must be a dict"):
        render_5why_canvas(steps=[123])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# 3. FastMCP In-Process Client-Server Round-Trip Tests
# ---------------------------------------------------------------------------


def test_mcp_client_session_handshake_and_5why_tool_discovery() -> None:
    """In-process FastMCP client session initializes and discovers validate_5why and render_5why_canvas."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "quality-mcp"
            assert init_result.serverInfo.version is not None

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            assert "validate_5why" in tool_names
            assert "render_5why_canvas" in tool_names

            # Check tool metadata
            v5_tool = next(t for t in tools_result.tools if t.name == "validate_5why")
            assert v5_tool.description is not None
            assert "5-Why" in v5_tool.description
            assert v5_tool.inputSchema is not None

            r5_tool = next(t for t in tools_result.tools if t.name == "render_5why_canvas")
            assert r5_tool.description is not None
            assert "canvas" in r5_tool.description.lower()

    asyncio.run(_run())


def test_mcp_client_session_validate_5why_roundtrip() -> None:
    """Execute validate_5why over in-process FastMCP client session with dual-payload verification."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Call with default arguments (None)
            result = await session.call_tool("validate_5why", {})
            assert not result.isError
            assert len(result.content) > 0
            text_payload = result.content[0].text  # type: ignore[union-attr]
            data = json.loads(text_payload)
            assert data["basis"] == "AIAG CQI-20 / Ford Global 8D / ASQ Quality Toolbox"
            assert data["valid"] is True
            assert data["verdict"] == "ACCEPT"
            assert data["reversibility_score"] == 1.0

            # Dual-payload parity: structuredContent vs content[0].text
            if hasattr(result, "structuredContent") and result.structuredContent is not None:
                assert result.structuredContent["verdict"] == data["verdict"]
                assert result.structuredContent["reversibility_score"] == data["reversibility_score"]

            # 2. Call with custom valid steps
            custom_steps = [
                {"step_number": 1, "why": "Why valve leaked?", "because": "Packing seal dried out."},
                {"step_number": 2, "why": "Why packing seal dried out?", "because": "Preventive maintenance procedure lacked packing replacement schedule."},
            ]
            res_custom = await session.call_tool(
                "validate_5why",
                {
                    "steps": custom_steps,
                    "problem_statement": "Valve leaked steam",
                    "root_cause": "Preventive maintenance procedure lacked packing replacement schedule",
                    "leg_type": "occurrence",
                },
            )
            assert not res_custom.isError
            data_custom = json.loads(res_custom.content[0].text)  # type: ignore[union-attr]
            assert data_custom["valid"] is True
            assert data_custom["total_steps"] == 2
            assert data_custom["systemic_assessment"]["is_systemic"] is True

            # 3. Call with invalid circular loop -> rejected
            bad_steps = [
                {"step_number": 1, "why": "Why valve leaked?", "because": "Valve leaked steam."},
                {"step_number": 2, "why": "Why did it leak?", "because": "Packing seal dried out."},
            ]
            res_bad = await session.call_tool(
                "validate_5why",
                {"steps": bad_steps, "problem_statement": "Valve leaked steam"},
            )
            assert not res_bad.isError
            data_bad = json.loads(res_bad.content[0].text)  # type: ignore[union-attr]
            assert data_bad["valid"] is False
            assert data_bad["verdict"] == "REJECT"

    asyncio.run(_run())


def test_mcp_client_session_render_5why_canvas_roundtrip() -> None:
    """Execute render_5why_canvas over in-process FastMCP client session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Default render
            result = await session.call_tool("render_5why_canvas", {})
            assert not result.isError
            data = json.loads(result.content[0].text)  # type: ignore[union-attr]
            assert data["title"] == "5-Why Root Cause Analysis Canvas"
            assert data["rows_count"] == 5
            assert "<!DOCTYPE html>" in data["html"]

            # 2. Custom render embedded
            custom_steps = [
                {"step_number": 1, "why": "Why tool broke?", "because": "Feed rate too high."},
                {"step_number": 2, "why": "Why feed rate too high?", "because": "CNC program feed rate parameter was not validated by engineering."},
            ]
            res_custom = await session.call_tool(
                "render_5why_canvas",
                {
                    "steps": custom_steps,
                    "problem_statement": "Tool broke during roughing",
                    "theme": "light",
                    "standalone": False,
                },
            )
            assert not res_custom.isError
            data_custom = json.loads(res_custom.content[0].text)  # type: ignore[union-attr]
            assert data_custom["rows_count"] == 2
            assert "<!DOCTYPE html>" not in data_custom["html"]
            assert "Tool broke during roughing" in data_custom["html"]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4. categorize_fishbone Direct Function Execution Tests
# ---------------------------------------------------------------------------


def test_categorize_fishbone_default_sample() -> None:
    """categorize_fishbone() with no arguments evaluates reference Sentinel-8D cylinder case."""
    result = categorize_fishbone()
    assert result["basis"] == "Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox"
    assert result["valid"] is True
    assert result["verdict"] == "ACCEPT"
    assert result["total_causes"] == 12
    assert result["empty_branches"] == []
    assert len(result["duplicate_causes"]) == 0
    assert len(result["warnings"]) == 0


def test_categorize_fishbone_custom_causes_and_effects() -> None:
    """categorize_fishbone() with custom causes, effect, and effect_statement alias."""
    custom_causes = [
        {"category": "Man", "cause": "Operator error", "sub_category": "Training"},
        {"category": "Machine", "cause": "Spindle runout", "sub_category": "Tooling"},
        {"category": "Method", "cause": "Missing torque spec", "sub_category": "Process"},
        {"category": "Material", "cause": "Seal batch hardness", "sub_category": "Material"},
        {"category": "Measurement", "cause": "Gage drift", "sub_category": "Calibration"},
        {"category": "Environment", "cause": "Ambient temp fluctuation", "sub_category": "HVAC"},
    ]

    # With effect
    res1 = categorize_fishbone(causes=custom_causes, effect="Custom Problem")
    assert res1["valid"] is True
    assert res1["verdict"] == "ACCEPT"
    assert res1["effect_statement"] == "Custom Problem"
    assert res1["total_causes"] == 6

    # With effect_statement overriding effect
    res2 = categorize_fishbone(causes=custom_causes, effect="Ignored", effect_statement="Overridden Problem")
    assert res2["effect_statement"] == "Overridden Problem"


def test_categorize_fishbone_empty_causes() -> None:
    """categorize_fishbone(causes=[]) returns valid=False, verdict=REJECT, and empty dataset warning."""
    result = categorize_fishbone(causes=[], effect="No causes")
    assert result["valid"] is False
    assert result["verdict"] == "REJECT"
    assert result["total_causes"] == 0
    assert len(result["empty_branches"]) == 6
    assert "Fishbone dataset contains no causes." in result["warnings"][0]


def test_categorize_fishbone_type_and_value_errors() -> None:
    """categorize_fishbone() raises TypeError and ValueError on invalid argument types."""
    # check_balance
    with pytest.raises(TypeError, match="check_balance must be a boolean"):
        categorize_fishbone(check_balance=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="check_balance must be a boolean"):
        categorize_fishbone(check_balance="true")  # type: ignore[arg-type]

    # balance_threshold
    with pytest.raises(TypeError, match="balance_threshold must be a float"):
        categorize_fishbone(balance_threshold=True)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="balance_threshold must be a float"):
        categorize_fishbone(balance_threshold="0.75")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="balance_threshold must be a float between 0 and 1"):
        categorize_fishbone(balance_threshold=0.0)

    with pytest.raises(ValueError, match="balance_threshold must be a float between 0 and 1"):
        categorize_fishbone(balance_threshold=1.5)

    # effect / effect_statement
    with pytest.raises(TypeError, match="effect must be a string"):
        categorize_fishbone(effect=123)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="effect must be a string"):
        categorize_fishbone(effect=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="effect must not be empty"):
        categorize_fishbone(effect="   ")

    # causes
    with pytest.raises(TypeError, match="causes must be a list of dictionaries or None"):
        categorize_fishbone(causes="invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="causes item at index 0 must be a dict"):
        categorize_fishbone(causes=["not-a-dict"])  # type: ignore[list-item]


def test_categorize_fishbone_schema_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """categorize_fishbone() catches pydantic.ValidationError and returns structured REJECT result."""
    import pydantic
    import quality_mcp.tools.rca as rca_tool_mod

    class DummyModel(pydantic.BaseModel):
        x: int

    def _mock_raise(*args: Any, **kwargs: Any) -> Any:
        DummyModel(x="not-an-int")  # type: ignore[arg-type]

    monkeypatch.setattr(rca_tool_mod, "_categorize_fishbone", _mock_raise)
    result = categorize_fishbone(causes=[{"category": "Man", "cause": "Operator error"}])
    assert result["valid"] is False
    assert result["verdict"] == "REJECT"
    assert any("Schema validation error" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# 5. render_fishbone_canvas Direct Function Execution Tests
# ---------------------------------------------------------------------------


def test_render_fishbone_canvas_default_sample() -> None:
    """render_fishbone_canvas() with default arguments renders sample benchmark canvas."""
    result = render_fishbone_canvas()
    assert result["title"] == "6M Fishbone Cause-and-Effect Canvas"
    assert result["rows_count"] == 12
    assert result["causes_count"] == 12
    assert result["valid"] is True
    assert result["verdict"] == "ACCEPT"
    assert "<!DOCTYPE html>" in result["html"]
    assert "qes-fishbone-canvas" in result["html"]
    assert "Pneumatic cylinder" in result["html"]


def test_render_fishbone_canvas_sample_with_custom_effect() -> None:
    """render_fishbone_canvas() with causes=None and custom effect overrides sample effect."""
    result = render_fishbone_canvas(causes=None, effect="Custom Hydraulic Cylinder Failure")
    assert result["rows_count"] == 12
    assert "Custom Hydraulic Cylinder Failure" in result["html"]


def test_render_fishbone_canvas_custom_dataset() -> None:
    """render_fishbone_canvas() with custom causes, theme, and embeddable mode."""
    custom_causes = [
        {"category": "Machine", "cause": "CNC spindle vibration", "sub_category": "Tooling"},
        {"category": "Material", "cause": "Aluminum rod hardness low", "sub_category": "Raw Material"},
    ]
    result = render_fishbone_canvas(
        causes=custom_causes,
        effect="Machining chatter",
        effect_statement="Machining chatter defect",
        title="Custom Machining Fishbone",
        theme="light",
        standalone=False,
        balance_threshold=0.80,
    )
    assert result["title"] == "Custom Machining Fishbone"
    assert result["rows_count"] == 2
    assert result["causes_count"] == 2
    assert "<!DOCTYPE html>" not in result["html"]
    assert "Machining chatter defect" in result["html"]


def test_render_fishbone_canvas_type_and_value_errors() -> None:
    """render_fishbone_canvas() raises TypeError and ValueError on invalid inputs."""
    # standalone
    with pytest.raises(TypeError, match="standalone must be a boolean"):
        render_fishbone_canvas(standalone=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="standalone must be a boolean"):
        render_fishbone_canvas(standalone="true")  # type: ignore[arg-type]

    # title
    with pytest.raises(TypeError, match="title must be a string"):
        render_fishbone_canvas(title=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="title must not be empty"):
        render_fishbone_canvas(title="   ")

    # effect
    with pytest.raises(TypeError, match="effect must be a string"):
        render_fishbone_canvas(effect=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="effect must not be empty"):
        render_fishbone_canvas(effect="   ")

    # theme
    with pytest.raises(ValueError, match="theme must be 'dark' or 'light'"):
        render_fishbone_canvas(theme="neon")

    # balance_threshold
    with pytest.raises(TypeError, match="balance_threshold must be a float"):
        render_fishbone_canvas(balance_threshold=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="balance_threshold must be a float between 0 and 1"):
        render_fishbone_canvas(balance_threshold=-0.5)

    # causes
    with pytest.raises(TypeError, match="causes must be a list of dictionaries or None"):
        render_fishbone_canvas(causes="invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="causes item at index 0 must be a dict"):
        render_fishbone_canvas(causes=["not-a-dict"])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# 6. FastMCP Client-Server Round-Trip Integration Tests (Fishbone)
# ---------------------------------------------------------------------------


def test_mcp_client_session_categorize_fishbone_roundtrip() -> None:
    """Execute categorize_fishbone over in-process FastMCP client session with dual-payload verification."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Call with default arguments (None)
            result = await session.call_tool("categorize_fishbone", {})
            assert not result.isError
            assert len(result.content) > 0
            text_payload = result.content[0].text  # type: ignore[union-attr]
            data = json.loads(text_payload)
            assert data["basis"] == "Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox"
            assert data["valid"] is True
            assert data["verdict"] == "ACCEPT"
            assert data["total_causes"] == 12
            assert data["empty_branches"] == []

            # Dual-payload parity
            if hasattr(result, "structuredContent") and result.structuredContent is not None:
                assert result.structuredContent["verdict"] == data["verdict"]
                assert result.structuredContent["total_causes"] == data["total_causes"]

            # 2. Call with custom valid causes across 6M
            custom_causes = [
                {"category": "Man", "cause": "Operator fatigue"},
                {"category": "Machine", "cause": "Spindle runout"},
                {"category": "Method", "cause": "Work instruction vague"},
                {"category": "Material", "cause": "Seal hardness high"},
                {"category": "Measurement", "cause": "Gage drift"},
                {"category": "Environment", "cause": "Ambient temp swing"},
            ]
            res_custom = await session.call_tool(
                "categorize_fishbone",
                {
                    "causes": custom_causes,
                    "effect": "Cylinder leak",
                },
            )
            assert not res_custom.isError
            data_custom = json.loads(res_custom.content[0].text)  # type: ignore[union-attr]
            assert data_custom["valid"] is True
            assert data_custom["verdict"] == "ACCEPT"
            assert data_custom["total_causes"] == 6

            # 3. Call with empty causes -> rejected
            res_empty = await session.call_tool(
                "categorize_fishbone",
                {"causes": []},
            )
            assert not res_empty.isError
            data_empty = json.loads(res_empty.content[0].text)  # type: ignore[union-attr]
            assert data_empty["valid"] is False
            assert data_empty["verdict"] == "REJECT"

    asyncio.run(_run())


def test_mcp_client_session_render_fishbone_canvas_roundtrip() -> None:
    """Execute render_fishbone_canvas over in-process FastMCP client session."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as session:
            await session.initialize()

            # 1. Default render
            result = await session.call_tool("render_fishbone_canvas", {})
            assert not result.isError
            data = json.loads(result.content[0].text)  # type: ignore[union-attr]
            assert data["title"] == "6M Fishbone Cause-and-Effect Canvas"
            assert data["rows_count"] == 12
            assert "<!DOCTYPE html>" in data["html"]

            # 2. Custom render embedded
            custom_causes = [
                {"category": "Machine", "cause": "Tool chatter", "sub_category": "Vibration"},
                {"category": "Method", "cause": "Feed rate unoptimized", "sub_category": "Parameters"},
            ]
            res_custom = await session.call_tool(
                "render_fishbone_canvas",
                {
                    "causes": custom_causes,
                    "effect": "Surface roughness defect",
                    "theme": "light",
                    "standalone": False,
                },
            )
            assert not res_custom.isError
            data_custom = json.loads(res_custom.content[0].text)  # type: ignore[union-attr]
            assert data_custom["rows_count"] == 2
            assert "<!DOCTYPE html>" not in data_custom["html"]
            assert "Surface roughness defect" in data_custom["html"]

    asyncio.run(_run())


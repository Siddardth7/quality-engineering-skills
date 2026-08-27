"""
Unit and integration tests for quality_mcp SQE (Supplier Quality Engineering) FastMCP tools.

Covers (issue #122):
1. 100% line & branch coverage on quality_mcp.tools.sqe.
2. All 6 FastMCP tools: calculate_supplier_ppm, calculate_otif, calculate_vendor_scorecard,
   evaluate_escalation, generate_scar, render_sqe_canvas.
3. Schema generation: Annotated Field descriptions on every parameter.
4. Benchmark dataset fallbacks on None input; explicit empty-list handling.
5. Empty / malformed input returning fully-shaped INDETERMINATE payloads (evaluate_escalation).
6. The three invariant negative controls (no-standard-implied, commercial-authority,
   root-cause-authorship) applied to BOTH the tool descriptions AND the benchmark payloads.
7. Type-guard negative controls per tool (boolean rejection, wrong container types, bad theme/title).
8. FastMCP in-process client three-way parity per tool
   (structuredContent == serialized text JSON == direct Python call).

NOTE ON THE VALIDATIONERROR CONTROL: render_sqe_canvas and evaluate_escalation construct no pydantic
model on their success paths, so they have no `except pydantic.ValidationError` branch of their own
and are deliberately omitted from the monkeypatch ValidationError controls below — that omission is
intentional, not a coverage gap. The other four tools each build a pydantic model and are covered
both through the public surface (inverted period window / blank issue_description) and via a
monkeypatch forcing the private core to raise.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from typing import Annotated, Any, get_args, get_origin, get_type_hints

import pydantic
import pytest
import quality_mcp
import quality_mcp.tools
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextContent
from pydantic.fields import FieldInfo
from quality_mcp.server import mcp
from quality_mcp.tools.sqe import (
    _BENCHMARK_SCAR_REQUEST,
    _clean_validation_error,
    calculate_otif,
    calculate_supplier_ppm,
    calculate_vendor_scorecard,
    evaluate_escalation,
    generate_scar,
    render_sqe_canvas,
)

_SQE_TOOL_NAMES = [
    "calculate_supplier_ppm",
    "calculate_otif",
    "calculate_vendor_scorecard",
    "evaluate_escalation",
    "generate_scar",
    "render_sqe_canvas",
]

_SQE_TOOLS = [
    calculate_supplier_ppm,
    calculate_otif,
    calculate_vendor_scorecard,
    evaluate_escalation,
    generate_scar,
    render_sqe_canvas,
]


# ===========================================================================
# 1. Module exports
# ===========================================================================


def test_sqe_module_exports() -> None:
    """quality_mcp and quality_mcp.tools re-export all six SQE tools."""
    for name in _SQE_TOOL_NAMES:
        assert hasattr(quality_mcp, name)
        assert hasattr(quality_mcp.tools, name)
        assert name in quality_mcp.__all__
        assert name in quality_mcp.tools.__all__


# ===========================================================================
# 2. Parameter schema / Field annotations
# ===========================================================================


@pytest.mark.parametrize("tool_fn", _SQE_TOOLS)
def test_tool_signatures_have_annotated_field_descriptions(tool_fn: Any) -> None:
    """Every parameter of each SQE tool must be Annotated with a non-empty Field(description=...)."""
    sig = inspect.signature(tool_fn)
    hints = get_type_hints(tool_fn, include_extras=True)
    for param_name in sig.parameters:
        assert param_name in hints, f"{tool_fn.__name__}.{param_name} lacks type hint"
        annotated_type = hints[param_name]
        assert get_origin(annotated_type) is Annotated, (
            f"{tool_fn.__name__}.{param_name} is not Annotated, got {annotated_type}"
        )
        field_infos = [a for a in get_args(annotated_type) if isinstance(a, FieldInfo)]
        assert len(field_infos) == 1, f"{tool_fn.__name__}.{param_name} lacks FieldInfo"
        assert field_infos[0].description, (
            f"{tool_fn.__name__}.{param_name} has empty Field description"
        )


# ===========================================================================
# 3. Per-tool benchmark-fallback / behaviour tests
# ===========================================================================


def test_calculate_supplier_ppm_benchmark() -> None:
    """calculate_supplier_ppm(None) resolves the benchmark receipt dataset to MEASURED."""
    res = calculate_supplier_ppm(None)
    assert res["verdict"] == "MEASURED"
    assert res["ppm"] == 400.0
    assert res["dpmo"] == 100.0
    assert res["denominator"] == 15000
    assert res["lot_count"] == 3
    assert res["basis"] == res["standards_basis"]


def test_calculate_supplier_ppm_empty_list() -> None:
    """calculate_supplier_ppm(lots=[]) reaches the engine as a bare [] -> INDETERMINATE."""
    res = calculate_supplier_ppm(lots=[])
    assert res["verdict"] == "INDETERMINATE"
    assert res["ppm"] is None
    assert res["numerator"] is None
    assert res["denominator"] == 0
    assert res["lot_count"] == 0
    assert res["reason"]


def test_calculate_supplier_ppm_config_override() -> None:
    """sample_adequacy_minimum override builds a PPMConfig (the is-not-None branch)."""
    res = calculate_supplier_ppm(None, sample_adequacy_minimum=500)
    assert res["verdict"] == "MEASURED"


def test_calculate_otif_benchmark() -> None:
    """calculate_otif(None) resolves the benchmark delivery dataset to MEASURED."""
    res = calculate_otif(None)
    assert res["verdict"] == "MEASURED"
    assert res["on_time_pct"] == 100.0
    assert res["in_full_pct"] == pytest.approx(66.6666667, abs=1e-4)
    assert res["otif_pct"] == pytest.approx(66.6666667, abs=1e-4)
    assert res["delivery_count"] == 3
    assert res["basis"] == res["standards_basis"]


def test_calculate_otif_empty_list() -> None:
    """calculate_otif(deliveries=[]) -> INDETERMINATE with all three percentages None."""
    res = calculate_otif(deliveries=[])
    assert res["verdict"] == "INDETERMINATE"
    assert res["on_time_pct"] is None
    assert res["in_full_pct"] is None
    assert res["otif_pct"] is None


def test_calculate_otif_config_override() -> None:
    """A supplied OTIF override builds an OTIFConfig (the otif_kwargs-truthy branch)."""
    res = calculate_otif(None, late_tolerance_days=0)
    assert res["verdict"] == "MEASURED"


def test_calculate_vendor_scorecard_benchmark() -> None:
    """calculate_vendor_scorecard(None, None, None) composes to composite ~84.27, band B."""
    res = calculate_vendor_scorecard(None, None, None)
    assert res["verdict"] == "RATED"
    # Independently recomputed: quality sub-score from ppm=400 on curve [0,10000] ->
    # 100*(1-400/10000)=96.0 * 0.60; delivery sub-score from otif=66.666 on [100,0] ->
    # 66.666 * 0.40. 96.0*0.6 + 66.6667*0.4 = 57.6 + 26.6667 = 84.2667.
    assert res["composite_score"] == pytest.approx(84.2667, abs=1e-3)
    assert res["band"] == "B"
    assert res["basis"] == res["standards_basis"]


def test_calculate_vendor_scorecard_empty_lists() -> None:
    """Both evidence lists empty -> INDETERMINATE, no composite/band, reason names both blockers."""
    res = calculate_vendor_scorecard(lots=[], deliveries=[])
    assert res["verdict"] == "INDETERMINATE"
    assert res["composite_score"] is None
    assert res["band"] is None
    assert "ppm" in res["reason"].lower()
    assert "otif" in res["reason"].lower()


def test_calculate_vendor_scorecard_curve_overrides() -> None:
    """quality_curve as an array and delivery_curve as a mapping both rebuild and score."""
    res = calculate_vendor_scorecard(
        None,
        None,
        None,
        quality_curve=[0.0, 10000.0],
        delivery_curve={"best_value": 100.0, "worst_value": 0.0},
    )
    assert res["verdict"] == "RATED"
    assert res["band"] == "B"


def test_calculate_vendor_scorecard_subconfig_overrides() -> None:
    """ppm_config / otif_config dict overrides rebuild PPMConfig / OTIFConfig (is-not-None arms)."""
    res = calculate_vendor_scorecard(
        None,
        None,
        None,
        ppm_config={"sample_adequacy_minimum": 500},
        otif_config={"late_tolerance_days": 0},
    )
    assert res["verdict"] == "RATED"


def test_calculate_vendor_scorecard_cost_weight_without_curve_raises_plain_valueerror() -> None:
    """A positive cost weight with no cost_curve raises ScorecardConfig's own plain ValueError.

    This is intentionally OUTSIDE the pydantic try/except (ScorecardConfig is a dataclass), so it is
    NOT a wrapped pydantic error — it propagates unwrapped and names the cost_curve requirement.
    """
    with pytest.raises(ValueError, match="cost_curve is required when cost_weight is positive"):
        calculate_vendor_scorecard(quality_weight=0.4, delivery_weight=0.4, cost_weight=0.2)


def test_evaluate_escalation_benchmark_monitor() -> None:
    """evaluate_escalation(None) drives the benchmark scorecard (~84.27) to MONITOR.

    Independently checked: composite 84.27 <= monitor_score_maximum 89.0 fires MONITOR, and
    > scar_score_maximum 74.0 so no higher tier fires; recurrence not supplied.
    """
    res = evaluate_escalation(None)
    assert res["tier"] == "MONITOR"
    assert res["basis"] == res["standards_basis"]


def test_evaluate_escalation_recurrence_override() -> None:
    """A supplied recurrence_count activates recurrence triggers (escalates past MONITOR)."""
    res = evaluate_escalation(None, recurrence_count=2)
    assert res["tier"] == "SCAR_REQUIRED"


def test_evaluate_escalation_empty_dict_is_indeterminate_not_raised() -> None:
    """scorecard={} returns a fully-shaped INDETERMINATE payload; it never raises.

    The key set must equal a real EscalationResult.to_dict()'s key set so downstream consumers
    (and render_sqe_canvas) never see a truncated envelope.
    """
    real = evaluate_escalation(None)
    res = evaluate_escalation(scorecard={})
    assert res["tier"] == "INDETERMINATE"
    assert res["scorecard_verdict"] == "INDETERMINATE"
    assert set(res.keys()) == set(real.keys())
    assert "malformed or incomplete" in res["reason"]
    assert res["basis"] == res["standards_basis"]


def test_evaluate_escalation_indeterminate_scorecard_propagates() -> None:
    """A well-formed but INDETERMINATE scorecard flows through the core engine's own short-circuit.

    Distinct from the malformed-dict path: reason text comes from the engine ("scorecard is
    INDETERMINATE..."), not from the tool's "malformed or incomplete" fallback.
    """
    indeterminate_scorecard = calculate_vendor_scorecard(lots=[], deliveries=[])
    res = evaluate_escalation(scorecard=indeterminate_scorecard)
    assert res["tier"] == "INDETERMINATE"
    assert res["scorecard_verdict"] == "INDETERMINATE"
    assert "scorecard is INDETERMINATE" in res["reason"]
    assert "malformed or incomplete" not in res["reason"]


def test_generate_scar_benchmark() -> None:
    """generate_scar(None) issues the benchmark SCAR, awaiting supplier response, no root cause."""
    res = generate_scar(None)
    assert res["status"] == "AWAITING_SUPPLIER_RESPONSE"
    assert res["root_cause"] is None
    assert res["basis"] == res["standards_basis"]


def test_generate_scar_temporal_contradiction_indeterminate() -> None:
    """date_issued=None with a verification statement is the Rule-0 INDETERMINATE case."""
    request = dict(_BENCHMARK_SCAR_REQUEST)
    request["date_issued"] = None
    res = generate_scar(
        request=request,
        verification_of_effectiveness="Retested 100 units, zero defects.",
    )
    assert res["status"] == "INDETERMINATE"


def test_generate_scar_linkage_flag_override() -> None:
    """evaluate_vendor_scorecard_linkage not None builds a SCARConfig (the is-not-None arm)."""
    res = generate_scar(None, evaluate_vendor_scorecard_linkage=False)
    assert res["status"] == "AWAITING_SUPPLIER_RESPONSE"


def test_generate_scar_empty_request_raises_valueerror() -> None:
    """generate_scar(request={}) is the pydantic path (missing required fields) -> clean ValueError."""
    with pytest.raises(ValueError):
        generate_scar(request={})


def test_render_sqe_canvas_benchmark() -> None:
    """render_sqe_canvas(None) loads the 6-supplier benchmark canvas with a full summary."""
    res = render_sqe_canvas(None)
    assert res["rows_count"] == 6
    assert res["summary"]["rows_count"] == 6
    assert res["summary"]["rated_count"] == 5
    assert res["summary"]["indeterminate_count"] == 1
    assert res["summary"]["band_counts"] == {"A": 1, "B": 1, "C": 3}
    assert res["summary"]["tier_counts"] == {
        "NONE": 1,
        "MONITOR": 1,
        "SCAR_REQUIRED": 1,
        "CONTAINMENT_REQUIRED": 1,
        "EXECUTIVE_REVIEW": 1,
        "INDETERMINATE": 1,
    }
    assert "<!DOCTYPE html>" in res["html"]
    assert res["basis"]


def test_render_sqe_canvas_empty_list() -> None:
    """render_sqe_canvas(rows=[]) renders an explicitly empty canvas, no exception."""
    res = render_sqe_canvas(rows=[])
    assert res["rows_count"] == 0
    assert "No supplier scorecard results captured" in res["html"]


def test_render_sqe_canvas_embedded_and_light_theme() -> None:
    """standalone=False and theme='light' exercise the non-DOCTYPE / theme-normalise branches."""
    embedded = render_sqe_canvas(None, standalone=False)
    assert "<!DOCTYPE html>" not in embedded["html"]
    light = render_sqe_canvas(None, theme="Light")
    assert "<!DOCTYPE html>" in light["html"]


def test_render_sqe_canvas_reconstructs_from_tool_envelopes() -> None:
    """Q1 envelope: the actual outputs of calculate_vendor_scorecard/evaluate_escalation feed in.

    This is the "consumed not authored" contract: the two round-trip helpers rebuild real dataclass
    instances from the tools' own .to_dict() envelopes.
    """
    scorecard = calculate_vendor_scorecard(None, None, None)
    escalation = evaluate_escalation(scorecard=scorecard)
    res = render_sqe_canvas(
        rows=[
            {
                "supplier_id": "SUP-1001",
                "supplier_name": "Acme Brackets",
                "scorecard": scorecard,
                "escalation": escalation,
            }
        ]
    )
    assert res["rows_count"] == 1
    assert res["summary"]["rated_count"] == 1
    assert res["summary"]["band_counts"]["B"] == 1


def test_render_sqe_canvas_indeterminate_envelope_row() -> None:
    """An INDETERMINATE scorecard envelope reconstructs and is counted as indeterminate/UNRATED."""
    scorecard = calculate_vendor_scorecard(lots=[], deliveries=[])
    escalation = evaluate_escalation(scorecard={})
    res = render_sqe_canvas(
        rows=[{"supplier_id": "SUP-9", "scorecard": scorecard, "escalation": escalation}]
    )
    assert res["summary"]["indeterminate_count"] == 1
    assert res["summary"]["rated_count"] == 0


def test_render_sqe_canvas_malformed_row_raises_indexed_valueerror() -> None:
    """A row missing 'scorecard' raises a ValueError naming the row index, never a bare KeyError."""
    with pytest.raises(ValueError, match=r"rows\[0\]:"):
        render_sqe_canvas(rows=[{"supplier_id": "X"}])


# ===========================================================================
# 4. Type-guard negative controls
# ===========================================================================


@pytest.mark.parametrize(
    ("tool_fn", "invalid_kwargs", "expected_err", "match_str"),
    [
        # calculate_supplier_ppm
        (calculate_supplier_ppm, {"period": "x"}, TypeError, "period must be a dict"),
        (calculate_supplier_ppm, {"lots": "x"}, TypeError, "lots must be a list"),
        (calculate_supplier_ppm, {"lots": ["x"]}, TypeError, r"lots\[0\] must be a dict"),
        (calculate_supplier_ppm, {"sample_adequacy_minimum": True}, TypeError, "must be an integer"),
        (calculate_supplier_ppm, {"sample_adequacy_minimum": "5"}, TypeError, "must be an integer"),
        # calculate_otif
        (calculate_otif, {"period": 1}, TypeError, "period must be a dict"),
        (calculate_otif, {"deliveries": "x"}, TypeError, "deliveries must be a list"),
        (calculate_otif, {"deliveries": [1]}, TypeError, r"deliveries\[0\] must be a dict"),
        (calculate_otif, {"early_tolerance_days": True}, TypeError, "must be an integer"),
        (calculate_otif, {"late_tolerance_days": 1.5}, TypeError, "must be an integer"),
        (calculate_otif, {"early_counts_as_on_time": 1}, TypeError, "must be a bool"),
        (calculate_otif, {"in_full_tolerance_pct": True}, TypeError, "must be a number"),
        (calculate_otif, {"over_delivery_counts_as_in_full": "y"}, TypeError, "must be a bool"),
        # calculate_vendor_scorecard
        (calculate_vendor_scorecard, {"copq_items": "x"}, TypeError, "copq_items must be a list"),
        (calculate_vendor_scorecard, {"revenue_base": True}, TypeError, "must be a number"),
        (calculate_vendor_scorecard, {"quality_weight": True}, TypeError, "must be a number"),
        (calculate_vendor_scorecard, {"delivery_weight": "x"}, TypeError, "must be a number"),
        (calculate_vendor_scorecard, {"cost_weight": True}, TypeError, "must be a number"),
        (calculate_vendor_scorecard, {"a_band_minimum": True}, TypeError, "must be a number"),
        (calculate_vendor_scorecard, {"b_band_minimum": "x"}, TypeError, "must be a number"),
        (calculate_vendor_scorecard, {"ppm_config": "x"}, TypeError, "ppm_config must be a dict"),
        (calculate_vendor_scorecard, {"otif_config": 1}, TypeError, "otif_config must be a dict"),
        (calculate_vendor_scorecard, {"quality_curve": [1.0]}, ValueError, "best_value, worst_value"),
        (calculate_vendor_scorecard, {"quality_curve": {"best_value": 1.0}}, ValueError, "must supply both"),
        (calculate_vendor_scorecard, {"quality_curve": "x"}, TypeError, "quality_curve must be"),
        # evaluate_escalation
        (evaluate_escalation, {"scorecard": "x"}, TypeError, "scorecard must be a dict"),
        (evaluate_escalation, {"recurrence_count": True}, TypeError, "must be an integer"),
        (evaluate_escalation, {"monitor_score_maximum": True}, TypeError, "must be a number"),
        (evaluate_escalation, {"scar_recurrence_minimum": 1.5}, TypeError, "must be an integer"),
        # generate_scar
        (generate_scar, {"request": "x"}, TypeError, "request must be a dict"),
        (generate_scar, {"linked_ncr_evidence": 1}, TypeError, "must be a dict, a list, or None"),
        (generate_scar, {"supplier_root_cause_evidence": 1}, TypeError, "must be a dict, a list"),
        (generate_scar, {"cost_impact_evidence": 1}, TypeError, "must be a dict, a list"),
        (generate_scar, {"verification_of_effectiveness": 1}, TypeError, "must be a string"),
        (generate_scar, {"verification_of_effectiveness": True}, TypeError, "must be a string"),
        (generate_scar, {"evaluate_vendor_scorecard_linkage": 1}, TypeError, "must be a bool"),
        # render_sqe_canvas
        (render_sqe_canvas, {"standalone": 1}, TypeError, "standalone must be a boolean"),
        (render_sqe_canvas, {"title": 123}, TypeError, "title must be a string"),
        (render_sqe_canvas, {"title": True}, TypeError, "title must be a string"),
        (render_sqe_canvas, {"title": "   "}, ValueError, "title must not be empty"),
        (render_sqe_canvas, {"theme": 123}, TypeError, "theme must be a string"),
        (render_sqe_canvas, {"theme": True}, TypeError, "theme must be a string"),
        (render_sqe_canvas, {"theme": "neon"}, ValueError, "theme must be 'dark' or 'light'"),
        (render_sqe_canvas, {"rows": "x"}, TypeError, "rows must be a list"),
        (render_sqe_canvas, {"rows": ["x"]}, TypeError, r"rows\[0\] must be a dict"),
    ],
)
def test_type_guard_negative_controls(
    tool_fn: Any,
    invalid_kwargs: dict[str, Any],
    expected_err: type[Exception],
    match_str: str,
) -> None:
    """Every type guard raises before the engine call, with an f-string naming the bad value."""
    with pytest.raises(expected_err, match=match_str):
        tool_fn(**invalid_kwargs)


# ===========================================================================
# 5. ValidationError -> clean_pydantic_message
# ===========================================================================

_INVERTED_WINDOW = {
    "supplier_id": "SUP-X",
    "period_start": "2026-02-01",
    "period_end": "2026-01-01",
}


@pytest.mark.parametrize(
    ("tool_fn", "kwargs"),
    [
        (calculate_supplier_ppm, {"period": _INVERTED_WINDOW}),
        (calculate_otif, {"period": _INVERTED_WINDOW}),
        (calculate_vendor_scorecard, {"period": _INVERTED_WINDOW}),
        (generate_scar, {"request": {"supplier_id": "S", "issue_description": "", "scar_id": "X"}}),
    ],
)
def test_pydantic_validation_error_surfaces_clean(tool_fn: Any, kwargs: dict[str, Any]) -> None:
    """A pydantic ValidationError surfaces as a bare, cleaned ValueError (no raw URL/traceback)."""
    with pytest.raises(ValueError) as excinfo:
        tool_fn(**kwargs)
    message = str(excinfo.value)
    assert "http" not in message
    assert "ValidationError" not in message
    assert "\n" not in message


@pytest.mark.parametrize(
    ("module_target", "tool_fn", "kwargs"),
    [
        ("_calculate_supplier_ppm_core", calculate_supplier_ppm, {}),
        ("_calculate_otif_core", calculate_otif, {}),
        ("_calculate_vendor_scorecard_core", calculate_vendor_scorecard, {}),
        ("_generate_scar_core", generate_scar, {}),
    ],
)
def test_core_validation_error_is_wrapped(
    monkeypatch: pytest.MonkeyPatch,
    module_target: str,
    tool_fn: Any,
    kwargs: dict[str, Any],
) -> None:
    """Forcing the private core to raise pydantic.ValidationError closes the final except branch."""

    class _Dummy(pydantic.BaseModel):
        val: int

    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        _Dummy(val="not-an-int")  # type: ignore[arg-type]

    monkeypatch.setattr(f"quality_mcp.tools.sqe.{module_target}", _raise)
    with pytest.raises(ValueError):
        tool_fn(**kwargs)


def test_clean_validation_error_zero_error_fallback() -> None:
    """A zero-error ValidationError falls back to the literal 'invalid value' message."""
    zero = pydantic.ValidationError.from_exception_data("X", [])
    assert str(_clean_validation_error(zero)) == "invalid value"


# ===========================================================================
# 6. FastMCP in-process client three-way parity
# ===========================================================================


@pytest.mark.parametrize(
    ("tool_name", "direct_fn"),
    [
        ("calculate_supplier_ppm", calculate_supplier_ppm),
        ("calculate_otif", calculate_otif),
        ("calculate_vendor_scorecard", calculate_vendor_scorecard),
        ("evaluate_escalation", evaluate_escalation),
        ("generate_scar", generate_scar),
        ("render_sqe_canvas", render_sqe_canvas),
    ],
)
def test_three_way_parity(tool_name: str, direct_fn: Any) -> None:
    """structuredContent == serialized text-content JSON == direct .to_dict() call, per tool.

    This is the whole point of the MCP layer: the wire form and the Python call must agree exactly.
    """
    direct = direct_fn()

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            result = await client.call_tool(tool_name, {})
            assert not result.isError
            assert result.structuredContent is not None
            assert len(result.content) == 1
            assert isinstance(result.content[0], TextContent)
            text_json = json.loads(result.content[0].text)
            assert result.structuredContent == text_json
            assert result.structuredContent == direct

    asyncio.run(_run())


def test_three_way_parity_tool_discovery() -> None:
    """All six SQE tools are discoverable over the client session with descriptions and schemas."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            for name in _SQE_TOOL_NAMES:
                assert name in names

    asyncio.run(_run())


def test_client_error_response_for_bad_input() -> None:
    """Invalid input over the client surfaces as an isError response (not a crash)."""

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            res = await client.call_tool("render_sqe_canvas", {"theme": "neon"})
            assert res.isError

    asyncio.run(_run())


# ===========================================================================
# 7. Invariant leak detector — applied to descriptions AND payloads
# ===========================================================================

_NO_STANDARD_ATTRIBUTION = re.compile(r"\bper\s+(ISO|IATF|AIAG)\b", re.IGNORECASE)
_ROOT_CAUSE_OFFER_PHRASES = (
    "produces a root cause",
    "provides the root cause",
    "invents a root cause",
    "assigns a root cause",
    "determines the root cause",
    "determine the root cause",
)
_COMMERCIAL_ACTION_PHRASES = (
    "recommends a hold",
    "recommend a hold",
    "recommends de-sourcing",
    "recommend de-sourcing",
    "recommends removal",
    "recommend removal",
    "recommends a charge-back",
    "recommend a charge-back",
    "authorizes a hold",
    "authorizes de-sourcing",
)


def _assert_no_invariant_leak(text: str) -> None:
    assert not _NO_STANDARD_ATTRIBUTION.search(text), f"standard-attribution leak: {text!r}"
    lowered = text.lower()
    for phrase in _ROOT_CAUSE_OFFER_PHRASES:
        assert phrase not in lowered, f"root-cause-authorship leak: {text!r}"
    for phrase in _COMMERCIAL_ACTION_PHRASES:
        assert phrase not in lowered, f"commercial-authority leak: {text!r}"


def _walk_strings(obj: Any) -> Any:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_strings(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item)


def _field_descriptions(tool_fn: Any) -> list[str]:
    hints = get_type_hints(tool_fn, include_extras=True)
    descriptions: list[str] = []
    for annotated_type in hints.values():
        if get_origin(annotated_type) is Annotated:
            for arg in get_args(annotated_type):
                if isinstance(arg, FieldInfo) and arg.description:
                    descriptions.append(arg.description)
    return descriptions


@pytest.mark.parametrize("tool_fn", _SQE_TOOLS)
def test_no_invariant_leak_in_descriptions(tool_fn: Any) -> None:
    """No tool's docstring or Field description attributes a standard, offers a root cause, or
    recommends a commercial action."""
    _assert_no_invariant_leak(tool_fn.__doc__ or "")
    for description in _field_descriptions(tool_fn):
        _assert_no_invariant_leak(description)


@pytest.mark.parametrize("tool_fn", _SQE_TOOLS)
def test_no_invariant_leak_in_benchmark_payload(tool_fn: Any) -> None:
    """No string anywhere in a tool's benchmark (None-input) payload leaks an invariant."""
    payload = tool_fn()
    for text in _walk_strings(payload):
        _assert_no_invariant_leak(text)


def test_leak_detector_reads_the_mcp_exposed_description() -> None:
    """The invariant text an MCP host shows an agent (list_tools description) must match __doc__.

    The _with_notes decorator populates __doc__; the MCP server exposes that same string. This
    guards against the two diverging — the description-leak controls would be theatre otherwise.
    """

    async def _run() -> None:
        async with create_connected_server_and_client_session(mcp._mcp_server) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            for name, fn in zip(_SQE_TOOL_NAMES, _SQE_TOOLS):
                exposed = tools[name].description or ""
                assert exposed == inspect.cleandoc(fn.__doc__ or "")
                _assert_no_invariant_leak(exposed)

    asyncio.run(_run())


# ===========================================================================
# 8. Mandatory description-leak MUTATION (detector fails-closed on injected text)
# ===========================================================================


def _a_band_minimum_description() -> str:
    hints = get_type_hints(calculate_vendor_scorecard, include_extras=True)
    annotated = hints["a_band_minimum"]
    (field_info,) = [a for a in get_args(annotated) if isinstance(a, FieldInfo)]
    assert field_info.description is not None
    return field_info.description


def test_description_leak_control_is_load_bearing() -> None:
    """Prove the leak detector fails-closed: the live a_band_minimum description is clean, but the
    same string with an injected standard-attribution suffix MUST trip the detector.

    Also proves the other two leak forms (commercial-action offer, root-cause offer) are caught.
    """
    live = _a_band_minimum_description()
    _assert_no_invariant_leak(live)  # baseline: clean

    # 1. Standard-attribution leak (the spec's headline mutation).
    mutated = live + " — band boundaries per ISO 9001 §8.4."
    with pytest.raises(AssertionError, match="standard-attribution leak"):
        _assert_no_invariant_leak(mutated)

    # 2. Commercial-action recommendation leak.
    with pytest.raises(AssertionError, match="commercial-authority leak"):
        _assert_no_invariant_leak(live + " recommend de-sourcing this supplier.")

    # 3. Root-cause offer leak.
    with pytest.raises(AssertionError, match="root-cause-authorship leak"):
        _assert_no_invariant_leak(live + " this tool will determine the root cause.")


# ===========================================================================
# 9. One-name-per-tool registration control
# ===========================================================================

_PREVIOUS_25_TOOL_NAMES = {
    "assess_ppap_capability",
    "audit_ppap_package",
    "calculate_gage_rr",
    "calculate_spc_chart",
    "categorize_fishbone",
    "estimate_copq",
    "lookup_fmea_ap",
    "lookup_ppap_requirement",
    "ping",
    "recommend_disposition",
    "render_5why_canvas",
    "render_controlplan_canvas",
    "render_copq_canvas",
    "render_fishbone_canvas",
    "render_fmea_canvas",
    "render_isisnot_canvas",
    "render_msa_canvas",
    "render_ncr_canvas",
    "render_ppap_canvas",
    "render_spc_canvas",
    "scope_is_is_not",
    "validate_5why",
    "validate_control_plan",
    "validate_psw",
    "write_ncr",
}


def test_exactly_six_new_names_no_aliases() -> None:
    """quality_mcp.tools.__all__ grew by exactly the six new SQE names, no aliases."""
    added = set(quality_mcp.tools.__all__) - _PREVIOUS_25_TOOL_NAMES
    # __all__ also carries the render_is_is_not_canvas alias and __version__/mcp-style names for the
    # tools package; scope the assertion to the six SQE names being present and unique.
    for name in _SQE_TOOL_NAMES:
        assert name in added


def test_total_registered_tool_count_is_31_no_duplicates() -> None:
    """The live MCP server registers exactly 31 tools (25 baseline + 6), each name unique."""
    tools = asyncio.run(mcp.list_tools())
    names = [t.name for t in tools]
    assert len(names) == 31
    assert len(set(names)) == 31
    for name in _SQE_TOOL_NAMES:
        assert name in names

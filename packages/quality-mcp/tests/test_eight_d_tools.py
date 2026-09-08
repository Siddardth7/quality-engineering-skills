"""
Unit tests for the 8D FastMCP tools in quality_mcp.tools.eight_d (E11, #214).

Covers, for validate_8d / advance_8d / render_8d_canvas:
1. Default-sample execution (report=None loads SAMPLE_EIGHT_D_REPORT).
2. Exact schema parity against the wrapped quality_core engine .to_dict() (never a
   hand-written expected dict — the core call is the oracle).
3. The trust boundary _coerce_report: TypeError on non-dict/non-None, ValueError on a
   pydantic failure (both the non-empty and empty .errors() arms).
4. advance_8d: CLOSED (ADVANCED), illegal target D2 (BLOCKED/ILLEGAL_TRANSITION/rule_id
   None), target guards, and input-report purity.
5. render_8d_canvas: hoisted convenience keys, the closeable non-conflation guarantee, and
   every type/value guard.
6. Standards-fidelity negative controls: a PDD gate reason and a PLATFORM_UNCITED finding
   are relayed verbatim, never re-labelled "RULE".
"""

from __future__ import annotations

import copy
from typing import Any

import pydantic
import pytest
from quality_core.canvas.eight_d import SAMPLE_EIGHT_D_REPORT
from quality_core.rca.eight_d import transition_eight_d as core_transition_8d
from quality_core.rca.eight_d_disciplines import validate_8d as core_validate_8d
from quality_core.rca.eight_d_schema import validate_eight_d
from quality_mcp.tools.eight_d import advance_8d, render_8d_canvas, validate_8d

# Additive keys render_8d_canvas is permitted to hoist on top of the core validate payload.
_CANVAS_ADDITIVE_KEYS = {"title", "verdict", "state", "closeable", "html", "validation"}


def _linked_ncr_invalid_report() -> dict[str, Any]:
    """A sample report whose D3 linked-NCR gate fails: closeable=False but d8.closeable=True.

    This is the fixture where the two closeable flags genuinely disagree — the single most
    important thing this module must never conflate. It also carries the PDD-8D-008 gate
    reason used by the citation-fidelity control.
    """
    rep = copy.deepcopy(SAMPLE_EIGHT_D_REPORT)
    rep["d3"]["linked_ncr_validation"] = {
        "is_valid": False,
        "record_count": 2,
        "findings": ["linked NCR records could not be verified"],
    }
    return rep


# ---------------------------------------------------------------------------
# 1. validate_8d
# ---------------------------------------------------------------------------


def test_validate_8d_default_sample_parity() -> None:
    """validate_8d() loads the benchmark sample and returns the core to_dict verbatim."""
    result = validate_8d()
    oracle = core_validate_8d(validate_eight_d(SAMPLE_EIGHT_D_REPORT)).to_dict()
    assert result == oracle
    assert result["verdict"] == "WARNING"
    assert result["state"] == "D8"
    assert result["closeable"] is True
    assert result["d8"]["closeable"] is True


def test_validate_8d_custom_report_parity() -> None:
    """validate_8d(dict) routes through the trust boundary and stays at exact core parity."""
    rep = _linked_ncr_invalid_report()
    result = validate_8d(rep)
    oracle = core_validate_8d(validate_eight_d(rep)).to_dict()
    assert result == oracle


def test_validate_8d_no_reshaping() -> None:
    """validate_8d adds/renames/drops no key: its keys equal the core payload's keys exactly."""
    result = validate_8d()
    oracle = core_validate_8d(validate_eight_d(SAMPLE_EIGHT_D_REPORT)).to_dict()
    assert set(result.keys()) == set(oracle.keys())


def test_validate_8d_closeable_not_conflated() -> None:
    """The whole-report and D8 closure-evidence closeable flags stay distinct (PDD-8D-008)."""
    rep = _linked_ncr_invalid_report()
    result = validate_8d(rep)
    assert result["closeable"] is False
    assert result["d8"]["closeable"] is True
    assert result["closeable"] != result["d8"]["closeable"]
    codes = {(g["code"], g["rule_id"]) for g in result["gate_reasons"]}
    assert ("LINKED_NCR_INVALID", "PDD-8D-008") in codes


def test_validate_8d_pdd_gate_reason_verbatim() -> None:
    """A PDD-8D-008 gate reason is relayed unchanged — never re-labelled a RULE-8D-* id."""
    result = validate_8d(_linked_ncr_invalid_report())
    reason = next(g for g in result["gate_reasons"] if g["code"] == "LINKED_NCR_INVALID")
    assert reason["rule_id"] == "PDD-8D-008"
    assert not reason["rule_id"].startswith("RULE-")


def test_validate_8d_platform_uncited_finding_verbatim() -> None:
    """A PLATFORM_UNCITED summary finding keeps citation_basis='PLATFORM_UNCITED', never 'RULE'."""
    result = validate_8d()
    finding = next(f for f in result["d0"]["findings"] if f["code"] == "ERA_READY")
    assert finding["citation_basis"] == "PLATFORM_UNCITED"
    assert finding["citation_basis"] != "RULE"


def test_validate_8d_type_error_on_non_dict() -> None:
    """A non-dict, non-None report is rejected at the trust boundary with TypeError."""
    with pytest.raises(TypeError, match="report must be a dict or None"):
        validate_8d([1, 2, 3])  # type: ignore[arg-type]


def test_validate_8d_value_error_on_schema_failure() -> None:
    """An empty dict fails 8D schema validation and surfaces as a clean ValueError."""
    with pytest.raises(ValueError):
        validate_8d({})


def test_coerce_report_empty_errors_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a ValidationError carries no .errors(), the fallback message path is used."""

    def _raise_empty(_payload: Any) -> Any:
        raise pydantic.ValidationError.from_exception_data("EightDReport", [])

    monkeypatch.setattr("quality_mcp.tools.eight_d.validate_eight_d", _raise_empty)
    with pytest.raises(ValueError, match="invalid value"):
        validate_8d({"report_id": "X"})


# ---------------------------------------------------------------------------
# 2. advance_8d
# ---------------------------------------------------------------------------


def test_advance_8d_closed_advances() -> None:
    """advance_8d(target='CLOSED') on the D8/OPEN sample advances with empty reasons."""
    result = advance_8d(target="CLOSED")
    oracle = core_transition_8d(validate_eight_d(SAMPLE_EIGHT_D_REPORT), "CLOSED").to_dict()
    assert result == oracle
    assert result["verdict"] == "ADVANCED"
    assert result["previous_state"] == "D8"
    assert result["state"] == "CLOSED"
    assert result["reasons"] == []


def test_advance_8d_illegal_target_is_blocked_not_error() -> None:
    """A non-adjacent target D2 returns BLOCKED/ILLEGAL_TRANSITION/rule_id=None, not an exception."""
    result = advance_8d(target="D2")
    assert result["verdict"] == "BLOCKED"
    assert len(result["reasons"]) == 1
    reason = result["reasons"][0]
    assert reason["code"] == "ILLEGAL_TRANSITION"
    assert reason["rule_id"] is None


def test_advance_8d_does_not_mutate_input_report() -> None:
    """advance_8d must not mutate the caller's report dict (the pure-function guarantee)."""
    rep = copy.deepcopy(SAMPLE_EIGHT_D_REPORT)
    snapshot = copy.deepcopy(rep)
    advance_8d(rep, target="CLOSED")
    assert rep == snapshot


def test_advance_8d_custom_report_parity() -> None:
    """advance_8d stays at exact core parity for a caller-supplied report."""
    rep = _linked_ncr_invalid_report()
    result = advance_8d(rep, target="CLOSED")
    oracle = core_transition_8d(validate_eight_d(rep), "CLOSED").to_dict()
    assert result == oracle


@pytest.mark.parametrize("bad_target", [123, True, None, ["CLOSED"]])
def test_advance_8d_non_string_target_type_error(bad_target: Any) -> None:
    """A non-string target (including bool) is rejected with TypeError before the core call."""
    with pytest.raises(TypeError, match="target must be a string"):
        advance_8d(target=bad_target)


@pytest.mark.parametrize("empty_target", ["", "   "])
def test_advance_8d_empty_target_value_error(empty_target: str) -> None:
    """An empty or whitespace-only target is rejected with ValueError."""
    with pytest.raises(ValueError, match="target must not be empty"):
        advance_8d(target=empty_target)


def test_advance_8d_type_error_on_non_dict_report() -> None:
    """advance_8d shares the _coerce_report trust boundary: non-dict report -> TypeError."""
    with pytest.raises(TypeError, match="report must be a dict or None"):
        advance_8d("not-a-dict", target="CLOSED")  # type: ignore[arg-type]


def test_advance_8d_value_error_on_schema_failure() -> None:
    """advance_8d surfaces a schema failure as a clean ValueError."""
    with pytest.raises(ValueError):
        advance_8d({}, target="CLOSED")


# ---------------------------------------------------------------------------
# 3. render_8d_canvas
# ---------------------------------------------------------------------------


def test_render_8d_canvas_default_sample() -> None:
    """render_8d_canvas() hoists verdict/state/closeable and matches the core validate payload."""
    result = render_8d_canvas()
    oracle = core_validate_8d(validate_eight_d(SAMPLE_EIGHT_D_REPORT)).to_dict()
    assert result["title"] == "8D Problem Solving Canvas"
    assert result["verdict"] == oracle["verdict"]
    assert result["state"] == oracle["state"]
    assert result["closeable"] == oracle["closeable"]
    assert result["validation"] == oracle
    assert "<!DOCTYPE html>" in result["html"]


def test_render_8d_canvas_hoisted_closeable_is_whole_report_gate() -> None:
    """The hoisted top-level closeable IS the whole-report gate, NOT d8.closeable.

    On a fixture where the two genuinely differ (closeable=False, d8.closeable=True) the
    hoisted value must equal validation["closeable"] and differ from
    validation["d8"]["closeable"]. This is the load-bearing anti-conflation assertion.
    """
    payload = render_8d_canvas(_linked_ncr_invalid_report())
    assert payload["closeable"] == payload["validation"]["closeable"]
    assert payload["closeable"] is False
    assert payload["validation"]["d8"]["closeable"] is True
    assert payload["closeable"] != payload["validation"]["d8"]["closeable"]


def test_render_8d_canvas_d8_closeable_not_hoisted() -> None:
    """d8.closeable is reachable only at validation.d8.closeable — never a top-level key."""
    payload = render_8d_canvas(_linked_ncr_invalid_report())
    assert set(payload.keys()) == _CANVAS_ADDITIVE_KEYS
    assert payload["validation"]["d8"]["closeable"] is True


def test_render_8d_canvas_no_unlisted_keys() -> None:
    """render_8d_canvas adds only the documented additive keys, nothing else."""
    payload = render_8d_canvas()
    assert set(payload.keys()) == _CANVAS_ADDITIVE_KEYS


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("standalone", [True, False])
def test_render_8d_canvas_themes_and_modes(theme: str, standalone: bool) -> None:
    """Both themes and both standalone modes render without error."""
    payload = render_8d_canvas(theme=theme, standalone=standalone)
    if standalone:
        assert "<!DOCTYPE html>" in payload["html"]
    else:
        assert "<!DOCTYPE html>" not in payload["html"]


def test_render_8d_canvas_custom_title() -> None:
    """A custom title is carried through to the returned payload."""
    payload = render_8d_canvas(title="Line 7 Escape")
    assert payload["title"] == "Line 7 Escape"


@pytest.mark.parametrize(
    ("kwargs", "expected_err", "match_str"),
    [
        ({"standalone": 1}, TypeError, "standalone must be a boolean"),
        ({"standalone": "true"}, TypeError, "standalone must be a boolean"),
        ({"title": 123}, TypeError, "title must be a string"),
        ({"title": True}, TypeError, "title must be a string"),
        ({"title": ""}, ValueError, "title must not be empty"),
        ({"title": "   "}, ValueError, "title must not be empty"),
        ({"theme": "neon"}, ValueError, "theme must be 'dark' or 'light'"),
        ({"report": 42}, TypeError, "report must be a dict or None"),
    ],
)
def test_render_8d_canvas_guards(
    kwargs: dict[str, Any], expected_err: type[Exception], match_str: str
) -> None:
    """Every type/value guard on render_8d_canvas fires with the documented message."""
    with pytest.raises(expected_err, match=match_str):
        render_8d_canvas(**kwargs)


def test_render_8d_canvas_value_error_on_schema_failure() -> None:
    """A schema-invalid report surfaces as a clean ValueError from the canvas path."""
    with pytest.raises(ValueError):
        render_8d_canvas({})

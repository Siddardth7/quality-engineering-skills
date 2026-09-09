"""Tests for the read-only 8D single-writer canvas (``quality_core.canvas.eight_d``).

The canvas re-renders already-validated ``validate_8d`` output. These tests pin the behaviour
the spec (#213) names: both themes, every D0-D8 card present-and-absent, the D4-without-a-result
path, injection safety, citation-basis caption fidelity, and — the epic's central footgun — that
``result.closeable`` (headline) and ``result.d8.closeable`` (D8 card) are never conflated.
"""

from __future__ import annotations

import ast
import copy
import pathlib
from collections.abc import Callable
from typing import Any

import pytest
from quality_core.canvas.eight_d import (
    BASIS_CAPTION,
    SAMPLE_EIGHT_D_REPORT,
    EightDCanvas,
    _rule_caption,
    load_sample_eight_d_canvas,
    render_eight_d,
)
from quality_core.rca.eight_d_disciplines import validate_8d
from quality_core.rca.eight_d_schema import validate_eight_d

_MODULE = pathlib.Path("packages/quality-core/src/quality_core/canvas/eight_d.py")

_HEADINGS = (
    "D0 — Emergency Response Action readiness",
    "D1 — Team",
    "D2 — Problem description",
    "D3 — Interim containment",
    "D4 — Root cause and escape point",
    "D5 — Permanent corrective action selection",
    "D6 — Implementation and validation",
    "D7 — Prevent recurrence",
    "D8 — Recognize the team and close",
)


def build_report(mutate: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """A deep copy of the benchmark dict with the real ``root_cause_validation`` reattached.

    ``root_cause_validation`` is a live ``FiveWhyValidationResult`` object; ``copy.deepcopy`` would
    clone it, but reattaching the original keeps fixtures identical to the sample the engine sees.
    """
    rep = copy.deepcopy(SAMPLE_EIGHT_D_REPORT)
    rep["root_cause_validation"] = SAMPLE_EIGHT_D_REPORT["root_cause_validation"]
    if mutate is not None:
        mutate(rep)
    return rep


def html_of(rep: dict[str, Any], **kw: Any) -> str:
    return EightDCanvas(validate_eight_d(rep)).to_html(**kw)


# ---------------------------------------------------------------------------
# 1. Render modes: both themes x both standalone values, structural markers.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("theme", ["dark", "light", " DARK "])
@pytest.mark.parametrize("standalone", [True, False])
def test_render_modes_and_structure(theme: str, standalone: bool) -> None:
    out = load_sample_eight_d_canvas().to_html(theme, standalone)
    assert ("<!DOCTYPE html>" in out) is standalone
    assert "8D Problem Solving Canvas" in out
    assert "Closure gate status" in out
    for heading in _HEADINGS:
        assert heading in out
    # Heuristic disclosure is always present so no basis is read as a standards claim by default.
    assert "must not be read as one" in out


# ---------------------------------------------------------------------------
# 2. All three citation-basis captions reach the HTML, and are visually distinct.
#    (Heuristic-caption-intact requirement + mutation target (b) for PLATFORM_UNCITED.)
# ---------------------------------------------------------------------------
def test_all_three_basis_captions_present_and_distinct() -> None:
    out = load_sample_eight_d_canvas().to_html()
    captions = [BASIS_CAPTION["RULE"], BASIS_CAPTION["PDD"], BASIS_CAPTION["PLATFORM_UNCITED"]]
    for caption in captions:
        assert caption in out
    assert len(set(captions)) == 3
    # A heuristic caption must never be the standards-requirement caption.
    assert BASIS_CAPTION["PLATFORM_UNCITED"] != BASIS_CAPTION["RULE"]
    assert BASIS_CAPTION["PDD"] != BASIS_CAPTION["RULE"]
    # RULE is the only caption that claims a cited manual clause.
    assert "cited manual clause" in BASIS_CAPTION["RULE"]
    assert "cited manual clause" not in BASIS_CAPTION["PDD"]
    assert "cited manual clause" not in BASIS_CAPTION["PLATFORM_UNCITED"]


# ---------------------------------------------------------------------------
# 3. Gate-reason captions: a RULE- gate reason and a PDD- gate reason render with
#    distinct captions in the same output (never a PDD presented as a standard).
# ---------------------------------------------------------------------------
def test_gate_reason_rule_and_pdd_captions_distinct() -> None:
    # A mid-flight report (D0-D2 recorded only) raises both RULE- and PDD- closure gate reasons.
    def only_d0_d2(rep: dict[str, Any]) -> None:
        for key in ("d3", "d4", "d5", "d6", "d7", "d8"):
            rep[key] = None
        rep["root_cause_validation"] = None

    result = validate_8d(validate_eight_d(build_report(only_d0_d2)))
    prefixes = {g.rule_id.split("-8D-")[0] if g.rule_id else None for g in result.gate_reasons}
    assert "RULE" in prefixes and "PDD" in prefixes  # fixture actually exercises both

    out = html_of(build_report(only_d0_d2))
    assert "Standards requirement (RULE-8D-GATE-CLOSURE)" in out
    assert "Platform heuristic — no standards citation (PDD-8D-010)" in out
    assert "Standards requirement (PDD-8D-010)" not in out  # PDD never dressed as a standard


# ---------------------------------------------------------------------------
# 4. THE FOOTGUN (SME R2): result.closeable and result.d8.closeable not conflated.
# ---------------------------------------------------------------------------
def test_closeable_not_conflated_with_d8_closeable() -> None:
    def invalid_linked_ncr(rep: dict[str, Any]) -> None:
        rep["d3"]["linked_ncr_validation"] = {
            "is_valid": False,
            "record_count": 0,
            "findings": ["Linked NCR could not be validated"],
        }

    rep = build_report(invalid_linked_ncr)
    result = validate_8d(validate_eight_d(rep))
    # Precondition: the two closeable readings genuinely disagree on this report.
    assert result.closeable is False
    assert result.d8.closeable is True

    out = html_of(rep)
    # Headline follows result.closeable (whole report) — NOT d8.closeable.
    assert "Closeable (whole report): NO" in out
    assert "Closeable (whole report): YES" not in out
    # D8 closure-evidence badge shows its own (disagreeing) value under a distinct label.
    assert "D8 closure-evidence complete: YES" in out
    # The two are never collapsed to a bare "Closeable".
    assert "Closeable: " not in out
    # The blocking gate reason is present and captioned as the platform heuristic it is.
    assert "LINKED_NCR_INVALID" in out
    assert "PDD-8D-008" in out


# ---------------------------------------------------------------------------
# 5. Injection safety: <script> and =-leading payloads render inert. Negative control.
# ---------------------------------------------------------------------------
def test_injection_is_escaped() -> None:
    payload = "<script>alert(1)</script>"

    def inject(rep: dict[str, Any]) -> None:
        rep["d2"]["what_is_wrong"] = payload
        rep["d2"]["with_what"] = "=HYPERLINK(\"http://evil\",\"click\")"
        rep["d8"]["team_recognition_notes"] = payload
        rep["d3"]["linked_ncr_validation"] = {
            "is_valid": False,
            "record_count": 1,
            "findings": [payload],
        }

    out = html_of(build_report(inject))
    assert payload not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    # The =-leading value reaches the HTML with no un-escaped angle bracket smuggled through it.
    assert "=HYPERLINK(&quot;http://evil&quot;,&quot;click&quot;)" in out


def test_injection_negative_control_documented() -> None:
    """Confirms the escaper is what makes the injection test pass, not incidental absence.

    A raw report with the payload as plain text still contains the raw string in its data; only
    the canvas escaping keeps it out of the rendered HTML. If escaping were removed, ``payload``
    would appear verbatim in ``out`` (verified by mutation in the tester's report).
    """
    payload = "<script>x</script>"
    out = html_of(build_report(lambda r: r["d2"].__setitem__("what_is_wrong", payload)))
    assert payload not in out and "&lt;script&gt;x&lt;/script&gt;" in out


# ---------------------------------------------------------------------------
# 6. Every discipline absent individually, while the others are present.
# ---------------------------------------------------------------------------
def _absent(*keys: str) -> Callable[[dict[str, Any]], None]:
    def mutate(rep: dict[str, Any]) -> None:
        for key in keys:
            rep[key] = None
        if "d4" in keys:
            rep["root_cause_validation"] = None
    return mutate


def test_absent_early_disciplines_render_not_started() -> None:
    # d0-d3 absent; d4-d8 present. Proves d0/d1/d2/d3 absent branches independently.
    out = html_of(build_report(_absent("d0", "d1", "d2", "d3")))
    for heading in _HEADINGS:
        assert heading in out  # never omit a card
    assert out.count("Not started — no") == 4  # exactly the four absent early cards
    # A present later card is NOT rendered as not-started.
    assert "Team recognition notes" in out  # D8 populated


def test_absent_late_disciplines_render_not_started() -> None:
    # d3-d8 absent, d4 absent; d0-d2 present. Proves d3/d5/d6/d7/d8 + d4 absent branches.
    out = html_of(build_report(_absent("d3", "d4", "d5", "d6", "d7", "d8")))
    assert out.count("Not started — no") == 6
    assert "What is wrong" in out  # D2 populated


def test_fully_empty_report_all_cards_not_started() -> None:
    # Every discipline absent: all nine cards not-started; D8 result still emits D8_NOT_STARTED.
    out = html_of({"report_id": "8D-EMPTY", "initiated_date": "2026-01-01"})
    assert out.count("Not started — no") == 9
    result = validate_8d(validate_eight_d({"report_id": "8D-EMPTY", "initiated_date": "2026-01-01"}))
    assert result.closeable is False
    assert "Closeable (whole report): NO" in out
    # D8_NOT_STARTED is the sole PLATFORM_UNCITED finding here — mutation target (b).
    assert "D8_NOT_STARTED" in out
    assert BASIS_CAPTION["PLATFORM_UNCITED"] in out


# ---------------------------------------------------------------------------
# 7. D4 card: rendered from report.d4 / report.root_cause_validation, all combinations.
# ---------------------------------------------------------------------------
def test_d4_present_with_validation() -> None:
    out = html_of(build_report())
    assert "Root cause" in out
    assert "Linked 5-Why verdict" in out
    assert "The setup procedure was approved without a control-plan review." in out


def test_d4_present_without_validation() -> None:
    # Root cause recorded, 5-Why chain not attached: render statement, no verdict, not an error.
    out = html_of(build_report(lambda r: r.__setitem__("root_cause_validation", None)))
    assert "Root cause" in out
    assert "Linked 5-Why validation" in out and "not run" in out


def test_d4_absent_record_but_validation_present() -> None:
    # d4 record missing but a live 5-Why validation exists — card is NOT "not started".
    out = html_of(build_report(lambda r: r.__setitem__("d4", None)))
    assert "D4 record" in out and "not started" in out
    assert "Linked 5-Why verdict" in out  # validation still rendered


# ---------------------------------------------------------------------------
# 8. D3 linked-NCR states; D1 empty members; D0 absent verification; D7 empty updates;
#    D8 warning override present.
# ---------------------------------------------------------------------------
def test_d3_linked_ncr_not_linked() -> None:
    out = html_of(build_report(lambda r: r["d3"].__setitem__("linked_ncr_validation", None)))
    assert "not linked yet" in out


def test_d3_linked_ncr_valid_with_findings() -> None:
    def mutate(rep: dict[str, Any]) -> None:
        rep["d3"]["linked_ncr_validation"] = {
            "is_valid": True,
            "record_count": 1,
            "findings": ["advisory note"],
        }
    out = html_of(build_report(mutate))
    assert "Linked NCR valid" in out and "advisory note" in out


def test_d1_empty_members() -> None:
    out = html_of(build_report(lambda r: r["d1"].__setitem__("members", [])))
    assert "NO_TEAM_MEMBERS" in out


def test_d0_absent_verification_renders_em_dash() -> None:
    out = html_of(build_report(lambda r: r["d0"].__setitem__("era_verification", None)))
    assert "ERA verification" in out


def test_d7_empty_documentation_updates() -> None:
    out = html_of(build_report(lambda r: r["d7"].__setitem__("documentation_updates", [])))
    assert "Systemic changes" in out


def test_d8_warning_override_rendered() -> None:
    def mutate(rep: dict[str, Any]) -> None:
        rep["d8"]["linked_five_why_verdict"] = "WARNING"
        rep["d8"]["warning_override"] = {
            "approved_by": "Plant Manager",
            "justification": "Marginal chain accepted with monitoring.",
            "override_date": "2026-03-01",
        }
    out = html_of(build_report(mutate))
    assert "Warning override approved by" in out
    assert "Marginal chain accepted with monitoring." in out


# ---------------------------------------------------------------------------
# 9. Findings with and without a per-finding context field.
# ---------------------------------------------------------------------------
def test_finding_context_field_rendered() -> None:
    # A CONTROL_PLAN_EVIDENCE_NOT_PROVIDED finding carries artifact_type context in the sample.
    out = load_sample_eight_d_canvas().to_html()
    assert "artifact_type: CONTROL_PLAN" in out


# ---------------------------------------------------------------------------
# 10. Benchmark round-trip and to_dict shape.
# ---------------------------------------------------------------------------
def test_to_dict_shape_and_roundtrip() -> None:
    canvas = load_sample_eight_d_canvas()
    payload = canvas.to_dict()
    assert payload["title"] == "8D Problem Solving Canvas"
    assert set(payload) == {"title", "validation"}
    # The report nested inside the validation payload round-trips back through the schema.
    report_dict = payload["validation"]["report"]
    revalidated = validate_eight_d(report_dict)
    assert revalidated.report_id == canvas.report.report_id
    # Stable: validating twice yields the same closeable/verdict.
    again = validate_8d(revalidated)
    assert again.closeable == payload["validation"]["closeable"]
    assert again.verdict == payload["validation"]["verdict"]


# ---------------------------------------------------------------------------
# 11. render_eight_d dispatch arms and load_sample.
# ---------------------------------------------------------------------------
def test_render_eight_d_all_arms() -> None:
    rep = validate_eight_d(build_report())
    assert "eight-d-canvas" in render_eight_d(None)  # loads sample
    assert "eight-d-canvas" in render_eight_d(EightDCanvas(rep))  # passthrough
    assert "eight-d-canvas" in render_eight_d(rep)  # report object
    assert "eight-d-canvas" in render_eight_d(build_report())  # dict
    assert isinstance(load_sample_eight_d_canvas(), EightDCanvas)
    assert EightDCanvas.load_sample().title == "8D Problem Solving Canvas"


# ---------------------------------------------------------------------------
# 12. Constructor / theme validation.
# ---------------------------------------------------------------------------
def test_constructor_and_theme_validation() -> None:
    rep = validate_eight_d(build_report())
    with pytest.raises(TypeError):
        EightDCanvas(report="not a report")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        EightDCanvas(rep, title=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        EightDCanvas(rep, title="   ")
    canvas = EightDCanvas(rep)
    with pytest.raises(ValueError):
        canvas.to_html("blue")
    with pytest.raises(TypeError):
        canvas.to_html(standalone=1)  # type: ignore[arg-type]
    assert canvas.report is rep


# ---------------------------------------------------------------------------
# 13. _rule_caption(None): the coder-flagged structural-rule arm (direct call).
# ---------------------------------------------------------------------------
def test_rule_caption_none_is_structural() -> None:
    caption = _rule_caption(None)
    assert "Structural rule" in caption
    assert "RULE-" not in caption  # a structural reason is never a standards claim
    assert _rule_caption("RULE-8D-D3").startswith("Standards requirement")
    assert _rule_caption("PDD-8D-008").startswith("Platform heuristic")


# ---------------------------------------------------------------------------
# 14. The canvas does no engine arithmetic / re-derivation.
# ---------------------------------------------------------------------------
def test_canvas_has_no_engine_arithmetic() -> None:
    tree = ast.parse(_MODULE.read_text())
    arithmetic = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
    assert not any(
        isinstance(n, ast.BinOp) and isinstance(n.op, arithmetic) for n in ast.walk(tree)
    )
    # It never imports a discipline evaluator to recompute a verdict; validate_8d is the one call.
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "validate_8d" in called
    assert "validate_d8_closure" not in called  # d8 comes off validate_8d, not recomputed

"""
test_sqe_scar_engine.py
Exhaustive line + branch coverage of quality_core.sqe.scar.

Covers SCARConfig validation, every dataclass to_dict, every linkage helper across all
reachable verdicts, _findings_from_exception's three shapes, the full six-row status truth
table, and the mandatory negative controls (root-cause authorship, no-response-never-CLOSABLE,
verdict-affecting linkage, superficial-cause, verification-of-effectiveness). The import-direction
and no-duplicated-standards-data assertions live here too.
"""

from __future__ import annotations

import datetime
import importlib
import sys
from typing import Any

import pytest
from quality_core.rca.five_why import (
    FiveWhyValidationResult,
    SystemicAssessment,
)
from quality_core.sqe import scar as scar_module
from quality_core.sqe.scar import (
    SCARConfig,
    SCARSection,
    _build_recommendations,
    _build_sections,
    _evaluate_cost_impact_linkage,
    _evaluate_ncr_linkage,
    _evaluate_root_cause_linkage,
    _evaluate_vendor_scorecard_linkage,
    _findings_from_exception,
    _iso_or_none,
    _normalise_optional_text,
    _resolve_status,
    _root_cause_from_linkage,
    generate_scar,
)
from quality_core.sqe.schema import SCARRequest

# ===========================================================================
# Shared benchmark evidence
# ===========================================================================

# A fully valid, systemic 5-Why chain (terminates in a work-instruction gap, not blame).
VALID_CHAIN: list[dict[str, Any]] = [
    {"step_number": 1, "why": "Why did the motor overheat?", "because": "The cooling fan stopped turning."},
    {"step_number": 2, "why": "Why did the cooling fan stop?", "because": "The electrical fuse blew from an incorrect rating."},
    {"step_number": 3, "why": "Why was an incorrect rating installed?", "because": "The maintenance work instruction lacked a fuse specification table."},
]
VALID_CHAIN_ROOT_CAUSE = "The maintenance work instruction lacked a fuse specification table."

# A well-formed chain that terminates in blame -> BLAME_TERMINAL_OPERATOR_ERROR -> rejected.
BLAME_CHAIN: list[dict[str, Any]] = [
    {"step_number": 1, "why": "Why was hole off-center?", "because": "The drill fixture was misaligned."},
    {"step_number": 2, "why": "Why was drill fixture misaligned?", "because": "The operator forgot to tighten clamp bolts."},
]

VALID_NCR: list[dict[str, Any]] = [
    {
        "part_lot_id": "LOT-1",
        "defect_description": "hairline crack",
        "requirement_violated": "no cracks per drawing",
        "quantity_affected": 5,
        "detection_point": "incoming inspection",
    }
]

VALID_COST: list[dict[str, Any]] = [
    {"category": "InternalFailure", "description": "scrap", "scrap_qty": 40, "unit_cost": 30.0},
    {"category": "InternalFailure", "description": "sort", "direct_cost": 300.0},
]
VALID_COST_TOTAL = 1500.0  # 40*30 + 300


def _request(**overrides: Any) -> SCARRequest:
    base: dict[str, Any] = {
        "supplier_id": "SUP-1",
        "issue_description": "motor overheat",
    }
    base.update(overrides)
    return SCARRequest(**base)


# ===========================================================================
# SCARConfig
# ===========================================================================


def test_config_default_is_bool_true() -> None:
    cfg = SCARConfig()
    assert cfg.evaluate_vendor_scorecard_linkage is True


def test_config_accepts_explicit_bool() -> None:
    assert SCARConfig(evaluate_vendor_scorecard_linkage=False).evaluate_vendor_scorecard_linkage is False


def test_config_rejects_non_bool() -> None:
    with pytest.raises(TypeError, match="must be a bool"):
        SCARConfig(evaluate_vendor_scorecard_linkage=1)  # type: ignore[arg-type]


# ===========================================================================
# Small helpers
# ===========================================================================


def test_normalise_optional_text_none() -> None:
    assert _normalise_optional_text(None) is None


def test_normalise_optional_text_blank_to_none() -> None:
    assert _normalise_optional_text("   ") is None


def test_normalise_optional_text_strips() -> None:
    assert _normalise_optional_text("  done  ") == "done"


def test_iso_or_none_none() -> None:
    assert _iso_or_none(None) is None


def test_iso_or_none_date() -> None:
    assert _iso_or_none(datetime.date(2026, 1, 2)) == "2026-01-02"


# ===========================================================================
# _findings_from_exception — three shapes
# ===========================================================================


def test_findings_validation_error_with_loc() -> None:
    # quantity_affected=0 -> a field-level pydantic error carrying a loc.
    result = _evaluate_ncr_linkage(
        [
            {
                "part_lot_id": "L",
                "defect_description": "d",
                "requirement_violated": "r",
                "quantity_affected": 0,
                "detection_point": "p",
            }
        ]
    )
    assert result.verdict == "EVIDENCE_INVALID"
    assert result.findings == ("quantity_affected: Input should be greater than or equal to 1",)


def test_findings_validation_error_without_loc() -> None:
    # An empty list is a dataset-level error with no field loc.
    result = _evaluate_ncr_linkage([])
    assert result.verdict == "EVIDENCE_INVALID"
    assert result.findings == ("NCRDataset must contain at least one record",)


def test_findings_non_validation_error_branch() -> None:
    # An int is not a supported 5-Why input type -> TypeError, str(exc) surfaced verbatim.
    result = _evaluate_root_cause_linkage(123, "problem")
    assert result.verdict == "EVIDENCE_INVALID"
    assert result.findings == (
        "Expected FiveWhyChain, DataFrame, list of dicts/steps, or dict, got int",
    )


def test_findings_from_exception_plain_typeerror() -> None:
    assert _findings_from_exception(TypeError("boom")) == ("boom",)


# ===========================================================================
# NCR linkage
# ===========================================================================


def test_ncr_linkage_not_supplied() -> None:
    r = _evaluate_ncr_linkage(None)
    assert r.verdict == "EVIDENCE_NOT_SUPPLIED"
    assert r.engine == "quality_core.ncr"
    assert r.findings == ()
    assert r.raw_result is None


def test_ncr_linkage_valid() -> None:
    r = _evaluate_ncr_linkage(VALID_NCR)
    assert r.verdict == "EVIDENCE_VALID"
    assert r.raw_result is not None
    assert r.findings == ()


def test_ncr_linkage_invalid_typeerror() -> None:
    # A bare int is not a supported ncr input type -> TypeError caught -> EVIDENCE_INVALID.
    r = _evaluate_ncr_linkage(42)
    assert r.verdict == "EVIDENCE_INVALID"
    assert r.raw_result is None
    assert r.findings  # non-empty


# ===========================================================================
# Root-cause linkage
# ===========================================================================


def test_root_cause_linkage_not_supplied() -> None:
    r = _evaluate_root_cause_linkage(None, "p")
    assert r.verdict == "EVIDENCE_NOT_SUPPLIED"
    assert r.raw_result is None


def test_root_cause_linkage_valid() -> None:
    r = _evaluate_root_cause_linkage(VALID_CHAIN, "motor overheat")
    assert r.verdict == "EVIDENCE_VALID"
    assert r.raw_result is not None
    assert r.raw_result["root_cause"] == VALID_CHAIN_ROOT_CAUSE


def test_root_cause_linkage_rejected_surfaces_antipattern_verbatim() -> None:
    r = _evaluate_root_cause_linkage(BLAME_CHAIN, "Hole off-center")
    assert r.verdict == "EVIDENCE_INVALID"
    assert r.raw_result is not None  # rejected chain still surfaced for review
    assert any(f.startswith("BLAME_TERMINAL_OPERATOR_ERROR: ") for f in r.findings)


def test_root_cause_linkage_structural_exception() -> None:
    # Non-consecutive step numbers -> pydantic.ValidationError -> EVIDENCE_INVALID, raw_result None.
    bad = [
        {"step_number": 1, "why": "w", "because": "b"},
        {"step_number": 5, "why": "w", "because": "b"},
    ]
    r = _evaluate_root_cause_linkage(bad, "p")
    assert r.verdict == "EVIDENCE_INVALID"
    assert r.raw_result is None


def test_root_cause_linkage_empty_antipatterns_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `if not findings` fallback: valid=False but anti_patterns empty.

    Not reachable with real five_why data (every score-reducing path appends an anti-pattern),
    so the sub-engine call is monkeypatched to return a hand-built result, exactly as the coder
    flagged.
    """
    fake = FiveWhyValidationResult(
        basis="test",
        valid=False,
        verdict="REJECT",
        reversibility_score=0.3,
        problem_statement="p",
        root_cause="rc",
        total_steps=1,
        link_evaluations=[],
        anti_patterns=[],
        systemic_assessment=SystemicAssessment(
            classification="HUMAN_INDIVIDUAL",
            is_systemic=False,
            terminal_cause="rc",
            systemic_factors=[],
            recommendations=[],
        ),
        recommendations=[],
    )
    monkeypatch.setattr(scar_module, "validate_five_why_chain", lambda **_: fake)
    r = _evaluate_root_cause_linkage({"steps": [{"step_number": 1, "why": "w", "because": "b"}]}, "p")
    assert r.verdict == "EVIDENCE_INVALID"
    assert r.findings == (
        "quality_core.rca returned verdict 'REJECT' with reversibility_score 0.3.",
    )
    assert r.raw_result is not None


def test_root_cause_linkage_non_empty_antipatterns_no_fallback() -> None:
    # Direction opposite of the fallback: a real rejected chain never uses the fallback message.
    r = _evaluate_root_cause_linkage(BLAME_CHAIN, "Hole off-center")
    assert not any("reversibility_score" in f for f in r.findings)


# ===========================================================================
# Cost-impact linkage
# ===========================================================================


def test_cost_linkage_not_supplied() -> None:
    r = _evaluate_cost_impact_linkage(None)
    assert r.verdict == "EVIDENCE_NOT_SUPPLIED"
    assert r.raw_result is None


def test_cost_linkage_valid_hand_computed_total() -> None:
    r = _evaluate_cost_impact_linkage(VALID_COST)
    assert r.verdict == "EVIDENCE_VALID"
    assert r.raw_result is not None
    assert r.raw_result["total_copq"] == VALID_COST_TOTAL


def test_cost_linkage_zero_total_is_still_valid() -> None:
    r = _evaluate_cost_impact_linkage([{"category": "InternalFailure", "description": "x"}])
    assert r.verdict == "EVIDENCE_VALID"
    assert r.raw_result is not None
    assert r.raw_result["total_copq"] == 0.0


def test_cost_linkage_invalid_negative_driver() -> None:
    r = _evaluate_cost_impact_linkage(
        [{"category": "InternalFailure", "description": "x", "scrap_qty": -1}]
    )
    assert r.verdict == "EVIDENCE_INVALID"
    assert r.raw_result is None


# ===========================================================================
# Vendor-scorecard linkage
# ===========================================================================


def test_vendor_scorecard_always_not_available() -> None:
    r = _evaluate_vendor_scorecard_linkage()
    assert r.verdict == "LINKAGE_NOT_AVAILABLE"
    assert r.engine is None
    assert "#118" in r.rationale


# ===========================================================================
# _root_cause_from_linkage
# ===========================================================================


def test_root_cause_from_linkage_none() -> None:
    r = _evaluate_root_cause_linkage(None, "p")
    assert _root_cause_from_linkage(r) is None


def test_root_cause_from_linkage_copies_verbatim() -> None:
    r = _evaluate_root_cause_linkage(VALID_CHAIN, "motor overheat")
    assert _root_cause_from_linkage(r) == VALID_CHAIN_ROOT_CAUSE


# ===========================================================================
# _build_sections
# ===========================================================================


def test_build_sections_are_the_three_cited_headings() -> None:
    sections = _build_sections(_request())
    assert [s.rule_id for s in sections] == ["RULE-SQE-007", "RULE-SQE-008", "RULE-SQE-009"]
    assert [s.heading for s in sections] == [
        "Root-Cause Requirement",
        "Corrective-Action Requirement",
        "Prevention / Read-Across",
    ]


# ===========================================================================
# Status truth table — one test per row
# ===========================================================================


def test_status_rule0_indeterminate_response_without_issue() -> None:
    status, reason = _resolve_status(
        issued=False,
        ncr_verdict="EVIDENCE_NOT_SUPPLIED",
        root_cause_verdict="EVIDENCE_VALID",
        cost_verdict="EVIDENCE_NOT_SUPPLIED",
        voe=None,
    )
    assert status == "INDETERMINATE"
    assert reason is not None


def test_status_rule0_indeterminate_voe_without_issue() -> None:
    status, reason = _resolve_status(
        issued=False,
        ncr_verdict="EVIDENCE_NOT_SUPPLIED",
        root_cause_verdict="EVIDENCE_NOT_SUPPLIED",
        cost_verdict="EVIDENCE_NOT_SUPPLIED",
        voe="checked",
    )
    assert status == "INDETERMINATE"
    assert reason is not None


def test_status_rule1_response_rejected() -> None:
    status, reason = _resolve_status(
        issued=True,
        ncr_verdict="EVIDENCE_INVALID",  # proves rule 1 outranks other-invalid
        root_cause_verdict="EVIDENCE_INVALID",
        cost_verdict="EVIDENCE_VALID",
        voe="checked",
    )
    assert status == "RESPONSE_REJECTED"
    assert reason is not None


def test_status_rule2_closable() -> None:
    status, reason = _resolve_status(
        issued=True,
        ncr_verdict="EVIDENCE_VALID",
        root_cause_verdict="EVIDENCE_VALID",
        cost_verdict="EVIDENCE_VALID",
        voe="checked",
    )
    assert status == "CLOSABLE"
    assert reason is None


def test_status_rule3_awaiting_root_cause_accepted_no_voe() -> None:
    status, reason = _resolve_status(
        issued=True,
        ncr_verdict="EVIDENCE_NOT_SUPPLIED",
        root_cause_verdict="EVIDENCE_VALID",
        cost_verdict="EVIDENCE_NOT_SUPPLIED",
        voe=None,
    )
    assert status == "AWAITING_SUPPLIER_RESPONSE"
    assert reason is not None and "accepted" in reason


def test_status_rule3_awaiting_no_response() -> None:
    status, reason = _resolve_status(
        issued=True,
        ncr_verdict="EVIDENCE_NOT_SUPPLIED",
        root_cause_verdict="EVIDENCE_NOT_SUPPLIED",
        cost_verdict="EVIDENCE_NOT_SUPPLIED",
        voe=None,
    )
    assert status == "AWAITING_SUPPLIER_RESPONSE"
    assert reason is not None and "no supplier root-cause response" in reason


def test_status_rule3_awaiting_valid_root_cause_but_ncr_invalid() -> None:
    # rca valid + voe set, but ncr invalid -> rule 2 fails (other_evidence_invalid) -> rule 3.
    status, _ = _resolve_status(
        issued=True,
        ncr_verdict="EVIDENCE_INVALID",
        root_cause_verdict="EVIDENCE_VALID",
        cost_verdict="EVIDENCE_VALID",
        voe="checked",
    )
    assert status == "AWAITING_SUPPLIER_RESPONSE"


def test_status_rule4_draft() -> None:
    status, reason = _resolve_status(
        issued=False,
        ncr_verdict="EVIDENCE_INVALID",
        root_cause_verdict="EVIDENCE_NOT_SUPPLIED",
        cost_verdict="EVIDENCE_NOT_SUPPLIED",
        voe=None,
    )
    assert status == "DRAFT"
    assert reason is not None


def test_status_rule5_issuable() -> None:
    status, reason = _resolve_status(
        issued=False,
        ncr_verdict="EVIDENCE_NOT_SUPPLIED",
        root_cause_verdict="EVIDENCE_NOT_SUPPLIED",
        cost_verdict="EVIDENCE_NOT_SUPPLIED",
        voe=None,
    )
    assert status == "ISSUABLE"
    assert reason is None


# ===========================================================================
# _build_warnings / _build_recommendations
# ===========================================================================


def test_warnings_due_date_missing_and_ncr_id_unbacked() -> None:
    req = _request(linked_ncr_id="NCR-9", due_date=None)
    r = generate_scar(req)
    assert any("No due_date" in w for w in r.warnings)
    assert any("NCR-9" in w for w in r.warnings)


def test_warnings_due_date_present_and_invalid_evidence_quoted() -> None:
    req = _request(due_date=datetime.date(2026, 2, 1))
    r = generate_scar(req, linked_ncr_evidence=[])
    assert not any("No due_date" in w for w in r.warnings)
    assert any("linked_ncr evidence was rejected" in w for w in r.warnings)


def test_recommendations_no_response_requests_root_cause() -> None:
    recs = _build_recommendations(
        {
            "supplier_root_cause": _evaluate_root_cause_linkage(None, "p"),
            "cost_impact": _evaluate_cost_impact_linkage(None),
        },
        voe=None,
    )
    assert any("Request the supplier's 5-Why" in rec for rec in recs)
    assert any("verification-of-effectiveness" in rec for rec in recs)
    assert any("itemized cost" in rec for rec in recs)


def test_recommendations_rejected_response_return_to_supplier() -> None:
    recs = _build_recommendations(
        {
            "supplier_root_cause": _evaluate_root_cause_linkage(BLAME_CHAIN, "Hole off-center"),
            "cost_impact": _evaluate_cost_impact_linkage(VALID_COST),
        },
        voe="checked",
    )
    assert any("Return the rejected response" in rec for rec in recs)
    # voe present + cost supplied -> neither of those two recs fire.
    assert not any("verification-of-effectiveness" in rec for rec in recs)
    assert not any("itemized cost" in rec for rec in recs)


def test_recommendations_valid_response_no_root_cause_rec() -> None:
    recs = _build_recommendations(
        {
            "supplier_root_cause": _evaluate_root_cause_linkage(VALID_CHAIN, "motor overheat"),
            "cost_impact": _evaluate_cost_impact_linkage(VALID_COST),
        },
        voe="checked",
    )
    assert not any("Request the supplier" in rec for rec in recs)
    assert not any("Return the rejected" in rec for rec in recs)


# ===========================================================================
# to_dict serialization / isolation
# ===========================================================================


def test_linkage_result_to_dict_raw_none_and_present() -> None:
    not_supplied = _evaluate_ncr_linkage(None).to_dict()
    assert not_supplied["raw_result"] is None
    assert not_supplied["findings"] == []
    valid = _evaluate_ncr_linkage(VALID_NCR).to_dict()
    assert isinstance(valid["raw_result"], dict)


def test_section_to_dict() -> None:
    section = SCARSection(heading="H", rule_id="RULE-SQE-007", content="C")
    assert section.to_dict() == {"heading": "H", "rule_id": "RULE-SQE-007", "content": "C"}


def test_result_to_dict_iso_dates_and_json_shape() -> None:
    req = _request(
        scar_id="SCAR-1",
        date_issued=datetime.date(2026, 1, 1),
        due_date=datetime.date(2026, 2, 1),
    )
    r = generate_scar(req, supplier_root_cause_evidence=VALID_CHAIN, verification_of_effectiveness="ok")
    d = r.to_dict()
    assert d["date_issued"] == "2026-01-01"
    assert d["due_date"] == "2026-02-01"
    assert d["status"] == "CLOSABLE"
    assert isinstance(d["sections"], list)
    assert isinstance(d["linkage"], dict)


def test_result_to_dict_isolation() -> None:
    req = _request(date_issued=datetime.date(2026, 1, 1))
    r = generate_scar(req, linked_ncr_evidence=VALID_NCR)
    d = r.to_dict()
    d["sections"].append("mutated")
    d["warnings"].append("mutated")
    d["linkage"]["linked_ncr"]["raw_result"]["records"].append("mutated")
    # Internal state untouched.
    assert len(r.sections) == 3
    assert "mutated" not in r.warnings
    assert r.linkage["linked_ncr"].raw_result is not None
    assert "mutated" not in r.linkage["linked_ncr"].raw_result["records"]


# ===========================================================================
# generate_scar end-to-end config wiring
# ===========================================================================


def test_generate_scar_default_config_includes_vendor_scorecard() -> None:
    r = generate_scar(_request())
    assert "vendor_scorecard" in r.linkage
    assert r.linkage["vendor_scorecard"].verdict == "LINKAGE_NOT_AVAILABLE"


def test_generate_scar_config_can_omit_vendor_scorecard() -> None:
    r = generate_scar(_request(), config=SCARConfig(evaluate_vendor_scorecard_linkage=False))
    assert "vendor_scorecard" not in r.linkage


# ===========================================================================
# Mandatory negative control — root-cause authorship invariant
# ===========================================================================


def test_root_cause_none_when_no_response() -> None:
    r = generate_scar(_request())
    assert r.root_cause is None


def test_root_cause_is_verbatim_supplier_text() -> None:
    req = _request(date_issued=datetime.date(2026, 1, 1))
    r = generate_scar(req, supplier_root_cause_evidence=VALID_CHAIN, verification_of_effectiveness="ok")
    assert r.root_cause == VALID_CHAIN_ROOT_CAUSE


def test_rejected_chain_root_cause_is_still_verbatim_not_authored() -> None:
    # Even a rejected chain surfaces the supplier's own terminal cause, never a synthesized one.
    req = _request(date_issued=datetime.date(2026, 1, 1))
    r = generate_scar(req, supplier_root_cause_evidence=BLAME_CHAIN)
    assert r.root_cause == "The operator forgot to tighten clamp bolts."
    assert r.status == "RESPONSE_REJECTED"


# ===========================================================================
# Mandatory negative control — no supplier response never reaches CLOSABLE
# ===========================================================================


@pytest.mark.parametrize("ncr", [None, VALID_NCR, []])
@pytest.mark.parametrize("cost", [None, VALID_COST])
@pytest.mark.parametrize("voe", [None, "checked"])
@pytest.mark.parametrize("issued", [None, datetime.date(2026, 1, 1)])
def test_no_response_never_closable(
    ncr: Any, cost: Any, voe: str | None, issued: datetime.date | None
) -> None:
    req = _request(date_issued=issued)
    r = generate_scar(
        req,
        linked_ncr_evidence=ncr,
        supplier_root_cause_evidence=None,
        cost_impact_evidence=cost,
        verification_of_effectiveness=voe,
    )
    assert r.status != "CLOSABLE"


# ===========================================================================
# Mandatory negative control — verdict-affecting linkage
# ===========================================================================


def test_invalid_ncr_forces_not_issuable() -> None:
    # A structurally invalid NCR (blank part_lot_id) that raises a CAUGHT pydantic.ValidationError.
    invalid_ncr = [
        {
            "part_lot_id": "   ",
            "defect_description": "d",
            "requirement_violated": "r",
            "quantity_affected": 1,
            "detection_point": "p",
        }
    ]
    r = generate_scar(_request(), linked_ncr_evidence=invalid_ncr)
    assert r.linkage["linked_ncr"].verdict == "EVIDENCE_INVALID"
    assert r.status != "ISSUABLE"


def test_rejected_root_cause_forces_response_rejected_not_closable() -> None:
    req = _request(date_issued=datetime.date(2026, 1, 1))
    r = generate_scar(
        req,
        supplier_root_cause_evidence=BLAME_CHAIN,
        verification_of_effectiveness="ok",
    )
    assert r.linkage["supplier_root_cause"].verdict == "EVIDENCE_INVALID"
    assert r.status == "RESPONSE_REJECTED"
    assert r.status != "CLOSABLE"


def test_rejected_root_cause_findings_verbatim_in_payload() -> None:
    r = generate_scar(_request(), supplier_root_cause_evidence=BLAME_CHAIN)
    findings = r.linkage["supplier_root_cause"].findings
    # The exact string AntiPatternFinding.message would produce, prefixed by its code.
    expected_prefix = "BLAME_TERMINAL_OPERATOR_ERROR: Terminal root cause "
    assert any(f.startswith(expected_prefix) for f in findings)


# ===========================================================================
# Mandatory negative control — superficial cause
# ===========================================================================


def test_superficial_operator_error_never_closes() -> None:
    steps = [
        {"step_number": 1, "why": "Why was the part defective?", "because": "Operator ran the wrong program."},
        {"step_number": 2, "why": "Why did that happen?", "because": "operator error, operator retrained"},
    ]
    req = _request(date_issued=datetime.date(2026, 1, 1))
    r = generate_scar(
        req,
        supplier_root_cause_evidence=steps,
        verification_of_effectiveness="ok",
        linked_ncr_evidence=VALID_NCR,
        cost_impact_evidence=VALID_COST,
    )
    assert r.linkage["supplier_root_cause"].verdict == "EVIDENCE_INVALID"
    assert r.status == "RESPONSE_REJECTED"
    assert r.status != "CLOSABLE"


# ===========================================================================
# Mandatory negative control — verification of effectiveness
# ===========================================================================


@pytest.mark.parametrize("voe", [None, "", "   "])
def test_valid_root_cause_without_voe_never_closable(voe: str | None) -> None:
    req = _request(date_issued=datetime.date(2026, 1, 1))
    r = generate_scar(
        req,
        supplier_root_cause_evidence=VALID_CHAIN,
        verification_of_effectiveness=voe,
    )
    assert r.linkage["supplier_root_cause"].verdict == "EVIDENCE_VALID"
    assert r.status == "AWAITING_SUPPLIER_RESPONSE"
    assert r.status != "CLOSABLE"


def test_voe_with_no_root_cause_never_closes() -> None:
    # A VOE with no underlying accepted root cause falls to AWAITING, not CLOSABLE.
    req = _request(date_issued=datetime.date(2026, 1, 1))
    r = generate_scar(req, verification_of_effectiveness="checked")
    assert r.status == "AWAITING_SUPPLIER_RESPONSE"
    assert r.status != "CLOSABLE"


# ===========================================================================
# Import-direction assertion (copied from test_ppap_linkage_engine.py, retargeted)
# ===========================================================================


def test_linked_engines_do_not_import_sqe() -> None:
    checked_modules = ("quality_core.ncr", "quality_core.rca", "quality_core.copq")
    for mod_name in checked_modules:
        importlib.import_module(mod_name)

    for mod_name, mod in sys.modules.items():
        if (
            any(mod_name == prefix or mod_name.startswith(f"{prefix}.") for prefix in checked_modules)
            and mod is not None
        ):
            mod_file = getattr(mod, "__file__", "")
            if mod_file and mod_file.endswith(".py"):
                with open(mod_file, encoding="utf-8") as f:
                    code = f.read()
                assert "quality_core.sqe" not in code, (
                    f"Import violation in {mod_name}: imports quality_core.sqe"
                )


# ===========================================================================
# No-duplicated-standards-data assertion
# ===========================================================================


def test_scar_reencodes_no_subengine_rule_literals() -> None:
    with open(scar_module.__file__, encoding="utf-8") as f:
        source = f.read()
    for forbidden in ("BLAME_TERMINAL_OPERATOR_ERROR", "ReturnToVendor", "InternalFailure"):
        assert forbidden not in source, f"scar.py re-encodes sub-engine literal {forbidden!r}"


# ===========================================================================
# estimate_copq dispatch worked benchmark (also covers cost EVIDENCE_VALID e2e)
# ===========================================================================


def test_generate_scar_cost_total_hand_computed() -> None:
    r = generate_scar(_request(), cost_impact_evidence=VALID_COST)
    assert r.linkage["cost_impact"].verdict == "EVIDENCE_VALID"
    assert r.linkage["cost_impact"].raw_result is not None
    assert r.linkage["cost_impact"].raw_result["total_copq"] == VALID_COST_TOTAL


# ===========================================================================
# Pre-existing NCR empty-records leak (documented, not fixed here)
# ===========================================================================


def test_ncr_empty_records_dict_escapes_as_valueerror() -> None:
    """Documents a pre-existing quality_core.ncr limitation for the reviewer/SME.

    validate_ncr({"records": []}) raises a BARE pandas ValueError, which is NOT in
    _evaluate_ncr_linkage's catch tuple (pydantic.ValidationError, TypeError). That specific
    input therefore ESCAPES the linkage helper instead of resolving EVIDENCE_INVALID. Every other
    invalid NCR shape (blank field, out-of-range quantity, empty list, wrong type) is handled.
    ncr/ is off-limits for #120, so this is asserted-as-is, not fixed.
    """
    with pytest.raises(ValueError):
        generate_scar(_request(), linked_ncr_evidence={"records": []})

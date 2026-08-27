"""Exhaustive behavioral tests for supplier escalation recommendations (#119)."""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import FrozenInstanceError

import pytest
from quality_core.sqe import (
    EscalationConfig,
    EscalationTrigger,
    ScorecardResult,
    evaluate_escalation,
)
from quality_core.sqe import escalation as escalation_module


def _scorecard(score: float | None = 100.0, verdict: str = "RATED") -> ScorecardResult:
    return ScorecardResult(
        supplier_id="SUP-119",
        period_start=datetime.date(2026, 1, 1),
        period_end=datetime.date(2026, 3, 31),
        period_label="2026 Q1",
        verdict=verdict,  # type: ignore[arg-type]
        composite_score=score,
        band="A" if score is not None else None,
        dimensions=[],
        heuristic_configuration={},
        omitted_dimensions=[],
        reason="missing evidence" if verdict == "INDETERMINATE" else None,
    )


def test_config_defaults_normalization_serialization_and_frozen_contract() -> None:
    config = EscalationConfig(monitor_score_maximum=90, scar_score_maximum=75,
                              containment_score_maximum=60, executive_score_maximum=40)
    assert config.monitor_score_maximum == 90.0
    assert config.to_dict()["monitor_score_maximum"] == {
        "value": 90.0, "is_heuristic": True,
        "basis": "caller-configurable engineering heuristic with no standards citation — see ASSUMPTIONS_LOG.md",
    }
    with pytest.raises(FrozenInstanceError):
        config.monitor_score_maximum = 88  # type: ignore[misc]


@pytest.mark.parametrize("field", ["monitor_score_maximum", "scar_score_maximum", "containment_score_maximum", "executive_score_maximum"])
@pytest.mark.parametrize("bad", [True, "75", None, object()])
def test_config_rejects_non_numeric_score_thresholds(field: str, bad: object) -> None:
    with pytest.raises(TypeError, match=f"{field} must be a finite number"):
        EscalationConfig(**{field: bad})  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["monitor_score_maximum", "scar_score_maximum", "containment_score_maximum", "executive_score_maximum"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_config_rejects_non_finite_score_thresholds(field: str, bad: float) -> None:
    with pytest.raises(ValueError, match=f"{field} must be finite"):
        EscalationConfig(**{field: bad})


@pytest.mark.parametrize("kwargs", [
    {"monitor_score_maximum": 101}, {"executive_score_maximum": -1},
    {"monitor_score_maximum": 74}, {"scar_score_maximum": 59},
    {"containment_score_maximum": 39},
])
def test_config_rejects_invalid_score_order(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="score thresholds must satisfy"):
        EscalationConfig(**kwargs)


@pytest.mark.parametrize("field", ["monitor_recurrence_minimum", "scar_recurrence_minimum", "containment_recurrence_minimum", "executive_recurrence_minimum"])
@pytest.mark.parametrize("bad", [True, 1.0, "1", None])
def test_config_rejects_non_integer_recurrence_thresholds(field: str, bad: object) -> None:
    with pytest.raises(TypeError, match=f"{field} must be an integer"):
        EscalationConfig(**{field: bad})  # type: ignore[arg-type]


@pytest.mark.parametrize("kwargs", [
    {"monitor_recurrence_minimum": 0}, {"scar_recurrence_minimum": 1},
    {"containment_recurrence_minimum": 2}, {"executive_recurrence_minimum": 3},
])
def test_config_rejects_invalid_recurrence_order(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="recurrence thresholds must be strictly increasing"):
        EscalationConfig(**kwargs)


@pytest.mark.parametrize(("score", "tier"), [(90, "NONE"), (89, "MONITOR"), (74, "SCAR_REQUIRED"), (59, "CONTAINMENT_REQUIRED"), (39, "EXECUTIVE_REVIEW")])
def test_score_threshold_boundaries_are_inclusive(score: float, tier: str) -> None:
    result = evaluate_escalation(_scorecard(score))
    assert result.tier == tier
    assert len(result.evaluated_triggers) == 4
    assert [row.tier for row in result.selected_evidence] == ([] if tier == "NONE" else [tier])


@pytest.mark.parametrize(("count", "tier"), [(0, "NONE"), (1, "MONITOR"), (2, "SCAR_REQUIRED"), (3, "CONTAINMENT_REQUIRED"), (4, "EXECUTIVE_REVIEW")])
def test_recurrence_threshold_boundaries_are_inclusive(count: int, tier: str) -> None:
    result = evaluate_escalation(_scorecard(100), recurrence_count=count)
    assert result.tier == tier
    assert len(result.evaluated_triggers) == 8
    assert all(row.metric == "recurrence_count" for row in result.selected_evidence)


def test_recurrence_is_explicit_only_and_highest_tier_wins_with_all_selected_evidence() -> None:
    omitted = evaluate_escalation(_scorecard(100))
    assert all(row.metric == "composite_score" for row in omitted.evaluated_triggers)
    combined = evaluate_escalation(_scorecard(39), recurrence_count=4)
    assert combined.tier == "EXECUTIVE_REVIEW"
    assert {(row.metric, row.tier) for row in combined.selected_evidence} == {
        ("composite_score", "EXECUTIVE_REVIEW"),
        ("recurrence_count", "EXECUTIVE_REVIEW")
    }


def test_highest_tier_selection_negative_control_is_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(escalation_module, "_TIER_RANK", {
        "NONE": 4, "MONITOR": 3, "SCAR_REQUIRED": 2, "CONTAINMENT_REQUIRED": 1, "EXECUTIVE_REVIEW": 0,
    })
    assert evaluate_escalation(_scorecard(74), recurrence_count=4).tier != "EXECUTIVE_REVIEW"


def test_indeterminate_is_terminal() -> None:
    result = evaluate_escalation(_scorecard(None, "INDETERMINATE"), recurrence_count=4)
    assert result.tier == "INDETERMINATE"
    assert result.evaluated_triggers == result.selected_evidence == []
    assert "neither cleared nor escalated" in result.reason  # type: ignore[operator]

@pytest.mark.parametrize("score", [True, "40", math.nan, math.inf, -math.inf, -0.1, 100.1])
def test_rated_scorecard_rejects_malformed_composite_score(score: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        evaluate_escalation(_scorecard(score))  # type: ignore[arg-type]


def test_type_and_malformed_scorecard_failures() -> None:
    with pytest.raises(TypeError, match="scorecard must"):
        evaluate_escalation(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="config must"):
        evaluate_escalation(_scorecard(), config=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must provide composite_score"):
        evaluate_escalation(_scorecard(None))
    with pytest.raises(ValueError, match="RATED or INDETERMINATE"):
        evaluate_escalation(_scorecard(80, "OTHER"))


@pytest.mark.parametrize("bad", [True, 1.0, "1", -1])
def test_recurrence_count_validation(bad: object) -> None:
    with pytest.raises((TypeError, ValueError), match="recurrence_count"):
        evaluate_escalation(_scorecard(), recurrence_count=bad)  # type: ignore[arg-type]


def test_trigger_and_result_serialization_are_json_safe_copy_isolated_and_authority_bound() -> None:
    result = evaluate_escalation(_scorecard(100))
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["commercial_authority"] == (
        "Any commercial response remains a business decision made by authorized people; this result recommends only a quality-engineering tier."
    )
    assert all(item["is_heuristic"] is True for item in payload["heuristic_configuration"].values())
    payload["heuristic_configuration"]["monitor_score_maximum"]["value"] = 0
    assert result.heuristic_configuration["monitor_score_maximum"]["value"] == 89.0

    trigger = EscalationTrigger("MONITOR", "composite_score", "<=", 89, 89, True)
    assert trigger.to_dict()["is_heuristic"] is True
    assert "no standards citation" in trigger.to_dict()["basis"]
    indeterminate = evaluate_escalation(_scorecard(None, "INDETERMINATE"))
    assert indeterminate.to_dict()["commercial_authority"] == payload["commercial_authority"]
    assert indeterminate.to_dict()["heuristic_configuration"]["monitor_score_maximum"]["is_heuristic"]


def test_heuristic_and_authority_wording_negative_control_is_load_bearing() -> None:
    result = evaluate_escalation(_scorecard(100))
    payload = result.to_dict()
    assert "authorized people" in payload["commercial_authority"]
    assert "no standards citation" in payload["evaluated_triggers"][0]["basis"]

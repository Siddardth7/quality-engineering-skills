"""Deterministic, evidence-first supplier escalation tier recommendations.

The tier ladder is informed by AIAG CQI-20 corrective-action discipline. Numeric thresholds are
caller-configurable engineering heuristics, not requirements of AIAG, ISO, or IATF.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from quality_core.sqe.scorecard import ScorecardResult

__all__ = [
    "EscalationConfig",
    "EscalationResult",
    "EscalationTier",
    "EscalationTrigger",
    "evaluate_escalation",
]

EscalationTier = Literal[
    "NONE",
    "MONITOR",
    "SCAR_REQUIRED",
    "CONTAINMENT_REQUIRED",
    "EXECUTIVE_REVIEW",
    "INDETERMINATE",
]
_RATED_TIERS: tuple[EscalationTier, ...] = (
    "NONE",
    "MONITOR",
    "SCAR_REQUIRED",
    "CONTAINMENT_REQUIRED",
    "EXECUTIVE_REVIEW",
)
_TIER_RANK = {tier: index for index, tier in enumerate(_RATED_TIERS)}
_HEURISTIC_BASIS = (
    "caller-configurable engineering heuristic with no standards citation — see "
    "ASSUMPTIONS_LOG.md"
)
_STRUCTURE_BASIS = (
    "AIAG CQI-20 corrective-action escalation discipline; organizational tier structure only, "
    "not numeric thresholds."
)
_COMMERCIAL_AUTHORITY = (
    "Any commercial response remains a business decision made by authorized people; this result "
    "recommends only a quality-engineering tier."
)
_SCORE_THRESHOLD_NAMES = (
    "monitor_score_maximum",
    "scar_score_maximum",
    "containment_score_maximum",
    "executive_score_maximum",
)
_RECURRENCE_THRESHOLD_NAMES = (
    "monitor_recurrence_minimum",
    "scar_recurrence_minimum",
    "containment_recurrence_minimum",
    "executive_recurrence_minimum",
)


def _finite_number(name: str, value: object) -> float:
    """Return a finite float, rejecting booleans and non-numeric values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number, got {type(value).__name__}: {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return numeric


def _recurrence_count(value: object, name: str) -> int:
    """Validate one explicitly supplied recurrence count or configuration threshold."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}: {value!r}")
    return value


def _criterion(value: float | int) -> dict[str, Any]:
    """Serialize one numeric criterion with its required no-standard disclosure."""
    return {
        "value": value,
        "is_heuristic": True,
        "basis": _HEURISTIC_BASIS,
    }


@dataclass(frozen=True)
class EscalationConfig:
    """Caller-owned numeric escalation thresholds. All defaults are heuristics."""

    monitor_score_maximum: float = 89.0
    scar_score_maximum: float = 74.0
    containment_score_maximum: float = 59.0
    executive_score_maximum: float = 39.0
    monitor_recurrence_minimum: int = 1
    scar_recurrence_minimum: int = 2
    containment_recurrence_minimum: int = 3
    executive_recurrence_minimum: int = 4

    def __post_init__(self) -> None:
        scores = tuple(_finite_number(name, getattr(self, name)) for name in _SCORE_THRESHOLD_NAMES)
        if not 0.0 <= scores[3] < scores[2] < scores[1] < scores[0] <= 100.0:
            raise ValueError(
                "score thresholds must satisfy "
                "0 <= executive < containment < scar < monitor <= 100"
            )
        for name, value in zip(_SCORE_THRESHOLD_NAMES, scores, strict=True):
            object.__setattr__(self, name, value)

        recurrence = tuple(
            _recurrence_count(getattr(self, name), name) for name in _RECURRENCE_THRESHOLD_NAMES
        )
        if not 1 <= recurrence[0] < recurrence[1] < recurrence[2] < recurrence[3]:
            raise ValueError("recurrence thresholds must be strictly increasing positive integers")

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Return copy-isolated, explicitly heuristic numeric configuration evidence."""
        return {
            name: _criterion(getattr(self, name))
            for name in (*_SCORE_THRESHOLD_NAMES, *_RECURRENCE_THRESHOLD_NAMES)
        }


@dataclass(frozen=True)
class EscalationTrigger:
    """One evaluated heuristic trigger, retained whether it fired or not."""

    tier: EscalationTier
    metric: str
    comparison: Literal["<=", ">="]
    observed_value: float | int
    threshold: float | int
    fired: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible trigger payload with heuristic disclosure."""
        return {
            "tier": self.tier,
            "metric": self.metric,
            "comparison": self.comparison,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
            "fired": self.fired,
            "is_heuristic": True,
            "basis": _HEURISTIC_BASIS,
        }


@dataclass(frozen=True)
class EscalationResult:
    """The single highest evidenced quality tier for a supplier scorecard."""

    supplier_id: str
    tier: EscalationTier
    scorecard_verdict: str
    evaluated_triggers: list[EscalationTrigger]
    selected_evidence: list[EscalationTrigger]
    recurrence_count: int | None
    reason: str | None
    heuristic_configuration: dict[str, dict[str, Any]] = field(default_factory=dict)
    standards_basis: str = _STRUCTURE_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible, copy-isolated escalation recommendation payload."""
        return {
            "supplier_id": self.supplier_id,
            "tier": self.tier,
            "scorecard_verdict": self.scorecard_verdict,
            "evaluated_triggers": [trigger.to_dict() for trigger in self.evaluated_triggers],
            "selected_evidence": [trigger.to_dict() for trigger in self.selected_evidence],
            "recurrence_count": self.recurrence_count,
            "reason": self.reason,
            "heuristic_configuration": {
                name: dict(criterion) for name, criterion in self.heuristic_configuration.items()
            },
            "standards_basis": self.standards_basis,
            "commercial_authority": _COMMERCIAL_AUTHORITY,
        }


def _evaluate_triggers(
    score: float,
    recurrence_count: int | None,
    config: EscalationConfig,
) -> list[EscalationTrigger]:
    """Evaluate every score trigger and every explicitly supplied recurrence trigger."""
    rows: list[EscalationTrigger] = []
    for tier, score_name, recurrence_name in zip(
        _RATED_TIERS[1:],
        _SCORE_THRESHOLD_NAMES,
        _RECURRENCE_THRESHOLD_NAMES,
        strict=True,
    ):
        score_threshold = getattr(config, score_name)
        rows.append(
            EscalationTrigger(
                tier=tier,
                metric="composite_score",
                comparison="<=",
                observed_value=score,
                threshold=score_threshold,
                fired=score <= score_threshold,
            )
        )
        if recurrence_count is not None:
            recurrence_threshold = getattr(config, recurrence_name)
            rows.append(
                EscalationTrigger(
                    tier=tier,
                    metric="recurrence_count",
                    comparison=">=",
                    observed_value=recurrence_count,
                    threshold=recurrence_threshold,
                    fired=recurrence_count >= recurrence_threshold,
                )
            )
    return rows


def evaluate_escalation(
    scorecard: ScorecardResult,
    *,
    config: EscalationConfig | None = None,
    recurrence_count: int | None = None,
) -> EscalationResult:
    """Recommend the highest evidenced escalation tier without a commercial disposition."""
    if not isinstance(scorecard, ScorecardResult):
        raise TypeError("scorecard must be a ScorecardResult")
    if config is not None and not isinstance(config, EscalationConfig):
        raise TypeError("config must be an EscalationConfig or None")
    if recurrence_count is not None:
        recurrence_count = _recurrence_count(recurrence_count, "recurrence_count")
        if recurrence_count < 0:
            raise ValueError("recurrence_count must be a non-negative integer or None")

    active_config = EscalationConfig() if config is None else config
    if scorecard.verdict == "INDETERMINATE":
        return EscalationResult(
            supplier_id=scorecard.supplier_id,
            tier="INDETERMINATE",
            scorecard_verdict=scorecard.verdict,
            evaluated_triggers=[],
            selected_evidence=[],
            recurrence_count=recurrence_count,
            reason=(
                "scorecard is INDETERMINATE; supplier is neither cleared nor escalated until "
                "required scorecard evidence is available"
            ),
            heuristic_configuration=active_config.to_dict(),
        )
    if scorecard.verdict != "RATED":
        raise ValueError(f"scorecard verdict must be RATED or INDETERMINATE, got {scorecard.verdict!r}")
    if scorecard.composite_score is None:
        raise ValueError("RATED scorecard must provide composite_score")

    score = _finite_number("scorecard.composite_score", scorecard.composite_score)
    if not 0.0 <= score <= 100.0:
        raise ValueError("scorecard.composite_score must be within [0, 100]")
    triggers = _evaluate_triggers(score, recurrence_count, active_config)
    fired = [trigger for trigger in triggers if trigger.fired]
    tier: EscalationTier = max(
        (trigger.tier for trigger in fired),
        key=lambda candidate: _TIER_RANK[candidate],
        default="NONE",
    )
    return EscalationResult(
        supplier_id=scorecard.supplier_id,
        tier=tier,
        scorecard_verdict=scorecard.verdict,
        evaluated_triggers=triggers,
        selected_evidence=[trigger for trigger in fired if trigger.tier == tier],
        recurrence_count=recurrence_count,
        reason=None,
        heuristic_configuration=active_config.to_dict(),
    )

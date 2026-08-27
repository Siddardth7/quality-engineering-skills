"""
Deterministic supplier scorecard composed from the SQE PPM and OTIF engines and, when
explicitly weighted, the COPQ estimator.

No published standard defines the weights, linear scoring curves, or A/B/C bands in this
module. ISO 9001:2015 section 8.4 and IATF 16949:2016 section 8.4 require organizations to
evaluate external providers against organization-determined criteria; neither clause supplies a
numeric scorecard criterion. Every numeric choice is therefore a caller-configurable engineering
heuristic carrying no standards citation (see ``ASSUMPTIONS_LOG.md``, RULE-SQE-007..010).

The source arithmetic is deliberately not repeated here. Quality is the PPM engine's measured
``ppm`` value, delivery is the OTIF engine's strict-conjunction ``otif_pct``, and cost is the COPQ
estimator's ``copq_percentage_of_revenue``. Every positively weighted dimension must be measured
before the scorecard may emit a composite or band; weights are never redistributed.
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from quality_core.copq import COPQDataset, CostItem, estimate_copq
from quality_core.sqe.otif import OTIFConfig, calculate_otif
from quality_core.sqe.ppm import PPMConfig, calculate_supplier_ppm
from quality_core.sqe.schema import (
    DeliveryRecord,
    DeliveryRecordDataset,
    ReceiptLot,
    ReceiptLotDataset,
    SupplierPeriod,
)

__all__ = [
    "LinearScoringCurve",
    "ScorecardConfig",
    "ScorecardDimensionResult",
    "ScorecardResult",
    "calculate_vendor_scorecard",
]

_HEURISTIC_BASIS = (
    "caller-configurable engineering heuristic with no standards citation — see "
    "ASSUMPTIONS_LOG.md"
)
_STANDARDS_BASIS = (
    "ISO 9001:2015 section 8.4 and IATF 16949:2016 section 8.4 require supplier "
    "evaluation against criteria determined by the organization; those clauses do not define "
    "any scorecard weight, scoring curve, or A/B/C band."
)
_SERIALIZATION_DIGITS = 10

DimensionName = Literal["quality", "delivery", "cost"]
ScorecardVerdict = Literal["RATED", "INDETERMINATE"]
ScorecardBand = Literal["A", "B", "C"]


def _finite_number(name: str, value: object) -> float:
    """Return a finite float, rejecting booleans and non-numeric values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}: {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return numeric


def _criterion(value: float) -> dict[str, Any]:
    """Serialize one numeric scorecard criterion with its required heuristic labels."""
    return {
        "value": value,
        "is_heuristic": True,
        "basis": _HEURISTIC_BASIS,
    }


@dataclass(frozen=True)
class LinearScoringCurve:
    """Linear mapping from a finite raw metric to a clamped score in ``[0, 100]``.

    ``best_value`` always maps to 100 and ``worst_value`` always maps to 0. Their order
    establishes whether a higher or lower raw value is better.
    """

    best_value: float
    worst_value: float

    def __post_init__(self) -> None:
        best = _finite_number("best_value", self.best_value)
        worst = _finite_number("worst_value", self.worst_value)
        if best == worst:
            raise ValueError("best_value and worst_value must be different")
        object.__setattr__(self, "best_value", best)
        object.__setattr__(self, "worst_value", worst)

    def score(self, raw_metric: float) -> float:
        """Map ``raw_metric`` to ``[0, 100]`` with interpolation and endpoint clamping."""
        raw = _finite_number("raw_metric", raw_metric)
        score = (raw - self.worst_value) / (self.best_value - self.worst_value) * 100.0
        return min(100.0, max(0.0, score))


@dataclass(frozen=True)
class ScorecardConfig:
    """Caller-configurable scorecard heuristics and source-engine configurations."""

    quality_weight: float = 0.60
    delivery_weight: float = 0.40
    cost_weight: float = 0.0
    quality_curve: LinearScoringCurve = field(
        default_factory=lambda: LinearScoringCurve(best_value=0.0, worst_value=10_000.0)
    )
    delivery_curve: LinearScoringCurve = field(
        default_factory=lambda: LinearScoringCurve(best_value=100.0, worst_value=0.0)
    )
    cost_curve: LinearScoringCurve | None = None
    a_band_minimum: float = 90.0
    b_band_minimum: float = 75.0
    ppm_config: PPMConfig = field(default_factory=PPMConfig)
    otif_config: OTIFConfig = field(default_factory=OTIFConfig)

    def __post_init__(self) -> None:
        weights: dict[str, float] = {}
        for name in ("quality_weight", "delivery_weight", "cost_weight"):
            value = _finite_number(name, getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1], got {value}")
            weights[name] = value
            object.__setattr__(self, name, value)
        if not math.isclose(sum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(
                "quality_weight + delivery_weight + cost_weight must equal 1.0; "
                f"got {sum(weights.values())!r}"
            )

        for name in ("quality_curve", "delivery_curve"):
            if not isinstance(getattr(self, name), LinearScoringCurve):
                raise TypeError(f"{name} must be a LinearScoringCurve")
        if self.cost_curve is not None and not isinstance(self.cost_curve, LinearScoringCurve):
            raise TypeError("cost_curve must be a LinearScoringCurve or None")
        if self.cost_weight > 0.0 and self.cost_curve is None:
            raise ValueError("cost_curve is required when cost_weight is positive")

        a_minimum = _finite_number("a_band_minimum", self.a_band_minimum)
        b_minimum = _finite_number("b_band_minimum", self.b_band_minimum)
        if not 0.0 <= b_minimum < a_minimum <= 100.0:
            raise ValueError(
                "band boundaries must satisfy "
                "0 <= b_band_minimum < a_band_minimum <= 100"
            )
        object.__setattr__(self, "a_band_minimum", a_minimum)
        object.__setattr__(self, "b_band_minimum", b_minimum)

        if not isinstance(self.ppm_config, PPMConfig):
            raise TypeError("ppm_config must be a PPMConfig")
        if not isinstance(self.otif_config, OTIFConfig):
            raise TypeError("otif_config must be an OTIFConfig")


@dataclass(frozen=True)
class ScorecardDimensionResult:
    """One weighted scorecard dimension and the source evidence behind it."""

    name: DimensionName
    source_metric_name: str
    raw_metric: float | None
    sub_score: float | None
    weight: float
    weighted_contribution: float | None
    source_verdict: str
    source_reason: str | None
    source_evidence: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    is_heuristic: bool = True
    basis: str = _HEURISTIC_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible, copy-isolated dimension payload."""
        return {
            "name": self.name,
            "source_metric_name": self.source_metric_name,
            "raw_metric": _rounded(self.raw_metric),
            "sub_score": _rounded(self.sub_score),
            "weight": self.weight,
            "weighted_contribution": _rounded(self.weighted_contribution),
            "source_verdict": self.source_verdict,
            "source_reason": self.source_reason,
            "source_evidence": _json_copy(self.source_evidence),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "is_heuristic": self.is_heuristic,
            "basis": self.basis,
        }


@dataclass(frozen=True)
class ScorecardResult:
    """Fully shaped vendor-scorecard result for one supplier period."""

    supplier_id: str
    period_start: datetime.date
    period_end: datetime.date
    period_label: str | None
    verdict: ScorecardVerdict
    composite_score: float | None
    band: ScorecardBand | None
    dimensions: list[ScorecardDimensionResult]
    heuristic_configuration: dict[str, Any]
    omitted_dimensions: list[dict[str, str]]
    reason: str | None
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    standards_basis: str = _STANDARDS_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Serialize dates and nested evidence to a stable JSON-compatible payload."""
        dimensions = [dimension.to_dict() for dimension in self.dimensions]
        serialized_composite: float | None = None
        if self.composite_score is not None:
            # Use the serialized contributions as the serialized composite's single source of
            # truth. This preserves sum(contributions) == composite at this precision.
            serialized_composite = sum(
                dimension["weighted_contribution"]
                for dimension in dimensions
                if dimension["weighted_contribution"] is not None
            )
        return {
            "supplier_id": self.supplier_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "period_label": self.period_label,
            "verdict": self.verdict,
            "composite_score": serialized_composite,
            "band": self.band,
            "dimensions": dimensions,
            "heuristic_configuration": _json_copy(self.heuristic_configuration),
            "omitted_dimensions": [dict(item) for item in self.omitted_dimensions],
            "reason": self.reason,
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "standards_basis": self.standards_basis,
        }


def _rounded(value: float | None) -> float | None:
    """Apply the scorecard's stable serialization precision to an optional float."""
    return None if value is None else round(value, _SERIALIZATION_DIGITS)


def _json_copy(value: Any) -> Any:
    """Copy the JSON-compatible structures emitted by composed engine ``to_dict`` methods."""
    if isinstance(value, dict):
        return {key: _json_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_copy(item) for item in value]
    return value


def _curve_payload(curve: LinearScoringCurve | None) -> dict[str, Any] | None:
    """Describe one curve and label both endpoint criteria independently."""
    if curve is None:
        return None
    return {
        "best_value": _criterion(curve.best_value),
        "worst_value": _criterion(curve.worst_value),
        "is_heuristic": True,
        "basis": _HEURISTIC_BASIS,
    }


def _heuristic_configuration(config: ScorecardConfig) -> dict[str, Any]:
    """Build the scorecard's fully labelled numeric-criteria disclosure."""
    return {
        "weights": {
            "quality": _criterion(config.quality_weight),
            "delivery": _criterion(config.delivery_weight),
            "cost": _criterion(config.cost_weight),
            "is_heuristic": True,
            "basis": _HEURISTIC_BASIS,
        },
        "curves": {
            "quality": _curve_payload(config.quality_curve),
            "delivery": _curve_payload(config.delivery_curve),
            "cost": _curve_payload(config.cost_curve),
            "is_heuristic": True,
            "basis": _HEURISTIC_BASIS,
        },
        "rating_bands": {
            "a_band_minimum": _criterion(config.a_band_minimum),
            "b_band_minimum": _criterion(config.b_band_minimum),
            "is_heuristic": True,
            "basis": _HEURISTIC_BASIS,
        },
        "is_heuristic": True,
        "basis": _HEURISTIC_BASIS,
    }


def _dimension(
    *,
    name: DimensionName,
    source_metric_name: str,
    raw_metric: float | None,
    weight: float,
    curve: LinearScoringCurve,
    source_verdict: str,
    source_reason: str | None,
    source_evidence: dict[str, Any],
    warnings: Sequence[str],
    recommendations: Sequence[str],
) -> ScorecardDimensionResult:
    """Build one measured or blocking dimension without imputing an absent raw metric."""
    sub_score = curve.score(raw_metric) if raw_metric is not None else None
    contribution = sub_score * weight if sub_score is not None else None
    return ScorecardDimensionResult(
        name=name,
        source_metric_name=source_metric_name,
        raw_metric=raw_metric,
        sub_score=sub_score,
        weight=weight,
        weighted_contribution=contribution,
        source_verdict=source_verdict,
        source_reason=source_reason,
        source_evidence=source_evidence,
        warnings=list(warnings),
        recommendations=list(recommendations),
    )


def _band_for(composite: float, config: ScorecardConfig) -> ScorecardBand:
    """Assign the band from the unrounded composite and configured boundaries."""
    if composite >= config.a_band_minimum:
        return "A"
    if composite >= config.b_band_minimum:
        return "B"
    return "C"


def calculate_vendor_scorecard(
    period: SupplierPeriod,
    lots: Sequence[ReceiptLot] | ReceiptLotDataset = (),
    deliveries: Sequence[DeliveryRecord] | DeliveryRecordDataset = (),
    *,
    copq_items: Sequence[CostItem | dict[str, Any]] | COPQDataset | None = None,
    revenue_base: float | None = None,
    config: ScorecardConfig | None = None,
) -> ScorecardResult:
    """Compose PPM, strict-conjunction OTIF, and optional COPQ into a vendor scorecard."""
    active_config = ScorecardConfig() if config is None else config
    if not isinstance(active_config, ScorecardConfig):
        raise TypeError("config must be a ScorecardConfig or None")

    # Each source engine is invoked once. Its arithmetic and missing-data policy stay authoritative.
    ppm_result = calculate_supplier_ppm(period, lots, config=active_config.ppm_config)
    otif_result = calculate_otif(period, deliveries, config=active_config.otif_config)

    dimensions: list[ScorecardDimensionResult] = []
    omissions: list[dict[str, str]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    if active_config.quality_weight > 0.0:
        quality = _dimension(
            name="quality",
            source_metric_name="ppm",
            raw_metric=ppm_result.ppm,
            weight=active_config.quality_weight,
            curve=active_config.quality_curve,
            source_verdict=ppm_result.verdict,
            source_reason=ppm_result.reason,
            source_evidence=ppm_result.to_dict(),
            warnings=ppm_result.warnings,
            recommendations=ppm_result.recommendations,
        )
        dimensions.append(quality)
        if ppm_result.verdict == "INDETERMINATE":
            blockers.append(f"quality/ppm is INDETERMINATE: {ppm_result.reason}")
    else:
        omissions.append({"name": "quality", "reason": "quality_weight is 0.0; not scored"})

    if active_config.delivery_weight > 0.0:
        delivery = _dimension(
            name="delivery",
            source_metric_name="otif_pct",
            raw_metric=otif_result.otif_pct,
            weight=active_config.delivery_weight,
            curve=active_config.delivery_curve,
            source_verdict=otif_result.verdict,
            source_reason=otif_result.reason,
            source_evidence=otif_result.to_dict(),
            warnings=otif_result.warnings,
            recommendations=otif_result.recommendations,
        )
        dimensions.append(delivery)
        if otif_result.verdict == "INDETERMINATE":
            blockers.append(f"delivery/otif_pct is INDETERMINATE: {otif_result.reason}")
    else:
        omissions.append({"name": "delivery", "reason": "delivery_weight is 0.0; not scored"})

    if active_config.cost_weight > 0.0:
        cost_evidence: dict[str, Any] = {
            "copq_percentage_of_revenue": None,
            "reason": None,
            "warnings": [],
            "recommendations": [],
        }
        cost_raw: float | None = None
        cost_verdict = "INDETERMINATE"
        cost_reason: str | None = None
        cost_warnings: list[str] = []
        cost_recommendations: list[str] = []
        has_items = copq_items is not None and (
            isinstance(copq_items, COPQDataset) or len(copq_items) > 0
        )
        if not has_items:
            cost_reason = "cost evidence is absent; positive cost weight cannot be redistributed"
            cost_recommendations.append(
                "Supply COPQ items and a positive revenue base, then re-run the scorecard."
            )
        else:
            try:
                copq_result = estimate_copq(items=copq_items, revenue_base=revenue_base)
            except (TypeError, ValueError) as exc:
                cost_reason = f"cost evidence is unusable: {exc}"
                cost_recommendations.append(
                    "Correct the COPQ evidence and revenue base, then re-run the scorecard."
                )
            else:
                cost_evidence = copq_result.to_dict()
                cost_raw = copq_result.copq_percentage_of_revenue
                cost_warnings = list(copq_result.warnings)
                cost_recommendations = list(copq_result.recommendations)
                if cost_raw is None:
                    cost_reason = (
                        "COPQ percentage-of-revenue is unavailable; a positive revenue base is "
                        "required and the cost weight cannot be redistributed"
                    )
                else:
                    cost_verdict = "MEASURED"

        cost_curve = active_config.cost_curve
        if cost_curve is None:  # Defensive for a config constructed without __post_init__.
            cost_reason = "configured cost scoring curve is absent"
            cost_verdict = "INDETERMINATE"
        else:
            cost = _dimension(
                name="cost",
                source_metric_name="copq_percentage_of_revenue",
                raw_metric=cost_raw,
                weight=active_config.cost_weight,
                curve=cost_curve,
                source_verdict=cost_verdict,
                source_reason=cost_reason,
                source_evidence=cost_evidence,
                warnings=cost_warnings,
                recommendations=cost_recommendations,
            )
            dimensions.append(cost)
        if cost_verdict == "INDETERMINATE":
            blockers.append(f"cost/copq_percentage_of_revenue is INDETERMINATE: {cost_reason}")
    else:
        omission_reason = (
            "cost_weight is 0.0; supplied COPQ evidence was not scored"
            if copq_items is not None or revenue_base is not None
            else "cost_weight is 0.0 and no COPQ evidence was supplied; cost was not scored"
        )
        omissions.append({"name": "cost", "reason": omission_reason})

    for dimension in dimensions:
        warnings.extend(f"{dimension.name}: {item}" for item in dimension.warnings)
        recommendations.extend(
            f"{dimension.name}: {item}" for item in dimension.recommendations
        )

    composite: float | None = None
    band: ScorecardBand | None = None
    verdict: ScorecardVerdict = "INDETERMINATE"
    reason = "; ".join(blockers) if blockers else None
    if not blockers:
        contributions = [
            dimension.weighted_contribution
            for dimension in dimensions
            if dimension.weighted_contribution is not None
        ]
        composite = sum(contributions)
        band = _band_for(composite, active_config)
        verdict = "RATED"

    return ScorecardResult(
        supplier_id=period.supplier_id,
        period_start=period.period_start,
        period_end=period.period_end,
        period_label=period.period_label,
        verdict=verdict,
        composite_score=composite,
        band=band,
        dimensions=dimensions,
        heuristic_configuration=_heuristic_configuration(active_config),
        omitted_dimensions=omissions,
        reason=reason,
        warnings=warnings,
        recommendations=recommendations,
    )

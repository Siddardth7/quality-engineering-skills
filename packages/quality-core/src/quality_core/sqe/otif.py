"""
otif.py
Deterministic OTIF (On-Time In-Full) and delivery-performance calculator for the SQE suite.

**No published standard defines any threshold in this module.** ISO 9001:2015 §8.4 and
IATF 16949:2016 §8.4 require that external providers be evaluated and monitored against criteria
*the organization determines*; they supply no on-time window, no in-full tolerance, and no rule for
whether an early delivery counts as on-time. Every ``OTIFConfig`` value here is therefore a declared
engineering heuristic, caller-configurable, and labelled as such in the result payload
(``heuristic_configuration["is_heuristic"]``). None of them traces to an AIAG/ISO/IATF clause, and
no ``CITATIONS.tsv`` row backs them — see ``ASSUMPTIONS_LOG.md`` (RULE-SQE-001/002/003).

Three figures are reported separately and are never collapsed into one another:

- ``on_time_pct`` — matched deliveries whose ``actual_delivery_date`` falls inside the configured
  window around ``promised_date``.
- ``in_full_pct`` — matched deliveries whose ``quantity_delivered`` meets the configured in-full
  tolerance against ``quantity_ordered``.
- ``otif_pct`` — the **strict conjunction**: a delivery counts only when it is on-time *and*
  in-full. It is derived from a per-delivery ``is_on_time and is_in_full`` count, never from an
  average of the other two percentages.

All three share one denominator, ``delivery_count`` (the number of matched deliveries).

Missing data is undecided, never imputed. If any matched delivery has an absent/unparseable
``promised_date`` or ``actual_delivery_date``, or an undecided ``quantity_delivered`` sentinel
(``None``), the *whole period* resolves ``INDETERMINATE`` — no partial percentages are computed
over the deliveries that do have complete data, and no date is ever substituted from a neighbouring
field or from the period bounds.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from quality_core.sqe.schema import DeliveryRecord, DeliveryRecordDataset, SupplierPeriod

__all__ = [
    "OTIFConfig",
    "OTIFResult",
    "calculate_otif",
]

_STANDARDS_BASIS: str = (
    "No published AIAG/ISO/IATF standard defines an on-time window, an in-full tolerance, or "
    "whether early delivery counts as on-time; every OTIFConfig value here is a declared "
    "engineering heuristic, caller-configurable (see ASSUMPTIONS_LOG.md, RULE-SQE-001/002)."
)

_HEURISTIC_BASIS: str = (
    "declared engineering default, no standards citation — see ASSUMPTIONS_LOG.md"
)

_HEURISTIC_RECOMMENDATION: str = (
    "Confirm the on-time window, the in-full tolerance, and the early-delivery rule against the "
    "supplier agreement: they are engineering defaults, not standards requirements."
)


@dataclass(frozen=True)
class OTIFConfig:
    """Caller-overridable OTIF engine configuration.

    Every field is a declared engineering heuristic — none traces to a published standard
    (see the module docstring and ``ASSUMPTIONS_LOG.md``).

    Attributes
    ----------
    early_tolerance_days : int
        Days before ``promised_date`` a delivery may arrive and still count as on-time when
        ``early_counts_as_on_time`` is ``False``.
    late_tolerance_days : int
        Days after ``promised_date`` a delivery may arrive and still count as on-time.
    early_counts_as_on_time : bool
        When ``True``, any arrival at or before the late bound counts as on-time regardless of how
        early it is; ``early_tolerance_days`` is then not applied.
    in_full_tolerance_pct : float
        Percentage of ``quantity_ordered`` that may be short and still count as in-full.
    over_delivery_counts_as_in_full : bool
        Whether ``quantity_delivered > quantity_ordered`` counts as in-full. Under schema-valid
        data this never differs, because ``DeliveryRecord`` rejects over-delivery outright.
    """

    early_tolerance_days: int = 0
    late_tolerance_days: int = 2
    early_counts_as_on_time: bool = False
    in_full_tolerance_pct: float = 0.0
    over_delivery_counts_as_in_full: bool = True

    def __post_init__(self) -> None:
        # bool is a subclass of int, so it is rejected explicitly for the numeric fields —
        # matching copq/estimator.py's boolean-rejection style.
        for name, value in (
            ("early_tolerance_days", self.early_tolerance_days),
            ("late_tolerance_days", self.late_tolerance_days),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int, got {type(value).__name__}: {value!r}")
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")
        for flag_name, flag_value in (
            ("early_counts_as_on_time", self.early_counts_as_on_time),
            ("over_delivery_counts_as_in_full", self.over_delivery_counts_as_in_full),
        ):
            if not isinstance(flag_value, bool):
                raise TypeError(
                    f"{flag_name} must be a bool, got {type(flag_value).__name__}: {flag_value!r}"
                )
        if isinstance(self.in_full_tolerance_pct, bool) or not isinstance(
            self.in_full_tolerance_pct, (int, float)
        ):
            raise TypeError(
                "in_full_tolerance_pct must be a number, got "
                f"{type(self.in_full_tolerance_pct).__name__}: {self.in_full_tolerance_pct!r}"
            )
        if not 0.0 <= float(self.in_full_tolerance_pct) <= 100.0:
            raise ValueError(
                f"in_full_tolerance_pct must be within [0, 100], got {self.in_full_tolerance_pct}"
            )


@dataclass
class OTIFResult:
    """Structured result of an OTIF / delivery-performance evaluation.

    ``delivery_count`` is the shared denominator of all three percentages; ``on_time_count``,
    ``in_full_count``, and ``otif_count`` are their respective numerators. The three percentages
    are reported separately and are never collapsed: ``otif_pct`` is the strict conjunction of
    on-time and in-full, not an average of ``on_time_pct`` and ``in_full_pct``.

    Every count and percentage is ``None`` exactly when ``verdict == "INDETERMINATE"``.
    """

    supplier_id: str
    period_start: datetime.date
    period_end: datetime.date
    period_label: str | None
    verdict: Literal["MEASURED", "INDETERMINATE"]
    delivery_count: int
    on_time_count: int | None
    in_full_count: int | None
    otif_count: int | None
    on_time_pct: float | None
    in_full_pct: float | None
    otif_pct: float | None
    delivery_breakdown: list[dict[str, Any]]
    heuristic_configuration: dict[str, Any]
    reason: str | None
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    standards_basis: str = _STANDARDS_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to a JSON-compatible dictionary.

        Built manually rather than via ``asdict()`` so the ``datetime.date`` period bounds are
        emitted as ISO-8601 strings.
        """
        return {
            "supplier_id": self.supplier_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "period_label": self.period_label,
            "verdict": self.verdict,
            "delivery_count": self.delivery_count,
            "on_time_count": self.on_time_count,
            "in_full_count": self.in_full_count,
            "otif_count": self.otif_count,
            "on_time_pct": self.on_time_pct,
            "in_full_pct": self.in_full_pct,
            "otif_pct": self.otif_pct,
            "delivery_breakdown": [dict(row) for row in self.delivery_breakdown],
            "heuristic_configuration": dict(self.heuristic_configuration),
            "reason": self.reason,
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "standards_basis": self.standards_basis,
        }


@dataclass(frozen=True)
class _DeliveryOutcome:
    """Per-delivery on-time / in-full / conjunction outcome for one complete delivery."""

    order_id: str
    is_on_time: bool
    is_in_full: bool
    is_otif: bool
    shortfall_qty: int


def _pct(numerator: int, denominator: int) -> float:
    """Percentage of a count over a count, exact float, no rounding.

    Both arguments are counts by type: a percentage can never be fed back in, so no percentage in
    this module can be derived by averaging two other percentages. ``denominator`` is always the
    matched-delivery count, which every caller has already proven non-zero.
    """
    return numerator / denominator * 100.0


def _heuristic_configuration(config: OTIFConfig) -> dict[str, Any]:
    """Every OTIFConfig value, flagged as a heuristic. Built for every verdict."""
    return {
        "early_tolerance_days": config.early_tolerance_days,
        "late_tolerance_days": config.late_tolerance_days,
        "early_counts_as_on_time": config.early_counts_as_on_time,
        "in_full_tolerance_pct": config.in_full_tolerance_pct,
        "over_delivery_counts_as_in_full": config.over_delivery_counts_as_in_full,
        "is_heuristic": True,
        "basis": _HEURISTIC_BASIS,
    }


def _resolve_deliveries(
    deliveries: Sequence[DeliveryRecord] | DeliveryRecordDataset,
) -> list[DeliveryRecord]:
    """Flatten the deliveries argument, unwrapping a DeliveryRecordDataset if one was passed.

    A plain sequence (including an empty one) is accepted directly: ``DeliveryRecordDataset``
    rejects an empty ``records`` list, so requiring the dataset type would make the empty-period
    case impossible to express as input.
    """
    if isinstance(deliveries, DeliveryRecordDataset):
        return list(deliveries.records)
    return list(deliveries)


def _evaluate_delivery(
    order_id: str,
    promised_date: datetime.date,
    actual_delivery_date: datetime.date,
    quantity_ordered: int,
    quantity_delivered: int,
    config: OTIFConfig,
) -> _DeliveryOutcome:
    """Resolve one complete delivery's on-time, in-full, and OTIF outcomes."""
    late_bound = promised_date + datetime.timedelta(days=config.late_tolerance_days)
    if config.early_counts_as_on_time:
        # Any early arrival counts, however early; the late side stays bounded.
        is_on_time = actual_delivery_date <= late_bound
    else:
        early_bound = promised_date - datetime.timedelta(days=config.early_tolerance_days)
        is_on_time = early_bound <= actual_delivery_date <= late_bound

    in_full_lower_bound = quantity_ordered * (1.0 - float(config.in_full_tolerance_pct) / 100.0)
    if config.over_delivery_counts_as_in_full:
        is_in_full = quantity_delivered >= in_full_lower_bound
    else:
        # Defensive branch: DeliveryRecord.reject_delivered_exceeding_ordered makes
        # quantity_delivered > quantity_ordered unreachable for schema-valid rows, so this
        # upper bound only bites on a record built via DeliveryRecord.model_construct().
        is_in_full = in_full_lower_bound <= quantity_delivered <= quantity_ordered

    return _DeliveryOutcome(
        order_id=order_id,
        is_on_time=is_on_time,
        is_in_full=is_in_full,
        # STRICT CONJUNCTION — a delivery is OTIF only if it is both on-time and in-full.
        is_otif=is_on_time and is_in_full,
        shortfall_qty=max(0, quantity_ordered - quantity_delivered),
    )


def _indeterminate(
    period: SupplierPeriod,
    config: OTIFConfig,
    delivery_count: int,
    reason: str,
    warnings: list[str],
    recommendations: list[str],
) -> OTIFResult:
    """Build a fully-shaped INDETERMINATE result through the same constructor as MEASURED."""
    return OTIFResult(
        supplier_id=period.supplier_id,
        period_start=period.period_start,
        period_end=period.period_end,
        period_label=period.period_label,
        verdict="INDETERMINATE",
        delivery_count=delivery_count,
        on_time_count=None,
        in_full_count=None,
        otif_count=None,
        on_time_pct=None,
        in_full_pct=None,
        otif_pct=None,
        delivery_breakdown=[],
        heuristic_configuration=_heuristic_configuration(config),
        reason=reason,
        warnings=warnings,
        recommendations=recommendations,
    )


def calculate_otif(
    period: SupplierPeriod,
    deliveries: Sequence[DeliveryRecord] | DeliveryRecordDataset = (),
    *,
    config: OTIFConfig | None = None,
) -> OTIFResult:
    """Calculate on-time, in-full, and OTIF delivery performance for one supplier period.

    Parameters
    ----------
    period : SupplierPeriod
        Caller-supplied supplier + inclusive evaluation window ``[period_start, period_end]``.
    deliveries : Sequence[DeliveryRecord] | DeliveryRecordDataset, optional
        Delivery records to evaluate. Records are matched by exact ``supplier_id`` and by
        ``promised_date`` falling inside the period window; a matched-supplier delivery whose
        ``promised_date`` is ``None`` is held **in scope** (it drives INDETERMINATE) rather than
        silently dropped. Defaults to an empty sequence, which resolves INDETERMINATE.
    config : OTIFConfig, optional
        Heuristic engine configuration. Defaults to ``OTIFConfig()``. No field of it traces to a
        published standard.

    Returns
    -------
    OTIFResult
        ``verdict == "MEASURED"`` with all three percentages populated, or
        ``verdict == "INDETERMINATE"`` with every count and percentage ``None`` when no delivery
        matched, or when any matched delivery is missing ``promised_date``,
        ``actual_delivery_date``, or ``quantity_delivered``. Nothing is imputed and no partial
        percentage is computed over the decided remainder.
    """
    active_config = config if config is not None else OTIFConfig()
    records = _resolve_deliveries(deliveries)

    matched = [
        record
        for record in records
        if record.supplier_id == period.supplier_id
        and (
            record.promised_date is None
            or period.period_start <= record.promised_date <= period.period_end
        )
    ]
    delivery_count = len(matched)

    if delivery_count == 0:
        return _indeterminate(
            period=period,
            config=active_config,
            delivery_count=0,
            reason="no delivery records matched supplier_id and period window",
            warnings=[
                "No delivery records matched this supplier and evaluation window; delivery "
                "performance is undecided, not perfect."
            ],
            recommendations=[
                "Supply delivery records for this supplier and window before reporting OTIF.",
                _HEURISTIC_RECOMMENDATION,
            ],
        )

    missing_promised: list[str] = []
    missing_actual: list[str] = []
    missing_quantity: list[str] = []
    complete: list[tuple[str, datetime.date, datetime.date, int, int]] = []

    for record in matched:
        promised = record.promised_date
        actual = record.actual_delivery_date
        delivered = record.quantity_delivered
        if promised is None:
            missing_promised.append(record.order_id)
        if actual is None:
            missing_actual.append(record.order_id)
        if delivered is None:
            missing_quantity.append(record.order_id)
        if promised is not None and actual is not None and delivered is not None:
            complete.append(
                (record.order_id, promised, actual, record.quantity_ordered, delivered)
            )

    blockers: list[str] = []
    if missing_promised:
        blockers.append(f"missing or unparseable promised_date: {', '.join(missing_promised)}")
    if missing_actual:
        blockers.append(
            f"missing or unparseable actual_delivery_date: {', '.join(missing_actual)}"
        )
    if missing_quantity:
        blockers.append(f"undecided quantity_delivered: {', '.join(missing_quantity)}")

    if blockers:
        # Whole-period rollup: one blocking delivery makes the entire period INDETERMINATE.
        # No percentage is computed over the deliveries that do have complete data.
        return _indeterminate(
            period=period,
            config=active_config,
            delivery_count=delivery_count,
            reason="; ".join(blockers),
            warnings=[
                f"{delivery_count - len(complete)} of {delivery_count} matched deliveries carry "
                "undecided data; no date or quantity was imputed."
            ],
            recommendations=[
                "Complete the missing delivery dates and received quantities, then re-run: a "
                "partial figure over the decided deliveries would overstate confidence.",
                _HEURISTIC_RECOMMENDATION,
            ],
        )

    outcomes = [
        _evaluate_delivery(
            order_id=order_id,
            promised_date=promised,
            actual_delivery_date=actual,
            quantity_ordered=ordered,
            quantity_delivered=delivered,
            config=active_config,
        )
        for order_id, promised, actual, ordered, delivered in complete
    ]

    on_time_count = sum(1 for outcome in outcomes if outcome.is_on_time)
    in_full_count = sum(1 for outcome in outcomes if outcome.is_in_full)
    # Counted from the per-delivery conjunction, never from the two percentages above.
    otif_count = sum(1 for outcome in outcomes if outcome.is_otif)

    warnings: list[str] = []
    recommendations: list[str] = [_HEURISTIC_RECOMMENDATION]
    if on_time_count < delivery_count:
        warnings.append(
            f"{delivery_count - on_time_count} of {delivery_count} deliveries fell outside the "
            "configured on-time window."
        )
    if in_full_count < delivery_count:
        warnings.append(
            f"{delivery_count - in_full_count} of {delivery_count} deliveries fell short of the "
            "configured in-full tolerance."
        )
    if otif_count < delivery_count:
        recommendations.append(
            "Review delivery_breakdown: OTIF counts only deliveries that are both on-time and "
            "in-full, so it is at or below each of on_time_pct and in_full_pct."
        )

    return OTIFResult(
        supplier_id=period.supplier_id,
        period_start=period.period_start,
        period_end=period.period_end,
        period_label=period.period_label,
        verdict="MEASURED",
        delivery_count=delivery_count,
        on_time_count=on_time_count,
        in_full_count=in_full_count,
        otif_count=otif_count,
        on_time_pct=_pct(on_time_count, delivery_count),
        in_full_pct=_pct(in_full_count, delivery_count),
        otif_pct=_pct(otif_count, delivery_count),
        delivery_breakdown=[
            {
                "order_id": outcome.order_id,
                "is_on_time": outcome.is_on_time,
                "is_in_full": outcome.is_in_full,
                "is_otif": outcome.is_otif,
                "shortfall_qty": outcome.shortfall_qty,
            }
            for outcome in outcomes
        ],
        heuristic_configuration=_heuristic_configuration(active_config),
        reason=None,
        warnings=warnings,
        recommendations=recommendations,
    )

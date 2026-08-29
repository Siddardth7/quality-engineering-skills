"""
ppm.py
Supplier defect-rate engine — parts per million (PPM) and defects per million opportunities
(DPMO) over a caller-supplied :class:`~quality_core.sqe.schema.SupplierPeriod` and the receipt
lots that fall inside it.

Computes, for one supplier and one inclusive window:
- ``ppm = (total_defective / total_received) * 1_000_000`` — the defect rate, reported with its
  numerator, denominator, matched lot count, and period bounds so every figure is re-derivable.
- ``dpmo = (total_defective / total_opportunities) * 1_000_000`` where
  ``total_opportunities = sum(quantity_received * opportunities_per_unit)`` — reported only when
  *every* in-scope lot states ``opportunities_per_unit``. DPMO is not PPM: the two are kept in
  separately named fields and are never substituted for one another.

No published standard behind the arithmetic
-------------------------------------------
No AIAG, ISO, IATF, or CQI-20 clause defines a PPM formula, a DPMO opportunity model, or a
sample-adequacy threshold. ISO 9001:2015 §8.4/§10.2 and IATF 16949:2016 §8.4 require that external
providers be evaluated against criteria *the organization determines*; they supply no arithmetic
and no numeric criterion. The arithmetic in this module is therefore generic industry practice and
is cited to nothing, and ``PPMConfig.sample_adequacy_minimum`` (default 1000 received units) is a
**declared engineering heuristic that traces to no AIAG/ISO/IATF/CQI-20 clause** — it is
caller-overridable, is labelled ``is_heuristic: True`` in every payload, and is recorded with its
rationale in ``ASSUMPTIONS_LOG.md``. Nothing here is added to ``CITATIONS.tsv``, because there is
no standards quotation to check.

The undecided sentinel
----------------------
``ReceiptLot.defect_count is None`` means *undecided* — never inspected/counted — and is distinct
from a decided ``0``. This engine is the downstream consumer that ``schema.py`` names: an undecided
lot resolves the whole period to ``INDETERMINATE``; it is never coerced to ``0`` and a PPM figure
is never computed over the decided remainder. The same rule governs ``receipt_date``: a lot whose
``supplier_id`` matches but whose ``receipt_date`` is ``None`` cannot be confirmed inside the
window, so it is held in scope and drives ``INDETERMINATE`` rather than being silently dropped —
silently dropping it would be a confident verdict built on absent data.

A supplier that shipped nothing, or whose lots were never counted, must never read as a perfect
performer: ``ppm`` is ``None`` on every ``INDETERMINATE`` path, and ``0.0`` is emitted only from
lots that were decided and decided clean.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from quality_core.sqe.schema import ReceiptLot, ReceiptLotDataset, SupplierPeriod

__all__ = [
    "PPMConfig",
    "PPMResult",
    "calculate_supplier_ppm",
]

_MILLION: int = 1_000_000

_STANDARDS_BASIS: str = (
    "No published AIAG/ISO/IATF standard defines a PPM formula, DPMO opportunity model, or "
    "sample-adequacy threshold; the arithmetic here is generic industry practice and the "
    "sample-adequacy minimum is a declared engineering heuristic (see ASSUMPTIONS_LOG.md)."
)

_SAMPLE_ADEQUACY_BASIS: str = (
    "declared engineering default, no standards citation — see ASSUMPTIONS_LOG.md"
)

_DEFAULT_SAMPLE_ADEQUACY_MINIMUM: int = 1000


@dataclass(frozen=True)
class PPMConfig:
    """Caller-overridable PPM engine configuration.

    Every field is a declared engineering heuristic — none traces to a published standard
    (see ``ASSUMPTIONS_LOG.md``).

    Attributes
    ----------
    sample_adequacy_minimum : int
        Received-unit count below which a computed rate is flagged as thin. Defaults to
        ``1000``: PPM is volatile at low denominators (one defect in 100 units reads as
        10,000 PPM), so a figure under this many received units is reported with a warning
        rather than suppressed. Not sourced from AIAG/ISO/IATF/CQI-20 — override it with a
        customer-agreed value where one exists.
    """

    sample_adequacy_minimum: int = _DEFAULT_SAMPLE_ADEQUACY_MINIMUM

    def __post_init__(self) -> None:
        """Validate the configured minimum, rejecting non-int and negative values."""
        if isinstance(self.sample_adequacy_minimum, bool) or not isinstance(
            self.sample_adequacy_minimum, int
        ):
            raise TypeError(
                "sample_adequacy_minimum must be an integer, got "
                f"{type(self.sample_adequacy_minimum).__name__}: "
                f"{self.sample_adequacy_minimum!r}"
            )
        if self.sample_adequacy_minimum < 0:
            raise ValueError(
                f"sample_adequacy_minimum must be >= 0, got {self.sample_adequacy_minimum}"
            )


@dataclass
class PPMResult:
    """Structured result of a supplier PPM / DPMO calculation over one period.

    ``ppm`` and ``numerator`` are ``None`` on every ``INDETERMINATE`` verdict — absent or
    undecided data never renders as ``0.0``. ``denominator`` and ``lot_count`` are always
    reported, because what *was* received is knowable even when what was defective is not.
    """

    supplier_id: str
    period_start: datetime.date
    period_end: datetime.date
    period_label: str | None
    verdict: Literal["MEASURED", "INDETERMINATE"]
    ppm: float | None
    numerator: int | None
    denominator: int
    lot_count: int
    dpmo: float | None
    dpmo_opportunity_count: int | None
    sample_adequacy: dict[str, Any]
    reason: str | None
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    standards_basis: str = _STANDARDS_BASIS

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to a JSON-compatible dictionary (dates as ISO-8601 strings)."""
        return {
            "supplier_id": self.supplier_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "period_label": self.period_label,
            "verdict": self.verdict,
            "ppm": self.ppm,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "lot_count": self.lot_count,
            "dpmo": self.dpmo,
            "dpmo_opportunity_count": self.dpmo_opportunity_count,
            "sample_adequacy": dict(self.sample_adequacy),
            "reason": self.reason,
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
            "standards_basis": self.standards_basis,
        }


def _resolve_lots(lots: Sequence[ReceiptLot] | ReceiptLotDataset) -> list[ReceiptLot]:
    """Flatten the ``lots`` argument to a list, unwrapping a ``ReceiptLotDataset``.

    A plain (possibly empty) sequence is accepted as-is: an empty period must be
    representable, and ``ReceiptLotDataset`` rejects an empty ``records`` list.
    """
    if isinstance(lots, ReceiptLotDataset):
        return list(lots.records)
    return list(lots)


def _select_in_scope_lots(
    period: SupplierPeriod, lots: Sequence[ReceiptLot]
) -> tuple[list[ReceiptLot], list[str]]:
    """Return the lots in scope for ``period`` plus the ids of those with no ``receipt_date``.

    A lot is in scope when its ``supplier_id`` matches exactly (ids are already stripped at
    ingest, so no fuzzy matching is applied here) and either its ``receipt_date`` falls inside
    the inclusive window or its ``receipt_date`` is the undecided sentinel. An undated lot is
    held in scope — it cannot be confirmed inside the window, and dropping it would silently
    decide a question the data leaves open.
    """
    in_scope: list[ReceiptLot] = []
    undated_lot_ids: list[str] = []
    for lot in lots:
        if lot.supplier_id != period.supplier_id:
            continue
        if lot.receipt_date is None:
            in_scope.append(lot)
            undated_lot_ids.append(lot.lot_id)
        elif period.period_start <= lot.receipt_date <= period.period_end:
            in_scope.append(lot)
    return in_scope, undated_lot_ids


def _format_lot_ids(lot_ids: Sequence[str]) -> str:
    """Render lot ids in input order for an operator-facing reason/warning string."""
    return ", ".join(repr(lot_id) for lot_id in lot_ids)


def _build_sample_adequacy(denominator: int, config: PPMConfig) -> dict[str, Any]:
    """Build the sample-adequacy payload, always labelled as the heuristic it is."""
    return {
        "minimum": config.sample_adequacy_minimum,
        "meets_minimum": denominator >= config.sample_adequacy_minimum,
        "is_heuristic": True,
        "basis": _SAMPLE_ADEQUACY_BASIS,
    }


def calculate_supplier_ppm(
    period: SupplierPeriod,
    lots: Sequence[ReceiptLot] | ReceiptLotDataset = (),
    *,
    config: PPMConfig | None = None,
) -> PPMResult:
    """Calculate a supplier's PPM defect rate (and DPMO where available) for one period.

    Parameters
    ----------
    period : SupplierPeriod
        Supplier identity and the inclusive evaluation window ``[period_start, period_end]``.
    lots : Sequence[ReceiptLot] | ReceiptLotDataset, optional
        Receipt lots to evaluate; a ``ReceiptLotDataset`` is unwrapped to its ``records``.
        Defaults to an empty sequence, which resolves ``INDETERMINATE``.
    config : PPMConfig, optional
        Engine heuristics. ``None`` uses :class:`PPMConfig` defaults.

    Returns
    -------
    PPMResult
        ``verdict="MEASURED"`` with a computed ``ppm`` only when at least one lot is in scope,
        the received total is non-zero, every in-scope lot carries a decided ``defect_count``,
        and no in-scope lot is undated. Otherwise ``verdict="INDETERMINATE"`` with ``ppm`` and
        ``numerator`` set to ``None`` and ``reason`` naming what blocked the figure — the
        result is the same shape either way.
    """
    resolved_config = PPMConfig() if config is None else config
    resolved_lots = _resolve_lots(lots)

    in_scope, undated_lot_ids = _select_in_scope_lots(period, resolved_lots)
    lot_count = len(in_scope)
    denominator = sum(lot.quantity_received for lot in in_scope)
    undecided_lot_ids = [lot.lot_id for lot in in_scope if lot.defect_count is None]
    decided_defect_counts = [lot.defect_count for lot in in_scope if lot.defect_count is not None]

    sample_adequacy = _build_sample_adequacy(denominator, resolved_config)
    warnings: list[str] = []
    recommendations: list[str] = []

    verdict: Literal["MEASURED", "INDETERMINATE"] = "INDETERMINATE"
    ppm: float | None = None
    numerator: int | None = None
    dpmo: float | None = None
    dpmo_opportunity_count: int | None = None
    reason: str | None = None

    if lot_count == 0 or denominator == 0:
        # Nothing (confirmed) received: the rate is undefined, not zero. A supplier that
        # shipped nothing must never read as a perfect performer.
        reason = (
            f"no in-scope received quantity: {lot_count} receipt lot(s) matched supplier_id "
            f"{period.supplier_id!r} in window "
            f"[{period.period_start.isoformat()}, {period.period_end.isoformat()}], "
            f"totalling {denominator} unit(s) received; PPM is undefined over a zero "
            "denominator and is not reported as 0.0"
        )
        recommendations.append(
            "Supply the receipt lots for this supplier and window before quoting a PPM figure."
        )
    elif undated_lot_ids or undecided_lot_ids:
        # Some in-scope lot leaves an input undecided. The period is INDETERMINATE as a whole:
        # a rate over the decided remainder would understate the exposure it omits.
        blockers: list[str] = []
        if undated_lot_ids:
            blockers.append(
                f"receipt_date is undecided on lot(s) {_format_lot_ids(undated_lot_ids)}, "
                "which cannot be confirmed inside the period window"
            )
            recommendations.append(
                "Record a receipt_date for lot(s) "
                f"{_format_lot_ids(undated_lot_ids)}, then re-run the calculation."
            )
        if undecided_lot_ids:
            blockers.append(
                f"defect_count is undecided on lot(s) {_format_lot_ids(undecided_lot_ids)}, "
                "which were never inspected or counted"
            )
            recommendations.append(
                "Complete the inspection count for lot(s) "
                f"{_format_lot_ids(undecided_lot_ids)}, then re-run the calculation."
            )
        reason = (
            "; ".join(blockers)
            + " — the period is INDETERMINATE and no PPM is computed over the decided remainder"
        )
    else:
        # Every in-scope lot is dated and decided, so decided_defect_counts covers all of them.
        verdict = "MEASURED"
        numerator = sum(decided_defect_counts)
        ppm = (numerator / denominator) * _MILLION
        missing_opportunity_lot_ids = [
            lot.lot_id for lot in in_scope if lot.opportunities_per_unit is None
        ]
        if missing_opportunity_lot_ids:
            warnings.append(
                "DPMO not computed: opportunities_per_unit is absent on lot(s) "
                f"{_format_lot_ids(missing_opportunity_lot_ids)}; DPMO requires an opportunity "
                "count for every in-scope lot and is not interchangeable with PPM."
            )
        else:
            dpmo_opportunity_count = sum(
                lot.quantity_received * lot.opportunities_per_unit
                for lot in in_scope
                if lot.opportunities_per_unit is not None
            )
            dpmo = (numerator / dpmo_opportunity_count) * _MILLION

    if not sample_adequacy["meets_minimum"]:
        warnings.append(
            f"Received quantity {denominator} is below the sample-adequacy minimum of "
            f"{resolved_config.sample_adequacy_minimum} unit(s); that minimum is a declared "
            "engineering heuristic with no standards basis (see ASSUMPTIONS_LOG.md)."
        )
        recommendations.append(
            "Treat the figure as indicative only until at least "
            f"{resolved_config.sample_adequacy_minimum} unit(s) are received, or override "
            "PPMConfig.sample_adequacy_minimum with a customer-agreed value."
        )

    return PPMResult(
        supplier_id=period.supplier_id,
        period_start=period.period_start,
        period_end=period.period_end,
        period_label=period.period_label,
        verdict=verdict,
        ppm=ppm,
        numerator=numerator,
        denominator=denominator,
        lot_count=lot_count,
        dpmo=dpmo,
        dpmo_opportunity_count=dpmo_opportunity_count,
        sample_adequacy=sample_adequacy,
        reason=reason,
        warnings=warnings,
        recommendations=recommendations,
    )

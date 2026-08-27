"""
sqe.py
FastMCP tools for Supplier Quality Engineering (SQE).

Wraps the six merged ``quality_core.sqe`` / ``quality_core.canvas.sqe`` engines — supplier
PPM/DPMO, OTIF delivery performance, the composed vendor scorecard, escalation-tier evaluation,
SCAR generation, and the read-only vendor-scorecard canvas — as deterministic MCP tools that
return JSON-compatible dictionaries to AI agents and MCP client hosts.

Six engines, six different standards postures
---------------------------------------------
These engines do not share one standards basis, so this module does not invent one. Each tool
echoes the ``standards_basis`` its own engine result carries as that payload's ``basis``:

- ``calculate_supplier_ppm`` / ``calculate_otif`` — assert that **no** published AIAG/ISO/IATF
  clause defines a PPM formula, a DPMO opportunity model, an on-time window, or an in-full
  tolerance.
- ``calculate_vendor_scorecard`` — cites ISO 9001:2015 section 8.4 and IATF 16949:2016
  section 8.4 only to record that they require supplier evaluation against
  organization-determined criteria while supplying no scorecard weight, scoring curve, or band.
- ``evaluate_escalation`` — cites AIAG CQI-20 corrective-action discipline for the tier
  *structure* only, never for a numeric threshold.
- ``generate_scar`` — cites AIAG CQI-20 (2nd Edition, 2018) and the Ford Global 8D Manual for
  three rendered section headings only.
- ``render_sqe_canvas`` — renders already-computed results rather than computing any, so it
  carries a canvas-local disclosure constant instead of an engine basis.

Every numeric weight, band boundary, curve endpoint, and threshold in every payload is
caller-configurable and is labelled ``is_heuristic: True`` by the engine that owns it. This tool
layer changes none of that: it type-guards input, forwards evidence, and serializes the engine's
own result.
"""

from __future__ import annotations

import datetime
import inspect
from collections import Counter
from typing import Annotated, Any, Callable, TypeVar

import pydantic
from pydantic import Field
from quality_core.canvas.sqe import SQECanvas, SQECanvasRow, render_sqe
from quality_core.io.validate import clean_pydantic_message
from quality_core.sqe.escalation import (
    EscalationConfig,
    EscalationResult,
    EscalationTrigger,
)
from quality_core.sqe.escalation import (
    evaluate_escalation as _evaluate_escalation_core,
)
from quality_core.sqe.otif import OTIFConfig
from quality_core.sqe.otif import calculate_otif as _calculate_otif_core
from quality_core.sqe.ppm import PPMConfig
from quality_core.sqe.ppm import calculate_supplier_ppm as _calculate_supplier_ppm_core
from quality_core.sqe.scar import (
    LINKAGE_KEYS,
    SCARConfig,
    SCARLinkageResult,
    SCARResult,
)
from quality_core.sqe.scar import generate_scar as _generate_scar_core
from quality_core.sqe.schema import (
    SCARRequest,
    SupplierPeriod,
    validate_sqe_delivery,
    validate_sqe_receipt,
)
from quality_core.sqe.scorecard import (
    LinearScoringCurve,
    ScorecardConfig,
    ScorecardDimensionResult,
    ScorecardResult,
)
from quality_core.sqe.scorecard import (
    calculate_vendor_scorecard as _calculate_vendor_scorecard_core,
)

__all__ = [
    "calculate_otif",
    "calculate_supplier_ppm",
    "calculate_vendor_scorecard",
    "evaluate_escalation",
    "generate_scar",
    "render_sqe_canvas",
]


# ===========================================================================
# Shared invariant notes
#
# Written once and appended verbatim to the tool docstrings and Field descriptions that need
# them, so the invariants survive into the prompt text an agent actually reads — not only into
# the returned payloads.
# ===========================================================================

_HEURISTIC_NOTE = (
    "Note on Engineering Heuristics: no AIAG/ISO/IATF/CQI-20 clause defines the PPM formula, the "
    "DPMO opportunity model, the OTIF on-time window or in-full tolerance, the scorecard weights, "
    "scoring curves, or A/B/C bands, or the escalation score/recurrence thresholds used here. "
    "ISO 9001:2015 section 8.4/10.2 and IATF 16949:2016 section 8.4 require supplier evaluation "
    "against organization-determined criteria but supply no numeric criterion of their own. Every "
    "threshold in this payload is a caller-configurable engineering default labelled "
    "is_heuristic=True (see quality_core.sqe.ASSUMPTIONS_LOG.md, RULE-SQE-001 through 010)."
)

_COMMERCIAL_AUTHORITY_NOTE = (
    "Note on Commercial Authority: this tool's output is never a commercial hold, de-sourcing "
    "action, or charge-back recommendation. Those remain decisions made by an authorized business "
    "owner; this tool returns only a quality-engineering figure or tier (sqe/ASSUMPTIONS_LOG.md "
    "RULE-SQE-014)."
)

_ROOT_CAUSE_AUTHORITY_NOTE = (
    "Note on Root-Cause Authorship: this tool requests and validates a supplier-authored root "
    "cause; it never states, infers, or synthesizes one itself. root_cause is None until a "
    "parseable supplier response is supplied."
)

_CANVAS_BASIS = (
    "All weights, thresholds, curves, bands, and escalation tiers rendered on this canvas are "
    "caller-configurable engineering heuristics with no standards citation; see each row's own "
    "scorecard/escalation standards_basis for engine-level detail."
)


# ===========================================================================
# Shared parameter descriptions
# ===========================================================================

_PERIOD_DESCRIPTION = (
    "Supplier evaluation window: {'supplier_id': str, 'period_start': ISO date, "
    "'period_end': ISO date, 'period_label': str | None}. If None, falls back to the "
    "benchmark period (supplier SUP-1001, January 2026)."
)

_LOTS_DESCRIPTION = (
    "Receipt lot rows: supplier_id, lot_id, quantity_received, receipt_date, defect_count, "
    "opportunities_per_unit. defect_count=None means the lot was never inspected/counted "
    "(undecided) — it is never treated as zero defects. If None, falls back to a benchmark "
    "3-lot receipt dataset (15,000 units received, 6 defective). Pass an empty list [] "
    "(not None) to evaluate a period with zero in-scope receipts."
)

_DELIVERIES_DESCRIPTION = (
    "Delivery rows: supplier_id, order_id, quantity_ordered, quantity_delivered, "
    "requested_date, promised_date, actual_delivery_date. quantity_delivered=None means the "
    "shipment was never received/counted (undecided), never coerced to 0 or to "
    "quantity_ordered. If None, falls back to a benchmark 3-delivery dataset. Pass an empty "
    "list [] (not None) to evaluate a period with zero matched deliveries."
)

_CURVE_DESCRIPTION_SUFFIX = (
    "Supplied as a two-element [best_value, worst_value] array or as "
    "{'best_value': float, 'worst_value': float}; best_value always maps to a sub-score of 100 "
    "and worst_value to 0. If None, the engine default curve is used — no curve is fabricated "
    "here. " + _HEURISTIC_NOTE
)


# ===========================================================================
# Deterministic benchmark datasets
#
# Hand-authored and internally consistent, so the demonstrated MEASURED -> RATED -> MONITOR
# chain is coherent end to end across tools 1-4.
# ===========================================================================

_BENCHMARK_PERIOD: dict[str, Any] = {
    "supplier_id": "SUP-1001",
    "period_start": "2026-01-01",
    "period_end": "2026-01-31",
    "period_label": "January 2026",
}

# denominator=15000, numerator=6 -> ppm=400.0; opportunities=60000 -> dpmo=100.0
_BENCHMARK_RECEIPT_LOTS: list[dict[str, Any]] = [
    {
        "supplier_id": "SUP-1001",
        "lot_id": "LOT-001",
        "quantity_received": 5000,
        "receipt_date": "2026-01-05",
        "defect_count": 3,
        "opportunities_per_unit": 4,
    },
    {
        "supplier_id": "SUP-1001",
        "lot_id": "LOT-002",
        "quantity_received": 4800,
        "receipt_date": "2026-01-12",
        "defect_count": 2,
        "opportunities_per_unit": 4,
    },
    {
        "supplier_id": "SUP-1001",
        "lot_id": "LOT-003",
        "quantity_received": 5200,
        "receipt_date": "2026-01-20",
        "defect_count": 1,
        "opportunities_per_unit": 4,
    },
]

# on_time = 3/3 = 100% (PO-9002 is 1 day late, inside the default late_tolerance_days=2)
# in_full = 2/3 (PO-9003 is short by 100 units, default in_full_tolerance_pct=0.0)
# otif    = 2/3 (strict conjunction: PO-9003 is on-time but not in-full)
_BENCHMARK_DELIVERY_RECORDS: list[dict[str, Any]] = [
    {
        "supplier_id": "SUP-1001",
        "order_id": "PO-9001",
        "quantity_ordered": 5000,
        "quantity_delivered": 5000,
        "promised_date": "2026-01-05",
        "actual_delivery_date": "2026-01-05",
    },
    {
        "supplier_id": "SUP-1001",
        "order_id": "PO-9002",
        "quantity_ordered": 4800,
        "quantity_delivered": 4800,
        "promised_date": "2026-01-12",
        "actual_delivery_date": "2026-01-13",
    },
    {
        "supplier_id": "SUP-1001",
        "order_id": "PO-9003",
        "quantity_ordered": 5200,
        "quantity_delivered": 5100,
        "promised_date": "2026-01-20",
        "actual_delivery_date": "2026-01-20",
    },
]

# No evidence supplied by default -> status="AWAITING_SUPPLIER_RESPONSE" and root_cause is None.
_BENCHMARK_SCAR_REQUEST: dict[str, Any] = {
    "supplier_id": "SUP-1001",
    "issue_description": (
        "Incoming inspection found 6 defective units across 3 receipt lots in January 2026 "
        "(bracket bore diameter out of tolerance)."
    ),
    "scar_id": "SCAR-2026-0042",
    "linked_ncr_id": None,
    "date_issued": "2026-02-03",
    "due_date": "2026-02-17",
    "requested_by": "Jane Doe, Senior Quality Engineer",
}


# ===========================================================================
# Docstring composition
# ===========================================================================

_ToolFunction = TypeVar("_ToolFunction", bound=Callable[..., dict[str, Any]])


def _with_notes(*notes: str) -> Callable[[_ToolFunction], _ToolFunction]:
    """Append shared invariant notes verbatim to a tool's docstring.

    The notes are single-sourced module constants rather than re-authored per tool, so the
    description an MCP host shows an agent carries exactly the same invariant wording the
    payload does.
    """

    def decorate(function: _ToolFunction) -> _ToolFunction:
        summary = inspect.cleandoc(function.__doc__ or "")
        function.__doc__ = "\n\n".join([summary, *notes])
        return function

    return decorate


# ===========================================================================
# Type guards (run before any engine call)
# ===========================================================================


def _guard_optional_dict(name: str, value: object) -> None:
    """Reject a non-dict, non-None value for a dictionary-shaped parameter."""
    if value is not None and not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict or None, got {type(value).__name__}: {value!r}")


def _guard_optional_dict_list(name: str, value: object) -> None:
    """Reject anything that is not a list of dicts (or None) for a row-list parameter."""
    if value is None:
        return
    if not isinstance(value, list):
        raise TypeError(
            f"{name} must be a list of dicts or None, got {type(value).__name__}: {value!r}"
        )
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise TypeError(f"{name}[{index}] must be a dict, got {type(item).__name__}: {item!r}")


def _guard_optional_int(name: str, value: object) -> None:
    """Reject a non-int (bool included, since bool subclasses int) for an integer parameter."""
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise TypeError(f"{name} must be an integer or None, got {type(value).__name__}: {value!r}")


def _guard_optional_number(name: str, value: object) -> None:
    """Reject a non-numeric value (bool included) for a float parameter."""
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise TypeError(f"{name} must be a number or None, got {type(value).__name__}: {value!r}")


def _guard_optional_bool(name: str, value: object) -> None:
    """Reject a non-bool value for a flag parameter; truthiness is never accepted."""
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool or None, got {type(value).__name__}: {value!r}")


def _guard_optional_str(name: str, value: object) -> None:
    """Reject a non-string value for an optional text parameter."""
    if value is not None and (isinstance(value, bool) or not isinstance(value, str)):
        raise TypeError(f"{name} must be a string or None, got {type(value).__name__}: {value!r}")


def _guard_optional_evidence(name: str, value: object) -> None:
    """Reject evidence that is neither a dict, a list, nor None.

    Evidence payloads are forwarded verbatim to the NCR / RCA / COPQ engines, which own their
    own shape validation; this guard only rejects container types those engines cannot accept.
    """
    if value is not None and not isinstance(value, (dict, list)):
        raise TypeError(
            f"{name} must be a dict, a list, or None, got {type(value).__name__}: {value!r}"
        )


# ===========================================================================
# Shared conversion helpers
# ===========================================================================


def _supplied_kwargs(**candidates: Any) -> dict[str, Any]:
    """Keep only the caller-supplied overrides, so every omitted one falls to the engine default."""
    return {name: value for name, value in candidates.items() if value is not None}


def _clean_validation_error(exc: pydantic.ValidationError) -> ValueError:
    """Convert a pydantic ``ValidationError`` into a bare, operator-readable ``ValueError``."""
    errors = exc.errors()
    message = str(errors[0].get("msg", "invalid value")) if errors else "invalid value"
    return ValueError(clean_pydantic_message(message))


def _clean_validation_details(exc: pydantic.ValidationError) -> str:
    """Render every error in a ``ValidationError`` as a cleaned ``"location: message"`` phrase.

    Unlike :func:`_clean_validation_error`, which surfaces only the first error because it is
    building an exception message, this names **every** offending field — it backs the ``reason``
    of a fully-shaped INDETERMINATE payload, where the caller is being told what a usable input
    would have had to contain rather than being handed an error.
    """
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: "
        f"{clean_pydantic_message(str(error['msg']))}"
        for error in exc.errors()
    )


def _curve_from_payload(
    name: str, payload: list[float] | dict[str, float] | None
) -> LinearScoringCurve | None:
    """Rebuild one ``LinearScoringCurve`` from its wire form, or ``None`` for the engine default.

    Accepts a two-element ``[best_value, worst_value]`` array or a mapping carrying both keys.
    ``LinearScoringCurve`` validates finiteness and endpoint distinctness itself; nothing is
    defaulted or fabricated here.
    """
    if payload is None:
        return None
    best: Any
    worst: Any
    if isinstance(payload, dict):
        if "best_value" not in payload or "worst_value" not in payload:
            raise ValueError(
                f"{name} mapping must supply both 'best_value' and 'worst_value', got "
                f"{sorted(payload)}"
            )
        best = payload["best_value"]
        worst = payload["worst_value"]
    elif isinstance(payload, list):
        if len(payload) != 2:
            raise ValueError(
                f"{name} must be a [best_value, worst_value] pair, got {len(payload)} element(s)"
            )
        best, worst = payload
    else:
        raise TypeError(
            f"{name} must be a [best_value, worst_value] pair, a mapping, or None, got "
            f"{type(payload).__name__}: {payload!r}"
        )
    return LinearScoringCurve(best_value=best, worst_value=worst)


def _scorecard_result_from_payload(payload: dict[str, Any]) -> ScorecardResult:
    """Rebuild a ``ScorecardResult`` from ``calculate_vendor_scorecard``'s own ``to_dict`` shape.

    Inverse of ``ScorecardResult.to_dict()`` / ``ScorecardDimensionResult.to_dict()``. Raises
    ``KeyError`` / ``TypeError`` / ``ValueError`` on a malformed payload — callers decide whether
    that surfaces as a ``ValueError`` or as a fully-shaped INDETERMINATE result.
    """
    dimensions = [
        ScorecardDimensionResult(
            name=dimension["name"],
            source_metric_name=dimension["source_metric_name"],
            raw_metric=dimension["raw_metric"],
            sub_score=dimension["sub_score"],
            weight=dimension["weight"],
            weighted_contribution=dimension["weighted_contribution"],
            source_verdict=dimension["source_verdict"],
            source_reason=dimension["source_reason"],
            source_evidence=dimension["source_evidence"],
            warnings=list(dimension.get("warnings", [])),
            recommendations=list(dimension.get("recommendations", [])),
            is_heuristic=dimension.get("is_heuristic", True),
            basis=dimension.get("basis", ""),
        )
        for dimension in payload["dimensions"]
    ]
    return ScorecardResult(
        supplier_id=payload["supplier_id"],
        period_start=datetime.date.fromisoformat(payload["period_start"]),
        period_end=datetime.date.fromisoformat(payload["period_end"]),
        period_label=payload.get("period_label"),
        verdict=payload["verdict"],
        composite_score=payload["composite_score"],
        band=payload["band"],
        dimensions=dimensions,
        heuristic_configuration=payload["heuristic_configuration"],
        omitted_dimensions=list(payload.get("omitted_dimensions", [])),
        reason=payload.get("reason"),
        warnings=list(payload.get("warnings", [])),
        recommendations=list(payload.get("recommendations", [])),
        standards_basis=payload.get("standards_basis", ""),
    )


def _escalation_trigger_from_payload(payload: dict[str, Any]) -> EscalationTrigger:
    """Rebuild one ``EscalationTrigger``; the serialized heuristic labels are dropped on the way in."""
    return EscalationTrigger(
        tier=payload["tier"],
        metric=payload["metric"],
        comparison=payload["comparison"],
        observed_value=payload["observed_value"],
        threshold=payload["threshold"],
        fired=payload["fired"],
    )


def _escalation_result_from_payload(payload: dict[str, Any]) -> EscalationResult:
    """Rebuild an ``EscalationResult`` from ``evaluate_escalation``'s own ``to_dict`` shape.

    ``EscalationTrigger``'s dataclass fields are exactly {tier, metric, comparison,
    observed_value, threshold, fired}; ``to_dict`` adds is_heuristic/basis, which are dropped
    here. Raises ``KeyError`` / ``TypeError`` / ``ValueError`` on a malformed payload.
    """
    return EscalationResult(
        supplier_id=payload["supplier_id"],
        tier=payload["tier"],
        scorecard_verdict=payload["scorecard_verdict"],
        evaluated_triggers=[
            _escalation_trigger_from_payload(trigger)
            for trigger in payload.get("evaluated_triggers", [])
        ],
        selected_evidence=[
            _escalation_trigger_from_payload(trigger)
            for trigger in payload.get("selected_evidence", [])
        ],
        recurrence_count=payload.get("recurrence_count"),
        reason=payload.get("reason"),
        heuristic_configuration=dict(payload.get("heuristic_configuration", {})),
        standards_basis=payload.get("standards_basis", ""),
    )


def _benchmark_scorecard() -> ScorecardResult:
    """Compose the benchmark vendor scorecard from the benchmark PPM and OTIF datasets."""
    return _calculate_vendor_scorecard_core(
        SupplierPeriod(**_BENCHMARK_PERIOD),
        validate_sqe_receipt([dict(row) for row in _BENCHMARK_RECEIPT_LOTS]),
        validate_sqe_delivery([dict(row) for row in _BENCHMARK_DELIVERY_RECORDS]),
    )


def _indeterminate_escalation_payload(
    *,
    supplier_id: Any,
    reason: str,
    config: EscalationConfig,
    recurrence_count: int | None,
) -> dict[str, Any]:
    """Build the fully-shaped INDETERMINATE escalation payload for an unusable scorecard payload.

    A real ``EscalationResult`` is constructed and serialized rather than a dict hand-rolled, so
    this payload's key set can never drift from the engine's own.
    """
    result = EscalationResult(
        supplier_id=supplier_id,
        tier="INDETERMINATE",
        scorecard_verdict="INDETERMINATE",
        evaluated_triggers=[],
        selected_evidence=[],
        recurrence_count=recurrence_count,
        reason=reason,
        heuristic_configuration=config.to_dict(),
    )
    payload = result.to_dict()
    payload["basis"] = payload["standards_basis"]
    return payload


def _indeterminate_scar_payload(*, reason: str) -> dict[str, Any]:
    """Build the fully-shaped INDETERMINATE SCAR payload for an empty request.

    A real ``SCARResult`` is constructed and serialized rather than a dict hand-rolled, so this
    payload's key set can never drift from the engine's own — the same technique
    :func:`_indeterminate_escalation_payload` uses.

    Every linkage slot resolves ``LINKAGE_NOT_AVAILABLE`` rather than ``EVIDENCE_NOT_SUPPLIED``:
    the request could not be constructed, so no evidence was ever dispatched to an owning engine.
    Saying "not supplied" would assert something about the caller's evidence that was never
    checked. For the same reason no caller-supplied evidence or verification statement is echoed
    back here — there is no SCAR for it to belong to.
    """
    result = SCARResult(
        supplier_id="",
        scar_id=None,
        issue_description="",
        status="INDETERMINATE",
        sections=[],
        linkage={
            key: SCARLinkageResult(
                linkage_key=key,
                verdict="LINKAGE_NOT_AVAILABLE",
                engine=None,
                findings=(),
                rationale=(
                    "The SCAR request was empty, so no evidence slot was dispatched to its "
                    "owning engine."
                ),
                raw_result=None,
            )
            for key in LINKAGE_KEYS
        },
        root_cause=None,
        verification_of_effectiveness=None,
        due_date=None,
        date_issued=None,
        reason=reason,
    )
    payload = result.to_dict()
    payload["basis"] = payload["standards_basis"]
    return payload


# ===========================================================================
# Tools
# ===========================================================================


@_with_notes(_HEURISTIC_NOTE)
def calculate_supplier_ppm(
    period: Annotated[
        dict[str, Any] | None,
        Field(description=_PERIOD_DESCRIPTION),
    ] = None,
    lots: Annotated[
        list[dict[str, Any]] | None,
        Field(description=_LOTS_DESCRIPTION),
    ] = None,
    sample_adequacy_minimum: Annotated[
        int | None,
        Field(
            description=(
                "Received-unit floor below which a computed PPM is flagged thin. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Calculate a supplier's PPM defect rate and DPMO (where available) for one evaluation period.

    Wraps quality_core.sqe.ppm.calculate_supplier_ppm. An uninspected lot (defect_count=None) or
    an undated in-scope lot resolves the whole period to INDETERMINATE with ppm=None: a supplier
    whose lots were never counted never reads as a perfect performer. DPMO is reported in its own
    field and is never substituted for PPM.
    """
    _guard_optional_dict("period", period)
    _guard_optional_dict_list("lots", lots)
    _guard_optional_int("sample_adequacy_minimum", sample_adequacy_minimum)

    period_payload = dict(_BENCHMARK_PERIOD) if period is None else period
    lots_payload = [dict(row) for row in _BENCHMARK_RECEIPT_LOTS] if lots is None else lots
    config: PPMConfig | None = None
    if sample_adequacy_minimum is not None:
        config = PPMConfig(sample_adequacy_minimum=sample_adequacy_minimum)

    try:
        result = _calculate_supplier_ppm_core(
            SupplierPeriod(**period_payload),
            validate_sqe_receipt(lots_payload) if lots_payload else [],
            config=config,
        )
    except pydantic.ValidationError as exc:
        raise _clean_validation_error(exc) from exc

    payload = result.to_dict()
    payload["basis"] = payload["standards_basis"]
    return payload


@_with_notes(_HEURISTIC_NOTE)
def calculate_otif(
    period: Annotated[
        dict[str, Any] | None,
        Field(description=_PERIOD_DESCRIPTION),
    ] = None,
    deliveries: Annotated[
        list[dict[str, Any]] | None,
        Field(description=_DELIVERIES_DESCRIPTION),
    ] = None,
    early_tolerance_days: Annotated[
        int | None,
        Field(
            description=(
                "OTIFConfig override (default 0): days before promised_date a delivery may arrive "
                "and still count as on-time. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    late_tolerance_days: Annotated[
        int | None,
        Field(
            description=(
                "OTIFConfig override (default 2): days after promised_date a delivery may arrive "
                "and still count as on-time. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    early_counts_as_on_time: Annotated[
        bool | None,
        Field(
            description=(
                "OTIFConfig override (default False): whether an arbitrarily early arrival counts "
                "as on-time. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    in_full_tolerance_pct: Annotated[
        float | None,
        Field(
            description=(
                "OTIFConfig override (default 0.0): percentage of quantity_ordered that may be "
                "short and still count as in-full. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    over_delivery_counts_as_in_full: Annotated[
        bool | None,
        Field(
            description=(
                "OTIFConfig override (default True): whether an over-delivery counts as in-full. "
                + _HEURISTIC_NOTE
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Calculate on-time, in-full, and strict-conjunction OTIF delivery performance for one period.

    Wraps quality_core.sqe.otif.calculate_otif. otif_pct is the strict conjunction of on-time and
    in-full, never an average of the two. A matched delivery missing promised_date,
    actual_delivery_date, or quantity_delivered resolves the period to INDETERMINATE rather than
    letting an uncounted shipment read as delivered.
    """
    _guard_optional_dict("period", period)
    _guard_optional_dict_list("deliveries", deliveries)
    _guard_optional_int("early_tolerance_days", early_tolerance_days)
    _guard_optional_int("late_tolerance_days", late_tolerance_days)
    _guard_optional_bool("early_counts_as_on_time", early_counts_as_on_time)
    _guard_optional_number("in_full_tolerance_pct", in_full_tolerance_pct)
    _guard_optional_bool("over_delivery_counts_as_in_full", over_delivery_counts_as_in_full)

    period_payload = dict(_BENCHMARK_PERIOD) if period is None else period
    deliveries_payload = (
        [dict(row) for row in _BENCHMARK_DELIVERY_RECORDS] if deliveries is None else deliveries
    )

    otif_kwargs = _supplied_kwargs(
        early_tolerance_days=early_tolerance_days,
        late_tolerance_days=late_tolerance_days,
        early_counts_as_on_time=early_counts_as_on_time,
        in_full_tolerance_pct=in_full_tolerance_pct,
        over_delivery_counts_as_in_full=over_delivery_counts_as_in_full,
    )
    config: OTIFConfig | None = None
    if otif_kwargs:
        config = OTIFConfig(**otif_kwargs)

    try:
        result = _calculate_otif_core(
            SupplierPeriod(**period_payload),
            validate_sqe_delivery(deliveries_payload) if deliveries_payload else [],
            config=config,
        )
    except pydantic.ValidationError as exc:
        raise _clean_validation_error(exc) from exc

    payload = result.to_dict()
    payload["basis"] = payload["standards_basis"]
    return payload


@_with_notes(_HEURISTIC_NOTE, _COMMERCIAL_AUTHORITY_NOTE)
def calculate_vendor_scorecard(
    period: Annotated[
        dict[str, Any] | None,
        Field(description=_PERIOD_DESCRIPTION),
    ] = None,
    lots: Annotated[
        list[dict[str, Any]] | None,
        Field(description=_LOTS_DESCRIPTION),
    ] = None,
    deliveries: Annotated[
        list[dict[str, Any]] | None,
        Field(description=_DELIVERIES_DESCRIPTION),
    ] = None,
    copq_items: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional Cost-of-Poor-Quality line items forwarded to quality_core.copq."
                "estimate_copq. Only scored when cost_weight > 0."
            )
        ),
    ] = None,
    revenue_base: Annotated[
        float | None,
        Field(
            description="Optional revenue base for the COPQ percentage-of-revenue dimension."
        ),
    ] = None,
    quality_weight: Annotated[
        float | None,
        Field(
            description=(
                "ScorecardConfig override (default 0.60). The three weights must sum to 1.0. "
                + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    delivery_weight: Annotated[
        float | None,
        Field(
            description=(
                "ScorecardConfig override (default 0.40). The three weights must sum to 1.0. "
                + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    cost_weight: Annotated[
        float | None,
        Field(
            description=(
                "ScorecardConfig override (default 0.0). A positive cost weight requires "
                "cost_curve, copq_items, and revenue_base to score. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    a_band_minimum: Annotated[
        float | None,
        Field(
            description=(
                "ScorecardConfig override (default 90.0): composite score at or above which the "
                "band is A. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    b_band_minimum: Annotated[
        float | None,
        Field(
            description=(
                "ScorecardConfig override (default 75.0): composite score at or above which the "
                "band is B, below which it is C. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    quality_curve: Annotated[
        list[float] | dict[str, float] | None,
        Field(
            description=(
                "ScorecardConfig override for the quality (PPM) scoring curve, engine default "
                "[0.0, 10000.0]. " + _CURVE_DESCRIPTION_SUFFIX
            )
        ),
    ] = None,
    delivery_curve: Annotated[
        list[float] | dict[str, float] | None,
        Field(
            description=(
                "ScorecardConfig override for the delivery (OTIF) scoring curve, engine default "
                "[100.0, 0.0]. " + _CURVE_DESCRIPTION_SUFFIX
            )
        ),
    ] = None,
    cost_curve: Annotated[
        list[float] | dict[str, float] | None,
        Field(
            description=(
                "ScorecardConfig override for the cost (COPQ percentage-of-revenue) scoring "
                "curve; there is no engine default, so it is required whenever cost_weight is "
                "positive. " + _CURVE_DESCRIPTION_SUFFIX
            )
        ),
    ] = None,
    ppm_config: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "ScorecardConfig override for the composed PPM engine, e.g. "
                "{'sample_adequacy_minimum': 500}. If None, the engine default PPMConfig is used. "
                + _HEURISTIC_NOTE
            )
        ),
    ] = None,
    otif_config: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "ScorecardConfig override for the composed OTIF engine, e.g. "
                "{'late_tolerance_days': 0, 'in_full_tolerance_pct': 1.0}. If None, the engine "
                "default OTIFConfig is used. " + _HEURISTIC_NOTE
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Compose PPM, strict-conjunction OTIF, and optional COPQ into a supplier scorecard.

    Wraps quality_core.sqe.scorecard.calculate_vendor_scorecard, which invokes each source engine
    once and keeps that engine's arithmetic and missing-data policy authoritative. Every
    positively weighted dimension must be measured before a composite or band is emitted; weight
    is never redistributed away from a dimension whose evidence is absent, so an unmeasured
    dimension resolves the scorecard to INDETERMINATE instead of inflating the score.
    """
    _guard_optional_dict("period", period)
    _guard_optional_dict_list("lots", lots)
    _guard_optional_dict_list("deliveries", deliveries)
    _guard_optional_dict_list("copq_items", copq_items)
    _guard_optional_number("revenue_base", revenue_base)
    _guard_optional_number("quality_weight", quality_weight)
    _guard_optional_number("delivery_weight", delivery_weight)
    _guard_optional_number("cost_weight", cost_weight)
    _guard_optional_number("a_band_minimum", a_band_minimum)
    _guard_optional_number("b_band_minimum", b_band_minimum)
    _guard_optional_dict("ppm_config", ppm_config)
    _guard_optional_dict("otif_config", otif_config)

    period_payload = dict(_BENCHMARK_PERIOD) if period is None else period
    lots_payload = [dict(row) for row in _BENCHMARK_RECEIPT_LOTS] if lots is None else lots
    deliveries_payload = (
        [dict(row) for row in _BENCHMARK_DELIVERY_RECORDS] if deliveries is None else deliveries
    )

    # A None override falls through to the engine default; no curve or sub-config is fabricated.
    scorecard_kwargs = _supplied_kwargs(
        quality_weight=quality_weight,
        delivery_weight=delivery_weight,
        cost_weight=cost_weight,
        a_band_minimum=a_band_minimum,
        b_band_minimum=b_band_minimum,
        quality_curve=_curve_from_payload("quality_curve", quality_curve),
        delivery_curve=_curve_from_payload("delivery_curve", delivery_curve),
        cost_curve=_curve_from_payload("cost_curve", cost_curve),
        ppm_config=None if ppm_config is None else PPMConfig(**ppm_config),
        otif_config=None if otif_config is None else OTIFConfig(**otif_config),
    )
    # ScorecardConfig.__post_init__ owns the weight-sum, band-ordering, and cost-curve rules and
    # raises its own TypeError/ValueError; those propagate unwrapped, as PPMConfig's do.
    config: ScorecardConfig | None = None
    if scorecard_kwargs:
        config = ScorecardConfig(**scorecard_kwargs)

    try:
        result = _calculate_vendor_scorecard_core(
            SupplierPeriod(**period_payload),
            validate_sqe_receipt(lots_payload) if lots_payload else [],
            validate_sqe_delivery(deliveries_payload) if deliveries_payload else [],
            copq_items=copq_items,
            revenue_base=revenue_base,
            config=config,
        )
    except pydantic.ValidationError as exc:
        raise _clean_validation_error(exc) from exc

    payload = result.to_dict()
    payload["basis"] = payload["standards_basis"]
    return payload


@_with_notes(_HEURISTIC_NOTE, _COMMERCIAL_AUTHORITY_NOTE)
def evaluate_escalation(
    scorecard: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "A ScorecardResult payload in the exact shape calculate_vendor_scorecard returns "
                "(the same dict, unmodified). If None, falls back to the benchmark scorecard "
                "composed from the benchmark PPM/OTIF datasets. An empty {} or a payload missing "
                "required keys is treated as absent input and returns a fully-shaped "
                "INDETERMINATE result rather than raising. A payload that reconstructs but "
                "carries an invalid value — a verdict other than RATED or INDETERMINATE, or a "
                "composite_score outside [0, 100] — raises a clean, single-line error instead."
            )
        ),
    ] = None,
    recurrence_count: Annotated[
        int | None,
        Field(
            description=(
                "Optional explicit recurrence count for this supplier's open corrective actions. "
                "Recurrence triggers are evaluated only when it is supplied."
            )
        ),
    ] = None,
    monitor_score_maximum: Annotated[
        float | None,
        Field(description="EscalationConfig override (default 89.0). " + _HEURISTIC_NOTE),
    ] = None,
    scar_score_maximum: Annotated[
        float | None,
        Field(description="EscalationConfig override (default 74.0). " + _HEURISTIC_NOTE),
    ] = None,
    containment_score_maximum: Annotated[
        float | None,
        Field(description="EscalationConfig override (default 59.0). " + _HEURISTIC_NOTE),
    ] = None,
    executive_score_maximum: Annotated[
        float | None,
        Field(description="EscalationConfig override (default 39.0). " + _HEURISTIC_NOTE),
    ] = None,
    monitor_recurrence_minimum: Annotated[
        int | None,
        Field(description="EscalationConfig override (default 1). " + _HEURISTIC_NOTE),
    ] = None,
    scar_recurrence_minimum: Annotated[
        int | None,
        Field(description="EscalationConfig override (default 2). " + _HEURISTIC_NOTE),
    ] = None,
    containment_recurrence_minimum: Annotated[
        int | None,
        Field(description="EscalationConfig override (default 3). " + _HEURISTIC_NOTE),
    ] = None,
    executive_recurrence_minimum: Annotated[
        int | None,
        Field(description="EscalationConfig override (default 4). " + _HEURISTIC_NOTE),
    ] = None,
) -> dict[str, Any]:
    """Evaluate the single highest-evidenced supplier escalation tier from a vendor scorecard.

    Wraps quality_core.sqe.escalation.evaluate_escalation. Every trigger is retained in
    evaluated_triggers whether it fired or not, and the tier the result carries is backed by
    selected_evidence rather than asserted. An INDETERMINATE scorecard yields tier=INDETERMINATE:
    the supplier is neither cleared nor escalated while required evidence is missing.

    Missing input and invalid input are answered differently. An empty {} or a scorecard missing
    required keys is absent evidence and yields tier=INDETERMINATE with a stated reason. A
    scorecard that reconstructs but carries an invalid value — a verdict other than RATED or
    INDETERMINATE, or a composite_score outside [0, 100] — raises a clean, single-line error:
    an unreadable scorecard is not the same claim as an inconclusive one.
    """
    _guard_optional_dict("scorecard", scorecard)
    _guard_optional_int("recurrence_count", recurrence_count)
    for score_name, score_value in (
        ("monitor_score_maximum", monitor_score_maximum),
        ("scar_score_maximum", scar_score_maximum),
        ("containment_score_maximum", containment_score_maximum),
        ("executive_score_maximum", executive_score_maximum),
    ):
        _guard_optional_number(score_name, score_value)
    for recurrence_name, recurrence_value in (
        ("monitor_recurrence_minimum", monitor_recurrence_minimum),
        ("scar_recurrence_minimum", scar_recurrence_minimum),
        ("containment_recurrence_minimum", containment_recurrence_minimum),
        ("executive_recurrence_minimum", executive_recurrence_minimum),
    ):
        _guard_optional_int(recurrence_name, recurrence_value)

    # EscalationConfig.__post_init__ owns the threshold-ordering rules and raises its own
    # ValueError on a bad override combination; that propagates unwrapped.
    active_config = EscalationConfig(
        **_supplied_kwargs(
            monitor_score_maximum=monitor_score_maximum,
            scar_score_maximum=scar_score_maximum,
            containment_score_maximum=containment_score_maximum,
            executive_score_maximum=executive_score_maximum,
            monitor_recurrence_minimum=monitor_recurrence_minimum,
            scar_recurrence_minimum=scar_recurrence_minimum,
            containment_recurrence_minimum=containment_recurrence_minimum,
            executive_recurrence_minimum=executive_recurrence_minimum,
        )
    )

    scorecard_model: ScorecardResult
    if scorecard is None:
        scorecard_model = _benchmark_scorecard()
    else:
        try:
            scorecard_model = _scorecard_result_from_payload(scorecard)
        except (KeyError, TypeError, ValueError) as exc:
            return _indeterminate_escalation_payload(
                supplier_id=scorecard.get("supplier_id"),
                reason=f"scorecard payload is malformed or incomplete: {exc}",
                config=active_config,
                recurrence_count=recurrence_count,
            )

    # A scorecard that reconstructed cleanly can still be semantically invalid — a verdict outside
    # {RATED, INDETERMINATE}, or a composite_score outside [0, 100]. That is a supplied-but-wrong
    # VALUE, not missing input, so it surfaces as a clean error rather than as an INDETERMINATE
    # tier: reporting "neither cleared nor escalated" would imply the scorecard was read and found
    # inconclusive, when in fact it was rejected.
    try:
        result = _evaluate_escalation_core(
            scorecard_model,
            config=active_config,
            recurrence_count=recurrence_count,
        )
    except pydantic.ValidationError as exc:
        raise _clean_validation_error(exc) from exc
    except ValueError as exc:
        raise ValueError(clean_pydantic_message(str(exc))) from exc

    payload = result.to_dict()
    payload["basis"] = payload["standards_basis"]
    return payload


@_with_notes(_ROOT_CAUSE_AUTHORITY_NOTE, _COMMERCIAL_AUTHORITY_NOTE)
def generate_scar(
    request: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "SCAR request: supplier_id, issue_description, scar_id, linked_ncr_id, "
                "date_issued, due_date, requested_by. If None, falls back to a benchmark issued "
                "SCAR request for SUP-1001. An empty {} returns a fully-shaped INDETERMINATE SCAR "
                "naming the fields a usable request must carry; a non-empty request holding an "
                "invalid value raises a clean, single-line error instead."
            )
        ),
    ] = None,
    linked_ncr_evidence: Annotated[
        dict[str, Any] | list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional nonconformance evidence forwarded verbatim to quality_core.ncr."
                "validate_ncr. None resolves EVIDENCE_NOT_SUPPLIED — a linked_ncr_id with no "
                "evidence behind it is still nothing to check."
            )
        ),
    ] = None,
    supplier_root_cause_evidence: Annotated[
        dict[str, Any] | list[dict[str, Any]] | None,
        Field(
            description=(
                "The supplier's returned 5-Why causal chain, forwarded verbatim to "
                "quality_core.rca.validate_five_why_chain. None resolves EVIDENCE_NOT_SUPPLIED. "
                + _ROOT_CAUSE_AUTHORITY_NOTE
            )
        ),
    ] = None,
    cost_impact_evidence: Annotated[
        dict[str, Any] | list[dict[str, Any]] | None,
        Field(
            description=(
                "Optional itemized cost evidence forwarded verbatim to quality_core.copq."
                "estimate_copq. None resolves EVIDENCE_NOT_SUPPLIED."
            )
        ),
    ] = None,
    verification_of_effectiveness: Annotated[
        str | None,
        Field(
            description=(
                "Caller-supplied verification-of-effectiveness statement. Never authored or "
                "inferred here; a blank or whitespace-only value normalises to None."
            )
        ),
    ] = None,
    evaluate_vendor_scorecard_linkage: Annotated[
        bool | None,
        Field(
            description=(
                "SCARConfig override (default True). The vendor_scorecard linkage slot always "
                "resolves LINKAGE_NOT_AVAILABLE this release regardless of this flag; it only "
                "controls whether the key is present at all."
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Generate a Supplier Corrective Action Request with cross-engine evidence linkage.

    Wraps quality_core.sqe.scar.generate_scar. Each evidence slot is dispatched to the engine
    that owns it (quality_core.ncr, quality_core.rca, quality_core.copq) and that engine's own
    findings are surfaced verbatim. The status state machine is not caller-tunable: CLOSABLE
    requires a stated verification of effectiveness, and a request issued with no date but with a
    response or verification attached resolves INDETERMINATE rather than picking a side.

    Empty input versus invalid input: an empty request ({}) returns a fully-shaped INDETERMINATE
    SCAR whose reason names every field a usable request must carry, and whose linkage slots all
    read LINKAGE_NOT_AVAILABLE because no evidence was ever dispatched. A non-empty request
    carrying an invalid value raises a clean, single-line error instead of a status.
    """
    _guard_optional_dict("request", request)
    _guard_optional_evidence("linked_ncr_evidence", linked_ncr_evidence)
    _guard_optional_evidence("supplier_root_cause_evidence", supplier_root_cause_evidence)
    _guard_optional_evidence("cost_impact_evidence", cost_impact_evidence)
    _guard_optional_str("verification_of_effectiveness", verification_of_effectiveness)
    _guard_optional_bool("evaluate_vendor_scorecard_linkage", evaluate_vendor_scorecard_linkage)

    request_payload = dict(_BENCHMARK_SCAR_REQUEST) if request is None else request
    config: SCARConfig | None = None
    if evaluate_vendor_scorecard_linkage is not None:
        config = SCARConfig(
            evaluate_vendor_scorecard_linkage=evaluate_vendor_scorecard_linkage
        )

    try:
        result = _generate_scar_core(
            SCARRequest(**request_payload),
            config=config,
            linked_ncr_evidence=linked_ncr_evidence,
            supplier_root_cause_evidence=supplier_root_cause_evidence,
            cost_impact_evidence=cost_impact_evidence,
            verification_of_effectiveness=verification_of_effectiveness,
        )
    except pydantic.ValidationError as exc:
        # An EMPTY request ({}) is the empty-input case, not a caller mistake: like every other
        # tool here it resolves to a fully-shaped INDETERMINATE payload naming what a usable
        # request would have carried. A NON-empty request that fails validation supplied
        # genuinely invalid values, and surfaces as a clean single-line ValueError.
        if not request_payload:
            return _indeterminate_scar_payload(
                reason=(
                    "SCAR request payload is empty, so no request could be constructed: "
                    + _clean_validation_details(exc)
                )
            )
        raise _clean_validation_error(exc) from exc

    payload = result.to_dict()
    payload["basis"] = payload["standards_basis"]
    return payload


@_with_notes(_HEURISTIC_NOTE, _COMMERCIAL_AUTHORITY_NOTE)
def render_sqe_canvas(
    rows: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Pre-computed supplier rows, each shaped exactly like the envelope "
                "{'supplier_id': str, 'supplier_name': str | None, "
                "'scorecard': <calculate_vendor_scorecard's own return dict>, "
                "'escalation': <evaluate_escalation's own return dict>}. This tool renders "
                "already-computed scorecard/escalation results; it does not recompute them from "
                "raw receipt or delivery data. If None, loads the 6-supplier benchmark canvas. "
                "An empty list [] (not None) is empty input: the canvas renders with no rows and "
                "the envelope resolves verdict=INDETERMINATE with a stated reason, so zero "
                "supplier results is never reported as a clean supplier population."
            )
        ),
    ] = None,
    title: Annotated[
        str,
        Field(description="Title displayed on the canvas header."),
    ] = "SQE Vendor Scorecard Canvas",
    theme: Annotated[
        str,
        Field(description="Theme mode for styling: 'dark' or 'light'. Defaults to 'dark'."),
    ] = "dark",
    standalone: Annotated[
        bool,
        Field(
            description="If True, returns a complete standalone HTML document; if False, returns an embeddable container."
        ),
    ] = True,
) -> dict[str, Any]:
    """Render an interactive HTML canvas of supplier vendor-scorecard and escalation results.

    Wraps quality_core.canvas.sqe. The canvas is read-only over results the caller already
    computed: an agent calls calculate_vendor_scorecard and evaluate_escalation per supplier,
    assembles those two payloads into a row envelope, and passes the rows here. An INDETERMINATE
    scorecard is rendered as UNRATED rather than as a score.

    Every payload carries verdict and reason. Supplying rows=[] is empty input and resolves
    verdict=INDETERMINATE with a stated reason; a canvas built from None (benchmark) or from at
    least one row resolves verdict=RENDERED with reason=None.
    """
    if type(standalone) is not bool:
        raise TypeError(f"standalone must be a boolean, got {type(standalone).__name__}: {standalone!r}")

    if type(title) is bool or not isinstance(title, str):
        raise TypeError(f"title must be a string, got {type(title).__name__}: {title!r}")
    if not title.strip():
        raise ValueError("title must not be empty.")

    if type(theme) is bool or not isinstance(theme, str):
        raise TypeError(f"theme must be a string, got {type(theme).__name__}: {theme!r}")
    clean_theme = theme.strip().lower()
    if clean_theme not in ("dark", "light"):
        raise ValueError(f"theme must be 'dark' or 'light', got {theme!r}")

    _guard_optional_dict_list("rows", rows)

    canvas: SQECanvas
    if rows is None:
        canvas = SQECanvas(title=title).load_sample()
    else:
        row_objects: list[SQECanvasRow] = []
        for index, row in enumerate(rows):
            try:
                row_objects.append(
                    SQECanvasRow(
                        supplier_id=row["supplier_id"],
                        scorecard=_scorecard_result_from_payload(row["scorecard"]),
                        escalation=_escalation_result_from_payload(row["escalation"]),
                        supplier_name=row.get("supplier_name"),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"rows[{index}]: {exc}") from exc
        canvas = SQECanvas(rows=row_objects, title=title)

    html_content = render_sqe(canvas, theme=clean_theme, standalone=standalone)

    canvas_rows = canvas.rows
    band_counts: Counter[str] = Counter(
        row.scorecard.band
        for row in canvas_rows
        if row.scorecard.verdict == "RATED" and row.scorecard.band is not None
    )
    tier_counts: Counter[str] = Counter(row.escalation.tier for row in canvas_rows)
    summary: dict[str, Any] = {
        "rows_count": len(canvas_rows),
        "rated_count": sum(1 for row in canvas_rows if row.scorecard.verdict == "RATED"),
        "indeterminate_count": sum(
            1 for row in canvas_rows if row.scorecard.verdict == "INDETERMINATE"
        ),
        "band_counts": {band: band_counts.get(band, 0) for band in ("A", "B", "C")},
        "tier_counts": {
            tier: tier_counts.get(tier, 0)
            for tier in (
                "NONE",
                "MONITOR",
                "SCAR_REQUIRED",
                "CONTAINMENT_REQUIRED",
                "EXECUTIVE_REVIEW",
                "INDETERMINATE",
            )
        },
    }

    # An explicitly empty row list is empty input, not a rendered result: the envelope says so
    # rather than returning a zero-row canvas that reads like a supplier population with nothing
    # wrong in it. The HTML is still rendered so the key set never varies.
    if rows is not None and not rows:
        verdict = "INDETERMINATE"
        reason: str | None = (
            "rows=[] was supplied, so no supplier scorecard or escalation result was available "
            "to render; no supplier on this canvas is rated, cleared, or escalated. Pass None to "
            "load the benchmark canvas."
        )
    else:
        verdict = "RENDERED"
        reason = None

    return {
        "title": canvas.title,
        "verdict": verdict,
        "reason": reason,
        "rows_count": len(canvas_rows),
        "summary": summary,
        "html": html_content,
        "basis": _CANVAS_BASIS,
    }

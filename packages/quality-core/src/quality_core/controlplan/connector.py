"""
connector.py
FMEA → Control Plan connector and PFMEA-linkage engine.

Maps a relational FMEA (``quality_core.schema.relational.RelationalFMEA``) into the
Control Plan contract (``quality_core.controlplan.schema.ControlPlanDataset``)
and performs deterministic PFMEA-linkage validation (orphan characteristic detection
and coverage verification).

Design Decisions (AIAG APQP & Control Plan / SPC Manual):
- Granularity: one ``ControlPlanRow`` per ``FailureMode``.
- Characteristic naming: ``f"{function.component} — {failure_mode.description}"``;
  on collision, appends failure-mode id and an incrementing counter suffix (`#N`)
  until unique.
- Recommended chart: always ``None`` from ``build_control_plan`` (the FMEA carries
  no data-type or subgroup-size input); ``recommend_chart()`` implements the AIAG
  SPC 4th Edition decision tree when data parameters are specified.
- Placeholders: ``sample_size=1``, ``frequency="per shift"``, ``reaction_plan``
  templated from the worst-risk effect. Every emitted row carries
  ``sample_plan_is_placeholder=True``.
- Prioritization: sorted descending by (AP ordinal, RPN, characteristic).
- Join key: stamps ``source_cause_id = f"{function.id}::{failure_mode.id}::{cause.id}"``
  and provides ``source_index()`` for runtime inspection.
- PFMEA Linkage Validation: ``validate_pfmea_linkage()`` checks that all Control Plan
  rows tie back to genuine FMEA causes, flagging any orphan characteristics without
  silent passes.
"""

from __future__ import annotations

from typing import Any, Iterator, Literal

from quality_core.controlplan.schema import ControlPlanDataset, ControlPlanRow, SPCChart
from quality_core.schema.relational import Cause, FailureLink, FailureMode, Function, RelationalFMEA
from quality_core.scoring import AP_ORDER, action_priority, rpn
from quality_core.spc.constants import XBAR_S_CONSTANTS

__all__ = [
    "DataType",
    "build_control_plan",
    "recommend_chart",
    "source_index",
    "validate_pfmea_linkage",
]

DataType = Literal["variable", "attribute"]

#: Largest subgroup size the SPC engine can compute an X-bar/S chart for (12).
_MAX_XBAR_S_N = max(XBAR_S_CONSTANTS)

_DEFAULT_SAMPLE_SIZE = 1
_DEFAULT_FREQUENCY = "per shift"


def _reaction_plan(effect_description: str) -> str:
    return f"Contain and investigate; failure effect: {effect_description}."


def recommend_chart(
    data_type: DataType,
    subgroup_size: int,
    *,
    defect_based: bool = False,
    constant_sample: bool = True,
) -> SPCChart:
    """Standards rule table (AIAG SPC Reference Manual, 4th Ed.) -> an ``SPCChart`` key.

    Variable data:
      - ``n == 1`` -> ``I-MR``
      - ``2 <= n <= 9`` -> ``Xbar-R``
      - ``10 <= n <= 12`` -> ``Xbar-S``
      - ``n > 12`` -> raises :class:`ValueError` (AIAG publishes no constants above 12).

    Attribute data:
      - Classifying units defective (``defect_based=False``) -> ``p`` regardless of sample size constancy.
      - Counting defects per unit (``defect_based=True``) -> ``c`` for constant sample, ``u`` for variable sample.

    Raises :class:`ValueError` if ``subgroup_size < 1`` or if variable ``subgroup_size > 12``.
    """
    if subgroup_size < 1:
        raise ValueError(f"subgroup_size must be >= 1, got {subgroup_size!r}")

    if data_type == "variable":
        if subgroup_size == 1:
            return "I-MR"
        if subgroup_size <= 9:
            return "Xbar-R"
        if subgroup_size > _MAX_XBAR_S_N:
            raise ValueError(
                f"subgroup_size {subgroup_size} exceeds the largest supported X-bar/S "
                f"subgroup size ({_MAX_XBAR_S_N}); AIAG publishes no A3/B3/B4/c4 "
                f"constants above it."
            )
        return "Xbar-S"

    # attribute data
    if not defect_based:
        return "p"
    return "c" if constant_sample else "u"


def _worst_link(failure_mode: FailureMode) -> tuple[FailureLink, int, str]:
    """Return the failure mode's worst-risk link with its (rpn, ap), by (AP, RPN, row_id)."""
    best: tuple[FailureLink, int, str] | None = None
    best_key: tuple[int, int, int] | None = None
    for link in failure_mode.links:
        effect, cause, control = failure_mode.resolve(link)
        link_rpn = rpn(effect.severity, cause.occurrence, control.detection)
        link_ap = action_priority(effect.severity, cause.occurrence, control.detection)
        key = (AP_ORDER[link_ap], link_rpn, link.row_id)
        if best_key is None or key > best_key:
            best_key = key
            best = (link, link_rpn, link_ap)
    assert best is not None
    return best


def _iter_named_modes(
    fmea: RelationalFMEA,
) -> Iterator[tuple[str, Function, FailureMode, FailureLink]]:
    """Yield ``(characteristic, function, failure_mode, worst_link)`` once per ``FailureMode``."""
    seen_characteristics: set[str] = set()
    for function in fmea.functions:
        for failure_mode in function.failure_modes:
            link, _link_rpn, _link_ap = _worst_link(failure_mode)

            characteristic = f"{function.component} — {failure_mode.description}"
            if characteristic in seen_characteristics:
                base = f"{characteristic} ({failure_mode.id})"
                characteristic, suffix = base, 2
                while characteristic in seen_characteristics:
                    characteristic = f"{base} #{suffix}"
                    suffix += 1
            seen_characteristics.add(characteristic)

            yield characteristic, function, failure_mode, link


def _source_cause_id(function: Function, failure_mode: FailureMode, cause: Cause) -> str:
    """Deterministic, dataset-wide-unique join key for an FMEA Cause."""
    return f"{function.id}::{failure_mode.id}::{cause.id}"


def build_control_plan(fmea: RelationalFMEA) -> ControlPlanDataset:
    """Derive a ControlPlanDataset from a RelationalFMEA with one row per FailureMode."""
    entries: list[tuple[str, str, int, str, str, str]] = []

    for characteristic, function, failure_mode, link in _iter_named_modes(fmea):
        worst_effect, worst_cause, worst_control = failure_mode.resolve(link)
        link_rpn = rpn(worst_effect.severity, worst_cause.occurrence, worst_control.detection)
        link_ap = action_priority(
            worst_effect.severity, worst_cause.occurrence, worst_control.detection
        )

        entries.append(
            (
                characteristic,
                worst_control.description,
                link_rpn,
                link_ap,
                _reaction_plan(worst_effect.description),
                _source_cause_id(function, failure_mode, worst_cause),
            )
        )

    entries.sort(key=lambda e: (AP_ORDER[e[3]], e[2], e[0]), reverse=True)

    rows = [
        ControlPlanRow(
            characteristic=characteristic,
            lsl=None,
            usl=None,
            target=None,
            measurement_method=measurement_method,
            sample_size=_DEFAULT_SAMPLE_SIZE,
            frequency=_DEFAULT_FREQUENCY,
            recommended_chart=None,
            reaction_plan=reaction_plan,
            source_cause_id=source_cause_id,
            sample_plan_is_placeholder=True,
        )
        for characteristic, measurement_method, _rpn, _ap, reaction_plan, source_cause_id in entries
    ]
    return ControlPlanDataset(rows=rows)


def source_index(fmea: RelationalFMEA) -> dict[str, dict[str, object]]:
    """Map each Control Plan characteristic to its source-cause identity dictionary."""
    index: dict[str, dict[str, object]] = {}
    for characteristic, function, failure_mode, link in _iter_named_modes(fmea):
        _, cause, _ = failure_mode.resolve(link)
        index[characteristic] = {
            "failure_mode_id": failure_mode.id,
            "cause_id": _source_cause_id(function, failure_mode, cause),
            "cause_description": cause.description,
            "occurrence": cause.occurrence,
            "component": function.component,
        }
    return index


def validate_pfmea_linkage(control_plan: ControlPlanDataset, fmea: RelationalFMEA) -> dict[str, Any]:
    """Validate bidirectional linkage between a Control Plan and a Relational FMEA.

    Checks:
    1. Every Control Plan row with a ``source_cause_id`` resolves to a valid cause in ``fmea``.
    2. Any Control Plan row with a missing or unresolvable ``source_cause_id`` is flagged
       as an orphan characteristic.
    3. Identifies any failure modes in the FMEA that have no linked Control Plan rows.

    Returns a structured dictionary:
    ``{"valid": bool, "total_rows": int, "linked_rows": int, "orphan_characteristics": list[str],
       "uncovered_failure_modes": list[str], "findings": list[str]}``
    """
    total_rows = len(control_plan.rows)

    # Collect valid cause IDs and failure mode keys from FMEA
    valid_cause_map: dict[str, tuple[str, str, str]] = {}
    fmea_failure_modes: set[tuple[str, str]] = set()

    for fn in fmea.functions:
        for fm in fn.failure_modes:
            fmea_failure_modes.add((fn.id, fm.id))
            for c in fm.causes:
                cid = _source_cause_id(fn, fm, c)
                valid_cause_map[cid] = (fn.id, fm.id, c.id)

    linked_rows = 0
    orphan_characteristics: list[str] = []
    covered_failure_modes: set[tuple[str, str]] = set()
    findings: list[str] = []

    for row in control_plan.rows:
        if row.source_cause_id is not None and row.source_cause_id in valid_cause_map:
            linked_rows += 1
            fn_id, fm_id, _ = valid_cause_map[row.source_cause_id]
            covered_failure_modes.add((fn_id, fm_id))
        else:
            orphan_characteristics.append(row.characteristic)
            if row.source_cause_id is None:
                findings.append(
                    f"Orphan characteristic '{row.characteristic}': missing source_cause_id."
                )
            else:
                findings.append(
                    f"Orphan characteristic '{row.characteristic}': source_cause_id "
                    f"'{row.source_cause_id}' not found in FMEA."
                )

    uncovered_fms = fmea_failure_modes - covered_failure_modes
    uncovered_failure_mode_ids = sorted([f"{fn_id}::{fm_id}" for fn_id, fm_id in uncovered_fms])

    for u_fm in uncovered_failure_mode_ids:
        findings.append(f"Uncovered FMEA failure mode '{u_fm}': no linked Control Plan row.")

    is_valid = len(orphan_characteristics) == 0

    return {
        "valid": is_valid,
        "total_rows": total_rows,
        "linked_rows": linked_rows,
        "orphan_characteristics": orphan_characteristics,
        "uncovered_failure_modes": uncovered_failure_mode_ids,
        "findings": findings,
    }

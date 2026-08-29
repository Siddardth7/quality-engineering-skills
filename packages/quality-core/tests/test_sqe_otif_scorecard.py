"""
test_sqe_otif_scorecard.py
Worked benchmark delivery sets for quality_core.sqe.otif.

Each benchmark hand-computes on_time_pct / in_full_pct / otif_pct on a mixed multi-delivery
period, then re-runs the same set with one injected late/short delivery and asserts the figures
move as expected. The headline benchmark is the CONJUNCTION set where on_time_pct == in_full_pct
== 66.67 but otif_pct == 33.33 (not the 66.67 average) — the mutation target for the strict-
conjunction control.
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from quality_core.sqe import DeliveryRecord, SupplierPeriod, calculate_otif

SUP = "SUP-BENCH"
P_START = datetime.date(2026, 3, 1)
P_END = datetime.date(2026, 3, 31)
PROMISED = datetime.date(2026, 3, 15)


def _period(**overrides: Any) -> SupplierPeriod:
    base: dict[str, Any] = {
        "supplier_id": SUP,
        "period_start": P_START,
        "period_end": P_END,
        "period_label": "2026-Q1-M3",
    }
    base.update(overrides)
    return SupplierPeriod(**base)


def _d(order_id: str, delivered: int, actual: datetime.date, ordered: int = 10) -> DeliveryRecord:
    return DeliveryRecord(
        supplier_id=SUP,
        order_id=order_id,
        quantity_ordered=ordered,
        quantity_delivered=delivered,
        promised_date=PROMISED,
        actual_delivery_date=actual,
    )


# ==============================================================================
# Headline conjunction benchmark: on_time 66.67, in_full 66.67, otif 33.33
# ==============================================================================


def _conjunction_set() -> list[DeliveryRecord]:
    return [
        # D1 OTIF: on-time and in-full
        _d("D1", delivered=10, actual=PROMISED),
        # D2 on-time but SHORT (in-full False under default 0% tolerance)
        _d("D2", delivered=8, actual=datetime.date(2026, 3, 16)),
        # D3 in-full but LATE (on-time False, > promised + 2 days)
        _d("D3", delivered=10, actual=datetime.date(2026, 3, 20)),
    ]


def test_conjunction_benchmark_figures() -> None:
    res = calculate_otif(_period(), _conjunction_set())
    assert res.verdict == "MEASURED"
    assert res.delivery_count == 3
    assert res.on_time_count == 2
    assert res.in_full_count == 2
    assert res.otif_count == 1
    assert res.on_time_pct == pytest.approx(66.6666, abs=1e-3)
    assert res.in_full_pct == pytest.approx(66.6666, abs=1e-3)
    assert res.otif_pct == pytest.approx(33.3333, abs=1e-3)


def test_otif_is_conjunction_not_average() -> None:
    # THE headline control: otif_pct must NOT equal the mean of on_time_pct and in_full_pct.
    res = calculate_otif(_period(), _conjunction_set())
    assert res.on_time_pct is not None
    assert res.in_full_pct is not None
    assert res.otif_pct is not None
    average = (res.on_time_pct + res.in_full_pct) / 2
    assert res.otif_pct != pytest.approx(average)
    # The conjunction is strictly at or below each component figure.
    assert res.otif_pct <= res.on_time_pct
    assert res.otif_pct <= res.in_full_pct
    # And exactly the single fully-OTIF delivery.
    assert res.otif_pct == pytest.approx(33.3333, abs=1e-3)


def test_conjunction_breakdown_flags() -> None:
    res = calculate_otif(_period(), _conjunction_set())
    by_id = {row["order_id"]: row for row in res.delivery_breakdown}
    assert by_id["D1"]["is_otif"] is True
    assert by_id["D2"] == {
        "order_id": "D2",
        "is_on_time": True,
        "is_in_full": False,
        "is_otif": False,
        "shortfall_qty": 2,
    }
    assert by_id["D3"] == {
        "order_id": "D3",
        "is_on_time": False,
        "is_in_full": True,
        "is_otif": False,
        "shortfall_qty": 0,
    }


# ==============================================================================
# Perfect benchmark + injected defects (negative controls)
# ==============================================================================


def _perfect_set() -> list[DeliveryRecord]:
    return [
        _d("P1", delivered=10, actual=PROMISED),
        _d("P2", delivered=10, actual=datetime.date(2026, 3, 16)),
        _d("P3", delivered=10, actual=datetime.date(2026, 3, 17)),
        _d("P4", delivered=10, actual=PROMISED),
    ]


def test_perfect_benchmark_is_100_pct() -> None:
    res = calculate_otif(_period(), _perfect_set())
    assert res.verdict == "MEASURED"
    assert res.on_time_pct == 100.0
    assert res.in_full_pct == 100.0
    assert res.otif_pct == 100.0
    assert res.otif_count == 4


def test_injected_late_delivery_drops_on_time_and_otif() -> None:
    deliveries = _perfect_set()
    # P4 arrives 5 days late (> promised + 2): on-time and OTIF fall, in-full holds.
    deliveries[3] = _d("P4", delivered=10, actual=datetime.date(2026, 3, 20))
    res = calculate_otif(_period(), deliveries)
    assert res.on_time_pct == pytest.approx(75.0)
    assert res.in_full_pct == 100.0
    assert res.otif_pct == pytest.approx(75.0)
    assert res.otif_count == 3


def test_injected_short_delivery_drops_in_full_and_otif() -> None:
    deliveries = _perfect_set()
    # P2 short by 3 units: in-full and OTIF fall, on-time holds.
    deliveries[1] = _d("P2", delivered=7, actual=datetime.date(2026, 3, 16))
    res = calculate_otif(_period(), deliveries)
    assert res.on_time_pct == 100.0
    assert res.in_full_pct == pytest.approx(75.0)
    assert res.otif_pct == pytest.approx(75.0)
    assert res.delivery_breakdown[1]["shortfall_qty"] == 3


def test_injected_undecided_delivery_forces_indeterminate() -> None:
    deliveries = _perfect_set()
    deliveries.append(
        DeliveryRecord(
            supplier_id=SUP,
            order_id="P5",
            quantity_ordered=10,
            quantity_delivered=None,
            promised_date=PROMISED,
            actual_delivery_date=None,
        )
    )
    res = calculate_otif(_period(), deliveries)
    assert res.verdict == "INDETERMINATE"
    assert res.delivery_count == 5
    assert res.otif_pct is None
    assert res.delivery_breakdown == []

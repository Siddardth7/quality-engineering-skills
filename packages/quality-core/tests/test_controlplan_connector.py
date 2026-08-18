"""
Tests for quality_core.controlplan.connector (build_control_plan, recommend_chart, source_index).
"""

from __future__ import annotations

import pytest
from quality_core.controlplan.connector import (
    _MAX_XBAR_S_N,
    _source_cause_id,
    build_control_plan,
    recommend_chart,
    source_index,
)
from quality_core.controlplan.schema import ControlPlanDataset
from quality_core.schema.relational import (
    Cause,
    Control,
    Effect,
    FailureLink,
    FailureMode,
    Function,
    RelationalFMEA,
)
from quality_core.scoring import action_priority, rpn
from quality_core.spc.constants import XBAR_S_CONSTANTS


def _fm(
    fm_id: str,
    description: str,
    s: int,
    o: int,
    d: int,
    *,
    row_id: int,
    effect_desc: str = "Effect",
    cause_desc: str = "Cause",
    control_desc: str = "Control",
) -> FailureMode:
    return FailureMode(
        id=fm_id,
        description=description,
        effects=[Effect(id=f"{fm_id}-E1", description=effect_desc, severity=s)],
        causes=[Cause(id=f"{fm_id}-C1", description=cause_desc, occurrence=o)],
        controls=[Control(id=f"{fm_id}-CT1", description=control_desc, detection=d)],
        links=[
            FailureLink(row_id=row_id, effect_id=f"{fm_id}-E1", cause_id=f"{fm_id}-C1", control_id=f"{fm_id}-CT1")
        ],
    )


def _function(fn_id: str, component: str, failure_modes: list[FailureMode], *, process_step: str = "Step") -> Function:
    return Function(
        id=fn_id, process_step=process_step, component=component, description="Function", failure_modes=failure_modes
    )


def _multi_link_fm(fm_id: str, description: str, triples: list[tuple[int, int, int, str, str]]) -> FailureMode:
    effects = [Effect(id=f"{fm_id}-E{i}", description=eff, severity=s) for i, (s, _o, _d, eff, _ctl) in enumerate(triples, 1)]
    causes = [Cause(id=f"{fm_id}-C{i}", description="Cause", occurrence=o) for i, (_s, o, _d, _eff, _ctl) in enumerate(triples, 1)]
    controls = [
        Control(id=f"{fm_id}-CT{i}", description=ctl, detection=d) for i, (_s, _o, d, _eff, ctl) in enumerate(triples, 1)
    ]
    links = [
        FailureLink(row_id=i, effect_id=f"{fm_id}-E{i}", cause_id=f"{fm_id}-C{i}", control_id=f"{fm_id}-CT{i}")
        for i in range(1, len(triples) + 1)
    ]
    return FailureMode(id=fm_id, description=description, effects=effects, causes=causes, controls=controls, links=links)


def test_field_mapping_single_row() -> None:
    fm = _fm(
        "F1-M1",
        "Incomplete weld",
        s=9,
        o=8,
        d=8,
        row_id=1,
        effect_desc="Joint fails in service",
        control_desc="Visual weld inspection",
    )
    fmea = RelationalFMEA(functions=[_function("F1", "Bracket", [fm])])

    dataset = build_control_plan(fmea)

    assert len(dataset.rows) == 1
    row = dataset.rows[0]
    assert row.characteristic == "Bracket — Incomplete weld"
    assert row.measurement_method == "Visual weld inspection"
    assert row.lsl is None
    assert row.usl is None
    assert row.target is None
    assert row.sample_size == 1
    assert row.frequency == "per shift"
    assert row.recommended_chart is None
    assert row.reaction_plan == "Contain and investigate; failure effect: Joint fails in service."


def test_build_control_plan_stamps_placeholder_flag_on_every_row() -> None:
    fms = [
        _fm("F1-M1", "Mode A", s=3, o=3, d=3, row_id=1),
        _fm("F1-M2", "Mode B", s=9, o=8, d=8, row_id=2),
        _fm("F1-M3", "Mode C", s=5, o=5, d=5, row_id=3),
    ]
    fmea = RelationalFMEA(functions=[_function("F1", "Widget", fms)])

    dataset = build_control_plan(fmea)

    assert len(dataset.rows) == 3
    assert [row.sample_plan_is_placeholder for row in dataset.rows] == [True, True, True]
    for row in dataset.rows:
        assert row.sample_size == 1
        assert row.frequency == "per shift"


def test_one_row_per_failure_mode() -> None:
    fms = [
        _fm("F1-M1", "Mode A", s=3, o=3, d=3, row_id=1),
        _fm("F1-M2", "Mode B", s=4, o=4, d=4, row_id=2),
        _fm("F1-M3", "Mode C", s=5, o=5, d=5, row_id=3),
    ]
    fmea = RelationalFMEA(functions=[_function("F1", "Widget", fms)])

    dataset = build_control_plan(fmea)

    assert len(dataset.rows) == 3
    assert {r.characteristic for r in dataset.rows} == {
        "Widget — Mode A",
        "Widget — Mode B",
        "Widget — Mode C",
    }


def test_empty_fmea_yields_empty_dataset() -> None:
    dataset = build_control_plan(RelationalFMEA(functions=[]))
    assert dataset == ControlPlanDataset(rows=[])


def test_ap_is_primary_over_rpn() -> None:
    assert action_priority(9, 6, 1) == "High"
    assert action_priority(3, 7, 10) == "Low"
    assert rpn(9, 6, 1) < rpn(3, 7, 10)

    fm_high_ap_low_rpn = _fm("F1-M1", "High AP mode", s=9, o=6, d=1, row_id=1)
    fm_low_ap_high_rpn = _fm("F1-M2", "Low AP mode", s=3, o=7, d=10, row_id=2)
    fmea = RelationalFMEA(functions=[_function("F1", "Comp", [fm_low_ap_high_rpn, fm_high_ap_low_rpn])])

    dataset = build_control_plan(fmea)

    assert [r.characteristic for r in dataset.rows] == [
        "Comp — High AP mode",
        "Comp — Low AP mode",
    ]


def test_rpn_breaks_ties_within_same_ap_band() -> None:
    assert action_priority(9, 8, 8) == "High"
    assert action_priority(9, 6, 1) == "High"
    assert rpn(9, 8, 8) > rpn(9, 6, 1)

    fm_low_rpn = _fm("F1-M1", "Low RPN mode", s=9, o=6, d=1, row_id=1)
    fm_high_rpn = _fm("F1-M2", "High RPN mode", s=9, o=8, d=8, row_id=2)
    fmea = RelationalFMEA(functions=[_function("F1", "Comp", [fm_low_rpn, fm_high_rpn])])

    dataset = build_control_plan(fmea)

    assert [r.characteristic for r in dataset.rows] == [
        "Comp — High RPN mode",
        "Comp — Low RPN mode",
    ]


def test_characteristic_breaks_ties_when_ap_and_rpn_are_equal() -> None:
    fm_alpha = _fm("F1-M1", "Alpha failure", s=5, o=5, d=5, row_id=1)
    fm_beta = _fm("F1-M2", "Beta failure", s=5, o=5, d=5, row_id=2)
    fmea = RelationalFMEA(functions=[_function("F1", "Comp", [fm_alpha, fm_beta])])

    dataset = build_control_plan(fmea)

    assert [r.characteristic for r in dataset.rows] == [
        "Comp — Beta failure",
        "Comp — Alpha failure",
    ]


def test_worst_link_is_not_necessarily_first_or_last() -> None:
    assert action_priority(3, 3, 3) == "Low"
    assert action_priority(9, 8, 8) == "High"
    assert action_priority(5, 5, 5) == "Low"

    fm = _multi_link_fm(
        "F1-M1",
        "Multi-link mode",
        [
            (3, 3, 3, "Effect 1", "Control 1"),
            (9, 8, 8, "Effect 2 (worst)", "Control 2 (worst)"),
            (5, 5, 5, "Effect 3", "Control 3"),
        ],
    )
    fmea = RelationalFMEA(functions=[_function("F1", "Comp", [fm])])

    dataset = build_control_plan(fmea)

    row = dataset.rows[0]
    assert row.measurement_method == "Control 2 (worst)"
    assert "Effect 2 (worst)" in row.reaction_plan


def test_worst_link_first_link_stays_best_when_later_link_is_weaker() -> None:
    assert action_priority(9, 8, 8) == "High"
    assert action_priority(3, 3, 3) == "Low"

    fm = _multi_link_fm(
        "F1-M1",
        "Descending-risk mode",
        [
            (9, 8, 8, "Effect 1 (worst)", "Control 1 (worst)"),
            (3, 3, 3, "Effect 2", "Control 2"),
        ],
    )
    fmea = RelationalFMEA(functions=[_function("F1", "Comp", [fm])])

    dataset = build_control_plan(fmea)

    row = dataset.rows[0]
    assert row.measurement_method == "Control 1 (worst)"
    assert "Effect 1 (worst)" in row.reaction_plan


def test_characteristic_collision_falls_back_to_failure_mode_id() -> None:
    fm1 = _fm("F1-M1", "Incomplete weld", s=9, o=6, d=1, row_id=1)
    fm2 = _fm("F2-M1", "Incomplete weld", s=3, o=3, d=3, row_id=2)
    fmea = RelationalFMEA(
        functions=[
            _function("F1", "Bracket", [fm1], process_step="Weld"),
            _function("F2", "Bracket", [fm2], process_step="Rework"),
        ]
    )

    dataset = build_control_plan(fmea)

    characteristics = [r.characteristic for r in dataset.rows]
    assert characteristics == [
        "Bracket — Incomplete weld",
        "Bracket — Incomplete weld (F2-M1)",
    ]
    assert len(set(characteristics)) == len(characteristics)


def test_characteristic_collision_across_many_functions_with_same_fm_id() -> None:
    fms = [_fm("M1", "weld", s=1, o=1, d=1, row_id=i) for i in range(1, 6)]
    fmea = RelationalFMEA(
        functions=[
            _function(f"F{i}", "Bracket", [fm], process_step=f"Step{i}")
            for i, fm in enumerate(fms, start=1)
        ]
    )

    dataset = build_control_plan(fmea)

    assert len(dataset.rows) == 5
    characteristics = {r.characteristic for r in dataset.rows}
    assert len(characteristics) == 5
    assert characteristics == {
        "Bracket — weld",
        "Bracket — weld (M1)",
        "Bracket — weld (M1) #2",
        "Bracket — weld (M1) #3",
        "Bracket — weld (M1) #4",
    }


# --- recommend_chart ---------------------------------------------------------


@pytest.mark.parametrize(
    ("data_type", "n", "kwargs", "expected"),
    [
        ("variable", 1, {}, "I-MR"),
        ("variable", 2, {}, "Xbar-R"),
        ("variable", 5, {}, "Xbar-R"),
        ("variable", 9, {}, "Xbar-R"),
        ("variable", 10, {}, "Xbar-S"),
        ("variable", 12, {}, "Xbar-S"),
        ("attribute", 5, {"defect_based": False, "constant_sample": True}, "p"),
        ("attribute", 5, {"defect_based": False, "constant_sample": False}, "p"),
        ("attribute", 5, {"defect_based": True, "constant_sample": True}, "c"),
        ("attribute", 5, {"defect_based": True, "constant_sample": False}, "u"),
        ("attribute", 5, {}, "p"),
    ],
)
def test_recommend_chart_rule_table_every_cell(data_type, n, kwargs, expected) -> None:
    assert recommend_chart(data_type, n, **kwargs) == expected


def test_recommend_chart_boundary_nine_is_xbar_r_and_ten_is_xbar_s() -> None:
    assert recommend_chart("variable", 9) == "Xbar-R"
    assert recommend_chart("variable", 10) == "Xbar-S"


@pytest.mark.parametrize("subgroup_size", [0, -1, -100])
def test_recommend_chart_rejects_invalid_subgroup_size(subgroup_size: int) -> None:
    with pytest.raises(ValueError, match="subgroup_size"):
        recommend_chart("variable", subgroup_size)


def test_recommend_chart_ceiling_is_the_xbar_s_constants_table_max() -> None:
    assert _MAX_XBAR_S_N == max(XBAR_S_CONSTANTS) == 12


def test_recommend_chart_variable_at_ceiling_returns_xbar_s() -> None:
    assert recommend_chart("variable", _MAX_XBAR_S_N) == "Xbar-S"


def test_recommend_chart_rejects_subgroup_size_above_xbar_s_ceiling() -> None:
    with pytest.raises(ValueError, match="exceeds the largest supported") as exc:
        recommend_chart("variable", _MAX_XBAR_S_N + 1)
    message = str(exc.value)
    assert "12" in message
    assert "13" in message
    assert "A3/B3/B4/c4" in message


# --- source_index & _source_cause_id -----------------------------------------


def test_source_index_empty_fmea_yields_empty_dict() -> None:
    assert source_index(RelationalFMEA(functions=[])) == {}


def test_source_index_single_mode_matches_worst_link_cause() -> None:
    fm = _fm(
        "F1-M1",
        "Incomplete weld",
        s=9,
        o=7,
        d=8,
        row_id=1,
        cause_desc="Contaminated joint surface",
    )
    fmea = RelationalFMEA(functions=[_function("F1", "Bracket", [fm])])

    dataset = build_control_plan(fmea)
    index = source_index(fmea)

    assert len(dataset.rows) == 1
    row = dataset.rows[0]
    assert set(index) == {row.characteristic}

    entry = index[row.characteristic]
    assert entry == {
        "failure_mode_id": "F1-M1",
        "cause_id": "F1::F1-M1::F1-M1-C1",
        "cause_description": "Contaminated joint surface",
        "occurrence": 7,
        "component": "Bracket",
    }
    assert row.source_cause_id == entry["cause_id"]


def test_source_cause_id_is_unique_across_causes_with_same_local_id() -> None:
    cause1 = Cause(id="C1", description="Cause in mode 1", occurrence=5)
    cause2 = Cause(id="C1", description="Cause in mode 2", occurrence=6)
    function = _function(
        "F1",
        "Comp",
        [
            FailureMode(
                id="M1",
                description="Mode 1",
                effects=[Effect(id="M1-E1", description="Effect", severity=5)],
                causes=[cause1],
                controls=[Control(id="M1-CT1", description="Control", detection=5)],
                links=[FailureLink(row_id=1, effect_id="M1-E1", cause_id="C1", control_id="M1-CT1")],
            ),
            FailureMode(
                id="M2",
                description="Mode 2",
                effects=[Effect(id="M2-E1", description="Effect", severity=5)],
                causes=[cause2],
                controls=[Control(id="M2-CT1", description="Control", detection=5)],
                links=[FailureLink(row_id=2, effect_id="M2-E1", cause_id="C1", control_id="M2-CT1")],
            ),
        ],
    )
    fmea = RelationalFMEA(functions=[function])

    id1 = _source_cause_id(function, function.failure_modes[0], cause1)
    id2 = _source_cause_id(function, function.failure_modes[1], cause2)
    assert id1 != id2
    assert id1 == "F1::M1::C1"
    assert id2 == "F1::M2::C1"

    index = source_index(fmea)
    cause_ids = {entry["cause_id"] for entry in index.values()}
    assert len(cause_ids) == 2

"""
Tests for quality_core.controlplan.schema.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pydantic
import pytest
from quality_core.controlplan.schema import (
    CONTROL_PLAN_SCHEMA,
    ControlPlanDataset,
    ControlPlanRow,
    IngestError,
    load_control_plan_csv,
    validate_control_plan,
)

TEMPLATE_PATH = Path(__file__).resolve().parent / "data" / "control_plan_template.csv"

GOOD_ROW_KWARGS = dict(
    characteristic="Bore Diameter",
    measurement_method="Bore gauge",
    sample_size=5,
    frequency="per shift",
    reaction_plan="Stop line; notify quality engineer.",
)


def _csv(rows, name: str = "upload.csv") -> io.BytesIO:
    buf = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode())
    buf.name = name
    return buf


def _good_csv_row() -> dict:
    return {
        "characteristic": "Bore Diameter",
        "measurement_method": "Bore gauge",
        "sample_size": 5,
        "frequency": "per shift",
        "reaction_plan": "Stop line; notify quality engineer.",
    }


def test_required_columns_are_the_five_always_required_fields() -> None:
    assert CONTROL_PLAN_SCHEMA.required_columns == (
        "characteristic",
        "measurement_method",
        "sample_size",
        "frequency",
        "reaction_plan",
    )


def test_ingest_error_is_value_error() -> None:
    assert issubclass(IngestError, ValueError)


def test_row_valid_full_tolerance_and_chart() -> None:
    row = ControlPlanRow(
        lsl=24.90, usl=25.10, target=25.00, recommended_chart="Xbar-R", **GOOD_ROW_KWARGS
    )
    assert row.lsl == 24.90
    assert row.usl == 25.10
    assert row.recommended_chart == "Xbar-R"


def test_row_usl_equal_to_lsl_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="usl must be greater than lsl"):
        ControlPlanRow(lsl=25.0, usl=25.0, **GOOD_ROW_KWARGS)


def test_row_usl_below_lsl_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="usl must be greater than lsl"):
        ControlPlanRow(lsl=25.0, usl=24.0, **GOOD_ROW_KWARGS)


def test_row_target_below_lsl_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="target must be within"):
        ControlPlanRow(lsl=25.0, usl=26.0, target=24.0, **GOOD_ROW_KWARGS)


def test_row_target_above_usl_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="target must be within"):
        ControlPlanRow(lsl=25.0, usl=26.0, target=27.0, **GOOD_ROW_KWARGS)


def test_row_target_at_bounds_accepted() -> None:
    assert ControlPlanRow(lsl=25.0, usl=26.0, target=25.0, **GOOD_ROW_KWARGS).target == 25.0
    assert ControlPlanRow(lsl=25.0, usl=26.0, target=26.0, **GOOD_ROW_KWARGS).target == 26.0


def test_row_one_sided_spec_lsl_only_accepted() -> None:
    row = ControlPlanRow(lsl=24.90, **GOOD_ROW_KWARGS)
    assert row.lsl == 24.90
    assert row.usl is None


def test_row_one_sided_spec_usl_only_accepted() -> None:
    row = ControlPlanRow(usl=3.2, **GOOD_ROW_KWARGS)
    assert row.usl == 3.2
    assert row.lsl is None


def test_row_target_without_bounds_accepted() -> None:
    row = ControlPlanRow(target=25.0, **GOOD_ROW_KWARGS)
    assert row.target == 25.0


def test_row_optional_fields_default_to_none() -> None:
    row = ControlPlanRow(**GOOD_ROW_KWARGS)
    assert row.lsl is None
    assert row.usl is None
    assert row.target is None
    assert row.recommended_chart is None
    assert row.source_cause_id is None


def test_row_source_cause_id_round_trips() -> None:
    row = ControlPlanRow(source_cause_id="F1::F1-M1::F1-M1-C1", **GOOD_ROW_KWARGS)
    assert row.source_cause_id == "F1::F1-M1::F1-M1-C1"


def test_row_source_cause_id_blank_coerced_to_none() -> None:
    row = ControlPlanRow(source_cause_id="   ", **GOOD_ROW_KWARGS)
    assert row.source_cause_id is None


def test_row_source_cause_id_stripped() -> None:
    row = ControlPlanRow(source_cause_id="  F1::F1-M1::F1-M1-C1  ", **GOOD_ROW_KWARGS)
    assert row.source_cause_id == "F1::F1-M1::F1-M1-C1"


def test_row_source_cause_id_none_passes_through() -> None:
    row = ControlPlanRow(source_cause_id=None, **GOOD_ROW_KWARGS)
    assert row.source_cause_id is None


def test_row_recommended_chart_accepts_every_spc_chart_key() -> None:
    for chart in ("Xbar-R", "Xbar-S", "I-MR", "p", "c", "u"):
        assert ControlPlanRow(recommended_chart=chart, **GOOD_ROW_KWARGS).recommended_chart == chart


def test_row_recommended_chart_none_accepted() -> None:
    assert ControlPlanRow(recommended_chart=None, **GOOD_ROW_KWARGS).recommended_chart is None


def test_row_recommended_chart_unknown_string_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="recommended_chart"):
        ControlPlanRow(recommended_chart="Bogus-Chart", **GOOD_ROW_KWARGS)


def test_row_lsl_infinite_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="lsl"):
        ControlPlanRow(lsl=float("inf"), **GOOD_ROW_KWARGS)


def test_row_usl_infinite_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="usl"):
        ControlPlanRow(usl=float("-inf"), **GOOD_ROW_KWARGS)


def test_row_target_infinite_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="target"):
        ControlPlanRow(target=float("nan"), **GOOD_ROW_KWARGS)


def test_row_float_field_coerces_numeric_string() -> None:
    row = ControlPlanRow(lsl="24.90", **GOOD_ROW_KWARGS)
    assert row.lsl == 24.90


def test_row_characteristic_blank_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["characteristic"] = "   "
    with pytest.raises(pydantic.ValidationError, match="characteristic"):
        ControlPlanRow(**kwargs)


def test_row_measurement_method_blank_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["measurement_method"] = ""
    with pytest.raises(pydantic.ValidationError, match="measurement_method"):
        ControlPlanRow(**kwargs)


def test_row_frequency_blank_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["frequency"] = "\t"
    with pytest.raises(pydantic.ValidationError, match="frequency"):
        ControlPlanRow(**kwargs)


def test_row_reaction_plan_blank_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["reaction_plan"] = "  \n  "
    with pytest.raises(pydantic.ValidationError, match="reaction_plan"):
        ControlPlanRow(**kwargs)


def test_row_string_fields_are_stripped() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["characteristic"] = "  Bore Diameter  "
    row = ControlPlanRow(**kwargs)
    assert row.characteristic == "Bore Diameter"


def test_row_non_string_characteristic_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["characteristic"] = 123
    with pytest.raises(pydantic.ValidationError, match="characteristic"):
        ControlPlanRow(**kwargs)


def test_row_sample_size_below_one_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["sample_size"] = 0
    with pytest.raises(pydantic.ValidationError, match="sample_size"):
        ControlPlanRow(**kwargs)


def test_row_sample_size_non_integer_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["sample_size"] = 1.5
    with pytest.raises(pydantic.ValidationError, match="sample_size"):
        ControlPlanRow(**kwargs)


def test_row_sample_size_coerces_numeric_string() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["sample_size"] = "5"
    assert ControlPlanRow(**kwargs).sample_size == 5


def test_row_characteristic_too_long_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["characteristic"] = "x" * 201
    with pytest.raises(pydantic.ValidationError, match="characteristic"):
        ControlPlanRow(**kwargs)


def test_row_reaction_plan_too_long_rejected() -> None:
    kwargs = dict(GOOD_ROW_KWARGS)
    kwargs["reaction_plan"] = "x" * 2001
    with pytest.raises(pydantic.ValidationError, match="reaction_plan"):
        ControlPlanRow(**kwargs)


def test_dataset_accepts_unique_characteristics() -> None:
    ds = ControlPlanDataset(
        rows=[
            ControlPlanRow(**GOOD_ROW_KWARGS),
            ControlPlanRow(**{**GOOD_ROW_KWARGS, "characteristic": "Surface Finish"}),
        ]
    )
    assert len(ds.rows) == 2


def test_dataset_rejects_duplicate_characteristic() -> None:
    with pytest.raises(pydantic.ValidationError, match="duplicate characteristic"):
        ControlPlanDataset(
            rows=[
                ControlPlanRow(**GOOD_ROW_KWARGS),
                ControlPlanRow(**GOOD_ROW_KWARGS),
            ]
        )


def test_dataset_accepts_empty_rows() -> None:
    assert ControlPlanDataset(rows=[]).rows == []


def test_valid_upload_passes_and_returns_frame() -> None:
    out = load_control_plan_csv(_csv([_good_csv_row()]))
    assert len(out) == 1
    assert list(out["characteristic"]) == ["Bore Diameter"]


def test_template_validates_as_the_documented_shape() -> None:
    out = load_control_plan_csv(str(TEMPLATE_PATH))
    assert len(out) == 3
    assert sorted(out["characteristic"]) == [
        "Bore Diameter",
        "Surface Finish",
        "Visual Inspection",
    ]


def test_placeholder_flag_defaults_to_false() -> None:
    assert ControlPlanRow(**GOOD_ROW_KWARGS).sample_plan_is_placeholder is False


@pytest.mark.parametrize("blank", [None, "", "   ", "\t\n"])
def test_placeholder_flag_missing_or_blank_coerces_to_false(blank: object) -> None:
    row = ControlPlanRow(**GOOD_ROW_KWARGS, sample_plan_is_placeholder=blank)
    assert row.sample_plan_is_placeholder is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("True", True), (1, True), ("false", False), ("False", False), (0, False)],
)
def test_placeholder_flag_non_blank_values_pass_through_to_coercion(
    raw: object, expected: bool
) -> None:
    row = ControlPlanRow(**GOOD_ROW_KWARGS, sample_plan_is_placeholder=raw)
    assert row.sample_plan_is_placeholder is expected


def test_placeholder_flag_rejects_uninterpretable_value() -> None:
    with pytest.raises(pydantic.ValidationError):
        ControlPlanRow(**GOOD_ROW_KWARGS, sample_plan_is_placeholder="maybe")


# --- validate_control_plan ---------------------------------------------------


def test_validate_control_plan_passes_dataset_through() -> None:
    ds = ControlPlanDataset(rows=[ControlPlanRow(**GOOD_ROW_KWARGS)])
    assert validate_control_plan(ds) is ds


def test_validate_control_plan_from_dataframe() -> None:
    df = pd.DataFrame([_good_csv_row()])
    ds = validate_control_plan(df)
    assert len(ds.rows) == 1
    assert ds.rows[0].characteristic == "Bore Diameter"


def test_validate_control_plan_from_list_of_dicts() -> None:
    ds = validate_control_plan([_good_csv_row()])
    assert len(ds.rows) == 1
    assert ds.rows[0].characteristic == "Bore Diameter"


def test_validate_control_plan_from_list_of_rows() -> None:
    row = ControlPlanRow(**GOOD_ROW_KWARGS)
    ds = validate_control_plan([row])
    assert len(ds.rows) == 1
    assert ds.rows[0] is row


def test_validate_control_plan_rejects_invalid_list_item() -> None:
    with pytest.raises(TypeError, match="Expected ControlPlanRow or dict"):
        validate_control_plan(["not a dict"])


def test_validate_control_plan_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Expected ControlPlanDataset, DataFrame"):
        validate_control_plan(12345)

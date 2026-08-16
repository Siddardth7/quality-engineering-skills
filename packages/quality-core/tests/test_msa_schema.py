"""Tests for quality_core/msa/schema.py — validated gage-study upload ingest (W08-1).

Drives the page-facing load_gage_study_csv (read + validate via the shared
quality_core.io boundary) with in-memory CSVs, asserting valid crossed uploads
pass and malformed ones raise a friendly, row-addressed IngestError. The bundled
template — the documented upload shape — must itself validate.
"""

from __future__ import annotations

import io
import warnings
from pathlib import Path

import pandas as pd
import pytest
from quality_core.io import validate_table
from quality_core.msa.gage_rr import compute_gage_rr
from quality_core.msa.schema import GAGE_STUDY_SCHEMA, IngestError, load_gage_study_csv

TEMPLATE_PATH = Path(__file__).resolve().parent / "data" / "gage_rr_template.csv"

GOOD_ROWS = [
    {"part": "P01", "appraiser": "A", "trial": 1, "measurement": 10.054},
    {"part": "P01", "appraiser": "A", "trial": 2, "measurement": 10.048},
    {"part": "P01", "appraiser": "B", "trial": 1, "measurement": 10.057},
]


def _csv(rows: list[dict[str, object]], name: str = "upload.csv") -> io.BytesIO:
    buf = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode())
    buf.name = name
    return buf


def _csv_from_frame(frame: pd.DataFrame, name: str = "upload.csv") -> io.BytesIO:
    buf = io.BytesIO(frame.to_csv(index=False).encode())
    buf.name = name
    return buf


# --- schema wiring -----------------------------------------------------------


def test_required_columns_are_the_four_gage_fields() -> None:
    assert GAGE_STUDY_SCHEMA.required_columns == (
        "part",
        "appraiser",
        "trial",
        "measurement",
    )


def test_ingest_error_is_value_error() -> None:
    assert issubclass(IngestError, ValueError)


# --- happy paths -------------------------------------------------------------


def test_valid_upload_passes_and_returns_frame() -> None:
    out = load_gage_study_csv(_csv(GOOD_ROWS))
    assert len(out) == 3
    assert list(out["part"].unique()) == ["P01"]


def test_template_validates_as_the_documented_shape() -> None:
    # The bundled template is the documented upload shape (5 parts x 3 appraisers
    # x 3 trials = 45 rows), so it must pass the schema unchanged — guards against drift.
    out = load_gage_study_csv(str(TEMPLATE_PATH))
    assert len(out) == 45
    assert sorted(out["part"].unique()) == ["P01", "P02", "P03", "P04", "P05"]
    assert sorted(out["appraiser"].unique()) == ["A", "B", "C"]
    assert sorted(out["trial"].unique()) == [1, 2, 3]


def test_numeric_only_labels_are_rejected_row_addressed() -> None:
    # A wholly-numeric part/appraiser column arrives from pandas as ints, not str.
    # The before-validator passes the non-str value through (exercising its else
    # branch); pydantic's str field then rejects it in lax mode (no int->str coercion),
    # so a numeric-only label ID is a friendly, row-addressed IngestError. This mirrors
    # SPC's `stream` (str) behaviour and is a documented limitation, not a crash.
    rows: list[dict[str, object]] = [{"part": 1, "appraiser": 7, "trial": 1, "measurement": 10.0}]
    with pytest.raises(IngestError) as exc:
        load_gage_study_csv(_csv(rows))
    assert "part" in str(exc.value)


def test_labels_with_surrounding_whitespace_accepted() -> None:
    rows = [{"part": " P01 ", "appraiser": " A ", "trial": 1, "measurement": 10.0}]
    assert len(load_gage_study_csv(_csv(rows))) == 1


# --- malformed paths ---------------------------------------------------------


def test_blank_part_rejected() -> None:
    rows = [{"part": "  ", "appraiser": "A", "trial": 1, "measurement": 10.0}]
    with pytest.raises(IngestError, match="part"):
        load_gage_study_csv(_csv(rows))


def test_blank_appraiser_rejected() -> None:
    rows = [{"part": "P01", "appraiser": "   ", "trial": 1, "measurement": 10.0}]
    with pytest.raises(IngestError, match="appraiser"):
        load_gage_study_csv(_csv(rows))


def test_non_numeric_measurement_is_row_addressed() -> None:
    rows: list[dict[str, object]] = [
        {"part": "P01", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P01", "appraiser": "A", "trial": 2, "measurement": "oops"},
    ]
    with pytest.raises(IngestError) as exc:
        load_gage_study_csv(_csv(rows))
    msg = str(exc.value)
    assert "Row 3" in msg  # header is row 1
    assert "measurement" in msg


def test_infinite_measurement_rejected() -> None:
    rows = [{"part": "P01", "appraiser": "A", "trial": 1, "measurement": float("inf")}]
    with pytest.raises(IngestError) as exc:
        load_gage_study_csv(_csv(rows))
    assert "measurement" in str(exc.value)


def test_blank_measurement_is_addressed_not_nan() -> None:
    rows = [{"part": "P01", "appraiser": "A", "trial": 1, "measurement": float("nan")}]
    with pytest.raises(IngestError) as exc:
        load_gage_study_csv(_csv(rows))
    msg = str(exc.value)
    assert "measurement" in msg
    assert "nan" not in msg.lower()  # NaN normalised to None, not echoed as "nan"


def test_trial_below_one_rejected() -> None:
    rows = [{"part": "P01", "appraiser": "A", "trial": 0, "measurement": 10.0}]
    with pytest.raises(IngestError, match="trial"):
        load_gage_study_csv(_csv(rows))


def test_non_integer_trial_rejected() -> None:
    rows: list[dict[str, object]] = [{"part": "P01", "appraiser": "A", "trial": 1.5, "measurement": 10.0}]
    with pytest.raises(IngestError, match="trial"):
        load_gage_study_csv(_csv(rows))


def test_missing_required_column_is_friendly() -> None:
    rows: list[dict[str, object]] = [{"part": "P01", "appraiser": "A", "trial": 1}]  # no measurement
    with pytest.raises(IngestError, match=r"Missing required column\(s\): \['measurement'\]"):
        load_gage_study_csv(_csv(rows))


def test_empty_upload_is_friendly() -> None:
    empty = pd.DataFrame(columns=["part", "appraiser", "trial", "measurement"])
    with pytest.raises(IngestError, match="at least one"):
        load_gage_study_csv(_csv_from_frame(empty))


# --- #200: narrowed return, and the copy the R&R math depends on --------------


def test_schema_declares_no_optional_columns() -> None:
    assert GAGE_STUDY_SCHEMA.optional_columns == ()


def test_extra_column_is_dropped_leaving_exactly_the_four_validated_ones() -> None:
    rows = [{**r, "operator_notes": "n/a", "Unnamed: 0": i} for i, r in enumerate(GOOD_ROWS)]
    out = load_gage_study_csv(_csv(rows))
    assert list(out.columns) == ["part", "appraiser", "trial", "measurement"]


def test_gage_rr_over_a_loaded_frame_runs_without_a_pandas_copy_warning() -> None:
    # gage_rr assigns `df["measurement"] = ...` straight into the frame the
    # loader returns, so that assignment must stay warning-free on the narrowed
    # frame. `simplefilter("error")` turns any pandas warning into a failure.
    rows = [
        {"part": p, "appraiser": a, "trial": t, "measurement": 10.0 + i * 0.01}
        for i, (p, a, t) in enumerate(
            (p, a, t)
            for p in ("P01", "P02", "P03")
            for a in ("A", "B")
            for t in (1, 2)
        )
    ]
    # An extra column makes the returned frame a strict projection of the parsed one.
    loaded = load_gage_study_csv(_csv([{**r, "operator_notes": "x"} for r in rows]))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = compute_gage_rr(loaded)
    assert result["pgrr_study"] >= 0


def test_mutating_the_validated_frame_does_not_touch_the_caller_s_frame() -> None:
    # Drives validate_table with ONE input frame we still hold a reference to: a
    # re-parsed second frame would be unchanged even if validate_table returned the
    # caller's object, so it proves nothing about the copy.
    source = pd.DataFrame([{**r, "operator_notes": "x"} for r in GOOD_ROWS])
    validated = validate_table(source, GAGE_STUDY_SCHEMA)
    validated.loc[0, "measurement"] = 999.0
    assert source.loc[0, "measurement"] == GOOD_ROWS[0]["measurement"]


def test_duplicate_triple_rejected() -> None:
    rows = [
        {"part": "P01", "appraiser": "A", "trial": 1, "measurement": 10.0},
        {"part": "P01", "appraiser": "A", "trial": 1, "measurement": 10.2},  # same triple
    ]
    with pytest.raises(IngestError, match=r"duplicate \(part, appraiser, trial\)"):
        load_gage_study_csv(_csv(rows))

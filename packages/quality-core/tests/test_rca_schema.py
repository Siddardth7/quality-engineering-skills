"""
Tests for quality_core.rca.schema and quality_core.rca module exports.

Covers:
- 5-Why domain models, validation, consecutive step checks, CSV loading, and boundary validation
- 6M Fishbone domain models, category normalization/aliases, CSV loading, and boundary validation
- Kepner-Tregoe Is/Is-Not domain models, 4-dimension validation, completeness, CSV loading, and boundary validation
- Negative controls and error boundaries
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd
import pydantic
import pytest
import quality_core.rca as rca
from quality_core.rca import (
    FISHBONE_SCHEMA,
    FIVE_WHY_SCHEMA,
    IS_IS_NOT_SCHEMA,
    Category6M,
    FishboneCause,
    FishboneDataset,
    FiveWhyChain,
    FiveWhyStep,
    IngestError,
    IsIsNotMatrix,
    IsIsNotRow,
    KTDimension,
    load_fishbone_csv,
    load_five_why_csv,
    load_is_is_not_csv,
    validate_fishbone,
    validate_five_why,
    validate_is_is_not,
)
from quality_core.rca.schema import (
    CATEGORY_6M_ALIASES,
    CATEGORY_6M_VALUES,
    KT_DIMENSIONS,
)

# ==============================================================================
# Helper functions
# ==============================================================================


def _csv_buf(rows: list[dict[str, Any]], name: str = "upload.csv") -> io.BytesIO:
    buf = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode("utf-8"))
    buf.name = name
    return buf


# ==============================================================================
# 0. Module exports & IngestError tests
# ==============================================================================


def test_rca_module_all_exports() -> None:
    expected_exports = {
        # 8D
        "CONTAINMENT_ACTION_SCHEMA",
        "CORRECTIVE_ACTION_CANDIDATE_SCHEMA",
        "CandidateCauseTest",
        "ContainmentAction",
        "ContainmentActionList",
        "CorrectiveActionCandidate",
        "CorrectiveActionCandidateList",
        "D0Discipline",
        "D1Discipline",
        "D2Discipline",
        "D3Discipline",
        "D4Discipline",
        "D5Discipline",
        "D6Discipline",
        "D7Discipline",
        "D8Discipline",
        "DOCUMENTATION_UPDATE_SCHEMA",
        "DocumentationUpdate",
        "DocumentationUpdateList",
        "EffectivenessVerification",
        "EightDReport",
        "EightDStatus",
        "EscapePointFinding",
        "FiveWhyLegType",
        "FiveWhyVerdict",
        "ImplementedAction",
        "RootCauseFinding",
        "TEAM_MEMBER_SCHEMA",
        "TeamMember",
        "TeamMemberList",
        "WarningOverride",
        "load_containment_actions_csv",
        "load_corrective_action_candidates_csv",
        "load_documentation_updates_csv",
        "load_eight_d_json",
        "load_eight_d_json_from_path",
        "load_team_members_csv",
        "validate_containment_actions",
        "validate_corrective_action_candidates",
        "validate_documentation_updates",
        "validate_eight_d",
        "validate_team_members",
        # 5-Why
        "AntiPatternFinding",
        "FIVE_WHY_COLUMN_WIDTHS",
        "FIVE_WHY_EXPORT_COLUMNS",
        "FIVE_WHY_SCHEMA",
        "FIVE_WHY_SHEET_TITLE",
        "FiveWhyChain",
        "FiveWhyLinkEval",
        "FiveWhyStep",
        "FiveWhyValidationResult",
        "SystemicAssessment",
        "benchmark_five_why_chain",
        "export_five_why_workbook",
        "load_five_why_csv",
        "validate_five_why",
        "validate_five_why_chain",
        # Fishbone
        "Category6M",
        "FISHBONE_COLUMN_WIDTHS",
        "FISHBONE_EXPORT_COLUMNS",
        "FISHBONE_SCHEMA",
        "FISHBONE_SHEET_TITLE",
        "FishboneCategorizationResult",
        "FishboneCause",
        "FishboneDataset",
        "benchmark_fishbone_dataset",
        "categorize_fishbone",
        "export_fishbone_workbook",
        "load_fishbone_csv",
        "validate_fishbone",
        # Is/Is-Not
        "CandidateCause",
        "IS_IS_NOT_COLUMN_WIDTHS",
        "IS_IS_NOT_EXPORT_COLUMNS",
        "IS_IS_NOT_SCHEMA",
        "IS_IS_NOT_SHEET_TITLE",
        "IsIsNotMatrix",
        "IsIsNotRow",
        "IsIsNotScopingResult",
        "KTDimension",
        "benchmark_is_is_not_matrix",
        "export_is_is_not_workbook",
        "load_is_is_not_csv",
        "scope_is_is_not",
        "validate_is_is_not",
        # Combined RCA Exporters & Benchmarks
        "benchmark_rca_datasets",
        "build_rca_workbook",
        "export_rca_workbook",
        # Error
        "IngestError",
    }

    assert set(rca.__all__) == expected_exports
    for symbol in expected_exports:
        assert hasattr(rca, symbol)


def test_ingest_error_is_subclass_of_value_error() -> None:
    assert issubclass(IngestError, ValueError)


def test_constants_and_taxonomies() -> None:
    assert CATEGORY_6M_VALUES == (
        "Man",
        "Machine",
        "Method",
        "Material",
        "Measurement",
        "Environment",
    )
    assert KT_DIMENSIONS == ("WHAT", "WHERE", "WHEN", "EXTENT")


# ==============================================================================
# 1. 5-Why Problem Solving Suite
# ==============================================================================


def test_five_why_step_valid() -> None:
    step = FiveWhyStep(step_number=1, why="Motor stopped", because="Fuse blew")
    assert step.step_number == 1
    assert step.why == "Motor stopped"
    assert step.because == "Fuse blew"


def test_five_why_step_whitespace_stripping() -> None:
    step = FiveWhyStep(
        step_number=1,
        why="  Motor stopped  \t",
        because="  Fuse blew \n ",
    )
    assert step.why == "Motor stopped"
    assert step.because == "Fuse blew"


def test_five_why_step_rejects_blank_why() -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        FiveWhyStep(step_number=1, why="   ", because="Valid explanation")


def test_five_why_step_rejects_blank_because() -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        FiveWhyStep(step_number=1, why="Valid why", because="\t\n")


def test_five_why_step_rejects_step_number_less_than_one() -> None:
    with pytest.raises(pydantic.ValidationError):
        FiveWhyStep(step_number=0, why="Why", because="Because")

    with pytest.raises(pydantic.ValidationError):
        FiveWhyStep(step_number=-2, why="Why", because="Because")


def test_five_why_step_rejects_non_integer_step_number() -> None:
    with pytest.raises(pydantic.ValidationError):
        FiveWhyStep(step_number="invalid", why="Why", because="Because")  # type: ignore[arg-type]


def test_five_why_step_field_length_bounds() -> None:
    long_text = "x" * 2001
    with pytest.raises(pydantic.ValidationError):
        FiveWhyStep(step_number=1, why=long_text, because="Valid")
    with pytest.raises(pydantic.ValidationError):
        FiveWhyStep(step_number=1, why="Valid", because=long_text)


def test_five_why_chain_valid_single_step() -> None:
    chain = FiveWhyChain(
        problem_statement="Pump overheating",
        steps=[FiveWhyStep(step_number=1, why="Why stopped?", because="Thermal trip")],
        root_cause="Thermal trip",
    )
    assert chain.problem_statement == "Pump overheating"
    assert len(chain.steps) == 1
    assert chain.rows == chain.steps
    assert chain.root_cause == "Thermal trip"


def test_five_why_chain_valid_multi_step() -> None:
    steps = [
        FiveWhyStep(step_number=1, why="Machine stopped", because="Overload"),
        FiveWhyStep(step_number=2, why="Why overload?", because="Bearing seized"),
        FiveWhyStep(step_number=3, why="Why seized?", because="No lubrication"),
        FiveWhyStep(step_number=4, why="Why no lube?", because="Pump worn"),
        FiveWhyStep(step_number=5, why="Why pump worn?", because="Filter clogged"),
    ]
    chain = FiveWhyChain(
        problem_statement="Machine shutdown",
        steps=steps,
        root_cause="Filter clogged",
    )
    assert len(chain.steps) == 5
    assert chain.steps[4].because == "Filter clogged"


def test_five_why_chain_default_fields() -> None:
    chain = FiveWhyChain(
        steps=[FiveWhyStep(step_number=1, why="Why", because="Because")]
    )
    assert chain.problem_statement == "Problem Statement"
    assert chain.root_cause is None


def test_five_why_chain_whitespace_stripping_and_blank_rejection() -> None:
    chain = FiveWhyChain(
        problem_statement="  Pump issue  ",
        steps=[FiveWhyStep(step_number=1, why="Why", because="Because")],
        root_cause="  Root cause  ",
    )
    assert chain.problem_statement == "Pump issue"
    assert chain.root_cause == "Root cause"

    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        FiveWhyChain(
            problem_statement="   ",
            steps=[FiveWhyStep(step_number=1, why="Why", because="Because")],
        )

    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        FiveWhyChain(
            problem_statement="Valid",
            steps=[FiveWhyStep(step_number=1, why="Why", because="Because")],
            root_cause="   ",
        )


def test_five_why_chain_rejects_empty_steps() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one step"):
        FiveWhyChain(steps=[])


def test_five_why_chain_rejects_duplicate_step_numbers() -> None:
    steps = [
        FiveWhyStep(step_number=1, why="Why 1", because="Because 1"),
        FiveWhyStep(step_number=1, why="Why 2", because="Because 2"),
    ]
    with pytest.raises(pydantic.ValidationError, match="duplicate step numbers"):
        FiveWhyChain(steps=steps)


def test_five_why_chain_rejects_non_consecutive_step_numbers() -> None:
    steps = [
        FiveWhyStep(step_number=1, why="Why 1", because="Because 1"),
        FiveWhyStep(step_number=3, why="Why 3", because="Because 3"),
    ]
    with pytest.raises(pydantic.ValidationError, match="consecutive integers starting from 1"):
        FiveWhyChain(steps=steps)


def test_five_why_chain_rejects_out_of_order_step_numbers() -> None:
    steps = [
        FiveWhyStep(step_number=2, why="Why 2", because="Because 2"),
        FiveWhyStep(step_number=1, why="Why 1", because="Because 1"),
    ]
    with pytest.raises(pydantic.ValidationError, match="consecutive integers starting from 1"):
        FiveWhyChain(steps=steps)


def test_five_why_chain_coerces_rows_to_steps_in_dict() -> None:
    data = {
        "problem_statement": "Issue",
        "rows": [{"step_number": 1, "why": "Why", "because": "Because"}],
    }
    chain = FiveWhyChain.model_validate(data)
    assert len(chain.steps) == 1
    assert chain.steps[0].why == "Why"


def test_five_why_schema_properties() -> None:
    assert FIVE_WHY_SCHEMA.name == "5-Why"
    assert FIVE_WHY_SCHEMA.required_columns == ("step_number", "why", "because")
    assert FIVE_WHY_SCHEMA.optional_columns == ()
    assert FIVE_WHY_SCHEMA.row_model is FiveWhyStep
    assert FIVE_WHY_SCHEMA.dataset_model is FiveWhyChain
    assert FIVE_WHY_SCHEMA.template_hint == "data/five_why_template.csv"


def test_load_five_why_csv_from_buffer() -> None:
    rows = [
        {"step_number": 1, "why": "Why 1", "because": "Because 1"},
        {"step_number": 2, "why": "Why 2", "because": "Because 2"},
    ]
    buf = _csv_buf(rows)
    df = load_five_why_csv(buf)
    assert len(df) == 2
    assert list(df.columns) == ["step_number", "why", "because"]
    assert df["step_number"].tolist() == [1, 2]


def test_load_five_why_csv_from_path(tmp_path: Path) -> None:
    file_path = tmp_path / "test_five_why.csv"
    df_in = pd.DataFrame(
        [
            {"step_number": 1, "why": "Why 1", "because": "Because 1", "extra": "ignored"},
            {"step_number": 2, "why": "Why 2", "because": "Because 2", "extra": "ignored"},
        ]
    )
    df_in.to_csv(file_path, index=False)
    df_out = load_five_why_csv(str(file_path))
    assert len(df_out) == 2
    assert list(df_out.columns) == ["step_number", "why", "because"]


def test_load_five_why_csv_missing_required_column_raises_ingest_error() -> None:
    rows = [{"step_number": 1, "why": "Why 1"}]  # missing "because"
    buf = _csv_buf(rows)
    with pytest.raises(IngestError, match="Missing required column"):
        load_five_why_csv(buf)


def test_load_five_why_csv_empty_raises_ingest_error() -> None:
    buf = io.BytesIO(b"step_number,why,because\n")
    buf.name = "empty.csv"
    with pytest.raises(IngestError, match="No data rows found"):
        load_five_why_csv(buf)


def test_validate_five_why_from_chain_passthrough() -> None:
    chain = FiveWhyChain(
        steps=[FiveWhyStep(step_number=1, why="Why", because="Because")]
    )
    validated = validate_five_why(chain)
    assert validated is chain


def test_validate_five_why_from_dataframe() -> None:
    df = pd.DataFrame(
        [
            {"step_number": 1, "why": "Why 1", "because": "Because 1"},
            {"step_number": 2, "why": "Why 2", "because": "Because 2"},
        ]
    )
    chain = validate_five_why(df, problem_statement="Custom Issue", root_cause="Because 2")
    assert chain.problem_statement == "Custom Issue"
    assert chain.root_cause == "Because 2"
    assert len(chain.steps) == 2


def test_validate_five_why_from_list_of_steps() -> None:
    steps = [
        FiveWhyStep(step_number=1, why="Why 1", because="Because 1"),
        FiveWhyStep(step_number=2, why="Why 2", because="Because 2"),
    ]
    chain = validate_five_why(steps, problem_statement="List Test")
    assert len(chain.steps) == 2
    assert chain.steps[0] is steps[0]


def test_validate_five_why_from_list_of_dicts() -> None:
    records = [
        {"step_number": 1, "why": "Why 1", "because": "Because 1"},
        {"step_number": 2, "why": "Why 2", "because": "Because 2"},
    ]
    chain = validate_five_why(records)
    assert len(chain.steps) == 2
    assert chain.steps[0].why == "Why 1"


def test_validate_five_why_from_dict() -> None:
    data = {
        "problem_statement": "Dict problem",
        "steps": [{"step_number": 1, "why": "Why", "because": "Because"}],
        "root_cause": "Because",
    }
    chain = validate_five_why(data)
    assert chain.problem_statement == "Dict problem"
    assert chain.root_cause == "Because"
    assert len(chain.steps) == 1


def test_validate_five_why_rejects_invalid_list_item() -> None:
    with pytest.raises(TypeError, match="Expected FiveWhyStep or dict in list"):
        validate_five_why(["not a dict"])


def test_validate_five_why_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Expected FiveWhyChain, DataFrame"):
        validate_five_why(12345)


# ==============================================================================
# 2. 6M Fishbone (Cause-and-Effect) Suite
# ==============================================================================


@pytest.mark.parametrize("cat", CATEGORY_6M_VALUES)
def test_fishbone_cause_valid_canonical_categories(cat: Category6M) -> None:
    cause = FishboneCause(category=cat, cause="Sample cause")
    assert cause.category == cat
    assert cause.cause == "Sample cause"
    assert cause.sub_category is None


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("manpower", "Man"),
        ("Man Power", "Man"),
        ("man_power", "Man"),
        ("people", "Man"),
        ("personnel", "Man"),
        ("worker", "Man"),
        ("operators", "Man"),
        ("equipment", "Machine"),
        ("tools", "Machine"),
        ("machinery", "Machine"),
        ("technology", "Machine"),
        ("process", "Method"),
        ("procedure", "Method"),
        ("work method", "Method"),
        ("method of work", "Method"),
        ("raw material", "Material"),
        ("raw materials", "Material"),
        ("parts", "Material"),
        ("supplies", "Material"),
        ("inspection", "Measurement"),
        ("testing", "Measurement"),
        ("gage", "Measurement"),
        ("gauge", "Measurement"),
        ("measuring method", "Measurement"),
        ("mother nature", "Environment"),
        ("mother_nature", "Environment"),
        ("nature", "Environment"),
        ("surroundings", "Environment"),
        ("environmental", "Environment"),
        ("milieu", "Environment"),
    ],
)
def test_fishbone_cause_category_alias_normalization(alias: str, expected: Category6M) -> None:
    cause = FishboneCause(category=alias, cause="Alias test")  # type: ignore[arg-type]
    assert cause.category == expected


def test_fishbone_cause_category_case_insensitivity_and_whitespace() -> None:
    cause = FishboneCause(category="  mAchIne  ", cause="Noise")  # type: ignore[arg-type]
    assert cause.category == "Machine"


def test_fishbone_cause_rejects_blank_or_invalid_category() -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        FishboneCause(category="   ", cause="Noise")  # type: ignore[arg-type]

    with pytest.raises(pydantic.ValidationError, match="Invalid 6M category"):
        FishboneCause(category="Software", cause="Bug")  # type: ignore[arg-type]


def test_fishbone_cause_whitespace_stripping_and_blank_cause_rejected() -> None:
    cause = FishboneCause(
        category="Man",
        cause="  Operator fatigue  ",
        sub_category="  Shift work  ",
    )
    assert cause.cause == "Operator fatigue"
    assert cause.sub_category == "Shift work"

    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        FishboneCause(category="Man", cause="   ")


def test_fishbone_cause_sub_category_blank_coerced_to_none() -> None:
    cause1 = FishboneCause(category="Man", cause="Fatigue", sub_category="   ")
    assert cause1.sub_category is None

    cause2 = FishboneCause(category="Man", cause="Fatigue", sub_category=None)
    assert cause2.sub_category is None


def test_fishbone_cause_field_length_bounds() -> None:
    long_text = "x" * 2001
    with pytest.raises(pydantic.ValidationError):
        FishboneCause(category="Man", cause=long_text)
    with pytest.raises(pydantic.ValidationError):
        FishboneCause(category="Man", cause="Valid", sub_category=long_text)


def test_fishbone_dataset_valid() -> None:
    causes = [
        FishboneCause(category="Man", cause="Lack of training"),
        FishboneCause(category="Machine", cause="Bearing wear"),
        FishboneCause(category="Method", cause="Outdated SOP"),
    ]
    ds = FishboneDataset(effect="High defect rate", causes=causes)
    assert ds.effect == "High defect rate"
    assert len(ds.causes) == 3
    assert ds.rows == ds.causes


def test_fishbone_dataset_default_effect() -> None:
    ds = FishboneDataset(
        causes=[FishboneCause(category="Material", cause="Off-spec resin")]
    )
    assert ds.effect == "Problem Effect"


def test_fishbone_dataset_effect_whitespace_and_blank_rejection() -> None:
    ds = FishboneDataset(
        effect="  Excessive scrap  ",
        causes=[FishboneCause(category="Material", cause="Off-spec resin")],
    )
    assert ds.effect == "Excessive scrap"

    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        FishboneDataset(
            effect="   ",
            causes=[FishboneCause(category="Material", cause="Off-spec resin")],
        )


def test_fishbone_dataset_rejects_empty_causes() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one cause"):
        FishboneDataset(causes=[])


def test_fishbone_dataset_coerces_rows_to_causes_in_dict() -> None:
    data = {
        "effect": "Defect",
        "rows": [{"category": "Man", "cause": "Fatigue"}],
    }
    ds = FishboneDataset.model_validate(data)
    assert len(ds.causes) == 1
    assert ds.causes[0].category == "Man"


def test_fishbone_schema_properties() -> None:
    assert FISHBONE_SCHEMA.name == "Fishbone"
    assert FISHBONE_SCHEMA.required_columns == ("category", "cause")
    assert FISHBONE_SCHEMA.optional_columns == ("sub_category",)
    assert FISHBONE_SCHEMA.row_model is FishboneCause
    assert FISHBONE_SCHEMA.dataset_model is FishboneDataset
    assert FISHBONE_SCHEMA.template_hint == "data/fishbone_template.csv"


def test_load_fishbone_csv_from_buffer() -> None:
    rows = [
        {"category": "manpower", "cause": "Fatigue", "sub_category": "Night shift"},
        {"category": "Machine", "cause": "Vibration"},
    ]
    buf = _csv_buf(rows)
    df = load_fishbone_csv(buf)
    assert len(df) == 2
    assert "category" in df.columns
    assert "cause" in df.columns
    assert "sub_category" in df.columns


def test_load_fishbone_csv_from_path(tmp_path: Path) -> None:
    file_path = tmp_path / "test_fishbone.csv"
    df_in = pd.DataFrame(
        [
            {"category": "Man", "cause": "Fatigue", "extra_col": "discarded"},
            {"category": "Method", "cause": "Missing step", "extra_col": "discarded"},
        ]
    )
    df_in.to_csv(file_path, index=False)
    df_out = load_fishbone_csv(str(file_path))
    assert len(df_out) == 2
    assert "extra_col" not in df_out.columns


def test_load_fishbone_csv_missing_required_column_raises_ingest_error() -> None:
    rows = [{"category": "Man"}]  # missing "cause"
    buf = _csv_buf(rows)
    with pytest.raises(IngestError, match="Missing required column"):
        load_fishbone_csv(buf)


def test_load_fishbone_csv_empty_raises_ingest_error() -> None:
    buf = io.BytesIO(b"category,cause\n")
    buf.name = "empty_fishbone.csv"
    with pytest.raises(IngestError, match="No data rows found"):
        load_fishbone_csv(buf)


def test_validate_fishbone_from_dataset_passthrough() -> None:
    ds = FishboneDataset(causes=[FishboneCause(category="Man", cause="Fatigue")])
    validated = validate_fishbone(ds)
    assert validated is ds


def test_validate_fishbone_from_dataframe() -> None:
    df = pd.DataFrame(
        [
            {"category": "Man", "cause": "Fatigue", "sub_category": None},
            {"category": "Machine", "cause": "Worn gear", "sub_category": "Drive"},
        ]
    )
    ds = validate_fishbone(df, effect="Custom Effect")
    assert ds.effect == "Custom Effect"
    assert len(ds.causes) == 2
    assert ds.causes[1].sub_category == "Drive"


def test_validate_fishbone_from_list_of_causes() -> None:
    causes = [
        FishboneCause(category="Man", cause="Fatigue"),
        FishboneCause(category="Method", cause="Wrong temp"),
    ]
    ds = validate_fishbone(causes, effect="List Effect")
    assert ds.effect == "List Effect"
    assert len(ds.causes) == 2
    assert ds.causes[0] is causes[0]


def test_validate_fishbone_from_list_of_dicts() -> None:
    records = [
        {"category": "Material", "cause": "Off-spec"},
        {"category": "Measurement", "cause": "Uncalibrated"},
    ]
    ds = validate_fishbone(records)
    assert len(ds.causes) == 2
    assert ds.causes[0].category == "Material"


def test_validate_fishbone_from_dict() -> None:
    data = {
        "effect": "Dict Effect",
        "causes": [{"category": "Environment", "cause": "High humidity"}],
    }
    ds = validate_fishbone(data)
    assert ds.effect == "Dict Effect"
    assert len(ds.causes) == 1
    assert ds.causes[0].category == "Environment"


def test_validate_fishbone_rejects_invalid_list_item() -> None:
    with pytest.raises(TypeError, match="Expected FishboneCause or dict in list"):
        validate_fishbone(["invalid"])


def test_validate_fishbone_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Expected FishboneDataset, DataFrame"):
        validate_fishbone(99.9)


# ==============================================================================
# 3. Kepner-Tregoe Is/Is-Not Suite
# ==============================================================================


@pytest.mark.parametrize("dim", KT_DIMENSIONS)
def test_is_is_not_row_valid_dimensions(dim: KTDimension) -> None:
    row = IsIsNotRow(
        dimension=dim,
        is_data="Observed fact",
        is_not_data="Could be but is not",
        distinctions="Specific difference",
        changes="Recent change",
    )
    assert row.dimension == dim
    assert row.is_data == "Observed fact"
    assert row.is_not_data == "Could be but is not"
    assert row.distinctions == "Specific difference"
    assert row.changes == "Recent change"


def test_is_is_not_row_dimension_case_normalization() -> None:
    assert IsIsNotRow(dimension="what", is_data="X", is_not_data="Y").dimension == "WHAT"  # type: ignore[arg-type]
    assert IsIsNotRow(dimension="  Where  ", is_data="X", is_not_data="Y").dimension == "WHERE"  # type: ignore[arg-type]
    assert IsIsNotRow(dimension="When", is_data="X", is_not_data="Y").dimension == "WHEN"  # type: ignore[arg-type]
    assert IsIsNotRow(dimension="extent", is_data="X", is_not_data="Y").dimension == "EXTENT"  # type: ignore[arg-type]


def test_is_is_not_row_rejects_blank_or_invalid_dimension() -> None:
    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        IsIsNotRow(dimension="   ", is_data="X", is_not_data="Y")  # type: ignore[arg-type]

    with pytest.raises(pydantic.ValidationError, match="Invalid Kepner-Tregoe dimension"):
        IsIsNotRow(dimension="WHO", is_data="X", is_not_data="Y")  # type: ignore[arg-type]


def test_is_is_not_row_whitespace_stripping_and_blank_data_rejected() -> None:
    row = IsIsNotRow(
        dimension="WHAT",
        is_data="  Filter leaking  ",
        is_not_data="  Valve leaking  ",
        distinctions="  Gasket shape  ",
        changes="  New supplier  ",
    )
    assert row.is_data == "Filter leaking"
    assert row.is_not_data == "Valve leaking"
    assert row.distinctions == "Gasket shape"
    assert row.changes == "New supplier"

    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        IsIsNotRow(dimension="WHAT", is_data="   ", is_not_data="Valid")

    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        IsIsNotRow(dimension="WHAT", is_data="Valid", is_not_data="\t\n")


def test_is_is_not_row_optional_fields_blank_coerced_to_none() -> None:
    row = IsIsNotRow(
        dimension="WHAT",
        is_data="Filter leaking",
        is_not_data="Valve leaking",
        distinctions="   ",
        changes=None,
    )
    assert row.distinctions is None
    assert row.changes is None


def test_is_is_not_row_field_length_bounds() -> None:
    long_text = "x" * 2001
    with pytest.raises(pydantic.ValidationError):
        IsIsNotRow(dimension="WHAT", is_data=long_text, is_not_data="Valid")
    with pytest.raises(pydantic.ValidationError):
        IsIsNotRow(dimension="WHAT", is_data="Valid", is_not_data=long_text)
    with pytest.raises(pydantic.ValidationError):
        IsIsNotRow(dimension="WHAT", is_data="Valid", is_not_data="Valid", distinctions=long_text)
    with pytest.raises(pydantic.ValidationError):
        IsIsNotRow(dimension="WHAT", is_data="Valid", is_not_data="Valid", changes=long_text)


def test_is_is_not_matrix_valid_all_dimensions() -> None:
    rows = [
        IsIsNotRow(dimension="WHAT", is_data="Filter 1 leaking", is_not_data="Filters 2-5 leaking"),
        IsIsNotRow(dimension="WHERE", is_data="North wing", is_not_data="South wing"),
        IsIsNotRow(dimension="WHEN", is_data="Since Monday", is_not_data="Before Monday"),
        IsIsNotRow(dimension="EXTENT", is_data="2 liters/hr", is_not_data="10 liters/hr"),
    ]
    matrix = IsIsNotMatrix(problem_statement="Oil leak", rows=rows)
    assert matrix.problem_statement == "Oil leak"
    assert len(matrix.rows) == 4
    assert matrix.is_complete is True


def test_is_is_not_matrix_completeness_check() -> None:
    partial_rows = [
        IsIsNotRow(dimension="WHAT", is_data="Leak", is_not_data="No leak"),
        IsIsNotRow(dimension="WHERE", is_data="North", is_not_data="South"),
    ]
    matrix = IsIsNotMatrix(rows=partial_rows)
    assert matrix.is_complete is False


def test_is_is_not_matrix_default_problem_statement() -> None:
    matrix = IsIsNotMatrix(
        rows=[IsIsNotRow(dimension="WHAT", is_data="Leak", is_not_data="No leak")]
    )
    assert matrix.problem_statement == "Problem Statement"


def test_is_is_not_matrix_problem_statement_whitespace_and_blank_rejection() -> None:
    matrix = IsIsNotMatrix(
        problem_statement="  Hydraulic leak  ",
        rows=[IsIsNotRow(dimension="WHAT", is_data="Leak", is_not_data="No leak")],
    )
    assert matrix.problem_statement == "Hydraulic leak"

    with pytest.raises(pydantic.ValidationError, match="must not be blank"):
        IsIsNotMatrix(
            problem_statement="   ",
            rows=[IsIsNotRow(dimension="WHAT", is_data="Leak", is_not_data="No leak")],
        )


def test_is_is_not_matrix_rejects_empty_rows() -> None:
    with pytest.raises(pydantic.ValidationError, match="at least one row"):
        IsIsNotMatrix(rows=[])


def test_is_is_not_matrix_rejects_duplicate_dimensions() -> None:
    rows = [
        IsIsNotRow(dimension="WHAT", is_data="Leak 1", is_not_data="No leak"),
        IsIsNotRow(dimension="WHAT", is_data="Leak 2", is_not_data="No leak"),
    ]
    with pytest.raises(pydantic.ValidationError, match="duplicate dimensions found"):
        IsIsNotMatrix(rows=rows)


def test_is_is_not_schema_properties() -> None:
    assert IS_IS_NOT_SCHEMA.name == "Is/Is-Not"
    assert IS_IS_NOT_SCHEMA.required_columns == ("dimension", "is_data", "is_not_data")
    assert IS_IS_NOT_SCHEMA.optional_columns == ("distinctions", "changes")
    assert IS_IS_NOT_SCHEMA.row_model is IsIsNotRow
    assert IS_IS_NOT_SCHEMA.dataset_model is IsIsNotMatrix
    assert IS_IS_NOT_SCHEMA.template_hint == "data/is_is_not_template.csv"


def test_load_is_is_not_csv_from_buffer() -> None:
    rows = [
        {
            "dimension": "what",
            "is_data": "Leak",
            "is_not_data": "No leak",
            "distinctions": "Shape",
            "changes": "Supplier",
        },
        {"dimension": "where", "is_data": "North", "is_not_data": "South"},
    ]
    buf = _csv_buf(rows)
    df = load_is_is_not_csv(buf)
    assert len(df) == 2
    assert "dimension" in df.columns
    assert "is_data" in df.columns
    assert "is_not_data" in df.columns
    assert "distinctions" in df.columns
    assert "changes" in df.columns


def test_load_is_is_not_csv_from_path(tmp_path: Path) -> None:
    file_path = tmp_path / "test_is_is_not.csv"
    df_in = pd.DataFrame(
        [
            {
                "dimension": "WHAT",
                "is_data": "Leak",
                "is_not_data": "No leak",
                "extra": "ignored",
            }
        ]
    )
    df_in.to_csv(file_path, index=False)
    df_out = load_is_is_not_csv(str(file_path))
    assert len(df_out) == 1
    assert "extra" not in df_out.columns


def test_load_is_is_not_csv_missing_required_column_raises_ingest_error() -> None:
    rows = [{"dimension": "WHAT", "is_data": "Leak"}]  # missing "is_not_data"
    buf = _csv_buf(rows)
    with pytest.raises(IngestError, match="Missing required column"):
        load_is_is_not_csv(buf)


def test_load_is_is_not_csv_empty_raises_ingest_error() -> None:
    buf = io.BytesIO(b"dimension,is_data,is_not_data\n")
    buf.name = "empty_is_is_not.csv"
    with pytest.raises(IngestError, match="No data rows found"):
        load_is_is_not_csv(buf)


def test_validate_is_is_not_from_matrix_passthrough() -> None:
    matrix = IsIsNotMatrix(
        rows=[IsIsNotRow(dimension="WHAT", is_data="Leak", is_not_data="No leak")]
    )
    validated = validate_is_is_not(matrix)
    assert validated is matrix


def test_validate_is_is_not_from_dataframe() -> None:
    df = pd.DataFrame(
        [
            {
                "dimension": "WHAT",
                "is_data": "Leak",
                "is_not_data": "No leak",
                "distinctions": None,
                "changes": "New batch",
            },
            {
                "dimension": "WHERE",
                "is_data": "North",
                "is_not_data": "South",
                "distinctions": "Ventilation",
                "changes": None,
            },
        ]
    )
    matrix = validate_is_is_not(df, problem_statement="Custom KT Problem")
    assert matrix.problem_statement == "Custom KT Problem"
    assert len(matrix.rows) == 2
    assert matrix.rows[0].changes == "New batch"
    assert matrix.rows[1].distinctions == "Ventilation"


def test_validate_is_is_not_from_list_of_rows() -> None:
    rows = [
        IsIsNotRow(dimension="WHAT", is_data="Leak", is_not_data="No leak"),
        IsIsNotRow(dimension="WHEN", is_data="Morning", is_not_data="Night"),
    ]
    matrix = validate_is_is_not(rows, problem_statement="List Matrix")
    assert matrix.problem_statement == "List Matrix"
    assert len(matrix.rows) == 2
    assert matrix.rows[0] is rows[0]


def test_validate_is_is_not_from_list_of_dicts() -> None:
    records = [
        {"dimension": "WHAT", "is_data": "Leak", "is_not_data": "No leak"},
        {"dimension": "EXTENT", "is_data": "10 units", "is_not_data": "100 units"},
    ]
    matrix = validate_is_is_not(records)
    assert len(matrix.rows) == 2
    assert matrix.rows[1].dimension == "EXTENT"


def test_validate_is_is_not_from_dict() -> None:
    data = {
        "problem_statement": "Dict KT Problem",
        "rows": [{"dimension": "WHAT", "is_data": "Leak", "is_not_data": "No leak"}],
    }
    matrix = validate_is_is_not(data)
    assert matrix.problem_statement == "Dict KT Problem"
    assert len(matrix.rows) == 1
    assert matrix.rows[0].dimension == "WHAT"


def test_validate_is_is_not_rejects_invalid_list_item() -> None:
    with pytest.raises(TypeError, match="Expected IsIsNotRow or dict in list"):
        validate_is_is_not(["invalid"])


def test_validate_is_is_not_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Expected IsIsNotMatrix, DataFrame"):
        validate_is_is_not({"invalid_set_instead": {1, 2, 3}}["invalid_set_instead"])


# ==============================================================================
# 4. Branch Coverage & Edge-Case Completeness Suite
# ==============================================================================


def test_five_why_step_field_validator_non_string_passthrough() -> None:
    assert FiveWhyStep.reject_blank_step_fields(123) == 123


def test_five_why_chain_validators_non_string_and_none_passthrough() -> None:
    assert FiveWhyChain.reject_blank_problem_statement(123) == 123
    assert FiveWhyChain.reject_blank_root_cause(123) == 123
    assert FiveWhyChain.reject_blank_root_cause(None) is None


def test_five_why_chain_coerce_rows_to_steps_branches() -> None:
    assert FiveWhyChain._coerce_rows_to_steps("not a dict") == "not a dict"
    res = FiveWhyChain.model_validate(
        {
            "problem_statement": "Problem",
            "steps": [{"step_number": 1, "why": "Why", "because": "Because"}],
            "rows": [{"step_number": 1, "why": "Why2", "because": "Because2"}],
        }
    )
    assert res.steps[0].why == "Why"


def test_fishbone_cause_field_validator_non_string_passthrough() -> None:
    assert FishboneCause.normalize_category(123) == 123
    assert FishboneCause.reject_blank_cause(123) == 123
    assert FishboneCause.normalize_sub_category(123) == 123


def test_fishbone_dataset_field_validator_non_string_passthrough() -> None:
    assert FishboneDataset.reject_blank_effect(123) == 123


def test_fishbone_normalize_category_direct_value_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quality_core.rca.schema.CATEGORY_6M_ALIASES",
        {k: v for k, v in CATEGORY_6M_ALIASES.items() if k != "man"},
    )
    assert FishboneCause.normalize_category("Man") == "Man"


def test_fishbone_dataset_coerce_rows_to_causes_branches() -> None:
    assert FishboneDataset._coerce_rows_to_causes("not a dict") == "not a dict"
    res = FishboneDataset.model_validate(
        {
            "effect": "Effect",
            "causes": [{"category": "Man", "cause": "Fatigue"}],
            "rows": [{"category": "Machine", "cause": "Noise"}],
        }
    )
    assert res.causes[0].category == "Man"


def test_is_is_not_row_field_validator_non_string_passthrough() -> None:
    assert IsIsNotRow.normalize_dimension(123) == 123
    assert IsIsNotRow.reject_blank_data_fields(123) == 123
    assert IsIsNotRow.normalize_optional_fields(123) == 123


def test_is_is_not_matrix_field_validator_non_string_passthrough() -> None:
    assert IsIsNotMatrix.reject_blank_problem_statement(123) == 123


def test_nan_handling_in_all_validators() -> None:
    df_5w = pd.DataFrame([{"step_number": 1, "why": "Why", "because": "Because"}])
    res_5w = validate_five_why(df_5w)
    assert res_5w.root_cause is None

    dict_5w = {
        "problem_statement": "Problem",
        "steps": [{"step_number": 1, "why": "Why", "because": "Because"}],
        "root_cause": float("nan"),
    }
    res_dict_5w = validate_five_why(dict_5w)
    assert res_dict_5w.root_cause is None

    df_fb = pd.DataFrame([{"category": "Man", "cause": "Fatigue", "sub_category": float("nan")}])
    res_fb = validate_fishbone(df_fb)
    assert res_fb.causes[0].sub_category is None

    list_dict_fb = [{"category": "Man", "cause": "Fatigue", "sub_category": float("nan")}]
    res_list_dict_fb = validate_fishbone(list_dict_fb)
    assert res_list_dict_fb.causes[0].sub_category is None

    df_in = pd.DataFrame([{"dimension": "WHAT", "is_data": "Leak", "is_not_data": "No leak", "distinctions": float("nan"), "changes": float("nan")}])
    res_in = validate_is_is_not(df_in)
    assert res_in.rows[0].distinctions is None
    assert res_in.rows[0].changes is None

    list_dict_in = [{"dimension": "WHAT", "is_data": "Leak", "is_not_data": "No leak", "distinctions": float("nan"), "changes": float("nan")}]
    res_list_dict_in = validate_is_is_not(list_dict_in)
    assert res_list_dict_in.rows[0].distinctions is None
    assert res_list_dict_in.rows[0].changes is None



"""
Unit tests for deterministic 6M Fishbone (Ishikawa) categorizer and validation engine (quality_core.rca.fishbone).

Tests:
1. FishboneCategorizationResult dataclass construction and to_dict() serialization.
2. Positive controls:
   - Reference Sentinel-8D pneumatic cylinder case across all 6 branches (ACCEPT, 0 empty branches, 100% balance).
   - Reference Wave Soldering Bridging dataset across all 6 branches.
   - Categorization across all 6M canonical branches (Man, Machine, Method, Material, Measurement, Environment).
   - Normalization of all industry category aliases in CATEGORY_6M_ALIASES.
   - Input format polymorphism: FishboneDataset, pd.DataFrame, list of dicts, list of FishboneCause, dict with causes/rows, single cause dict.
   - Custom effect statement propagation.
   - Sub-category parsing and normalization.
   - Handling of check_balance=False and small cause counts (< 3).
3. Negative controls & anti-pattern detection:
   - Empty dataset handling: returns valid=False, verdict="REJECT", total_causes=0, 6 empty branches.
   - Empty branch / bare leg detection: returns valid=True, verdict="WARNING", lists empty branches with CQI-20 / Ishikawa recommendation.
   - Duplicate cause detection: duplicate cause strings within same branch or across branches flagged in duplicate_causes (verdict="WARNING").
   - Single-branch concentration balance check: >= 75% in one branch triggers warning & bias recommendation (verdict="WARNING"); < 75% passes.
   - Uncategorized / invalid categories: isolated in uncategorized_causes with warning (verdict="WARNING" or "REJECT").
4. Boundary and error conditions:
   - balance_threshold validation: rejects bool, non-numeric, <= 0.0, > 1.0.
   - effect_statement validation: rejects non-string or blank strings.
   - cause text validation: rejects non-string or blank/whitespace-only cause strings.
   - input type validation: rejects non-supported types (int, float, None, bool, etc.).
   - list item validation: rejects invalid types in list or causes/rows.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from quality_core.canvas.rca import SAMPLE_FISHBONE_CAUSES
from quality_core.rca.fishbone import (
    FishboneCategorizationResult,
    categorize_fishbone,
)
from quality_core.rca.schema import (
    CATEGORY_6M_VALUES,
    FishboneCause,
    FishboneDataset,
)

# ---------------------------------------------------------------------------
# Benchmark Data Fixtures
# ---------------------------------------------------------------------------

_SENTINEL_8D_CAUSES = SAMPLE_FISHBONE_CAUSES

_WAVE_SOLDER_CAUSES: list[dict[str, Any]] = [
    {"category": "Man", "cause": "Operator soldering speed too fast for preheat cycle", "sub_category": "Technique"},
    {"category": "Machine", "cause": "Solder wave height fluctuation exceeding +/- 0.5 mm", "sub_category": "Pump"},
    {"category": "Method", "cause": "Conveyor angle set to 5 degrees instead of required 7 degrees", "sub_category": "Setup"},
    {"category": "Material", "cause": "Flux specific gravity out of specification (low solids content)", "sub_category": "Chemical"},
    {"category": "Measurement", "cause": "Thermal profiler thermocouple detachment during conveyor run", "sub_category": "Instrumentation"},
    {"category": "Environment", "cause": "Exhaust ventilation duct velocity drop causing flux vapor condensation", "sub_category": "Ventilation"},
]


# ---------------------------------------------------------------------------
# 1. FishboneCategorizationResult Dataclass Unit Tests
# ---------------------------------------------------------------------------


def test_fishbone_categorization_result_construction_and_to_dict() -> None:
    """FishboneCategorizationResult constructs cleanly and serializes to dictionary."""
    result = FishboneCategorizationResult(
        basis="Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox",
        valid=True,
        verdict="ACCEPT",
        effect_statement="Stroke binding in pneumatic cylinder",
        total_causes=6,
        branch_counts={b: 1 for b in CATEGORY_6M_VALUES},
        grouped_causes={b: [{"category": b, "cause": f"{b} cause", "sub_category": None}] for b in CATEGORY_6M_VALUES},
        empty_branches=[],
        duplicate_causes=[],
        uncategorized_causes=[],
        warnings=[],
        recommendations=["Proceed with root cause verification."],
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_causes == 6
    assert len(result.empty_branches) == 0

    d = result.to_dict()
    assert d["basis"] == "Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox"
    assert d["valid"] is True
    assert d["verdict"] == "ACCEPT"
    assert d["effect_statement"] == "Stroke binding in pneumatic cylinder"
    assert d["total_causes"] == 6
    assert d["branch_counts"]["Man"] == 1
    assert len(d["grouped_causes"]["Machine"]) == 1
    assert d["empty_branches"] == []
    assert d["duplicate_causes"] == []
    assert d["uncategorized_causes"] == []
    assert d["warnings"] == []
    assert len(d["recommendations"]) == 1


# ---------------------------------------------------------------------------
# 2. Positive Controls & Normalization Unit Tests
# ---------------------------------------------------------------------------


def test_categorize_fishbone_sentinel_8d_case() -> None:
    """Positive Control: Sentinel-8D pneumatic cylinder case across all 6 branches yields ACCEPT."""
    result = categorize_fishbone(
        data=_SENTINEL_8D_CAUSES,
        effect_statement="Pneumatic cylinder functional defect (stroke binding & seal leakage)",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_causes == 12
    assert result.empty_branches == []
    assert len(result.duplicate_causes) == 0
    assert len(result.uncategorized_causes) == 0
    assert len(result.warnings) == 0
    assert all(result.branch_counts[b] == 2 for b in CATEGORY_6M_VALUES)
    assert len(result.recommendations) > 0


def test_categorize_fishbone_wave_solder_case() -> None:
    """Positive Control: Wave Soldering Bridging case with 1 cause per branch yields ACCEPT."""
    result = categorize_fishbone(
        data=_WAVE_SOLDER_CAUSES,
        effect_statement="Solder bridging defect on PCB SMT assembly",
    )

    assert result.valid is True
    assert result.verdict == "ACCEPT"
    assert result.total_causes == 6
    assert result.empty_branches == []
    assert all(result.branch_counts[b] == 1 for b in CATEGORY_6M_VALUES)


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("manpower", "Man"),
        ("Man Power", "Man"),
        ("man_power", "Man"),
        ("people", "Man"),
        ("personnel", "Man"),
        ("worker", "Man"),
        ("workers", "Man"),
        ("operator", "Man"),
        ("operators", "Man"),
        ("equipment", "Machine"),
        ("machines", "Machine"),
        ("tools", "Machine"),
        ("tooling", "Machine"),
        ("machinery", "Machine"),
        ("technology", "Machine"),
        ("hardware", "Machine"),
        ("process", "Method"),
        ("processes", "Method"),
        ("procedure", "Method"),
        ("procedures", "Method"),
        ("work method", "Method"),
        ("method of work", "Method"),
        ("raw material", "Material"),
        ("raw materials", "Material"),
        ("parts", "Material"),
        ("supply", "Material"),
        ("supplies", "Material"),
        ("measure", "Measurement"),
        ("measurements", "Measurement"),
        ("inspection", "Measurement"),
        ("testing", "Measurement"),
        ("gage", "Measurement"),
        ("gauge", "Measurement"),
        ("metrology", "Measurement"),
        ("measuring method", "Measurement"),
        ("milieu", "Environment"),
        ("mother nature", "Environment"),
        ("mother_nature", "Environment"),
        ("nature", "Environment"),
        ("surroundings", "Environment"),
        ("environmental", "Environment"),
    ],
)
def test_categorize_fishbone_category_alias_normalization(alias: str, canonical: str) -> None:
    """All known aliases in CATEGORY_6M_ALIASES are mapped to canonical 6M categories."""
    data = [{"category": alias, "cause": f"Test cause for {alias}"}]
    result = categorize_fishbone(data=data, effect_statement="Alias test")

    assert result.branch_counts[canonical] == 1
    assert result.grouped_causes[canonical][0]["cause"] == f"Test cause for {alias}"
    assert len(result.uncategorized_causes) == 0


def test_categorize_fishbone_input_polymorphism() -> None:
    """categorize_fishbone ingests FishboneDataset, pd.DataFrame, list[dict], list[FishboneCause], and dict."""
    raw_list = [
        {"category": "Man", "cause": "Operator error", "sub_category": "Training"},
        {"category": "Machine", "cause": "Spindle runout", "sub_category": "Tooling"},
        {"category": "Method", "cause": "No standard torque", "sub_category": "Process"},
        {"category": "Material", "cause": "Seal hardness out of spec", "sub_category": "Raw Material"},
        {"category": "Measurement", "cause": "Gage uncalibrated", "sub_category": "Calibration"},
        {"category": "Environment", "cause": "Ambient temperature fluctuation", "sub_category": "HVAC"},
    ]

    # 1. list[dict]
    r1 = categorize_fishbone(raw_list, effect_statement="Polymorphism Test")
    assert r1.total_causes == 6
    assert r1.verdict == "ACCEPT"

    # 2. list[FishboneCause]
    causes_objs = [FishboneCause(**item) for item in raw_list]
    r2 = categorize_fishbone(causes_objs, effect_statement="Polymorphism Test")
    assert r2.total_causes == 6
    assert r2.verdict == "ACCEPT"

    # 3. FishboneDataset
    dataset = FishboneDataset(effect="Polymorphism Test", causes=causes_objs)
    r3 = categorize_fishbone(dataset)
    assert r3.total_causes == 6
    assert r3.effect_statement == "Polymorphism Test"
    assert r3.verdict == "ACCEPT"

    # 4. pd.DataFrame (including NaN handling)
    df = pd.DataFrame(raw_list)
    df.loc[0, "sub_category"] = float("nan")  # NaN sub_category
    r4 = categorize_fishbone(df, effect_statement="Polymorphism Test")
    assert r4.total_causes == 6
    assert r4.grouped_causes["Man"][0]["sub_category"] is None
    assert r4.verdict == "ACCEPT"

    # 5. dict with "causes"
    dict_causes = {"effect": "Polymorphism Test", "causes": raw_list}
    r5 = categorize_fishbone(dict_causes)
    assert r5.total_causes == 6
    assert r5.verdict == "ACCEPT"

    # 6. dict with "rows"
    dict_rows = {"effect": "Polymorphism Test", "rows": causes_objs}
    r6 = categorize_fishbone(dict_rows)
    assert r6.total_causes == 6
    assert r6.verdict == "ACCEPT"

    # 7. single cause dict
    single_dict = {"category": "Man", "cause": "Solo cause"}
    r7 = categorize_fishbone(single_dict)
    assert r7.total_causes == 1
    assert r7.branch_counts["Man"] == 1


def test_categorize_fishbone_canonical_category_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When CATEGORY_6M_ALIASES does not contain lowercase key, canonical CATEGORY_6M_VALUES matches."""
    import quality_core.rca.fishbone as fb_mod

    monkeypatch.setattr(fb_mod, "CATEGORY_6M_ALIASES", {})
    res = fb_mod.categorize_fishbone([{"category": "Man", "cause": "Direct canonical category"}])
    assert res.branch_counts["Man"] == 1
    assert res.grouped_causes["Man"][0]["cause"] == "Direct canonical category"


def test_categorize_fishbone_sub_category_variations() -> None:
    """Sub-categories are cleaned and whitespace stripped, or None if blank."""
    data = [
        {"category": "Man", "cause": "Cause 1", "sub_category": "  Shift Handover  "},
        {"category": "Machine", "cause": "Cause 2", "sub_category": "   "},
        {"category": "Method", "cause": "Cause 3", "sub_category": None},
    ]
    res = categorize_fishbone(data)
    assert res.grouped_causes["Man"][0]["sub_category"] == "Shift Handover"
    assert res.grouped_causes["Machine"][0]["sub_category"] is None
    assert res.grouped_causes["Method"][0]["sub_category"] is None


def test_categorize_fishbone_check_balance_flag_and_small_count() -> None:
    """Balance check can be disabled or skipped when total valid causes < 3."""
    # 2 causes in Man (100% in Man, but N < 3 -> no balance warning)
    data_small = [
        {"category": "Man", "cause": "Cause 1"},
        {"category": "Man", "cause": "Cause 2"},
    ]
    res_small = categorize_fishbone(data_small, check_balance=True)
    assert not any("Branch concentration imbalance" in w for w in res_small.warnings)

    # 4 causes in Man (100% in Man, N >= 3, check_balance=False -> no balance warning)
    data_four = [
        {"category": "Man", "cause": f"Cause {i}"} for i in range(1, 5)
    ]
    res_no_check = categorize_fishbone(data_four, check_balance=False)
    assert not any("Branch concentration imbalance" in w for w in res_no_check.warnings)


# ---------------------------------------------------------------------------
# 3. Negative Controls & Anti-Pattern Detection
# ---------------------------------------------------------------------------


def test_categorize_fishbone_empty_dataset_rejection() -> None:
    """Negative Control: Empty dataset returns valid=False, verdict=REJECT, and all 6 branches empty."""
    res = categorize_fishbone([])
    assert res.valid is False
    assert res.verdict == "REJECT"
    assert res.total_causes == 0
    assert len(res.empty_branches) == 6
    assert "Fishbone dataset contains no causes." in res.warnings[0]
    assert len(res.recommendations) > 0


def test_categorize_fishbone_empty_branch_warning() -> None:
    """Negative Control: Dataset missing some 6M branches triggers WARNING verdict with bare leg advice."""
    data = [
        {"category": "Man", "cause": "Operator fatigued"},
        {"category": "Machine", "cause": "Spindle misaligned"},
    ]
    res = categorize_fishbone(data)
    assert res.valid is True
    assert res.verdict == "WARNING"
    assert len(res.empty_branches) == 4
    assert "Method" in res.empty_branches
    assert "Material" in res.empty_branches
    assert "Measurement" in res.empty_branches
    assert "Environment" in res.empty_branches
    assert any("Empty branches detected" in w for w in res.warnings)
    assert any("AIAG CQI-20" in w for w in res.warnings)


def test_categorize_fishbone_duplicate_causes_detection() -> None:
    """Negative Control: Duplicate cause strings (within same branch or across branches) are detected."""
    data = [
        {"category": "Man", "cause": "Inadequate training on tie-rod torquing"},
        {"category": "Method", "cause": "  inadequate training on tie-rod torquing  "},  # Duplicate across branch
        {"category": "Machine", "cause": "Lathe spindle runout"},
        {"category": "Machine", "cause": "Lathe spindle runout"},  # Duplicate within branch
        {"category": "Material", "cause": "Seal hardness out of spec"},
        {"category": "Measurement", "cause": "Gage calibration drift"},
        {"category": "Environment", "cause": "Ambient temperature variation"},
    ]
    res = categorize_fishbone(data)
    assert res.valid is True
    assert res.verdict == "WARNING"
    assert len(res.duplicate_causes) == 2
    assert res.duplicate_causes[0]["category"] == "Method"
    assert res.duplicate_causes[0]["duplicate_of_category"] == "Man"
    assert res.duplicate_causes[1]["category"] == "Machine"
    assert any("duplicate cause entries" in w for w in res.warnings)


def test_categorize_fishbone_branch_concentration_balance_warning() -> None:
    """Negative Control: Single-branch concentration >= balance_threshold (default 0.75) triggers WARNING."""
    # 4 causes in Man, 1 in Machine -> 4/5 = 80% >= 75%
    data = [
        {"category": "Man", "cause": "Operator fatigue"},
        {"category": "Man", "cause": "Operator distraction"},
        {"category": "Man", "cause": "Operator lack of experience"},
        {"category": "Man", "cause": "Operator hurried shift handover"},
        {"category": "Machine", "cause": "Fixture loose"},
    ]
    res = categorize_fishbone(data, balance_threshold=0.75)
    assert res.valid is True
    assert res.verdict == "WARNING"
    assert any("Branch concentration imbalance: 'Man'" in w for w in res.warnings)
    assert any("80.0%" in w for w in res.warnings)
    assert any("tunnel vision" in w for w in res.warnings)
    assert any("Broaden brainstorming" in r for r in res.recommendations)

    # 3 causes across 6M balanced -> passes balance check (each < 75%)
    data_balanced = [
        {"category": "Man", "cause": "Operator fatigue"},
        {"category": "Machine", "cause": "Fixture loose"},
        {"category": "Method", "cause": "Procedure vague"},
    ]
    res_bal = categorize_fishbone(data_balanced, balance_threshold=0.75)
    # Still warning for empty branches (Material, Measurement, Environment), but NO concentration warning
    assert not any("Branch concentration imbalance" in w for w in res_bal.warnings)


def test_categorize_fishbone_uncategorized_causes() -> None:
    """Negative Control: Causes with unrecognized categories are isolated in uncategorized_causes."""
    data = [
        {"category": "Software", "cause": "Null pointer exception in controller"},
        {"category": None, "cause": "Unknown failure mode"},
    ]
    res = categorize_fishbone(data)
    assert res.valid is False
    assert res.verdict == "REJECT"
    assert len(res.uncategorized_causes) == 2
    assert res.uncategorized_causes[0]["category"] == "Software"
    assert res.uncategorized_causes[1]["category"] == "None"
    assert any("invalid/unrecognized categories" in w for w in res.warnings)

    # Mixed valid + uncategorized
    mixed_data = [
        {"category": "Man", "cause": "Operator fatigue"},
        {"category": "UnknownCategory", "cause": "Mysterious glitch"},
    ]
    res_mixed = categorize_fishbone(mixed_data)
    assert res_mixed.valid is True
    assert res_mixed.verdict == "WARNING"
    assert len(res_mixed.uncategorized_causes) == 1


# ---------------------------------------------------------------------------
# 4. Boundary and Error Handling Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_threshold",
    [
        0.0,
        -0.25,
        1.5,
        True,
        False,
        "0.75",
        None,
    ],
)
def test_categorize_fishbone_rejects_invalid_balance_threshold(bad_threshold: Any) -> None:
    """categorize_fishbone raises ValueError when balance_threshold is not a float in (0, 1]."""
    with pytest.raises(ValueError, match="balance_threshold must be a float between 0 and 1"):
        categorize_fishbone(data=_SENTINEL_8D_CAUSES, balance_threshold=bad_threshold)


@pytest.mark.parametrize(
    "bad_effect",
    [
        "",
        "   ",
        123,
        True,
    ],
)
def test_categorize_fishbone_rejects_invalid_effect_statement(bad_effect: Any) -> None:
    """categorize_fishbone raises ValueError or TypeError when effect_statement is invalid."""
    with pytest.raises((ValueError, TypeError)):
        categorize_fishbone(data=_SENTINEL_8D_CAUSES, effect_statement=bad_effect)


@pytest.mark.parametrize(
    "bad_data",
    [
        12345,
        None,
        3.14,
        True,
        "raw string",
    ],
)
def test_categorize_fishbone_rejects_unsupported_data_type(bad_data: Any) -> None:
    """categorize_fishbone raises TypeError for unsupported data types."""
    with pytest.raises(TypeError, match="Expected FishboneDataset, DataFrame"):
        categorize_fishbone(data=bad_data)


def test_categorize_fishbone_rejects_invalid_list_items() -> None:
    """categorize_fishbone raises TypeError when a list contains non-dict / non-FishboneCause items."""
    with pytest.raises(TypeError, match="Expected FishboneCause or dict in list at index 0"):
        categorize_fishbone(data=["not-a-dict"])  # type: ignore[list-item]

    with pytest.raises(TypeError, match="Expected FishboneCause or dict in list at index 1"):
        categorize_fishbone(data=[{"category": "Man", "cause": "Valid"}, 12345])  # type: ignore[list-item]


def test_categorize_fishbone_dict_with_invalid_causes_type() -> None:
    """categorize_fishbone raises TypeError when dict 'causes' or 'rows' is not a list."""
    with pytest.raises(TypeError, match="Expected list for causes/rows in dict"):
        categorize_fishbone(data={"effect": "Test", "causes": "not-a-list"})

    with pytest.raises(TypeError, match="Expected FishboneCause or dict in causes list at index 0"):
        categorize_fishbone(data={"effect": "Test", "causes": ["not-a-dict"]})


def test_categorize_fishbone_rejects_blank_or_invalid_cause_text() -> None:
    """categorize_fishbone raises ValueError or TypeError when cause description is blank or not a string."""
    with pytest.raises(ValueError, match="Cause at index 0 must be a non-empty string"):
        categorize_fishbone(data=[{"category": "Man", "cause": "   "}])

    with pytest.raises(ValueError, match="Cause at index 0 must be a non-empty string"):
        categorize_fishbone(data=[{"category": "Man", "cause": None}])

    with pytest.raises(TypeError, match="Cause at index 0 must be a string"):
        categorize_fishbone(data=[{"category": "Man", "cause": 12345}])

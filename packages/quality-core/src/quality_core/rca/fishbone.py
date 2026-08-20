"""
fishbone.py
Deterministic 6M Fishbone (Cause-and-Effect / Ishikawa) categorizer and validation engine.

Implements canonical 6M taxonomy assignment (Man, Machine, Method, Material, Measurement,
Environment), industry category alias normalization, empty branch / bare leg detection per
Ishikawa (1986) & AIAG CQI-20 Section G1 (RULE 1), multi-category cause placement per ASQ
Quality Toolbox (RULE 5), duplicate cause detection, branch concentration balance auditing
(internal design heuristic), and actionable recommendations generation.

Standards References:
- Kaoru Ishikawa, Guide to Quality Control (2nd Revised Edition, 1986), Chapter 3.
- AIAG CQI-20 Effective Problem Solving Guide (2nd Edition, 2018), Section G1 & Figure 34.
- Nancy R. Tague, The Quality Toolbox (2nd Edition, ASQ Quality Press, 2005), Chapter 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

import pandas as pd

from quality_core.rca.schema import (
    CATEGORY_6M_ALIASES,
    CATEGORY_6M_VALUES,
    Category6M,
    FishboneCause,
    FishboneDataset,
)

__all__ = [
    "FishboneCategorizationResult",
    "categorize_fishbone",
]

_STANDARDS_BASIS = "Ishikawa (1986) / AIAG CQI-20 / ASQ Quality Toolbox"


@dataclass
class FishboneCategorizationResult:
    """Structured result of 6M Fishbone cause-and-effect categorization and validation."""

    basis: str
    valid: bool
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    effect_statement: str
    total_causes: int
    branch_counts: dict[str, int]
    grouped_causes: dict[str, list[dict[str, Any]]]
    empty_branches: list[str]
    duplicate_causes: list[dict[str, Any]]
    uncategorized_causes: list[dict[str, Any]]
    warnings: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return serializable dictionary representation of categorization result."""
        return {
            "basis": self.basis,
            "valid": self.valid,
            "verdict": self.verdict,
            "effect_statement": self.effect_statement,
            "total_causes": self.total_causes,
            "branch_counts": dict(self.branch_counts),
            "grouped_causes": {k: list(v) for k, v in self.grouped_causes.items()},
            "empty_branches": list(self.empty_branches),
            "duplicate_causes": list(self.duplicate_causes),
            "uncategorized_causes": list(self.uncategorized_causes),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
        }


def categorize_fishbone(
    data: Any,
    effect_statement: str | None = None,
    check_balance: bool = True,
    balance_threshold: float = 0.75,
) -> FishboneCategorizationResult:
    """Categorize, validate, and audit a 6M Fishbone cause-and-effect dataset.

    Normalizes cause categories across the canonical 6M taxonomy (Man, Machine,
    Method, Material, Measurement, Environment), detects empty branches / bare legs
    per Ishikawa (1986) & AIAG CQI-20 Section G1, identifies duplicate causes,
    audits branch concentration balance against `balance_threshold`, and provides
    structured recommendations.

    Parameters
    ----------
    data : Any
        Untrusted Fishbone dataset: FishboneDataset, pd.DataFrame, list of dicts/causes, or dict.
    effect_statement : str | None, optional
        Problem effect statement being investigated. If None, inferred from dataset or defaults to 'Problem Effect'.
    check_balance : bool, default True
        Whether to perform branch concentration balance check (flagging single-branch concentration >= threshold).
    balance_threshold : float, default 0.75
        Fractional threshold (0.0 to 1.0) above which a single branch triggers an imbalance warning when total causes >= 3.

    Returns
    -------
    FishboneCategorizationResult
        Structured categorization and audit output containing verdict, branch counts,
        grouped causes, empty branches, duplicate causes, warnings, and recommendations.

    Raises
    ------
    TypeError
        If data is not a supported type (e.g. integer, None, float) or causes list contains invalid items.
    ValueError
        If balance_threshold is not between 0 and 1, or cause text is blank.
    """
    if isinstance(balance_threshold, bool) or not isinstance(balance_threshold, (int, float)) or not (0.0 < balance_threshold <= 1.0):
        raise ValueError(f"balance_threshold must be a float between 0 and 1, got {balance_threshold!r}")

    effective_effect: str
    raw_causes: list[dict[str, Any]]

    if isinstance(data, FishboneDataset):
        effective_effect = effect_statement if effect_statement is not None else data.effect
        raw_causes = [c.model_dump() for c in data.causes]
    elif isinstance(data, pd.DataFrame):
        effective_effect = effect_statement if effect_statement is not None else "Problem Effect"
        raw_causes = [
            cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in row.items()})
            for row in data.to_dict("records")
        ]
    elif isinstance(data, list):
        effective_effect = effect_statement if effect_statement is not None else "Problem Effect"
        raw_causes = []
        for idx, item in enumerate(data):
            if isinstance(item, FishboneCause):
                raw_causes.append(item.model_dump())
            elif isinstance(item, dict):
                clean_rec = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in item.items()})
                raw_causes.append(clean_rec)
            else:
                raise TypeError(f"Expected FishboneCause or dict in list at index {idx}, got {type(item).__name__}")
    elif isinstance(data, dict):
        if "causes" in data or "rows" in data:
            effective_effect = effect_statement if effect_statement is not None else data.get("effect", "Problem Effect")
            items = data.get("causes", data.get("rows", []))
            if not isinstance(items, list):
                raise TypeError(f"Expected list for causes/rows in dict, got {type(items).__name__}")
            raw_causes = []
            for idx, item in enumerate(items):
                if isinstance(item, FishboneCause):
                    raw_causes.append(item.model_dump())
                elif isinstance(item, dict):
                    clean_rec = cast("dict[str, Any]", {k: (None if pd.isna(v) else v) for k, v in item.items()})
                    raw_causes.append(clean_rec)
                else:
                    raise TypeError(f"Expected FishboneCause or dict in causes list at index {idx}, got {type(item).__name__}")
        else:
            effective_effect = effect_statement if effect_statement is not None else "Problem Effect"
            raw_causes = [dict(data)]
    else:
        raise TypeError(f"Expected FishboneDataset, DataFrame, list of dicts/causes, or dict, got {type(data).__name__}")

    if not isinstance(effective_effect, str) or not effective_effect.strip():
        raise ValueError("effect_statement must be a non-empty string")
    effective_effect = effective_effect.strip()

    # Initialize 6M containers
    branch_counts: dict[str, int] = {b: 0 for b in CATEGORY_6M_VALUES}
    grouped_causes: dict[str, list[dict[str, Any]]] = {b: [] for b in CATEGORY_6M_VALUES}
    empty_branches: list[str] = []
    duplicate_causes: list[dict[str, Any]] = []
    uncategorized_causes: list[dict[str, Any]] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    if len(raw_causes) == 0:
        return FishboneCategorizationResult(
            basis=_STANDARDS_BASIS,
            valid=False,
            verdict="REJECT",
            effect_statement=effective_effect,
            total_causes=0,
            branch_counts=branch_counts,
            grouped_causes=grouped_causes,
            empty_branches=list(CATEGORY_6M_VALUES),
            duplicate_causes=[],
            uncategorized_causes=[],
            warnings=["Fishbone dataset contains no causes."],
            recommendations=["Populate brainstormed causes across the 6M categories (Man, Machine, Method, Material, Measurement, Environment)."],
        )

    seen_causes: dict[str, str] = {}
    valid_causes_count = 0

    for idx, item in enumerate(raw_causes):
        # Extract fields
        raw_cat = item.get("category", item.get("Category", item.get("branch", item.get("Branch"))))
        raw_cause = item.get("cause", item.get("Cause", item.get("description", item.get("Description", item.get("text", item.get("Text"))))))
        raw_sub = item.get("sub_category", item.get("SubCategory", item.get("subcategory", item.get("Subcategory"))))

        if raw_cause is None or (isinstance(raw_cause, str) and not raw_cause.strip()):
            raise ValueError(f"Cause at index {idx} must be a non-empty string")
        if not isinstance(raw_cause, str):
            raise TypeError(f"Cause at index {idx} must be a string, got {type(raw_cause).__name__}")

        cause_text = raw_cause.strip()
        sub_category = raw_sub.strip() if isinstance(raw_sub, str) and raw_sub.strip() else None

        # Normalize category
        norm_cat: Category6M | None = None
        if isinstance(raw_cat, str) and raw_cat.strip():
            cat_clean = raw_cat.strip()
            cat_lower = cat_clean.lower()
            if cat_lower in CATEGORY_6M_ALIASES:
                norm_cat = CATEGORY_6M_ALIASES[cat_lower]
            elif cat_clean in CATEGORY_6M_VALUES:
                norm_cat = cast(Category6M, cat_clean)

        if norm_cat is not None:
            cause_entry: dict[str, Any] = {
                "category": norm_cat,
                "cause": cause_text,
                "sub_category": sub_category,
            }
            # Duplicate check
            norm_key = cause_text.lower()
            if norm_key in seen_causes:
                duplicate_causes.append({
                    "category": norm_cat,
                    "cause": cause_text,
                    "sub_category": sub_category,
                    "duplicate_of_category": seen_causes[norm_key],
                })
            else:
                seen_causes[norm_key] = norm_cat

            grouped_causes[norm_cat].append(cause_entry)
            branch_counts[norm_cat] += 1
            valid_causes_count += 1
        else:
            uncategorized_causes.append({
                "category": str(raw_cat) if raw_cat is not None else "None",
                "cause": cause_text,
                "sub_category": sub_category,
                "reason": f"Category '{raw_cat}' is not a recognized 6M category or alias.",
            })

    # Empty branch detection per Ishikawa (1986) & AIAG CQI-20
    empty_branches = [b for b in CATEGORY_6M_VALUES if branch_counts[b] == 0]

    # Branch concentration / balance audit
    if check_balance and valid_causes_count >= 3:
        for b in CATEGORY_6M_VALUES:
            cnt = branch_counts[b]
            frac = cnt / valid_causes_count
            if frac >= balance_threshold:
                warnings.append(
                    f"Branch concentration imbalance: '{b}' contains {cnt}/{valid_causes_count} ({frac:.1%}) "
                    f"of total causes (threshold: {balance_threshold:.0%}). Consider broadening brainstorming across "
                    f"other 6M branches to prevent tunnel vision."
                )
                recommendations.append(
                    f"Broaden brainstorming across underrepresented branches ({', '.join(empty_branches) if empty_branches else 'other categories'}) "
                    f"to avoid single-branch bias."
                )

    if empty_branches and valid_causes_count > 0:
        warnings.append(
            f"Empty branches detected: {', '.join(empty_branches)}. "
            f"Ishikawa (1986) and AIAG CQI-20 recommend exploring bare legs to ensure no critical failure causes are overlooked."
        )
        recommendations.append(
            f"Review bare branches ({', '.join(empty_branches)}) with the cross-functional team to identify potential latent causes per AIAG CQI-20 Section G1."
        )

    if duplicate_causes:
        warnings.append(f"Detected {len(duplicate_causes)} duplicate cause entries across fishbone branches.")
        recommendations.append(
            "Consolidate duplicate cause entries or clarify distinct sub-mechanisms across categories per ASQ Quality Toolbox (p. 248)."
        )

    if uncategorized_causes:
        warnings.append(f"Detected {len(uncategorized_causes)} causes with invalid/unrecognized categories.")
        recommendations.append(
            f"Reassign uncategorized causes to the canonical 6M taxonomy ({', '.join(CATEGORY_6M_VALUES)})."
        )

    # Determine verdict and overall validity
    total_all_causes = valid_causes_count + len(uncategorized_causes)
    verdict: Literal["ACCEPT", "WARNING", "REJECT"]
    if valid_causes_count == 0:
        verdict = "REJECT"
        valid = False
    elif warnings:
        verdict = "WARNING"
        valid = True
    else:
        verdict = "ACCEPT"
        valid = True
        recommendations.append(
            "6M Fishbone diagram is well-balanced across all categories. Proceed to prioritize high-potential causes for 5-Why root cause analysis or verification testing."
        )

    return FishboneCategorizationResult(
        basis=_STANDARDS_BASIS,
        valid=valid,
        verdict=verdict,
        effect_statement=effective_effect,
        total_causes=total_all_causes,
        branch_counts=branch_counts,
        grouped_causes=grouped_causes,
        empty_branches=empty_branches,
        duplicate_causes=duplicate_causes,
        uncategorized_causes=uncategorized_causes,
        warnings=warnings,
        recommendations=recommendations,
    )

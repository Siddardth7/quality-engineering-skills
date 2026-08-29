"""
AIAG PPAP 4th Edition (June 2006) Section 2.2.11: Initial Process Studies Capability Gate.

Evaluates initial process capability / performance studies against the AIAG acceptance criteria
(§2.2.11.3), enforces stability gates (§2.2.11.4), prevents misuse on attribute data (§2.2.11.1 Note 2),
enforces sample adequacy thresholds (§2.2.11.1 Note 5), and attaches verbatim standard-mandated actions.

Reuses statistical primitives directly from `quality_core.spc` (no duplicated formulas).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from quality_core.spc.capability import compute_capability_study
from quality_core.spc.stability import stability_fields

__all__ = [
    "ACCEPTANCE_THRESHOLD_CAPABLE",
    "ACCEPTANCE_THRESHOLD_POTENTIALLY_CAPABLE",
    "ACTION_ATTRIBUTE_DATA",
    "ACTION_BETWEEN_1_33_AND_1_67",
    "ACTION_GREATER_THAN_1_67",
    "ACTION_INSUFFICIENT_SAMPLE",
    "ACTION_LESS_THAN_1_33",
    "ACTION_UNSTABLE",
    "AcceptanceBand",
    "IndexType",
    "MINIMUM_INITIAL_STUDY_SAMPLES",
    "MINIMUM_INITIAL_STUDY_SUBGROUPS",
    "ProcessStudyResult",
    "StudyVerdict",
    "assess_initial_process_study",
]

StudyVerdict = Literal[
    "ACCEPTABLE",
    "POTENTIALLY_ACCEPTABLE",
    "UNACCEPTABLE",
    "INDETERMINATE",
    "NOT_APPLICABLE_ATTRIBUTE_DATA",
]

AcceptanceBand = Literal[
    "GREATER_THAN_1_67",
    "BETWEEN_1_33_AND_1_67",
    "LESS_THAN_1_33",
]

IndexType = Literal["Ppk", "Cpk"]

# Constants from AIAG PPAP 4th Edition §2.2.11
MINIMUM_INITIAL_STUDY_SAMPLES = 100
MINIMUM_INITIAL_STUDY_SUBGROUPS = 25
ACCEPTANCE_THRESHOLD_CAPABLE = 1.67
ACCEPTANCE_THRESHOLD_POTENTIALLY_CAPABLE = 1.33

# Verbatim standard-prescribed actions from AIAG PPAP 4th Edition §2.2.11
ACTION_GREATER_THAN_1_67 = "The process currently meets the acceptance criteria."
ACTION_BETWEEN_1_33_AND_1_67 = (
    "The process may be acceptable. Contact the authorized customer representative "
    "for a review of the study results."
)
ACTION_LESS_THAN_1_33 = (
    "The process does not currently meet the acceptance criteria. Contact the authorized "
    "customer representative for a review of the study results. The organization shall "
    "submit to the authorized customer representative for approval a corrective action "
    "plan and a modified Control Plan normally providing for 100% inspection. Variation "
    "reduction efforts shall continue until the acceptance criteria are met, or until "
    "customer approval is received."
)
ACTION_UNSTABLE = (
    "Process is not in statistical control. The organization shall identify, evaluate and, "
    "wherever possible, eliminate special causes of variation prior to PPAP submission. "
    "The organization shall notify the authorized customer representative of any unstable "
    "processes that exist and shall submit a corrective action plan to the customer prior "
    "to any submission."
)
ACTION_ATTRIBUTE_DATA = (
    "Unless approved by the authorized customer representative, attribute data are not "
    "acceptable for PPAP submissions. To understand the performance of characteristics "
    "monitored by attribute data will require more data collected over time."
)
ACTION_INSUFFICIENT_SAMPLE = (
    "When not enough data are available (< 100 samples / < 25 subgroups) or there are "
    "unknown sources of variation, contact the authorized customer representative to "
    "develop a suitable plan."
)


@dataclass(frozen=True)
class ProcessStudyResult:
    """Evaluation result for an Initial Process Study under AIAG PPAP 4th Edition §2.2.11."""

    verdict: StudyVerdict
    index_type: IndexType | None
    index_value: float | None
    band: AcceptanceBand | None
    required_action: str
    rationales: tuple[str, ...]
    citations: tuple[str, ...]
    stable: bool | None
    violations: tuple[dict[str, Any], ...] | None
    sample_size: int
    subgroup_count: int | None
    is_attribute: bool
    customer_concurrence: bool | None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a standard JSON-serializable dictionary."""
        d = asdict(self)
        d["rationales"] = list(self.rationales)
        d["citations"] = list(self.citations)
        if self.violations is not None:
            d["violations"] = list(self.violations)
        return d


def assess_initial_process_study(
    data: list[float] | list[list[float]] | np.ndarray | None = None,
    lsl: float | None = None,
    usl: float | None = None,
    *,
    is_attribute: bool = False,
    is_ongoing_stable_process: bool = False,
    violations: Sequence[Mapping[str, int | str]] | None = None,
    customer_concurrence: bool = False,
    custom_threshold_capable: float = ACCEPTANCE_THRESHOLD_CAPABLE,
    custom_threshold_potentially_capable: float = ACCEPTANCE_THRESHOLD_POTENTIALLY_CAPABLE,
    alpha: float = 0.05,
    precomputed_index_type: IndexType | None = None,
    precomputed_index_value: float | None = None,
    precomputed_sample_size: int | None = None,
    precomputed_subgroup_count: int | None = None,
) -> ProcessStudyResult:
    """Assess an Initial Process Study against AIAG PPAP 4th Edition §2.2.11 criteria.

    Args:
        data: 1D array of individual measurements or 2D array of subgroups.
        lsl: Lower specification limit (optional for unilateral specs).
        usl: Upper specification limit (optional for unilateral specs).
        is_attribute: Flag indicating attribute data (rejects capability indices).
        is_ongoing_stable_process: When True, uses Cpk (within-subgroup); otherwise Ppk (total).
        violations: Control-chart out-of-control signals from stability assessment.
        customer_concurrence: Flag indicating customer concurrence for small samples or substitutions.
        custom_threshold_capable: Threshold for ACCEPTABLE verdict (default 1.67).
        custom_threshold_potentially_capable: Threshold for POTENTIALLY_ACCEPTABLE (default 1.33).
        alpha: Significance level for statistical intervals (default 0.05).
        precomputed_index_type: Optional precomputed index type ('Ppk' or 'Cpk') when data is omitted.
        precomputed_index_value: Optional precomputed index value when data is omitted.
        precomputed_sample_size: Optional precomputed sample size when data is omitted.
        precomputed_subgroup_count: Optional precomputed subgroup count when data is omitted.

    Returns:
        ProcessStudyResult containing the verdict, index, acceptance band, required action,
        and standards citations.

    Raises:
        ValueError: If neither data nor precomputed values are provided, or if spec limits are invalid.
    """
    # 1. Attribute Data Guard (§2.2.11.1 Note 2)
    if is_attribute:
        return ProcessStudyResult(
            verdict="NOT_APPLICABLE_ATTRIBUTE_DATA",
            index_type=None,
            index_value=None,
            band=None,
            required_action=ACTION_ATTRIBUTE_DATA,
            rationales=(
                "Attribute data (e.g. defect counts, pass/fail) cannot yield variables capability indices (Ppk/Cpk).",
                "AIAG PPAP 4th Edition §2.2.11.1 Note 2 prohibits attribute data for initial studies unless approved by customer.",
            ),
            citations=("AIAG PPAP 4th Edition §2.2.11.1 Note 2",),
            stable=None,
            violations=None,
            sample_size=0 if data is None else int(np.asarray(data).reshape(-1).size),
            subgroup_count=None if data is None or np.asarray(data).ndim < 2 else len(data),
            is_attribute=True,
            customer_concurrence=customer_concurrence,
        )

    # 2. Extract Sample Structure and Raw/Precomputed Metrics
    sample_size: int
    subgroup_count: int | None = None
    index_type: IndexType
    index_val: float | None = None
    stable: bool | None
    stability_note: str | None

    violations_tuple = tuple(dict(v) for v in violations) if violations is not None else None
    stable, stability_note = stability_fields(violations)

    if data is not None:
        shaped = np.asarray(data, dtype=float)
        if shaped.ndim not in (1, 2):
            raise ValueError("data must be 1D individual readings or 2D subgroups.")
        flat = shaped.reshape(-1)
        sample_size = int(flat.size)
        if shaped.ndim == 2:
            subgroup_count = int(shaped.shape[0])

        if lsl is None and usl is None:
            raise ValueError("At least one specification limit (LSL or USL) must be provided.")
        if lsl is not None and usl is not None and lsl >= usl:
            raise ValueError(f"LSL ({lsl}) must be strictly less than USL ({usl}).")

        # 3. Insufficient Sample Guard (§2.2.11.1 Note 5, §2.2.11.2)
        insufficient_n = sample_size < MINIMUM_INITIAL_STUDY_SAMPLES
        insufficient_k = (
            subgroup_count is not None and subgroup_count < MINIMUM_INITIAL_STUDY_SUBGROUPS
        )
        if (insufficient_n or insufficient_k) and not customer_concurrence:
            subgroup_note = (
                f", subgroups={subgroup_count} < {MINIMUM_INITIAL_STUDY_SUBGROUPS}"
                if subgroup_count
                else ""
            )
            return ProcessStudyResult(
                verdict="INDETERMINATE",
                index_type=None,
                index_value=None,
                band=None,
                required_action=ACTION_INSUFFICIENT_SAMPLE,
                rationales=(
                    f"Sample size inadequate for initial study (n={sample_size} < {MINIMUM_INITIAL_STUDY_SAMPLES}{subgroup_note}).",
                    "AIAG PPAP 4th Edition §2.2.11.1 Note 5 requires minimum 25 subgroups / 100 readings without customer concurrence.",
                ),
                citations=(
                    "AIAG PPAP 4th Edition §2.2.11.1 Note 5",
                    "AIAG PPAP 4th Edition §2.2.11.2",
                ),
                stable=stable,
                violations=violations_tuple,
                sample_size=sample_size,
                subgroup_count=subgroup_count,
                is_attribute=False,
                customer_concurrence=customer_concurrence,
            )

        # 4. Compute capability using quality_core.spc
        study = compute_capability_study(
            data=shaped,
            lsl=lsl,
            usl=usl,
            alpha=alpha,
            violations=violations,
        )

        if is_ongoing_stable_process:
            index_type = "Cpk"
            index_val = study["cpk"]
        else:
            index_type = "Ppk"
            index_val = study["ppk"]

    elif precomputed_index_type is not None:
        index_type = precomputed_index_type
        index_val = precomputed_index_value
        sample_size = precomputed_sample_size if precomputed_sample_size is not None else 100
        subgroup_count = precomputed_subgroup_count
    else:
        raise ValueError(
            "Must provide either 'data' with spec limits or 'precomputed_index_type' with 'precomputed_index_value'."
        )

    # 5. Stability Gate (§2.2.11.4)
    if stable is False or (violations is not None and len(violations) > 0):
        signal_count = len(violations) if violations is not None else 0
        return ProcessStudyResult(
            verdict="INDETERMINATE",
            index_type=index_type,
            index_value=index_val,
            band=None,
            required_action=ACTION_UNSTABLE,
            rationales=(
                f"Process is out of control ({signal_count} stability signal(s) detected).",
                "AIAG PPAP 4th Edition §2.2.11.4 requires eliminating special causes and submitting a corrective action plan.",
            ),
            citations=("AIAG PPAP 4th Edition §2.2.11.4",),
            stable=False,
            violations=violations_tuple,
            sample_size=sample_size,
            subgroup_count=subgroup_count,
            is_attribute=False,
            customer_concurrence=customer_concurrence,
        )

    if index_val is None:
        raise ValueError("Failed to compute capability index value.")

    # 6. Acceptance Band Evaluation (§2.2.11.3)
    band: AcceptanceBand
    verdict: StudyVerdict
    action: str
    citations_list: list[str]

    if index_val > custom_threshold_capable:
        band = "GREATER_THAN_1_67"
        verdict = "ACCEPTABLE"
        action = ACTION_GREATER_THAN_1_67
        citations_list = [
            "AIAG PPAP 4th Edition §2.2.11.3 (Table 2.2.11.3: Index > 1.67)",
        ]
        rationale = f"{index_type} = {index_val:.4f} > {custom_threshold_capable}: Process meets acceptance criteria."
    elif index_val >= custom_threshold_potentially_capable:
        band = "BETWEEN_1_33_AND_1_67"
        verdict = "POTENTIALLY_ACCEPTABLE"
        action = ACTION_BETWEEN_1_33_AND_1_67
        citations_list = [
            "AIAG PPAP 4th Edition §2.2.11.3 (Table 2.2.11.3: 1.33 <= Index <= 1.67)",
        ]
        rationale = (
            f"{custom_threshold_potentially_capable} <= {index_type} = {index_val:.4f} <= "
            f"{custom_threshold_capable}: Process may be acceptable; customer review required."
        )
    else:
        band = "LESS_THAN_1_33"
        verdict = "UNACCEPTABLE"
        action = ACTION_LESS_THAN_1_33
        citations_list = [
            "AIAG PPAP 4th Edition §2.2.11.3 (Table 2.2.11.3: Index < 1.33)",
            "AIAG PPAP 4th Edition §2.2.11.6 (Actions when criteria not satisfied)",
        ]
        rationale = (
            f"{index_type} = {index_val:.4f} < {custom_threshold_potentially_capable}: "
            "Process does not meet acceptance criteria; corrective action plan and 100% inspection required."
        )

    index_rationale = f"Used {index_type} based on " + (
        "demonstrated stable historical process (§2.2.11.2)."
        if is_ongoing_stable_process
        else "initial process study short-term data (§2.2.11.2)."
    )

    return ProcessStudyResult(
        verdict=verdict,
        index_type=index_type,
        index_value=float(index_val),
        band=band,
        required_action=action,
        rationales=(rationale, index_rationale),
        citations=tuple(citations_list),
        stable=stable,
        violations=violations_tuple,
        sample_size=sample_size,
        subgroup_count=subgroup_count,
        is_attribute=False,
        customer_concurrence=customer_concurrence,
    )
